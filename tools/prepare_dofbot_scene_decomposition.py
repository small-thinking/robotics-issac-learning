#!/usr/bin/env python3
"""Prepare the GPU-free DOFBOT scene-decomposition audit and paid-run plan."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

try:
    from .audit_dofbot_context_transfer import (
        CURRENT_SHARED_RUNTIME_PATHS,
        _source_bundle,
    )
    from .dofbot_reaching import load_reaching_config
    from .dofbot_scene_decomposition import (
        SceneDecompositionError,
        axis_aligned_bounds,
        load_scene_decomposition_config,
        sha256_file,
    )
except ImportError:
    from audit_dofbot_context_transfer import (
        CURRENT_SHARED_RUNTIME_PATHS,
        _source_bundle,
    )
    from dofbot_reaching import load_reaching_config
    from dofbot_scene_decomposition import (
        SceneDecompositionError,
        axis_aligned_bounds,
        load_scene_decomposition_config,
        sha256_file,
    )


class SceneDecompositionPlanError(ValueError):
    """The offline audit cannot authorize the planned matrix."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SceneDecompositionPlanError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise SceneDecompositionPlanError(f"{path} must contain an object")
    return value


def _spawn_function_audit(path: Path) -> dict[str, Any]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "spawn_static_reaching_boxes"
        ),
        None,
    )
    if function is None:
        raise SceneDecompositionPlanError("historical static-box spawner is missing")
    dump = ast.dump(function, include_attributes=False)
    facts = {
        "fixed_table_then_cube_iteration": (
            "Attribute(value=Name(id='config'" in dump
            and "attr='table'" in dump
            and "attr='target_cube'" in dump
        ),
        "collision_properties_unconditionally_constructed": (
            "attr='CollisionPropertiesCfg'" in dump
        ),
        "source_config_collision_flag_not_read": "attr='collision_enabled'" not in dump,
    }
    if not all(facts.values()):
        raise SceneDecompositionPlanError(
            "historical spawner no longer matches the audited DF-046 boundary"
        )
    return facts


def _object_plan(scene: Any, cell: Any) -> list[dict[str, Any]]:
    result = []
    for name in cell.objects:
        box = scene.table if name == "table" else scene.target_cube
        center = tuple(
            box.center_world_m[index] + cell.translation_offset_world_m[index]
            for index in range(3)
        )
        result.append(
            {
                "name": name,
                "prim_path": box.prim_path,
                "source_center_world_m": list(box.center_world_m),
                "authored_center_world_m": list(center),
                "size_m": list(box.size_m),
                "collision_enabled": cell.collision_enabled,
                "rigid_body_authored": False,
                "expected_static": True,
                "axis_aligned_bounds": axis_aligned_bounds(center, box.size_m),
            }
        )
    return result


