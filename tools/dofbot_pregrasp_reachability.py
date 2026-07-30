"""Offline, evidence-calibrated reachability search for DOFBOT pre-grasp poses.

The local Mac does not run Isaac. This module therefore fits a deliberately
small planar model to recorded Isaac observations and keeps the result bounded
by that evidence. It can reject a target before another paid run, but it never
upgrades a local candidate to Isaac or Viewer acceptance.
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
    from .dofbot_pregrasp_pose import _inverse, direction_error_deg
except ImportError:
    from dofbot_pregrasp_pose import _inverse, direction_error_deg

SCHEMA_VERSION = 1
EXPECTED_MODEL_TYPE = "planar_three_pitch_chain"
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ReachabilityError(ValueError):
    """Raised when calibration evidence or a search request is invalid."""


@dataclass(frozen=True)
class CalibrationSource:
    full_machine_artifact_sha256: str
    failure_summary_sha256: str
    machine_git_commit: str
    sample_step_indices: tuple[int, ...]


@dataclass(frozen=True)
class ModelConfig:
    type: str
    base_servo_angle_deg: float
    servo_center_angle_deg: float
    maximum_fit_position_error_m: float
    maximum_fit_approach_error_deg: float


@dataclass(frozen=True)
class SearchConfig:
    physical_angle_min_deg: int
    physical_angle_max_deg: int
    command_angle_min_deg: int
    command_angle_max_deg: int
    grid_step_deg: int
    maximum_ranked_candidates: int
    minimum_workspace_front_y_m: float


@dataclass(frozen=True)
class CalibrationSample:
    step_index: int
    angles_deg: tuple[float, float, float, float]
    origin_world_m: tuple[float, float, float]
    approach_axis_world_unit: tuple[float, float, float]


@dataclass(frozen=True)
class ReachabilityConfig:
    name: str
    source: CalibrationSource
    model: ModelConfig
    search: SearchConfig
    samples: tuple[CalibrationSample, ...]


@dataclass(frozen=True)
class PlanarModel:
    x_offset_m: float
    y_offset_m: float
    z_offset_m: float
    link_lengths_m: tuple[float, float, float]
    approach_x: float
    approach_angle_offset_deg: float
    maximum_position_residual_m: float
    rms_position_residual_m: float
    maximum_approach_residual_deg: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": EXPECTED_MODEL_TYPE,
            "x_offset_m": self.x_offset_m,
            "y_offset_m": self.y_offset_m,
            "z_offset_m": self.z_offset_m,
            "link_lengths_m": list(self.link_lengths_m),
            "approach_x": self.approach_x,
            "approach_angle_offset_deg": self.approach_angle_offset_deg,
            "maximum_position_residual_m": self.maximum_position_residual_m,
            "rms_position_residual_m": self.rms_position_residual_m,
            "maximum_approach_residual_deg": self.maximum_approach_residual_deg,
        }


@dataclass(frozen=True)
class ReachabilityCandidate:
    angles_deg: tuple[int, int, int, int]
    posture_branch: str
    origin_world_m: tuple[float, float, float]
    approach_axis_world_unit: tuple[float, float, float]
    position_error_m: float
    approach_error_deg: float
    minimum_angle_margin_deg: int
    normalized_score: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "angles_deg": list(self.angles_deg),
            "posture_branch": self.posture_branch,
            "origin_world_m": list(self.origin_world_m),
            "approach_axis_world_unit": list(self.approach_axis_world_unit),
            "position_error_m": self.position_error_m,
            "approach_error_deg": self.approach_error_deg,
            "minimum_angle_margin_deg": self.minimum_angle_margin_deg,
            "normalized_score": self.normalized_score,
            "passed": self.passed,
        }


def _strict_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ReachabilityError(
            f"{label} keys must match {sorted(keys)}; got {actual}"
        )
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReachabilityError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ReachabilityError(f"{label} must be finite")
    return result


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReachabilityError(f"{label} must be an integer")
    return value


def _vector(
    value: Any,
    *,
    length: int,
    label: str,
) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise ReachabilityError(f"{label} must contain exactly {length} values")
    return tuple(_number(item, f"{label}[{index}]") for index, item in enumerate(value))


def _sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReachabilityError(f"{label} must be a lowercase SHA-256")
    return value


def _git_commit(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReachabilityError(f"{label} must be a lowercase 40-hex commit")
    return value


def _unit_vector(value: Any, label: str) -> tuple[float, float, float]:
    vector = _vector(value, length=3, label=label)
    norm = math.sqrt(sum(component * component for component in vector))
    if not math.isclose(norm, 1.0, abs_tol=1e-8):
        raise ReachabilityError(f"{label} must be unit length")
    return vector  # type: ignore[return-value]


def parse_reachability_config(value: Any) -> ReachabilityConfig:
    raw = _strict_object(
        value,
        {"schema_version", "name", "source", "model", "search", "samples"},
        "root",
    )
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(
        raw["schema_version"], bool
    ):
        raise ReachabilityError(f"schema_version must equal {SCHEMA_VERSION}")
    name = raw["name"]
    if not isinstance(name, str) or _NAME_PATTERN.fullmatch(name) is None:
        raise ReachabilityError("name must be lowercase snake_case")

    source_raw = _strict_object(
        raw["source"],
        {
            "full_machine_artifact_sha256",
            "failure_summary_sha256",
            "machine_git_commit",
            "sample_step_indices",
        },
        "source",
    )
    indices_raw = source_raw["sample_step_indices"]
    if not isinstance(indices_raw, list) or len(indices_raw) < 8:
        raise ReachabilityError("source.sample_step_indices must contain at least 8 values")
    indices = tuple(
        _integer(value, f"source.sample_step_indices[{index}]")
        for index, value in enumerate(indices_raw)
    )
    if tuple(sorted(set(indices))) != indices:
        raise ReachabilityError("source.sample_step_indices must be sorted and unique")
    source = CalibrationSource(
        full_machine_artifact_sha256=_sha256(
            source_raw["full_machine_artifact_sha256"],
            "source.full_machine_artifact_sha256",
        ),
        failure_summary_sha256=_sha256(
            source_raw["failure_summary_sha256"],
            "source.failure_summary_sha256",
        ),
        machine_git_commit=_git_commit(
            source_raw["machine_git_commit"],
            "source.machine_git_commit",
        ),
        sample_step_indices=indices,
    )

    model_raw = _strict_object(
        raw["model"],
        {
            "type",
            "base_servo_angle_deg",
            "servo_center_angle_deg",
            "maximum_fit_position_error_m",
            "maximum_fit_approach_error_deg",
        },
        "model",
    )
    if model_raw["type"] != EXPECTED_MODEL_TYPE:
        raise ReachabilityError(f"model.type must equal {EXPECTED_MODEL_TYPE}")
    model = ModelConfig(
        type=model_raw["type"],
        base_servo_angle_deg=_number(
            model_raw["base_servo_angle_deg"], "model.base_servo_angle_deg"
        ),
        servo_center_angle_deg=_number(
            model_raw["servo_center_angle_deg"], "model.servo_center_angle_deg"
        ),
        maximum_fit_position_error_m=_number(
            model_raw["maximum_fit_position_error_m"],
            "model.maximum_fit_position_error_m",
        ),
        maximum_fit_approach_error_deg=_number(
            model_raw["maximum_fit_approach_error_deg"],
            "model.maximum_fit_approach_error_deg",
        ),
    )
    if model.base_servo_angle_deg != 90.0 or model.servo_center_angle_deg != 90.0:
        raise ReachabilityError("model servo reference angles must remain 90 degrees")
    if not 0.0005 <= model.maximum_fit_position_error_m <= 0.01:
        raise ReachabilityError("model maximum position residual is outside [0.0005, 0.01]")
    if not 0.0001 <= model.maximum_fit_approach_error_deg <= 1.0:
        raise ReachabilityError("model maximum approach residual is outside [0.0001, 1]")

    search_raw = _strict_object(
        raw["search"],
        {
            "physical_angle_min_deg",
            "physical_angle_max_deg",
            "command_angle_min_deg",
            "command_angle_max_deg",
            "grid_step_deg",
            "maximum_ranked_candidates",
            "minimum_workspace_front_y_m",
        },
        "search",
    )
    search = SearchConfig(
        physical_angle_min_deg=_integer(
            search_raw["physical_angle_min_deg"], "search.physical_angle_min_deg"
        ),
        physical_angle_max_deg=_integer(
            search_raw["physical_angle_max_deg"], "search.physical_angle_max_deg"
        ),
        command_angle_min_deg=_integer(
            search_raw["command_angle_min_deg"], "search.command_angle_min_deg"
        ),
        command_angle_max_deg=_integer(
            search_raw["command_angle_max_deg"], "search.command_angle_max_deg"
        ),
        grid_step_deg=_integer(search_raw["grid_step_deg"], "search.grid_step_deg"),
        maximum_ranked_candidates=_integer(
            search_raw["maximum_ranked_candidates"],
            "search.maximum_ranked_candidates",
        ),
        minimum_workspace_front_y_m=_number(
            search_raw["minimum_workspace_front_y_m"],
            "search.minimum_workspace_front_y_m",
        ),
    )
    if (
        search.physical_angle_min_deg,
        search.physical_angle_max_deg,
        search.command_angle_min_deg,
        search.command_angle_max_deg,
    ) != (60, 120, 68, 112):
        raise ReachabilityError(
            "search bounds must preserve physical [60,120] and command [68,112]"
        )
    if search.grid_step_deg != 1:
        raise ReachabilityError("search.grid_step_deg must equal 1")
    if not 3 <= search.maximum_ranked_candidates <= 50:
        raise ReachabilityError("search.maximum_ranked_candidates must be in [3, 50]")
    if not 0.0 <= search.minimum_workspace_front_y_m <= 0.10:
        raise ReachabilityError("minimum workspace-front y must be in [0, 0.10]")

    samples_raw = raw["samples"]
    if not isinstance(samples_raw, list) or len(samples_raw) != len(indices):
        raise ReachabilityError("samples must match source.sample_step_indices")
    samples: list[CalibrationSample] = []
    for index, sample_value in enumerate(samples_raw):
        sample_raw = _strict_object(
            sample_value,
            {
                "step_index",
                "angles_deg",
                "origin_world_m",
                "approach_axis_world_unit",
            },
            f"samples[{index}]",
        )
        step_index = _integer(sample_raw["step_index"], f"samples[{index}].step_index")
        if step_index != indices[index]:
            raise ReachabilityError("sample step indices do not match source provenance")
        angles = _vector(
            sample_raw["angles_deg"], length=4, label=f"samples[{index}].angles_deg"
        )
        if abs(angles[0] - model.base_servo_angle_deg) > 0.1:
            raise ReachabilityError("calibration base joint must remain at 90 degrees")
        samples.append(
            CalibrationSample(
                step_index=step_index,
                angles_deg=angles,  # type: ignore[arg-type]
                origin_world_m=_vector(
                    sample_raw["origin_world_m"],
                    length=3,
                    label=f"samples[{index}].origin_world_m",
                ),  # type: ignore[arg-type]
                approach_axis_world_unit=_unit_vector(
                    sample_raw["approach_axis_world_unit"],
                    f"samples[{index}].approach_axis_world_unit",
                ),
            )
        )
    return ReachabilityConfig(
        name=name,
        source=source,
        model=model,
        search=search,
        samples=tuple(samples),
    )


def load_reachability_config(path: Path) -> tuple[ReachabilityConfig, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReachabilityError(f"{path} is not valid JSON: {error}") from error
    return parse_reachability_config(value), hashlib.sha256(raw).hexdigest()


def _matmul_inverse(
    rows: Sequence[Sequence[float]],
    values: Sequence[float],
) -> tuple[float, ...]:
    width = len(rows[0])
    normal = [
        [
            sum(row[left] * row[right] for row in rows)
            for right in range(width)
        ]
        for left in range(width)
    ]
    right_hand = [
        sum(row[column] * value for row, value in zip(rows, values, strict=True))
        for column in range(width)
    ]
    inverse = _inverse(normal)
    return tuple(
        sum(inverse[row][column] * right_hand[column] for column in range(width))
        for row in range(width)
    )


def fit_planar_model(config: ReachabilityConfig) -> PlanarModel:
    """Fit and validate the planar three-pitch-chain model."""

    rows: list[list[float]] = []
    values: list[float] = []
    center = config.model.servo_center_angle_deg
    for sample in config.samples:
        q2, q3, q4 = (
            math.radians(value - center) for value in sample.angles_deg[1:]
        )
        cumulative = (q2, q2 + q3, q2 + q3 + q4)
        rows.append(
            [
                1.0,
                0.0,
                -math.sin(cumulative[0]),
                -math.sin(cumulative[1]),
                -math.sin(cumulative[2]),
            ]
        )
        values.append(sample.origin_world_m[1])
        rows.append(
            [
                0.0,
                1.0,
                math.cos(cumulative[0]),
                math.cos(cumulative[1]),
                math.cos(cumulative[2]),
            ]
        )
        values.append(sample.origin_world_m[2])
    y_offset, z_offset, link1, link2, link3 = _matmul_inverse(rows, values)
    links = (link1, link2, link3)
    if any(length <= 0.01 or length >= 0.20 for length in links):
        raise ReachabilityError("fitted link lengths are outside conservative bounds")

    x_offset = sum(sample.origin_world_m[0] for sample in config.samples) / len(
        config.samples
    )
    approach_x = sum(
        sample.approach_axis_world_unit[0] for sample in config.samples
    ) / len(config.samples)
    offsets: list[float] = []
    for sample in config.samples:
        qsum = sum(
            math.radians(value - center) for value in sample.angles_deg[1:]
        )
        observed_angle = math.atan2(
            sample.approach_axis_world_unit[1],
            sample.approach_axis_world_unit[2],
        )
        offsets.append(observed_angle + qsum)
    approach_offset = sum(offsets) / len(offsets)

    preliminary = PlanarModel(
        x_offset_m=x_offset,
        y_offset_m=y_offset,
        z_offset_m=z_offset,
        link_lengths_m=links,
        approach_x=approach_x,
        approach_angle_offset_deg=math.degrees(approach_offset),
        maximum_position_residual_m=0.0,
        rms_position_residual_m=0.0,
        maximum_approach_residual_deg=0.0,
    )
    position_residuals: list[float] = []
    approach_residuals: list[float] = []
    for sample in config.samples:
        origin, approach = predict_planar_frame(preliminary, sample.angles_deg)
        position_residuals.append(
            math.sqrt(
                sum(
                    (predicted - observed) ** 2
                    for predicted, observed in zip(
                        origin, sample.origin_world_m, strict=True
                    )
                )
            )
        )
        approach_residuals.append(
            direction_error_deg(approach, sample.approach_axis_world_unit)
        )
    model = PlanarModel(
        x_offset_m=x_offset,
        y_offset_m=y_offset,
        z_offset_m=z_offset,
        link_lengths_m=links,
        approach_x=approach_x,
        approach_angle_offset_deg=math.degrees(approach_offset),
        maximum_position_residual_m=max(position_residuals),
        rms_position_residual_m=math.sqrt(
            sum(value * value for value in position_residuals)
            / len(position_residuals)
        ),
        maximum_approach_residual_deg=max(approach_residuals),
    )
    if (
        model.maximum_position_residual_m
        > config.model.maximum_fit_position_error_m
    ):
        raise ReachabilityError("planar model exceeds position residual limit")
    if (
        model.maximum_approach_residual_deg
        > config.model.maximum_fit_approach_error_deg
    ):
        raise ReachabilityError("planar model exceeds approach residual limit")
    return model


def predict_planar_frame(
    model: PlanarModel,
    angles_deg: Sequence[float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if len(angles_deg) != 4:
        raise ReachabilityError("angles_deg must contain four values")
    angles = tuple(_number(value, f"angles_deg[{index}]") for index, value in enumerate(angles_deg))
    if abs(angles[0] - 90.0) > 0.1:
        raise ReachabilityError("offline planar model only supports the 90-degree base branch")
    q2, q3, q4 = (math.radians(value - 90.0) for value in angles[1:])
    cumulative = (q2, q2 + q3, q2 + q3 + q4)
    y = model.y_offset_m - sum(
        length * math.sin(angle)
        for length, angle in zip(model.link_lengths_m, cumulative, strict=True)
    )
    z = model.z_offset_m + sum(
        length * math.cos(angle)
        for length, angle in zip(model.link_lengths_m, cumulative, strict=True)
    )
    theta = math.radians(model.approach_angle_offset_deg) - sum((q2, q3, q4))
    planar_scale = math.sqrt(max(0.0, 1.0 - model.approach_x**2))
    approach = (
        model.approach_x,
        planar_scale * math.sin(theta),
        planar_scale * math.cos(theta),
    )
    return (model.x_offset_m, y, z), approach


def minimum_approach_error_over_bounds(
    model: PlanarModel,
    target_axis_world_unit: Sequence[float],
    *,
    angle_min_deg: float,
    angle_max_deg: float,
) -> float:
    target = _unit_vector(list(target_axis_world_unit), "target_axis_world_unit")
    center = 90.0
    theta_min = math.radians(model.approach_angle_offset_deg) - 3.0 * math.radians(
        angle_max_deg - center
    )
    theta_max = math.radians(model.approach_angle_offset_deg) - 3.0 * math.radians(
        angle_min_deg - center
    )
    planar_scale = math.sqrt(max(0.0, 1.0 - model.approach_x**2))
    preferred = math.atan2(target[1], target[2])
    candidates = [theta_min, theta_max]
    for turn in range(-2, 3):
        angle = preferred + turn * 2.0 * math.pi
        if theta_min <= angle <= theta_max:
            candidates.append(angle)
    maximum_dot = max(
        model.approach_x * target[0]
        + planar_scale * (
            target[1] * math.sin(angle) + target[2] * math.cos(angle)
        )
        for angle in candidates
    )
    return math.degrees(math.acos(max(-1.0, min(1.0, maximum_dot))))


def terminal_pose_proximal_reach(
    model: PlanarModel,
    *,
    target_position_world_m: Sequence[float],
    target_approach_axis_world_unit: Sequence[float],
) -> dict[str, Any]:
    """Check coupled position/orientation reach without applying angle bounds."""

    target_position = _vector(
        list(target_position_world_m),
        length=3,
        label="target_position_world_m",
    )
    target_approach = _unit_vector(
        list(target_approach_axis_world_unit),
        "target_approach_axis_world_unit",
    )
    terminal_length = model.link_lengths_m[2]
    wrist_anchor = tuple(
        position - terminal_length * direction
        for position, direction in zip(
            target_position,
            target_approach,
            strict=True,
        )
    )
    proximal_base = (
        model.x_offset_m,
        model.y_offset_m,
        model.z_offset_m,
    )
    required = math.sqrt(
        sum(
            (target - base) ** 2
            for target, base in zip(wrist_anchor, proximal_base, strict=True)
        )
    )
    minimum = abs(model.link_lengths_m[0] - model.link_lengths_m[1])
    maximum = model.link_lengths_m[0] + model.link_lengths_m[1]
    return {
        "target_wrist_anchor_world_m": list(wrist_anchor),
        "proximal_base_world_m": list(proximal_base),
        "terminal_link_length_m": terminal_length,
        "required_proximal_reach_m": required,
        "minimum_proximal_reach_m": minimum,
        "maximum_proximal_reach_m": maximum,
        "maximum_reach_margin_m": maximum - required,
        "reachable_without_angle_bounds": minimum <= required <= maximum,
    }


def _posture_branch(angles_deg: Sequence[int]) -> str:
    labels = []
    for value in angles_deg[1:]:
        if value < 90:
            labels.append("low")
        elif value > 90:
            labels.append("high")
        else:
            labels.append("neutral")
    return "/".join(
        f"joint{index + 2}_{label}" for index, label in enumerate(labels)
    )


def search_planar_pose(
    model: PlanarModel,
    *,
    target_position_world_m: Sequence[float],
    target_approach_axis_world_unit: Sequence[float],
    position_tolerance_m: float,
    approach_tolerance_deg: float,
    angle_min_deg: int,
    angle_max_deg: int,
    grid_step_deg: int,
    minimum_workspace_front_y_m: float,
    maximum_ranked_candidates: int,
) -> dict[str, Any]:
    target_position = _vector(
        list(target_position_world_m), length=3, label="target_position_world_m"
    )
    target_approach = _unit_vector(
        list(target_approach_axis_world_unit),
        "target_approach_axis_world_unit",
    )
    if position_tolerance_m <= 0.0 or approach_tolerance_deg <= 0.0:
        raise ReachabilityError("pose tolerances must be positive")
    if angle_min_deg >= angle_max_deg or grid_step_deg <= 0:
        raise ReachabilityError("search angle bounds or grid step are invalid")

    best_by_branch: dict[str, ReachabilityCandidate] = {}
    passed_count = 0
    evaluated_count = 0
    front_count = 0
    minimum_front_approach_error = math.inf
    values = range(angle_min_deg, angle_max_deg + 1, grid_step_deg)
    for joint2 in values:
        for joint3 in values:
            for joint4 in values:
                evaluated_count += 1
                angles = (90, joint2, joint3, joint4)
                origin, approach = predict_planar_frame(model, angles)
                if origin[1] < minimum_workspace_front_y_m:
                    continue
                front_count += 1
                position_error = math.sqrt(
                    sum(
                        (predicted - target) ** 2
                        for predicted, target in zip(
                            origin, target_position, strict=True
                        )
                    )
                )
                approach_error = direction_error_deg(approach, target_approach)
                minimum_front_approach_error = min(
                    minimum_front_approach_error,
                    approach_error,
                )
                passed = (
                    position_error <= position_tolerance_m
                    and approach_error <= approach_tolerance_deg
                )
                if passed:
                    passed_count += 1
                normalized_score = math.sqrt(
                    (position_error / position_tolerance_m) ** 2
                    + (approach_error / approach_tolerance_deg) ** 2
                )
                branch = _posture_branch(angles)
                candidate = ReachabilityCandidate(
                    angles_deg=angles,
                    posture_branch=branch,
                    origin_world_m=origin,
                    approach_axis_world_unit=approach,
                    position_error_m=position_error,
                    approach_error_deg=approach_error,
                    minimum_angle_margin_deg=min(
                        joint2 - angle_min_deg,
                        joint3 - angle_min_deg,
                        joint4 - angle_min_deg,
                        angle_max_deg - joint2,
                        angle_max_deg - joint3,
                        angle_max_deg - joint4,
                    ),
                    normalized_score=normalized_score,
                    passed=passed,
                )
                previous = best_by_branch.get(branch)
                if previous is None or (
                    candidate.normalized_score,
                    -candidate.minimum_angle_margin_deg,
                    candidate.angles_deg,
                ) < (
                    previous.normalized_score,
                    -previous.minimum_angle_margin_deg,
                    previous.angles_deg,
                ):
                    best_by_branch[branch] = candidate
    ranked = sorted(
        best_by_branch.values(),
        key=lambda candidate: (
            candidate.normalized_score,
            -candidate.minimum_angle_margin_deg,
            candidate.angles_deg,
        ),
    )
    return {
        "angle_bounds_deg": [angle_min_deg, angle_max_deg],
        "grid_step_deg": grid_step_deg,
        "evaluated_count": evaluated_count,
        "workspace_front_count": front_count,
        "posture_branch_count": len(best_by_branch),
        "passed_candidate_count": passed_count,
        "target_feasible": passed_count > 0,
        "minimum_approach_error_lower_bound_deg": minimum_approach_error_over_bounds(
            model,
            target_approach,
            angle_min_deg=angle_min_deg,
            angle_max_deg=angle_max_deg,
        ),
        "minimum_workspace_front_approach_error_deg": (
            minimum_front_approach_error
        ),
        "ranked_branch_candidates": [
            candidate.to_dict()
            for candidate in ranked[:maximum_ranked_candidates]
        ],
    }
