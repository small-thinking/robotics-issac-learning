"""GPU-free task-space design for a reachable DOFBOT pre-grasp.

The search starts from joint poses rather than guessed Cartesian targets. A
small planar model fitted to recorded Isaac observations predicts the terminal
finger midpoint and approach axis. The task scene is then derived from each
pose and filtered by joint, table, target, and model-residual margins.
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
    from .dofbot_pregrasp_pose import (
        direction_error_deg,
        signed_point_box_distance,
    )
    from .dofbot_pregrasp_reachability import PlanarModel, predict_planar_frame
except ImportError:
    from dofbot_pregrasp_pose import (
        direction_error_deg,
        signed_point_box_distance,
    )
    from dofbot_pregrasp_reachability import PlanarModel, predict_planar_frame

SCHEMA_VERSION = 1
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class TaskspaceSearchError(ValueError):
    """Raised when the task-space design contract is malformed or unsafe."""


@dataclass(frozen=True)
class SourceContracts:
    asset_contract_sha256: str
    motion_config_contract_sha256: str
    reachability_config_sha256: str
    rejected_reachability_artifact_sha256: str


@dataclass(frozen=True)
class GeometryConfig:
    table_size_m: tuple[float, float, float]
    cube_size_m: tuple[float, float, float]
    table_center_ahead_of_cube_m: float
    pregrasp_standoff_m: float
    cube_focus_height_above_center_m: float


@dataclass(frozen=True)
class SearchConfig:
    physical_angle_min_deg: int
    physical_angle_max_deg: int
    validated_command_angle_min_deg: int
    validated_command_angle_max_deg: int
    search_angle_min_deg: int
    search_angle_max_deg: int
    grid_step_deg: int
    minimum_physical_angle_margin_deg: int
    minimum_search_angle_margin_deg: int
    minimum_forward_approach_component: float
    minimum_upward_approach_component: float
    maximum_upward_approach_component: float
    requested_low_table_top_max_m: float
    minimum_candidate_table_top_m: float
    maximum_candidate_table_top_m: float
    minimum_table_front_clearance_m: float
    minimum_terminal_table_clearance_m: float
    minimum_terminal_cube_clearance_m: float
    minimum_model_residual_reserve_m: float
    maximum_approach_projection_error_deg: float
    maximum_ranked_candidates: int


@dataclass(frozen=True)
class TaskspaceConfig:
    name: str
    sources: SourceContracts
    geometry: GeometryConfig
    search: SearchConfig


@dataclass(frozen=True)
class TaskspaceCandidate:
    angles_deg: tuple[int, int, int, int]
    target_origin_world_m: tuple[float, float, float]
    predicted_approach_axis_world_unit: tuple[float, float, float]
    target_approach_axis_world_unit: tuple[float, float, float]
    target_closing_axis_world_unit: tuple[float, float, float]
    cube_focus_world_m: tuple[float, float, float]
    cube_center_world_m: tuple[float, float, float]
    table_center_world_m: tuple[float, float, float]
    table_top_m: float
    physical_angle_margin_deg: int
    search_angle_margin_deg: int
    approach_projection_error_deg: float
    table_front_clearance_m: float
    cube_edge_inset_m: float
    terminal_table_clearance_m: float
    terminal_cube_clearance_m: float
    robust_terminal_table_clearance_m: float
    robust_terminal_cube_clearance_m: float
    minimum_clearance_reserve_m: float
    checks: dict[str, bool]

    def to_dict(self, *, geometry: GeometryConfig) -> dict[str, Any]:
        return {
            "angles_deg": list(self.angles_deg),
            "target_pose": {
                "origin_world_m": list(self.target_origin_world_m),
                "predicted_approach_axis_world_unit": list(
                    self.predicted_approach_axis_world_unit
                ),
                "approach_axis_world_unit": list(
                    self.target_approach_axis_world_unit
                ),
                "closing_axis_world_unit": list(
                    self.target_closing_axis_world_unit
                ),
                "approach_projection_error_deg": (
                    self.approach_projection_error_deg
                ),
            },
            "scene": {
                "cube_focus_world_m": list(self.cube_focus_world_m),
                "cube_center_world_m": list(self.cube_center_world_m),
                "cube_size_m": list(geometry.cube_size_m),
                "table_center_world_m": list(self.table_center_world_m),
                "table_size_m": list(geometry.table_size_m),
                "table_top_m": self.table_top_m,
                "table_front_clearance_m": self.table_front_clearance_m,
                "cube_edge_inset_m": self.cube_edge_inset_m,
            },
            "margins": {
                "physical_angle_margin_deg": self.physical_angle_margin_deg,
                "search_angle_margin_deg": self.search_angle_margin_deg,
                "terminal_table_clearance_m": (
                    self.terminal_table_clearance_m
                ),
                "terminal_cube_clearance_m": self.terminal_cube_clearance_m,
                "robust_terminal_table_clearance_m": (
                    self.robust_terminal_table_clearance_m
                ),
                "robust_terminal_cube_clearance_m": (
                    self.robust_terminal_cube_clearance_m
                ),
                "minimum_clearance_reserve_m": (
                    self.minimum_clearance_reserve_m
                ),
            },
            "checks": self.checks,
            "passed": all(self.checks.values()),
        }


def _strict_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise TaskspaceSearchError(
            f"{label} keys must match {sorted(keys)}; got {actual}"
        )
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TaskspaceSearchError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise TaskspaceSearchError(f"{label} must be finite")
    return result


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TaskspaceSearchError(f"{label} must be an integer")
    return value


def _vector3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise TaskspaceSearchError(f"{label} must contain three values")
    return tuple(
        _number(item, f"{label}[{index}]") for index, item in enumerate(value)
    )  # type: ignore[return-value]


def _sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TaskspaceSearchError(f"{label} must be a lowercase SHA-256")
    return value


def parse_taskspace_config(value: Any) -> TaskspaceConfig:
    raw = _strict_object(
        value,
        {"schema_version", "name", "source_contracts", "geometry", "search"},
        "root",
    )
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(
        raw["schema_version"], bool
    ):
        raise TaskspaceSearchError(f"schema_version must equal {SCHEMA_VERSION}")
    name = raw["name"]
    if not isinstance(name, str) or _NAME_PATTERN.fullmatch(name) is None:
        raise TaskspaceSearchError("name must be lowercase snake_case")

    source_raw = _strict_object(
        raw["source_contracts"],
        {
            "asset_contract_sha256",
            "motion_config_contract_sha256",
            "reachability_config_sha256",
            "rejected_reachability_artifact_sha256",
        },
        "source_contracts",
    )
    sources = SourceContracts(
        asset_contract_sha256=_sha256(
            source_raw["asset_contract_sha256"],
            "source_contracts.asset_contract_sha256",
        ),
        motion_config_contract_sha256=_sha256(
            source_raw["motion_config_contract_sha256"],
            "source_contracts.motion_config_contract_sha256",
        ),
        reachability_config_sha256=_sha256(
            source_raw["reachability_config_sha256"],
            "source_contracts.reachability_config_sha256",
        ),
        rejected_reachability_artifact_sha256=_sha256(
            source_raw["rejected_reachability_artifact_sha256"],
            "source_contracts.rejected_reachability_artifact_sha256",
        ),
    )

    geometry_raw = _strict_object(
        raw["geometry"],
        {
            "table_size_m",
            "cube_size_m",
            "table_center_ahead_of_cube_m",
            "pregrasp_standoff_m",
            "cube_focus_height_above_center_m",
        },
        "geometry",
    )
    geometry = GeometryConfig(
        table_size_m=_vector3(geometry_raw["table_size_m"], "geometry.table_size_m"),
        cube_size_m=_vector3(geometry_raw["cube_size_m"], "geometry.cube_size_m"),
        table_center_ahead_of_cube_m=_number(
            geometry_raw["table_center_ahead_of_cube_m"],
            "geometry.table_center_ahead_of_cube_m",
        ),
        pregrasp_standoff_m=_number(
            geometry_raw["pregrasp_standoff_m"],
            "geometry.pregrasp_standoff_m",
        ),
        cube_focus_height_above_center_m=_number(
            geometry_raw["cube_focus_height_above_center_m"],
            "geometry.cube_focus_height_above_center_m",
        ),
    )
    if geometry.table_size_m != (0.5, 0.3, 0.04):
        raise TaskspaceSearchError("table size must remain 0.50 x 0.30 x 0.04 m")
    if geometry.cube_size_m != (0.05, 0.05, 0.05):
        raise TaskspaceSearchError("cube size must remain 0.05 m on every axis")
    if not 0.04 <= geometry.table_center_ahead_of_cube_m <= 0.08:
        raise TaskspaceSearchError("table/cube center offset must be in [0.04, 0.08]")
    if not 0.07 <= geometry.pregrasp_standoff_m <= 0.10:
        raise TaskspaceSearchError("pre-grasp standoff must be in [0.07, 0.10]")
    if not 0.015 <= geometry.cube_focus_height_above_center_m <= 0.024:
        raise TaskspaceSearchError("cube focus height must stay below the cube top")

    search_raw = _strict_object(
        raw["search"],
        {
            "physical_angle_min_deg",
            "physical_angle_max_deg",
            "validated_command_angle_min_deg",
            "validated_command_angle_max_deg",
            "search_angle_min_deg",
            "search_angle_max_deg",
            "grid_step_deg",
            "minimum_physical_angle_margin_deg",
            "minimum_search_angle_margin_deg",
            "minimum_forward_approach_component",
            "minimum_upward_approach_component",
            "maximum_upward_approach_component",
            "requested_low_table_top_max_m",
            "minimum_candidate_table_top_m",
            "maximum_candidate_table_top_m",
            "minimum_table_front_clearance_m",
            "minimum_terminal_table_clearance_m",
            "minimum_terminal_cube_clearance_m",
            "minimum_model_residual_reserve_m",
            "maximum_approach_projection_error_deg",
            "maximum_ranked_candidates",
        },
        "search",
    )
    integers = {
        field: _integer(search_raw[field], f"search.{field}")
        for field in (
            "physical_angle_min_deg",
            "physical_angle_max_deg",
            "validated_command_angle_min_deg",
            "validated_command_angle_max_deg",
            "search_angle_min_deg",
            "search_angle_max_deg",
            "grid_step_deg",
            "minimum_physical_angle_margin_deg",
            "minimum_search_angle_margin_deg",
            "maximum_ranked_candidates",
        )
    }
    numbers = {
        field: _number(search_raw[field], f"search.{field}")
        for field in (
            "minimum_forward_approach_component",
            "minimum_upward_approach_component",
            "maximum_upward_approach_component",
            "requested_low_table_top_max_m",
            "minimum_candidate_table_top_m",
            "maximum_candidate_table_top_m",
            "minimum_table_front_clearance_m",
            "minimum_terminal_table_clearance_m",
            "minimum_terminal_cube_clearance_m",
            "minimum_model_residual_reserve_m",
            "maximum_approach_projection_error_deg",
        )
    }
    search = SearchConfig(**integers, **numbers)
    if (
        search.physical_angle_min_deg,
        search.physical_angle_max_deg,
        search.validated_command_angle_min_deg,
        search.validated_command_angle_max_deg,
        search.search_angle_min_deg,
        search.search_angle_max_deg,
        search.grid_step_deg,
    ) != (60, 120, 62, 118, 64, 116, 1):
        raise TaskspaceSearchError(
            "angle contracts must remain physical [60,120], validated "
            "[62,118], search [64,116], step 1"
        )
    if (
        search.minimum_physical_angle_margin_deg,
        search.minimum_search_angle_margin_deg,
    ) != (6, 2):
        raise TaskspaceSearchError("joint margins must remain physical 6 and search 2")
    if not 0.85 <= search.minimum_forward_approach_component <= 0.95:
        raise TaskspaceSearchError("minimum forward approach is outside [0.85, 0.95]")
    if not (
        search.minimum_upward_approach_component == 0.0
        and 0.3 <= search.maximum_upward_approach_component <= 0.5
    ):
        raise TaskspaceSearchError("upward approach band is invalid")
    if not (
        0.10 <= search.requested_low_table_top_max_m <= 0.12
        and 0.18 <= search.minimum_candidate_table_top_m
        < search.maximum_candidate_table_top_m
        <= 0.30
    ):
        raise TaskspaceSearchError("table height bands are invalid")
    if not 0.10 <= search.minimum_table_front_clearance_m <= 0.20:
        raise TaskspaceSearchError("table front clearance is outside [0.10, 0.20]")
    if not 0.015 <= search.minimum_terminal_table_clearance_m <= 0.03:
        raise TaskspaceSearchError("terminal/table clearance is invalid")
    if not 0.04 <= search.minimum_terminal_cube_clearance_m <= 0.08:
        raise TaskspaceSearchError("terminal/cube clearance is invalid")
    if not 0.002 <= search.minimum_model_residual_reserve_m <= 0.01:
        raise TaskspaceSearchError("model residual reserve is invalid")
    if not 0.1 <= search.maximum_approach_projection_error_deg <= 2.0:
        raise TaskspaceSearchError("approach projection error is invalid")
    if not 1 <= search.maximum_ranked_candidates <= 25:
        raise TaskspaceSearchError("maximum ranked candidates must be in [1, 25]")
    return TaskspaceConfig(
        name=name,
        sources=sources,
        geometry=geometry,
        search=search,
    )


def load_taskspace_config(path: Path) -> tuple[TaskspaceConfig, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise TaskspaceSearchError(f"{path} is not valid JSON: {error}") from error
    return parse_taskspace_config(value), hashlib.sha256(raw).hexdigest()


def project_approach_to_closing_plane(
    approach: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Project the measured approach into the YZ plane orthogonal to +X."""

    norm = math.hypot(approach[1], approach[2])
    if norm < 1e-9:
        raise TaskspaceSearchError("approach cannot be projected into the YZ plane")
    return (0.0, approach[1] / norm, approach[2] / norm)


