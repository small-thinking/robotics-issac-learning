"""Re-evaluate retrieved actuator samples with position-derived velocity."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .dofbot_actuator_calibration import (
        ActuatorCalibrationError,
        load_actuator_calibration_config,
        position_derived_velocity_deg_s,
        velocity_signal_mismatch_deg_s,
    )
except ImportError:
    from dofbot_actuator_calibration import (
        ActuatorCalibrationError,
        load_actuator_calibration_config,
        position_derived_velocity_deg_s,
        velocity_signal_mismatch_deg_s,
    )


SOURCE_KEYS = {
    "gravity_off_effort_100": "gravity_off_effort_100_json",
    "gravity_on_effort_100": "gravity_on_effort_100_json",
    "gravity_on_effort_250": "gravity_on_effort_250_json",
}


def _load_json(path: Path) -> tuple[dict[str, Any], str, int]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest(), len(raw)


def analyze_pose_velocity(
    samples: list[dict[str, Any]],
    *,
    duration_s: float,
    position_velocity_window_s: float,
    settle_velocity_threshold_deg_s: float,
    settle_hold_s: float,
    maximum_velocity_signal_mismatch_deg_s: float,
) -> dict[str, Any]:
    history: list[dict[str, Any]] = []
    stable_s = 0.0
    previous_elapsed: float | None = None
    stable_mismatches: list[float] = []
    settled_sample: dict[str, Any] | None = None
    terminal_derived: list[float] | None = None
    terminal_raw: list[float] | None = None

    for sample in samples:
        elapsed_s = float(sample["elapsed_s"])
        if previous_elapsed is not None and elapsed_s <= previous_elapsed:
            raise ActuatorCalibrationError("pose samples must have increasing elapsed_s")
        physics_dt = 0.0 if previous_elapsed is None else elapsed_s - previous_elapsed
        previous_elapsed = elapsed_s
        history.append(sample)
        derived = position_derived_velocity_deg_s(
            history,
            window_s=position_velocity_window_s,
        )
        raw = sample.get("observed_joint_velocities_deg_s")
        mismatch = velocity_signal_mismatch_deg_s(raw, derived)
        position_stable = (
            elapsed_s + 1.0e-12 >= duration_s
            and derived is not None
            and max(abs(float(value)) for value in derived) <= settle_velocity_threshold_deg_s
        )
        if position_stable:
            stable_s += physics_dt
            if mismatch is not None:
                stable_mismatches.append(mismatch)
        else:
            stable_s = 0.0
            stable_mismatches = []
        terminal_derived = derived
        terminal_raw = raw
        if stable_s + 1.0e-12 >= settle_hold_s:
            settled_sample = sample
            break

    terminal = settled_sample or samples[-1]
    if terminal_derived is None:
        terminal_derived = [0.0] * 4
    if terminal_raw is None:
        terminal_raw = [0.0] * 4
    maximum_mismatch = max(stable_mismatches, default=0.0)
    mismatch_observed = bool(stable_mismatches)
    observed_angles = [float(value) for value in terminal["observed_joint_angles_deg"]]
    command_angles = [float(value) for value in terminal["api_command_angles_deg"]]
    return {
        "position_derived_settled": settled_sample is not None,
        "settle_elapsed_s": float(terminal["elapsed_s"]),
        "terminal_observed_angles_deg": observed_angles,
        "terminal_position_derived_velocities_deg_s": terminal_derived,
        "terminal_raw_joint_velocities_deg_s": terminal_raw,
        "maximum_terminal_position_derived_velocity_deg_s": max(
            abs(float(value)) for value in terminal_derived
        ),
        "maximum_terminal_raw_joint_velocity_deg_s": max(
            abs(float(value)) for value in terminal_raw
        ),
        "maximum_stable_raw_position_velocity_mismatch_deg_s": (maximum_mismatch),
        "raw_position_velocity_consistent": (
            mismatch_observed and maximum_mismatch <= maximum_velocity_signal_mismatch_deg_s
        ),
        "maximum_tracking_error_deg": max(
            abs(observed - command)
            for observed, command in zip(
                observed_angles,
                command_angles,
                strict=True,
            )
        ),
        "record_ended_before_position_hold": (
            settled_sample is None
            and max(abs(float(value)) for value in terminal_derived)
            <= settle_velocity_threshold_deg_s
        ),
    }


def build_velocity_reanalysis(
    *,
    config_path: Path,
    remote_result_path: Path,
    input_dir: Path,
) -> dict[str, Any]:
    config, config_sha256 = load_actuator_calibration_config(config_path)
    remote_result, remote_result_sha256, _ = _load_json(remote_result_path)
    duration_s = config.trajectory.duration_ms / 1000.0
    window_s = config.trajectory.position_velocity_window_ms / 1000.0
    settle_hold_s = config.trajectory.settle_hold_ms / 1000.0
    case_results: dict[str, Any] = {}
    source_checks: dict[str, bool] = {}
    for case_name, source_key in SOURCE_KEYS.items():
        path = input_dir / f"{case_name}.json"
        artifact, artifact_sha256, artifact_bytes = _load_json(path)
        expected = remote_result["source_artifacts"][source_key]
        source_checks[f"{case_name}_sha256_matches"] = artifact_sha256 == expected["sha256"]
        source_checks[f"{case_name}_size_matches"] = artifact_bytes == expected["bytes"]
        samples = artifact["measurement"]["samples"]
        pose_results = []
        for pose in config.poses:
            pose_samples = [sample for sample in samples if sample["pose_name"] == pose.name]
            if not pose_samples:
                raise ValueError(f"{case_name} is missing pose {pose.name}")
            pose_results.append(
                {
                    "name": pose.name,
                    **analyze_pose_velocity(
                        pose_samples,
                        duration_s=duration_s,
                        position_velocity_window_s=window_s,
                        settle_velocity_threshold_deg_s=(
                            config.trajectory.settle_velocity_threshold_deg_s
                        ),
                        settle_hold_s=settle_hold_s,
                        maximum_velocity_signal_mismatch_deg_s=(
                            config.trajectory.maximum_velocity_signal_mismatch_deg_s
                        ),
                    ),
                }
            )
        case_results[case_name] = {
            "source": {
                "path": str(path),
                "bytes": artifact_bytes,
                "sha256": artifact_sha256,
            },
            "all_poses_settled_by_position_derived_velocity": all(
                pose["position_derived_settled"] for pose in pose_results
            ),
            "all_raw_position_velocity_signals_consistent": all(
                pose["raw_position_velocity_consistent"] for pose in pose_results
            ),
            "all_terminal_position_derived_velocities_below_threshold": all(
                pose["maximum_terminal_position_derived_velocity_deg_s"]
                <= config.trajectory.settle_velocity_threshold_deg_s
                for pose in pose_results
            ),
            "maximum_tracking_error_deg": max(
                pose["maximum_tracking_error_deg"] for pose in pose_results
            ),
            "maximum_position_derived_velocity_deg_s": max(
                pose["maximum_terminal_position_derived_velocity_deg_s"] for pose in pose_results
            ),
            "maximum_raw_joint_velocity_deg_s": max(
                pose["maximum_terminal_raw_joint_velocity_deg_s"] for pose in pose_results
            ),
            "maximum_raw_position_velocity_mismatch_deg_s": max(
                pose["maximum_stable_raw_position_velocity_mismatch_deg_s"] for pose in pose_results
            ),
            "pose_results": pose_results,
        }

    gravity_on_cases = (
        case_results["gravity_on_effort_100"],
        case_results["gravity_on_effort_250"],
    )
    checks = {
        **source_checks,
        "source_matrix_was_complete": bool(remote_result["matrix"]["matrix_complete"]),
        "gravity_on_cases_settle_by_position_difference": all(
            case["all_poses_settled_by_position_derived_velocity"] for case in gravity_on_cases
        ),
        "gravity_off_record_is_right_censored_but_terminal_velocity_is_stable": (
            bool(
                case_results["gravity_off_effort_100"][
                    "all_terminal_position_derived_velocities_below_threshold"
                ]
            )
            and not bool(
                case_results["gravity_off_effort_100"][
                    "all_poses_settled_by_position_derived_velocity"
                ]
            )
        ),
        "gravity_off_velocity_signals_are_consistent": bool(
            case_results["gravity_off_effort_100"]["all_raw_position_velocity_signals_consistent"]
        ),
        "gravity_on_velocity_mismatch_is_reproduced": all(
            not case["all_raw_position_velocity_signals_consistent"] for case in gravity_on_cases
        ),
        "gravity_on_tracking_error_remains_real": all(
            case["maximum_tracking_error_deg"]
            > config.acceptance.maximum_settled_tracking_error_deg
            for case in gravity_on_cases
        ),
    }
    return {
        "schema_version": 1,
        "experiment": "dofbot_actuator_velocity_offline_reanalysis",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_config": {
            "path": str(config_path),
            "sha256": config_sha256,
            "position_velocity_window_ms": (config.trajectory.position_velocity_window_ms),
            "settle_velocity_threshold_deg_s": (config.trajectory.settle_velocity_threshold_deg_s),
            "settle_hold_ms": config.trajectory.settle_hold_ms,
            "maximum_velocity_signal_mismatch_deg_s": (
                config.trajectory.maximum_velocity_signal_mismatch_deg_s
            ),
        },
        "source_remote_result": {
            "path": str(remote_result_path),
            "sha256": remote_result_sha256,
        },
        "cases": case_results,
        "checks": checks,
        "reanalysis_passed": all(checks.values()),
        "conclusion": (
            "All gravity-on poses settle by position difference; the older "
            "gravity-off records end on the original raw-velocity gate before "
            "a full derived hold but finish below the derived threshold. "
            "Gravity-on raw joint_vel remains incompatible with settled "
            "position, and the approximately five-degree error remains real."
        ),
        "gpu_started": False,
        "isaac_started": False,
        "viewer_started": False,
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
        "--input-dir",
        type=Path,
        default=Path("artifacts/dofbot/actuator_calibration_cases"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json"),
    )
    args = parser.parse_args()
    result = build_velocity_reanalysis(
        config_path=args.config,
        remote_result_path=args.remote_result,
        input_dir=args.input_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[VELOCITY REANALYSIS] "
        f"reanalysis_passed={result['reanalysis_passed']} "
        f"output={args.output}"
    )
    if not result["reanalysis_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
