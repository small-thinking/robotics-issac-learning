#!/usr/bin/env python3
"""Audit tracked bindings for ignored DOFBOT residual-force source payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

TRACKED_SOURCES = {
    "drive_model_result": "drive_result",
    "actuator_result": "actuator_result",
    "asset_drive_audit": "asset_audit",
}
RAW_SOURCE_KEYS = {
    "force_damping_53_raw": "force_damping_53_json",
    "force_authored_tuning_raw": "force_authored_tuning_json",
}
EXPECTED_AUDIT_CHECKS = {
    "reviewed_drive_matrix_complete",
    "reviewed_drive_matrix_selects_no_passing_case",
    "raw_force_100_source_identity_matches",
    "raw_force_5_2_source_identity_matches",
    "physics_timestep_is_60_hz",
    "runtime_max_force_readback_changed",
    "all_selected_physical_samples_identical",
    "all_pose_summaries_identical",
    "gravity_off_tracking_passes",
    "gravity_on_tracking_fails",
    "best_force_tracking_still_fails",
    "target_buffer_matches",
    "all_controlled_joints_share_axis_and_chain",
    "viewer_pregrasp_contact_and_hardware_blocked",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def build_evidence_audit(
    *,
    drive_result_path: Path,
    actuator_result_path: Path,
    asset_audit_path: Path,
    residual_audit_path: Path,
) -> dict[str, Any]:
    paths = {
        "drive_result": drive_result_path,
        "actuator_result": actuator_result_path,
        "asset_audit": asset_audit_path,
    }
    drive_result = _load_json(drive_result_path)
    residual_audit = _load_json(residual_audit_path)
    promoted_checks = residual_audit.get("checks", {})
    checks = {
        "promoted_checks_complete": set(promoted_checks) == EXPECTED_AUDIT_CHECKS,
        "promoted_checks_all_passed": all(promoted_checks.values()),
        "promoted_audit_passed": residual_audit.get("audit_passed") is True,
        "paid_gpu_was_not_authorized": (
            residual_audit.get("paid_gpu_run_authorized") is False
        ),
        "pregrasp_was_not_authorized": residual_audit.get("pregrasp_authorized") is False,
        "viewer_was_not_authorized": residual_audit.get("viewer_authorized") is False,
        "contact_or_grasp_was_not_authorized": (
            residual_audit.get("contact_or_grasp_authorized") is False
        ),
    }
    for evidence_key, path_key in TRACKED_SOURCES.items():
        expected = residual_audit["source_evidence"][evidence_key]
        actual = _identity(paths[path_key])
        checks[f"{evidence_key}_sha256_matches"] = actual["sha256"] == expected["sha256"]
        checks[f"{evidence_key}_byte_count_matches"] = actual["bytes"] == expected["bytes"]

    for evidence_key, source_key in RAW_SOURCE_KEYS.items():
        promoted = residual_audit["source_evidence"][evidence_key]
        upstream = drive_result["source_artifacts"][source_key]
        checks[f"{evidence_key}_sha256_binding_matches"] = (
            promoted["sha256"] == upstream["sha256"]
        )
        checks[f"{evidence_key}_byte_count_binding_matches"] = (
            promoted["bytes"] == upstream["bytes"]
        )

    return {
        "schema_version": 1,
        "experiment": "dofbot_residual_force_evidence_audit",
        "checks": checks,
        "audit_passed": all(checks.values()),
        "raw_payloads_required": False,
        "gpu_started": False,
        "isaac_started": False,
        "viewer_started": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drive-result", type=Path, required=True)
    parser.add_argument("--actuator-result", type=Path, required=True)
    parser.add_argument("--asset-audit", type=Path, required=True)
    parser.add_argument("--residual-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_evidence_audit(
        drive_result_path=args.drive_result,
        actuator_result_path=args.actuator_result,
        asset_audit_path=args.asset_audit,
        residual_audit_path=args.residual_audit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "[RESIDUAL FORCE EVIDENCE AUDIT] "
        f"audit_passed={result['audit_passed']} output={args.output}"
    )
    if not result["audit_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
