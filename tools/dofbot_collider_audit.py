#!/usr/bin/env python3
"""Pure contracts and geometry for the DF-049 robot/table collider audit."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ColliderAuditError(ValueError):
    """The collider audit config or telemetry is incomplete."""


@dataclass(frozen=True)
class ColliderAuditConfig:
    ledger_discriminator: str
    prior_matrix_artifact: str
    scene_decomposition_config: str
    allowed_cells: tuple[str, ...]
    robot_root_prim_path: str
    table_root_prim_path: str
    maximum_executed_cells: int
    case_timeout_seconds: int
    deadline_seconds: int
    viewer_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_discriminator": self.ledger_discriminator,
            "prior_matrix_artifact": self.prior_matrix_artifact,
            "scene_decomposition_config": self.scene_decomposition_config,
            "allowed_cells": list(self.allowed_cells),
            "robot_root_prim_path": self.robot_root_prim_path,
            "table_root_prim_path": self.table_root_prim_path,
            "maximum_executed_cells": self.maximum_executed_cells,
            "case_timeout_seconds": self.case_timeout_seconds,
            "deadline_seconds": self.deadline_seconds,
            "viewer_authorized": self.viewer_authorized,
        }


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ColliderAuditError(f"{label} must be an object")
    return value


def _strict_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ColliderAuditError(
            f"{label} keys must be exactly {sorted(expected)}, got {sorted(value)}"
        )


def _absolute_prim_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or value.endswith("/"):
        raise ColliderAuditError(f"{label} must be an absolute prim path")
    return value


def load_collider_audit_config(path: Path) -> tuple[ColliderAuditConfig, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ColliderAuditError(f"cannot load {path}: {error}") from error
    root = _object(value, "collider audit config")
    _strict_keys(
        root,
        {
            "schema_version",
            "ledger_discriminator",
            "sources",
            "cells",
            "prim_roots",
            "required_evidence",
            "paid_window",
        },
        "collider audit config",
    )
    if root["schema_version"] != 1 or root["ledger_discriminator"] != "DF-049":
        raise ColliderAuditError("collider audit schema or discriminator changed")
    sources = _object(root["sources"], "sources")
    _strict_keys(
        sources,
        {"prior_matrix_artifact", "scene_decomposition_config"},
        "sources",
    )
    cells = root["cells"]
    if cells != ["S0", "T1"]:
        raise ColliderAuditError("DF-049 must run exactly S0 then T1")
    roots = _object(root["prim_roots"], "prim_roots")
    _strict_keys(roots, {"robot", "table"}, "prim_roots")
    evidence = _object(root["required_evidence"], "required_evidence")
    required_evidence = {
        "every_robot_and_table_collision_prim": True,
        "nearest_rigid_body_owner": True,
        "body_local_and_world_aabb": True,
        "collision_contact_rest_offsets": True,
        "collision_filter_relationships": True,
        "raw_and_normalized_contact_actor_paths": True,
        "per_step_closest_collider_pair": True,
    }
    if evidence != required_evidence:
        raise ColliderAuditError("required collider evidence was weakened")
    paid = _object(root["paid_window"], "paid_window")
    _strict_keys(
        paid,
        {
            "maximum_executed_cells",
            "case_timeout_seconds",
            "deadline_seconds",
            "viewer_authorized",
        },
        "paid_window",
    )
    if paid != {
        "maximum_executed_cells": 2,
        "case_timeout_seconds": 180,
        "deadline_seconds": 480,
        "viewer_authorized": False,
    }:
        raise ColliderAuditError("DF-049 paid-window boundary changed")
    for source_name, source_path in sources.items():
        if not isinstance(source_path, str) or source_path.startswith("/"):
            raise ColliderAuditError(f"{source_name} must be a repository path")
    config = ColliderAuditConfig(
        ledger_discriminator="DF-049",
        prior_matrix_artifact=sources["prior_matrix_artifact"],
        scene_decomposition_config=sources["scene_decomposition_config"],
        allowed_cells=tuple(cells),
        robot_root_prim_path=_absolute_prim_path(roots["robot"], "robot root"),
        table_root_prim_path=_absolute_prim_path(roots["table"], "table root"),
        maximum_executed_cells=2,
        case_timeout_seconds=180,
        deadline_seconds=480,
        viewer_authorized=False,
    )
    return config, hashlib.sha256(raw).hexdigest()


def is_same_or_descendant(path: str, ancestor: str) -> bool:
    """Return true only for a complete Sdf path-prefix match."""
    return path == ancestor or path.startswith(f"{ancestor}/")


def nearest_path_ancestor(path: str, candidates: Iterable[str]) -> str | None:
    """Resolve a collider/actor path to its deepest monitored ancestor."""
    matches = [value for value in candidates if is_same_or_descendant(path, value)]
    return max(matches, key=len, default=None)


def _vector3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ColliderAuditError(f"{label} must contain three values")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ColliderAuditError(f"{label} must be finite")
    return result  # type: ignore[return-value]


def _quaternion(value: Any) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ColliderAuditError("body quaternion must contain w,x,y,z")
    result = tuple(float(item) for item in value)
    norm = math.sqrt(sum(item * item for item in result))
    if not math.isfinite(norm) or norm <= 1.0e-12:
        raise ColliderAuditError("body quaternion must be finite and nonzero")
    return tuple(item / norm for item in result)  # type: ignore[return-value]


def _rotate_wxyz(
    vector: tuple[float, float, float],
    quaternion_wxyz: tuple[float, float, float, float],
) -> tuple[float, float, float]:
    w, x, y, z = quaternion_wxyz
    vx, vy, vz = vector
    # Unit-quaternion rotation, expanded to avoid runtime-only dependencies.
    return (
        (1 - 2 * (y * y + z * z)) * vx
        + 2 * (x * y - z * w) * vy
        + 2 * (x * z + y * w) * vz,
        2 * (x * y + z * w) * vx
        + (1 - 2 * (x * x + z * z)) * vy
        + 2 * (y * z - x * w) * vz,
        2 * (x * z - y * w) * vx
        + 2 * (y * z + x * w) * vy
        + (1 - 2 * (x * x + y * y)) * vz,
    )


def transform_local_aabb(
    *,
    minimum_body_m: Any,
    maximum_body_m: Any,
    body_position_world_m: Any,
    body_quaternion_wxyz: Any,
) -> dict[str, list[float]]:
    """Conservatively transform a body-frame AABB into a world-frame AABB."""
    minimum = _vector3(minimum_body_m, "local AABB minimum")
    maximum = _vector3(maximum_body_m, "local AABB maximum")
    if any(low > high for low, high in zip(minimum, maximum, strict=True)):
        raise ColliderAuditError("local AABB minimum exceeds maximum")
    position = _vector3(body_position_world_m, "body position")
    quaternion = _quaternion(body_quaternion_wxyz)
    corners = []
    for x in (minimum[0], maximum[0]):
        for y in (minimum[1], maximum[1]):
            for z in (minimum[2], maximum[2]):
                rotated = _rotate_wxyz((x, y, z), quaternion)
                corners.append(
                    tuple(
                        rotated[index] + position[index] for index in range(3)
                    )
                )
    return {
        "minimum_world_m": [min(point[index] for point in corners) for index in range(3)],
        "maximum_world_m": [max(point[index] for point in corners) for index in range(3)],
    }


def signed_aabb_separation(a: Any, b: Any) -> float:
    """Euclidean gap when disjoint; negative minimum overlap depth otherwise."""
    first = _object(a, "first AABB")
    second = _object(b, "second AABB")
    first_min = _vector3(first.get("minimum_world_m"), "first AABB minimum")
    first_max = _vector3(first.get("maximum_world_m"), "first AABB maximum")
    second_min = _vector3(second.get("minimum_world_m"), "second AABB minimum")
    second_max = _vector3(second.get("maximum_world_m"), "second AABB maximum")
    gaps = [
        max(first_min[i] - second_max[i], second_min[i] - first_max[i], 0.0)
        for i in range(3)
    ]
    if any(value > 0.0 for value in gaps):
        return math.sqrt(sum(value * value for value in gaps))
    overlaps = [
        min(first_max[i], second_max[i]) - max(first_min[i], second_min[i])
        for i in range(3)
    ]
    return -min(overlaps)


def evaluate_collider_clearance(
    *,
    robot_colliders: list[dict[str, Any]],
    table_colliders: list[dict[str, Any]],
    body_poses: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return the closest conservative robot/table collider pair for one step."""
    if not robot_colliders:
        raise ColliderAuditError("robot collision inventory is empty")
    if not table_colliders:
        return {
            "evaluated_robot_collider_count": len(robot_colliders),
            "evaluated_table_collider_count": 0,
            "evaluated_pair_count": 0,
            "overlap_pair_count": 0,
            "minimum_signed_aabb_separation_m": None,
            "closest_pair": None,
        }
    best: dict[str, Any] | None = None
    overlap_count = 0
    for robot in robot_colliders:
        owner = robot.get("owner_body_name")
        if not isinstance(owner, str) or owner not in body_poses:
            raise ColliderAuditError(
                f"robot collider {robot.get('prim_path')} has no live body owner"
            )
        local = _object(robot.get("body_local_aabb"), "body-local collider AABB")
        pose = _object(body_poses[owner], f"body pose {owner}")
        robot_world = transform_local_aabb(
            minimum_body_m=local.get("minimum_body_m"),
            maximum_body_m=local.get("maximum_body_m"),
            body_position_world_m=pose.get("position_world_m"),
            body_quaternion_wxyz=pose.get("quaternion_wxyz"),
        )
        for table in table_colliders:
            table_world = _object(table.get("world_aabb"), "table collider AABB")
            separation = signed_aabb_separation(robot_world, table_world)
            if separation <= 0.0:
                overlap_count += 1
            candidate = {
                "signed_aabb_separation_m": separation,
                "robot_collider_path": robot.get("prim_path"),
                "robot_owner_body_name": owner,
                "table_collider_path": table.get("prim_path"),
                "robot_world_aabb": robot_world,
                "table_world_aabb": table_world,
            }
            if best is None or separation < best["signed_aabb_separation_m"]:
                best = candidate
    return {
        "evaluated_robot_collider_count": len(robot_colliders),
        "evaluated_table_collider_count": len(table_colliders),
        "evaluated_pair_count": len(robot_colliders) * len(table_colliders),
        "overlap_pair_count": overlap_count,
        "minimum_signed_aabb_separation_m": best["signed_aabb_separation_m"],
        "closest_pair": best,
    }


def summarize_collider_clearance_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize per-step collider telemetry without discarding the closest pair."""
    with_table = [
        sample
        for sample in samples
        if sample.get("minimum_signed_aabb_separation_m") is not None
    ]
    if not with_table:
        return {
            "sample_count": len(samples),
            "table_sample_count": 0,
            "minimum_signed_aabb_separation_m": None,
            "closest_sample": None,
            "overlap_observed": False,
            "first_overlap_sample": None,
        }
    closest = min(
        with_table,
        key=lambda value: float(value["minimum_signed_aabb_separation_m"]),
    )
    overlap = next(
        (
            value
            for value in with_table
            if float(value["minimum_signed_aabb_separation_m"]) <= 0.0
        ),
        None,
    )
    return {
        "sample_count": len(samples),
        "table_sample_count": len(with_table),
        "minimum_signed_aabb_separation_m": float(
            closest["minimum_signed_aabb_separation_m"]
        ),
        "closest_sample": closest,
        "overlap_observed": overlap is not None,
        "first_overlap_sample": overlap,
    }
