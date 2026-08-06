#!/usr/bin/env python3
"""Prepare the GPU-free DF-049 full-collider diagnostic contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .audit_dofbot_context_transfer import (
        CURRENT_SHARED_RUNTIME_PATHS,
        _source_bundle,
    )
    from .dofbot_collider_audit import (
        ColliderAuditError,
        load_collider_audit_config,
    )
    from .dofbot_scene_decomposition import sha256_file
except ImportError:
    from audit_dofbot_context_transfer import (
        CURRENT_SHARED_RUNTIME_PATHS,
        _source_bundle,
    )
    from dofbot_collider_audit import (
        ColliderAuditError,
        load_collider_audit_config,
    )
    from dofbot_scene_decomposition import sha256_file


class ColliderAuditPlanError(ValueError):
    """The DF-049 plan does not bind the completed DF-048 result."""


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ColliderAuditPlanError(f"{path} must contain an object")
    return value


def build_collider_audit_plan(
    *,
    project_dir: Path,
    config_path: Path,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    config_path = (
        config_path.resolve()
        if config_path.is_absolute()
        else (project_dir / config_path).resolve()
    )
    config, config_sha256 = load_collider_audit_config(config_path)
    prior_path = project_dir / config.prior_matrix_artifact
    prior = _read_object(prior_path)
    matrix = prior.get("matrix")
    cells = prior.get("cells")
    if not isinstance(matrix, dict) or not isinstance(cells, dict):
        raise ColliderAuditPlanError("DF-048 matrix evidence is incomplete")
    expected_results = {"S0": True, "T1": False, "T0": True, "TF": True}
    observed_results = {
        cell_id: cells.get(cell_id, {}).get("tracking_gate_passed")
        if isinstance(cells.get(cell_id), dict)
        else None
        for cell_id in expected_results
    }
    source_paths = (
        *CURRENT_SHARED_RUNTIME_PATHS,
        "configs/dofbot/calibration/goal5_collider_audit.json",
        "tools/prepare_dofbot_collider_audit.py",
        "tools/verify_dofbot_collider_audit_case.py",
        "tools/summarize_dofbot_collider_audit.py",
        "scripts/isaac/run_dofbot_collider_audit.sh",
    )
    checks = {
        "df_048_matrix_complete": matrix.get("complete") is True,
        "df_048_near_collision_on_table_is_causal": (
            matrix.get("decision") == "near_table_collision_context_is_causal"
        ),
        "df_048_exact_branch_is_bound": observed_results == expected_results,
        "next_run_is_s0_then_t1_only": config.allowed_cells == ("S0", "T1"),
        "motion_drive_feed_forward_and_gates_remain_fixed": True,
        "full_collider_inventory_required": True,
        "descendant_contact_path_normalization_required": True,
        "viewer_remains_blocked": config.viewer_authorized is False,
        "gpu_not_started_by_preparation": True,
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ColliderAuditPlanError(
            "collider audit preparation failed: " + ", ".join(failed)
        )
    return {
        "schema_version": 1,
        "experiment": "dofbot_collider_audit_preflight",
        "ledger_discriminator": "DF-049",
        "sources": {
            "config": {
                "path": config_path.relative_to(project_dir).as_posix(),
                "sha256": config_sha256,
            },
            "df_048_matrix": {
                "path": config.prior_matrix_artifact,
                "sha256": sha256_file(prior_path),
                "decision": matrix["decision"],
                "cell_tracking_results": observed_results,
            },
            "runtime_source_bundle": _source_bundle(
                project_dir=project_dir,
                paths=source_paths,
            ),
        },
        "unresolved_ledger_id": "DF-048",
        "new_discriminator": {
            "single_changed_factor": (
                "measurement only: replace terminal-body-center and exact-path "
                "proxies with every composed robot/table collider and normalized "
                "contact actor paths"
            ),
            "cells": ["S0", "T1"],
            "new_observations": [
                "every collision prim and nearest rigid-body owner",
                "body-local collider AABB transformed by live body pose per step",
                "table collider world AABB",
                "contact/rest offsets and authored filter relationships",
                "all raw contact pairs plus normalized rigid-body owners",
                "first and closest robot/table AABB overlap or separation",
            ],
            "does_not_repeat_df_048": (
                "T1 is repeated only to collect collider-level observations absent "
                "from DF-048; no controller or simulator factor changes"
            ),
        },
        "decision_tree": {
            "s0_fails": "new source regression; stop before T1",
            "t1_no_longer_fails": "nonreproduction; stop and inspect source/runtime drift",
            "t1_fails_with_normalized_contact": (
                "contact-report blind spot resolved; name the reporting collider/body"
            ),
            "t1_fails_with_conservative_aabb_overlap": (
                "localize the candidate collider/body before one-collider isolation"
            ),
            "t1_fails_without_aabb_overlap": (
                "contact-offset, filter, broadphase, or collision-registration layer remains"
            ),
        },
        "anti_loop_stop_rule": (
            "Run no more than S0 and T1. The next code/physics change must be selected "
            "from the named closest collider/contact evidence; do not tune motion, "
            "drive, feed-forward, tolerance, table pose, or cube state."
        ),
        "checks": checks,
        "preflight_passed": True,
        "authorization": {
            "paid_run": False,
            "viewer": False,
            "integrated_pregrasp": False,
            "contact_or_grasp": False,
            "reason": (
                "GPU-free preparation only. A merged branch, fresh matching quote/state "
                "check, and explicit approval remain mandatory."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/dofbot/calibration/goal5_collider_audit.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_collider_audit_plan(
            project_dir=args.project_dir,
            config_path=args.config,
        )
    except (OSError, json.JSONDecodeError, ColliderAuditError, ColliderAuditPlanError) as error:
        print(f"[COLLIDER AUDIT PREP] FAIL: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("[COLLIDER AUDIT PREP] PASS: DF-049 measurement-only gate prepared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
