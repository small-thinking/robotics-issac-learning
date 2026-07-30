from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.dofbot_actuator_calibration import (
    ActuatorCalibrationError,
    calibration_trajectory_extrema,
    classify_calibration_matrix,
    evaluate_calibration_case,
    load_actuator_calibration_config,
    parse_actuator_calibration_config,
)
from tools.preview_dofbot_actuator_calibration import build_preview
from tools.summarize_dofbot_actuator_calibration import build_summary

PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/calibration/goal5_actuator_diagnostic.json"
)
FAILURE_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json"
)
RUNNER_PATH = PROJECT_DIR / "tools/run_dofbot_actuator_calibration.py"
CONTRACT_PATH = PROJECT_DIR / "tools/dofbot_actuator_calibration.py"
RUN_SCRIPT_PATH = (
    PROJECT_DIR / "scripts/isaac/run_dofbot_actuator_calibration.sh"
)


class DofbotActuatorCalibrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, cls.config_sha256 = load_actuator_calibration_config(
            CONFIG_PATH
        )

    def _pose_summaries(
        self,
        *,
        tracking_error_deg: float = 0.2,
        target_error_deg: float = 0.01,
        settled: bool = True,
        contact_force_n: float = 0.0,
    ) -> list[dict[str, object]]:
        summaries = []
        for pose in self.config.poses:
            observed = list(float(value) for value in pose.angles_deg)
            observed[2] += tracking_error_deg
            summaries.append(
                {
                    "name": pose.name,
                    "command_angles_deg": list(pose.angles_deg),
                    "settled": settled,
                    "settle_elapsed_s": 1.5,
                    "terminal_observed_angles_deg": observed,
                    "terminal_actual_velocities_deg_s": [0.02] * 4,
                    "maximum_tracking_error_deg": tracking_error_deg,
                    "maximum_target_buffer_error_deg": target_error_deg,
                    "maximum_overshoot_deg": 0.1,
                    "maximum_contact_force_n": contact_force_n,
                    "terminal_body_positions_world_m": {
                        "Wrist_Twist": [0.0, 0.1, 0.2],
                        "Finger_Left_03": [-0.02, 0.2, 0.3],
                        "Finger_Right_03": [0.02, 0.2, 0.3],
                    },
                }
            )
        return summaries

    def _evaluation(
        self,
        *,
        tracking_passed: bool,
        target_ok: bool = True,
        settled: bool = True,
        contact_ok: bool = True,
        diagnostic_complete: bool = True,
    ) -> dict[str, object]:
        return {
            "checks": {
                "contact_force_below_threshold": contact_ok,
                "all_poses_settled_by_actual_velocity": settled,
                "target_buffer_telemetry_available": target_ok,
                "target_buffer_matches_backend_target": target_ok,
            },
            "diagnostic_complete": diagnostic_complete,
            "tracking_gate_passed": tracking_passed,
        }

    def test_config_locks_three_orthogonal_cases_and_pose_order(self) -> None:
        self.assertEqual(
            [case.name for case in self.config.cases],
            [
                "gravity_on_effort_100",
                "gravity_off_effort_100",
                "gravity_on_effort_250",
            ],
        )
        self.assertEqual(
            [pose.name for pose in self.config.poses],
            [
                "neutral_start",
                "mid_load",
                "pregrasp_candidate",
                "neutral_return",
            ],
        )
        self.assertEqual(
            self.config.poses[2].angles_deg,
            (90, 66, 66, 66),
        )
        self.assertEqual(self.config.poses[-1].angles_deg, (90, 90, 90, 90))
        self.assertEqual(self.config.trajectory.duration_ms, 2000)
        extrema = calibration_trajectory_extrema(self.config)
        self.assertEqual(extrema["maximum_transition_delta_deg"], 24.0)
        self.assertEqual(extrema["smoothstep_peak_velocity_deg_s"], 18.0)
        self.assertEqual(
            extrema["smoothstep_peak_acceleration_deg_s2"],
            36.0,
        )
        self.assertEqual(len(self.config_sha256), 64)

    def test_schema_rejects_unsafe_or_confounded_matrix(self) -> None:
        extra = {**self.raw, "viewer": True}
        with self.assertRaisesRegex(ActuatorCalibrationError, "keys must match"):
            parse_actuator_calibration_config(extra)

        unsafe = copy.deepcopy(self.raw)
        unsafe["poses"][2]["angles_deg"][3] = 59
        with self.assertRaisesRegex(ActuatorCalibrationError, "safe envelope"):
            parse_actuator_calibration_config(unsafe)

        confounded = copy.deepcopy(self.raw)
        confounded["cases"][1]["effort_limit_sim"] = 250
        with self.assertRaisesRegex(ActuatorCalibrationError, "isolate gravity"):
            parse_actuator_calibration_config(confounded)

        loose = copy.deepcopy(self.raw)
        loose["acceptance"]["maximum_settled_tracking_error_deg"] = 2.0
        with self.assertRaisesRegex(ActuatorCalibrationError, r"\[0.1, 1.0\]"):
            parse_actuator_calibration_config(loose)

        too_fast = copy.deepcopy(self.raw)
        too_fast["trajectory"]["duration_ms"] = 1000
        with self.assertRaisesRegex(ActuatorCalibrationError, "20 deg/s"):
            parse_actuator_calibration_config(too_fast)

    def test_case_evaluation_uses_actual_velocity_and_target_buffer(self) -> None:
        result = evaluate_calibration_case(
            self.config,
            self.config.case("gravity_on_effort_100"),
            self._pose_summaries(),
            official_api_call_count=16,
            target_buffer_available=True,
            actual_velocity_available=True,
            torque_interpretation=(
                "implicit_zero_or_unavailable_do_not_infer"
            ),
            torque_saturation_observed=False,
        )
        self.assertTrue(result["diagnostic_complete"])
        self.assertTrue(result["tracking_gate_passed"])
        self.assertTrue(all(result["checks"].values()))

        mismatch = evaluate_calibration_case(
            self.config,
            self.config.case("gravity_on_effort_100"),
            self._pose_summaries(target_error_deg=1.0),
            official_api_call_count=16,
            target_buffer_available=True,
            actual_velocity_available=True,
            torque_interpretation=(
                "implicit_zero_or_unavailable_do_not_infer"
            ),
            torque_saturation_observed=False,
        )
        self.assertFalse(mismatch["diagnostic_complete"])
        self.assertFalse(
            mismatch["checks"]["target_buffer_matches_backend_target"]
        )
        with self.assertRaisesRegex(
            ActuatorCalibrationError,
            "torque interpretation",
        ):
            evaluate_calibration_case(
                self.config,
                self.config.case("gravity_on_effort_100"),
                self._pose_summaries(),
                official_api_call_count=16,
                target_buffer_available=True,
                actual_velocity_available=True,
                torque_interpretation="zero_means_no_saturation",
                torque_saturation_observed=False,
            )

    def test_matrix_decision_tree_separates_root_cause_classes(self) -> None:
        baseline_fail = self._evaluation(tracking_passed=False)
        all_fail = {
            case.name: copy.deepcopy(baseline_fail)
            for case in self.config.cases
        }
        self.assertEqual(
            classify_calibration_matrix(self.config, all_fail)["decision"],
            "drive_gain_axis_solver_or_model_mapping_failure",
        )

        gravity_sensitive = copy.deepcopy(all_fail)
        gravity_sensitive["gravity_off_effort_100"][
            "tracking_gate_passed"
        ] = True
        self.assertEqual(
            classify_calibration_matrix(
                self.config,
                gravity_sensitive,
            )["decision"],
            "gravity_load_sensitive_tracking",
        )

        observed_saturation = copy.deepcopy(all_fail)
        observed_saturation["gravity_on_effort_100"][
            "torque_saturation_observed"
        ] = True
        self.assertEqual(
            classify_calibration_matrix(
                self.config,
                observed_saturation,
            )["decision"],
            "effort_saturation_observed",
        )

        effort_sensitive = copy.deepcopy(all_fail)
        effort_sensitive["gravity_on_effort_250"][
            "tracking_gate_passed"
        ] = True
        self.assertEqual(
            classify_calibration_matrix(
                self.config,
                effort_sensitive,
            )["decision"],
            "effort_limit_sensitive_tracking",
        )

        target_mismatch = copy.deepcopy(all_fail)
        target_mismatch["gravity_on_effort_100"]["checks"][
            "target_buffer_matches_backend_target"
        ] = False
        self.assertEqual(
            classify_calibration_matrix(
                self.config,
                target_mismatch,
            )["decision"],
            "backend_or_target_buffer_mismatch",
        )
        self.assertEqual(
            classify_calibration_matrix(
                self.config,
                {
                    "gravity_on_effort_100": self._evaluation(
                        tracking_passed=False
                    )
                },
            )["decision"],
            "incomplete_case_matrix",
        )

    def test_local_plan_binds_failure_without_authorizing_gpu_or_pregrasp(self) -> None:
        result = build_preview(
            config_path=CONFIG_PATH,
            tracking_failure_path=FAILURE_PATH,
        )
        self.assertTrue(result["local_preparation_passed"])
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(result["paid_gpu_run_authorized"])
        self.assertFalse(result["viewer_authorized"])
        self.assertFalse(result["contact_or_grasp_authorized"])

    def test_summary_requires_every_case_and_preserves_pregrasp_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            input_dir = Path(temporary)
            for case in self.config.cases:
                evaluation = self._evaluation(tracking_passed=False)
                artifact = {
                    "experiment": "dofbot_actuator_diagnostic_case",
                    "git_commit": "test",
                    "case": case.to_dict(),
                    "calibration_config": {"sha256": self.config_sha256},
                    "evaluation": evaluation,
                }
                (input_dir / f"{case.name}.json").write_text(
                    json.dumps(artifact),
                    encoding="utf-8",
                )
            result = build_summary(
                config_path=CONFIG_PATH,
                input_dir=input_dir,
                git_commit="test",
            )
            self.assertTrue(result["matrix_complete"])
            self.assertEqual(
                result["decision"]["decision"],
                "drive_gain_axis_solver_or_model_mapping_failure",
            )
            self.assertFalse(result["pregrasp_authorized"])
            self.assertFalse(result["viewer_authorized"])

            stale_path = input_dir / "gravity_on_effort_250.json"
            stale = json.loads(stale_path.read_text(encoding="utf-8"))
            stale["git_commit"] = "stale"
            stale_path.write_text(json.dumps(stale), encoding="utf-8")
            stale_result = build_summary(
                config_path=CONFIG_PATH,
                input_dir=input_dir,
                git_commit="test",
            )
            self.assertFalse(stale_result["matrix_complete"])
            self.assertFalse(
                stale_result["checks"][
                    "gravity_on_effort_250_git_commit_matches"
                ]
            )

    def test_runner_records_full_chain_without_task_scene_or_viewer(self) -> None:
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        run_script = RUN_SCRIPT_PATH.read_text(encoding="utf-8")
        for field in (
            "api_command_angles_deg",
            "backend_interpolated_target_angles_deg",
            "joint_pos_target_angles_deg",
            "observed_joint_angles_deg",
            "observed_joint_velocities_deg_s",
            "joint_stiffness",
            "joint_damping",
            "joint_effort_limits",
            "computed_torque",
            "applied_torque",
            "critical_contact_force_n",
            "body_positions_world_m",
            "get_masses",
            "get_inertias",
            "get_dof_stiffnesses",
            "get_dof_max_forces",
            "optional_probe_errors",
        ):
            self.assertIn(field, runner)
        self.assertIn("sample_every_physics_step", runner)
        self.assertIn(
            "all_poses_settled_by_actual_velocity",
            CONTRACT_PATH.read_text(encoding="utf-8"),
        )
        self.assertNotIn("CameraCfg", runner)
        self.assertNotIn("_spawn_scene_boxes", runner)
        self.assertNotIn("Arm_Lib", runner)
        self.assertNotIn("--livestream", run_script)
        self.assertNotIn("--viz", run_script)
        self.assertIn("run_case gravity_on_effort_100", run_script)
        self.assertIn("run_case gravity_off_effort_100", run_script)
        self.assertIn("run_case gravity_on_effort_250", run_script)
        self.assertIn("[MATRIX_EXIT_CODE]", run_script)
        self.assertIn("timeout $quoted_case_timeout_seconds", run_script)
        self.assertIn("archive_dir=", run_script)
        self.assertIn("mv ", run_script)
        self.assertIn("exit 0", run_script)
        self.assertIn("grep -Fqx '[MATRIX_EXIT_CODE] 0'", run_script)
        self.assertIn('transport_exit_code="${PIPESTATUS[0]}"', run_script)


if __name__ == "__main__":
    unittest.main()
