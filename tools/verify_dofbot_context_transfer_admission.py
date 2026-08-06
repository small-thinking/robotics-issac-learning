#!/usr/bin/env python3
"""Fail closed until current-runtime context transfer has machine evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .audit_dofbot_context_transfer import build_context_transfer_audit
except ImportError:
    from audit_dofbot_context_transfer import build_context_transfer_audit


class ContextTransferAdmissionError(ValueError):
    """The integrated pre-grasp admission evidence is stale or incomplete."""


def verify_context_transfer_admission(
    *,
    contract_path: Path,
    project_dir: Path,
) -> dict:
    project_dir = project_dir.resolve()
    try:
        recorded = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContextTransferAdmissionError(
            f"cannot load context-transfer contract: {error}"
        ) from error
    current = build_context_transfer_audit(
        project_dir=project_dir,
        calibration_config_path=(
            project_dir
            / "configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json"
        ),
        pregrasp_pose_config_path=(
            project_dir / "configs/dofbot/pregrasp/goal5_angled_pregrasp.json"
        ),
        pregrasp_scene_config_path=(
            project_dir
            / "configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json"
        ),
        accepted_machine_result_path=(
            project_dir
            / "artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json"
        ),
        direct_machine_result_path=(
            project_dir
            / "artifacts/dofbot/pregrasp_single_boundary_discriminator_2026-08-01.json"
        ),
    )
    if recorded != current:
        raise ContextTransferAdmissionError(
            "context-transfer contract is stale relative to the checked-out sources"
        )
    analysis = recorded.get("analysis")
    if not isinstance(analysis, dict) or analysis.get("audit_complete") is not True:
        raise ContextTransferAdmissionError("context-transfer audit is incomplete")
    if analysis.get("integrated_pregrasp_authorized") is not True:
        raise ContextTransferAdmissionError(
            "integrated pre-grasp is blocked: complete and promote the DF-047 "
            "adaptive scene-decomposition matrix, then define a separate "
            "integrated machine re-acceptance gate"
        )
    return recorded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        verify_context_transfer_admission(
            contract_path=args.contract,
            project_dir=args.project_dir,
        )
    except ContextTransferAdmissionError as error:
        print(f"[CONTEXT TRANSFER ADMISSION] FAIL: {error}", file=sys.stderr)
        return 1
    print("[CONTEXT TRANSFER ADMISSION] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
