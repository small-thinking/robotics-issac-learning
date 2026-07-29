"""Pure pose-aware pre-grasp contracts and controller math for DOFBOT.

The grasp frame is derived from the two terminal finger bodies and the wrist.
Only joint1-joint4 are controlled. The fixed wrist-twist closing-axis
alignment is therefore monitored as an acceptance gate, never presented as a
controlled degree of freedom.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CONTROLLED_JOINT_NAMES = ("joint1", "joint2", "joint3", "joint4")
EXPECTED_FRAME_MODE = "terminal_finger_midpoint"
EXPECTED_APPROACH_DEFINITION = "wrist_to_finger_midpoint"
EXPECTED_CLOSING_DEFINITION = "left_tip_to_right_tip"
EXPECTED_CLOSING_CONTROL = "monitor_only_wrist_twist_uncontrolled"
EXPECTED_WRIST_BODY = "Wrist_Twist"
EXPECTED_LEFT_TIP_BODY = "Finger_Left_03"
EXPECTED_RIGHT_TIP_BODY = "Finger_Right_03"
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class PregraspPoseError(ValueError):
    """Raised when a pose contract, observation, or command is unsafe."""


@dataclass(frozen=True)
class SourceContracts:
    asset_contract_sha256: str
    scene_config_sha256: str


@dataclass(frozen=True)
class GraspFrameConfig:
    mode: str
    wrist_body_name: str
    left_tip_body_name: str
    right_tip_body_name: str
    approach_axis_definition: str
    closing_axis_definition: str
    minimum_finger_separation_m: float
    maximum_finger_separation_m: float
    minimum_axis_cross_norm: float


@dataclass(frozen=True)
class TargetPoseConfig:
    position_world_m: tuple[float, float, float]
    approach_axis_world_unit: tuple[float, float, float]
    closing_axis_world_unit: tuple[float, float, float]
    position_tolerance_m: float
    approach_tolerance_deg: float
    closing_tolerance_deg: float
    closing_axis_control: str


@dataclass(frozen=True)
class PoseSolverConfig:
    controlled_joint_names: tuple[str, str, str, str]
    control_hz: int
    maximum_steps: int
    damping: float
    translation_gain: float
    orientation_gain: float
    orientation_length_scale_m: float
    posture_weight: float
    posture_gain: float
    preferred_angles_deg: tuple[float, float, float, float]
    safe_angle_min_deg: float
    safe_angle_max_deg: float
    command_limit_margin_deg: float
    maximum_joint_delta_deg: float
    maximum_joint_velocity_deg_s: float
    maximum_joint_acceleration_deg_s2: float

    @property
    def control_dt_s(self) -> float:
        return 1.0 / self.control_hz


@dataclass(frozen=True)
class CollisionConfig:
    critical_body_names: tuple[str, ...]
    minimum_body_center_table_distance_m: float
    minimum_nonfinger_body_center_target_distance_m: float
    minimum_terminal_finger_target_distance_m: float
    maximum_contact_force_n: float
    require_static_target: bool
    contact_authorized: bool


@dataclass(frozen=True)
class AcceptanceConfig:
    minimum_position_improvement_m: float
    maximum_neutral_reset_error_deg: float
    viewer_connection_hold_seconds: int
    viewer_success_hold_seconds: int


@dataclass(frozen=True)
class PregraspPoseConfig:
    name: str
    source_contracts: SourceContracts
    grasp_frame: GraspFrameConfig
    target_pose: TargetPoseConfig
    solver: PoseSolverConfig
    collision: CollisionConfig
    acceptance: AcceptanceConfig


@dataclass(frozen=True)
class DerivedGraspFrame:
    origin_world_m: tuple[float, float, float]
    approach_axis_world_unit: tuple[float, float, float]
    closing_axis_world_unit: tuple[float, float, float]
    lateral_axis_world_unit: tuple[float, float, float]
    finger_separation_m: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin_world_m": list(self.origin_world_m),
            "approach_axis_world_unit": list(self.approach_axis_world_unit),
            "closing_axis_world_unit": list(self.closing_axis_world_unit),
            "lateral_axis_world_unit": list(self.lateral_axis_world_unit),
            "finger_separation_m": self.finger_separation_m,
        }


@dataclass(frozen=True)
class PoseCommand:
    angles_deg: tuple[float, float, float, float]
    velocities_deg_s: tuple[float, float, float, float]
    raw_delta_deg: tuple[float, float, float, float]
    position_error_m: tuple[float, float, float]
    approach_error_rad: tuple[float, float, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "angles_deg": list(self.angles_deg),
            "velocities_deg_s": list(self.velocities_deg_s),
            "raw_delta_deg": list(self.raw_delta_deg),
            "position_error_m": list(self.position_error_m),
            "approach_error_rad": list(self.approach_error_rad),
        }


def _strict_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise PregraspPoseError(
            f"{label} keys must match {sorted(keys)}; got {actual}"
        )
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PregraspPoseError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise PregraspPoseError(f"{label} must be finite")
    return result


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PregraspPoseError(f"{label} must be an integer")
    return value


def _vector(
    value: Any,
    *,
    length: int,
    label: str,
) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise PregraspPoseError(f"{label} must contain exactly {length} values")
    return tuple(_number(item, f"{label}[{index}]") for index, item in enumerate(value))


def _vector3(value: Any, label: str) -> tuple[float, float, float]:
    values = _vector(value, length=3, label=label)
    return values  # type: ignore[return-value]


def _vector4(value: Any, label: str) -> tuple[float, float, float, float]:
    values = _vector(value, length=4, label=label)
    return values  # type: ignore[return-value]


def _sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PregraspPoseError(f"{label} must be a lowercase SHA-256")
    return value


def _unit_vector(value: Any, label: str) -> tuple[float, float, float]:
    vector = _vector3(value, label)
    norm = math.sqrt(sum(component * component for component in vector))
    if not math.isclose(norm, 1.0, abs_tol=1e-8):
        raise PregraspPoseError(f"{label} must be unit length")
    return vector


def parse_pregrasp_pose_config(value: Any) -> PregraspPoseConfig:
    raw = _strict_object(
        value,
        {
            "schema_version",
            "name",
            "source_contracts",
            "grasp_frame",
            "target_pose",
            "solver",
            "collision",
            "acceptance",
        },
        "root",
    )
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(
        raw["schema_version"], bool
    ):
        raise PregraspPoseError(f"schema_version must equal {SCHEMA_VERSION}")
    name = raw["name"]
    if not isinstance(name, str) or _NAME_PATTERN.fullmatch(name) is None:
        raise PregraspPoseError("name must be lowercase snake_case")

    source_raw = _strict_object(
        raw["source_contracts"],
        {"asset_contract_sha256", "scene_config_sha256"},
        "source_contracts",
    )
    sources = SourceContracts(
        asset_contract_sha256=_sha256(
            source_raw["asset_contract_sha256"],
            "source_contracts.asset_contract_sha256",
        ),
        scene_config_sha256=_sha256(
            source_raw["scene_config_sha256"],
            "source_contracts.scene_config_sha256",
        ),
    )

    frame_raw = _strict_object(
        raw["grasp_frame"],
        {
            "mode",
            "wrist_body_name",
            "left_tip_body_name",
            "right_tip_body_name",
            "approach_axis_definition",
            "closing_axis_definition",
            "minimum_finger_separation_m",
            "maximum_finger_separation_m",
            "minimum_axis_cross_norm",
        },
        "grasp_frame",
    )
    exact_frame_values = {
        "mode": EXPECTED_FRAME_MODE,
        "wrist_body_name": EXPECTED_WRIST_BODY,
        "left_tip_body_name": EXPECTED_LEFT_TIP_BODY,
        "right_tip_body_name": EXPECTED_RIGHT_TIP_BODY,
        "approach_axis_definition": EXPECTED_APPROACH_DEFINITION,
        "closing_axis_definition": EXPECTED_CLOSING_DEFINITION,
    }
    for field, expected in exact_frame_values.items():
        if frame_raw[field] != expected:
            raise PregraspPoseError(f"grasp_frame.{field} must equal {expected}")
    minimum_separation = _number(
        frame_raw["minimum_finger_separation_m"],
        "grasp_frame.minimum_finger_separation_m",
    )
    maximum_separation = _number(
        frame_raw["maximum_finger_separation_m"],
        "grasp_frame.maximum_finger_separation_m",
    )
    cross_norm = _number(
        frame_raw["minimum_axis_cross_norm"],
        "grasp_frame.minimum_axis_cross_norm",
    )
    if not 0.001 <= minimum_separation < maximum_separation <= 0.20:
        raise PregraspPoseError("finger separation bounds must satisfy 0.001 <= min < max <= 0.20")
    if not 0.1 <= cross_norm <= 0.95:
        raise PregraspPoseError("minimum_axis_cross_norm must be in [0.1, 0.95]")
    frame = GraspFrameConfig(
        mode=frame_raw["mode"],
        wrist_body_name=frame_raw["wrist_body_name"],
        left_tip_body_name=frame_raw["left_tip_body_name"],
        right_tip_body_name=frame_raw["right_tip_body_name"],
        approach_axis_definition=frame_raw["approach_axis_definition"],
        closing_axis_definition=frame_raw["closing_axis_definition"],
        minimum_finger_separation_m=minimum_separation,
        maximum_finger_separation_m=maximum_separation,
        minimum_axis_cross_norm=cross_norm,
    )

    target_raw = _strict_object(
        raw["target_pose"],
        {
            "position_world_m",
            "approach_axis_world_unit",
            "closing_axis_world_unit",
            "position_tolerance_m",
            "approach_tolerance_deg",
            "closing_tolerance_deg",
            "closing_axis_control",
        },
        "target_pose",
    )
    target_position = _vector3(
        target_raw["position_world_m"],
        "target_pose.position_world_m",
    )
    target_approach = _unit_vector(
        target_raw["approach_axis_world_unit"],
        "target_pose.approach_axis_world_unit",
    )
    target_closing = _unit_vector(
        target_raw["closing_axis_world_unit"],
        "target_pose.closing_axis_world_unit",
    )
    if abs(_dot(target_approach, target_closing)) > 1e-8:
        raise PregraspPoseError("target approach and closing axes must be orthogonal")
    position_tolerance = _number(
        target_raw["position_tolerance_m"],
        "target_pose.position_tolerance_m",
    )
    approach_tolerance = _number(
        target_raw["approach_tolerance_deg"],
        "target_pose.approach_tolerance_deg",
    )
    closing_tolerance = _number(
        target_raw["closing_tolerance_deg"],
        "target_pose.closing_tolerance_deg",
    )
    if not 0.005 <= position_tolerance <= 0.05:
        raise PregraspPoseError("position_tolerance_m must be in [0.005, 0.05]")
    if not 2.0 <= approach_tolerance <= 20.0:
        raise PregraspPoseError("approach_tolerance_deg must be in [2, 20]")
    if not 5.0 <= closing_tolerance <= 30.0:
        raise PregraspPoseError("closing_tolerance_deg must be in [5, 30]")
    if target_raw["closing_axis_control"] != EXPECTED_CLOSING_CONTROL:
        raise PregraspPoseError(
            f"target_pose.closing_axis_control must equal {EXPECTED_CLOSING_CONTROL}"
        )
    target = TargetPoseConfig(
        position_world_m=target_position,
        approach_axis_world_unit=target_approach,
        closing_axis_world_unit=target_closing,
        position_tolerance_m=position_tolerance,
        approach_tolerance_deg=approach_tolerance,
        closing_tolerance_deg=closing_tolerance,
        closing_axis_control=target_raw["closing_axis_control"],
    )

    solver_raw = _strict_object(
        raw["solver"],
        {
            "controlled_joint_names",
            "control_hz",
            "maximum_steps",
            "damping",
            "translation_gain",
            "orientation_gain",
            "orientation_length_scale_m",
            "posture_weight",
            "posture_gain",
            "preferred_angles_deg",
            "safe_angle_min_deg",
            "safe_angle_max_deg",
            "command_limit_margin_deg",
            "maximum_joint_delta_deg",
            "maximum_joint_velocity_deg_s",
            "maximum_joint_acceleration_deg_s2",
        },
        "solver",
    )
    joint_names = solver_raw["controlled_joint_names"]
    if not isinstance(joint_names, list) or tuple(joint_names) != CONTROLLED_JOINT_NAMES:
        raise PregraspPoseError("solver.controlled_joint_names must be joint1-joint4")
    control_hz = _integer(solver_raw["control_hz"], "solver.control_hz")
    maximum_steps = _integer(solver_raw["maximum_steps"], "solver.maximum_steps")
    if not 2 <= control_hz <= 10:
        raise PregraspPoseError("solver.control_hz must be in [2, 10]")
    if not 1 <= maximum_steps <= 100:
        raise PregraspPoseError("solver.maximum_steps must be in [1, 100]")
    numeric_solver = {
        field: _number(solver_raw[field], f"solver.{field}")
        for field in (
            "damping",
            "translation_gain",
            "orientation_gain",
            "orientation_length_scale_m",
            "posture_weight",
            "posture_gain",
            "safe_angle_min_deg",
            "safe_angle_max_deg",
            "command_limit_margin_deg",
            "maximum_joint_delta_deg",
            "maximum_joint_velocity_deg_s",
            "maximum_joint_acceleration_deg_s2",
        )
    }
    if not 0.01 <= numeric_solver["damping"] <= 0.5:
        raise PregraspPoseError("solver.damping must be in [0.01, 0.5]")
    if not 0.05 <= numeric_solver["translation_gain"] <= 1.0:
        raise PregraspPoseError("solver.translation_gain must be in [0.05, 1]")
    if not 0.05 <= numeric_solver["orientation_gain"] <= 1.0:
        raise PregraspPoseError("solver.orientation_gain must be in [0.05, 1]")
    if not 0.01 <= numeric_solver["orientation_length_scale_m"] <= 0.20:
        raise PregraspPoseError("orientation_length_scale_m must be in [0.01, 0.20]")
    if not 0.0 < numeric_solver["posture_weight"] <= 0.10:
        raise PregraspPoseError("solver.posture_weight must be in (0, 0.10]")
    if not 0.0 < numeric_solver["posture_gain"] <= 0.5:
        raise PregraspPoseError("solver.posture_gain must be in (0, 0.5]")
    safe_min = numeric_solver["safe_angle_min_deg"]
    safe_max = numeric_solver["safe_angle_max_deg"]
    margin = numeric_solver["command_limit_margin_deg"]
    if (safe_min, safe_max) != (60.0, 120.0):
        raise PregraspPoseError("solver safe angle envelope must remain [60, 120]")
    if not 4.0 <= margin <= 15.0 or safe_min + margin >= safe_max - margin:
        raise PregraspPoseError("solver.command_limit_margin_deg is invalid")
    if not 0.5 <= numeric_solver["maximum_joint_delta_deg"] <= 4.0:
        raise PregraspPoseError("maximum_joint_delta_deg must be in [0.5, 4]")
    if not 5.0 <= numeric_solver["maximum_joint_velocity_deg_s"] <= 30.0:
        raise PregraspPoseError("maximum_joint_velocity_deg_s must be in [5, 30]")
    if not 20.0 <= numeric_solver["maximum_joint_acceleration_deg_s2"] <= 100.0:
        raise PregraspPoseError(
            "maximum_joint_acceleration_deg_s2 must be in [20, 100]"
        )
    preferred = _vector4(
        solver_raw["preferred_angles_deg"],
        "solver.preferred_angles_deg",
    )
    command_min = safe_min + margin
    command_max = safe_max - margin
    if any(angle < command_min or angle > command_max for angle in preferred):
        raise PregraspPoseError("preferred angles must stay inside command margins")
    solver = PoseSolverConfig(
        controlled_joint_names=CONTROLLED_JOINT_NAMES,
        control_hz=control_hz,
        maximum_steps=maximum_steps,
        preferred_angles_deg=preferred,
        **numeric_solver,
    )

    collision_raw = _strict_object(
        raw["collision"],
        {
            "critical_body_names",
            "minimum_body_center_table_distance_m",
            "minimum_nonfinger_body_center_target_distance_m",
            "minimum_terminal_finger_target_distance_m",
            "maximum_contact_force_n",
            "require_static_target",
            "contact_authorized",
        },
        "collision",
    )
    body_names = collision_raw["critical_body_names"]
    if (
        not isinstance(body_names, list)
        or not body_names
        or any(not isinstance(value, str) for value in body_names)
        or len(body_names) != len(set(body_names))
    ):
        raise PregraspPoseError("collision.critical_body_names must be unique strings")
    if EXPECTED_LEFT_TIP_BODY not in body_names or EXPECTED_RIGHT_TIP_BODY not in body_names:
        raise PregraspPoseError("collision bodies must include both terminal fingers")
    table_distance = _number(
        collision_raw["minimum_body_center_table_distance_m"],
        "collision.minimum_body_center_table_distance_m",
    )
    nonfinger_distance = _number(
        collision_raw["minimum_nonfinger_body_center_target_distance_m"],
        "collision.minimum_nonfinger_body_center_target_distance_m",
    )
    finger_distance = _number(
        collision_raw["minimum_terminal_finger_target_distance_m"],
        "collision.minimum_terminal_finger_target_distance_m",
    )
    maximum_contact_force = _number(
        collision_raw["maximum_contact_force_n"],
        "collision.maximum_contact_force_n",
    )
    if not 0.005 <= table_distance <= 0.05:
        raise PregraspPoseError("table body-center distance must be in [0.005, 0.05]")
    if not 0.01 <= nonfinger_distance <= 0.10:
        raise PregraspPoseError("nonfinger target distance must be in [0.01, 0.10]")
    if not 0.02 <= finger_distance <= 0.10:
        raise PregraspPoseError("terminal finger target distance must be in [0.02, 0.10]")
    if not 0.0 <= maximum_contact_force <= 2.0:
        raise PregraspPoseError("maximum_contact_force_n must be in [0, 2]")
    if collision_raw["require_static_target"] is not True:
        raise PregraspPoseError("collision.require_static_target must be true")
    if collision_raw["contact_authorized"] is not False:
        raise PregraspPoseError("collision.contact_authorized must be false")
    collision = CollisionConfig(
        critical_body_names=tuple(body_names),
        minimum_body_center_table_distance_m=table_distance,
        minimum_nonfinger_body_center_target_distance_m=nonfinger_distance,
        minimum_terminal_finger_target_distance_m=finger_distance,
        maximum_contact_force_n=maximum_contact_force,
        require_static_target=True,
        contact_authorized=False,
    )

    acceptance_raw = _strict_object(
        raw["acceptance"],
        {
            "minimum_position_improvement_m",
            "maximum_neutral_reset_error_deg",
            "viewer_connection_hold_seconds",
            "viewer_success_hold_seconds",
        },
        "acceptance",
    )
    reset = _number(
        acceptance_raw["maximum_neutral_reset_error_deg"],
        "acceptance.maximum_neutral_reset_error_deg",
    )
    improvement = _number(
        acceptance_raw["minimum_position_improvement_m"],
        "acceptance.minimum_position_improvement_m",
    )
    connection_hold = _integer(
        acceptance_raw["viewer_connection_hold_seconds"],
        "acceptance.viewer_connection_hold_seconds",
    )
    success_hold = _integer(
        acceptance_raw["viewer_success_hold_seconds"],
        "acceptance.viewer_success_hold_seconds",
    )
    if not 0.01 <= improvement <= 0.20:
        raise PregraspPoseError("minimum_position_improvement_m must be in [0.01, 0.20]")
    if not 0.1 <= reset <= 2.0:
        raise PregraspPoseError("maximum_neutral_reset_error_deg must be in [0.1, 2]")
    if not 0 <= connection_hold <= 60 or not 0 <= success_hold <= 10:
        raise PregraspPoseError("viewer hold seconds are outside safe bounds")
    acceptance = AcceptanceConfig(
        minimum_position_improvement_m=improvement,
        maximum_neutral_reset_error_deg=reset,
        viewer_connection_hold_seconds=connection_hold,
        viewer_success_hold_seconds=success_hold,
    )
    return PregraspPoseConfig(
        name=name,
        source_contracts=sources,
        grasp_frame=frame,
        target_pose=target,
        solver=solver,
        collision=collision,
        acceptance=acceptance,
    )


def load_pregrasp_pose_config(path: Path) -> tuple[PregraspPoseConfig, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PregraspPoseError(f"{path} is not valid JSON: {error}") from error
    return parse_pregrasp_pose_config(value), hashlib.sha256(raw).hexdigest()


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _cross(
    left: Sequence[float],
    right: Sequence[float],
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _subtract(
    left: Sequence[float],
    right: Sequence[float],
) -> tuple[float, float, float]:
    return tuple(
        left[index] - right[index] for index in range(3)
    )  # type: ignore[return-value]


def _normalize(
    vector: Sequence[float],
    *,
    label: str,
) -> tuple[float, float, float]:
    if len(vector) != 3 or any(not math.isfinite(float(value)) for value in vector):
        raise PregraspPoseError(f"{label} must contain three finite values")
    norm = math.sqrt(sum(float(value) ** 2 for value in vector))
    if norm < 1e-9:
        raise PregraspPoseError(f"{label} must have non-zero length")
    return tuple(float(value) / norm for value in vector)  # type: ignore[return-value]


def derive_grasp_frame(
    *,
    wrist_position_world_m: Sequence[float],
    left_tip_position_world_m: Sequence[float],
    right_tip_position_world_m: Sequence[float],
    config: GraspFrameConfig,
) -> DerivedGraspFrame:
    wrist = _normalize_position(wrist_position_world_m, "wrist_position_world_m")
    left = _normalize_position(left_tip_position_world_m, "left_tip_position_world_m")
    right = _normalize_position(right_tip_position_world_m, "right_tip_position_world_m")
    origin = tuple(
        (left[index] + right[index]) / 2.0 for index in range(3)
    )
    closing_raw = _subtract(right, left)
    separation = math.sqrt(_dot(closing_raw, closing_raw))
    if (
        separation < config.minimum_finger_separation_m
        or separation > config.maximum_finger_separation_m
    ):
        raise PregraspPoseError("terminal finger separation is outside configured bounds")
    closing = _normalize(closing_raw, label="closing axis")
    approach_raw = _subtract(origin, wrist)
    approach_raw = tuple(
        approach_raw[index] - _dot(approach_raw, closing) * closing[index]
        for index in range(3)
    )
    approach_raw_norm = math.sqrt(_dot(approach_raw, approach_raw))
    wrist_to_origin = _subtract(origin, wrist)
    wrist_to_origin_norm = math.sqrt(_dot(wrist_to_origin, wrist_to_origin))
    if wrist_to_origin_norm < 1e-9:
        raise PregraspPoseError("wrist and grasp origin must be distinct")
    axis_cross_norm = approach_raw_norm / wrist_to_origin_norm
    if axis_cross_norm < config.minimum_axis_cross_norm:
        raise PregraspPoseError("grasp approach and closing axes are nearly collinear")
    approach = _normalize(approach_raw, label="approach axis")
    lateral = _normalize(_cross(approach, closing), label="lateral axis")
    approach = _normalize(_cross(closing, lateral), label="orthogonal approach axis")
    return DerivedGraspFrame(
        origin_world_m=origin,  # type: ignore[arg-type]
        approach_axis_world_unit=approach,
        closing_axis_world_unit=closing,
        lateral_axis_world_unit=lateral,
        finger_separation_m=separation,
    )


def _normalize_position(
    values: Sequence[float],
    label: str,
) -> tuple[float, float, float]:
    if len(values) != 3:
        raise PregraspPoseError(f"{label} must contain three values")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise PregraspPoseError(f"{label} must contain finite values")
    return result  # type: ignore[return-value]


def direction_error_vector(
    current: Sequence[float],
    target: Sequence[float],
) -> tuple[float, float, float]:
    current_unit = _normalize(current, label="current direction")
    target_unit = _normalize(target, label="target direction")
    cosine = max(-1.0, min(1.0, _dot(current_unit, target_unit)))
    angle = math.acos(cosine)
    if angle < 1e-10:
        return (0.0, 0.0, 0.0)
    axis = _cross(current_unit, target_unit)
    axis_norm = math.sqrt(_dot(axis, axis))
    if axis_norm < 1e-10:
        basis = min(
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            key=lambda candidate: abs(_dot(current_unit, candidate)),
        )
        axis = _normalize(_cross(current_unit, basis), label="opposite direction axis")
    else:
        axis = tuple(value / axis_norm for value in axis)
    return tuple(angle * value for value in axis)  # type: ignore[return-value]


def direction_error_deg(current: Sequence[float], target: Sequence[float]) -> float:
    current_unit = _normalize(current, label="current direction")
    target_unit = _normalize(target, label="target direction")
    cosine = max(-1.0, min(1.0, _dot(current_unit, target_unit)))
    return math.degrees(math.acos(cosine))


def _inverse(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    size = len(matrix)
    if size == 0 or any(len(row) != size for row in matrix):
        raise PregraspPoseError("matrix must be non-empty and square")
    augmented = [
        [float(value) for value in row]
        + [1.0 if row_index == column else 0.0 for column in range(size)]
        for row_index, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot_row = max(
            range(column, size),
            key=lambda row: abs(augmented[row][column]),
        )
        if abs(augmented[pivot_row][column]) < 1e-12:
            raise PregraspPoseError("pose IK normal matrix is singular")
        augmented[column], augmented[pivot_row] = (
            augmented[pivot_row],
            augmented[column],
        )
        pivot = augmented[column][column]
        augmented[column] = [value / pivot for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(
                    augmented[row],
                    augmented[column],
                    strict=True,
                )
            ]
    return [row[size:] for row in augmented]


def weighted_pose_delta(
    *,
    pose_jacobian: Sequence[Sequence[float]],
    position_error_m: Sequence[float],
    approach_error_rad: Sequence[float],
    current_angles_deg: Sequence[float],
    solver: PoseSolverConfig,
) -> tuple[float, float, float, float]:
    if len(pose_jacobian) != 6 or any(len(row) != 4 for row in pose_jacobian):
        raise PregraspPoseError("pose_jacobian must have shape 6x4")
    position = _normalize_position(position_error_m, "position_error_m")
    approach = _normalize_position(approach_error_rad, "approach_error_rad")
    if len(current_angles_deg) != 4:
        raise PregraspPoseError("current_angles_deg must contain four values")
    current = tuple(
        _number(value, f"current_angles_deg[{index}]")
        for index, value in enumerate(current_angles_deg)
    )
    values = [value for row in pose_jacobian for value in row]
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in values
    ):
        raise PregraspPoseError("pose_jacobian must contain finite numeric values")
    scale = solver.orientation_length_scale_m
    weighted_jacobian = [
        [float(value) for value in row]
        if row_index < 3
        else [scale * float(value) for value in row]
        for row_index, row in enumerate(pose_jacobian)
    ]
    weighted_error = [
        solver.translation_gain * value for value in position
    ] + [
        scale * solver.orientation_gain * value for value in approach
    ]
    normal = [
        [
            sum(
                weighted_jacobian[row][joint] * weighted_jacobian[row][column]
                for row in range(6)
            )
            + (
                solver.damping**2 + solver.posture_weight
                if joint == column
                else 0.0
            )
            for column in range(4)
        ]
        for joint in range(4)
    ]
    right_hand = [
        sum(
            weighted_jacobian[row][joint] * weighted_error[row]
            for row in range(6)
        )
        + solver.posture_weight
        * solver.posture_gain
        * math.radians(solver.preferred_angles_deg[joint] - current[joint])
        for joint in range(4)
    ]
    inverse = _inverse(normal)
    delta = tuple(
        sum(inverse[row][column] * right_hand[column] for column in range(4))
        for row in range(4)
    )
    if not all(math.isfinite(value) for value in delta):
        raise PregraspPoseError("pose IK produced non-finite joint deltas")
    return delta  # type: ignore[return-value]


def next_pose_command(
    *,
    frame: DerivedGraspFrame,
    pose_jacobian: Sequence[Sequence[float]],
    current_angles_deg: Sequence[float],
    previous_velocities_deg_s: Sequence[float],
    solver: PoseSolverConfig,
    target: TargetPoseConfig,
) -> PoseCommand:
    if len(current_angles_deg) != 4 or len(previous_velocities_deg_s) != 4:
        raise PregraspPoseError("joint angle and velocity vectors must contain four values")
    current = tuple(
        _number(value, f"current_angles_deg[{index}]")
        for index, value in enumerate(current_angles_deg)
    )
    previous_velocity = tuple(
        _number(value, f"previous_velocities_deg_s[{index}]")
        for index, value in enumerate(previous_velocities_deg_s)
    )
    if any(
        angle < solver.safe_angle_min_deg or angle > solver.safe_angle_max_deg
        for angle in current
    ):
        raise PregraspPoseError("current joint angles are outside the safe envelope")
    position_error = _subtract(target.position_world_m, frame.origin_world_m)
    approach_error = direction_error_vector(
        frame.approach_axis_world_unit,
        target.approach_axis_world_unit,
    )
    raw_delta_rad = weighted_pose_delta(
        pose_jacobian=pose_jacobian,
        position_error_m=position_error,
        approach_error_rad=approach_error,
        current_angles_deg=current,
        solver=solver,
    )
    raw_delta_deg = tuple(math.degrees(value) for value in raw_delta_rad)
    maximum = max(abs(value) for value in raw_delta_deg)
    if maximum > solver.maximum_joint_delta_deg:
        factor = solver.maximum_joint_delta_deg / maximum
        raw_delta_deg = tuple(value * factor for value in raw_delta_deg)
    proposed = tuple(
        angle + delta for angle, delta in zip(current, raw_delta_deg, strict=True)
    )
    command_min = solver.safe_angle_min_deg + solver.command_limit_margin_deg
    command_max = solver.safe_angle_max_deg - solver.command_limit_margin_deg
    proposed = tuple(max(command_min, min(command_max, value)) for value in proposed)
    dt = solver.control_dt_s
    maximum_velocity = solver.maximum_joint_velocity_deg_s
    maximum_acceleration_step = solver.maximum_joint_acceleration_deg_s2 * dt
    velocities: list[float] = []
    commands: list[float] = []
    for index, (angle, target_angle, prior_velocity) in enumerate(
        zip(current, proposed, previous_velocity, strict=True)
    ):
        desired_velocity = max(
            -maximum_velocity,
            min(maximum_velocity, (target_angle - angle) / dt),
        )
        velocity = max(
            prior_velocity - maximum_acceleration_step,
            min(prior_velocity + maximum_acceleration_step, desired_velocity),
        )
        velocity = max(-maximum_velocity, min(maximum_velocity, velocity))
        command = max(command_min, min(command_max, angle + velocity * dt))
        if abs(command - angle) > solver.maximum_joint_delta_deg + 1e-9:
            raise PregraspPoseError(f"joint {index} command exceeds maximum delta")
        velocities.append(velocity)
        commands.append(command)
    return PoseCommand(
        angles_deg=tuple(commands),  # type: ignore[arg-type]
        velocities_deg_s=tuple(velocities),  # type: ignore[arg-type]
        raw_delta_deg=raw_delta_deg,  # type: ignore[arg-type]
        position_error_m=position_error,
        approach_error_rad=approach_error,
    )


def quantize_pose_command(
    command: PoseCommand,
    *,
    current_angles_deg: Sequence[float],
    previous_velocities_deg_s: Sequence[float],
    solver: PoseSolverConfig,
) -> PoseCommand:
    """Quantize to Yahboom integer degrees without violating motion limits."""

    if len(current_angles_deg) != 4 or len(previous_velocities_deg_s) != 4:
        raise PregraspPoseError("joint angle and velocity vectors must contain four values")
    current = tuple(
        _number(value, f"current_angles_deg[{index}]")
        for index, value in enumerate(current_angles_deg)
    )
    previous_velocity = tuple(
        _number(value, f"previous_velocities_deg_s[{index}]")
        for index, value in enumerate(previous_velocities_deg_s)
    )
    minimum = math.ceil(
        solver.safe_angle_min_deg + solver.command_limit_margin_deg
    )
    maximum = math.floor(
        solver.safe_angle_max_deg - solver.command_limit_margin_deg
    )
    dt = solver.control_dt_s
    angles: list[float] = []
    velocities: list[float] = []
    for index, desired in enumerate(command.angles_deg):
        candidates: list[tuple[float, int, float]] = []
        for candidate in range(minimum, maximum + 1):
            delta = candidate - current[index]
            velocity = delta / dt
            acceleration = (velocity - previous_velocity[index]) / dt
            if (
                abs(delta) <= solver.maximum_joint_delta_deg + 1e-9
                and abs(velocity)
                <= solver.maximum_joint_velocity_deg_s + 1e-9
                and abs(acceleration)
                <= solver.maximum_joint_acceleration_deg_s2 + 1e-9
            ):
                candidates.append((abs(candidate - desired), candidate, velocity))
        if not candidates:
            raise PregraspPoseError(
                f"joint {index} has no safe integer-degree command"
            )
        _, angle, velocity = min(candidates)
        angles.append(float(angle))
        velocities.append(velocity)
    return PoseCommand(
        angles_deg=tuple(angles),  # type: ignore[arg-type]
        velocities_deg_s=tuple(velocities),  # type: ignore[arg-type]
        raw_delta_deg=command.raw_delta_deg,
        position_error_m=command.position_error_m,
        approach_error_rad=command.approach_error_rad,
    )


def signed_point_box_distance(
    point: Sequence[float],
    center: Sequence[float],
    size: Sequence[float],
) -> float:
    position = _normalize_position(point, "point")
    box_center = _normalize_position(center, "box center")
    box_size = _normalize_position(size, "box size")
    if any(value <= 0.0 for value in box_size):
        raise PregraspPoseError("box size must be positive")
    q = [
        abs(position[index] - box_center[index]) - box_size[index] / 2.0
        for index in range(3)
    ]
    outside = math.sqrt(sum(max(value, 0.0) ** 2 for value in q))
    inside = min(max(q), 0.0)
    return outside + inside


def evaluate_pregrasp_observation(
    *,
    config: PregraspPoseConfig,
    frame: DerivedGraspFrame,
    body_positions_world_m: Mapping[str, Sequence[float]],
    table_center_world_m: Sequence[float],
    table_size_m: Sequence[float],
    target_center_world_m: Sequence[float],
    target_size_m: Sequence[float],
    target_is_static: bool,
    angles_deg: Sequence[float],
    velocities_deg_s: Sequence[float],
    accelerations_deg_s2: Sequence[float],
    maximum_contact_force_n: float,
) -> dict[str, Any]:
    missing = set(config.collision.critical_body_names) - set(body_positions_world_m)
    if missing:
        raise PregraspPoseError(f"missing critical body positions: {sorted(missing)}")
    if len(angles_deg) != 4 or len(velocities_deg_s) != 4 or len(accelerations_deg_s2) != 4:
        raise PregraspPoseError("joint observation vectors must contain four values")
    angles = tuple(_number(value, "angles_deg") for value in angles_deg)
    velocities = tuple(_number(value, "velocities_deg_s") for value in velocities_deg_s)
    accelerations = tuple(
        _number(value, "accelerations_deg_s2") for value in accelerations_deg_s2
    )
    contact_force = _number(maximum_contact_force_n, "maximum_contact_force_n")
    if contact_force < 0.0:
        raise PregraspPoseError("maximum_contact_force_n must be nonnegative")
    table_distances = {
        name: signed_point_box_distance(
            body_positions_world_m[name],
            table_center_world_m,
            table_size_m,
        )
        for name in config.collision.critical_body_names
    }
    target_distances = {
        name: signed_point_box_distance(
            body_positions_world_m[name],
            target_center_world_m,
            target_size_m,
        )
        for name in config.collision.critical_body_names
    }
    terminal_names = {
        config.grasp_frame.left_tip_body_name,
        config.grasp_frame.right_tip_body_name,
    }
    terminal_distance = min(target_distances[name] for name in terminal_names)
    nonterminal_distance = min(
        distance
        for name, distance in target_distances.items()
        if name not in terminal_names
    )
    position_error = math.dist(
        frame.origin_world_m,
        config.target_pose.position_world_m,
    )
    approach_error = direction_error_deg(
        frame.approach_axis_world_unit,
        config.target_pose.approach_axis_world_unit,
    )
    closing_error = direction_error_deg(
        frame.closing_axis_world_unit,
        config.target_pose.closing_axis_world_unit,
    )
    command_min = (
        config.solver.safe_angle_min_deg + config.solver.command_limit_margin_deg
    )
    command_max = (
        config.solver.safe_angle_max_deg - config.solver.command_limit_margin_deg
    )
    checks = {
        "grasp_origin_reached_pregrasp_position": (
            position_error <= config.target_pose.position_tolerance_m
        ),
        "approach_axis_points_down_within_tolerance": (
            approach_error <= config.target_pose.approach_tolerance_deg
        ),
        "fixed_closing_axis_is_acceptable_without_wrist_command": (
            closing_error <= config.target_pose.closing_tolerance_deg
        ),
        "joint_angles_preserve_command_limit_margin": all(
            command_min <= value <= command_max for value in angles
        ),
        "joint_velocity_limit_respected": all(
            abs(value) <= config.solver.maximum_joint_velocity_deg_s + 1e-9
            for value in velocities
        ),
        "joint_acceleration_limit_respected": all(
            abs(value) <= config.solver.maximum_joint_acceleration_deg_s2 + 1e-9
            for value in accelerations
        ),
        "critical_body_centers_clear_table_proxy": (
            min(table_distances.values())
            >= config.collision.minimum_body_center_table_distance_m
        ),
        "nonfinger_body_centers_clear_target_proxy": (
            nonterminal_distance
            >= config.collision.minimum_nonfinger_body_center_target_distance_m
        ),
        "terminal_finger_centers_remain_precontact": (
            terminal_distance
            >= config.collision.minimum_terminal_finger_target_distance_m
        ),
        "contact_reporter_force_remains_below_threshold": (
            contact_force <= config.collision.maximum_contact_force_n
        ),
        "target_remains_static": (
            target_is_static is True and config.collision.require_static_target
        ),
        "contact_remains_unauthorized": (
            config.collision.contact_authorized is False
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "position_error_m": position_error,
        "approach_error_deg": approach_error,
        "closing_error_deg": closing_error,
        "minimum_body_center_table_distance_m": min(table_distances.values()),
        "minimum_nonfinger_body_center_target_distance_m": nonterminal_distance,
        "minimum_terminal_finger_target_distance_m": terminal_distance,
        "maximum_contact_force_n": contact_force,
        "body_center_table_distances_m": table_distances,
        "body_center_target_distances_m": target_distances,
    }