def build_scene_decomposition_plan(
    *,
    project_dir: Path,
    config_path: Path,
    context_matrix_path: Path,
    taskspace_path: Path,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    config_path = (
        config_path.resolve()
        if config_path.is_absolute()
        else (project_dir / config_path).resolve()
    )
    context_matrix_path = (
        context_matrix_path.resolve()
        if context_matrix_path.is_absolute()
        else (project_dir / context_matrix_path).resolve()
    )
    taskspace_path = (
        taskspace_path.resolve()
        if taskspace_path.is_absolute()
        else (project_dir / taskspace_path).resolve()
    )
    config, config_sha256 = load_scene_decomposition_config(config_path)
    source_scene_path = project_dir / config.source_scene_config
    calibration_path = project_dir / config.calibration_config
    scene, scene_sha256 = load_reaching_config(source_scene_path)
    context = _read_object(context_matrix_path)
    taskspace = _read_object(taskspace_path)
    matrix = context.get("matrix")
    cells = context.get("cells")
    if not isinstance(matrix, dict) or not isinstance(cells, dict):
        raise SceneDecompositionPlanError("DF-046 matrix evidence is incomplete")
    historical_c = cells.get("C")
    if not isinstance(historical_c, dict):
        raise SceneDecompositionPlanError("DF-046 cell C is missing")
    candidate = taskspace.get("selected_candidate")
    if not isinstance(candidate, dict) or candidate.get("passed") is not True:
        raise SceneDecompositionPlanError("task-space candidate is not accepted")
    source_bundle_paths = (
        *CURRENT_SHARED_RUNTIME_PATHS,
        "tools/prepare_dofbot_scene_decomposition.py",
        "scripts/isaac/run_dofbot_scene_decomposition_matrix.sh",
        "tools/verify_dofbot_scene_decomposition_case.py",
        "tools/summarize_dofbot_scene_decomposition_matrix.py",
    )
    cell_plans = [
        {
            **cell.to_dict(),
            "spawned_objects": _object_plan(scene, cell),
        }
        for cell in config.cells
    ]
    adaptive_paths = {
        "S0_fails": ["S0"],
        "table_branch": ["S0", "T1", "T0", "TF"],
        "cube_branch": ["S0", "T1", "Q1", "Q0", "QF"],
        "pair_branch": ["S0", "T1", "Q1", "P1", "P0", "PF"],
        "nonreproduction_branch": ["S0", "T1", "Q1", "P1"],
    }
    checks = {
        "df_046_matrix_complete": matrix.get("complete") is True,
        "df_046_static_scene_family_is_causal": (
            matrix.get("decision") == "static_scene_context_is_causal"
        ),
        "df_046_cell_c_failed_tracking": (
            historical_c.get("tracking_gate_passed") is False
        ),
        "df_046_cell_c_had_integrity": historical_c.get("integrity_passed") is True,
        "source_scene_keeps_table_and_cube_collision_enabled": (
            scene.table.collision_enabled and scene.target_cube.collision_enabled
        ),
        "candidate_pose_source_passed": candidate.get("passed") is True,
        "sentinel_runs_first": config.cells[0].id == "S0",
        "adaptive_paths_respect_cell_cap": all(
            len(path) <= config.maximum_executed_cells
            for path in adaptive_paths.values()
        ),
        "per_cell_timeouts_fit_matrix_deadline": (
            config.maximum_executed_cells * config.case_timeout_seconds
            <= config.matrix_deadline_seconds
        ),
        "viewer_remains_blocked": config.viewer_authorized is False,
        "gpu_not_started_by_preparation": True,
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise SceneDecompositionPlanError(
            "scene decomposition preparation failed: " + ", ".join(failed)
        )
    return {
        "schema_version": 1,
        "experiment": "dofbot_scene_decomposition_preflight",
        "ledger_discriminator": "DF-047",
        "sources": {
            "decomposition_config": {
                "path": config_path.relative_to(project_dir).as_posix(),
                "sha256": config_sha256,
            },
            "source_scene_config": {
                "path": config.source_scene_config,
                "sha256": scene_sha256,
            },
            "calibration_config": {
                "path": config.calibration_config,
                "sha256": sha256_file(calibration_path),
            },
            "df_046_matrix": {
                "path": context_matrix_path.relative_to(project_dir).as_posix(),
                "sha256": sha256_file(context_matrix_path),
                "historical_cell_c_artifact": historical_c.get("artifact"),
            },
            "taskspace_candidate": {
                "path": taskspace_path.relative_to(project_dir).as_posix(),
                "sha256": sha256_file(taskspace_path),
            },
            "runtime_source_bundle": _source_bundle(
                project_dir=project_dir,
                paths=source_bundle_paths,
            ),
        },
        "offline_scene_spawn_audit": {
            "historical_spawner": _spawn_function_audit(
                project_dir / "tools/dofbot_pregrasp_scene_cfg.py"
            ),
            "historical_df_046_changed_two_objects_together": True,
            "historical_df_046_collision_flag_was_not_independent": True,
            "candidate_terminal_midpoint_world_m": candidate["target_pose"][
                "origin_world_m"
            ],
            "candidate_terminal_table_clearance_m": candidate["margins"][
                "terminal_table_clearance_m"
            ],
            "candidate_terminal_cube_clearance_m": candidate["margins"][
                "terminal_cube_clearance_m"
            ],
            "inference_boundary": (
                "Analytical point/AABB clearance and zero monitored contact do not "
                "exclude a collision-registration, broadphase, indexing, or other "
                "scene-spawn side effect."
            ),
        },
        "cells": cell_plans,
        "adaptive_execution": {
            "paths": adaptive_paths,
            "maximum_executed_cells": config.maximum_executed_cells,
            "case_timeout_seconds": config.case_timeout_seconds,
            "matrix_deadline_seconds": config.matrix_deadline_seconds,
            "stop_rule": (
                "Stop after the first completed table, cube, or pair branch; never "
                "sweep cells outside the selected adaptive path."
            ),
        },
        "required_machine_evidence": {
            "source_and_config_hashes": True,
            "authored_prim_paths_and_collision_flags": True,
            "runtime_prim_type_collision_and_rigid_body_readback": True,
            "runtime_world_bounds_and_transforms": True,
            "articulation_joint_body_names_and_controlled_indices": True,
            "physics_view_shape_before_motion": True,
            "target_live_position_velocity_gravity_and_contact_telemetry": True,
            "terminal_body_to_spawned_aabb_clearance": True,
            "complete_contact_event_counts_and_actor_pairs": True,
        },
        "controls_held_fixed": {
            "candidate_path_angles_deg": [
                [90.0, 90.0, 90.0, 90.0],
                [90.0, 78.0, 78.0, 78.0],
                [90.0, 66.0, 66.0, 66.0],
            ],
            "actuator_case": config.case_name,
            "tracking_tolerance_deg": config.maximum_settled_tracking_error_deg,
            "contact_limit_n": config.maximum_contact_force_n,
            "trajectory_drive_and_feed_forward_unchanged": True,
        },
        "checks": checks,
        "preflight_passed": True,
        "authorization": {
            "paid_run": False,
            "viewer": False,
            "integrated_pregrasp": False,
            "contact_or_grasp": False,
            "reason": (
                "This artifact prepares DF-047 only. A fresh quote, Brev login, "
                "explicit approval, and a matching STOPPED instance are still required."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/dofbot/calibration/goal5_scene_decomposition.json"
        ),
    )
    parser.add_argument(
        "--context-matrix",
        type=Path,
        default=Path("artifacts/dofbot/context_transfer_matrix_contract.json"),
    )
    parser.add_argument(
        "--taskspace-candidate",
        type=Path,
        default=Path("artifacts/dofbot/pregrasp_taskspace_candidate.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_scene_decomposition_plan(
            project_dir=args.project_dir,
            config_path=args.config,
            context_matrix_path=args.context_matrix,
            taskspace_path=args.taskspace_candidate,
        )
    except (
        OSError,
        json.JSONDecodeError,
        SceneDecompositionError,
        SceneDecompositionPlanError,
    ) as error:
        print(f"[SCENE DECOMPOSITION] FAIL: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "[SCENE DECOMPOSITION] PASS: "
        f"cells={len(result['cells'])} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
