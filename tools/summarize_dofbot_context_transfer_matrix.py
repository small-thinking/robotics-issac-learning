#!/usr/bin/env python3
"""Summarize the fail-fast DOFBOT context-transfer machine matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .verify_dofbot_context_transfer_case import (
        ContextTransferCaseError,
        load_case_artifact,
        verify_context_transfer_case,
    )
except ImportError:
    from verify_dofbot_context_transfer_case import (
        ContextTransferCaseError,
        load_case_artifact,
        verify_context_transfer_case,
    )


class ContextTransferMatrixError(ValueError):
    """The machine matrix is incomplete or contains invalid evidence."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path, project_dir: Path) -> str:
    try:
        return path.relative_to(project_dir).as_posix()
    except ValueError:
        return str(path)


def _load_cell(
    *,
    input_dir: Path,
    cell_id: str,
    project_dir: Path,
    expected_git_commit: str,
    enforce_tracking_policy: bool,
) -> dict[str, Any]:
    path = input_dir / f"cell_{cell_id.lower()}.json"
    if not path.is_file():
        raise ContextTransferMatrixError(f"matrix cell {cell_id} is missing")
    try:
        result = verify_context_transfer_case(
            load_case_artifact(path),
            cell_id=cell_id,
            project_dir=project_dir,
            expected_git_commit=expected_git_commit,
            enforce_tracking_policy=enforce_tracking_policy,
        )
    except ContextTransferCaseError as error:
        raise ContextTransferMatrixError(
            f"matrix cell {cell_id} failed integrity: {error}"
        ) from error
    result["artifact"] = {
        "path": _display_path(path, project_dir),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }
    return result


def summarize_context_transfer_matrix(
    *,
    input_dir: Path,
    project_dir: Path,
    expected_git_commit: str,
    failed_direct_reference: Path,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    input_dir = input_dir.resolve()
    cell_a = _load_cell(
        input_dir=input_dir,
        cell_id="A",
        project_dir=project_dir,
        expected_git_commit=expected_git_commit,
        enforce_tracking_policy=False,
    )
    cells = {"A": cell_a}
    fail_fast = not cell_a["tracking_gate_passed"]
    if fail_fast:
        decision = "current_shared_runtime_regression_failed"
        causal_conclusion = (
            "The current shared runtime did not reproduce the accepted "
            "isolated split-path result. Stop before B/C and debug the "
            "runtime refactor against cell A only."
        )
    else:
        for cell_id in ("B", "C"):
            cells[cell_id] = _load_cell(
                input_dir=input_dir,
                cell_id=cell_id,
                project_dir=project_dir,
                expected_git_commit=expected_git_commit,
                enforce_tracking_policy=True,
            )
        b_pass = cells["B"]["tracking_gate_passed"]
        c_pass = cells["C"]["tracking_gate_passed"]
        if not b_pass and c_pass:
            decision = "direct_transition_or_missing_mid_load_history_is_causal"
            causal_conclusion = (
                "The split path passes with and without static boxes, while "
                "the direct path fails. Transition history is the isolated cause."
            )
        elif b_pass and not c_pass:
            decision = "static_scene_context_is_causal"
            causal_conclusion = (
                "The direct isolated path passes, while adding only static boxes "
                "breaks the split path. Static scene context is the isolated cause."
            )
        elif not b_pass and not c_pass:
            decision = "direct_transition_and_static_scene_are_independent_failures"
            causal_conclusion = (
                "Both single-factor cells fail after the regression sentinel passes; "
                "record both effects and do not combine them."
            )
        else:
            decision = "remaining_integrated_runner_context_requires_isolation"
            causal_conclusion = (
                "Neither the direct transition nor static boxes reproduces the "
                "failure in isolation. Isolate the remaining integrated-runner "
                "settling and observation protocol before Viewer."
            )

    reference_value = json.loads(failed_direct_reference.read_text(encoding="utf-8"))
    if not isinstance(reference_value, dict):
        raise ContextTransferMatrixError("failed direct reference must be an object")
    reference_machine = reference_value.get("machine")
    reference_conclusion = reference_value.get("conclusion")
    if (
        not isinstance(reference_machine, dict)
        or reference_machine.get("machine_passed") is not False
        or not isinstance(reference_conclusion, dict)
        or reference_conclusion.get("viewer_authorized") is not False
    ):
        raise ContextTransferMatrixError(
            "cell D reference must remain a failed, Viewer-blocked artifact"
        )
    return {
        "schema_version": 1,
        "experiment": "dofbot_context_transfer_machine_matrix",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": expected_git_commit,
        "cells": cells,
        "existing_failed_reference": {
            "id": "D",
            "path": _display_path(failed_direct_reference, project_dir),
            "sha256": _sha256(failed_direct_reference),
            "rerun": False,
        },
        "matrix": {
            "complete": True,
            "fail_fast_triggered": fail_fast,
            "executed_cells": list(cells),
            "decision": decision,
            "causal_conclusion": causal_conclusion,
        },
        "authorization": {
            "integrated_pregrasp": False,
            "viewer": False,
            "contact_or_grasp": False,
            "reason": (
                "This matrix isolates context transfer; it does not itself "
                "constitute a passing integrated pre-grasp run."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    parser.add_argument(
        "--failed-direct-reference",
        type=Path,
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = summarize_context_transfer_matrix(
            input_dir=args.input_dir,
            project_dir=args.project_dir,
            expected_git_commit=args.expected_git_commit,
            failed_direct_reference=args.failed_direct_reference,
        )
    except (ContextTransferMatrixError, OSError, json.JSONDecodeError) as error:
        print(f"[CONTEXT MATRIX] FAIL: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "[CONTEXT MATRIX] PASS: "
        f"decision={result['matrix']['decision']} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
