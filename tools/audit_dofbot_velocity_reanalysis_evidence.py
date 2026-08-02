#!/usr/bin/env python3
"""Audit the tracked bindings for ignored DOFBOT velocity source payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CASE_SOURCE_KEYS = {
    "gravity_off_effort_100": "gravity_off_effort_100_json",
    "gravity_on_effort_100": "gravity_on_effort_100_json",
    "gravity_on_effort_250": "gravity_on_effort_250_json",
}
EXPECTED_REANALYSIS_CHECKS = {
    "gravity_off_effort_100_sha256_matches",
    "gravity_off_effort_100_size_matches",
    "gravity_on_effort_100_sha256_matches",
    "gravity_on_effort_100_size_matches",
    "gravity_on_effort_250_sha256_matches",
    "gravity_on_effort_250_size_matches",
    "source_matrix_was_complete",
    "gravity_on_cases_settle_by_position_difference",
    "gravity_off_record_is_right_censored_but_terminal_velocity_is_stable",
    "gravity_off_velocity_signals_are_consistent",
    "gravity_on_velocity_mismatch_is_reproduced",
    "gravity_on_tracking_error_remains_real",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_evidence_audit(
    *,
    config_path: Path,
    remote_result_path: Path,
    reanalysis_path: Path,
) -> dict[str, Any]:
    remote_result = _load_json(remote_result_path)
    reanalysis = _load_json(reanalysis_path)
    promoted_checks = reanalysis.get("checks", {})
    checks = {
        "analysis_config_sha256_matches": (
            reanalysis["analysis_config"]["sha256"] == _sha256(config_path)
        ),
        "remote_result_sha256_matches": (
            reanalysis["source_remote_result"]["sha256"]
            == _sha256(remote_result_path)
        ),
        "promoted_reanalysis_passed": reanalysis.get("reanalysis_passed") is True,
        "promoted_checks_complete": set(promoted_checks) == EXPECTED_REANALYSIS_CHECKS,
        "promoted_checks_all_passed": all(promoted_checks.values()),
        "gpu_was_not_started": reanalysis.get("gpu_started") is False,
        "isaac_was_not_started": reanalysis.get("isaac_started") is False,
        "viewer_was_not_started": reanalysis.get("viewer_started") is False,
        "pregrasp_was_not_authorized": reanalysis.get("pregrasp_authorized") is False,
        "contact_or_grasp_was_not_authorized": (
            reanalysis.get("contact_or_grasp_authorized") is False
        ),
    }
    for case_name, source_key in CASE_SOURCE_KEYS.items():
        promoted_source = reanalysis["cases"][case_name]["source"]
        upstream_source = remote_result["source_artifacts"][source_key]
        checks[f"{case_name}_sha256_binding_matches"] = (
            promoted_source["sha256"] == upstream_source["sha256"]
        )
        checks[f"{case_name}_byte_count_binding_matches"] = (
            promoted_source["bytes"] == upstream_source["bytes"]
        )

    return {
        "schema_version": 1,
        "experiment": "dofbot_actuator_velocity_evidence_audit",
        "checks": checks,
        "audit_passed": all(checks.values()),
        "raw_payloads_required": False,
        "gpu_started": False,
        "isaac_started": False,
        "viewer_started": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--remote-result", type=Path, required=True)
    parser.add_argument("--reanalysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_evidence_audit(
        config_path=args.config,
        remote_result_path=args.remote_result,
        reanalysis_path=args.reanalysis,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "[VELOCITY EVIDENCE AUDIT] "
        f"audit_passed={result['audit_passed']} output={args.output}"
    )
    if not result["audit_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
