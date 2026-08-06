#!/usr/bin/env python3
"""Semantically verify one S0/T1 DF-049 collider-audit artifact."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

try:
    from .dofbot_collider_audit import (
        ColliderAuditError,
        load_collider_audit_config,
        summarize_collider_clearance_samples,
    )
    from .verify_dofbot_scene_decomposition_case import (
        SceneDecompositionCaseError,
        load_scene_cell_artifact,
        verify_scene_decomposition_case,
    )
except ImportError:
    from dofbot_collider_audit import (
        ColliderAuditError,
        load_collider_audit_config,
        summarize_collider_clearance_samples,
    )
    from verify_dofbot_scene_decomposition_case import (
        SceneDecompositionCaseError,
        load_scene_cell_artifact,
        verify_scene_decomposition_case,
    )


class ColliderAuditCaseError(ValueError):
    """A machine collider-audit artifact is incomplete or stale."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ColliderAuditCaseError(f"{label} must be an object")
    return value


def _finite_vector(value: Any, size: int, label: str) -> None:
    if not isinstance(value, list) or len(value) != size:
        raise ColliderAuditCaseError(f"{label} has wrong shape")
    if not all(isinstance(item, (int, float)) and math.isfinite(item) for item in value):
        raise ColliderAuditCaseError(f"{label} must be finite")


def _verify_aabb(value: Any, frame: str, label: str) -> None:
    bounds = _object(value, label)
    _finite_vector(bounds.get(f"minimum_{frame}_m"), 3, f"{label} minimum")
    _finite_vector(bounds.get(f"maximum_{frame}_m"), 3, f"{label} maximum")


