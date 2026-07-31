"""Audit the DOFBOT force-limit residual without starting Isaac or a GPU."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PHYSICAL_SAMPLE_FIELDS = (
    "pose_name",
    "pose_step",
    "elapsed_s",
    "api_command_angles_deg",
    "backend_interpolated_target_angles_deg",
    "joint_pos_target_angles_deg",
    "joint_vel_target_deg_s",
    "observed_joint_angles_deg",
    "observed_joint_velocities_deg_s",
    "critical_contact_force_n",
    "body_positions_world_m",
    "position_derived_joint_velocities_deg_s",
    "raw_position_velocity_mismatch_deg_s",
    "trajectory_complete",
    "position_derived_velocity_stable",
)


def _load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value, raw


def _source_identity(path: Path, raw: bytes) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _require_source_identity(
    *,
    path: Path,
    raw: bytes,
    expected: dict[str, Any],
) -> None:
    actual = _source_identity(path, raw)
    if actual["bytes"] != expected["bytes"]:
        raise ValueError(f"{path} byte count does not match reviewed evidence")
    if actual["sha256"] != expected["sha256"]:
        raise ValueError(f"{path} SHA-256 does not match reviewed evidence")


def drive_limit_equivalent_force(
    limit: float,
    physics_dt_s: float,
) -> float:
    """Return force-equivalent magnitude when a limit is an impulse."""
    if limit <= 0:
        raise ValueError("drive limit must be positive")
    if physics_dt_s <= 0:
        raise ValueError("physics_dt_s must be positive")
    return limit / physics_dt_s


def selected_physical_samples(case: dict[str, Any]) -> list[dict[str, Any]]:
    samples = case["measurement"]["samples"]
    return [
        {field: sample[field] for field in PHYSICAL_SAMPLE_FIELDS}
        for sample in samples
    ]


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _maximum_absolute(values: list[list[float]]) -> float:
    return max(abs(float(value)) for row in values for value in row)


def _candidate_terminal_sample(case: dict[str, Any]) -> dict[str, Any]:
    samples = [
        sample
        for sample in case["measurement"]["samples"]
        if (
            sample["pose_name"] == "pregrasp_candidate"
            and sample["trajectory_complete"]
        )
    ]
    if not samples:
        raise ValueError("pregrasp candidate has no completed sample")
    return samples[-1]


def build_residual_force_audit(
    *,
    drive_result_path: Path,
    actuator_result_path: Path,
    asset_audit_path: Path,
    force_100_case_path: Path,
    force_5_2_case_path: Path,
) -> dict[str, Any]:
    drive_result, drive_result_raw = _load_json(drive_result_path)
    actuator_result, actuator_result_raw = _load_json(actuator_result_path)
    asset_audit, asset_audit_raw = _load_json(asset_audit_path)
    force_100, force_100_raw = _load_json(force_100_case_path)
    force_5_2, force_5_2_raw = _load_json(force_5_2_case_path)

    reviewed_sources = drive_result["source_artifacts"]
    _require_source_identity(
        path=force_100_case_path,
        raw=force_100_raw,
        expected=reviewed_sources["force_damping_53_json"],
    )
    _require_source_identity(
        path=force_5_2_case_path,
        raw=force_5_2_raw,
        expected=reviewed_sources["force_authored_tuning_json"],
    )

    dt_100 = float(force_100["runtime"]["physics_dt_s"])
    dt_5_2 = float(force_5_2["runtime"]["physics_dt_s"])
    if dt_100 != dt_5_2:
        raise ValueError("force-limit cases used different physics timesteps")
    physics_dt_s = dt_100

    physical_100 = selected_physical_samples(force_100)
    physical_5_2 = selected_physical_samples(force_5_2)
    physical_samples_identical = physical_100 == physical_5_2
    pose_summaries_identical = (
        force_100["measurement"]["pose_summaries"]
        == force_5_2["measurement"]["pose_summaries"]
    )
    sample_count = len(physical_100)

    limit_100 = float(
        force_100["runtime"]["configured_effort_limit_sim"]
    )
    limit_5_2 = float(
        force_5_2["runtime"]["configured_effort_limit_sim"]
    )
    terminal = _candidate_terminal_sample(force_5_2)
    terminal_pd_estimate = [
        float(value) for value in terminal["computed_torque"]
    ]
    maximum_pd_estimate = _maximum_absolute(
        [
            [float(value) for value in sample["computed_torque"]]
            for sample in force_5_2["measurement"]["samples"]
        ]
    )

    gravity_off = actuator_result["cases"]["gravity_off_effort_100"]
    gravity_on = actuator_result["cases"]["gravity_on_effort_100"]
    best_force = drive_result["cases"]["force_damping_53"]
    authored_force = drive_result["cases"]["force_authored_tuning"]
    drives = asset_audit["controlled_joint_drives"]

    checks = {
        "reviewed_drive_matrix_complete": bool(
            drive_result["matrix"]["matrix_complete"]
        ),
        "reviewed_drive_matrix_selects_no_passing_case": (
            drive_result["matrix"]["reviewed_decision"]
            == "drive_model_ladder_no_resolution"
        ),
        "raw_force_100_source_identity_matches": True,
        "raw_force_5_2_source_identity_matches": True,
        "physics_timestep_is_60_hz": abs(physics_dt_s - 1.0 / 60.0)
        < 1.0e-12,
        "runtime_max_force_readback_changed": all(
            value == 100.0
            for value in best_force["physx_controlled_dof_max_forces"]
        )
        and all(
            abs(value - 5.2) < 1.0e-5
            for value in authored_force[
                "physx_controlled_dof_max_forces"
            ]
        ),
        "all_selected_physical_samples_identical": (
            physical_samples_identical and sample_count == 647
        ),
        "all_pose_summaries_identical": pose_summaries_identical,
        "gravity_off_tracking_passes": bool(
            gravity_off["tracking_gate_passed"]
        ),
        "gravity_on_tracking_fails": not bool(
            gravity_on["tracking_gate_passed"]
        ),
        "best_force_tracking_still_fails": not bool(
            best_force["tracking_gate_passed"]
        ),
        "target_buffer_matches": bool(
            drive_result["comparisons"][
                "every_case_matches_backend_target_buffer"
            ]
        ),
        "all_controlled_joints_share_axis_and_chain": (
            [drive["name"] for drive in drives]
            == ["joint1", "joint2", "joint3", "joint4"]
            and all(drive["axis"] == "X" for drive in drives)
            and all(
                drive["body1"].endswith(f"/link{index}")
                for index, drive in enumerate(drives, start=1)
            )
        ),
        "viewer_pregrasp_contact_and_hardware_blocked": True,
    }

    limit_analysis = {
        "physics_dt_s": physics_dt_s,
        "physics_frequency_hz": 1.0 / physics_dt_s,
        "runtime_limits": {
            "force_damping_53": limit_100,
            "force_authored_tuning": limit_5_2,
        },
        "if_limits_are_impulses_equivalent_force_per_second": {
            "force_damping_53": drive_limit_equivalent_force(
                limit_100,
                physics_dt_s,
            ),
            "force_authored_tuning": drive_limit_equivalent_force(
                limit_5_2,
                physics_dt_s,
            ),
        },
        "selected_physical_sample_count": sample_count,
        "selected_physical_sequence_sha256": _canonical_sha256(
            physical_5_2
        ),
        "physical_sequences_identical": physical_samples_identical,
        "pose_summaries_identical": pose_summaries_identical,
        "maximum_absolute_implicit_pd_estimate": maximum_pd_estimate,
        "candidate_terminal_implicit_pd_estimate": terminal_pd_estimate,
        "implicit_pd_estimate_is_not_solver_torque": True,
    }

    return {
        "schema_version": 1,
        "experiment": "dofbot_residual_force_semantics_audit",
        "source_evidence": {
            "drive_model_result": _source_identity(
                drive_result_path,
                drive_result_raw,
            ),
            "actuator_result": _source_identity(
                actuator_result_path,
                actuator_result_raw,
            ),
            "asset_drive_audit": _source_identity(
                asset_audit_path,
                asset_audit_raw,
            ),
            "force_damping_53_raw": _source_identity(
                force_100_case_path,
                force_100_raw,
            ),
            "force_authored_tuning_raw": _source_identity(
                force_5_2_case_path,
                force_5_2_raw,
            ),
        },
        "official_semantics": {
            "physx_release_109_source_commit": (
                "176bc52d9605cedf79a5631ca42a42716f5f6d9d"
            ),
            "physx_rule": (
                "PxArticulationFlag::eDRIVE_LIMITS_ARE_FORCES makes "
                "maxForce a force or torque and the solver scales it by the "
                "timestep to obtain an impulse; without the flag maxForce is "
                "used directly as an impulse"
            ),
            "physx_documentation": (
                "https://nvidia-omniverse.github.io/PhysX/physx/5.7.0/"
                "docs/Articulations.html"
            ),
            "physx_cpu_implementation": (
                "https://github.com/NVIDIA-Omniverse/PhysX/blob/"
                "176bc52d9605cedf79a5631ca42a42716f5f6d9d/"
                "physx/source/lowleveldynamics/src/"
                "DyFeatherstoneArticulation.cpp#L3010"
            ),
            "runtime_flag_directly_recorded": False,
            "usd_articulation_authors_drive_limit_unit_flag": False,
        },
        "drive_limit_analysis": limit_analysis,
        "residual_cause_ranking": [
            {
                "candidate": "gravity_load_without_feed_forward",
                "status": "selected_for_next_machine_test",
                "evidence": (
                    "gravity-off tracks within 0.0032 degrees while the "
                    "otherwise matched gravity-on case misses by 4.9762 "
                    "degrees; force-drive tuning reduces but does not remove "
                    "the residual"
                ),
            },
            {
                "candidate": "drive_limit_impulse_semantics",
                "status": "high_confidence_explanation_of_limit_invariance",
                "evidence": (
                    "at 60 Hz an impulse limit of 5.2 is equivalent to 312 "
                    "force units per second, and changing 100 to 5.2 leaves "
                    "647 selected physical samples identical"
                ),
                "boundary": (
                    "the runtime articulation flag was not directly exposed "
                    "by the recorded USD or tensor telemetry"
                ),
            },
            {
                "candidate": "runtime_joint_frame_or_sign_error",
                "status": "rejected_as_primary_cause",
                "evidence": (
                    "the same target and joint-frame path passes with gravity "
                    "off, the target buffer matches, and all four controlled "
                    "joints retain the expected X-axis parent-child chain"
                ),
            },
            {
                "candidate": "full_explicit_pd_actuator",
                "status": "fallback_not_first_change",
                "evidence": (
                    "an explicit actuator makes torque clipping observable "
                    "but introduces a new discrete-time controller; test the "
                    "smaller gravity-feed-forward correction first"
                ),
            },
        ],
        "selected_next_machine_experiment": {
            "name": "bounded_gravity_feed_forward",
            "baseline": {
                "drive_type": "force",
                "stiffness": 1048.0,
                "damping": 53.0,
                "effort_limit_sim": 100.0,
                "enable_external_forces_every_iteration": True,
            },
            "single_changed_behavior": (
                "read PhysX gravity compensation every step and apply the "
                "controlled joint components as bounded external actuation "
                "forces in addition to the unchanged implicit drive"
            ),
            "required_runtime_apis": [
                "ArticulationView.get_gravity_compensation_forces",
                "ArticulationView.set_dof_actuation_forces",
                "ArticulationView.get_link_incoming_joint_force",
            ],
            "runtime_api_documentation": (
                "https://docs.omniverse.nvidia.com/kit/docs/"
                "omni_physics/109.0/extensions/runtime/source/"
                "omni.physics.tensors/docs/api/python.html"
            ),
            "fail_closed_requirements": [
                "all three runtime APIs are available before motion",
                "gravity-compensation values are finite and recorded",
                "only joint1 through joint4 receive feed-forward effort",
                "feed-forward effort is bounded before application",
                "position-derived settling and target-buffer identity remain",
                "maximum gravity-on tracking error is at most 1 degree",
                "zero monitored contact and unchanged safe trajectory",
            ],
            "full_explicit_pd_actuator_is_fallback": True,
        },
        "gate_order": [
            "implement_and_review_bounded_gravity_feed_forward",
            "headless_gravity_on_calibration_at_most_1_degree",
            "headless_pregrasp_machine_gate",
            "viewer_visual_acceptance",
        ],
        "checks": checks,
        "audit_passed": all(checks.values()),
        "paid_gpu_run_authorized": False,
        "pregrasp_authorized": False,
        "viewer_authorized": False,
        "contact_or_grasp_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--drive-result",
        type=Path,
        default=Path(
            "artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json"
        ),
    )
    parser.add_argument(
        "--actuator-result",
        type=Path,
        default=Path(
            "artifacts/dofbot/actuator_calibration_result_2026-07-30.json"
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
        "--force-100-case",
        type=Path,
        default=Path(
            "artifacts/dofbot/drive_model_diagnostic_cases/"
            "force_damping_53.json"
        ),
    )
    parser.add_argument(
        "--force-5-2-case",
        type=Path,
        default=Path(
            "artifacts/dofbot/drive_model_diagnostic_cases/"
            "force_authored_tuning.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/dofbot/residual_force_audit_2026-07-30.json"
        ),
    )
    args = parser.parse_args()
    result = build_residual_force_audit(
        drive_result_path=args.drive_result,
        actuator_result_path=args.actuator_result,
        asset_audit_path=args.asset_audit,
        force_100_case_path=args.force_100_case,
        force_5_2_case_path=args.force_5_2_case,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[RESIDUAL FORCE AUDIT] "
        f"audit_passed={result['audit_passed']} "
        f"output={args.output}"
    )
    if not result["audit_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
