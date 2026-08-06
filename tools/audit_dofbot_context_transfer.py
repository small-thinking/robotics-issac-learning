#!/usr/bin/env python3
"""Audit whether isolated DOFBOT evidence transfers to pre-grasp.

This module is intentionally GPU-free.  It compares the exact command history,
trajectory derivatives, scene scope, settling protocol, and runtime-source
provenance of the passing isolated calibration with the failing integrated
pre-grasp run.  The audit can prove that two protocols differ; it cannot claim
that either protocol passes Isaac/PhysX without new machine evidence.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .dofbot_actuator_calibration import (
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )
    from .dofbot_gravity_feed_forward import (
        load_accepted_gravity_feed_forward_runtime,
    )
    from .dofbot_pregrasp_pose import (
        cubic_smoothstep_motion_contract,
        load_pregrasp_pose_config,
    )
    from .dofbot_reaching import load_reaching_config
except ImportError:
    from dofbot_actuator_calibration import (
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )
    from dofbot_gravity_feed_forward import (
        load_accepted_gravity_feed_forward_runtime,
    )
    from dofbot_pregrasp_pose import (
        cubic_smoothstep_motion_contract,
        load_pregrasp_pose_config,
    )
    from dofbot_reaching import load_reaching_config


CURRENT_SHARED_RUNTIME_PATHS = (
    "tools/dofbot_actuator_calibration.py",
    "tools/dofbot_collider_audit.py",
    "tools/dofbot_contact_report.py",
    "tools/dofbot_control_api.py",
    "tools/dofbot_gravity_feed_forward.py",
    "tools/dofbot_gravity_feed_forward_runtime.py",
    "tools/dofbot_pregrasp_scene_cfg.py",
    "tools/dofbot_motion_plan.py",
    "tools/dofbot_reaching.py",
    "tools/dofbot_scene_decomposition.py",
    "tools/dofbot_scene_cfg.py",
    "tools/run_dofbot_actuator_calibration.py",
)
CURRENT_INTEGRATED_CONSUMER_PATHS = (
    *CURRENT_SHARED_RUNTIME_PATHS,
    "tools/run_dofbot_pregrasp.py",
)
EXPECTED_ISOLATED_POSE_NAMES = (
    "neutral_start",
    "mid_load",
    "pregrasp_candidate",
    "neutral_return",
)


class ContextTransferAuditError(ValueError):
    """The offline context-transfer evidence is malformed or incomplete."""


def _read_object(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ContextTransferAuditError(f"{path} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ContextTransferAuditError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _source_bundle(
    *,
    project_dir: Path,
    paths: tuple[str, ...],
) -> dict[str, Any]:
    files: dict[str, str] = {}
    for relative_path in paths:
        path = project_dir / relative_path
        if not path.is_file():
            raise ContextTransferAuditError(
                f"runtime source is missing: {relative_path}"
            )
        files[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    canonical = "".join(
        f"{path}\0{sha256}\n" for path, sha256 in sorted(files.items())
    ).encode()
    return {
        "algorithm": "sha256(path_nul_sha256_newline_sorted_v1)",
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "files": files,
    }


def _machine_source_bundle_bound(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "algorithm",
        "sha256",
        "files",
    }:
        return False
    if value.get("algorithm") != "sha256(path_nul_sha256_newline_sorted_v1)":
        return False
    files = value.get("files")
    if not isinstance(files, dict) or set(files) != set(
        CURRENT_SHARED_RUNTIME_PATHS
    ):
        return False
    if not all(
        isinstance(path, str)
        and isinstance(sha256, str)
        and len(sha256) == 64
        and all(character in "0123456789abcdef" for character in sha256)
        for path, sha256 in files.items()
    ):
        return False
    canonical = "".join(
        f"{path}\0{sha256}\n" for path, sha256 in sorted(files.items())
    ).encode()
    return value.get("sha256") == hashlib.sha256(canonical).hexdigest()


def _normalized_function_ast(path: Path, function_name: str) -> str:
    module = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        ),
        None,
    )
    if function is None:
        raise ContextTransferAuditError(
            f"{path} is missing function {function_name}"
        )
    function.name = "spawn_static_boxes"
    function.returns = None
    function.decorator_list = []
    for argument in (*function.args.posonlyargs, *function.args.args):
        argument.annotation = None
    if (
        function.body
        and isinstance(function.body[0], ast.Expr)
        and isinstance(function.body[0].value, ast.Constant)
        and isinstance(function.body[0].value.value, str)
    ):
        function.body.pop(0)
    return ast.dump(function, include_attributes=False)


def _pose_angles(
    config: Any,
    name: str,
) -> list[float]:
    for pose in config.poses:
        if pose.name == name:
            return [float(value) for value in pose.angles_deg]
    raise ContextTransferAuditError(f"isolated calibration is missing pose {name}")


def build_context_transfer_audit(
    *,
    project_dir: Path,
    calibration_config_path: Path,
    pregrasp_pose_config_path: Path,
    pregrasp_scene_config_path: Path,
    accepted_machine_result_path: Path,
    direct_machine_result_path: Path,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    calibration, calibration_sha256 = load_actuator_calibration_config(
        calibration_config_path
    )
    pose, pose_sha256 = load_pregrasp_pose_config(pregrasp_pose_config_path)
    scene, scene_sha256 = load_reaching_config(pregrasp_scene_config_path)
    actuator = load_accepted_gravity_feed_forward_runtime(
        calibration_config_path=calibration_config_path,
        machine_result_path=accepted_machine_result_path,
    )
    accepted_result, accepted_result_sha256 = _read_object(
        accepted_machine_result_path
    )
    direct_result, direct_result_sha256 = _read_object(
        direct_machine_result_path
    )

    pose_names = tuple(item.name for item in calibration.poses)
    if pose_names != EXPECTED_ISOLATED_POSE_NAMES:
        raise ContextTransferAuditError(
            "isolated calibration pose sequence is not the recorded four-pose probe"
        )
    candidate_index = pose_names.index("pregrasp_candidate")
    isolated_candidate_start = [
        float(value) for value in calibration.poses[candidate_index - 1].angles_deg
    ]
    isolated_candidate_goal = _pose_angles(calibration, "pregrasp_candidate")
    isolated_motion = cubic_smoothstep_motion_contract(
        start_angles_deg=isolated_candidate_start,
        goal_angles_deg=isolated_candidate_goal,
        duration_s=calibration.trajectory.duration_ms / 1000.0,
    )
    integrated_start = [90.0, 90.0, 90.0, 90.0]
    integrated_goal = [float(value) for value in pose.solver.preferred_angles_deg]
    integrated_motion = cubic_smoothstep_motion_contract(
        start_angles_deg=integrated_start,
        goal_angles_deg=integrated_goal,
        duration_s=actuator.trajectory_duration_ms / 1000.0,
    )
    calibration_extrema = calibration_trajectory_extrema(calibration)

    accepted_provenance = accepted_result.get("provenance")
    if not isinstance(accepted_provenance, dict):
        raise ContextTransferAuditError(
            "accepted machine result is missing provenance"
        )
    accepted_source_bundle = accepted_result.get("runtime_source_bundle")
    accepted_source_bundle_bound = _machine_source_bundle_bound(
        accepted_source_bundle
    )
    direct_conclusion = direct_result.get("conclusion")
    direct_machine = direct_result.get("machine")
    if not isinstance(direct_conclusion, dict) or not isinstance(
        direct_machine, dict
    ):
        raise ContextTransferAuditError(
            "direct-transition result is missing its machine conclusion"
        )

    same_candidate_start = isolated_candidate_start == integrated_start
    same_candidate_goal = isolated_candidate_goal == integrated_goal
    same_candidate_motion = isolated_motion == integrated_motion
    mismatches = {
        "candidate_start_angles": not same_candidate_start,
        "candidate_transition_delta": (
            isolated_motion["delta_angles_deg"]
            != integrated_motion["delta_angles_deg"]
        ),
        "candidate_peak_velocity": (
            isolated_motion["peak_velocity_deg_s"]
            != integrated_motion["peak_velocity_deg_s"]
        ),
        "candidate_peak_acceleration": (
            isolated_motion["peak_acceleration_deg_s2"]
            != integrated_motion["peak_acceleration_deg_s2"]
        ),
        "preceding_pose_history": True,
        "scene_boxes": True,
        "settling_and_observation_protocol": True,
        "machine_validated_runtime_source_bundle": (
            not accepted_source_bundle_bound
        ),
    }
    if _normalized_function_ast(
        project_dir / "tools/run_dofbot_pregrasp.py",
        "_spawn_scene_boxes",
    ) != _normalized_function_ast(
        project_dir / "tools/dofbot_pregrasp_scene_cfg.py",
        "spawn_static_reaching_boxes",
    ):
        raise ContextTransferAuditError(
            "isolated and integrated static-scene spawners differ"
        )
    analysis_checks = {
        "isolated_success_result_is_machine_passed": (
            accepted_result.get("matrix", {}).get("matrix_complete") is True
            and accepted_result.get("cases", {})
            .get("bounded_gravity_feed_forward", {})
            .get("tracking_gate_passed")
            is True
        ),
        "isolated_candidate_goal_matches_integrated_goal": same_candidate_goal,
        "isolated_candidate_starts_from_mid_load": (
            isolated_candidate_start == [90.0, 78.0, 78.0, 78.0]
        ),
        "isolated_candidate_transition_is_twelve_degrees": (
            max(abs(value) for value in isolated_motion["delta_angles_deg"])
            == 12.0
        ),
        "isolated_full_sequence_includes_twenty_four_degree_return": (
            calibration_extrema["maximum_transition_delta_deg"] == 24.0
        ),
        "integrated_direct_transition_is_twenty_four_degrees": (
            max(abs(value) for value in integrated_motion["delta_angles_deg"])
            == 24.0
        ),
        "protocol_mismatch_is_detected": any(mismatches.values()),
        "direct_transition_machine_result_failed": (
            direct_machine.get("machine_passed") is False
        ),
        "direct_transition_viewer_was_blocked": (
            direct_conclusion.get("viewer_authorized") is False
        ),
        "accepted_result_source_bundle_gap_is_explicit": (
            not accepted_source_bundle_bound
        ),
        "gpu_not_started_by_audit": True,
    }

    return {
        "schema_version": 1,
        "experiment": "dofbot_pregrasp_context_transfer_audit",
        "sources": {
            "isolated_calibration_config": {
                "path": calibration_config_path.relative_to(project_dir).as_posix(),
                "sha256": calibration_sha256,
            },
            "pregrasp_pose_config": {
                "path": pregrasp_pose_config_path.relative_to(project_dir).as_posix(),
                "sha256": pose_sha256,
            },
            "pregrasp_scene_config": {
                "path": pregrasp_scene_config_path.relative_to(project_dir).as_posix(),
                "sha256": scene_sha256,
            },
            "accepted_isolated_machine_result": {
                "path": accepted_machine_result_path.relative_to(
                    project_dir
                ).as_posix(),
                "sha256": accepted_result_sha256,
                "runtime_fix_commit": accepted_provenance.get(
                    "runtime_fix_commit"
                ),
            },
            "failed_direct_machine_result": {
                "path": direct_machine_result_path.relative_to(project_dir).as_posix(),
                "sha256": direct_result_sha256,
            },
        },
        "runtime_provenance": {
            "accepted_machine_result_contains_source_bundle": (
                accepted_source_bundle_bound
            ),
            "accepted_machine_result_source_bundle": accepted_source_bundle,
            "current_shared_runtime_bundle": _source_bundle(
                project_dir=project_dir,
                paths=CURRENT_SHARED_RUNTIME_PATHS,
            ),
            "current_integrated_consumer_bundle": _source_bundle(
                project_dir=project_dir,
                paths=CURRENT_INTEGRATED_CONSUMER_PATHS,
            ),
            "current_runtime_machine_regression_validated": False,
            "reason": (
                "DF-046 validates the prior source-bound runtime, but DF-047 "
                "adds scene-cell instrumentation to that runner and spawner. "
                "The new source bundle requires its own no-scene S0 sentinel."
            ),
        },
        "protocols": {
            "accepted_isolated_calibration": {
                "pose_sequence_angles_deg": [
                    [float(value) for value in item.angles_deg]
                    for item in calibration.poses
                ],
                "candidate_start_angles_deg": isolated_candidate_start,
                "candidate_goal_angles_deg": isolated_candidate_goal,
                "candidate_motion_contract": isolated_motion,
                "full_sequence_extrema": calibration_extrema,
                "table_or_cube_spawned": False,
                "settle_velocity_threshold_deg_s": (
                    calibration.trajectory.settle_velocity_threshold_deg_s
                ),
                "settle_hold_ms": calibration.trajectory.settle_hold_ms,
                "settle_timeout_ms": calibration.trajectory.settle_timeout_ms,
                "sample_every_physics_step": (
                    calibration.trajectory.sample_every_physics_step
                ),
            },
            "failed_integrated_direct_pregrasp": {
                "pose_sequence_angles_deg": [integrated_start, integrated_goal],
                "candidate_start_angles_deg": integrated_start,
                "candidate_goal_angles_deg": integrated_goal,
                "candidate_motion_contract": integrated_motion,
                "table_or_cube_spawned": True,
                "table_prim_path": scene.table.prim_path,
                "target_cube_prim_path": scene.target_cube.prim_path,
                "control_hz": pose.solver.control_hz,
                "maximum_steps": pose.solver.maximum_steps,
                "maximum_observation_horizon_s": (
                    pose.solver.maximum_steps / pose.solver.control_hz
                ),
                "sample_every_physics_step": False,
            },
        },
        "protocol_mismatches": mismatches,
        "analysis": {
            "checks": analysis_checks,
            "audit_complete": all(analysis_checks.values()),
            "df_035_equivalence_claim_valid": (
                same_candidate_start and same_candidate_motion
            ),
            "df_039_falsifies_direct_90_to_66_transition": True,
            "df_039_falsifies_safe_90_to_78_to_66_path": False,
            "accepted_isolated_result_transfers_to_current_runtime": False,
            "integrated_pregrasp_authorized": False,
            "viewer_authorized": False,
        },
        "next_machine_matrix": {
            "status": "completed_by_df_046_and_superseded_by_df_047",
            "next_discriminator": (
                "DF-047 adaptive table/cube/collision/near-far decomposition"
            ),
            "paid_run_requires_fresh_quote_and_explicit_approval": True,
            "viewer_blocked": True,
            "cells": [
                {
                    "id": "A",
                    "context": "current_shared_runtime_isolated_no_boxes",
                    "path_angles_deg": [
                        [90.0, 90.0, 90.0, 90.0],
                        [90.0, 78.0, 78.0, 78.0],
                        [90.0, 66.0, 66.0, 66.0],
                    ],
                    "role": "machine regression sentinel",
                    "fail_fast": True,
                },
                {
                    "id": "B",
                    "context": "current_shared_runtime_isolated_no_boxes",
                    "path_angles_deg": [
                        [90.0, 90.0, 90.0, 90.0],
                        [90.0, 66.0, 66.0, 66.0],
                    ],
                    "role": "path-history discriminator",
                    "requires": "A passes",
                },
                {
                    "id": "C",
                    "context": "current_shared_runtime_isolated_with_static_boxes",
                    "path_angles_deg": [
                        [90.0, 90.0, 90.0, 90.0],
                        [90.0, 78.0, 78.0, 78.0],
                        [90.0, 66.0, 66.0, 66.0],
                    ],
                    "role": "static-scene discriminator",
                    "requires": "A passes",
                },
                {
                    "id": "D",
                    "context": "integrated_pregrasp_with_static_boxes",
                    "path_angles_deg": [
                        [90.0, 90.0, 90.0, 90.0],
                        [90.0, 66.0, 66.0, 66.0],
                    ],
                    "role": "existing failed reference; do not rerun",
                    "evidence": direct_machine_result_path.relative_to(
                        project_dir
                    ).as_posix(),
                },
            ],
            "decision_rules": {
                "A_fails": (
                    "current shared runtime does not reproduce the accepted "
                    "isolated result; stop before B/C"
                ),
                "A_passes_B_fails": (
                    "direct transition or missing mid-load history is causal"
                ),
                "A_passes_C_fails": "static scene context is causal",
                "A_B_C_pass": (
                    "path and static boxes are insufficient separately; "
                    "isolate the remaining integrated-runner context"
                ),
            },
        },
        "scope": {
            "gpu_started": False,
            "isaac_started": False,
            "controller_changed": False,
            "machine_claim_added": False,
            "viewer_started": False,
            "contact_or_grasp_authorized": False,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--calibration-config",
        type=Path,
        default=Path(
            "configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json"
        ),
    )
    parser.add_argument(
        "--pregrasp-pose-config",
        type=Path,
        default=Path("configs/dofbot/pregrasp/goal5_angled_pregrasp.json"),
    )
    parser.add_argument(
        "--pregrasp-scene-config",
        type=Path,
        default=Path(
            "configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json"
        ),
    )
    parser.add_argument(
        "--accepted-machine-result",
        type=Path,
        default=Path(
            "artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json"
        ),
    )
    parser.add_argument(
        "--direct-machine-result",
        type=Path,
        default=Path(
            "artifacts/dofbot/pregrasp_single_boundary_discriminator_2026-08-01.json"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--expected",
        type=Path,
        default=None,
        help="Optional tracked JSON snapshot that must equal the generated audit.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    project_dir = args.project_dir.resolve()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else project_dir / path

    result = build_context_transfer_audit(
        project_dir=project_dir,
        calibration_config_path=resolve(args.calibration_config),
        pregrasp_pose_config_path=resolve(args.pregrasp_pose_config),
        pregrasp_scene_config_path=resolve(args.pregrasp_scene_config),
        accepted_machine_result_path=resolve(args.accepted_machine_result),
        direct_machine_result_path=resolve(args.direct_machine_result),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.expected is not None:
        expected, _ = _read_object(args.expected)
        if expected != result:
            raise SystemExit(
                "DOFBOT context-transfer snapshot is stale; regenerate it "
                "after reviewing the source/protocol change"
            )
    print(
        "[CONTEXT TRANSFER AUDIT] "
        f"audit_complete={result['analysis']['audit_complete']} "
        "integrated_pregrasp_authorized="
        f"{result['analysis']['integrated_pregrasp_authorized']} "
        f"output={args.output}",
        flush=True,
    )
    if not result["analysis"]["audit_complete"]:
        raise SystemExit("DOFBOT context-transfer audit is incomplete")


if __name__ == "__main__":
    main()
