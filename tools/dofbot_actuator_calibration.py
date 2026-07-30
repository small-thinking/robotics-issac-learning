"""Pure contracts for DOFBOT actuator tracking calibration.

The calibration separates the vendor-shaped API request, Isaac position-target
buffer, and settled articulation observation.  It deliberately treats tracking
failure as diagnostic evidence rather than as a reason to discard the run.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .dofbot_control_api import CONTROLLED_JOINT_NAMES
except ImportError:
    from dofbot_control_api import CONTROLLED_JOINT_NAMES

REQUIRED_CASE_NAMES = (
    "gravity_on_effort_100",
    "gravity_off_effort_100",
    "gravity_on_effort_250",
)
REQUIRED_POSE_NAMES = (
    "neutral_start",
    "mid_load",
    "pregrasp_candidate",
    "neutral_return",
)
MAXIMUM_PLANNED_VELOCITY_DEG_S = 20.0
MAXIMUM_PLANNED_ACCELERATION_DEG_S2 = 60.0
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ActuatorCalibrationError(ValueError):
    """Raised when a calibration input or result is incomplete or unsafe."""


@dataclass(frozen=True)
class CalibrationPose:
    name: str
    angles_deg: tuple[int, int, int, int]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "angles_deg": list(self.angles_deg)}


@dataclass(frozen=True)
class CalibrationCase:
    name: str
    gravity_enabled: bool
    effort_limit_sim: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "gravity_enabled": self.gravity_enabled,
            "effort_limit_sim": self.effort_limit_sim,
        }


@dataclass(frozen=True)
class TrajectoryConfig:
    duration_ms: int
    settle_velocity_threshold_deg_s: float
    settle_hold_ms: int
    settle_timeout_ms: int
    sample_every_physics_step: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_ms": self.duration_ms,
            "settle_velocity_threshold_deg_s": (
                self.settle_velocity_threshold_deg_s
            ),
            "settle_hold_ms": self.settle_hold_ms,
            "settle_timeout_ms": self.settle_timeout_ms,
            "sample_every_physics_step": self.sample_every_physics_step,
        }


@dataclass(frozen=True)
class CalibrationAcceptance:
    maximum_target_buffer_error_deg: float
    maximum_settled_tracking_error_deg: float
    maximum_overshoot_deg: float
    maximum_contact_force_n: float

    def to_dict(self) -> dict[str, float]:
        return {
            "maximum_target_buffer_error_deg": (
                self.maximum_target_buffer_error_deg
            ),
            "maximum_settled_tracking_error_deg": (
                self.maximum_settled_tracking_error_deg
            ),
            "maximum_overshoot_deg": self.maximum_overshoot_deg,
            "maximum_contact_force_n": self.maximum_contact_force_n,
        }


@dataclass(frozen=True)
class ActuatorCalibrationConfig:
    schema_version: int
    name: str
    controlled_joint_names: tuple[str, str, str, str]
    safe_angle_min_deg: int
    safe_angle_max_deg: int
    poses: tuple[CalibrationPose, ...]
    trajectory: TrajectoryConfig
    cases: tuple[CalibrationCase, ...]
    acceptance: CalibrationAcceptance

    def case(self, name: str) -> CalibrationCase:
        for case in self.cases:
            if case.name == name:
                return case
        raise ActuatorCalibrationError(f"unknown calibration case: {name}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "controlled_joint_names": list(self.controlled_joint_names),
            "safe_angle_min_deg": self.safe_angle_min_deg,
            "safe_angle_max_deg": self.safe_angle_max_deg,
            "poses": [pose.to_dict() for pose in self.poses],
            "trajectory": self.trajectory.to_dict(),
            "cases": [case.to_dict() for case in self.cases],
            "acceptance": self.acceptance.to_dict(),
        }


def _strict_object(
    value: Any,
    expected_keys: set[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ActuatorCalibrationError(f"{label} must be an object")
    if set(value) != expected_keys:
        raise ActuatorCalibrationError(
            f"{label} keys must match {sorted(expected_keys)}"
        )
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ActuatorCalibrationError(f"{label} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise ActuatorCalibrationError(f"{label} must be finite")
    return converted


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ActuatorCalibrationError(f"{label} must be an integer")
    return value


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _NAME_PATTERN.fullmatch(value):
        raise ActuatorCalibrationError(
            f"{label} must be a lowercase snake_case identifier"
        )
    return value


def _four_numbers(value: Any, label: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ActuatorCalibrationError(f"{label} must contain four values")
    converted = tuple(_number(item, f"{label}[{index}]") for index, item in enumerate(value))
    return converted  # type: ignore[return-value]


def parse_actuator_calibration_config(value: Any) -> ActuatorCalibrationConfig:
    raw = _strict_object(
        value,
        {
            "schema_version",
            "name",
            "controlled_joint_names",
            "safe_angle_min_deg",
            "safe_angle_max_deg",
            "poses",
            "trajectory",
            "cases",
            "acceptance",
        },
        "calibration config",
    )
    schema_version = _integer(raw["schema_version"], "schema_version")
    if schema_version != 1:
        raise ActuatorCalibrationError("schema_version must be 1")
    name = _name(raw["name"], "name")
    controlled = raw["controlled_joint_names"]
    if controlled != list(CONTROLLED_JOINT_NAMES):
        raise ActuatorCalibrationError(
            "controlled_joint_names must be joint1 through joint4 in order"
        )
    safe_min = _integer(raw["safe_angle_min_deg"], "safe_angle_min_deg")
    safe_max = _integer(raw["safe_angle_max_deg"], "safe_angle_max_deg")
    if (safe_min, safe_max) != (60, 120):
        raise ActuatorCalibrationError(
            "calibration must preserve the validated 60-120 degree envelope"
        )

    poses_raw = raw["poses"]
    if not isinstance(poses_raw, list) or len(poses_raw) != len(REQUIRED_POSE_NAMES):
        raise ActuatorCalibrationError("poses must contain the four required probes")
    poses: list[CalibrationPose] = []
    for index, item in enumerate(poses_raw):
        pose_raw = _strict_object(item, {"name", "angles_deg"}, f"poses[{index}]")
        pose_name = _name(pose_raw["name"], f"poses[{index}].name")
        angles_value = pose_raw["angles_deg"]
        if not isinstance(angles_value, list) or len(angles_value) != 4:
            raise ActuatorCalibrationError(
                f"poses[{index}].angles_deg must contain four integers"
            )
        angles = tuple(
            _integer(angle, f"poses[{index}].angles_deg[{joint_index}]")
            for joint_index, angle in enumerate(angles_value)
        )
        if any(angle < safe_min or angle > safe_max for angle in angles):
            raise ActuatorCalibrationError("calibration pose leaves the safe envelope")
        poses.append(
            CalibrationPose(
                name=pose_name,
                angles_deg=angles,  # type: ignore[arg-type]
            )
        )
    if tuple(pose.name for pose in poses) != REQUIRED_POSE_NAMES:
        raise ActuatorCalibrationError(
            f"pose order must be {list(REQUIRED_POSE_NAMES)}"
        )
    if poses[0].angles_deg != (90, 90, 90, 90) or poses[-1].angles_deg != (
        90,
        90,
        90,
        90,
    ):
        raise ActuatorCalibrationError("calibration must start and end neutral")
    if poses[2].angles_deg != (90, 66, 66, 66):
        raise ActuatorCalibrationError(
            "pregrasp_candidate must reproduce the failed 90/66/66/66 endpoint"
        )

    trajectory_raw = _strict_object(
        raw["trajectory"],
        {
            "duration_ms",
            "settle_velocity_threshold_deg_s",
            "settle_hold_ms",
            "settle_timeout_ms",
            "sample_every_physics_step",
        },
        "trajectory",
    )
    duration_ms = _integer(trajectory_raw["duration_ms"], "trajectory.duration_ms")
    settle_hold_ms = _integer(
        trajectory_raw["settle_hold_ms"],
        "trajectory.settle_hold_ms",
    )
    settle_timeout_ms = _integer(
        trajectory_raw["settle_timeout_ms"],
        "trajectory.settle_timeout_ms",
    )
    velocity_threshold = _number(
        trajectory_raw["settle_velocity_threshold_deg_s"],
        "trajectory.settle_velocity_threshold_deg_s",
    )
    sample_every_step = trajectory_raw["sample_every_physics_step"]
    if not isinstance(sample_every_step, bool) or not sample_every_step:
        raise ActuatorCalibrationError(
            "calibration must sample every physics step"
        )
    if not 200 <= duration_ms <= 3000:
        raise ActuatorCalibrationError("trajectory.duration_ms must be in [200, 3000]")
    if not 100 <= settle_hold_ms <= 2000:
        raise ActuatorCalibrationError(
            "trajectory.settle_hold_ms must be in [100, 2000]"
        )
    if not 1000 <= settle_timeout_ms <= 10_000:
        raise ActuatorCalibrationError(
            "trajectory.settle_timeout_ms must be in [1000, 10000]"
        )
    if not 0.02 <= velocity_threshold <= 0.5:
        raise ActuatorCalibrationError(
            "settle velocity threshold must be in [0.02, 0.5] deg/s"
        )
    trajectory = TrajectoryConfig(
        duration_ms=duration_ms,
        settle_velocity_threshold_deg_s=velocity_threshold,
        settle_hold_ms=settle_hold_ms,
        settle_timeout_ms=settle_timeout_ms,
        sample_every_physics_step=sample_every_step,
    )
    duration_s = duration_ms / 1000.0
    maximum_transition_delta = max(
        abs(current - previous)
        for previous_pose, current_pose in zip(
            poses,
            poses[1:],
            strict=False,
        )
        for previous, current in zip(
            previous_pose.angles_deg,
            current_pose.angles_deg,
            strict=True,
        )
    )
    smoothstep_peak_velocity = (
        1.5 * maximum_transition_delta / duration_s
    )
    smoothstep_peak_acceleration = (
        6.0 * maximum_transition_delta / (duration_s * duration_s)
    )
    if smoothstep_peak_velocity > MAXIMUM_PLANNED_VELOCITY_DEG_S:
        raise ActuatorCalibrationError(
            "smoothstep calibration trajectory exceeds 20 deg/s"
        )
    if smoothstep_peak_acceleration > MAXIMUM_PLANNED_ACCELERATION_DEG_S2:
        raise ActuatorCalibrationError(
            "smoothstep calibration trajectory exceeds 60 deg/s^2"
        )

    cases_raw = raw["cases"]
    if not isinstance(cases_raw, list) or len(cases_raw) != len(REQUIRED_CASE_NAMES):
        raise ActuatorCalibrationError("cases must contain the three diagnostic cases")
    cases: list[CalibrationCase] = []
    for index, item in enumerate(cases_raw):
        case_raw = _strict_object(
            item,
            {"name", "gravity_enabled", "effort_limit_sim"},
            f"cases[{index}]",
        )
        case_name = _name(case_raw["name"], f"cases[{index}].name")
        gravity_enabled = case_raw["gravity_enabled"]
        if not isinstance(gravity_enabled, bool):
            raise ActuatorCalibrationError(
                f"cases[{index}].gravity_enabled must be boolean"
            )
        effort = _number(
            case_raw["effort_limit_sim"],
            f"cases[{index}].effort_limit_sim",
        )
        if not 50.0 <= effort <= 300.0:
            raise ActuatorCalibrationError("effort_limit_sim must be in [50, 300]")
        cases.append(
            CalibrationCase(
                name=case_name,
                gravity_enabled=gravity_enabled,
                effort_limit_sim=effort,
            )
        )
    if tuple(case.name for case in cases) != REQUIRED_CASE_NAMES:
        raise ActuatorCalibrationError(
            f"case order must be {list(REQUIRED_CASE_NAMES)}"
        )
    expected_case_values = (
        (True, 100.0),
        (False, 100.0),
        (True, 250.0),
    )
    if tuple(
        (case.gravity_enabled, case.effort_limit_sim) for case in cases
    ) != expected_case_values:
        raise ActuatorCalibrationError(
            "diagnostic cases must isolate gravity and the 100-to-250 effort change"
        )

    acceptance_raw = _strict_object(
        raw["acceptance"],
        {
            "maximum_target_buffer_error_deg",
            "maximum_settled_tracking_error_deg",
            "maximum_overshoot_deg",
            "maximum_contact_force_n",
        },
        "acceptance",
    )
    target_error = _number(
        acceptance_raw["maximum_target_buffer_error_deg"],
        "acceptance.maximum_target_buffer_error_deg",
    )
    tracking_error = _number(
        acceptance_raw["maximum_settled_tracking_error_deg"],
        "acceptance.maximum_settled_tracking_error_deg",
    )
    overshoot = _number(
        acceptance_raw["maximum_overshoot_deg"],
        "acceptance.maximum_overshoot_deg",
    )
    contact_force = _number(
        acceptance_raw["maximum_contact_force_n"],
        "acceptance.maximum_contact_force_n",
    )
    if not 0.001 <= target_error <= 0.1:
        raise ActuatorCalibrationError(
            "maximum_target_buffer_error_deg must be in [0.001, 0.1]"
        )
    if not 0.1 <= tracking_error <= 1.0:
        raise ActuatorCalibrationError(
            "maximum_settled_tracking_error_deg must be in [0.1, 1.0]"
        )
    if not 0.5 <= overshoot <= 3.0:
        raise ActuatorCalibrationError("maximum_overshoot_deg must be in [0.5, 3]")
    if not 0.05 <= contact_force <= 0.5:
        raise ActuatorCalibrationError(
            "maximum_contact_force_n must be in [0.05, 0.5]"
        )
    acceptance = CalibrationAcceptance(
        maximum_target_buffer_error_deg=target_error,
        maximum_settled_tracking_error_deg=tracking_error,
        maximum_overshoot_deg=overshoot,
        maximum_contact_force_n=contact_force,
    )

    return ActuatorCalibrationConfig(
        schema_version=schema_version,
        name=name,
        controlled_joint_names=tuple(controlled),  # type: ignore[arg-type]
        safe_angle_min_deg=safe_min,
        safe_angle_max_deg=safe_max,
        poses=tuple(poses),
        trajectory=trajectory,
        cases=tuple(cases),
        acceptance=acceptance,
    )


def load_actuator_calibration_config(
    path: Path,
) -> tuple[ActuatorCalibrationConfig, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ActuatorCalibrationError(f"{path} is not valid JSON") from error
    return parse_actuator_calibration_config(value), hashlib.sha256(raw).hexdigest()


def calibration_trajectory_extrema(
    config: ActuatorCalibrationConfig,
) -> dict[str, float]:
    maximum_transition_delta = max(
        abs(current - previous)
        for previous_pose, current_pose in zip(
            config.poses,
            config.poses[1:],
            strict=False,
        )
        for previous, current in zip(
            previous_pose.angles_deg,
            current_pose.angles_deg,
            strict=True,
        )
    )
    duration_s = config.trajectory.duration_ms / 1000.0
    return {
        "maximum_transition_delta_deg": float(maximum_transition_delta),
        "smoothstep_peak_velocity_deg_s": (
            1.5 * maximum_transition_delta / duration_s
        ),
        "smoothstep_peak_acceleration_deg_s2": (
            6.0 * maximum_transition_delta / (duration_s * duration_s)
        ),
    }


def maximum_vector_error_deg(
    actual: Any,
    expected: Any,
    *,
    label: str,
) -> float:
    actual_values = _four_numbers(actual, f"{label}.actual")
    expected_values = _four_numbers(expected, f"{label}.expected")
    return max(
        abs(actual_value - expected_value)
        for actual_value, expected_value in zip(
            actual_values,
            expected_values,
            strict=True,
        )
    )


def evaluate_calibration_case(
    config: ActuatorCalibrationConfig,
    case: CalibrationCase,
    pose_summaries: Any,
    *,
    official_api_call_count: Any,
    target_buffer_available: Any,
    actual_velocity_available: Any,
    torque_interpretation: Any,
    torque_saturation_observed: Any,
) -> dict[str, Any]:
    if not isinstance(pose_summaries, list):
        raise ActuatorCalibrationError("pose_summaries must be a list")
    if len(pose_summaries) != len(config.poses):
        raise ActuatorCalibrationError("pose_summaries has the wrong count")
    expected_api_calls = len(config.poses) * len(CONTROLLED_JOINT_NAMES)
    if isinstance(official_api_call_count, bool) or not isinstance(
        official_api_call_count,
        int,
    ):
        raise ActuatorCalibrationError("official_api_call_count must be an integer")
    if not isinstance(target_buffer_available, bool):
        raise ActuatorCalibrationError("target_buffer_available must be boolean")
    if not isinstance(actual_velocity_available, bool):
        raise ActuatorCalibrationError("actual_velocity_available must be boolean")
    if torque_interpretation not in {
        "measured_nonzero_buffers",
        "implicit_zero_or_unavailable_do_not_infer",
    }:
        raise ActuatorCalibrationError("torque interpretation is not explicit")
    if not isinstance(torque_saturation_observed, bool):
        raise ActuatorCalibrationError(
            "torque_saturation_observed must be boolean"
        )
    if (
        torque_saturation_observed
        and torque_interpretation != "measured_nonzero_buffers"
    ):
        raise ActuatorCalibrationError(
            "torque saturation requires meaningful nonzero torque buffers"
        )

    normalized: list[dict[str, Any]] = []
    for index, (summary, pose) in enumerate(
        zip(pose_summaries, config.poses, strict=True)
    ):
        raw = _strict_object(
            summary,
            {
                "name",
                "command_angles_deg",
                "settled",
                "settle_elapsed_s",
                "terminal_observed_angles_deg",
                "terminal_actual_velocities_deg_s",
                "maximum_tracking_error_deg",
                "maximum_target_buffer_error_deg",
                "maximum_overshoot_deg",
                "maximum_contact_force_n",
                "terminal_body_positions_world_m",
            },
            f"pose_summaries[{index}]",
        )
        if raw["name"] != pose.name:
            raise ActuatorCalibrationError("pose summary order does not match config")
        command_angles = _four_numbers(
            raw["command_angles_deg"],
            f"pose_summaries[{index}].command_angles_deg",
        )
        if command_angles != tuple(float(value) for value in pose.angles_deg):
            raise ActuatorCalibrationError("pose summary command differs from config")
        if not isinstance(raw["settled"], bool):
            raise ActuatorCalibrationError("pose summary settled must be boolean")
        observed = _four_numbers(
            raw["terminal_observed_angles_deg"],
            f"pose_summaries[{index}].terminal_observed_angles_deg",
        )
        velocities = _four_numbers(
            raw["terminal_actual_velocities_deg_s"],
            f"pose_summaries[{index}].terminal_actual_velocities_deg_s",
        )
        numeric = {
            key: _number(raw[key], f"pose_summaries[{index}].{key}")
            for key in (
                "settle_elapsed_s",
                "maximum_tracking_error_deg",
                "maximum_target_buffer_error_deg",
                "maximum_overshoot_deg",
                "maximum_contact_force_n",
            )
        }
        if not isinstance(raw["terminal_body_positions_world_m"], dict):
            raise ActuatorCalibrationError(
                "terminal_body_positions_world_m must be an object"
            )
        normalized.append(
            {
                **raw,
                "command_angles_deg": list(command_angles),
                "terminal_observed_angles_deg": list(observed),
                "terminal_actual_velocities_deg_s": list(velocities),
                **numeric,
            }
        )

    maximum_tracking = max(
        summary["maximum_tracking_error_deg"] for summary in normalized
    )
    maximum_target_error = max(
        summary["maximum_target_buffer_error_deg"] for summary in normalized
    )
    maximum_overshoot = max(
        summary["maximum_overshoot_deg"] for summary in normalized
    )
    maximum_contact = max(
        summary["maximum_contact_force_n"] for summary in normalized
    )
    maximum_terminal_velocity = max(
        abs(value)
        for summary in normalized
        for value in summary["terminal_actual_velocities_deg_s"]
    )
    checks = {
        "pose_sequence_complete": True,
        "official_api_call_count_matches": (
            official_api_call_count == expected_api_calls
        ),
        "target_buffer_telemetry_available": target_buffer_available,
        "actual_joint_velocity_telemetry_available": actual_velocity_available,
        "all_poses_settled_by_actual_velocity": all(
            summary["settled"] for summary in normalized
        ),
        "target_buffer_matches_backend_target": (
            target_buffer_available
            and maximum_target_error
            <= config.acceptance.maximum_target_buffer_error_deg
        ),
        "overshoot_within_diagnostic_limit": (
            maximum_overshoot <= config.acceptance.maximum_overshoot_deg
        ),
        "contact_force_below_threshold": (
            maximum_contact <= config.acceptance.maximum_contact_force_n
        ),
        "torque_observability_declared": True,
    }
    diagnostic_complete = all(checks.values())
    tracking_gate_passed = (
        diagnostic_complete
        and maximum_tracking
        <= config.acceptance.maximum_settled_tracking_error_deg
    )
    return {
        "case": case.to_dict(),
        "pose_summaries": normalized,
        "official_api_call_count": official_api_call_count,
        "expected_official_api_call_count": expected_api_calls,
        "maximum_settled_tracking_error_deg": maximum_tracking,
        "maximum_target_buffer_error_deg": maximum_target_error,
        "maximum_overshoot_deg": maximum_overshoot,
        "maximum_contact_force_n": maximum_contact,
        "maximum_terminal_actual_velocity_deg_s": maximum_terminal_velocity,
        "torque_interpretation": torque_interpretation,
        "torque_saturation_observed": torque_saturation_observed,
        "checks": checks,
        "diagnostic_complete": diagnostic_complete,
        "tracking_gate_passed": tracking_gate_passed,
    }


def classify_calibration_matrix(
    config: ActuatorCalibrationConfig,
    case_evaluations: Any,
) -> dict[str, Any]:
    if not isinstance(case_evaluations, dict):
        raise ActuatorCalibrationError("case_evaluations must be an object")
    if set(case_evaluations) != set(REQUIRED_CASE_NAMES):
        return {
            "decision": "incomplete_case_matrix",
            "pregrasp_authorized": False,
            "next_action": "repair the missing calibration case before tuning",
        }

    cases = {name: case_evaluations[name] for name in REQUIRED_CASE_NAMES}
    for name, value in cases.items():
        if not isinstance(value, dict):
            raise ActuatorCalibrationError(f"case evaluation {name} must be an object")
    if any(
        not bool(value.get("checks", {}).get("contact_force_below_threshold"))
        for value in cases.values()
    ):
        decision = "contact_or_self_collision_interference"
        next_action = "inspect contact actors and remove collision interference"
    elif any(
        not bool(value.get("checks", {}).get("all_poses_settled_by_actual_velocity"))
        for value in cases.values()
    ):
        decision = "settling_or_drive_stability_failure"
        next_action = "inspect actual velocity, damping, solver iterations, and oscillation"
    elif any(
        not bool(value.get("checks", {}).get("target_buffer_telemetry_available"))
        or not bool(value.get("checks", {}).get("target_buffer_matches_backend_target"))
        for value in cases.values()
    ):
        decision = "backend_or_target_buffer_mismatch"
        next_action = "fix the API/backend/Isaac target path before changing actuator effort"
    elif any(not bool(value.get("diagnostic_complete")) for value in cases.values()):
        decision = "instrumentation_or_runtime_compatibility_failure"
        next_action = "repair missing telemetry or runtime compatibility before pre-grasp"
    else:
        baseline = cases["gravity_on_effort_100"]
        gravity_off = cases["gravity_off_effort_100"]
        higher_effort = cases["gravity_on_effort_250"]
        if bool(baseline.get("tracking_gate_passed")):
            decision = "baseline_tracking_identity_validated"
            next_action = "keep effort 100 and investigate task-scene-only differences"
        elif bool(baseline.get("torque_saturation_observed")):
            decision = "effort_saturation_observed"
            next_action = "tune the lowest stable effort using the measured clamp evidence"
        elif bool(gravity_off.get("tracking_gate_passed")):
            decision = "gravity_load_sensitive_tracking"
            next_action = "tune the lowest stable effort or gain using measured load evidence"
        elif bool(higher_effort.get("tracking_gate_passed")):
            decision = "effort_limit_sensitive_tracking"
            next_action = "adopt the lowest validated effort limit and rerun calibration"
        else:
            decision = "drive_gain_axis_solver_or_model_mapping_failure"
            next_action = (
                "inspect drive gains, axis mapping, solver settings, mass/inertia, "
                "and command-to-settled-state calibration"
            )

    return {
        "decision": decision,
        "pregrasp_authorized": False,
        "tracking_identity_validated": (
            decision == "baseline_tracking_identity_validated"
        ),
        "next_action": next_action,
        "unchanged_pregrasp_gates": {
            "maximum_position_error_m": 0.025,
            "maximum_approach_error_deg": 12.0,
        },
    }