def _derive_candidate(
    model: PlanarModel,
    config: TaskspaceConfig,
    angles_deg: tuple[int, int, int, int],
) -> TaskspaceCandidate:
    origin, predicted_approach = predict_planar_frame(model, angles_deg)
    approach = project_approach_to_closing_plane(predicted_approach)
    geometry = config.geometry
    search = config.search
    focus = tuple(
        origin[index] + geometry.pregrasp_standoff_m * approach[index]
        for index in range(3)
    )
    cube_center = (
        origin[0],
        focus[1],
        focus[2] - geometry.cube_focus_height_above_center_m,
    )
    table_top = cube_center[2] - geometry.cube_size_m[2] / 2.0
    table_center = (
        origin[0],
        cube_center[1] + geometry.table_center_ahead_of_cube_m,
        table_top - geometry.table_size_m[2] / 2.0,
    )
    physical_margin = min(
        [
            value - search.physical_angle_min_deg
            for value in angles_deg[1:]
        ]
        + [
            search.physical_angle_max_deg - value
            for value in angles_deg[1:]
        ]
    )
    search_margin = min(
        [
            value - search.search_angle_min_deg
            for value in angles_deg[1:]
        ]
        + [
            search.search_angle_max_deg - value
            for value in angles_deg[1:]
        ]
    )
    table_front = table_center[1] - geometry.table_size_m[1] / 2.0
    cube_edge_inset = min(
        geometry.table_size_m[0] / 2.0 - geometry.cube_size_m[0] / 2.0,
        geometry.table_size_m[1] / 2.0
        - geometry.table_center_ahead_of_cube_m
        - geometry.cube_size_m[1] / 2.0,
    )
    table_clearance = signed_point_box_distance(
        origin,
        table_center,
        geometry.table_size_m,
    )
    cube_clearance = signed_point_box_distance(
        origin,
        cube_center,
        geometry.cube_size_m,
    )
    robust_table = table_clearance - model.maximum_position_residual_m
    robust_cube = cube_clearance - model.maximum_position_residual_m
    minimum_reserve = min(
        robust_table - search.minimum_terminal_table_clearance_m,
        robust_cube - search.minimum_terminal_cube_clearance_m,
    )
    projection_error = direction_error_deg(predicted_approach, approach)
    checks = {
        "physical_angle_margin_met": (
            physical_margin >= search.minimum_physical_angle_margin_deg
        ),
        "search_angle_margin_met": (
            search_margin >= search.minimum_search_angle_margin_deg
        ),
        "approach_points_into_workspace_front": (
            approach[1] >= search.minimum_forward_approach_component
        ),
        "approach_upward_component_in_band": (
            search.minimum_upward_approach_component
            <= approach[2]
            <= search.maximum_upward_approach_component
        ),
        "approach_projection_error_bounded": (
            projection_error
            <= search.maximum_approach_projection_error_deg
        ),
        "table_top_in_candidate_band": (
            search.minimum_candidate_table_top_m
            <= table_top
            <= search.maximum_candidate_table_top_m
        ),
        "table_outside_base_keepout": (
            table_front >= search.minimum_table_front_clearance_m
        ),
        "cube_footprint_has_edge_inset": cube_edge_inset >= 0.05,
        "terminal_table_clearance_robust_to_model_residual": (
            robust_table >= search.minimum_terminal_table_clearance_m
        ),
        "terminal_cube_clearance_robust_to_model_residual": (
            robust_cube >= search.minimum_terminal_cube_clearance_m
        ),
        "minimum_model_residual_reserve_met": (
            minimum_reserve >= search.minimum_model_residual_reserve_m
        ),
    }
    return TaskspaceCandidate(
        angles_deg=angles_deg,
        target_origin_world_m=origin,
        predicted_approach_axis_world_unit=predicted_approach,
        target_approach_axis_world_unit=approach,
        target_closing_axis_world_unit=(1.0, 0.0, 0.0),
        cube_focus_world_m=focus,
        cube_center_world_m=cube_center,
        table_center_world_m=table_center,
        table_top_m=table_top,
        physical_angle_margin_deg=physical_margin,
        search_angle_margin_deg=search_margin,
        approach_projection_error_deg=projection_error,
        table_front_clearance_m=table_front,
        cube_edge_inset_m=cube_edge_inset,
        terminal_table_clearance_m=table_clearance,
        terminal_cube_clearance_m=cube_clearance,
        robust_terminal_table_clearance_m=robust_table,
        robust_terminal_cube_clearance_m=robust_cube,
        minimum_clearance_reserve_m=minimum_reserve,
        checks=checks,
    )


