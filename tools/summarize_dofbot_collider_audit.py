#!/usr/bin/env python3
"""Verify and summarize the two-cell DF-049 collider audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .dofbot_collider_audit import ColliderAuditError, load_collider_audit_config
    from .verify_dofbot_collider_audit_case import (
        ColliderAuditCaseError,
        verify_collider_audit_case,
    )
    from .verify_dofbot_scene_decomposition_case import (
        SceneDecompositionCaseError,
        load_scene_cell_artifact,
    )
except ImportError:
    from dofbot_collider_audit import ColliderAuditError, load_collider_audit_config
    from verify_dofbot_collider_audit_case import (
        ColliderAuditCaseError,
        verify_collider_audit_case,
    )
    from verify_dofbot_scene_decomposition_case import (
        SceneDecompositionCaseError,
        load_scene_cell_artifact,
    )


class ColliderAuditSummaryError(ValueError):
    """The two-cell collider audit is incomplete."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_collider_audit(
    *,
    input_dir: Path,
    project_dir: Path,
    scene_config_path: Path,
    collider_config_path: Path,
    expected_git_commit: str,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    config, config_sha256 = load_collider_audit_config(collider_config_path)
    cells = {}
    for cell_id in config.allowed_cells:
        path = input_dir / f"cell_{cell_id.lower()}.json"
        if not path.is_file():
            raise ColliderAuditSummaryError(f"missing required cell {cell_id}")
        summary = verify_collider_audit_case(
            load_scene_cell_artifact(path),
            cell_id=cell_id,
            project_dir=project_dir,
            scene_config_path=scene_config_path,
            collider_config_path=collider_config_path,
            expected_git_commit=expected_git_commit,
        )
        summary["artifact"] = {
            "path": path.relative_to(project_dir).as_posix()
            if path.is_relative_to(project_dir)
            else str(path),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        cells[cell_id] = summary
    if cells["S0"]["tracking_gate_passed"] is not True:
        raise ColliderAuditSummaryError("S0 source sentinel failed")
    t1 = cells["T1"]
    if t1["tracking_gate_passed"] is True:
        decision = "t1_residual_not_reproduced_stop_for_source_runtime_audit"
    elif t1["normalized_monitored_actor_pairs"]:
        decision = "normalized_robot_table_contact_detected"
    elif t1["overlap_observed"]:
        decision = "conservative_robot_table_aabb_overlap_localized"
    else:
        decision = "no_aabb_overlap_contact_offset_filter_or_registration_remains"
    return {
        "schema_version": 1,
        "experiment": "dofbot_collider_audit_machine_result",
        "ledger_discriminator": "DF-049",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": expected_git_commit,
        "config": {
            "path": collider_config_path.relative_to(project_dir).as_posix(),
            "sha256": config_sha256,
        },
        "cells": cells,
        "result": {
            "complete": True,
            "executed_cells": list(config.allowed_cells),
            "decision": decision,
            "closest_t1_sample": t1["closest_sample"],
        },
        "authorization": {
            "integrated_pregrasp": False,
            "viewer": False,
            "contact_or_grasp": False,
            "reason": (
                "DF-049 is a measurement-only mechanism discriminator, not a "
                "passing integrated pre-grasp gate."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--scene-config", type=Path, required=True)
    parser.add_argument("--collider-config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = summarize_collider_audit(
            input_dir=args.input_dir,
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
        ColliderAuditSummaryError,
        SceneDecompositionCaseError,
    ) as error:
        print(f"[COLLIDER AUDIT] FAIL: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[COLLIDER AUDIT] PASS: decision={result['result']['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
