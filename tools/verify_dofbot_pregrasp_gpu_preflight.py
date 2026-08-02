#!/usr/bin/env python3
"""Fail closed unless the tracked DOFBOT GPU input bundle is self-consistent."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


class PregraspGpuPreflightError(ValueError):
    """The offline GPU-admission contract is missing, stale, or unsafe."""


EXPECTED_SOURCES = {
    "pose_config",
    "scene_config",
    "asset_contract",
    "actuator_config",
    "actuator_machine_result",
    "pregrasp_runner",
    "gravity_feed_forward_runtime",
}
EXPECTED_PREFLIGHT_CHECKS = {
    "asset_contract_sha256_matches",
    "asset_contract_passed",
    "required_grasp_and_collision_bodies_present",
    "scene_config_sha256_matches",
    "target_position_matches_scene_waypoint",
    "target_cube_is_static",
    "grasp_origin_is_terminal_finger_midpoint",
    "approach_axis_matches_target",
    "closing_axis_matches_target",
    "frame_axes_are_orthogonal",
    "only_joint1_through_joint4_are_controlled",
    "wrist_twist_closing_axis_is_monitor_only",
    "synthetic_pose_command_preserves_joint_margin",
    "synthetic_pose_command_respects_velocity_limit",
    "synthetic_pose_command_respects_acceleration_ramp",
    "validated_candidate_reaches_exact_stopped_api_target",
    "safe_synthetic_pregrasp_observation_passed",
    "collision_probe_rejected",
    "reversed_fixed_closing_axis_rejected",
    "contact_remains_unauthorized",
    "accepted_actuator_machine_result_bound",
    "actuator_runtime_probe_occurs_before_first_pose",
    "gravity_feed_forward_applies_after_pd_write_before_step",
    "native_warp_setter_is_shared_with_calibration",
    "pregrasp_runner_records_actuator_failure_classification",
    "real_hardware_not_commanded",
    "gpu_not_started",
}
EXPECTED_SCOPE = {
    "gpu_started": False,
    "isaac_started": False,
    "real_hardware_commanded": False,
    "wrist_twist_commanded": False,
    "gripper_commanded": False,
    "target_cube_moved": False,
    "camera_used_as_controller_input": False,
    "policy_or_checkpoint_loaded": False,
}
EXPECTED_START_ANGLES = [90.0, 90.0, 90.0, 90.0]
EXPECTED_GOAL_ANGLES = [90.0, 66.0, 66.0, 66.0]
EXPECTED_PEAK_VELOCITIES = [0.0, 18.0, 18.0, 18.0]
EXPECTED_PEAK_ACCELERATIONS = [0.0, 36.0, 36.0, 36.0]


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PregraspGpuPreflightError(
            f"cannot read {label} {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise PregraspGpuPreflightError(f"{label} root must be a JSON object")
    return value


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PregraspGpuPreflightError(f"{label} must be an object")
    return value


def _sha256(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise PregraspGpuPreflightError(
            f"cannot read preflight source {path}: {error}"
        ) from error
    return hashlib.sha256(raw).hexdigest()


def _require_exact_numbers(actual: Any, expected: list[float], label: str) -> None:
    if not isinstance(actual, list) or len(actual) != len(expected):
        raise PregraspGpuPreflightError(f"{label} has the wrong shape")
    for index, (value, target) in enumerate(zip(actual, expected, strict=True)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not math.isclose(float(value), target, rel_tol=0.0, abs_tol=1e-12)
        ):
            raise PregraspGpuPreflightError(
                f"{label}[{index}] differs from the accepted DF-035 contract"
            )


def verify_gpu_preflight(
    contract: dict[str, Any],
    *,
    project_dir: Path,
) -> None:
    if contract.get("schema_version") != 1:
        raise PregraspGpuPreflightError("preflight schema_version must be 1")
    if contract.get("experiment") != "dofbot_pose_aware_pregrasp_local_preparation":
        raise PregraspGpuPreflightError("unexpected preflight experiment")

    root = project_dir.resolve()
    sources = _require_object(contract.get("sources"), "sources")
    if set(sources) != EXPECTED_SOURCES:
        raise PregraspGpuPreflightError("preflight source set is incomplete or unexpected")
    for source_name, source_value in sources.items():
        source = _require_object(source_value, f"sources.{source_name}")
        relative_path = source.get("path")
        expected_sha256 = source.get("sha256")
        if not isinstance(relative_path, str) or not relative_path:
            raise PregraspGpuPreflightError(f"sources.{source_name}.path is invalid")
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise PregraspGpuPreflightError(
                f"sources.{source_name}.path must stay inside the repository"
            )
        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root):
            raise PregraspGpuPreflightError(
                f"sources.{source_name}.path escapes the repository"
            )
        if _sha256(resolved) != expected_sha256:
            raise PregraspGpuPreflightError(
                f"sources.{source_name} SHA-256 does not match the checked-out file"
            )

    acceptance = _require_object(contract.get("acceptance"), "acceptance")
    checks = _require_object(acceptance.get("checks"), "acceptance.checks")
    if set(checks) != EXPECTED_PREFLIGHT_CHECKS:
        raise PregraspGpuPreflightError(
            "preflight acceptance check set is incomplete or unexpected"
        )
    if any(value is not True for value in checks.values()):
        failed = sorted(name for name, value in checks.items() if value is not True)
        raise PregraspGpuPreflightError(
            "preflight acceptance checks failed: " + ", ".join(failed)
        )
    if acceptance.get("local_preparation_passed") is not True:
        raise PregraspGpuPreflightError("local preflight did not pass")
    for blocked in (
        "candidate_isaac_machine_passed",
        "candidate_visual_passed",
        "contact_or_grasp_authorized",
    ):
        if acceptance.get(blocked) is not False:
            raise PregraspGpuPreflightError(f"preflight must keep {blocked} false")
    if contract.get("scope") != EXPECTED_SCOPE:
        raise PregraspGpuPreflightError("preflight scope exceeds offline preparation")

    actuator = _require_object(contract.get("actuator_runtime"), "actuator_runtime")
    required_actuator = {
        "selected_case_name": "bounded_gravity_feed_forward",
        "gravity_enabled": True,
        "drive_type": "force",
        "stiffness": 1048.0,
        "damping": 53.0,
        "effort_limit_sim": 100.0,
        "solver_position_iteration_count": 8,
        "solver_velocity_iteration_count": 0,
        "enable_external_forces_every_iteration": True,
        "gravity_compensation_feed_forward": True,
        "gravity_compensation_effort_limit": 5.2,
        "trajectory_duration_ms": 2000,
    }
    for name, expected in required_actuator.items():
        if actuator.get(name) != expected:
            raise PregraspGpuPreflightError(
                f"actuator_runtime.{name} differs from the accepted contract"
            )

    solver = _require_object(contract.get("solver_probe"), "solver_probe")
    if solver.get("algorithm") != "validated_joint_candidate":
        raise PregraspGpuPreflightError("unexpected pre-grasp control algorithm")
    trajectory = solver.get("command_trajectory")
    if not isinstance(trajectory, list) or len(trajectory) != 1:
        raise PregraspGpuPreflightError("DF-035 requires exactly one candidate boundary")
    command = _require_object(solver.get("command"), "solver_probe.command")
    _require_exact_numbers(command.get("angles_deg"), EXPECTED_GOAL_ANGLES, "command angles")
    _require_exact_numbers(
        command.get("velocities_deg_s"), [0.0, 0.0, 0.0, 0.0], "command velocities"
    )

    motion = _require_object(
        solver.get("candidate_backend_motion_contract"),
        "candidate_backend_motion_contract",
    )
    if motion.get("profile") != "cubic_smoothstep_3u2_minus_2u3":
        raise PregraspGpuPreflightError("unexpected backend motion profile")
    _require_exact_numbers(motion.get("start_angles_deg"), EXPECTED_START_ANGLES, "motion start")
    _require_exact_numbers(motion.get("goal_angles_deg"), EXPECTED_GOAL_ANGLES, "motion goal")
    _require_exact_numbers(
        motion.get("peak_velocity_deg_s"), EXPECTED_PEAK_VELOCITIES, "motion peak velocity"
    )
    _require_exact_numbers(
        motion.get("peak_acceleration_deg_s2"),
        EXPECTED_PEAK_ACCELERATIONS,
        "motion peak acceleration",
    )
    if motion.get("duration_s") != 2.0:
        raise PregraspGpuPreflightError("DF-035 motion duration must be 2 seconds")
    if motion.get("maximum_peak_velocity_deg_s") != 18.0:
        raise PregraspGpuPreflightError("DF-035 peak velocity must be 18 degrees/s")
    if motion.get("maximum_peak_acceleration_deg_s2") != 36.0:
        raise PregraspGpuPreflightError("DF-035 peak acceleration must be 36 degrees/s2")

    collision = _require_object(contract.get("collision_probe"), "collision_probe")
    safe = _require_object(collision.get("safe_evaluation"), "safe_evaluation")
    if safe.get("passed") is not True:
        raise PregraspGpuPreflightError("synthetic safe pose did not pass")
    if collision.get("deliberate_terminal_finger_collision_passed") is not False:
        raise PregraspGpuPreflightError("collision mutation was not rejected")
    if collision.get("reversed_closing_axis_passed") is not False:
        raise PregraspGpuPreflightError("reversed closing-axis mutation was not rejected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        contract = load_json_object(args.contract, label="GPU preflight contract")
        verify_gpu_preflight(contract, project_dir=args.project_dir)
    except PregraspGpuPreflightError as error:
        print(f"[PREGRASP GPU PREFLIGHT] FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "[PREGRASP GPU PREFLIGHT] PASS: "
        f"contract={args.contract} project_dir={args.project_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
