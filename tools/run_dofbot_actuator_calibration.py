"""Run one isolated DOFBOT actuator diagnostic case in Isaac Lab.

The runner has no table, cube, camera, policy, or hardware backend.  It records
the complete API -> interpolated target -> Isaac target buffer -> articulation
state path every physics step and uses actual joint velocity for settling.
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
    calibration_trajectory_extrema,
    evaluate_calibration_case,
    load_actuator_calibration_config,
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

import isaaclab.sim as sim_utils
import omni.physx
from isaaclab.scene import InteractiveScene
from pxr import PhysicsSchemaTools

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
            return value.detach().cpu().tolist()
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
    saturation_observed = (
        interpretation == "measured_nonzero_buffers"
        and maximum_applied >= 0.98 * effort_limit_sim
        and maximum_gap > 1.0e-6
    )
    return {
        "maximum_absolute_computed_torque": maximum_computed,
        "maximum_absolute_applied_torque": maximum_applied,
        "maximum_absolute_computed_applied_gap": maximum_gap,
        "configured_effort_limit_sim": effort_limit_sim,
        "saturation_observed": saturation_observed,
        "buffers_shape_match": buffers_shape_match,
        "criterion": (
            "meaningful buffers and applied >= 98% of limit with "
            "nonzero computed/applied gap"
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
    while elapsed_s < maximum_elapsed_s - 1.0e-12:
        if not simulation_app.is_running():
            raise ActuatorCalibrationError(
                f"simulation stopped during calibration pose {pose_name}"
            )
        backend.advance(physics_dt)
        scene.write_data_to_sim()
        sim.step(render=False)
        scene.update(physics_dt)
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
        )
        samples.append(observation)
        actual_velocities = observation["observed_joint_velocities_deg_s"]
        velocity_stable = (
            actual_velocities is not None
            and max(abs(float(value)) for value in actual_velocities)
            <= settle_velocity_threshold_deg_s
        )
        if backend.trajectory_complete and velocity_stable:
            stable_s += physics_dt
        else:
            stable_s = 0.0
        if stable_s + 1.0e-12 >= required_stable_s:
            settled = True
            break

    terminal = samples[-1]
    terminal_observed = terminal["observed_joint_angles_deg"]
    terminal_velocities = terminal["observed_joint_velocities_deg_s"]
    if terminal_velocities is None:
        terminal_velocities = [0.0] * 4
    summary = {
        "name": pose_name,
        "command_angles_deg": list(target_angles_deg),
        "settled": settled,
        "settle_elapsed_s": elapsed_s,
        "terminal_observed_angles_deg": terminal_observed,
        "terminal_actual_velocities_deg_s": terminal_velocities,
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
        f"{max(abs(float(value)) for value in terminal_velocities):.4f}",
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
    for actuator in scene_cfg.dofbot.actuators.values():
        actuator.effort_limit_sim = case.effort_limit_sim

    sim = sim_utils.SimulationContext(
        sim_utils.SimulationCfg(device=args_cli.device)
    )
    scene = InteractiveScene(scene_cfg)
    sim.reset()
    scene.update(sim.get_physics_dt())
    assert_compatible_asset_contracts(
        recorded_contract,
        _live_asset_contract(scene),
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
    contact_reporter = _CriticalContactReporter(sim.get_physics_dt())

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
        "measured_nonzero_buffers"
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
        torque_interpretation=torque_interpretation,
        torque_saturation_observed=torque_metrics[
            "saturation_observed"
        ],
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
            "configured_stiffness": 10000.0,
            "configured_damping": 100.0,
            "solver_position_iteration_count": 8,
            "solver_velocity_iteration_count": 0,
            "planned_trajectory_extrema": calibration_trajectory_extrema(
                config
            ),
        },
        "physics_snapshot": {
            "joint_names": list(scene["dofbot"].joint_names),
            "body_names": list(scene["dofbot"].body_names),
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
            "computed_torque_buffer_available": computed_available,
            "applied_torque_buffer_available": applied_available,
            "torque_interpretation": torque_interpretation,
            "torque_metrics": torque_metrics,
            "zero_or_missing_implicit_torque_does_not_disprove_saturation": True,
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
