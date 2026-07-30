from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.dofbot_actuator_calibration import (
    SOLVER_DRIVE_CASE_NAMES,
    ActuatorCalibrationError,
    classify_calibration_matrix,
    load_actuator_calibration_config,
    parse_actuator_calibration_config,
    position_derived_velocity_deg_s,
    velocity_signal_mismatch_deg_s,
)
from tools.preview_dofbot_solver_drive_diagnostic import (
    build_solver_drive_preview,
)
from tools.reanalyze_dofbot_velocity_signals import analyze_pose_velocity

PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/calibration/goal5_solver_drive_diagnostic.json"
)
REMOTE_RESULT_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/actuator_calibration_result_2026-07-30.json"
)
RUNNER_PATH = PROJECT_DIR / "tools/run_dofbot_actuator_calibration.py"
RUN_SCRIPT_PATH = (
    PROJECT_DIR / "scripts/isaac/run_dofbot_actuator_calibration.sh"
)


def _evaluation(
    *,
    tracking_passed: bool = False,
    velocity_consistent: bool = True,
) -> dict[str, object]:
    return {
        "checks": {
            "contact_force_below_threshold": True,
            "target_buffer_telemetry_available": True,
            "target_buffer_matches_backend_target": True,
            "actual_joint_velocity_telemetry_available": True,
            "position_derived_velocity_available": True,
            "raw_position_velocity_signals_consistent": velocity_consistent,
            "all_poses_settled_by_position_derived_velocity": True,
        },
        "diagnostic_complete": velocity_consistent,
        "tracking_gate_passed": tracking_passed,
    }


class DofbotVelocitySolverDiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, _ = load_actuator_calibration_config(CONFIG_PATH)

    def test_solver_drive_ladder_changes_one_factor_at_a_time(self) -> None:
        self.assertEqual(self.config.case_names, SOLVER_DRIVE_CASE_NAMES)
        cases = self.config.cases
        self.assertTrue(all(case.gravity_enabled for case in cases))
        self.assertTrue(all(case.effort_limit_sim == 100.0 for case in cases))
        self.assertFalse(cases[0].enable_external_forces_every_iteration)
        self.assertTrue(cases[1].enable_external_forces_every_iteration)
        self.assertEqual(cases[2].solver_velocity_iteration_count, 2)
        self.assertEqual(cases[3].damping, 50.0)
        self.assertEqual(self.config.trajectory.position_velocity_window_ms, 100)
        self.assertEqual(
            self.config.trajectory.maximum_velocity_signal_mismatch_deg_s,
            1.0,
        )

    def test_solver_drive_schema_rejects_confounded_stage(self) -> None:
        confounded = copy.deepcopy(self.raw)
        confounded["cases"][1]["damping"] = 50
        with self.assertRaisesRegex(
            ActuatorCalibrationError,
            "solver/drive cases",
        ):
            parse_actuator_calibration_config(confounded)

    def test_position_velocity_and_raw_mismatch_are_separate(self) -> None:
        samples = [
            {
                "elapsed_s": 0.0,
                "observed_joint_angles_deg": [0.0, 1.0, 2.0, 3.0],
            },
            {
                "elapsed_s": 0.1,
                "observed_joint_angles_deg": [0.2, 1.0, 2.0, 3.0],
            },
        ]
        derived = position_derived_velocity_deg_s(samples, window_s=0.1)
        self.assertEqual(derived, [2.0, 0.0, 0.0, 0.0])
        self.assertEqual(
            velocity_signal_mismatch_deg_s(
                [10.0, 0.0, 0.0, 0.0],
                derived,
            ),
            8.0,
        )

    def test_offline_pose_analysis_settles_but_flags_raw_velocity(self) -> None:
        samples = [
            {
                "elapsed_s": elapsed,
                "observed_joint_angles_deg": [90.0] * 4,
                "observed_joint_velocities_deg_s": [12.0] * 4,
                "api_command_angles_deg": [90.0] * 4,
            }
            for elapsed in (0.1, 0.2, 0.3, 0.4)
        ]
        result = analyze_pose_velocity(
            samples,
            duration_s=0.1,
            position_velocity_window_s=0.1,
            settle_velocity_threshold_deg_s=0.1,
            settle_hold_s=0.2,
            maximum_velocity_signal_mismatch_deg_s=1.0,
        )
        self.assertTrue(result["position_derived_settled"])
        self.assertFalse(result["raw_position_velocity_consistent"])
        self.assertEqual(
            result["maximum_terminal_position_derived_velocity_deg_s"],
            0.0,
        )
        self.assertEqual(
            result["maximum_terminal_raw_joint_velocity_deg_s"],
            12.0,
        )

    def test_solver_classifier_identifies_tracking_and_telemetry_repairs(self) -> None:
        no_resolution = {
            name: _evaluation() for name in SOLVER_DRIVE_CASE_NAMES
        }
        self.assertEqual(
            classify_calibration_matrix(
                self.config,
                no_resolution,
            )["decision"],
            "solver_drive_ladder_no_resolution",
        )
        tracking_repair = copy.deepcopy(no_resolution)
        tracking_repair["velocity_iterations_2"]["tracking_gate_passed"] = True
        self.assertEqual(
            classify_calibration_matrix(
                self.config,
                tracking_repair,
            )["decision"],
            "velocity_iterations_resolve_tracking",
        )
        telemetry_repair = copy.deepcopy(no_resolution)
        telemetry_repair["baseline_tgs"] = _evaluation(
            velocity_consistent=False
        )
        self.assertEqual(
            classify_calibration_matrix(
                self.config,
                telemetry_repair,
            )["decision"],
            "external_force_iteration_repairs_velocity_telemetry_only",
        )

    def test_solver_preview_is_complete_but_authorizes_nothing(self) -> None:
        result = build_solver_drive_preview(
            config_path=CONFIG_PATH,
            remote_result_path=REMOTE_RESULT_PATH,
        )
        self.assertTrue(result["local_preparation_passed"])
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(result["paid_gpu_run_authorized"])
        self.assertFalse(result["viewer_authorized"])
        self.assertFalse(result["pregrasp_authorized"])

    def test_runner_wires_velocity_contract_and_physx_controls(self) -> None:
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        run_script = RUN_SCRIPT_PATH.read_text(encoding="utf-8")
        for value in (
            "position_derived_joint_velocities_deg_s",
            "raw_position_velocity_mismatch_deg_s",
            "position_derived_velocity_available",
            "PhysxCfg",
            "enable_external_forces_every_iteration",
            "solver_position_iteration_count",
            "solver_velocity_iteration_count",
            "actuator.stiffness = case.stiffness",
            "actuator.damping = case.damping",
        ):
            self.assertIn(value, runner)
        self.assertIn("DOFBOT_ACTUATOR_MATRIX_PROFILE", run_script)
        self.assertIn("solver_drive", run_script)


if __name__ == "__main__":
    unittest.main()
