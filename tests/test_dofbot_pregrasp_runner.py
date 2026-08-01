from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_DIR / "tools/run_dofbot_pregrasp.py"
SCENE_CFG_PATH = PROJECT_DIR / "tools/dofbot_pregrasp_scene_cfg.py"
BASE_SCENE_CFG_PATH = PROJECT_DIR / "tools/dofbot_scene_cfg.py"
POSE_MODULE_PATH = PROJECT_DIR / "tools/dofbot_pregrasp_pose.py"
RUN_SCRIPT_PATH = PROJECT_DIR / "scripts/isaac/run_dofbot_pregrasp.sh"
VIEW_SCRIPT_PATH = PROJECT_DIR / "scripts/isaac/view_dofbot_pregrasp.sh"
GRAVITY_RUNTIME_PATH = (
    PROJECT_DIR / "tools/dofbot_gravity_feed_forward_runtime.py"
)


class DofbotPregraspRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = RUNNER_PATH.read_text(encoding="utf-8")
        cls.scene_cfg = SCENE_CFG_PATH.read_text(encoding="utf-8")
        cls.base_scene_cfg = BASE_SCENE_CFG_PATH.read_text(encoding="utf-8")
        cls.pose_module = POSE_MODULE_PATH.read_text(encoding="utf-8")
        cls.run_script = RUN_SCRIPT_PATH.read_text(encoding="utf-8")
        cls.view_script = VIEW_SCRIPT_PATH.read_text(encoding="utf-8")
        cls.gravity_runtime = GRAVITY_RUNTIME_PATH.read_text(encoding="utf-8")

    def test_preflight_contracts_run_before_kit_launch(self) -> None:
        self.assertLess(
            self.runner.index("preflight_scene, preflight_scene_sha256"),
            self.runner.index("app_launcher = AppLauncher(args_cli)"),
        )
        self.assertLess(
            self.runner.index("preflight_asset_sha256"),
            self.runner.index("app_launcher = AppLauncher(args_cli)"),
        )
        self.assertLess(
            self.runner.index("preflight_actuator_runtime ="),
            self.runner.index("app_launcher = AppLauncher(args_cli)"),
        )
        self.assertIn(
            "load_accepted_gravity_feed_forward_runtime(",
            self.runner,
        )
        self.assertIn(
            "pose target does not match the scene approach waypoint",
            self.runner,
        )

    def test_runner_uses_terminal_finger_frame_and_full_body_jacobian(self) -> None:
        self.assertIn("derive_grasp_frame(", self.runner)
        self.assertIn("left_tip_body_name", self.runner)
        self.assertIn("right_tip_body_name", self.runner)
        self.assertIn("body_link_jacobian_w.torch", self.runner)
        self.assertIn("0:6", self.runner)
        self.assertIn("_terminal_midpoint_jacobian", self.runner)
        self.assertNotIn("root_physx_view.get_jacobians", self.runner)

    def test_contact_reporter_is_enabled_and_machine_gated(self) -> None:
        self.assertIn("activate_contact_sensors=True", self.scene_cfg)
        self.assertNotIn("ContactSensorCfg", self.scene_cfg)
        for expected_text in (
            'f"/World/envs/env_0/Dofbot/{name}"',
            'f"/World/envs/env_0/Dofbot/link5/{name}"',
            '"link2", "link3", "link4"',
            '"Wrist_Twist"',
            '"Finger_Left_02"',
            '"Finger_Right_03"',
        ):
            self.assertIn(expected_text, self.scene_cfg)
        self.assertNotIn("Finger_Left_02/Finger_Left_02", self.scene_cfg)
        self.assertIn("subscribe_contact_report_events", self.runner)
        self.assertIn("PhysicsSchemaTools.intToSdfPath", self.runner)
        self.assertIn("maximum_monitored_contact_force_n(", self.runner)
        self.assertIn("physics_dt=self._physics_dt", self.runner)
        self.assertIn(
            "contact_reporter_force_remains_below_threshold",
            self.runner,
        )
        self.assertIn("maximum_critical_contact_force_n", self.runner)
        self.assertIn('"step=0 "', self.runner)
        self.assertIn("angles_deg={initial['angles_deg']}", self.runner)
        self.assertIn("angles_deg={observation['angles_deg']}", self.runner)

    def test_runner_preserves_yahboom_four_servo_boundary(self) -> None:
        self.assertIn("Arm_serial_servo_write(", self.runner)
        self.assertIn("next_pregrasp_command(", self.runner)
        self.assertNotIn("Arm_serial_servo_write6", self.runner)
        self.assertNotIn("Wrist_Twist_RevoluteJoint", self.runner)
        self.assertNotIn("CameraCfg", self.runner)
        self.assertNotIn("Arm_Lib", self.runner)
        self.assertIn('"wrist_twist_commanded": False', self.runner)
        self.assertIn('"gripper_commanded": False', self.runner)

    def test_runner_gates_pose_smoothness_collision_reset_and_api_count(self) -> None:
        for expected in (
            "grasp_origin_reached_pregrasp_position",
            "approach_axis_matches_target_within_tolerance",
            "fixed_closing_axis_is_acceptable_without_wrist_command",
            "joint_angles_remain_within_safe_limits",
            "joint_velocity_limit_respected",
            "joint_acceleration_limit_respected",
            "contact_reporter_force_remains_below_threshold",
            "pose_controller_improved_position",
            "official_api_call_count_matches",
            "api_commands_preserve_limit_margin",
            "validated_joint_candidate_command_reached",
            "final_api_joint_tracking_within_tolerance",
            "returned_to_neutral",
        ):
            self.assertIn(expected, self.runner + self.pose_module)
        self.assertIn('"status": "pending_user_confirmation"', self.runner)
        self.assertIn('"goal5_complete": False', self.runner)
        self.assertIn(
            "simulation app stopped before the headless pose",
            self.runner,
        )
        self.assertIn(
            "simulation app stopped before the headless neutral",
            self.runner,
        )
        self.assertIn(
            "simulation app stopped before initial neutral settle completed",
            self.runner,
        )
        self.assertIn("initialization_api_calls", self.runner)
        self.assertIn(
            "4 + len(controller_command_angles) * 4 + 4",
            self.runner,
        )
        self.assertIn(
            "mode=candidate_settle_without_api_reissue",
            self.runner,
        )
        settle_branch = self.runner.index(
            "== VALIDATED_JOINT_CANDIDATE_CONTROL_MODE"
        )
        next_command = self.runner.index(
            "command = next_pregrasp_command(",
            settle_branch,
        )
        self.assertLess(
            self.runner.index("continue", settle_branch),
            next_command,
        )
        self.assertIn(
            "Isaac requested a zero-code exit before pre-grasp completion",
            self.runner,
        )
        self.assertIn("except BaseException as error:", self.runner)
        self.assertIn("else:\n        simulation_app.close()", self.runner)
        self.assertNotIn("finally:\n        simulation_app.close()", self.runner)

    def test_runner_reuses_machine_validated_actuator_runtime(self) -> None:
        for expected in (
            "goal5_gravity_feed_forward_diagnostic.json",
            "gravity_feed_forward_result_2026-07-31.json",
            "actuator_runtime.stiffness",
            "actuator_runtime.damping",
            "actuator_runtime.effort_limit_sim",
            "solver_position_iteration_count",
            "solver_velocity_iteration_count",
            "enable_external_forces_every_iteration",
            "JointDrivePropertiesCfg(",
            "BoundedGravityFeedForward(",
            "controlled_joint_drive_snapshot()",
            "controlled_joint_runtime_effort_limits(",
            "drive_snapshot_matches_runtime(",
            "effort_limits_match_runtime(",
            "expected_drive_runtime",
            "actual_usd_drives={drive_snapshot}",
            "actual_runtime_effort_limits={runtime_effort_limits}",
            "evaluate_gravity_feed_forward_telemetry(",
            '"accepted_actuator_machine_evidence_bound": True',
            '"live_actuator_drive_matches_selected_contract"',
            '"live_actuator_effort_limits_match_selected_contract"',
            '"live_controlled_joint_runtime_effort_limits"',
            '"gravity_feed_forward_samples": gravity_samples',
        ):
            self.assertIn(expected, self.runner)
        self.assertLess(
            self.runner.index("gravity_feed_forward = BoundedGravityFeedForward("),
            self.runner.index("initialization_api_calls = _issue_angles("),
        )
        self.assertLess(
            self.runner.index("scene.write_data_to_sim()"),
            self.runner.index("gravity_sample = gravity_feed_forward.apply_before_step()"),
        )
        self.assertLess(
            self.runner.index("gravity_sample = gravity_feed_forward.apply_before_step()"),
            self.runner.index("sim.step(render=render)"),
        )
        self.assertIn("dtype=wp.float32", self.gravity_runtime)
        self.assertIn("dtype=wp.int32", self.gravity_runtime)

    def test_machine_result_classifies_failed_gate_for_next_iteration(self) -> None:
        self.assertIn('"failed_checks": failed_checks', self.runner)
        for decision in (
            "actuator_runtime_or_telemetry_failed",
            "joint_tracking_failed",
            "contact_safety_failed",
            "yahboom_api_accounting_failed",
            "neutral_reset_failed",
            "task_space_pregrasp_failed",
        ):
            self.assertIn(decision, self.runner)
        self.assertIn("def _write_runtime_failure(", self.runner)
        self.assertIn("class PregraspMachineAcceptanceError(", self.runner)
        self.assertIn(
            "if not isinstance(reported_error, PregraspMachineAcceptanceError):",
            self.runner,
        )
        self.assertIn("actuator_runtime_exception", self.runner)
        self.assertIn("pregrasp_runtime_exception", self.runner)
        self.assertIn(
            "dofbot_goal5_angled_pregrasp_runtime_failure",
            self.runner,
        )
        self.assertIn('"error_type": type(error).__name__', self.runner)
        self.assertIn('"message": str(error)', self.runner)

    def test_default_scene_preserves_original_effort_baseline(self) -> None:
        self.assertIn(
            "CONTROLLED_JOINT_EFFORT_LIMIT_SIM = 100.0",
            self.base_scene_cfg,
        )
        self.assertEqual(
            self.base_scene_cfg.count(
                "effort_limit_sim=CONTROLLED_JOINT_EFFORT_LIMIT_SIM"
            ),
            3,
        )

    def test_remote_wrappers_select_candidate_scene_and_pose_contract(self) -> None:
        for script in (self.run_script, self.view_script):
            self.assertIn(
                "goal5_angled_pregrasp_scene_candidate.json",
                script,
            )
            self.assertIn("goal5_angled_pregrasp.json", script)
            self.assertIn(
                "goal5_gravity_feed_forward_diagnostic.json",
                script,
            )
            self.assertIn(
                "gravity_feed_forward_result_2026-07-31.json",
                script,
            )
            self.assertIn("--actuator-config", script)
            self.assertIn("--actuator-result", script)
            self.assertIn("run_dofbot_pregrasp.py", script)
        self.assertIn("--cycles 1", self.run_script)
        self.assertIn("--headless", self.run_script)
        self.assertIn("[PREGRASP_EXIT_CODE]", self.run_script)
        self.assertIn('transport_exit_code="${PIPESTATUS[0]}"', self.run_script)
        self.assertIn("require_zero_exit_sentinel.sh", self.run_script)
        self.assertIn("--cycles -1", self.view_script)
        self.assertIn("--livestream 2", self.view_script)
        self.assertIn("--viz kit", self.view_script)


if __name__ == "__main__":
    unittest.main()
