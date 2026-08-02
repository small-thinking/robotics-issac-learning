#!/usr/bin/env python3
"""Semantically verify one headless DOFBOT context-transfer matrix cell."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    from .audit_dofbot_context_transfer import (
        CURRENT_SHARED_RUNTIME_PATHS,
        _source_bundle,
    )
    from .dofbot_actuator_calibration import load_actuator_calibration_config
except ImportError:
    from audit_dofbot_context_transfer import (
        CURRENT_SHARED_RUNTIME_PATHS,
        _source_bundle,
    )
    from dofbot_actuator_calibration import load_actuator_calibration_config


CELL_SPECS = {
    "A": {
        "config": (
            "configs/dofbot/calibration/"
            "goal5_gravity_feed_forward_diagnostic.json"
        ),
        "scene": None,
        "require_tracking_pass": True,
    },
    "B": {
        "config": (
            "configs/dofbot/calibration/"
            "goal5_gravity_feed_forward_direct_diagnostic.json"
        ),
        "scene": None,
        "require_tracking_pass": False,
    },
    "C": {
        "config": (
            "configs/dofbot/calibration/"
            "goal5_gravity_feed_forward_diagnostic.json"
        ),
        "scene": (
            "configs/dofbot/reaching/"
            "goal5_angled_pregrasp_scene_candidate.json"
        ),
        "require_tracking_pass": False,
    },
}


class ContextTransferCaseError(ValueError):
    """One matrix cell is incomplete, stale, unsafe, or semantically invalid."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContextTransferCaseError(f"{label} must be an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_case_artifact(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContextTransferCaseError(f"cannot load {path}: {error}") from error
    return _object(value, "case artifact")


def verify_context_transfer_case(
    artifact: dict[str, Any],
    *,
    cell_id: str,
    project_dir: Path,
    expected_git_commit: str,
    enforce_tracking_policy: bool = True,
) -> dict[str, Any]:
    if cell_id not in CELL_SPECS:
        raise ContextTransferCaseError(f"unknown context-transfer cell: {cell_id}")
    spec = CELL_SPECS[cell_id]
    expected_require_pass = bool(spec["require_tracking_pass"])
    project_dir = project_dir.resolve()
    config_path = project_dir / str(spec["config"])
    config, config_sha256 = load_actuator_calibration_config(config_path)
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != (
        "dofbot_actuator_diagnostic_case"
    ):
        raise ContextTransferCaseError("unexpected case artifact schema")
    if artifact.get("git_commit") != expected_git_commit:
        raise ContextTransferCaseError("case artifact commit is stale")
    recorded_config = _object(
        artifact.get("calibration_config"), "calibration_config"
    )
    if recorded_config.get("sha256") != config_sha256:
        raise ContextTransferCaseError("case calibration config SHA is stale")

    expected_scene_path = spec["scene"]
    recorded_scene = artifact.get("context_scene_config")
    if expected_scene_path is None:
        if recorded_scene is not None:
            raise ContextTransferCaseError(
                "isolated cell unexpectedly spawned a task scene"
            )
    else:
        scene = _object(recorded_scene, "context_scene_config")
        scene_path = project_dir / str(expected_scene_path)
        if scene.get("sha256") != _sha256(scene_path):
            raise ContextTransferCaseError("context scene SHA is stale")

    if artifact.get("runtime_source_bundle") != _source_bundle(
        project_dir=project_dir,
        paths=CURRENT_SHARED_RUNTIME_PATHS,
    ):
        raise ContextTransferCaseError(
            "case runtime source bundle differs from the checked-out runtime"
        )
    case = _object(artifact.get("case"), "case")
    required_case = {
        "name": "bounded_gravity_feed_forward",
        "gravity_enabled": True,
        "effort_limit_sim": 100.0,
        "stiffness": 1048.0,
        "damping": 53.0,
        "solver_position_iteration_count": 8,
        "solver_velocity_iteration_count": 0,
        "enable_external_forces_every_iteration": True,
        "drive_type": "force",
        "gravity_compensation_feed_forward": True,
        "gravity_compensation_effort_limit": 5.2,
    }
    if case != required_case:
        raise ContextTransferCaseError("case actuator factors are confounded")

    measurement = _object(artifact.get("measurement"), "measurement")
    summaries = measurement.get("pose_summaries")
    samples = measurement.get("samples")
    if not isinstance(summaries, list) or len(summaries) != len(config.poses):
        raise ContextTransferCaseError("case pose summaries are incomplete")
    if not isinstance(samples, list) or not samples:
        raise ContextTransferCaseError("case physics-step samples are empty")
    for summary, expected_pose in zip(summaries, config.poses, strict=True):
        value = _object(summary, f"pose summary {expected_pose.name}")
        if value.get("name") != expected_pose.name or value.get(
            "command_angles_deg"
        ) != list(expected_pose.angles_deg):
            raise ContextTransferCaseError(
                "case pose sequence differs from its checked-in config"
            )
        tracking_error = value.get("maximum_tracking_error_deg")
        if (
            isinstance(tracking_error, bool)
            or not isinstance(tracking_error, (int, float))
            or not math.isfinite(float(tracking_error))
        ):
            raise ContextTransferCaseError("case tracking telemetry is invalid")

    evaluation = _object(artifact.get("evaluation"), "evaluation")
    checks = _object(evaluation.get("checks"), "evaluation.checks")
    if not checks or any(value is not True for value in checks.values()):
        raise ContextTransferCaseError("case diagnostic checks are incomplete")
    if evaluation.get("diagnostic_complete") is not True:
        raise ContextTransferCaseError("case diagnostic did not complete")
    tracking_passed = evaluation.get("tracking_gate_passed")
    if not isinstance(tracking_passed, bool):
        raise ContextTransferCaseError("case tracking verdict must be boolean")
    if enforce_tracking_policy and expected_require_pass and not tracking_passed:
        raise ContextTransferCaseError(
            "cell A failed the current-runtime regression sentinel"
        )

    scope = _object(artifact.get("scope"), "scope")
    expected_boxes = expected_scene_path is not None
    required_scope = {
        "table_or_cube_spawned": expected_boxes,
        "viewer_started": False,
        "camera_tensor_captured": False,
        "real_hardware_commanded": False,
        "policy_or_checkpoint_loaded": False,
        "contact_or_grasp_authorized": False,
    }
    if scope != required_scope:
        raise ContextTransferCaseError("case scope exceeds the matrix contract")

    maximum_tracking = evaluation.get("maximum_settled_tracking_error_deg")
    if (
        isinstance(maximum_tracking, bool)
        or not isinstance(maximum_tracking, (int, float))
        or not math.isfinite(float(maximum_tracking))
    ):
        raise ContextTransferCaseError("maximum tracking result is invalid")
    return {
        "cell_id": cell_id,
        "integrity_passed": True,
        "tracking_gate_passed": tracking_passed,
        "maximum_settled_tracking_error_deg": float(maximum_tracking),
        "calibration_config_sha256": config_sha256,
        "context_scene_spawned": expected_boxes,
        "runtime_source_bundle_sha256": artifact["runtime_source_bundle"][
            "sha256"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--cell", choices=sorted(CELL_SPECS), required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()
    try:
        result = verify_context_transfer_case(
            load_case_artifact(args.artifact),
            cell_id=args.cell,
            project_dir=args.project_dir,
            expected_git_commit=args.expected_git_commit,
        )
    except ContextTransferCaseError as error:
        print(f"[CONTEXT CELL {args.cell}] FAIL: {error}", file=sys.stderr)
        return 1
    print(
        f"[CONTEXT CELL {args.cell}] PASS: "
        f"tracking_gate_passed={result['tracking_gate_passed']} "
        "maximum_settled_tracking_error_deg="
        f"{result['maximum_settled_tracking_error_deg']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
