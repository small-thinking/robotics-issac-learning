"""Run one isolated DOFBOT actuator diagnostic case in Isaac Lab.

The runner has no table, cube, camera, policy, or hardware backend.  It records
the complete API -> interpolated target -> Isaac target buffer -> articulation
state path every physics step.  Windowed position difference is the physical
settling signal; raw joint velocity is retained as a compatibility signal.
"""

# Isaac Lab modules must be imported after AppLauncher starts Kit.
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from isaaclab.app import AppLauncher

from dofbot_actuator_calibration import (
    ActuatorCalibrationError,
    GRAVITY_FEED_FORWARD_CASE_NAMES,
    calibration_trajectory_extrema,
    evaluate_calibration_case,
    load_actuator_calibration_config,
    position_derived_velocity_deg_s,
    velocity_signal_mismatch_deg_s,
)
from dofbot_gravity_feed_forward import (
    REQUIRED_GRAVITY_RUNTIME_APIS,
    GravityFeedForwardError,
    evaluate_gravity_feed_forward_telemetry,
    prepare_bounded_gravity_feed_forward,
)

parser = argparse.ArgumentParser(
    description="Run one fail-closed DOFBOT actuator calibration case."
)
parser.add_argument(
    "--asset-contract",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/artifacts/dofbot/asset_contract.json"
    ),
)
parser.add_argument(
    "--calibration-config",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/configs/dofbot/calibration/"
        "goal5_actuator_diagnostic.json"
    ),
)
parser.add_argument("--case-name", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--git-commit", default=None)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

preflight_config, preflight_config_sha256 = load_actuator_calibration_config(
    args_cli.calibration_config
)
preflight_case = preflight_config.case(args_cli.case_name)

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch
import warp as wp

import isaaclab.sim as sim_utils
import omni.physx
from isaaclab.scene import InteractiveScene
from isaaclab_physx.physics import PhysxCfg
from pxr import PhysicsSchemaTools, UsdPhysics

from dofbot_contact_report import maximum_monitored_contact_force_n
from dofbot_control_api import (
    CONTROLLED_JOINT_NAMES,
    DofbotArm,
    JointPositionCommand,
    YahboomServoApiAdapter,
)
from dofbot_motion_plan import (
    assert_compatible_asset_contracts,
    validate_recorded_asset_contract,
)
from dofbot_pregrasp_scene_cfg import (
    CONTACT_BODY_PATHS,
    DofbotPregraspSceneCfg,
)

TERMINAL_BODY_NAMES = (
    "Wrist_Twist",
    "Finger_Left_03",
    "Finger_Right_03",
)
CONTROLLED_JOINT_PRIM_PATHS = {
    "joint1": "/World/envs/env_0/Dofbot/base_link/joint1",
    "joint2": "/World/envs/env_0/Dofbot/link1/joint2",
    "joint3": "/World/envs/env_0/Dofbot/link2/joint3",
    "joint4": "/World/envs/env_0/Dofbot/link3/joint4",
}
CONTROLLED_CHILD_BODY_NAMES = ("link1", "link2", "link3", "link4")


def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ActuatorCalibrationError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _first_env_row(tensor: torch.Tensor) -> list[Any]:
    return tensor[0].detach().cpu().tolist()


def _live_asset_contract(scene: InteractiveScene) -> dict[str, Any]:
    robot = scene["dofbot"]
    joint_pos_limits = getattr(robot.data, "joint_pos_limits", None)
    if joint_pos_limits is None:
        joint_pos_limits = robot.data.soft_joint_pos_limits
    return {
        "articulation": {
            "joint_names": list(robot.joint_names),
            "default_joint_positions_rad": _first_env_row(
                robot.data.default_joint_pos
            ),
            "joint_position_limits_rad": _first_env_row(joint_pos_limits),
        }
    }


def _controlled_joint_ids(scene: InteractiveScene) -> list[int]:
    robot = scene["dofbot"]
    name_to_index = {name: index for index, name in enumerate(robot.joint_names)}
    missing = [name for name in CONTROLLED_JOINT_NAMES if name not in name_to_index]
    if missing:
        raise ActuatorCalibrationError(
            f"live articulation is missing joints: {missing}"
        )
    return [name_to_index[name] for name in CONTROLLED_JOINT_NAMES]


def _terminal_body_ids(scene: InteractiveScene) -> dict[str, int]:
    names = list(scene["dofbot"].body_names)
    name_to_index = {name: index for index, name in enumerate(names)}
    missing = [name for name in TERMINAL_BODY_NAMES if name not in name_to_index]
    if missing:
        raise ActuatorCalibrationError(
            f"live articulation is missing terminal bodies: {missing}"
        )
    return {name: name_to_index[name] for name in TERMINAL_BODY_NAMES}


def _controlled_child_body_ids(scene: InteractiveScene) -> list[int]:
    names = list(scene["dofbot"].body_names)
    name_to_index = {name: index for index, name in enumerate(names)}
    missing = [
        name for name in CONTROLLED_CHILD_BODY_NAMES if name not in name_to_index
    ]
    if missing:
        raise ActuatorCalibrationError(
            f"live articulation is missing controlled child bodies: {missing}"
        )
    return [name_to_index[name] for name in CONTROLLED_CHILD_BODY_NAMES]


class _IsaacJointPositionBackend:
    """Execute one smooth complete-pose command and expose its target state."""

    def __init__(
        self,
        *,
        scene: InteractiveScene,
        controlled_joint_ids: list[int],
        device: str,
    ) -> None:
        self._robot = scene["dofbot"]
        self._joint_ids = controlled_joint_ids
        self._device = device
        self._pending_goal: tuple[float, ...] | None = None
        self._pending_duration_s: float | None = None
        self._start: tuple[float, ...] | None = None
        self._goal: tuple[float, ...] | None = None
        self._target: tuple[float, ...] | None = None
        self._duration_s = 0.0
        self._elapsed_s = 0.0

    @property
    def trajectory_complete(self) -> bool:
        return (
            self._goal is not None
            and self._elapsed_s >= self._duration_s - 1.0e-12
        )

    @property
    def interpolated_target_rad(self) -> tuple[float, ...] | None:
        return self._target

    def command_joint_positions(self, command: JointPositionCommand) -> None:
        self._pending_goal = tuple(command.positions_rad)
        self._pending_duration_s = command.duration_ms / 1000.0

    def advance(self, physics_dt: float) -> None:
        if self._pending_goal is not None:
            current = (
                self._robot.data.joint_pos[0, self._joint_ids]
                .detach()
                .cpu()
                .tolist()
            )
            self._start = tuple(float(value) for value in current)
            self._goal = self._pending_goal
            self._duration_s = self._pending_duration_s or physics_dt
            self._elapsed_s = 0.0
            self._pending_goal = None
            self._pending_duration_s = None
        if self._start is None or self._goal is None:
            return
        self._elapsed_s = min(
            self._elapsed_s + physics_dt,
            self._duration_s,
        )
        progress = self._elapsed_s / self._duration_s
        smooth = progress * progress * (3.0 - 2.0 * progress)
        self._target = tuple(
            start + (goal - start) * smooth
            for start, goal in zip(self._start, self._goal, strict=True)
        )
        self._robot.set_joint_position_target(
            torch.tensor(
                [self._target],
                device=self._device,
                dtype=torch.float32,
            ),
            joint_ids=self._joint_ids,
        )

    def read_joint_positions(self) -> dict[str, float]:
        values = (
            self._robot.data.joint_pos[0, self._joint_ids]
            .detach()
            .cpu()
            .tolist()
        )
        return dict(zip(CONTROLLED_JOINT_NAMES, values, strict=True))


class _BoundedGravityFeedForward:
    """Apply bounded generalized-gravity effort after Isaac writes PD targets."""

    def __init__(
        self,
        *,
        scene: InteractiveScene,
        controlled_joint_ids: list[int],
        controlled_child_body_ids: list[int],
        enabled: bool,
        maximum_effort: float,
        device: str,
    ) -> None:
        self._robot = scene["dofbot"]
        self._view = getattr(self._robot, "root_view", None)
        if self._view is None:
            raise GravityFeedForwardError(
                "root_view is unavailable"
            )
        self._controlled_joint_ids = controlled_joint_ids
        self._controlled_child_body_ids = controlled_child_body_ids
        self._enabled = enabled
        self._maximum_effort = maximum_effort
        self._device = device
        self._dof_count = len(self._robot.joint_names)
        self._body_count = len(self._robot.body_names)
        self.api_availability = {
            name: callable(getattr(self._view, name, None))
            for name in REQUIRED_GRAVITY_RUNTIME_APIS
        }
        if not all(self.api_availability.values()):
            missing = [
                name
                for name, available in self.api_availability.items()
                if not available
            ]
            raise GravityFeedForwardError(
                f"required gravity runtime APIs are unavailable: {missing}"
            )
        # Isaac Lab 3.0's PhysX articulation view is backed by the Warp
        # frontend even though the public articulation state is exposed as
        # Torch tensors.  Raw view setters therefore require native Warp
        # arrays for both data and indices.
        self._indices = wp.array(
            [0],
            device=self._device,
            dtype=wp.int32,
        )
        # Probe every required API and write a zero vector before any API pose
        # command. This fails closed on incompatible Isaac/PhysX releases.
        self._gravity_matrix()
        self._incoming_joint_force_matrix()
        self._write_actuation_forces([0.0] * self._dof_count)

    def _write_actuation_forces(self, efforts: list[float]) -> None:
        if len(efforts) != self._dof_count:
            raise GravityFeedForwardError(
                "actuation force width does not match the articulation"
            )
        self._view.set_dof_actuation_forces(
            wp.array(
                [efforts],
                device=self._device,
                dtype=wp.float32,
            ),
            self._indices,
        )

    def _tensor(
        self,
        value: Any,
        *,
        label: str,
        shape: tuple[int, ...],
    ) -> torch.Tensor:
        try:
            if hasattr(value, "detach"):
                tensor = value.detach().to(
                    device=self._device,
                    dtype=torch.float32,
                )
            elif hasattr(value, "numpy"):
                tensor = torch.as_tensor(
                    value.numpy(),
                    device=self._device,
                    dtype=torch.float32,
                )
            elif hasattr(value, "tolist"):
                tensor = torch.tensor(
                    value.tolist(),
                    device=self._device,
                    dtype=torch.float32,
                )
            else:
                tensor = torch.tensor(
                    value,
                    device=self._device,
                    dtype=torch.float32,
                )
            if tensor.numel() != math.prod(shape):
                raise GravityFeedForwardError(
                    f"{label} has {tensor.numel()} values, expected "
                    f"{math.prod(shape)}"
                )
            tensor = tensor.reshape(shape)
            if not bool(torch.isfinite(tensor).all()):
                raise GravityFeedForwardError(
                    f"{label} contains non-finite values"
                )
            return tensor
        except GravityFeedForwardError:
            raise
        except Exception as error:
            raise GravityFeedForwardError(
                f"{label} cannot be converted to a finite tensor: "
                f"{type(error).__name__}: {error}"
            ) from error

    def _gravity_matrix(self) -> torch.Tensor:
        value = self._view.get_gravity_compensation_forces()
        return self._tensor(
            value,
            label="gravity compensation forces",
            shape=(1, self._dof_count),
        )

    def _incoming_joint_force_matrix(self) -> torch.Tensor:
        value = self._view.get_link_incoming_joint_force()
        return self._tensor(
            value,
            label="incoming joint forces",
            shape=(1, self._body_count, 6),
        )

    def apply_before_step(self) -> dict[str, Any]:
        gravity = self._gravity_matrix()[0].detach().cpu().tolist()
        prepared = prepare_bounded_gravity_feed_forward(
            gravity_compensation_efforts=gravity,
            dof_count=self._dof_count,
            controlled_joint_ids=self._controlled_joint_ids,
            enabled=self._enabled,
            maximum_effort=self._maximum_effort,
        )
        self._write_actuation_forces(
            prepared["applied_all_dof_efforts"]
        )
        return prepared

    def read_controlled_incoming_joint_forces(self) -> list[list[float]]:
        incoming = self._incoming_joint_force_matrix()[0]
        return [
            [
                float(value)
                for value in incoming[body_id].detach().cpu().tolist()
            ]
            for body_id in self._controlled_child_body_ids
        ]


class _CriticalContactReporter:
    """Accumulate monitored contact impulses between observation reads."""

    def __init__(self, physics_dt: float) -> None:
        self._physics_dt = physics_dt
        self._critical_paths = frozenset(CONTACT_BODY_PATHS)
        self._maximum_force_n_since_read = 0.0
        self._subscription = (
            omni.physx.get_physx_simulation_interface()
            .subscribe_contact_report_events(self._on_contact_report)
        )

    def _on_contact_report(self, headers: Any, contact_data: Any) -> None:
        force_n = maximum_monitored_contact_force_n(
            headers=headers,
            contact_data=contact_data,
            critical_paths=self._critical_paths,
            physics_dt=self._physics_dt,
            decode_path=lambda value: str(
                PhysicsSchemaTools.intToSdfPath(value)
            ),
        )
        self._maximum_force_n_since_read = max(
            self._maximum_force_n_since_read,
            force_n,
        )

    def maximum_force_n(self) -> float:
        maximum = self._maximum_force_n_since_read
        self._maximum_force_n_since_read = 0.0
        return maximum


def _angles_deg_from_rad(values: list[float] | tuple[float, ...]) -> list[float]:
    return [90.0 + math.degrees(float(value)) for value in values]


def _velocity_deg_s(values: list[float] | tuple[float, ...]) -> list[float]:
    return [math.degrees(float(value)) for value in values]


def _optional_joint_buffer(
    scene: InteractiveScene,
    controlled_joint_ids: list[int],
    name: str,
) -> list[float] | None:
    tensor = getattr(scene["dofbot"].data, name, None)
    if tensor is None:
        return None
    try:
        return [
            float(value)
            for value in (
                tensor[0, controlled_joint_ids].detach().cpu().tolist()
            )
        ]
    except (AttributeError, IndexError, TypeError):
        return None


def _optional_physx_view_tensor(
    scene: InteractiveScene,
    method_name: str,
    probe_errors: dict[str, str],
) -> Any:
    view = getattr(scene["dofbot"], "root_physx_view", None)
    method = getattr(view, method_name, None)
    if method is None:
        probe_errors[method_name] = "accessor_unavailable"
        return None
    try:
        value = method()
        if hasattr(value, "detach"):
            value = value.detach().cpu()
        if hasattr(value, "numpy"):
            value = value.numpy()
        if hasattr(value, "tolist"):
            value = value.tolist()
        json.dumps(value)
        return value
    # These probes are diagnostic-only and vary across Isaac/PhysX releases.
    # A missing or incompatible optional accessor must become explicit null
    # telemetry instead of aborting the required control-path measurements.
    except Exception as error:
        probe_errors[method_name] = f"{type(error).__name__}: {error}"
        return None


def _controlled_joint_drive_snapshot() -> dict[str, dict[str, Any]]:
    stage = sim_utils.get_current_stage()
    snapshot: dict[str, dict[str, Any]] = {}
    for name, path in CONTROLLED_JOINT_PRIM_PATHS.items():
        prim = stage.GetPrimAtPath(path)
        joint = UsdPhysics.RevoluteJoint(prim)
        drive = UsdPhysics.DriveAPI.Get(prim, "angular")
        if not prim.IsValid() or not joint or not drive:
            raise ActuatorCalibrationError(
                f"missing revolute joint or angular drive at {path}"
            )
        snapshot[name] = {
            "prim_path": path,
            "axis": str(joint.GetAxisAttr().Get()),
            "body0": [str(value) for value in joint.GetBody0Rel().GetTargets()],
            "body1": [str(value) for value in joint.GetBody1Rel().GetTargets()],
            "drive_type": str(drive.GetTypeAttr().Get()),
            "max_force": float(drive.GetMaxForceAttr().Get()),
            "stiffness": float(drive.GetStiffnessAttr().Get()),
            "damping": float(drive.GetDampingAttr().Get()),
        }
    return snapshot


def _body_positions_world_m(
    scene: InteractiveScene,
    body_ids: dict[str, int],
) -> dict[str, list[float]]:
    robot = scene["dofbot"]
    return {
        name: [
            float(value)
            for value in (
                robot.data.body_pos_w[0, body_id].detach().cpu().tolist()
            )
        ]
        for name, body_id in body_ids.items()
    }


def _issue_pose(
    *,
    yahboom_api: YahboomServoApiAdapter,
    angles_deg: tuple[int, int, int, int],
    duration_ms: int,
) -> int:
    for servo_id, angle_deg in enumerate(angles_deg, start=1):
        yahboom_api.Arm_serial_servo_write(
            servo_id,
            angle_deg,
            duration_ms,
        )
    return len(angles_deg)


def _write_result(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sample(
    *,
    scene: InteractiveScene,
    backend: _IsaacJointPositionBackend,
    controlled_joint_ids: list[int],
    body_ids: dict[str, int],
    contact_reporter: _CriticalContactReporter,
    pose_name: str,
    pose_step: int,
    elapsed_s: float,
    api_command_angles_deg: tuple[int, int, int, int],
    gravity_feed_forward: dict[str, Any] | None,
) -> dict[str, Any]:
    robot = scene["dofbot"]
    observed_rad = [
        float(value)
        for value in (
            robot.data.joint_pos[0, controlled_joint_ids]
            .detach()
            .cpu()
            .tolist()
        )
    ]
    actual_velocity_rad_s = _optional_joint_buffer(
        scene,
        controlled_joint_ids,
        "joint_vel",
    )
    backend_target = backend.interpolated_target_rad
    joint_pos_target = _optional_joint_buffer(
        scene,
        controlled_joint_ids,
        "joint_pos_target",
    )
    joint_vel_target = _optional_joint_buffer(
        scene,
        controlled_joint_ids,
        "joint_vel_target",
    )
    computed_torque = _optional_joint_buffer(
        scene,
        controlled_joint_ids,
        "computed_torque",
    )
    applied_torque = _optional_joint_buffer(
        scene,
        controlled_joint_ids,
        "applied_torque",
    )
    return {
        "pose_name": pose_name,
        "pose_step": pose_step,
        "elapsed_s": elapsed_s,
        "api_command_angles_deg": list(api_command_angles_deg),
        "backend_interpolated_target_angles_deg": (
            _angles_deg_from_rad(backend_target)
            if backend_target is not None
            else None
        ),
        "joint_pos_target_angles_deg": (
            _angles_deg_from_rad(joint_pos_target)
            if joint_pos_target is not None
            else None
        ),
        "joint_vel_target_deg_s": (
            _velocity_deg_s(joint_vel_target)
            if joint_vel_target is not None
            else None
        ),
        "observed_joint_angles_deg": _angles_deg_from_rad(observed_rad),
        "observed_joint_velocities_deg_s": (
            _velocity_deg_s(actual_velocity_rad_s)
            if actual_velocity_rad_s is not None
            else None
        ),
        "joint_stiffness": _optional_joint_buffer(
            scene,
            controlled_joint_ids,
            "joint_stiffness",
        ),
        "joint_damping": _optional_joint_buffer(
            scene,
            controlled_joint_ids,
            "joint_damping",
        ),
        "joint_effort_limits": _optional_joint_buffer(
            scene,
            controlled_joint_ids,
            "joint_effort_limits",
        ),
        "computed_torque": computed_torque,
        "applied_torque": applied_torque,
        "critical_contact_force_n": contact_reporter.maximum_force_n(),
        "gravity_feed_forward": gravity_feed_forward,
        "body_positions_world_m": _body_positions_world_m(
            scene,
            body_ids,
        ),
    }


def _maximum_target_buffer_error(samples: list[dict[str, Any]]) -> float:
    errors: list[float] = []
    for sample in samples:
        backend_target = sample["backend_interpolated_target_angles_deg"]
        target_buffer = sample["joint_pos_target_angles_deg"]
        if backend_target is None or target_buffer is None:
            continue
        errors.extend(
            abs(float(actual) - float(expected))
            for actual, expected in zip(
                target_buffer,
                backend_target,
                strict=True,
            )
        )
    return max(errors, default=0.0)


def _maximum_overshoot(
    *,
    samples: list[dict[str, Any]],
    start_angles_deg: list[float],
    target_angles_deg: tuple[int, int, int, int],
) -> float:
    maximum = 0.0
    for sample in samples:
        observed = sample["observed_joint_angles_deg"]
        for start, target, value in zip(
            start_angles_deg,
            target_angles_deg,
            observed,
            strict=True,
        ):
            direction = math.copysign(1.0, target - start) if target != start else 0.0
            if direction:
                maximum = max(
                    maximum,
                    (float(value) - target) * direction,
                )
            else:
                maximum = max(maximum, abs(float(value) - target))
    return max(0.0, maximum)


def _torque_metrics(
    *,
    samples: list[dict[str, Any]],
    effort_limit_sim: float,
    interpretation: str,
) -> dict[str, Any]:
    buffers_shape_match = all(
        len(sample["computed_torque"] or [])
        == len(sample["applied_torque"] or [])
        for sample in samples
    )
    computed_values = [
        abs(float(value))
        for sample in samples
        for value in (sample["computed_torque"] or [])
    ]
    applied_values = [
        abs(float(value))
        for sample in samples
        for value in (sample["applied_torque"] or [])
    ]
    gaps = [
        abs(float(computed) - float(applied))
        for sample in samples
        for computed, applied in zip(
            sample["computed_torque"] or [],
            sample["applied_torque"] or [],
            strict=False,
        )
    ]
    maximum_computed = max(computed_values, default=0.0)
    maximum_applied = max(applied_values, default=0.0)
    maximum_gap = max(gaps, default=0.0)
    estimated_clip_reached = (
        interpretation == "implicit_pd_estimate_not_measured_solver_torque"
        and maximum_applied >= 0.98 * effort_limit_sim
        and maximum_gap > 1.0e-6
    )
    return {
        "maximum_absolute_computed_torque": maximum_computed,
        "maximum_absolute_applied_torque": maximum_applied,
        "maximum_absolute_computed_applied_gap": maximum_gap,
        "configured_effort_limit_sim": effort_limit_sim,
        "estimated_clip_reached": estimated_clip_reached,
        "saturation_observed": False,
        "buffers_shape_match": buffers_shape_match,
        "criterion": (
            "Isaac Lab implicit-actuator PD estimate reached 98% of the "
            "configured limit; this is not measured PhysX solver torque"
        ),
    }


def _run_pose(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    backend: _IsaacJointPositionBackend,
    yahboom_api: YahboomServoApiAdapter,
    controlled_joint_ids: list[int],
    body_ids: dict[str, int],
    contact_reporter: _CriticalContactReporter,
    pose_name: str,
    target_angles_deg: tuple[int, int, int, int],
    duration_ms: int,
    settle_velocity_threshold_deg_s: float,
    settle_hold_ms: int,
    settle_timeout_ms: int,
    position_velocity_window_ms: int,
    maximum_velocity_signal_mismatch_deg_s: float,
    gravity_feed_forward: _BoundedGravityFeedForward | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    robot = scene["dofbot"]
    start_angles_deg = _angles_deg_from_rad(
        [
            float(value)
            for value in (
                robot.data.joint_pos[0, controlled_joint_ids]
                .detach()
                .cpu()
                .tolist()
            )
        ]
    )
    api_calls = _issue_pose(
        yahboom_api=yahboom_api,
        angles_deg=target_angles_deg,
        duration_ms=duration_ms,
    )
    physics_dt = sim.get_physics_dt()
    maximum_elapsed_s = (duration_ms + settle_timeout_ms) / 1000.0
    required_stable_s = settle_hold_ms / 1000.0
    elapsed_s = 0.0
    stable_s = 0.0
    samples: list[dict[str, Any]] = []
    settled = False
    stable_mismatches: list[float] = []
    while elapsed_s < maximum_elapsed_s - 1.0e-12:
        if not simulation_app.is_running():
            raise ActuatorCalibrationError(
                f"simulation stopped during calibration pose {pose_name}"
            )
        backend.advance(physics_dt)
        scene.write_data_to_sim()
        gravity_sample = (
            gravity_feed_forward.apply_before_step()
            if gravity_feed_forward is not None
            else None
        )
        sim.step(render=False)
        scene.update(physics_dt)
        if gravity_sample is not None:
            gravity_sample["controlled_incoming_joint_forces"] = (
                gravity_feed_forward.read_controlled_incoming_joint_forces()
            )
        elapsed_s += physics_dt
        observation = _sample(
            scene=scene,
            backend=backend,
            controlled_joint_ids=controlled_joint_ids,
            body_ids=body_ids,
            contact_reporter=contact_reporter,
            pose_name=pose_name,
            pose_step=len(samples),
            elapsed_s=elapsed_s,
            api_command_angles_deg=target_angles_deg,
            gravity_feed_forward=gravity_sample,
        )
        samples.append(observation)
        position_derived_velocities = position_derived_velocity_deg_s(
            samples,
            window_s=position_velocity_window_ms / 1000.0,
        )
        velocity_mismatch = velocity_signal_mismatch_deg_s(
            observation["observed_joint_velocities_deg_s"],
            position_derived_velocities,
        )
        position_velocity_stable = (
            position_derived_velocities is not None
            and max(
                abs(float(value))
                for value in position_derived_velocities
            )
            <= settle_velocity_threshold_deg_s
        )
        observation["position_derived_joint_velocities_deg_s"] = (
            position_derived_velocities
        )
        observation["raw_position_velocity_mismatch_deg_s"] = (
            velocity_mismatch
        )
        observation["trajectory_complete"] = backend.trajectory_complete
        observation["position_derived_velocity_stable"] = (
            position_velocity_stable
        )
        if backend.trajectory_complete and position_velocity_stable:
            stable_s += physics_dt
            if velocity_mismatch is not None:
                stable_mismatches.append(velocity_mismatch)
        else:
            stable_s = 0.0
            stable_mismatches = []
        if stable_s + 1.0e-12 >= required_stable_s:
            settled = True
            break

    terminal = samples[-1]
    terminal_observed = terminal["observed_joint_angles_deg"]
    terminal_velocities = terminal["observed_joint_velocities_deg_s"]
    if terminal_velocities is None:
        terminal_velocities = [0.0] * 4
    terminal_derived_velocities = terminal[
        "position_derived_joint_velocities_deg_s"
    ]
    if terminal_derived_velocities is None:
        terminal_derived_velocities = [0.0] * 4
    maximum_velocity_mismatch = max(stable_mismatches, default=0.0)
    raw_position_velocity_consistent = (
        bool(stable_mismatches)
        and maximum_velocity_mismatch
        <= maximum_velocity_signal_mismatch_deg_s
    )
    summary = {
        "name": pose_name,
        "command_angles_deg": list(target_angles_deg),
        "settled_by_position_derived_velocity": settled,
        "settle_elapsed_s": elapsed_s,
        "terminal_observed_angles_deg": terminal_observed,
        "terminal_actual_velocities_deg_s": terminal_velocities,
        "terminal_position_derived_velocities_deg_s": (
            terminal_derived_velocities
        ),
        "maximum_settling_velocity_signal_mismatch_deg_s": (
            maximum_velocity_mismatch
        ),
        "raw_position_velocity_consistent": (
            raw_position_velocity_consistent
        ),
        "maximum_tracking_error_deg": max(
            abs(float(observed) - target)
            for observed, target in zip(
                terminal_observed,
                target_angles_deg,
                strict=True,
            )
        ),
        "maximum_target_buffer_error_deg": _maximum_target_buffer_error(
            samples
        ),
        "maximum_overshoot_deg": _maximum_overshoot(
            samples=samples,
            start_angles_deg=start_angles_deg,
            target_angles_deg=target_angles_deg,
        ),
        "maximum_contact_force_n": max(
            float(sample["critical_contact_force_n"]) for sample in samples
        ),
        "terminal_body_positions_world_m": terminal[
            "body_positions_world_m"
        ],
    }
    print(
        "[ACTUATOR CALIBRATION] "
        f"case={args_cli.case_name} pose={pose_name} settled={settled} "
        f"tracking_error_deg={summary['maximum_tracking_error_deg']:.4f} "
        f"terminal_velocity_deg_s="
        f"{max(abs(float(value)) for value in terminal_velocities):.4f} "
        f"position_derived_velocity_deg_s="
        f"{max(abs(float(value)) for value in terminal_derived_velocities):.4f} "
        f"velocity_signal_mismatch_deg_s={maximum_velocity_mismatch:.4f}",
        flush=True,
    )
    return summary, samples, api_calls


def main() -> None:
    config = preflight_config
    case = preflight_case
    recorded_contract, asset_contract_sha256 = _load_json_object(
        args_cli.asset_contract
    )
    validate_recorded_asset_contract(recorded_contract)

    scene_cfg = DofbotPregraspSceneCfg(num_envs=1, env_spacing=2.0)
    scene_cfg.dofbot.spawn.rigid_props.disable_gravity = (
        not case.gravity_enabled
    )
    scene_cfg.dofbot.spawn.articulation_props.solver_position_iteration_count = (
        case.solver_position_iteration_count
    )
    scene_cfg.dofbot.spawn.articulation_props.solver_velocity_iteration_count = (
        case.solver_velocity_iteration_count
    )
    if case.drive_type is not None:
        scene_cfg.dofbot.spawn = scene_cfg.dofbot.spawn.replace(
            joint_drive_props=sim_utils.JointDrivePropertiesCfg(
                drive_type=case.drive_type,
            )
        )
    for actuator in scene_cfg.dofbot.actuators.values():
        actuator.effort_limit_sim = case.effort_limit_sim
        actuator.stiffness = case.stiffness
        actuator.damping = case.damping

    sim = sim_utils.SimulationContext(
        sim_utils.SimulationCfg(
            device=args_cli.device,
            physics=PhysxCfg(
                enable_external_forces_every_iteration=(
                    case.enable_external_forces_every_iteration
                )
            ),
        )
    )
    scene = InteractiveScene(scene_cfg)
    sim.reset()
    scene.update(sim.get_physics_dt())
    assert_compatible_asset_contracts(
        recorded_contract,
        _live_asset_contract(scene),
    )
    controlled_drive_snapshot = _controlled_joint_drive_snapshot()
    if case.drive_type is not None and any(
        value["drive_type"] != case.drive_type
        for value in controlled_drive_snapshot.values()
    ):
        raise ActuatorCalibrationError(
            "composed USD drive type does not match the requested case"
        )

    controlled_joint_ids = _controlled_joint_ids(scene)
    body_ids = _terminal_body_ids(scene)
    controlled_child_body_ids = _controlled_child_body_ids(scene)
    backend = _IsaacJointPositionBackend(
        scene=scene,
        controlled_joint_ids=controlled_joint_ids,
        device=args_cli.device,
    )
    arm = DofbotArm(backend)
    yahboom_api = YahboomServoApiAdapter(arm)
    contact_reporter = _CriticalContactReporter(sim.get_physics_dt())
    gravity_feed_forward: _BoundedGravityFeedForward | None = None
    if config.case_names == GRAVITY_FEED_FORWARD_CASE_NAMES:
        if case.gravity_compensation_feed_forward is None:
            raise ActuatorCalibrationError(
                "gravity feed-forward case is missing its enabled flag"
            )
        if case.gravity_compensation_effort_limit is None:
            raise ActuatorCalibrationError(
                "gravity feed-forward case is missing its effort limit"
            )
        gravity_feed_forward = _BoundedGravityFeedForward(
            scene=scene,
            controlled_joint_ids=controlled_joint_ids,
            controlled_child_body_ids=controlled_child_body_ids,
            enabled=case.gravity_compensation_feed_forward,
            maximum_effort=case.gravity_compensation_effort_limit,
            device=args_cli.device,
        )

    pose_summaries: list[dict[str, Any]] = []
    all_samples: list[dict[str, Any]] = []
    official_api_calls = 0
    for pose in config.poses:
        summary, samples, api_calls = _run_pose(
            scene=scene,
            sim=sim,
            backend=backend,
            yahboom_api=yahboom_api,
            controlled_joint_ids=controlled_joint_ids,
            body_ids=body_ids,
            contact_reporter=contact_reporter,
            pose_name=pose.name,
            target_angles_deg=pose.angles_deg,
            duration_ms=config.trajectory.duration_ms,
            settle_velocity_threshold_deg_s=(
                config.trajectory.settle_velocity_threshold_deg_s
            ),
            settle_hold_ms=config.trajectory.settle_hold_ms,
            settle_timeout_ms=config.trajectory.settle_timeout_ms,
            position_velocity_window_ms=(
                config.trajectory.position_velocity_window_ms
            ),
            maximum_velocity_signal_mismatch_deg_s=(
                config.trajectory.maximum_velocity_signal_mismatch_deg_s
            ),
            gravity_feed_forward=gravity_feed_forward,
        )
        pose_summaries.append(summary)
        all_samples.extend(samples)
        official_api_calls += api_calls

    target_buffer_available = all(
        sample["joint_pos_target_angles_deg"] is not None
        for sample in all_samples
    )
    actual_velocity_available = all(
        sample["observed_joint_velocities_deg_s"] is not None
        for sample in all_samples
    )
    derived_velocity_samples = [
        sample
        for sample in all_samples
        if sample["trajectory_complete"]
    ]
    position_derived_velocity_available = bool(
        derived_velocity_samples
    ) and all(
        sample["position_derived_joint_velocities_deg_s"] is not None
        for sample in derived_velocity_samples
    )
    computed_available = all(
        sample["computed_torque"] is not None for sample in all_samples
    )
    applied_available = all(
        sample["applied_torque"] is not None for sample in all_samples
    )
    torque_nonzero = any(
        abs(float(value)) > 1.0e-8
        for sample in all_samples
        for field in ("computed_torque", "applied_torque")
        for value in (sample[field] or [])
    )
    torque_buffers_shape_match = all(
        len(sample["computed_torque"] or [])
        == len(sample["applied_torque"] or [])
        for sample in all_samples
    )
    torque_interpretation = (
        "implicit_pd_estimate_not_measured_solver_torque"
        if (
            computed_available
            and applied_available
            and torque_nonzero
            and torque_buffers_shape_match
        )
        else "implicit_zero_or_unavailable_do_not_infer"
    )
    torque_metrics = _torque_metrics(
        samples=all_samples,
        effort_limit_sim=case.effort_limit_sim,
        interpretation=torque_interpretation,
    )
    evaluation = evaluate_calibration_case(
        config,
        case,
        pose_summaries,
        official_api_call_count=official_api_calls,
        target_buffer_available=target_buffer_available,
        actual_velocity_available=actual_velocity_available,
        position_derived_velocity_available=(
            position_derived_velocity_available
        ),
        torque_interpretation=torque_interpretation,
        torque_saturation_observed=torque_metrics[
            "saturation_observed"
        ],
    )
    gravity_feed_forward_telemetry: dict[str, Any] | None = None
    if gravity_feed_forward is not None:
        gravity_feed_forward_telemetry = (
            evaluate_gravity_feed_forward_telemetry(
                samples=[
                    sample["gravity_feed_forward"] for sample in all_samples
                ],
                runtime_api_availability=(
                    gravity_feed_forward.api_availability
                ),
                controlled_joint_ids=controlled_joint_ids,
                feed_forward_enabled=bool(
                    case.gravity_compensation_feed_forward
                ),
                maximum_effort=float(
                    case.gravity_compensation_effort_limit
                ),
            )
        )
        evaluation["checks"].update(
            gravity_feed_forward_telemetry["checks"]
        )
        evaluation["diagnostic_complete"] = all(
            evaluation["checks"].values()
        )
        evaluation["tracking_gate_passed"] = (
            evaluation["diagnostic_complete"]
            and evaluation["maximum_settled_tracking_error_deg"]
            <= config.acceptance.maximum_settled_tracking_error_deg
        )
    optional_physx_probe_errors: dict[str, str] = {}
    result = {
        "schema_version": 1,
        "experiment": "dofbot_actuator_diagnostic_case",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": args_cli.git_commit,
        "asset_contract": {
            "path": str(args_cli.asset_contract),
            "sha256": asset_contract_sha256,
        },
        "calibration_config": {
            "path": str(args_cli.calibration_config),
            "sha256": preflight_config_sha256,
        },
        "case": case.to_dict(),
        "runtime": {
            "physics_dt_s": sim.get_physics_dt(),
            "device": args_cli.device,
            "gravity_enabled": case.gravity_enabled,
            "configured_effort_limit_sim": case.effort_limit_sim,
            "configured_stiffness": case.stiffness,
            "configured_damping": case.damping,
            "solver_position_iteration_count": (
                case.solver_position_iteration_count
            ),
            "solver_velocity_iteration_count": (
                case.solver_velocity_iteration_count
            ),
            "enable_external_forces_every_iteration": (
                case.enable_external_forces_every_iteration
            ),
            "requested_drive_type": case.drive_type,
            "gravity_compensation_feed_forward": (
                case.gravity_compensation_feed_forward
            ),
            "gravity_compensation_effort_limit": (
                case.gravity_compensation_effort_limit
            ),
            "composed_controlled_drive_types": {
                name: value["drive_type"]
                for name, value in controlled_drive_snapshot.items()
            },
            "position_velocity_window_ms": (
                config.trajectory.position_velocity_window_ms
            ),
            "maximum_velocity_signal_mismatch_deg_s": (
                config.trajectory.maximum_velocity_signal_mismatch_deg_s
            ),
            "planned_trajectory_extrema": calibration_trajectory_extrema(
                config
            ),
        },
        "physics_snapshot": {
            "joint_names": list(scene["dofbot"].joint_names),
            "body_names": list(scene["dofbot"].body_names),
            "controlled_joint_drives": controlled_drive_snapshot,
            "masses": _optional_physx_view_tensor(
                scene,
                "get_masses",
                optional_physx_probe_errors,
            ),
            "inertias": _optional_physx_view_tensor(
                scene,
                "get_inertias",
                optional_physx_probe_errors,
            ),
            "dof_stiffnesses": _optional_physx_view_tensor(
                scene,
                "get_dof_stiffnesses",
                optional_physx_probe_errors,
            ),
            "dof_dampings": _optional_physx_view_tensor(
                scene,
                "get_dof_dampings",
                optional_physx_probe_errors,
            ),
            "dof_max_forces": _optional_physx_view_tensor(
                scene,
                "get_dof_max_forces",
                optional_physx_probe_errors,
            ),
            "dof_max_velocities": _optional_physx_view_tensor(
                scene,
                "get_dof_max_velocities",
                optional_physx_probe_errors,
            ),
            "optional_probe_errors": optional_physx_probe_errors,
            "missing_optional_physx_fields_are_recorded_as_null": True,
        },
        "telemetry": {
            "target_buffer_available": target_buffer_available,
            "actual_velocity_available": actual_velocity_available,
            "position_derived_velocity_available": (
                position_derived_velocity_available
            ),
            "computed_torque_buffer_available": computed_available,
            "applied_torque_buffer_available": applied_available,
            "torque_interpretation": torque_interpretation,
            "torque_metrics": torque_metrics,
            "implicit_torque_buffers_are_pd_estimates_not_solver_measurements": True,
            "zero_or_missing_implicit_torque_does_not_disprove_saturation": True,
            "gravity_feed_forward": gravity_feed_forward_telemetry,
        },
        "measurement": {
            "sample_every_physics_step": True,
            "pose_summaries": pose_summaries,
            "samples": all_samples,
        },
        "evaluation": evaluation,
        "scope": {
            "table_or_cube_spawned": False,
            "viewer_started": False,
            "camera_tensor_captured": False,
            "real_hardware_commanded": False,
            "policy_or_checkpoint_loaded": False,
            "contact_or_grasp_authorized": False,
        },
    }
    _write_result(args_cli.output, result)
    print(
        "[ACTUATOR CALIBRATION] "
        f"case={case.name} diagnostic_complete="
        f"{evaluation['diagnostic_complete']} tracking_gate_passed="
        f"{evaluation['tracking_gate_passed']} output={args_cli.output}",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        print(
            f"[ERROR] DOFBOT actuator calibration failed: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
        raise
    else:
        simulation_app.close()
