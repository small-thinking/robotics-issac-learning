"""Pure contracts for the adaptive DOFBOT static-scene decomposition.

This module intentionally imports no Isaac packages.  It makes the paid
experiment reviewable and mutation-testable on a CPU runner before Kit starts.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
EXPECTED_CELL_IDS = ("S0", "T1", "T0", "TF", "Q1", "Q0", "QF", "P1", "P0", "PF")
EXPECTED_OBJECTS = frozenset({"table", "target_cube"})
_CELL_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,2}$")


class SceneDecompositionError(ValueError):
    """The scene decomposition config or evidence is unsafe or malformed."""


@dataclass(frozen=True)
class SceneDecompositionCell:
    id: str
    objects: tuple[str, ...]
    collision_enabled: bool
    translation_offset_world_m: tuple[float, float, float]
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objects": list(self.objects),
            "collision_enabled": self.collision_enabled,
            "translation_offset_world_m": list(self.translation_offset_world_m),
            "role": self.role,
        }


@dataclass(frozen=True)
class SceneDecompositionConfig:
    name: str
    source_scene_config: str
    calibration_config: str
    case_name: str
    far_translation_offset_world_m: tuple[float, float, float]
    cells: tuple[SceneDecompositionCell, ...]
    maximum_settled_tracking_error_deg: float
    maximum_contact_force_n: float
    maximum_executed_cells: int
    case_timeout_seconds: int
    matrix_deadline_seconds: int
    viewer_authorized: bool

    def cell(self, cell_id: str) -> SceneDecompositionCell:
        for cell in self.cells:
            if cell.id == cell_id:
                return cell
        raise SceneDecompositionError(f"unknown scene decomposition cell: {cell_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "source_scene_config": self.source_scene_config,
            "calibration_config": self.calibration_config,
            "case_name": self.case_name,
            "far_translation_offset_world_m": list(self.far_translation_offset_world_m),
            "cells": [cell.to_dict() for cell in self.cells],
            "acceptance": {
                "maximum_settled_tracking_error_deg": self.maximum_settled_tracking_error_deg,
                "maximum_contact_force_n": self.maximum_contact_force_n,
            },
            "paid_window": {
                "maximum_executed_cells": self.maximum_executed_cells,
                "case_timeout_seconds": self.case_timeout_seconds,
                "matrix_deadline_seconds": self.matrix_deadline_seconds,
                "viewer_authorized": self.viewer_authorized,
            },
        }


def _strict_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise SceneDecompositionError(
            f"{label} keys must match {sorted(keys)}; got {actual}"
        )
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SceneDecompositionError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise SceneDecompositionError(f"{label} must be finite")
    return result


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SceneDecompositionError(f"{label} must be an integer")
    return value


def _vector3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise SceneDecompositionError(f"{label} must contain three numbers")
    return tuple(_number(item, f"{label}[{index}]") for index, item in enumerate(value))


def _repo_path(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or ".." in Path(value).parts
    ):
        raise SceneDecompositionError(f"{label} must be a repository-relative path")
    return value


def _parse_cell(value: Any, index: int) -> SceneDecompositionCell:
    raw = _strict_object(
        value,
        {"id", "objects", "collision_enabled", "translation_offset_world_m", "role"},
        f"cells[{index}]",
    )
    cell_id = raw["id"]
    if not isinstance(cell_id, str) or not _CELL_ID_PATTERN.fullmatch(cell_id):
        raise SceneDecompositionError(f"cells[{index}].id is invalid")
    objects = raw["objects"]
    if (
        not isinstance(objects, list)
        or len(objects) != len(set(objects))
        or any(value not in EXPECTED_OBJECTS for value in objects)
    ):
        raise SceneDecompositionError(
            f"cells[{index}].objects must be unique table/target_cube names"
        )
    collision_enabled = raw["collision_enabled"]
    if not isinstance(collision_enabled, bool):
        raise SceneDecompositionError(
            f"cells[{index}].collision_enabled must be boolean"
        )
    if not objects and collision_enabled:
        raise SceneDecompositionError("the S0 sentinel cannot enable collision")
    role = raw["role"]
    if not isinstance(role, str) or len(role.strip()) < 12:
        raise SceneDecompositionError(f"cells[{index}].role is too short")
    return SceneDecompositionCell(
        id=cell_id,
        objects=tuple(objects),
        collision_enabled=collision_enabled,
        translation_offset_world_m=_vector3(
            raw["translation_offset_world_m"],
            f"cells[{index}].translation_offset_world_m",
        ),
        role=role.strip(),
    )


def _expected_cell_contract(
    far_offset: tuple[float, float, float],
) -> dict[str, tuple[tuple[str, ...], bool, tuple[float, float, float]]]:
    near = (0.0, 0.0, 0.0)
    return {
        "S0": ((), False, near),
        "T1": (("table",), True, near),
        "T0": (("table",), False, near),
        "TF": (("table",), True, far_offset),
        "Q1": (("target_cube",), True, near),
        "Q0": (("target_cube",), False, near),
        "QF": (("target_cube",), True, far_offset),
        "P1": (("table", "target_cube"), True, near),
        "P0": (("table", "target_cube"), False, near),
        "PF": (("table", "target_cube"), True, far_offset),
    }


def load_scene_decomposition_config(path: Path) -> tuple[SceneDecompositionConfig, str]:
    raw_bytes = path.read_bytes()
    try:
        value = json.loads(raw_bytes)
    except json.JSONDecodeError as error:
        raise SceneDecompositionError(f"{path} is not valid JSON") from error
    raw = _strict_object(
        value,
        {
            "schema_version",
            "name",
            "source_scene_config",
            "calibration_config",
            "case_name",
            "far_translation_offset_world_m",
            "cells",
            "acceptance",
            "paid_window",
        },
        "scene decomposition config",
    )
    if raw["schema_version"] != SCHEMA_VERSION:
        raise SceneDecompositionError("unsupported scene decomposition schema")
    if raw["name"] != "goal5_scene_decomposition":
        raise SceneDecompositionError("unexpected scene decomposition name")
    if raw["case_name"] != "bounded_gravity_feed_forward":
        raise SceneDecompositionError("actuator case must remain bounded_gravity_feed_forward")
    far_offset = _vector3(raw["far_translation_offset_world_m"], "far offset")
    if math.sqrt(sum(value * value for value in far_offset)) < 1.0:
        raise SceneDecompositionError("far offset must move objects by at least one meter")
    cells_raw = raw["cells"]
    if not isinstance(cells_raw, list):
        raise SceneDecompositionError("cells must be a list")
    cells = tuple(_parse_cell(item, index) for index, item in enumerate(cells_raw))
    if tuple(cell.id for cell in cells) != EXPECTED_CELL_IDS:
        raise SceneDecompositionError(
            f"cell order must equal {list(EXPECTED_CELL_IDS)}"
        )
    expected = _expected_cell_contract(far_offset)
    for cell in cells:
        if (
            cell.objects,
            cell.collision_enabled,
            cell.translation_offset_world_m,
        ) != expected[cell.id]:
            raise SceneDecompositionError(f"cell {cell.id} changes an unexpected factor")
    acceptance = _strict_object(
        raw["acceptance"],
        {"maximum_settled_tracking_error_deg", "maximum_contact_force_n"},
        "acceptance",
    )
    tracking_limit = _number(
        acceptance["maximum_settled_tracking_error_deg"],
        "acceptance.maximum_settled_tracking_error_deg",
    )
    contact_limit = _number(
        acceptance["maximum_contact_force_n"],
        "acceptance.maximum_contact_force_n",
    )
    if tracking_limit != 1.0 or contact_limit != 0.5:
        raise SceneDecompositionError("existing tracking/contact gates cannot change")
    paid = _strict_object(
        raw["paid_window"],
        {
            "maximum_executed_cells",
            "case_timeout_seconds",
            "matrix_deadline_seconds",
            "viewer_authorized",
        },
        "paid_window",
    )
    maximum_cells = _integer(paid["maximum_executed_cells"], "maximum cells")
    case_timeout = _integer(paid["case_timeout_seconds"], "case timeout")
    matrix_deadline = _integer(paid["matrix_deadline_seconds"], "matrix deadline")
    if not 1 <= maximum_cells <= 6:
        raise SceneDecompositionError("maximum_executed_cells must be in [1, 6]")
    if not 60 <= case_timeout <= 240:
        raise SceneDecompositionError("case_timeout_seconds must be in [60, 240]")
    if not 600 <= matrix_deadline <= 1200:
        raise SceneDecompositionError("matrix_deadline_seconds must be in [600, 1200]")
    if maximum_cells * case_timeout > matrix_deadline:
        raise SceneDecompositionError("per-cell timeouts exceed the matrix deadline")
    if paid["viewer_authorized"] is not False:
        raise SceneDecompositionError("Viewer must remain blocked")
    config = SceneDecompositionConfig(
        name=raw["name"],
        source_scene_config=_repo_path(raw["source_scene_config"], "source_scene_config"),
        calibration_config=_repo_path(raw["calibration_config"], "calibration_config"),
        case_name=raw["case_name"],
        far_translation_offset_world_m=far_offset,
        cells=cells,
        maximum_settled_tracking_error_deg=tracking_limit,
        maximum_contact_force_n=contact_limit,
        maximum_executed_cells=maximum_cells,
        case_timeout_seconds=case_timeout,
        matrix_deadline_seconds=matrix_deadline,
        viewer_authorized=False,
    )
    return config, hashlib.sha256(raw_bytes).hexdigest()


def next_scene_decomposition_cell(results: dict[str, bool]) -> str | None:
    """Return the next adaptive cell, or ``None`` when the branch is complete."""
    unknown = set(results) - set(EXPECTED_CELL_IDS)
    if unknown:
        raise SceneDecompositionError(f"unknown recorded cells: {sorted(unknown)}")
    if "S0" not in results:
        return "S0"
    if results["S0"] is False:
        return None
    if "T1" not in results:
        return "T1"
    if results["T1"] is False:
        if "T0" not in results:
            return "T0"
        return "TF" if "TF" not in results else None
    if "Q1" not in results:
        return "Q1"
    if results["Q1"] is False:
        if "Q0" not in results:
            return "Q0"
        return "QF" if "QF" not in results else None
    if "P1" not in results:
        return "P1"
    if results["P1"] is True:
        return None
    if "P0" not in results:
        return "P0"
    return "PF" if "PF" not in results else None


def classify_scene_decomposition_results(results: dict[str, bool]) -> str:
    if next_scene_decomposition_cell(results) is not None:
        return "matrix_incomplete"
    if results.get("S0") is False:
        return "current_source_regression"
    for prefix, object_name in (("T", "table"), ("Q", "cube")):
        if results.get(f"{prefix}1") is False:
            collision_off_pass = results[f"{prefix}0"]
            far_pass = results[f"{prefix}F"]
            if collision_off_pass and far_pass:
                return f"near_{object_name}_collision_context_is_causal"
            if collision_off_pass and not far_pass:
                return f"{object_name}_collidable_registration_is_causal"
            if not collision_off_pass and far_pass:
                return f"near_{object_name}_spawn_geometry_is_causal"
            return f"{object_name}_spawn_side_effect_is_causal"
    if results.get("P1") is True:
        return "historical_static_scene_effect_not_reproduced"
    if results.get("P0") is True and results.get("PF") is True:
        return "near_pair_collision_context_is_causal"
    if results.get("P0") is True and results.get("PF") is False:
        return "pair_collidable_registration_is_causal"
    if results.get("P0") is False and results.get("PF") is True:
        return "near_pair_spawn_geometry_interaction_is_causal"
    return "pair_spawn_side_effect_is_causal"


def axis_aligned_bounds(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> dict[str, list[float]]:
    return {
        "minimum_world_m": [
            center[index] - size[index] / 2.0 for index in range(3)
        ],
        "maximum_world_m": [
            center[index] + size[index] / 2.0 for index in range(3)
        ],
    }


def minimum_body_center_aabb_clearances(
    samples: list[dict[str, Any]],
    spawned_objects: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure terminal-body-center separation from each authored world AABB."""
    by_object: dict[str, dict[str, Any]] = {}
    for spawned in spawned_objects:
        center = tuple(float(value) for value in spawned["center_world_m"])
        size = tuple(float(value) for value in spawned["size_m"])
        minimum = tuple(center[index] - size[index] / 2.0 for index in range(3))
        maximum = tuple(center[index] + size[index] / 2.0 for index in range(3))
        minimum_distance = math.inf
        closest_body = None
        closest_pose = None
        sample_count = 0
        for sample in samples:
            positions = sample.get("body_positions_world_m")
            if not isinstance(positions, dict):
                continue
            for body_name, position in positions.items():
                if not isinstance(position, list) or len(position) != 3:
                    continue
                deltas = [
                    max(minimum[index] - float(position[index]), 0.0)
                    + max(float(position[index]) - maximum[index], 0.0)
                    for index in range(3)
                ]
                distance = math.sqrt(sum(value * value for value in deltas))
                sample_count += 1
                if distance < minimum_distance:
                    minimum_distance = distance
                    closest_body = body_name
                    closest_pose = sample.get("pose_name")
        by_object[str(spawned["name"])] = {
            "minimum_terminal_body_center_aabb_distance_m": (
                minimum_distance if math.isfinite(minimum_distance) else None
            ),
            "closest_terminal_body": closest_body,
            "closest_pose": closest_pose,
            "evaluated_body_samples": sample_count,
        }
    return {
        "objects": by_object,
        "body_center_proxy_is_not_mesh_clearance": True,
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
