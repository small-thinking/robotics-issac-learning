"""Build the deterministic, GPU-free DOFBOT solver/drive diagnostic plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .dofbot_actuator_calibration import (
        SOLVER_DRIVE_CASE_NAMES,
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )
except ImportError:
    from dofbot_actuator_calibration import (
        SOLVER_DRIVE_CASE_NAMES,
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _changed_fields(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    ignored = {"name"}
    return sorted(
        key
        for key in set(previous) | set(current)
        if key not in ignored and previous.get(key) != current.get(key)
    )


def build_solver_drive_preview(
    *,
    config_path: Path,
    remote_result_path: Path,
) -> dict[str, Any]:
    config, config_sha256 = load_actuator_calibration_config(config_path)
    if config.name != "goal5_solver_drive_diagnostic":
        raise ValueError("config must select goal5_solver_drive_diagnostic")
    remote_result, remote_result_sha256 = _load_json(remote_result_path)
    comparisons = remote_result["comparisons"]
    cases = [case.to_dict() for case in config.cases]
    staged_changes = [
        {
            "from": previous["name"],
            "to": current["name"],
            "changed_fields": _changed_fields(previous, current),
        }
        for previous, current in zip(cases, cases[1:], strict=False)
    ]
    checks = {
        "source_matrix_complete": bool(remote_result["matrix"]["matrix_complete"]),
        "source_gravity_off_resolved_tracking": bool(comparisons["gravity_off_resolves_tracking"]),
        "source_effort_250_changed_force_limit": bool(
            comparisons["effort_250_changes_configured_and_physx_max_force"]
        ),
        "source_effort_250_did_not_change_sequence": not bool(
            comparisons["effort_250_changes_observed_or_control_sequence"]
        ),
        "source_velocity_warning_recorded": ("noisy velocities" in comparisons["runtime_warning"]),
        "case_order_locked": config.case_names == SOLVER_DRIVE_CASE_NAMES,
        "every_case_keeps_gravity_on": all(case.gravity_enabled for case in config.cases),
        "every_case_keeps_effort_100": all(case.effort_limit_sim == 100.0 for case in config.cases),
        "every_case_keeps_stiffness_10000": all(case.stiffness == 10000.0 for case in config.cases),
        "every_case_keeps_solver_position_iterations_8": all(
            case.solver_position_iteration_count == 8 for case in config.cases
        ),
        "each_stage_changes_exactly_one_field": all(
            len(stage["changed_fields"]) == 1 for stage in staged_changes
        ),
        "position_velocity_is_windowed": (config.trajectory.position_velocity_window_ms == 100),
        "velocity_mismatch_gate_is_bounded": (
            config.trajectory.maximum_velocity_signal_mismatch_deg_s == 1.0
        ),
        "pregrasp_viewer_contact_and_hardware_blocked": True,
    }
    return {
        "schema_version": 1,
        "experiment": "dofbot_solver_drive_diagnostic_plan",
        "calibration_config": {
            "path": str(config_path),
            "sha256": config_sha256,
            "value": config.to_dict(),
        },
        "source_remote_result": {
            "path": str(remote_result_path),
            "sha256": remote_result_sha256,
            "machine_commit": remote_result["machine_commit"],
            "matrix_decision": remote_result["matrix"]["decision"],
        },
        "hypotheses": [
            {
                "case": "external_forces_each_iteration",
                "question": (
                    "Does applying external forces on every TGS position "
                    "iteration repair raw velocity telemetry or tracking?"
                ),
            },
            {
                "case": "velocity_iterations_2",
                "question": (
                    "Conditional on external-force iteration, do two velocity "
                    "iterations repair telemetry or tracking?"
                ),
            },
            {
                "case": "reduced_damping_50",
                "question": (
                    "Conditional on the two solver changes, does halving the "
                    "implicit D-gain reduce the load-dependent position error?"
                ),
            },
        ],
        "staged_single_factor_changes": staged_changes,
        "remote_case_order": list(config.case_names),
        "trajectory_extrema": calibration_trajectory_extrema(config),
        "velocity_contract": {
            "physical_settling_signal": ("windowed finite difference of observed joint position"),
            "raw_joint_vel_role": "compatibility signal",
            "window_ms": config.trajectory.position_velocity_window_ms,
            "settle_threshold_deg_s": (config.trajectory.settle_velocity_threshold_deg_s),
            "maximum_signal_mismatch_deg_s": (
                config.trajectory.maximum_velocity_signal_mismatch_deg_s
            ),
            "material_disagreement_fails_closed": True,
        },
        "official_runtime_basis": [
            (
                "Isaac Lab 3.0 PhysxCfg.enable_external_forces_every_iteration "
                "is intended to improve noisy TGS velocity updates"
            ),
            ("Isaac implicit-actuator stiffness and damping are physics P-gain and D-gain"),
        ],
        "decision_order": [
            "contact_or_self_collision_interference",
            "backend_or_target_buffer_mismatch",
            "position_velocity_instrumentation_incomplete",
            "baseline_tracking_identity_validated",
            "external_force_iteration_resolves_tracking",
            "velocity_iterations_resolve_tracking",
            "reduced_damping_resolves_tracking",
            "external_force_iteration_repairs_velocity_telemetry_only",
            "velocity_iterations_repair_velocity_telemetry_only",
            "reduced_damping_repairs_velocity_telemetry_only",
            "solver_drive_ladder_no_resolution",
        ],
        "checks": checks,
        "local_preparation_passed": all(checks.values()),
        "paid_gpu_run_authorized": False,
        "viewer_authorized": False,
        "pregrasp_authorized": False,
        "contact_or_grasp_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/dofbot/calibration/goal5_solver_drive_diagnostic.json"),
    )
    parser.add_argument(
        "--remote-result",
        type=Path,
        default=Path("artifacts/dofbot/actuator_calibration_result_2026-07-30.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/dofbot/solver_drive_diagnostic_plan.json"),
    )
    args = parser.parse_args()
    result = build_solver_drive_preview(
        config_path=args.config,
        remote_result_path=args.remote_result,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[SOLVER DRIVE PLAN] "
        f"local_preparation_passed={result['local_preparation_passed']} "
        f"output={args.output}"
    )
    if not result["local_preparation_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
