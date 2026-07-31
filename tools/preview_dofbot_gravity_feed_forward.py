"""Build the GPU-free bounded gravity feed-forward machine plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .dofbot_actuator_calibration import (
        GRAVITY_FEED_FORWARD_CASE_NAMES,
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )
    from .dofbot_gravity_feed_forward import REQUIRED_GRAVITY_RUNTIME_APIS
except ImportError:
    from dofbot_actuator_calibration import (
        GRAVITY_FEED_FORWARD_CASE_NAMES,
        calibration_trajectory_extrema,
        load_actuator_calibration_config,
    )
    from dofbot_gravity_feed_forward import REQUIRED_GRAVITY_RUNTIME_APIS


def _load_object(path: Path) -> tuple[dict[str, Any], str]:
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


def build_gravity_feed_forward_preview(
    *,
    config_path: Path,
    residual_force_audit_path: Path,
    runner_path: Path,
) -> dict[str, Any]:
    config, config_sha256 = load_actuator_calibration_config(config_path)
    if config.name != "goal5_gravity_feed_forward_diagnostic":
        raise ValueError(
            "config must select goal5_gravity_feed_forward_diagnostic"
        )
    audit, audit_sha256 = _load_object(residual_force_audit_path)
    selected = audit["selected_next_machine_experiment"]
    cases = [case.to_dict() for case in config.cases]
    runner = runner_path.read_text(encoding="utf-8")
    required_api_names = [
        value.rsplit(".", 1)[-1] for value in selected["required_runtime_apis"]
    ]
    baseline = selected["baseline"]
    configured_baseline = {
        key: cases[0][key]
        for key in (
            "drive_type",
            "stiffness",
            "damping",
            "effort_limit_sim",
            "enable_external_forces_every_iteration",
        )
    }
    apply_index = runner.find("gravity_feed_forward.apply_before_step()")
    write_index = runner.find("scene.write_data_to_sim()")
    step_index = runner.find("sim.step(render=False)")
    checks = {
        "source_is_residual_force_audit": (
            audit["experiment"] == "dofbot_residual_force_semantics_audit"
        ),
        "source_selects_bounded_gravity_feed_forward": (
            selected["name"] == "bounded_gravity_feed_forward"
        ),
        "source_baseline_matches_config": configured_baseline == baseline,
        "case_order_locked": (
            config.case_names == GRAVITY_FEED_FORWARD_CASE_NAMES
        ),
        "both_cases_keep_gravity_on": all(
            case.gravity_enabled for case in config.cases
        ),
        "both_cases_keep_force_1048_53_100": all(
            (
                case.drive_type,
                case.stiffness,
                case.damping,
                case.effort_limit_sim,
                case.enable_external_forces_every_iteration,
            )
            == ("force", 1048.0, 53.0, 100.0, True)
            for case in config.cases
        ),
        "cases_change_only_feed_forward_enable": (
            _changed_fields(cases[0], cases[1])
            == ["gravity_compensation_feed_forward"]
        ),
        "feed_forward_bound_is_official_5_2": all(
            case.gravity_compensation_effort_limit == 5.2
            for case in config.cases
        ),
        "required_runtime_apis_match_audit": (
            required_api_names == list(REQUIRED_GRAVITY_RUNTIME_APIS)
        ),
        "runner_probes_every_required_api": all(
            name in runner for name in REQUIRED_GRAVITY_RUNTIME_APIS
        ),
        "runner_applies_after_pd_write_before_step": (
            -1 < write_index < apply_index < step_index
        ),
        "runner_records_gravity_and_incoming_force": all(
            value in runner
            for value in (
                "prepare_bounded_gravity_feed_forward",
                "evaluate_gravity_feed_forward_telemetry",
                "controlled_incoming_joint_forces",
            )
        ),
        "unchanged_one_degree_gate": (
            config.acceptance.maximum_settled_tracking_error_deg == 1.0
        ),
        "safe_trajectory_is_unchanged": (
            [pose.angles_deg for pose in config.poses]
            == [
                (90, 90, 90, 90),
                (90, 78, 78, 78),
                (90, 66, 66, 66),
                (90, 90, 90, 90),
            ]
        ),
        "pregrasp_viewer_contact_hardware_and_policy_blocked": True,
    }
    return {
        "schema_version": 1,
        "experiment": "dofbot_gravity_feed_forward_plan",
        "calibration_config": {
            "path": str(config_path),
            "sha256": config_sha256,
            "value": config.to_dict(),
        },
        "source_residual_force_audit": {
            "path": str(residual_force_audit_path),
            "sha256": audit_sha256,
            "selected_experiment": selected,
        },
        "runner": {
            "path": str(runner_path),
            "sha256": hashlib.sha256(runner.encode()).hexdigest(),
        },
        "single_factor_comparison": {
            "baseline_case": cases[0],
            "treatment_case": cases[1],
            "changed_fields": _changed_fields(cases[0], cases[1]),
        },
        "trajectory_extrema": calibration_trajectory_extrema(config),
        "runtime_contract": {
            "probe_before_motion": list(REQUIRED_GRAVITY_RUNTIME_APIS),
            "apply_order": [
                "write_implicit_pd_targets",
                "read_gravity_compensation",
                "clamp_joint1_through_joint4_to_plus_or_minus_5_2",
                "zero_all_uncontrolled_dofs",
                "set_dof_actuation_forces",
                "step_physics",
                "record_incoming_joint_forces",
            ],
            "position_derived_settling_required": True,
            "target_buffer_identity_required": True,
            "maximum_settled_tracking_error_deg": 1.0,
            "maximum_contact_force_n": (
                config.acceptance.maximum_contact_force_n
            ),
        },
        "decision_order": [
            "gravity_compensation_runtime_api_unavailable",
            "gravity_feed_forward_safety_contract_failed",
            "contact_or_self_collision_interference",
            "backend_or_target_buffer_mismatch",
            "position_velocity_instrumentation_incomplete",
            "stable_force_baseline_tracking_validated",
            "bounded_gravity_feed_forward_resolves_tracking",
            "bounded_gravity_feed_forward_no_resolution",
        ],
        "checks": checks,
        "local_preparation_passed": all(checks.values()),
        "paid_gpu_run_authorized": False,
        "pregrasp_authorized": False,
        "viewer_authorized": False,
        "contact_or_grasp_authorized": False,
        "real_hardware_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/dofbot/calibration/"
            "goal5_gravity_feed_forward_diagnostic.json"
        ),
    )
    parser.add_argument(
        "--residual-force-audit",
        type=Path,
        default=Path(
            "artifacts/dofbot/residual_force_audit_2026-07-30.json"
        ),
    )
    parser.add_argument(
        "--runner",
        type=Path,
        default=Path("tools/run_dofbot_actuator_calibration.py"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/dofbot/gravity_feed_forward_plan.json"),
    )
    args = parser.parse_args()
    result = build_gravity_feed_forward_preview(
        config_path=args.config,
        residual_force_audit_path=args.residual_force_audit,
        runner_path=args.runner,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[GRAVITY FEED-FORWARD PLAN] "
        f"local_preparation_passed={result['local_preparation_passed']} "
        f"output={args.output}"
    )
    if not result["local_preparation_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
