#!/usr/bin/env python3
"""Fail closed unless a fresh DOFBOT pre-grasp machine contract passed."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    from .verify_dofbot_pregrasp_gpu_preflight import (
        PregraspGpuPreflightError,
        load_json_object,
        verify_gpu_preflight,
    )
except ImportError:
    from verify_dofbot_pregrasp_gpu_preflight import (
        PregraspGpuPreflightError,
        load_json_object,
        verify_gpu_preflight,
    )


class PregraspContractVerificationError(ValueError):
    """The machine contract is missing, stale, malformed, or failed."""


EXPECTED_MACHINE_CHECKS = {
    "grasp_origin_reached_pregrasp_position",
    "approach_axis_matches_target_within_tolerance",
    "fixed_closing_axis_is_acceptable_without_wrist_command",
    "joint_angles_remain_within_safe_limits",
    "joint_velocity_limit_respected",
    "joint_acceleration_limit_respected",
    "critical_body_centers_clear_table_proxy",
    "nonfinger_body_centers_clear_target_proxy",
    "terminal_finger_centers_remain_precontact",
    "contact_reporter_force_remains_below_threshold",
    "target_remains_static",
    "contact_remains_unauthorized",
    "gravity_compensation_runtime_apis_available",
    "gravity_compensation_values_finite",
    "incoming_joint_force_values_finite",
    "feed_forward_effort_bounded",
    "only_controlled_joints_receive_feed_forward",
    "baseline_case_applies_zero_feed_forward",
    "accepted_actuator_machine_evidence_bound",
    "live_actuator_drive_matches_selected_contract",
    "live_actuator_effort_limits_match_selected_contract",
    "physical_table_prim_present",
    "static_target_cube_prim_present",
    "pose_controller_improved_position",
    "official_api_call_count_matches",
    "api_commands_preserve_limit_margin",
    "validated_joint_candidate_command_reached",
    "backend_trajectory_peak_velocity_within_limit",
    "backend_trajectory_peak_acceleration_within_limit",
    "joint_target_buffer_telemetry_available",
    "backend_target_matches_final_api_command",
    "joint_position_target_buffer_matches_backend_target",
    "physx_projected_joint_force_telemetry_available",
    "implicit_actuator_pd_estimate_telemetry_available",
    "projected_force_and_pd_estimates_are_sample_aligned",
    "final_api_joint_tracking_within_tolerance",
    "returned_to_neutral",
}
EXPECTED_MACHINE_SCOPE = {
    "real_hardware_commanded": False,
    "camera_used_as_controller_input": False,
    "wrist_twist_commanded": False,
    "gripper_commanded": False,
    "target_cube_moved": False,
    "contact_authorized": False,
    "policy_or_checkpoint_loaded": False,
}
MAXIMUM_INITIAL_NEUTRAL_ERROR_DEG = 1.0
MAXIMUM_TRAJECTORY_VELOCITY_DEG_S = 20.0
MAXIMUM_TRAJECTORY_ACCELERATION_DEG_S2 = 60.0


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PregraspContractVerificationError(
            f"cannot read machine contract {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise PregraspContractVerificationError(
            "machine contract root must be a JSON object"
        )
    return value


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PregraspContractVerificationError(f"{label} must be an object")
    return value


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PregraspContractVerificationError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise PregraspContractVerificationError(f"{label} must be a finite number")
    return number


def _finite_vector(value: Any, width: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != width:
        raise PregraspContractVerificationError(f"{label} must contain {width} values")
    return [
        _finite_number(item, f"{label}[{index}]")
        for index, item in enumerate(value)
    ]


def _require_at_most(value: Any, maximum: float, label: str) -> None:
    number = _finite_number(value, label)
    if number < 0.0 or number > maximum + 1.0e-12:
        raise PregraspContractVerificationError(
            f"{label}={number} exceeds {maximum}"
        )


def _require_vector_close(
    actual: Any,
    expected: list[float],
    *,
    tolerance: float,
    label: str,
) -> list[float]:
    values = _finite_vector(actual, len(expected), label)
    if any(
        not math.isclose(value, target, rel_tol=0.0, abs_tol=tolerance)
        for value, target in zip(values, expected, strict=True)
    ):
        raise PregraspContractVerificationError(
            f"{label} differs from the expected values"
        )
    return values


def _verify_machine_motion_contract(
    motion_value: Any,
    *,
    expected_motion: dict[str, Any],
    initial_observation: dict[str, Any],
) -> list[float]:
    motion = _object(motion_value, "candidate_backend_motion_contract")
    if motion.get("profile") != expected_motion.get("profile"):
        raise PregraspContractVerificationError(
            "machine backend motion profile differs from DF-035 preflight"
        )
    duration = _finite_number(motion.get("duration_s"), "motion duration")
    expected_duration = _finite_number(
        expected_motion.get("duration_s"), "preflight motion duration"
    )
    if duration != expected_duration:
        raise PregraspContractVerificationError(
            "machine backend motion duration differs from DF-035 preflight"
        )

    expected_start = _finite_vector(
        expected_motion.get("start_angles_deg"), 4, "preflight motion start"
    )
    expected_goal = _finite_vector(
        expected_motion.get("goal_angles_deg"), 4, "preflight motion goal"
    )
    start = _finite_vector(motion.get("start_angles_deg"), 4, "motion start")
    goal = _require_vector_close(
        motion.get("goal_angles_deg"),
        expected_goal,
        tolerance=1.0e-12,
        label="motion goal",
    )
    _require_vector_close(
        initial_observation.get("angles_deg"),
        start,
        tolerance=1.0e-12,
        label="initial observation/motion start",
    )
    if any(
        abs(value - neutral) > MAXIMUM_INITIAL_NEUTRAL_ERROR_DEG + 1.0e-12
        for value, neutral in zip(start, expected_start, strict=True)
    ):
        raise PregraspContractVerificationError(
            "machine motion did not start within one degree of neutral"
        )

    expected_delta = [target - value for value, target in zip(start, goal, strict=True)]
    expected_velocity = [1.5 * abs(delta) / duration for delta in expected_delta]
    expected_acceleration = [
        6.0 * abs(delta) / (duration * duration) for delta in expected_delta
    ]
    _require_vector_close(
        motion.get("delta_angles_deg"),
        expected_delta,
        tolerance=1.0e-9,
        label="motion delta",
    )
    _require_vector_close(
        motion.get("peak_velocity_deg_s"),
        expected_velocity,
        tolerance=1.0e-9,
        label="motion peak velocity",
    )
    _require_vector_close(
        motion.get("peak_acceleration_deg_s2"),
        expected_acceleration,
        tolerance=1.0e-9,
        label="motion peak acceleration",
    )
    maximum_velocity = _finite_number(
        motion.get("maximum_peak_velocity_deg_s"), "maximum motion velocity"
    )
    maximum_acceleration = _finite_number(
        motion.get("maximum_peak_acceleration_deg_s2"),
        "maximum motion acceleration",
    )
    if not math.isclose(
        maximum_velocity, max(expected_velocity), rel_tol=0.0, abs_tol=1.0e-9
    ):
        raise PregraspContractVerificationError(
            "maximum motion velocity is inconsistent with per-joint peaks"
        )
    if not math.isclose(
        maximum_acceleration,
        max(expected_acceleration),
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise PregraspContractVerificationError(
            "maximum motion acceleration is inconsistent with per-joint peaks"
        )
    _require_at_most(
        maximum_velocity,
        MAXIMUM_TRAJECTORY_VELOCITY_DEG_S,
        "maximum motion velocity",
    )
    _require_at_most(
        maximum_acceleration,
        MAXIMUM_TRAJECTORY_ACCELERATION_DEG_S2,
        "maximum motion acceleration",
    )
    return expected_goal


def verify_machine_contract(
    contract: dict[str, Any],
    *,
    expected_git_commit: str,
    preflight_contract: dict[str, Any],
    project_dir: Path,
) -> None:
    try:
        verify_gpu_preflight(preflight_contract, project_dir=project_dir)
    except PregraspGpuPreflightError as error:
        raise PregraspContractVerificationError(
            f"GPU preflight contract failed revalidation: {error}"
        ) from error

    if contract.get("schema_version") != 1:
        raise PregraspContractVerificationError("machine schema_version must be 1")
    if contract.get("experiment") != "dofbot_goal5_angled_pregrasp":
        raise PregraspContractVerificationError("unexpected machine experiment")
    actual_commit = contract.get("git_commit")
    if actual_commit != expected_git_commit:
        raise PregraspContractVerificationError(
            "machine contract git commit mismatch: "
            f"expected={expected_git_commit!r} actual={actual_commit!r}"
        )

    expected_source_map = {
        "asset_contract": "asset_contract",
        "scene_config": "scene_config",
        "pose_config": "pose_config",
        "actuator_config": "actuator_config",
        "actuator_machine_result": "actuator_machine_result",
    }
    sources = _object(contract.get("sources"), "sources")
    preflight_sources = _object(preflight_contract.get("sources"), "preflight sources")
    if set(sources) != set(expected_source_map):
        raise PregraspContractVerificationError("machine source set is incomplete or unexpected")
    for machine_name, preflight_name in expected_source_map.items():
        machine_source = _object(sources[machine_name], f"sources.{machine_name}")
        preflight_source = _object(
            preflight_sources[preflight_name], f"preflight sources.{preflight_name}"
        )
        if machine_source.get("sha256") != preflight_source.get("sha256"):
            raise PregraspContractVerificationError(
                f"machine source {machine_name} differs from GPU preflight"
            )

    acceptance = _object(contract.get("acceptance"), "acceptance")
    machine = _object(acceptance.get("machine"), "acceptance.machine")
    checks = _object(machine.get("checks"), "acceptance.machine.checks")
    if set(checks) != EXPECTED_MACHINE_CHECKS:
        raise PregraspContractVerificationError(
            "machine check set is incomplete or unexpected"
        )
    if any(value is not True for value in checks.values()):
        failed_values = sorted(
            name for name, value in checks.items() if value is not True
        )
        raise PregraspContractVerificationError(
            "machine checks contain non-passing values: " + ", ".join(failed_values)
        )

    failed_checks = machine.get("failed_checks")
    if (
        machine.get("machine_passed") is not True
        or machine.get("decision") != "pregrasp_machine_passed"
        or failed_checks != []
    ):
        raise PregraspContractVerificationError(
            "pre-grasp machine gate did not pass: "
            f"decision={machine.get('decision')!r} "
            f"failed_checks={failed_checks!r}"
        )

    measurement = _object(contract.get("measurement"), "measurement")
    observations = measurement.get("observations")
    gravity_samples = measurement.get("gravity_feed_forward_samples")
    if not isinstance(observations, list) or not observations:
        raise PregraspContractVerificationError("machine observations are empty")
    if not isinstance(gravity_samples, list) or not gravity_samples:
        raise PregraspContractVerificationError("gravity feed-forward samples are empty")
    initial_observation = _object(observations[0], "measurement.observations[0]")
    expected_motion = _object(
        preflight_contract["solver_probe"]["candidate_backend_motion_contract"],
        "preflight candidate_backend_motion_contract",
    )
    expected_goal = _verify_machine_motion_contract(
        machine.get("candidate_backend_motion_contract"),
        expected_motion=expected_motion,
        initial_observation=initial_observation,
    )
    control = _object(contract.get("control"), "control")
    required_control = {
        "application_api": "Arm_serial_servo_write(id, angle, time)",
        "algorithm": "validated_joint_candidate",
        "controlled_joint_names": ["joint1", "joint2", "joint3", "joint4"],
        "target_joint_candidate_angles_deg": expected_goal,
        "final_controller_api_command_angles_deg": expected_goal,
        "validated_joint_candidate_command_reached": True,
        "policy_free": True,
        "actuator_runtime": preflight_contract["actuator_runtime"],
    }
    for name, expected in required_control.items():
        if control.get(name) != expected:
            raise PregraspContractVerificationError(
                f"control.{name} differs from the GPU preflight contract"
            )

    expected_api_calls = 4 + 4 + 4
    if (
        machine.get("official_api_call_count") != expected_api_calls
        or machine.get("expected_official_api_call_count") != expected_api_calls
    ):
        raise PregraspContractVerificationError(
            "machine contract does not record exactly 12 official API calls"
        )
    _require_at_most(machine.get("final_position_error_m"), 0.025, "final position error")
    _require_at_most(machine.get("final_approach_error_deg"), 12.0, "final approach error")
    _require_at_most(machine.get("final_closing_error_deg"), 20.0, "final closing error")
    _require_at_most(machine.get("maximum_contact_force_n"), 0.5, "maximum contact force")
    if _finite_number(machine.get("position_improvement_m"), "position improvement") < 0.03:
        raise PregraspContractVerificationError("position improvement is below 0.03 m")

    alignment_limit = _finite_number(
        machine.get("maximum_allowed_target_buffer_alignment_error_deg"),
        "target-buffer alignment limit",
    )
    if alignment_limit != 0.05:
        raise PregraspContractVerificationError(
            "target-buffer alignment limit differs from 0.05 degrees"
        )
    _require_at_most(
        machine.get("maximum_backend_target_api_error_deg"),
        alignment_limit,
        "backend/API target error",
    )
    _require_at_most(
        machine.get("maximum_target_buffer_backend_error_deg"),
        alignment_limit,
        "target-buffer/backend error",
    )
    tracking_limit = _finite_number(
        machine.get("maximum_allowed_final_joint_tracking_error_deg"),
        "joint tracking limit",
    )
    if tracking_limit != 1.0:
        raise PregraspContractVerificationError(
            "joint tracking limit differs from 1 degree"
        )
    _require_at_most(
        machine.get("maximum_final_joint_tracking_error_deg"),
        tracking_limit,
        "final joint tracking error",
    )
    _require_at_most(
        machine.get("maximum_neutral_reset_error_deg"),
        1.0,
        "neutral reset error",
    )
    _finite_vector(machine.get("final_observed_angles_deg"), 4, "final observed angles")
    _finite_vector(
        machine.get("final_backend_interpolated_target_angles_deg"),
        4,
        "final backend target",
    )
    _finite_vector(
        machine.get("final_joint_position_target_angles_deg"),
        4,
        "final joint position target",
    )

    gravity = _object(
        measurement.get("gravity_feed_forward"), "measurement.gravity_feed_forward"
    )
    if (
        gravity.get("telemetry_complete") is not True
        or gravity.get("sample_count") != len(gravity_samples)
    ):
        raise PregraspContractVerificationError(
            "gravity feed-forward summary is incomplete or misaligned"
        )
    projected = _object(
        machine.get("projected_joint_force_telemetry"),
        "projected_joint_force_telemetry",
    )
    if projected.get("observation_count") != len(observations):
        raise PregraspContractVerificationError(
            "projected-force summary is not aligned with observations"
        )
    projected_checks = _object(
        projected.get("checks"), "projected_joint_force_telemetry.checks"
    )
    if any(value is not True for value in projected_checks.values()):
        raise PregraspContractVerificationError(
            "projected-force telemetry checks did not all pass"
        )

    if contract.get("scope") != EXPECTED_MACHINE_SCOPE:
        raise PregraspContractVerificationError("machine scope exceeds Goal 5 pre-grasp")
    visual = _object(acceptance.get("visual"), "acceptance.visual")
    if visual.get("status") != "pending_user_confirmation":
        raise PregraspContractVerificationError(
            "headless machine contract must leave visual acceptance pending"
        )
    if acceptance.get("goal5_complete") is not False:
        raise PregraspContractVerificationError(
            "headless machine contract cannot mark Goal 5 complete"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    parser.add_argument("--preflight-contract", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_contract(args.contract)
        preflight_contract = load_json_object(
            args.preflight_contract,
            label="GPU preflight contract",
        )
        verify_machine_contract(
            contract,
            expected_git_commit=args.expected_git_commit,
            preflight_contract=preflight_contract,
            project_dir=args.project_dir,
        )
    except (PregraspContractVerificationError, PregraspGpuPreflightError) as error:
        print(f"[PREGRASP CONTRACT] FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "[PREGRASP CONTRACT] PASS: "
        f"commit={args.expected_git_commit} contract={args.contract}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
