#!/usr/bin/env python3
"""Semantically verify one headless DF-047 scene-decomposition cell."""

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
    from .dofbot_reaching import load_reaching_config
    from .dofbot_scene_decomposition import (
        SceneDecompositionCell,
        SceneDecompositionError,
        load_scene_decomposition_config,
    )
except ImportError:
    from audit_dofbot_context_transfer import (
        CURRENT_SHARED_RUNTIME_PATHS,
        _source_bundle,
    )
    from dofbot_actuator_calibration import load_actuator_calibration_config
    from dofbot_reaching import load_reaching_config
    from dofbot_scene_decomposition import (
        SceneDecompositionCell,
        SceneDecompositionError,
        load_scene_decomposition_config,
    )


class SceneDecompositionCaseError(ValueError):
    """One DF-047 cell is stale, incomplete, unsafe, or confounded."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SceneDecompositionCaseError(f"{label} must be an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SceneDecompositionCaseError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise SceneDecompositionCaseError(f"{label} must be finite")
    return result


def _close_vector(actual: Any, expected: list[float], label: str) -> None:
    if not isinstance(actual, list) or len(actual) != len(expected):
        raise SceneDecompositionCaseError(f"{label} has the wrong shape")
    if any(
        not math.isclose(_finite(value, label), target, abs_tol=1.0e-5)
        for value, target in zip(actual, expected, strict=True)
    ):
        raise SceneDecompositionCaseError(f"{label} differs from its authored value")


def load_scene_cell_artifact(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SceneDecompositionCaseError(f"cannot load {path}: {error}") from error
    return _object(value, "scene cell artifact")


def _expected_spawn_plan(scene: Any, cell: SceneDecompositionCell) -> list[dict[str, Any]]:
    result = []
    for name in cell.objects:
        box = scene.table if name == "table" else scene.target_cube
        center = [
            float(box.center_world_m[index])
            + float(cell.translation_offset_world_m[index])
            for index in range(3)
        ]
        result.append(
            {
                "name": name,
                "prim_path": box.prim_path,
                "center_world_m": center,
                "size_m": list(box.size_m),
                "collision_enabled": cell.collision_enabled,
                "rigid_body_authored": False,
            }
        )
    return result


def _verify_runtime_objects(
    readback: Any,
    expected: list[dict[str, Any]],
) -> None:
    if not isinstance(readback, list) or len(readback) != len(expected):
        raise SceneDecompositionCaseError("runtime scene readback has wrong object count")
    for actual_value, planned in zip(readback, expected, strict=True):
        actual = _object(actual_value, "runtime scene object")
        if actual.get("name") != planned["name"] or actual.get(
            "prim_path"
        ) != planned["prim_path"]:
            raise SceneDecompositionCaseError("runtime object identity is confounded")
        if actual.get("prim_present") is not True:
            raise SceneDecompositionCaseError("planned scene prim is absent")
        if actual.get("collision_enabled_readback") is not planned[
            "collision_enabled"
        ]:
            raise SceneDecompositionCaseError("collision API readback is confounded")
        if actual.get("static_readback") is not True:
            raise SceneDecompositionCaseError("scene object unexpectedly has a rigid body")
        _close_vector(
            actual.get("translation_world_m_readback"),
            planned["center_world_m"],
            "scene translation readback",
        )
        bounds = _object(
            actual.get("axis_aligned_world_bounds_readback"),
            "scene bounds readback",
        )
        expected_minimum = [
            planned["center_world_m"][index] - planned["size_m"][index] / 2.0
            for index in range(3)
        ]
        expected_maximum = [
            planned["center_world_m"][index] + planned["size_m"][index] / 2.0
            for index in range(3)
        ]
        _close_vector(bounds.get("minimum_world_m"), expected_minimum, "minimum bounds")
        _close_vector(bounds.get("maximum_world_m"), expected_maximum, "maximum bounds")


def verify_scene_decomposition_case(
    artifact: dict[str, Any],
    *,
    cell_id: str,
    project_dir: Path,
    config_path: Path,
    expected_git_commit: str,
    enforce_sentinel: bool = True,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    config, config_sha256 = load_scene_decomposition_config(config_path)
    cell = config.cell(cell_id)
    calibration_path = project_dir / config.calibration_config
    calibration, calibration_sha256 = load_actuator_calibration_config(calibration_path)
    scene_path = project_dir / config.source_scene_config
    scene, scene_sha256 = load_reaching_config(scene_path)
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != (
        "dofbot_actuator_diagnostic_case"
    ):
        raise SceneDecompositionCaseError("unexpected actuator artifact schema")
    if artifact.get("git_commit") != expected_git_commit:
        raise SceneDecompositionCaseError("scene cell commit is stale")
    if artifact.get("runtime_source_bundle") != _source_bundle(
        project_dir=project_dir,
        paths=CURRENT_SHARED_RUNTIME_PATHS,
    ):
        raise SceneDecompositionCaseError("runtime source bundle is stale")
    if _object(artifact.get("calibration_config"), "calibration config").get(
        "sha256"
    ) != calibration_sha256:
        raise SceneDecompositionCaseError("calibration config SHA is stale")
    recorded_scene = _object(artifact.get("context_scene_config"), "scene config")
    if recorded_scene.get("sha256") != scene_sha256:
        raise SceneDecompositionCaseError("source scene SHA is stale")
    decomposition = _object(artifact.get("scene_decomposition"), "scene decomposition")
    if decomposition.get("config_sha256") != config_sha256:
        raise SceneDecompositionCaseError("decomposition config SHA is stale")
    if decomposition.get("cell") != cell.to_dict():
        raise SceneDecompositionCaseError("recorded scene cell is confounded")
    expected_spawn = _expected_spawn_plan(scene, cell)
    if decomposition.get("spawn_plan") != expected_spawn:
        raise SceneDecompositionCaseError("spawn plan differs from the selected cell")
    _verify_runtime_objects(decomposition.get("runtime_readback"), expected_spawn)
    clearance = _object(decomposition.get("clearance"), "clearance")
    if clearance.get("body_center_proxy_is_not_mesh_clearance") is not True:
        raise SceneDecompositionCaseError("clearance inference boundary is missing")
    clearance_objects = _object(clearance.get("objects"), "clearance objects")
    if set(clearance_objects) != set(cell.objects):
        raise SceneDecompositionCaseError("clearance object set is incomplete")
    for value in clearance_objects.values():
        item = _object(value, "clearance object")
        distance = _finite(
            item.get("minimum_terminal_body_center_aabb_distance_m"),
            "minimum terminal-body clearance",
        )
        if distance < 0.0 or item.get("evaluated_body_samples", 0) <= 0:
            raise SceneDecompositionCaseError("clearance evidence is invalid")

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
    if artifact.get("case") != required_case:
        raise SceneDecompositionCaseError("actuator factors changed")
    measurement = _object(artifact.get("measurement"), "measurement")
    summaries = measurement.get("pose_summaries")
    samples = measurement.get("samples")
    if not isinstance(summaries, list) or len(summaries) != len(calibration.poses):
        raise SceneDecompositionCaseError("pose summaries are incomplete")
    if not isinstance(samples, list) or not samples:
        raise SceneDecompositionCaseError("physics-step samples are missing")
    for summary_value, pose in zip(summaries, calibration.poses, strict=True):
        summary = _object(summary_value, "pose summary")
        if summary.get("name") != pose.name or summary.get(
            "command_angles_deg"
        ) != list(pose.angles_deg):
            raise SceneDecompositionCaseError("pose path changed")
    evaluation = _object(artifact.get("evaluation"), "evaluation")
    checks = _object(evaluation.get("checks"), "evaluation checks")
    if not checks or any(value is not True for value in checks.values()):
        raise SceneDecompositionCaseError("diagnostic checks are incomplete")
    if evaluation.get("diagnostic_complete") is not True:
        raise SceneDecompositionCaseError("diagnostic did not complete")
    tracking_passed = evaluation.get("tracking_gate_passed")
    if not isinstance(tracking_passed, bool):
        raise SceneDecompositionCaseError("tracking verdict is not boolean")
    if enforce_sentinel and cell_id == "S0" and not tracking_passed:
        raise SceneDecompositionCaseError("S0 current-source sentinel failed")
    maximum_tracking = _finite(
        evaluation.get("maximum_settled_tracking_error_deg"),
        "maximum tracking error",
    )
    if tracking_passed != (
        maximum_tracking <= config.maximum_settled_tracking_error_deg
    ):
        raise SceneDecompositionCaseError("tracking verdict and threshold disagree")

    physics = _object(artifact.get("physics_snapshot"), "physics snapshot")
    if len(physics.get("joint_names", [])) != 11 or len(physics.get("body_names", [])) != 12:
        raise SceneDecompositionCaseError("articulation shape changed")
    if physics.get("controlled_joint_ids") != [0, 1, 2, 3]:
        raise SceneDecompositionCaseError("controlled DOF indexing changed")
    view_shape = _object(physics.get("root_physx_view_shape"), "PhysX view shape")
    if not view_shape or view_shape.get("count") not in (1, 1.0):
        raise SceneDecompositionCaseError("articulation view count is unexpected")
    contact_events = _object(
        _object(artifact.get("telemetry"), "telemetry").get("contact_events"),
        "contact events",
    )
    if not isinstance(contact_events.get("contact_header_count"), int) or not isinstance(
        contact_events.get("monitored_actor_pairs"), list
    ):
        raise SceneDecompositionCaseError("contact event evidence is incomplete")
    required_scope = {
        "table_or_cube_spawned": bool(cell.objects),
        "viewer_started": False,
        "camera_tensor_captured": False,
        "real_hardware_commanded": False,
        "policy_or_checkpoint_loaded": False,
        "contact_or_grasp_authorized": False,
    }
    if artifact.get("scope") != required_scope:
        raise SceneDecompositionCaseError("cell scope exceeds DF-047")
    return {
        "cell_id": cell_id,
        "integrity_passed": True,
        "tracking_gate_passed": tracking_passed,
        "maximum_settled_tracking_error_deg": maximum_tracking,
        "objects": list(cell.objects),
        "collision_enabled": cell.collision_enabled,
        "translation_offset_world_m": list(cell.translation_offset_world_m),
        "runtime_source_bundle_sha256": artifact["runtime_source_bundle"]["sha256"],
        "config_sha256": config_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    parser.add_argument("--allow-sentinel-failure", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_scene_decomposition_case(
            load_scene_cell_artifact(args.artifact),
            cell_id=args.cell,
            project_dir=args.project_dir,
            config_path=args.config,
            expected_git_commit=args.expected_git_commit,
            enforce_sentinel=not args.allow_sentinel_failure,
        )
    except (SceneDecompositionCaseError, SceneDecompositionError) as error:
        print(f"[SCENE CELL {args.cell}] FAIL: {error}", file=sys.stderr)
        return 1
    print(
        f"[SCENE CELL {args.cell}] PASS: integrity_passed=true "
        f"tracking_gate_passed={str(result['tracking_gate_passed']).lower()} "
        "maximum_settled_tracking_error_deg="
        f"{result['maximum_settled_tracking_error_deg']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