def verify_collider_audit_case(
    artifact: dict[str, Any],
    *,
    cell_id: str,
    project_dir: Path,
    scene_config_path: Path,
    collider_config_path: Path,
    expected_git_commit: str,
) -> dict[str, Any]:
    config, config_sha256 = load_collider_audit_config(collider_config_path)
    if cell_id not in config.allowed_cells:
        raise ColliderAuditCaseError("cell is outside the DF-049 contract")
    base = verify_scene_decomposition_case(
        artifact,
        cell_id=cell_id,
        project_dir=project_dir,
        config_path=scene_config_path,
        expected_git_commit=expected_git_commit,
        enforce_sentinel=(cell_id == "S0"),
    )
    audit = _object(artifact.get("collider_audit"), "collider audit")
    if audit.get("config_sha256") != config_sha256 or audit.get(
        "config"
    ) != config.to_dict():
        raise ColliderAuditCaseError("collider audit config is stale")
    robot = audit.get("robot_colliders")
    table = audit.get("table_colliders")
    if not isinstance(robot, list) or not robot:
        raise ColliderAuditCaseError("robot collider inventory is empty")
    if not isinstance(table, list):
        raise ColliderAuditCaseError("table collider inventory is missing")
    if (cell_id == "S0" and table) or (cell_id == "T1" and not table):
        raise ColliderAuditCaseError("table collider inventory disagrees with cell")
    paths = []
    for item_value in robot:
        item = _object(item_value, "robot collider")
        path = item.get("prim_path")
        if not isinstance(path, str) or item.get("owner_status") != "resolved":
            raise ColliderAuditCaseError("robot collider owner is unresolved")
        if not isinstance(item.get("owner_body_name"), str):
            raise ColliderAuditCaseError("robot collider body name is missing")
        _verify_aabb(item.get("body_local_aabb"), "body", "robot local AABB")
        _verify_aabb(item.get("world_aabb"), "world", "robot world AABB")
        for field in ("contact_offset", "rest_offset"):
            snapshot = _object(item.get(field), field)
            if set(snapshot) != {"present", "authored", "value"}:
                raise ColliderAuditCaseError(f"{field} snapshot is incomplete")
        if not isinstance(item.get("filtered_pairs_targets"), list):
            raise ColliderAuditCaseError("robot collider filters are missing")
        paths.append(path)
    if len(paths) != len(set(paths)):
        raise ColliderAuditCaseError("robot collider paths are duplicated")
    for item_value in table:
        item = _object(item_value, "table collider")
        _verify_aabb(item.get("world_aabb"), "world", "table world AABB")
    samples = _object(artifact.get("measurement"), "measurement").get("samples")
    if not isinstance(samples, list) or not samples:
        raise ColliderAuditCaseError("physics-step samples are missing")
    collider_samples = []
    for sample_value in samples:
        sample = _object(sample_value, "physics sample")
        collider_sample = _object(sample.get("collider_audit"), "collider sample")
        if collider_sample.get("evaluated_robot_collider_count") != len(robot):
            raise ColliderAuditCaseError("per-step robot collider count changed")
        if collider_sample.get("evaluated_table_collider_count") != len(table):
            raise ColliderAuditCaseError("per-step table collider count changed")
        if table:
            separation = collider_sample.get("minimum_signed_aabb_separation_m")
            if not isinstance(separation, (int, float)) or not math.isfinite(separation):
                raise ColliderAuditCaseError("per-step separation is invalid")
            if not isinstance(collider_sample.get("closest_pair"), dict):
                raise ColliderAuditCaseError("closest collider pair is missing")
        collider_samples.append(collider_sample)
    recomputed = summarize_collider_clearance_samples(collider_samples)
    if audit.get("clearance_summary") != recomputed:
        raise ColliderAuditCaseError("collider clearance summary is inconsistent")
    if audit.get("aabb_is_conservative_not_exact_shape_distance") is not True:
        raise ColliderAuditCaseError("AABB inference boundary is missing")
    contact = _object(
        _object(artifact.get("telemetry"), "telemetry").get("contact_events"),
        "contact events",
    )
    if contact.get("path_matching_mode") != (
        "same_or_descendant_of_monitored_rigid_body"
    ):
        raise ColliderAuditCaseError("contact actor normalization is not active")
    monitored_paths = contact.get("monitored_rigid_body_paths")
    expected_owner_paths = sorted(
        {str(value["owner_body_path"]) for value in robot}
    )
    if monitored_paths != expected_owner_paths:
        raise ColliderAuditCaseError(
            "contact monitoring paths do not match live collider owners"
        )
    for field in (
        "all_actor_pairs",
        "monitored_actor_pairs",
        "normalized_monitored_actor_pairs",
    ):
        if not isinstance(contact.get(field), list):
            raise ColliderAuditCaseError(f"{field} is missing")
    return {
        **base,
        "robot_collider_count": len(robot),
        "table_collider_count": len(table),
        "minimum_signed_aabb_separation_m": recomputed[
            "minimum_signed_aabb_separation_m"
        ],
        "overlap_observed": recomputed["overlap_observed"],
        "closest_sample": recomputed["closest_sample"],
        "contact_header_count": contact["contact_header_count"],
        "normalized_monitored_actor_pairs": contact[
            "normalized_monitored_actor_pairs"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--cell", choices=("S0", "T1"), required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--scene-config", type=Path, required=True)
    parser.add_argument("--collider-config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()
    try:
        result = verify_collider_audit_case(
            load_scene_cell_artifact(args.artifact),
            cell_id=args.cell,
            project_dir=args.project_dir,
            scene_config_path=args.scene_config,
            collider_config_path=args.collider_config,
            expected_git_commit=args.expected_git_commit,
        )
    except (
        OSError,
        json.JSONDecodeError,
        ColliderAuditError,
        ColliderAuditCaseError,
        SceneDecompositionCaseError,
    ) as error:
        print(f"[COLLIDER AUDIT CASE] FAIL: {error}")
        return 1
    print(
        "[COLLIDER AUDIT CASE] PASS: "
        f"cell={args.cell} tracking_gate_passed="
        f"{str(result['tracking_gate_passed']).lower()} "
        f"robot_colliders={result['robot_collider_count']} "
        f"minimum_signed_aabb_separation_m="
        f"{result['minimum_signed_aabb_separation_m']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
