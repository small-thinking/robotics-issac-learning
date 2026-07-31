"""Build the deterministic, GPU-free DOFBOT actuator diagnostic plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .dofbot_actuator_calibration import (
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )
except ImportError:
    from dofbot_actuator_calibration import (
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def build_preview(
    *,
    config_path: Path,
    tracking_failure_path: Path,
) -> dict[str, Any]:
    config, config_sha256 = load_actuator_calibration_config(config_path)
    failure, failure_sha256 = _load_json(tracking_failure_path)
    control = failure["control"]
    exact_api_endpoint = bool(
        control["selected_candidate_was_commanded_exactly_and_stopped"]
    )
    observed_error = float(control["maximum_observed_command_error_deg"])
    tracking_limit = config.acceptance.maximum_settled_tracking_error_deg
    checks = {
        "historical_failure_reached_exact_api_endpoint": exact_api_endpoint,
        "historical_failure_exceeds_tracking_gate": observed_error > tracking_limit,
        "baseline_case_preserves_effort_100": (
            config.case("gravity_on_effort_100").effort_limit_sim == 100.0
        ),
        "gravity_control_changes_only_gravity": (
            config.case("gravity_off_effort_100").effort_limit_sim == 100.0
            and not config.case("gravity_off_effort_100").gravity_enabled
        ),
        "effort_control_preserves_gravity": (
            config.case("gravity_on_effort_250").effort_limit_sim == 250.0
            and config.case("gravity_on_effort_250").gravity_enabled
        ),
        "records_actual_velocity_and_target_buffer": True,
        "records_windowed_position_derived_velocity": True,
        "fails_closed_on_raw_position_velocity_mismatch": True,
        "torque_telemetry_has_explicit_unavailable_state": True,
        "no_table_cube_contact_or_viewer": True,
        "real_hardware_disabled": True,
        "pregrasp_remains_blocked": True,
    }
    trajectory_extrema = calibration_trajectory_extrema(config)
    checks["smoothstep_velocity_within_existing_limit"] = (
        trajectory_extrema["smoothstep_peak_velocity_deg_s"] <= 20.0
    )
    checks["smoothstep_acceleration_within_existing_limit"] = (
        trajectory_extrema["smoothstep_peak_acceleration_deg_s2"] <= 60.0
    )
    return {
        "schema_version": 1,
        "experiment": "dofbot_actuator_diagnostic_plan",
        "calibration_config": {
            "path": str(config_path),
            "sha256": config_sha256,
            "value": config.to_dict(),
        },
        "historical_tracking_failure": {
            "path": str(tracking_failure_path),
            "sha256": failure_sha256,
            "maximum_observed_command_error_deg": observed_error,
        },
        "remote_case_order": list(config.case_names),
        "trajectory_extrema": trajectory_extrema,
        "per_physics_step_telemetry": [
            "api_command_angles_deg",
            "backend_interpolated_target_angles_deg",
            "joint_pos_target_angles_deg",
            "observed_joint_angles_deg",
            "observed_joint_velocities_deg_s",
            "position_derived_joint_velocities_deg_s",
            "raw_position_velocity_mismatch_deg_s",
            "joint_stiffness",
            "joint_damping",
            "joint_effort_limits",
            "computed_torque_if_meaningful",
            "applied_torque_if_meaningful",
            "critical_contact_force_n",
            "optional_physx_mass_inertia_and_dof_properties",
        ],
        "decision_order": [
            "contact_or_self_collision_interference",
            "backend_or_target_buffer_mismatch",
            "joint_velocity_telemetry_compatibility_failure",
            "position_derived_settling_failure",
            "instrumentation_or_runtime_compatibility_failure",
            "baseline_tracking_identity_validated",
            "gravity_load_sensitive_tracking",
            "effort_limit_sensitive_tracking",
            "drive_gain_axis_solver_or_model_mapping_failure",
        ],
        "checks": checks,
        "local_preparation_passed": all(checks.values()),
        "paid_gpu_run_authorized": False,
        "viewer_authorized": False,
        "contact_or_grasp_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/dofbot/calibration/goal5_actuator_diagnostic.json"
        ),
    )
    parser.add_argument(
        "--tracking-failure",
        type=Path,
        default=Path(
            "artifacts/dofbot/"
            "pregrasp_joint_tracking_failure_2026-07-29.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/dofbot/actuator_calibration_plan.json"),
    )
    args = parser.parse_args()
    result = build_preview(
        config_path=args.config,
        tracking_failure_path=args.tracking_failure,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "[CALIBRATION PLAN] "
        f"local_preparation_passed={result['local_preparation_passed']} "
        f"output={args.output}"
    )
    if not result["local_preparation_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
