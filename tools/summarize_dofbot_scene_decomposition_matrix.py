#!/usr/bin/env python3
"""Validate and summarize the adaptive DF-047 static-scene matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .dofbot_scene_decomposition import (
        SceneDecompositionError,
        classify_scene_decomposition_results,
        load_scene_decomposition_config,
        next_scene_decomposition_cell,
    )
    from .verify_dofbot_scene_decomposition_case import (
        SceneDecompositionCaseError,
        load_scene_cell_artifact,
        verify_scene_decomposition_case,
    )
except ImportError:
    from dofbot_scene_decomposition import (
        SceneDecompositionError,
        classify_scene_decomposition_results,
        load_scene_decomposition_config,
        next_scene_decomposition_cell,
    )
    from verify_dofbot_scene_decomposition_case import (
        SceneDecompositionCaseError,
        load_scene_cell_artifact,
        verify_scene_decomposition_case,
    )


class SceneDecompositionMatrixError(ValueError):
    """The adaptive DF-047 matrix is incomplete or invalid."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_scene_decomposition_matrix(
    *,
    input_dir: Path,
    project_dir: Path,
    config_path: Path,
    expected_git_commit: str,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    config, config_sha256 = load_scene_decomposition_config(config_path)
    results: dict[str, bool] = {}
    cells: dict[str, Any] = {}
    while True:
        cell_id = next_scene_decomposition_cell(results)
        if cell_id is None:
            break
        path = input_dir / f"cell_{cell_id.lower()}.json"
        if not path.is_file():
            raise SceneDecompositionMatrixError(
                f"adaptive matrix requires cell {cell_id} next"
            )
        try:
            summary = verify_scene_decomposition_case(
                load_scene_cell_artifact(path),
                cell_id=cell_id,
                project_dir=project_dir,
                config_path=config_path,
                expected_git_commit=expected_git_commit,
                enforce_sentinel=False,
            )
        except SceneDecompositionCaseError as error:
            raise SceneDecompositionMatrixError(
                f"cell {cell_id} failed integrity: {error}"
            ) from error
        summary["artifact"] = {
            "path": path.relative_to(project_dir).as_posix()
            if path.is_relative_to(project_dir)
            else str(path),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        cells[cell_id] = summary
        results[cell_id] = bool(summary["tracking_gate_passed"])
    extra = sorted(
        path.stem.removeprefix("cell_").upper()
        for path in input_dir.glob("cell_*.json")
        if path.stem.removeprefix("cell_").upper() not in cells
    )
    if extra:
        raise SceneDecompositionMatrixError(
            f"matrix contains cells outside the adaptive branch: {extra}"
        )
    decision = classify_scene_decomposition_results(results)
    if decision == "matrix_incomplete":
        raise SceneDecompositionMatrixError("adaptive matrix is incomplete")
    return {
        "schema_version": 1,
        "experiment": "dofbot_scene_decomposition_machine_matrix",
        "ledger_discriminator": "DF-047",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": expected_git_commit,
        "config": {
            "path": config_path.relative_to(project_dir).as_posix(),
            "sha256": config_sha256,
        },
        "cells": cells,
        "matrix": {
            "complete": True,
            "executed_cells": list(cells),
            "executed_cell_count": len(cells),
            "maximum_executed_cells": config.maximum_executed_cells,
            "decision": decision,
            "s0_regression_sentinel_passed": results.get("S0") is True,
        },
        "authorization": {
            "integrated_pregrasp": False,
            "viewer": False,
            "contact_or_grasp": False,
            "reason": (
                "DF-047 identifies a static-scene mechanism layer; it does not "
                "constitute a passing integrated pre-grasp machine gate."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = summarize_scene_decomposition_matrix(
            input_dir=args.input_dir,
            project_dir=args.project_dir,
            config_path=args.config,
            expected_git_commit=args.expected_git_commit,
        )
    except (
        OSError,
        json.JSONDecodeError,
        SceneDecompositionError,
        SceneDecompositionCaseError,
        SceneDecompositionMatrixError,
    ) as error:
        print(f"[SCENE MATRIX] FAIL: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[SCENE MATRIX] PASS: decision={result['matrix']['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
