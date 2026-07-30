"""Build the GPU-free DOFBOT angled pre-grasp candidate contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .dofbot_pregrasp_pose import load_pregrasp_pose_config
    from .dofbot_pregrasp_reachability import (
        fit_planar_model,
        load_reachability_config,
    )
    from .dofbot_pregrasp_taskspace import (
        load_taskspace_config,
        search_taskspace,
    )
    from .dofbot_reaching import load_reaching_config
except ImportError:
    from dofbot_pregrasp_pose import load_pregrasp_pose_config
    from dofbot_pregrasp_reachability import (
        fit_planar_model,
        load_reachability_config,
    )
    from dofbot_pregrasp_taskspace import (
        load_taskspace_config,
        search_taskspace,
    )
    from dofbot_reaching import load_reaching_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search safe joint poses, derive a task scene, and verify the "
            "checked-in DOFBOT angled pre-grasp candidate without Isaac."
        )
    )
    parser.add_argument(
        "--taskspace-config",
        type=Path,
        default=Path(
            "configs/dofbot/pregrasp/goal5_taskspace_search.json"
        ),
    )
    parser.add_argument(
        "--reachability-config",
        type=Path,
        default=Path(
            "configs/dofbot/pregrasp/goal5_planar_reachability.json"
        ),
    )
    parser.add_argument(
        "--rejected-reachability-artifact",
        type=Path,
        default=Path("artifacts/dofbot/pregrasp_reachability.json"),
    )
    parser.add_argument(
        "--motion-config-contract",
        type=Path,
        default=Path("artifacts/dofbot/motion_config_contract.json"),
    )
    parser.add_argument(
        "--asset-contract",
        type=Path,
        default=Path("artifacts/dofbot/asset_contract.json"),
    )
    parser.add_argument(
        "--candidate-scene-config",
        type=Path,
        default=Path(
            "configs/dofbot/reaching/"
            "goal5_angled_pregrasp_scene_candidate.json"
        ),
    )
    parser.add_argument(
        "--candidate-pose-config",
        type=Path,
        default=Path(
            "configs/dofbot/pregrasp/goal5_angled_pregrasp.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/dofbot-pregrasp-taskspace-candidate.json"),
    )
    return parser.parse_args()


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _close_sequence(
    left: Sequence[float],
    right: Sequence[float],
    *,
    tolerance: float = 1e-12,
) -> bool:
    return len(left) == len(right) and all(
        math.isclose(
            float(left_value),
            float(right_value),
            rel_tol=0.0,
            abs_tol=tolerance,
        )
        for left_value, right_value in zip(left, right, strict=True)
    )


def _motion_pitch_bounds(
    motion_contract: dict[str, Any],
) -> dict[str, list[float]]:
    steps = motion_contract.get("motion_config", {}).get("value", {}).get("steps")
    if not isinstance(steps, list) or not steps:
        return {}
    angles = [
        step.get("angles_deg")
        for step in steps
        if isinstance(step, dict)
    ]
    if (
        len(angles) != len(steps)
        or any(not isinstance(value, list) or len(value) != 4 for value in angles)
    ):
        return {}
    return {
        f"joint{index + 1}": [
            min(float(value[index]) for value in angles),
            max(float(value[index]) for value in angles),
        ]
        for index in range(1, 4)
    }


def build_report(
    *,
    taskspace_config_path: Path,
    reachability_config_path: Path,
    rejected_reachability_artifact_path: Path,
    motion_config_contract_path: Path,
    asset_contract_path: Path,
    candidate_scene_config_path: Path,
    candidate_pose_config_path: Path,
) -> dict[str, Any]:
    taskspace, taskspace_sha256 = load_taskspace_config(
        taskspace_config_path
    )
    reachability, reachability_sha256 = load_reachability_config(
        reachability_config_path
    )
    rejected, rejected_sha256 = _read_json(
        rejected_reachability_artifact_path
    )
    motion, motion_sha256 = _read_json(motion_config_contract_path)
    asset, asset_sha256 = _read_json(asset_contract_path)
    scene, scene_sha256 = load_reaching_config(candidate_scene_config_path)
    pose, pose_sha256 = load_pregrasp_pose_config(candidate_pose_config_path)
    model = fit_planar_model(reachability)
    searches = search_taskspace(model, taskspace)
    ranked = searches["candidate_search"]["ranked_candidates"]
    selected = ranked[0] if ranked else None
    selected_target = selected["target_pose"] if selected else {}
    selected_scene = selected["scene"] if selected else {}
    selected_margins = selected["margins"] if selected else {}
    pitch_bounds = _motion_pitch_bounds(motion)

    source_checks = {
        "asset_contract_sha256_matches": (
            asset_sha256 == taskspace.sources.asset_contract_sha256
        ),
        "motion_config_contract_sha256_matches": (
            motion_sha256
            == taskspace.sources.motion_config_contract_sha256
        ),
        "reachability_config_sha256_matches": (
            reachability_sha256
            == taskspace.sources.reachability_config_sha256
        ),
        "rejected_reachability_artifact_sha256_matches": (
            rejected_sha256
            == taskspace.sources.rejected_reachability_artifact_sha256
        ),
        "asset_machine_contract_passed": (
            asset.get("acceptance", {}).get("passed") is True
            and all(
                asset.get("acceptance", {})
                .get("checks", {})
                .values()
            )
        ),
        "world_down_rejection_contract_passed": (
            rejected.get("acceptance", {}).get("search_contract_passed")
            is True
            and rejected.get("acceptance", {}).get("current_target_feasible")
            is False
            and rejected.get("scope", {}).get("gpu_started") is False
            and rejected.get("scope", {}).get("isaac_started") is False
        ),
        "motion_machine_contract_passed": (
            motion.get("acceptance", {})
            .get("machine", {})
            .get("machine_passed")
            is True
            and all(
                motion.get("acceptance", {})
                .get("machine", {})
                .get("checks", {})
                .values()
            )
        ),
        "motion_contract_did_not_command_hardware_or_policy": (
            motion.get("scope", {}).get("real_hardware_commanded") is False
            and motion.get("scope", {}).get("policy_or_checkpoint_loaded")
            is False
        ),
        "pitch_command_range_proves_search_envelope": (
            set(pitch_bounds) == {"joint2", "joint3", "joint4"}
            and all(
                bounds[0]
                <= taskspace.search.validated_command_angle_min_deg
                and bounds[1]
                >= taskspace.search.validated_command_angle_max_deg
                for bounds in pitch_bounds.values()
            )
        ),
    }
    search_checks = {
        "physical_envelope_exhaustively_searched": (
            searches["physical_envelope"]["evaluated_count"] == 61**3
        ),
        "candidate_envelope_exhaustively_searched": (
            searches["candidate_search"]["evaluated_count"] == 53**3
        ),
        "requested_low_table_rejected": (
            searches["physical_envelope"]["requested_low_table_feasible"]
            is False
            and searches["physical_envelope"][
                "minimum_derived_table_top_m"
            ]
            > taskspace.search.requested_low_table_top_max_m
        ),
        "strict_candidate_available": (
            selected is not None
            and searches["candidate_search"]["passed_candidate_count"] >= 1
            and selected.get("passed") is True
        ),
    }
    candidate_checks = {
        "scene_hash_linked_from_pose": (
            pose.source_contracts.scene_config_sha256 == scene_sha256
        ),
        "asset_hash_linked_from_pose": (
            pose.source_contracts.asset_contract_sha256 == asset_sha256
        ),
        "terminal_finger_midpoint_is_scene_end_effector": (
            scene.end_effector_body_name == "terminal_finger_midpoint"
        ),
        "scene_approach_target_matches_selected_origin": (
            selected is not None
            and _close_sequence(
                scene.approach_target_world_m,
                selected_target["origin_world_m"],
            )
        ),
        "pose_target_matches_selected_origin": (
            selected is not None
            and _close_sequence(
                pose.target_pose.position_world_m,
                selected_target["origin_world_m"],
            )
        ),
        "pose_approach_axis_matches_selected_axis": (
            selected is not None
            and _close_sequence(
                pose.target_pose.approach_axis_world_unit,
                selected_target["approach_axis_world_unit"],
            )
        ),
        "pose_closing_axis_matches_selected_axis": (
            selected is not None
            and _close_sequence(
                pose.target_pose.closing_axis_world_unit,
                selected_target["closing_axis_world_unit"],
            )
        ),
        "preferred_angles_match_selected_candidate": (
            selected is not None
            and _close_sequence(
                pose.solver.preferred_angles_deg,
                selected["angles_deg"],
            )
        ),
        "scene_cube_matches_selected_candidate": (
            selected is not None
            and _close_sequence(
                scene.target_cube.center_world_m,
                selected_scene["cube_center_world_m"],
            )
        ),
        "scene_table_matches_selected_candidate": (
            selected is not None
            and _close_sequence(
                scene.table.center_world_m,
                selected_scene["table_center_world_m"],
            )
        ),
        "solver_margin_matches_search_envelope": (
            pose.solver.safe_angle_min_deg
            + pose.solver.command_limit_margin_deg
            == taskspace.search.search_angle_min_deg
            and pose.solver.safe_angle_max_deg
            - pose.solver.command_limit_margin_deg
            == taskspace.search.search_angle_max_deg
        ),
        "candidate_clearance_reserve_met": (
            selected is not None
            and selected_margins["minimum_clearance_reserve_m"]
            >= taskspace.search.minimum_model_residual_reserve_m
        ),
        "contact_remains_unauthorized": (
            pose.collision.contact_authorized is False
            and scene.target_cube.static is True
        ),
    }
    checks = source_checks | search_checks | candidate_checks | {
        "gpu_not_started": True,
        "isaac_not_started": True,
        "real_hardware_command_not_sent": True,
        "contact_or_grasp_not_authorized": True,
    }
    local_design_passed = all(checks.values())
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "experiment": taskspace.name,
        "sources": {
            "taskspace_config": str(taskspace_config_path),
            "taskspace_config_sha256": taskspace_sha256,
            "reachability_config": str(reachability_config_path),
            "reachability_config_sha256": reachability_sha256,
            "rejected_reachability_artifact": str(
                rejected_reachability_artifact_path
            ),
            "rejected_reachability_artifact_sha256": rejected_sha256,
            "motion_config_contract": str(motion_config_contract_path),
            "motion_config_contract_sha256": motion_sha256,
            "asset_contract": str(asset_contract_path),
            "asset_contract_sha256": asset_sha256,
            "candidate_scene_config": str(candidate_scene_config_path),
            "candidate_scene_config_sha256": scene_sha256,
            "candidate_pose_config": str(candidate_pose_config_path),
            "candidate_pose_config_sha256": pose_sha256,
        },
        "scope": {
            "runtime": "local_pure_python",
            "model_limit": (
                "calibrated planar joint1=90 branch; not Isaac, dynamics, "
                "self-collision, contact, or command-tracking proof"
            ),
            "policy_used": False,
            "gpu_started": False,
            "isaac_started": False,
            "real_hardware_command_sent": False,
            "contact_or_grasp_authorized": False,
        },
        "fitted_model": model.to_dict(),
        "validated_pitch_command_bounds_deg": pitch_bounds,
        "searches": searches,
        "selected_candidate": selected,
        "acceptance": {
            "checks": checks,
            "local_design_passed": local_design_passed,
            "revised_candidate_ready_for_isaac_machine_validation": (
                local_design_passed
            ),
            "paid_gpu_run_authorized": False,
            "viewer_authorized": False,
            "contact_or_grasp_authorized": False,
        },
        "conclusion": (
            "The requested <=0.12 m tabletop is outside the calibrated safe "
            "joint envelope for a meaningful front-side pre-grasp. The "
            "selected candidate raises the tabletop and uses an angled "
            "upper-side approach with residual-aware joint and clearance "
            "margins. It is ready for a future Isaac machine gate, but is "
            "not yet Isaac, collision, visual, contact, or grasp proof."
        ),
    }


def main() -> None:
    args = _parse_args()
    report = build_report(
        taskspace_config_path=args.taskspace_config,
        reachability_config_path=args.reachability_config,
        rejected_reachability_artifact_path=(
            args.rejected_reachability_artifact
        ),
        motion_config_contract_path=args.motion_config_contract,
        asset_contract_path=args.asset_contract,
        candidate_scene_config_path=args.candidate_scene_config,
        candidate_pose_config_path=args.candidate_pose_config,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    checks = report["acceptance"]["checks"]
    passed = sum(value is True for value in checks.values())
    candidate = report["selected_candidate"]
    print(
        "[INFO] "
        f"checks={passed}/{len(checks)} "
        f"angles_deg={candidate['angles_deg'] if candidate else None} "
        f"gpu_started={report['scope']['gpu_started']} "
        f"output={args.output}"
    )
    if report["acceptance"]["local_design_passed"] is not True:
        raise SystemExit("task-space candidate contract failed")


if __name__ == "__main__":
    main()