def search_taskspace(
    model: PlanarModel,
    config: TaskspaceConfig,
) -> dict[str, Any]:
    search = config.search
    geometry = config.geometry
    low_table_minimum = math.inf
    low_table_angle: tuple[int, int, int, int] | None = None
    physical_front_count = 0
    physical_values = range(
        search.physical_angle_min_deg,
        search.physical_angle_max_deg + 1,
        search.grid_step_deg,
    )
    for joint2 in physical_values:
        for joint3 in physical_values:
            for joint4 in physical_values:
                candidate = _derive_candidate(
                    model,
                    config,
                    (90, joint2, joint3, joint4),
                )
                approach = candidate.target_approach_axis_world_unit
                if (
                    approach[1] < search.minimum_forward_approach_component
                    or not search.minimum_upward_approach_component
                    <= approach[2]
                    <= search.maximum_upward_approach_component
                ):
                    continue
                physical_front_count += 1
                if candidate.table_top_m < low_table_minimum:
                    low_table_minimum = candidate.table_top_m
                    low_table_angle = candidate.angles_deg

    candidates: list[TaskspaceCandidate] = []
    evaluated_count = 0
    values = range(
        search.search_angle_min_deg,
        search.search_angle_max_deg + 1,
        search.grid_step_deg,
    )
    for joint2 in values:
        for joint3 in values:
            for joint4 in values:
                evaluated_count += 1
                candidate = _derive_candidate(
                    model,
                    config,
                    (90, joint2, joint3, joint4),
                )
                if all(candidate.checks.values()):
                    candidates.append(candidate)
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            -candidate.minimum_clearance_reserve_m,
            candidate.table_top_m,
            sum(
                (
                    angle
                    - sum(candidate.angles_deg[1:]) / 3.0
                )
                ** 2
                for angle in candidate.angles_deg[1:]
            ),
            candidate.angles_deg,
        ),
    )
    if low_table_angle is None:
        raise TaskspaceSearchError("physical search found no front-side approach")
    return {
        "physical_envelope": {
            "angle_bounds_deg": [
                search.physical_angle_min_deg,
                search.physical_angle_max_deg,
            ],
            "evaluated_count": (
                (
                    search.physical_angle_max_deg
                    - search.physical_angle_min_deg
                )
                // search.grid_step_deg
                + 1
            )
            ** 3,
            "front_angled_approach_count": physical_front_count,
            "minimum_derived_table_top_m": low_table_minimum,
            "minimum_table_top_angles_deg": list(low_table_angle),
            "requested_low_table_top_max_m": (
                search.requested_low_table_top_max_m
            ),
            "requested_low_table_feasible": (
                low_table_minimum <= search.requested_low_table_top_max_m
            ),
        },
        "candidate_search": {
            "angle_bounds_deg": [
                search.search_angle_min_deg,
                search.search_angle_max_deg,
            ],
            "evaluated_count": evaluated_count,
            "passed_candidate_count": len(candidates),
            "ranked_candidates": [
                candidate.to_dict(geometry=geometry)
                for candidate in ranked[: search.maximum_ranked_candidates]
            ],
        },
    }
