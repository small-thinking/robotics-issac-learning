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

from audit_dofbot_context_transfer import (
    CURRENT_SHARED_RUNTIME_PATHS,
    _source_bundle,
)
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
    evaluate_gravity_feed_forward_telemetry,
)
from dofbot_scene_decomposition import (
    load_scene_decomposition_config,
    minimum_body_center_aabb_clearances,
)
from dofbot_collider_audit import load_collider_audit_config

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
    "--scene-decomposition-config",
    type=Path,
    default=None,
    help="Optional strict DF-047 scene-cell config; requires --scene-config.",
)
parser.add_argument(
    "--scene-cell",
    default=None,
    help="One cell ID from --scene-decomposition-config.",
)
parser.add_argument(
    "--collider-audit-config",
    type=Path,
    default=None,
    help="Optional strict DF-049 full-collider diagnostic contract.",
)
parser.add_argument(
    "--calibration-config",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/configs/dofbot/calibration/"
        "goal5_actuator_diagnostic.json"
    ),
)
parser.add_argument(
    "--scene-config",
    type=Path,
    default=None,
    help=(
        "Optional static reaching scene for a context-transfer discriminator; "
        "omit for the canonical isolated calibration."
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
preflight_scene_decomposition = None
preflight_scene_decomposition_sha256 = None
preflight_scene_cell = None
preflight_collider_audit = None
preflight_collider_audit_sha256 = None
if (args_cli.scene_decomposition_config is None) != (args_cli.scene_cell is None):
    parser.error(
        "--scene-decomposition-config and --scene-cell must be supplied together"
    )
if args_cli.scene_decomposition_config is not None:
    if args_cli.scene_config is None:
        parser.error("--scene-decomposition-config requires --scene-config")
    (
        preflight_scene_decomposition,
        preflight_scene_decomposition_sha256,
    ) = load_scene_decomposition_config(args_cli.scene_decomposition_config)
    preflight_scene_cell = preflight_scene_decomposition.cell(args_cli.scene_cell)
if args_cli.collider_audit_config is not None:
    if preflight_scene_cell is None:
        parser.error("--collider-audit-config requires a scene-decomposition cell")
    (
        preflight_collider_audit,
        preflight_collider_audit_sha256,
    ) = load_collider_audit_config(args_cli.collider_audit_config)
    if preflight_scene_cell.id not in preflight_collider_audit.allowed_cells:
        parser.error("DF-049 permits only S0 and T1")

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch

import isaaclab.sim as sim_utils
import omni.physx
from isaaclab.scene import InteractiveScene
from isaaclab_physx.physics import PhysxCfg
from pxr import PhysicsSchemaTools

from dofbot_collider_audit import (
    evaluate_collider_clearance,
    summarize_collider_clearance_samples,
)
from dofbot_contact_report import (
    maximum_monitored_contact_force_n,
    normalized_contact_pair,
)
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
from dofbot_gravity_feed_forward_runtime import (
    BoundedGravityFeedForward,
    controlled_joint_drive_snapshot,
)
from dofbot_pregrasp_scene_cfg import (
    CONTACT_BODY_PATHS,
    DofbotPregraspSceneCfg,
    inspect_collision_filter_relationships,
    inspect_collision_shapes,
    inspect_spawned_reaching_objects,
    spawn_reaching_scene_cell,
    spawn_static_reaching_boxes,
)
from dofbot_reaching import load_reaching_config

TERMINAL_BODY_NAMES = (
    "Wrist_Twist",
    "Finger_Left_03",
    "Finger_Right_03",
)
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


def _all_body_ids(scene: InteractiveScene) -> dict[str, int]:
    return {
        name: index for index, name in enumerate(scene["dofbot"].body_names)
    }


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


class _CriticalContactReporter:
    """Accumulate monitored contact impulses between observation reads."""

    def __init__(
        self,
        physics_dt: float,
        critical_paths: frozenset[str] | None = None,
    ) -> None:
        self._physics_dt = physics_dt
        self._critical_paths = critical_paths or frozenset(CONTACT_BODY_PATHS)
        self._maximum_force_n_since_read = 0.0
        self._callback_count = 0
        self._header_count = 0
        self._all_actor_pairs: set[tuple[str, str]] = set()
        self._monitored_actor_pairs: set[tuple[str, str]] = set()
        self._normalized_monitored_actor_pairs: set[
            tuple[str | None, str | None]
        ] = set()
        self._subscription = (
            omni.physx.get_physx_simulation_interface()
            .subscribe_contact_report_events(self._on_contact_report)
        )

    def _on_contact_report(self, headers: Any, contact_data: Any) -> None:
        headers = list(headers)
        self._callback_count += 1
        self._header_count += len(headers)

        def decode(value: Any) -> str:
            return str(PhysicsSchemaTools.intToSdfPath(value))

        for header in headers:
            actor0 = decode(header.actor0)
            actor1 = decode(header.actor1)
            self._all_actor_pairs.add((actor0, actor1))
            normalized = normalized_contact_pair(
                actor0,
                actor1,
                self._critical_paths,
            )
            if normalized[0] is not None or normalized[1] is not None:
                self._monitored_actor_pairs.add((actor0, actor1))
                self._normalized_monitored_actor_pairs.add(normalized)
        force_n = maximum_monitored_contact_force_n(
            headers=headers,
            contact_data=contact_data,
            critical_paths=self._critical_paths,
            physics_dt=self._physics_dt,
            decode_path=decode,
        )
        self._maximum_force_n_since_read = max(
            self._maximum_force_n_since_read,
            force_n,
        )

    def maximum_force_n(self) -> float:
        maximum = self._maximum_force_n_since_read
        self._maximum_force_n_since_read = 0.0
        return maximum

    def summary(self) -> dict[str, Any]:
        return {
            "callback_count": self._callback_count,
            "contact_header_count": self._header_count,
            "path_matching_mode": "same_or_descendant_of_monitored_rigid_body",
            "monitored_rigid_body_paths": sorted(self._critical_paths),
            "all_actor_pairs": [
                list(value) for value in sorted(self._all_actor_pairs)
            ],
            "monitored_actor_pairs": [
                list(value) for value in sorted(self._monitored_actor_pairs)
            ],
            "normalized_monitored_actor_pairs": [
                list(value)
                for value in sorted(
                    self._normalized_monitored_actor_pairs,
                    key=lambda pair: (pair[0] or "", pair[1] or ""),
                )
            ],
        }


def _root_physx_view_shape(scene: InteractiveScene) -> dict[str, Any]:
    view = scene["dofbot"].root_physx_view
    result: dict[str, Any] = {}
    for name in ("count", "max_links", "max_dofs", "num_links", "num_dofs"):
        value = getattr(view, name, None)
        if isinstance(value, (int, float, str, bool)) or value is None:
            result[name] = value
        else:
            result[name] = str(value)
    return result


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


def _body_poses_world_m(
    scene: InteractiveScene,
    body_ids: dict[str, int],
) -> dict[str, dict[str, list[float]]]:
    robot = scene["dofbot"]
    return {
        name: {
            "position_world_m": [
                float(value)
                for value in robot.data.body_pos_w[0, body_id]
                .detach()
                .cpu()
                .tolist()
            ],
            "quaternion_wxyz": [
                float(value)
                for value in robot.data.body_quat_w[0, body_id]
                .detach()
                .cpu()
                .tolist()
            ],
        }
        for name, body_id in body_ids.items()
    }


class _ColliderAuditSampler:
    def __init__(
        self,
        *,
        robot_colliders: list[dict[str, Any]],
        table_colliders: list[dict[str, Any]],
        body_ids: dict[str, int],
    ) -> None:
        self.robot_colliders = robot_colliders
        self.table_colliders = table_colliders
        self.body_ids = body_ids

    def sample(
        self,
        *,
        scene: InteractiveScene,
        pose_name: str,
        pose_step: int,
        elapsed_s: float,
    ) -> dict[str, Any]:
        result = evaluate_collider_clearance(
            robot_colliders=self.robot_colliders,
            table_colliders=self.table_colliders,
            body_poses=_body_poses_world_m(scene, self.body_ids),
        )
        return {
            "pose_name": pose_name,
            "pose_step": pose_step,
            "elapsed_s": elapsed_s,
            **result,
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
    collider_audit: _ColliderAuditSampler | None,
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
        "collider_audit": (
            collider_audit.sample(
                scene=scene,
                pose_name=pose_name,
                pose_step=pose_step,
                elapsed_s=elapsed_s,
            )
            if collider_audit is not None
            else None
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
    gravity_feed_forward: BoundedGravityFeedForward | None,
    collider_audit: _ColliderAuditSampler | None,
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
            collider_audit=collider_audit,
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
    context_scene = None
    context_scene_sha256 = None
    if args_cli.scene_config is not None:
        context_scene, context_scene_sha256 = load_reaching_config(
            args_cli.scene_config
        )
    scene = InteractiveScene(scene_cfg)
    spawned_scene_objects: list[dict[str, Any]] = []
    if context_scene is not None:
        if preflight_scene_cell is None:
            spawn_static_reaching_boxes(context_scene)
            spawned_scene_objects = [
                {
                    "name": name,
                    "prim_path": box.prim_path,
                    "center_world_m": list(box.center_world_m),
                    "size_m": list(box.size_m),
                    "collision_enabled": True,
                    "rigid_body_authored": False,
                }
                for name, box in (
                    ("table", context_scene.table),
                    ("target_cube", context_scene.target_cube),
                )
            ]
        else:
            spawned_scene_objects = spawn_reaching_scene_cell(
                context_scene,
                preflight_scene_cell,
            )
    sim.reset()
    scene.update(sim.get_physics_dt())
    spawned_scene_readback = inspect_spawned_reaching_objects(
        sim_utils.get_current_stage(),
        spawned_scene_objects,
    )
    robot_collider_inventory: list[dict[str, Any]] = []
    table_collider_inventory: list[dict[str, Any]] = []
    collision_filter_relationships: list[dict[str, Any]] = []
    collider_audit_sampler: _ColliderAuditSampler | None = None
    if preflight_collider_audit is not None:
        stage = sim_utils.get_current_stage()
        all_body_ids = _all_body_ids(scene)
        robot_collider_inventory = inspect_collision_shapes(
            stage,
            root_prim_path=preflight_collider_audit.robot_root_prim_path,
            require_rigid_body_owner=True,
            known_body_names=set(all_body_ids),
        )
        table_collider_inventory = inspect_collision_shapes(
            stage,
            root_prim_path=preflight_collider_audit.table_root_prim_path,
            require_rigid_body_owner=False,
        )
        collision_filter_relationships = inspect_collision_filter_relationships(
            stage
        )
        if not robot_collider_inventory:
            raise ActuatorCalibrationError("DF-049 found no robot collision prims")
        unresolved = [
            value["prim_path"]
            for value in robot_collider_inventory
            if value["owner_status"] != "resolved"
        ]
        if unresolved:
            raise ActuatorCalibrationError(
                f"DF-049 could not resolve collider owners: {unresolved}"
            )
        expected_table_count = 0 if preflight_scene_cell.id == "S0" else 1
        if (len(table_collider_inventory) > 0) != (expected_table_count > 0):
            raise ActuatorCalibrationError(
                "DF-049 table collider presence disagrees with the selected cell"
            )
        collider_audit_sampler = _ColliderAuditSampler(
            robot_colliders=robot_collider_inventory,
            table_colliders=table_collider_inventory,
            body_ids=all_body_ids,
        )
    assert_compatible_asset_contracts(
        recorded_contract,
        _live_asset_contract(scene),
    )
    controlled_drive_snapshot = controlled_joint_drive_snapshot()
    if case.drive_type is not None and any(
        value["drive_type"] != case.drive_type
        for value in controlled_drive_snapshot.values()
    ):
        raise ActuatorCalibrationError(
            "composed USD drive type does not match the requested case"
        )

    controlled_joint_ids = _controlled_joint_ids(scene)
    body_ids = _terminal_body_ids(scene)
    backend = _IsaacJointPositionBackend(
        scene=scene,
        controlled_joint_ids=controlled_joint_ids,
        device=args_cli.device,
    )
    arm = DofbotArm(backend)
    yahboom_api = YahboomServoApiAdapter(arm)
    live_collider_owner_paths = frozenset(
        str(value["owner_body_path"])
        for value in robot_collider_inventory
        if value.get("owner_body_path") is not None
    )
    contact_reporter = _CriticalContactReporter(
        sim.get_physics_dt(),
        critical_paths=(
            live_collider_owner_paths
            if preflight_collider_audit is not None
            else None
        ),
    )
    gravity_feed_forward: BoundedGravityFeedForward | None = None
    if config.case_names == GRAVITY_FEED_FORWARD_CASE_NAMES:
        if case.gravity_compensation_feed_forward is None:
            raise ActuatorCalibrationError(
                "gravity feed-forward case is missing its enabled flag"
            )
        if case.gravity_compensation_effort_limit is None:
            raise ActuatorCalibrationError(
                "gravity feed-forward case is missing its effort limit"
            )
        gravity_feed_forward = BoundedGravityFeedForward(
            scene=scene,
            controlled_joint_ids=controlled_joint_ids,
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
            collider_audit=collider_audit_sampler,
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
    collider_samples = [
        sample["collider_audit"]
        for sample in all_samples
        if sample["collider_audit"] is not None
    ]
    result = {
        "schema_version": 1,
        "experiment": "dofbot_actuator_diagnostic_case",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": args_cli.git_commit,
        "runtime_source_bundle": _source_bundle(
            project_dir=Path(__file__).resolve().parents[1],
            paths=CURRENT_SHARED_RUNTIME_PATHS,
        ),
        "asset_contract": {
            "path": str(args_cli.asset_contract),
            "sha256": asset_contract_sha256,
        },
        "calibration_config": {
            "path": str(args_cli.calibration_config),
            "sha256": preflight_config_sha256,
        },
        "context_scene_config": (
            {
                "path": str(args_cli.scene_config),
                "sha256": context_scene_sha256,
                "table_prim_path": context_scene.table.prim_path,
                "target_cube_prim_path": context_scene.target_cube.prim_path,
            }
            if context_scene is not None
            else None
        ),
        "scene_decomposition": (
            {
                "config_path": str(args_cli.scene_decomposition_config),
                "config_sha256": preflight_scene_decomposition_sha256,
                "cell": preflight_scene_cell.to_dict(),
                "spawn_plan": spawned_scene_objects,
                "runtime_readback": spawned_scene_readback,
                "clearance": minimum_body_center_aabb_clearances(
                    all_samples,
                    spawned_scene_objects,
                ),
            }
            if preflight_scene_cell is not None
            else None
        ),
        "collider_audit": (
            {
                "config_path": str(args_cli.collider_audit_config),
                "config_sha256": preflight_collider_audit_sha256,
                "config": preflight_collider_audit.to_dict(),
                "robot_colliders": robot_collider_inventory,
                "table_colliders": table_collider_inventory,
                "collision_filter_relationships": collision_filter_relationships,
                "clearance_summary": summarize_collider_clearance_samples(
                    collider_samples
                ),
                "body_pose_source": "Isaac ArticulationData body_pos_w/body_quat_w",
                "aabb_method": (
                    "USD collider bound relative to nearest rigid body, transformed "
                    "by the live body pose each physics step"
                ),
                "aabb_is_conservative_not_exact_shape_distance": True,
            }
            if preflight_collider_audit is not None
            else None
        ),
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
            "controlled_joint_ids": controlled_joint_ids,
            "terminal_body_ids": body_ids,
            "root_physx_view_shape": _root_physx_view_shape(scene),
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
            "contact_events": contact_reporter.summary(),
        },
        "measurement": {
            "sample_every_physics_step": True,
            "pose_summaries": pose_summaries,
            "samples": all_samples,
        },
        "evaluation": evaluation,
        "scope": {
            "table_or_cube_spawned": bool(spawned_scene_objects),
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
