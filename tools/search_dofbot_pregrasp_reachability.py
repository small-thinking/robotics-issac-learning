"""Run the GPU-free, evidence-calibrated DOFBOT pre-grasp reachability gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .dofbot_pregrasp_pose import load_pregrasp_pose_config
    from .dofbot_pregrasp_reachability import (
        fit_planar_model,
        load_reachability_config,
        search_planar_pose,
        terminal_pose_proximal_reach,
    )
except ImportError:
    from dofbot_pregrasp_pose import load_pregrasp_pose_config
    from dofbot_pregrasp_reachability import (
        fit_planar_model,
        load_reachability_config,
        search_planar_pose,
        terminal_pose_proximal_reach,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search all safe DOFBOT pitch-posture branches without Isaac."
    )
    parser.add_argument(
        "--reachability-config",
        type=Path,
        default=Path(
            "configs/dofbot/pregrasp/goal5_planar_reachability.json"
        ),
    )
    parser.add_argument(
        "--pose-config",
        type=Path,
        default=Path("configs/dofbot/pregrasp/goal5_pose_aware_pregrasp.json"),
    )
    parser.add_argument(
        "--failure-summary",
        type=Path,
        default=Path(
            "artifacts/dofbot/pregrasp_machine_failure_2026-07-29.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/dofbot-pregrasp-reachability.json"),
    )
    return parser.parse_args()


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def build_report(
    *,
    reachability_config_path: Path,
    pose_config_path: Path,
    failure_summary_path: Path,
) -> dict[str, Any]:
    config, config_sha256 = load_reachability_config(reachability_config_path)
    pose, pose_sha256 = load_pregrasp_pose_config(pose_config_path)
    failure, failure_sha256 = _read_json(failure_summary_path)
    model = fit_planar_model(config)
    proximal_reach = terminal_pose_proximal_reach(
        model,
        target_position_world_m=pose.target_pose.position_world_m,
        target_approach_axis_world_unit=pose.target_pose.approach_axis_world_unit,
    )

    physical = search_planar_pose(
        model,
        target_position_world_m=pose.target_pose.position_world_m,
        target_approach_axis_world_unit=pose.target_pose.approach_axis_world_unit,
        position_tolerance_m=pose.target_pose.position_tolerance_m,
        approach_tolerance_deg=pose.target_pose.approach_tolerance_deg,
        angle_min_deg=config.search.physical_angle_min_deg,
        angle_max_deg=config.search.physical_angle_max_deg,
        grid_step_deg=config.search.grid_step_deg,
        minimum_workspace_front_y_m=config.search.minimum_workspace_front_y_m,
        maximum_ranked_candidates=config.search.maximum_ranked_candidates,
    )
    command_margin = search_planar_pose(
        model,
        target_position_world_m=pose.target_pose.position_world_m,
        target_approach_axis_world_unit=pose.target_pose.approach_axis_world_unit,
        position_tolerance_m=pose.target_pose.position_tolerance_m,
        approach_tolerance_deg=pose.target_pose.approach_tolerance_deg,
        angle_min_deg=config.search.command_angle_min_deg,
        angle_max_deg=config.search.command_angle_max_deg,
        grid_step_deg=config.search.grid_step_deg,
        minimum_workspace_front_y_m=config.search.minimum_workspace_front_y_m,
        maximum_ranked_candidates=config.search.maximum_ranked_candidates,
    )
    failure_source_sha = failure.get("source_artifact_sha256")
    failure_commit = failure.get("git_commit")
    failure_passed = failure.get("machine", {}).get("passed")
    checks = {
        "failure_summary_sha256_matches": (
            failure_sha256 == config.source.failure_summary_sha256
        ),
        "full_machine_artifact_sha256_matches_summary": (
            failure_source_sha == config.source.full_machine_artifact_sha256
        ),
        "machine_git_commit_matches_summary": (
            failure_commit == config.source.machine_git_commit
        ),
        "source_machine_gate_failed": failure_passed is False,
        "calibration_sample_count_matches": (
            len(config.samples) == len(config.source.sample_step_indices)
        ),
        "calibration_position_residual_within_limit": (
            model.maximum_position_residual_m
            <= config.model.maximum_fit_position_error_m
        ),
        "calibration_approach_residual_within_limit": (
            model.maximum_approach_residual_deg
            <= config.model.maximum_fit_approach_error_deg
        ),
        "physical_envelope_exhaustively_searched": (
            physical["evaluated_count"]
            == (
                (config.search.physical_angle_max_deg
                 - config.search.physical_angle_min_deg)
                // config.search.grid_step_deg
                + 1
            )
            ** 3
        ),
        "command_margin_exhaustively_searched": (
            command_margin["evaluated_count"]
            == (
                (config.search.command_angle_max_deg
                 - config.search.command_angle_min_deg)
                // config.search.grid_step_deg
                + 1
            )
            ** 3
        ),
        "current_world_down_target_rejected_in_physical_envelope": (
            physical["minimum_approach_error_lower_bound_deg"]
            > pose.target_pose.approach_tolerance_deg
            and physical["target_feasible"] is False
        ),
        "current_world_down_target_rejected_in_command_margin": (
            command_margin["minimum_approach_error_lower_bound_deg"]
            > pose.target_pose.approach_tolerance_deg
            and command_margin["target_feasible"] is False
        ),
        "current_pose_rejected_by_unbounded_chain_geometry": (
            proximal_reach["reachable_without_angle_bounds"] is False
            and proximal_reach["maximum_reach_margin_m"] < 0.0
        ),
        "gpu_not_started": True,
        "isaac_not_started": True,
        "real_hardware_command_not_sent": True,
        "contact_or_grasp_not_authorized": True,
    }
    search_contract_passed = all(checks.values())
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "experiment": config.name,
        "sources": {
            "reachability_config": str(reachability_config_path),
            "reachability_config_sha256": config_sha256,
            "pose_config": str(pose_config_path),
            "pose_config_sha256": pose_sha256,
            "failure_summary": str(failure_summary_path),
            "failure_summary_sha256": failure_sha256,
            "full_machine_artifact_sha256": (
                config.source.full_machine_artifact_sha256
            ),
            "machine_git_commit": config.source.machine_git_commit,
            "sample_step_indices": list(config.source.sample_step_indices),
        },
        "scope": {
            "runtime": "local_pure_python",
            "model_limit": (
                "calibrated planar joint1=90 branch; not Isaac, dynamics, "
                "contact, or command-tracking proof"
            ),
            "policy_used": False,
            "gpu_started": False,
            "isaac_started": False,
            "real_hardware_command_sent": False,
            "contact_or_grasp_authorized": False,
        },
        "target_pose": {
            "position_world_m": list(pose.target_pose.position_world_m),
            "approach_axis_world_unit": list(
                pose.target_pose.approach_axis_world_unit
            ),
            "position_tolerance_m": pose.target_pose.position_tolerance_m,
            "approach_tolerance_deg": pose.target_pose.approach_tolerance_deg,
        },
        "fitted_model": model.to_dict(),
        "coupled_pose_geometry": proximal_reach,
        "searches": {
            "physical_envelope": physical,
            "command_margin": command_margin,
        },
        "acceptance": {
            "checks": checks,
            "search_contract_passed": search_contract_passed,
            "current_target_feasible": (
                physical["target_feasible"]
                and command_margin["target_feasible"]
            ),
            "revised_candidate_ready_for_remote_validation": False,
            "paid_gpu_run_authorized": False,
            "viewer_authorized": False,
            "contact_or_grasp_authorized": False,
        },
        "conclusion": (
            "The current world-down pose is unreachable under the "
            "evidence-calibrated planar model even before angle bounds, and "
            "its orientation is also outside the established physical and "
            "command envelopes. Revise the task pose or scene before another paid run."
        ),
    }


def main() -> None:
    args = _parse_args()
    report = build_report(
        reachability_config_path=args.reachability_config,
        pose_config_path=args.pose_config,
        failure_summary_path=args.failure_summary,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    checks = report["acceptance"]["checks"]
    passed = sum(value is True for value in checks.values())
    print(
        "[INFO] "
        f"checks={passed}/{len(checks)} "
        f"current_target_feasible={report['acceptance']['current_target_feasible']} "
        f"gpu_started={report['scope']['gpu_started']} "
        f"output={args.output}"
    )
    if report["acceptance"]["search_contract_passed"] is not True:
        raise SystemExit("reachability search contract failed")


if __name__ == "__main__":
    main()
