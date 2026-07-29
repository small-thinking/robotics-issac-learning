"""Pure contracts and controller math for fixed-target DOFBOT reaching.

Goal 4 deliberately stops at approach/retract. The target cube is static on a
physical tabletop, the controlled end-effector anchor is ``Wrist_Twist``, and
neither the wrist-twist joint nor the gripper is commanded. Isaac supplies the
live translational Jacobian; this module owns strict parsing, damped-least-
squares math, Yahboom-shaped angle boundaries, and machine-result evaluation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .dofbot_motion_config import (
        MotionConfig,
        compile_motion_config,
        parse_motion_config,
    )
except ImportError:
    from dofbot_motion_config import (
        MotionConfig,
        compile_motion_config,
        parse_motion_config,
    )

SCHEMA_VERSION = 1
CONTROLLED_JOINT_COUNT = 4
EXPECTED_END_EFFECTOR_BODY = "Wrist_Twist"
MAX_STATE_CONTROLLER_STEPS = 100
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ReachingConfigError(ValueError):
    """Raised when a reaching config, controller input, or result is unsafe."""


@dataclass(frozen=True)
class BoxGeometry:
    prim_path: str
    center_world_m: tuple[float, float, float]
    size_m: tuple[float, float, float]
    color_rgb: tuple[float, float, float]
    collision_enabled: bool

    @property
    def top_z_m(self) -> float:
        return self.center_world_m[2] + self.size_m[2] / 2.0

    @property
    def bottom_z_m(self) -> float:
        return self.center_world_m[2] - self.size_m[2] / 2.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "prim_path": self.prim_path,
            "center_world_m": list(self.center_world_m),
            "size_m": list(self.size_m),
            "color_rgb": list(self.color_rgb),
            "collision_enabled": self.collision_enabled,
        }


@dataclass(frozen=True)
class TargetCube(BoxGeometry):
    static: bool

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "static": self.static}


@dataclass(frozen=True)
class StateControllerConfig:
    control_hz: int
    maximum_steps: int
    command_duration_ms: int
    damping: float
    position_gain: float
    maximum_joint_delta_deg: float
    safe_angle_min_deg: int
    safe_angle_max_deg: int
    success_distance_m: float
    minimum_improvement_m: float
    minimum_wrist_table_clearance_m: float
    maximum_neutral_reset_error_deg: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_hz": self.control_hz,
            "maximum_steps": self.maximum_steps,
            "command_duration_ms": self.command_duration_ms,
            "damping": self.damping,
            "position_gain": self.position_gain,
            "maximum_joint_delta_deg": self.maximum_joint_delta_deg,
            "safe_angle_min_deg": self.safe_angle_min_deg,
            "safe_angle_max_deg": self.safe_angle_max_deg,
            "success_distance_m": self.success_distance_m,
            "minimum_improvement_m": self.minimum_improvement_m,
            "minimum_wrist_table_clearance_m": (self.minimum_wrist_table_clearance_m),
            "maximum_neutral_reset_error_deg": (self.maximum_neutral_reset_error_deg),
        }


@dataclass(frozen=True)
class DofbotReachingConfig:
    name: str
    table: BoxGeometry
    target_cube: TargetCube
    robot_base_keepout_radius_m: float
    end_effector_body_name: str
    approach_offset_from_cube_center_m: tuple[float, float, float]
    scripted_baseline: MotionConfig
    state_controller: StateControllerConfig
    viewer_connection_hold_seconds: int
    viewer_success_hold_seconds: int

    @property
    def approach_target_world_m(self) -> tuple[float, float, float]:
        return tuple(
            center + offset
            for center, offset in zip(
                self.target_cube.center_world_m,
                self.approach_offset_from_cube_center_m,
                strict=True,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "scene": {
                "table": self.table.to_dict(),
                "target_cube": self.target_cube.to_dict(),
                "robot_base_keepout_radius_m": (self.robot_base_keepout_radius_m),
            },
            "end_effector": {
                "body_name": self.end_effector_body_name,
                "approach_offset_from_cube_center_m": list(self.approach_offset_from_cube_center_m),
                "approach_target_world_m": list(self.approach_target_world_m),
            },
            "scripted_baseline": self.scripted_baseline.to_dict(),
            "state_controller": self.state_controller.to_dict(),
            "viewer": {
                "connection_hold_seconds": self.viewer_connection_hold_seconds,
                "success_hold_seconds": self.viewer_success_hold_seconds,
            },
        }


def _strict_object(
    value: Any,
    keys: set[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ReachingConfigError(f"{label} keys must match {sorted(keys)}; got {actual}")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReachingConfigError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ReachingConfigError(f"{label} must be finite")
    return result


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReachingConfigError(f"{label} must be an integer")
    return value


def _vector3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ReachingConfigError(f"{label} must contain exactly three values")
    return tuple(_number(item, f"{label}[{index}]") for index, item in enumerate(value))


def _color3(value: Any, label: str) -> tuple[float, float, float]:
    color = _vector3(value, label)
    if any(component < 0.0 or component > 1.0 for component in color):
        raise ReachingConfigError(f"{label} values must be in [0, 1]")
    return color


def _prim_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("/World/") or ".." in value:
        raise ReachingConfigError(f"{label} must be an absolute /World prim path")
    return value


def _box(value: Any, label: str, *, target: bool) -> BoxGeometry | TargetCube:
    keys = {
        "prim_path",
        "center_world_m",
        "size_m",
        "color_rgb",
        "collision_enabled",
    }
    if target:
        keys.add("static")
    raw = _strict_object(value, keys, label)
    center = _vector3(raw["center_world_m"], f"{label}.center_world_m")
    size = _vector3(raw["size_m"], f"{label}.size_m")
    if any(component <= 0.0 or component > 1.0 for component in size):
        raise ReachingConfigError(f"{label}.size_m must be in (0, 1]")
    if raw["collision_enabled"] is not True:
        raise ReachingConfigError(f"{label}.collision_enabled must be true")
    common = {
        "prim_path": _prim_path(raw["prim_path"], f"{label}.prim_path"),
        "center_world_m": center,
        "size_m": size,
        "color_rgb": _color3(raw["color_rgb"], f"{label}.color_rgb"),
        "collision_enabled": True,
    }
    if target:
        if raw["static"] is not True:
            raise ReachingConfigError(f"{label}.static must be true")
        return TargetCube(**common, static=True)
    return BoxGeometry(**common)


def _state_controller(value: Any) -> StateControllerConfig:
    keys = {
        "control_hz",
        "maximum_steps",
        "command_duration_ms",
        "damping",
        "position_gain",
        "maximum_joint_delta_deg",
        "safe_angle_min_deg",
        "safe_angle_max_deg",
        "success_distance_m",
        "minimum_improvement_m",
        "minimum_wrist_table_clearance_m",
        "maximum_neutral_reset_error_deg",
    }
    raw = _strict_object(value, keys, "state_controller")
    control_hz = _integer(raw["control_hz"], "state_controller.control_hz")
    maximum_steps = _integer(raw["maximum_steps"], "state_controller.maximum_steps")
    command_duration_ms = _integer(
        raw["command_duration_ms"],
        "state_controller.command_duration_ms",
    )
    if control_hz < 1 or control_hz > 10:
        raise ReachingConfigError("state_controller.control_hz must be in [1, 10]")
    if maximum_steps < 1 or maximum_steps > MAX_STATE_CONTROLLER_STEPS:
        raise ReachingConfigError(
            f"state_controller.maximum_steps must be in [1, {MAX_STATE_CONTROLLER_STEPS}]"
        )
    if command_duration_ms != round(1000 / control_hz):
        raise ReachingConfigError(
            "state_controller.command_duration_ms must equal one control interval"
        )
    damping = _number(raw["damping"], "state_controller.damping")
    gain = _number(raw["position_gain"], "state_controller.position_gain")
    max_delta = _number(
        raw["maximum_joint_delta_deg"],
        "state_controller.maximum_joint_delta_deg",
    )
    safe_min = _integer(raw["safe_angle_min_deg"], "state_controller.safe_angle_min_deg")
    safe_max = _integer(raw["safe_angle_max_deg"], "state_controller.safe_angle_max_deg")
    success = _number(raw["success_distance_m"], "state_controller.success_distance_m")
    improvement = _number(
        raw["minimum_improvement_m"],
        "state_controller.minimum_improvement_m",
    )
    clearance = _number(
        raw["minimum_wrist_table_clearance_m"],
        "state_controller.minimum_wrist_table_clearance_m",
    )
    reset = _number(
        raw["maximum_neutral_reset_error_deg"],
        "state_controller.maximum_neutral_reset_error_deg",
    )
    if not 0.001 <= damping <= 1.0:
        raise ReachingConfigError("state_controller.damping must be in [0.001, 1]")
    if not 0.05 <= gain <= 1.0:
        raise ReachingConfigError("state_controller.position_gain must be in [0.05, 1]")
    if not 0.5 <= max_delta <= 5.0:
        raise ReachingConfigError("state_controller.maximum_joint_delta_deg must be in [0.5, 5]")
    if (safe_min, safe_max) != (60, 120):
        raise ReachingConfigError("state_controller safe envelope must remain [60, 120] degrees")
    if not 0.01 <= success <= 0.08:
        raise ReachingConfigError("state_controller.success_distance_m must be in [0.01, 0.08]")
    if not 0.01 <= improvement <= 0.20:
        raise ReachingConfigError("state_controller.minimum_improvement_m must be in [0.01, 0.20]")
    if not 0.02 <= clearance <= 0.15:
        raise ReachingConfigError(
            "state_controller.minimum_wrist_table_clearance_m must be in [0.02, 0.15]"
        )
    if not 0.1 <= reset <= 2.0:
        raise ReachingConfigError(
            "state_controller.maximum_neutral_reset_error_deg must be in [0.1, 2]"
        )
    return StateControllerConfig(
        control_hz=control_hz,
        maximum_steps=maximum_steps,
        command_duration_ms=command_duration_ms,
        damping=damping,
        position_gain=gain,
        maximum_joint_delta_deg=max_delta,
        safe_angle_min_deg=safe_min,
        safe_angle_max_deg=safe_max,
        success_distance_m=success,
        minimum_improvement_m=improvement,
        minimum_wrist_table_clearance_m=clearance,
        maximum_neutral_reset_error_deg=reset,
    )


def parse_reaching_config(value: Any) -> DofbotReachingConfig:
    raw = _strict_object(
        value,
        {
            "schema_version",
            "name",
            "scene",
            "end_effector",
            "scripted_baseline",
            "state_controller",
            "viewer",
        },
        "root",
    )
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(raw["schema_version"], bool):
        raise ReachingConfigError(f"schema_version must equal {SCHEMA_VERSION}")
    if not isinstance(raw["name"], str) or _NAME_PATTERN.fullmatch(raw["name"]) is None:
        raise ReachingConfigError("name must be lowercase snake_case")

    scene = _strict_object(
        raw["scene"],
        {"table", "target_cube", "robot_base_keepout_radius_m"},
        "scene",
    )
    table = _box(scene["table"], "scene.table", target=False)
    target = _box(scene["target_cube"], "scene.target_cube", target=True)
    assert isinstance(table, BoxGeometry)
    assert isinstance(target, TargetCube)
    if table.prim_path == target.prim_path:
        raise ReachingConfigError("table and target cube prim paths must differ")
    keepout = _number(
        scene["robot_base_keepout_radius_m"],
        "scene.robot_base_keepout_radius_m",
    )
    if not 0.05 <= keepout <= 0.20:
        raise ReachingConfigError("scene.robot_base_keepout_radius_m must be in [0.05, 0.20]")
    if not math.isclose(target.bottom_z_m, table.top_z_m, abs_tol=1e-6):
        raise ReachingConfigError("target cube bottom must rest exactly on table top")
    for axis in (0, 1):
        table_half = table.size_m[axis] / 2.0
        cube_half = target.size_m[axis] / 2.0
        if abs(target.center_world_m[axis] - table.center_world_m[axis]) + cube_half > table_half:
            raise ReachingConfigError("target cube footprint must stay on table")
    table_near_edge_y = table.center_world_m[1] + table.size_m[1] / 2.0
    if table_near_edge_y > -keepout:
        raise ReachingConfigError("table must remain outside robot base keepout")

    end_effector = _strict_object(
        raw["end_effector"],
        {"body_name", "approach_offset_from_cube_center_m"},
        "end_effector",
    )
    if end_effector["body_name"] != EXPECTED_END_EFFECTOR_BODY:
        raise ReachingConfigError(f"end_effector.body_name must be {EXPECTED_END_EFFECTOR_BODY}")
    approach_offset = _vector3(
        end_effector["approach_offset_from_cube_center_m"],
        "end_effector.approach_offset_from_cube_center_m",
    )
    if (
        abs(approach_offset[0]) > 0.05
        or abs(approach_offset[1]) > 0.05
        or approach_offset[2] < target.size_m[2] / 2.0 + 0.04
        or approach_offset[2] > 0.20
    ):
        raise ReachingConfigError(
            "end-effector approach must remain centered and safely above the cube"
        )

    scripted_baseline = parse_motion_config(raw["scripted_baseline"])
    if not scripted_baseline.name.startswith("goal4_"):
        raise ReachingConfigError("scripted baseline name must start with goal4_")

    controller = _state_controller(raw["state_controller"])
    approach_target_z = target.center_world_m[2] + approach_offset[2]
    if approach_target_z - table.top_z_m < controller.minimum_wrist_table_clearance_m:
        raise ReachingConfigError("approach target violates minimum wrist-table clearance")

    viewer = _strict_object(
        raw["viewer"],
        {"connection_hold_seconds", "success_hold_seconds"},
        "viewer",
    )
    connection_hold = _integer(viewer["connection_hold_seconds"], "viewer.connection_hold_seconds")
    success_hold = _integer(viewer["success_hold_seconds"], "viewer.success_hold_seconds")
    if connection_hold < 0 or connection_hold > 60:
        raise ReachingConfigError("viewer.connection_hold_seconds must be in [0, 60]")
    if success_hold < 0 or success_hold > 10:
        raise ReachingConfigError("viewer.success_hold_seconds must be in [0, 10]")

    return DofbotReachingConfig(
        name=raw["name"],
        table=table,
        target_cube=target,
        robot_base_keepout_radius_m=keepout,
        end_effector_body_name=end_effector["body_name"],
        approach_offset_from_cube_center_m=approach_offset,
        scripted_baseline=scripted_baseline,
        state_controller=controller,
        viewer_connection_hold_seconds=connection_hold,
        viewer_success_hold_seconds=success_hold,
    )


def load_reaching_config(path: Path) -> tuple[DofbotReachingConfig, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReachingConfigError(f"{path} is not valid JSON: {error}") from error
    return parse_reaching_config(value), hashlib.sha256(raw).hexdigest()


def _matrix3_inverse(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    augmented = [
        [float(matrix[row][column]) for column in range(3)]
        + [1.0 if row == column else 0.0 for column in range(3)]
        for row in range(3)
    ]
    for column in range(3):
        pivot_row = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        pivot = augmented[pivot_row][column]
        if abs(pivot) < 1e-12:
            raise ReachingConfigError("damped Jacobian system is singular")
        augmented[column], augmented[pivot_row] = (
            augmented[pivot_row],
            augmented[column],
        )
        pivot = augmented[column][column]
        augmented[column] = [value / pivot for value in augmented[column]]
        for row in range(3):
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
    return [row[3:] for row in augmented]


def damped_least_squares_delta(
    jacobian: Sequence[Sequence[float]],
    position_error_m: Sequence[float],
    *,
    damping: float,
) -> tuple[float, float, float, float]:
    """Return four joint deltas in radians for a 3x4 translation Jacobian."""

    if len(jacobian) != 3 or any(len(row) != CONTROLLED_JOINT_COUNT for row in jacobian):
        raise ReachingConfigError("translation Jacobian must have shape 3x4")
    if len(position_error_m) != 3:
        raise ReachingConfigError("position error must have three values")
    values = [
        *[component for row in jacobian for component in row],
        *position_error_m,
        damping,
    ]
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in values
    ):
        raise ReachingConfigError("Jacobian controller inputs must be finite numbers")
    if damping <= 0.0:
        raise ReachingConfigError("damping must be positive")

    j = [[float(value) for value in row] for row in jacobian]
    error = [float(value) for value in position_error_m]
    normal = [
        [
            sum(j[row][joint] * j[column][joint] for joint in range(4))
            + (damping * damping if row == column else 0.0)
            for column in range(3)
        ]
        for row in range(3)
    ]
    inverse = _matrix3_inverse(normal)
    solved = [sum(inverse[row][column] * error[column] for column in range(3)) for row in range(3)]
    return tuple(sum(j[row][joint] * solved[row] for row in range(3)) for joint in range(4))


def next_state_controller_angles(
    *,
    current_angles_deg: Sequence[float],
    translation_jacobian: Sequence[Sequence[float]],
    position_error_m: Sequence[float],
    controller: StateControllerConfig,
) -> tuple[int, int, int, int]:
    """Compute one bounded absolute Yahboom-angle command."""

    if len(current_angles_deg) != CONTROLLED_JOINT_COUNT:
        raise ReachingConfigError("current_angles_deg must have four values")
    current = [
        _number(value, f"current_angles_deg[{index}]")
        for index, value in enumerate(current_angles_deg)
    ]
    if any(
        value < controller.safe_angle_min_deg or value > controller.safe_angle_max_deg
        for value in current
    ):
        raise ReachingConfigError("current angles are outside safe envelope")

    raw_delta = damped_least_squares_delta(
        translation_jacobian,
        position_error_m,
        damping=controller.damping,
    )
    scaled_delta_deg = [math.degrees(value) * controller.position_gain for value in raw_delta]
    maximum = max(abs(value) for value in scaled_delta_deg)
    if maximum > controller.maximum_joint_delta_deg:
        scale = controller.maximum_joint_delta_deg / maximum
        scaled_delta_deg = [value * scale for value in scaled_delta_deg]
    target = tuple(
        int(round(angle + delta)) for angle, delta in zip(current, scaled_delta_deg, strict=True)
    )
    if any(
        value < controller.safe_angle_min_deg or value > controller.safe_angle_max_deg
        for value in target
    ):
        raise ReachingConfigError("state controller proposed an angle outside safe envelope")
    return target


def _validated_observation(
    observation: Any,
    *,
    index: int,
) -> dict[str, Any]:
    raw = _strict_object(
        observation,
        {
            "step_index",
            "wrist_position_world_m",
            "target_position_world_m",
            "distance_m",
            "angles_deg",
            "wrist_table_clearance_m",
        },
        f"observations[{index}]",
    )
    if _integer(raw["step_index"], f"observations[{index}].step_index") != index:
        raise ReachingConfigError("observation step indexes must be contiguous")
    wrist = _vector3(
        raw["wrist_position_world_m"],
        f"observations[{index}].wrist_position_world_m",
    )
    target = _vector3(
        raw["target_position_world_m"],
        f"observations[{index}].target_position_world_m",
    )
    distance = _number(raw["distance_m"], f"observations[{index}].distance_m")
    clearance = _number(
        raw["wrist_table_clearance_m"],
        f"observations[{index}].wrist_table_clearance_m",
    )
    if distance < 0.0 or not math.isclose(
        distance,
        math.dist(wrist, target),
        rel_tol=1e-5,
        abs_tol=1e-6,
    ):
        raise ReachingConfigError("observation distance does not match positions")
    angles_raw = raw["angles_deg"]
    if not isinstance(angles_raw, list) or len(angles_raw) != 4:
        raise ReachingConfigError("observation angles_deg must have four values")
    angles = [_number(value, f"observations[{index}].angles_deg") for value in angles_raw]
    return {
        "step_index": index,
        "wrist_position_world_m": wrist,
        "target_position_world_m": target,
        "distance_m": distance,
        "angles_deg": angles,
        "wrist_table_clearance_m": clearance,
    }


def evaluate_reaching_observations(
    config: DofbotReachingConfig,
    *,
    end_effector_body_present: bool,
    table_prim_present: bool,
    target_prim_present: bool,
    scripted_observations: Sequence[Any],
    state_observations: Sequence[Any],
    official_api_call_count: int,
    maximum_neutral_reset_error_deg: float,
) -> dict[str, Any]:
    """Evaluate one scripted comparison and one state-based approach."""

    if not scripted_observations or len(state_observations) < 2:
        raise ReachingConfigError(
            "scripted observations and at least two state observations are required"
        )
    scripted = [
        _validated_observation(value, index=index)
        for index, value in enumerate(scripted_observations)
    ]
    state = [
        _validated_observation(value, index=index) for index, value in enumerate(state_observations)
    ]
    expected_target = config.approach_target_world_m
    target_static = all(
        all(
            math.isclose(actual, expected, abs_tol=1e-8)
            for actual, expected in zip(
                observation["target_position_world_m"],
                expected_target,
                strict=True,
            )
        )
        for observation in [*scripted, *state]
    )
    all_observations = [*scripted, *state]
    angles_safe = all(
        config.state_controller.safe_angle_min_deg - 1.0
        <= angle
        <= config.state_controller.safe_angle_max_deg + 1.0
        for observation in all_observations
        for angle in observation["angles_deg"]
    )
    minimum_clearance = min(
        observation["wrist_table_clearance_m"] for observation in all_observations
    )
    initial_distance = state[0]["distance_m"]
    final_distance = state[-1]["distance_m"]
    improvement = initial_distance - final_distance
    scripted_initial_distance = scripted[0]["distance_m"]
    scripted_best_distance = min(observation["distance_m"] for observation in scripted)
    scripted_improvement = scripted_initial_distance - scripted_best_distance
    scripted_api_calls = sum(
        len(sample.api_writes()) for sample in compile_motion_config(config.scripted_baseline)
    )
    expected_api_calls = scripted_api_calls + (len(state) - 1) * 4 + 4
    reset_error = _number(
        maximum_neutral_reset_error_deg,
        "maximum_neutral_reset_error_deg",
    )
    checks = {
        "end_effector_body_present": end_effector_body_present is True,
        "physical_table_prim_present": table_prim_present is True,
        "static_target_cube_prim_present": target_prim_present is True,
        "target_remained_world_fixed": target_static,
        "all_angles_within_safe_envelope": angles_safe,
        "wrist_stayed_above_table_clearance": (
            minimum_clearance >= config.state_controller.minimum_wrist_table_clearance_m
        ),
        "scripted_baseline_improved_distance": (
            scripted_improvement >= config.state_controller.minimum_improvement_m
        ),
        "state_controller_improved_distance": (
            improvement >= config.state_controller.minimum_improvement_m
        ),
        "state_controller_reached_approach_waypoint": (
            final_distance <= config.state_controller.success_distance_m
        ),
        "official_api_call_count_matches": (
            isinstance(official_api_call_count, int)
            and not isinstance(official_api_call_count, bool)
            and official_api_call_count == expected_api_calls
        ),
        "returned_to_neutral": (
            reset_error <= config.state_controller.maximum_neutral_reset_error_deg
        ),
    }
    return {
        "checks": checks,
        "machine_passed": all(checks.values()),
        "scripted_initial_distance_m": scripted_initial_distance,
        "scripted_best_distance_m": scripted_best_distance,
        "scripted_improvement_m": scripted_improvement,
        "state_initial_distance_m": initial_distance,
        "state_final_distance_m": final_distance,
        "state_improvement_m": improvement,
        "minimum_wrist_table_clearance_m": minimum_clearance,
        "official_api_call_count": official_api_call_count,
        "expected_official_api_call_count": expected_api_calls,
        "maximum_neutral_reset_error_deg": reset_error,
    }
