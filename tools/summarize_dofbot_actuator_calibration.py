"""Combine isolated DOFBOT actuator cases into one diagnostic decision."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .dofbot_actuator_calibration import (
        REQUIRED_CASE_NAMES,
        classify_calibration_matrix,
        load_actuator_calibration_config,
    )
except ImportError:
    from dofbot_actuator_calibration import (
        REQUIRED_CASE_NAMES,
        classify_calibration_matrix,
        load_actuator_calibration_config,
    )


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def build_summary(
    *,
    config_path: Path,
    input_dir: Path,
    git_commit: str | None,
) -> dict[str, Any]:
    config, config_sha256 = load_actuator_calibration_config(config_path)
    artifacts: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    evaluations: dict[str, dict[str, Any]] = {}
    for case_name in REQUIRED_CASE_NAMES:
        path = input_dir / f"{case_name}.json"
        present = path.is_file()
        checks[f"{case_name}_artifact_present"] = present
        if not present:
            continue
        artifact = _load_object(path)
        artifacts[case_name] = artifact
        checks[f"{case_name}_schema_matches"] = (
            artifact.get("experiment") == "dofbot_actuator_diagnostic_case"
            and artifact.get("case", {}).get("name") == case_name
        )
        checks[f"{case_name}_config_sha_matches"] = (
            artifact.get("calibration_config", {}).get("sha256")
            == config_sha256
        )
        checks[f"{case_name}_git_commit_matches"] = (
            git_commit is not None
            and artifact.get("git_commit") == git_commit
        )
        evaluation = artifact.get("evaluation")
        checks[f"{case_name}_evaluation_present"] = isinstance(evaluation, dict)
        if isinstance(evaluation, dict):
            evaluations[case_name] = evaluation

    decision = classify_calibration_matrix(config, evaluations)
    matrix_complete = (
        set(evaluations) == set(REQUIRED_CASE_NAMES)
        and all(checks.values())
    )
    return {
        "schema_version": 1,
        "experiment": "dofbot_actuator_diagnostic_matrix",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "calibration_config": {
            "path": str(config_path),
            "sha256": config_sha256,
            "value": config.to_dict(),
        },
        "case_artifacts": {
            name: {
                "path": str(input_dir / f"{name}.json"),
                "diagnostic_complete": bool(
                    artifact.get("evaluation", {}).get(
                        "diagnostic_complete"
                    )
                ),
                "tracking_gate_passed": bool(
                    artifact.get("evaluation", {}).get(
                        "tracking_gate_passed"
                    )
                ),
            }
            for name, artifact in artifacts.items()
        },
        "checks": checks,
        "matrix_complete": matrix_complete,
        "decision": decision,
        "pregrasp_authorized": False,
        "viewer_authorized": False,
        "contact_or_grasp_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-commit", default=None)
    args = parser.parse_args()
    result = build_summary(
        config_path=args.config,
        input_dir=args.input_dir,
        git_commit=args.git_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "[ACTUATOR MATRIX] "
        f"matrix_complete={result['matrix_complete']} "
        f"decision={result['decision']['decision']} "
        f"output={args.output}"
    )
    if not result["matrix_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
