"""Build the GPU-free DOFBOT drive-model diagnostic plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .dofbot_actuator_calibration import (
        DRIVE_MODEL_CASE_NAMES,
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )
except ImportError:
    from dofbot_actuator_calibration import (
        DRIVE_MODEL_CASE_NAMES,
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
    return sorted(
        key
        for key in set(previous) | set(current)
        if key != "name" and previous.get(key) != current.get(key)
    )


def build_drive_model_preview(
    *,
    config_path: Path,
    asset_audit_path: Path,
    solver_result_path: Path,
) -> dict[str, Any]:
    config, config_sha256 = load_actuator_calibration_config(config_path)
    if config.name != "goal5_drive_model_diagnostic":
        raise ValueError("config must select goal5_drive_model_diagnostic")
    asset_audit, asset_audit_sha256 = _load_json(asset_audit_path)
    solver_result, solver_result_sha256 = _load_json(solver_result_path)
    cases = [case.to_dict() for case in config.cases]
    staged_changes = [
        {
            "from": previous["name"],
            "to": current["name"],
            "changed_fields": _changed_fields(previous, current),
        }
        for previous, current in zip(cases, cases[1:], strict=False)
    ]
    authored_drives = asset_audit["controlled_joint_drives"]
    expected_changes = [
        ["drive_type"],
        ["stiffness"],
        ["damping"],
        ["effort_limit_sim"],
    ]
    checks = {
        "source_solver_matrix_complete": bool(
            solver_result["matrix"]["matrix_complete"]
        ),
        "source_tracking_still_blocked": not bool(
            solver_result["matrix"]["tracking_identity_validated"]
        ),
        "source_decision_requires_drive_audit": (
            solver_result["evidence_interpretation"]["next_local_action"]
            .startswith("retain external-force iteration")
        ),
        "official_asset_meter_scale": (
            asset_audit["source_asset"]["meters_per_unit"] == 1
        ),
        "official_asset_not_committed": not bool(
            asset_audit["source_asset"]["committed_to_repository"]
        ),
        "four_controlled_joint_drives": len(authored_drives) == 4,
        "controlled_joint_order_locked": [
            drive["name"] for drive in authored_drives
        ]
        == ["joint1", "joint2", "joint3", "joint4"],
        "every_controlled_axis_is_x": all(
            drive["axis"] == "X" for drive in authored_drives
        ),
        "every_authored_drive_is_acceleration": all(
            drive["drive_type"] == "acceleration"
            for drive in authored_drives
        ),
        "authored_tuning_is_uniform": all(
            (
                drive["stiffness"],
                drive["damping"],
                drive["max_force"],
            )
            == (1048, 53, 5.2)
            for drive in authored_drives
        ),
        "previous_torque_claim_corrected": not bool(
            asset_audit["torque_evidence_correction"][
                "physical_saturation_proven"
            ]
        ),
        "case_order_locked": config.case_names == DRIVE_MODEL_CASE_NAMES,
        "every_case_keeps_gravity_on": all(
            case.gravity_enabled for case in config.cases
        ),
        "every_case_keeps_external_force_iteration": all(
            case.enable_external_forces_every_iteration
            for case in config.cases
        ),
        "each_stage_changes_exactly_one_field": [
            stage["changed_fields"] for stage in staged_changes
        ]
        == expected_changes,
        "reference_reproduces_composed_acceleration_drive": (
            cases[0]["drive_type"] == "acceleration"
            and cases[0]["stiffness"] == 10000.0
            and cases[0]["damping"] == 100.0
            and cases[0]["effort_limit_sim"] == 100.0
        ),
        "final_case_tests_authored_tuning_as_force": (
            cases[-1]["drive_type"] == "force"
            and cases[-1]["stiffness"] == 1048.0
            and cases[-1]["damping"] == 53.0
            and cases[-1]["effort_limit_sim"] == 5.2
        ),
        "pregrasp_viewer_contact_and_hardware_blocked": True,
    }
    return {
        "schema_version": 1,
        "experiment": "dofbot_drive_model_diagnostic_plan",
        "calibration_config": {
            "path": str(config_path),
            "sha256": config_sha256,
            "value": config.to_dict(),
        },
        "source_asset_audit": {
            "path": str(asset_audit_path),
            "sha256": asset_audit_sha256,
            "asset_sha256": asset_audit["source_asset"]["sha256"],
        },
        "source_solver_result": {
            "path": str(solver_result_path),
            "sha256": solver_result_sha256,
            "machine_commit": solver_result["machine_commit"],
            "decision": solver_result["matrix"]["decision"],
        },
        "root_cause_boundary": {
            "established": (
                "joint1 through joint4 are uniform X-axis acceleration drives; "
                "the current runtime did not override drive type"
            ),
            "hypothesis": (
                "force-drive semantics repair or materially reduce the "
                "gravity-on position-tracking error"
            ),
            "not_yet_claimed": (
                "the drive type is the root cause or any candidate passes "
                "the one-degree tracking gate"
            ),
        },
        "staged_single_factor_changes": staged_changes,
        "remote_case_order": list(config.case_names),
        "trajectory_extrema": calibration_trajectory_extrema(config),
        "runtime_requirements": {
            "read_back_composed_usd_drive_type_per_controlled_joint": True,
            "treat_implicit_torque_buffers_as_pd_estimates_only": True,
            "position_derived_settling_required": True,
            "target_buffer_identity_required": True,
            "maximum_settled_tracking_error_deg": (
                config.acceptance.maximum_settled_tracking_error_deg
            ),
        },
        "decision_order": [
            "contact_or_self_collision_interference",
            "backend_or_target_buffer_mismatch",
            "position_velocity_instrumentation_incomplete",
            "acceleration_runtime_tracking_validated",
            "force_drive_resolves_tracking",
            "force_stiffness_1048_resolves_tracking",
            "force_damping_53_resolves_tracking",
            "force_authored_tuning_resolves_tracking",
            "drive_model_ladder_no_resolution",
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
        default=Path(
            "configs/dofbot/calibration/goal5_drive_model_diagnostic.json"
        ),
    )
    parser.add_argument(
        "--asset-audit",
        type=Path,
        default=Path(
            "artifacts/dofbot/asset_drive_audit_2026-07-30.json"
        ),
    )
    parser.add_argument(
        "--solver-result",
        type=Path,
        default=Path(
            "artifacts/dofbot/solver_drive_diagnostic_result_2026-07-30.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/dofbot/drive_model_diagnostic_plan.json"),
    )
    args = parser.parse_args()
    result = build_drive_model_preview(
        config_path=args.config,
        asset_audit_path=args.asset_audit,
        solver_result_path=args.solver_result,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[DRIVE MODEL PLAN] "
        f"local_preparation_passed={result['local_preparation_passed']} "
        f"output={args.output}"
    )
    if not result["local_preparation_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
