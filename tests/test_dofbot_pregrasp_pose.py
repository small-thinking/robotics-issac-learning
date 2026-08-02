from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from tools.dofbot_pregrasp_pose import (
    EXPECTED_CLOSING_CONTROL,
    VALIDATED_JOINT_CANDIDATE_CONTROL_MODE,
    PoseCommand,
    PregraspPoseError,
    cubic_smoothstep_motion_contract,
    cubic_smoothstep_motion_state,
    derive_grasp_frame,
    direction_error_vector,
    evaluate_pregrasp_observation,
    load_pregrasp_pose_config,
    maximum_joint_tracking_error_deg,
    next_pose_command,
    next_pregrasp_command,
    parse_pregrasp_pose_config,
    quantize_pose_command,
    signed_point_box_distance,
    validated_joint_candidate_command_reached,
    weighted_pose_delta,
)
from tools.dofbot_reaching import load_reaching_config
from tools.preview_dofbot_pregrasp_pose import build_preview

PROJECT_DIR = Path(__file__).resolve().parents[1]
POSE_CONFIG_PATH = (
    PROJECT_DIR / "configs/dofbot/pregrasp/goal5_pose_aware_pregrasp.json"
)
ANGLED_POSE_CONFIG_PATH = (
    PROJECT_DIR / "configs/dofbot/pregrasp/goal5_angled_pregrasp.json"
)
SCENE_CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json"
)
ANGLED_SCENE_CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json"
)
COMMAND_SPACE_CONTRACT_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/pregrasp_command_space_contract.json"
)
TRACKING_FAILURE_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json"
)


class DofbotPregraspPoseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(POSE_CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, cls.config_sha256 = load_pregrasp_pose_config(
            POSE_CONFIG_PATH
        )
        cls.scene, cls.scene_sha256 = load_reaching_config(SCENE_CONFIG_PATH)

    def _frame(
        self,
        *,
        origin: tuple[float, float, float] = (0.0, 0.25, 0.195),
        reverse_closing: bool = False,
    ):
        left_x, right_x = (-0.025, 0.025)
        if reverse_closing:
            left_x, right_x = right_x, left_x
        return derive_grasp_frame(
            wrist_position_world_m=(origin[0], origin[1], origin[2] + 0.06),
            left_tip_position_world_m=(left_x, origin[1], origin[2]),
            right_tip_position_world_m=(right_x, origin[1], origin[2]),
            config=self.config.grasp_frame,
        )

    def _body_positions(self) -> dict[str, tuple[float, float, float]]:
        return {
            "link2": (0.0, 0.08, 0.30),
            "link3": (0.0, 0.12, 0.28),
            "link4": (0.0, 0.18, 0.27),
            "Wrist_Twist": (0.0, 0.25, 0.255),
            "Finger_Left_01": (-0.02, 0.24, 0.24),
            "Finger_Right_01": (0.02, 0.24, 0.24),
            "Finger_Left_02": (-0.023, 0.245, 0.215),
            "Finger_Right_02": (0.023, 0.245, 0.215),
            "Finger_Left_03": (-0.025, 0.25, 0.195),
            "Finger_Right_03": (0.025, 0.25, 0.195),
        }

    def _evaluate(
        self,
        *,
        frame=None,
        body_positions=None,
        angles_deg=(90.0, 80.0, 80.0, 90.0),
        maximum_contact_force_n: float = 0.0,
    ) -> dict[str, object]:
        return evaluate_pregrasp_observation(
            config=self.config,
            frame=frame or self._frame(),
            body_positions_world_m=body_positions or self._body_positions(),
            table_center_world_m=self.scene.table.center_world_m,
            table_size_m=self.scene.table.size_m,
            target_center_world_m=self.scene.target_cube.center_world_m,
            target_size_m=self.scene.target_cube.size_m,
            target_is_static=True,
            angles_deg=angles_deg,
            velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
            accelerations_deg_s2=(0.0, 0.0, 0.0, 0.0),
            maximum_contact_force_n=maximum_contact_force_n,
        )

    def test_grasp_frame_uses_terminal_finger_midpoint_and_down_axis(self) -> None:
        frame = self._frame()
        self.assertEqual(frame.origin_world_m, (0.0, 0.25, 0.195))
        self.assertEqual(frame.closing_axis_world_unit, (1.0, 0.0, 0.0))
        self.assertEqual(frame.approach_axis_world_unit, (0.0, 0.0, -1.0))
        self.assertEqual(frame.lateral_axis_world_unit, (0.0, -1.0, 0.0))
        self.assertAlmostEqual(frame.finger_separation_m, 0.05)
        self.assertAlmostEqual(
            sum(
                left * right
                for left, right in zip(
                    frame.approach_axis_world_unit,
                    frame.closing_axis_world_unit,
                    strict=True,
                )
            ),
            0.0,
        )

    def test_target_matches_lower_farther_scene_waypoint(self) -> None:
        self.assertEqual(
            self.config.target_pose.position_world_m,
            self.scene.approach_target_world_m,
        )
        self.assertEqual(
            self.config.source_contracts.scene_config_sha256,
            self.scene_sha256,
        )
        self.assertEqual(self.config.target_pose.approach_axis_world_unit, (0.0, 0.0, -1.0))
        self.assertEqual(self.config.target_pose.closing_axis_world_unit, (1.0, 0.0, 0.0))

    def test_wrist_twist_is_monitor_only_and_not_a_hidden_fifth_control(self) -> None:
        self.assertEqual(
            self.config.target_pose.closing_axis_control,
            EXPECTED_CLOSING_CONTROL,
        )
        self.assertEqual(
            self.config.solver.controlled_joint_names,
            ("joint1", "joint2", "joint3", "joint4"),
        )
        self.assertNotIn(
            "Wrist_Twist_RevoluteJoint",
            self.config.solver.controlled_joint_names,
        )

    def test_machine_tracking_error_uses_observed_and_api_joint_state(self) -> None:
        self.assertAlmostEqual(
            maximum_joint_tracking_error_deg(
                observed_angles_deg=(90.092, 66.987, 70.641, 69.828),
                command_angles_deg=(90.0, 66.0, 66.0, 66.0),
            ),
            4.641,
        )
        self.assertEqual(
            self.config.acceptance.maximum_final_joint_tracking_error_deg,
            1.0,
        )

    def test_machine_tracking_error_rejects_wrong_vector_shape(self) -> None:
        with self.assertRaisesRegex(
            PregraspPoseError,
            "must contain four values",
        ):
            maximum_joint_tracking_error_deg(
                observed_angles_deg=(90.0, 90.0, 90.0),
                command_angles_deg=(90.0, 90.0, 90.0, 90.0),
            )

    def test_parser_rejects_loose_final_joint_tracking_gate(self) -> None:
        loose = copy.deepcopy(self.raw)
        loose["acceptance"]["maximum_final_joint_tracking_error_deg"] = 3.0
        with self.assertRaisesRegex(
            PregraspPoseError,
            "must be in",
        ):
            parse_pregrasp_pose_config(loose)

    def test_remote_tracking_failure_requires_discriminating_calibration(self) -> None:
        evidence = json.loads(TRACKING_FAILURE_PATH.read_text(encoding="utf-8"))
        control = evidence["control"]
        follow_up = evidence["local_follow_up"]
        self.assertAlmostEqual(
            maximum_joint_tracking_error_deg(
                observed_angles_deg=control["final_observed_angles_deg"],
                command_angles_deg=control["final_api_command_angles_deg"],
            ),
            control["maximum_observed_command_error_deg"],
        )
        self.assertGreater(
            control["maximum_observed_command_error_deg"],
            follow_up["tracking_gate_retained_deg"],
        )
        self.assertEqual(
            follow_up["default_controlled_joint_effort_limit_sim"],
            100.0,
        )
        self.assertEqual(
            follow_up["required_diagnostic_cases"],
            [
                "gravity_on_effort_100",
                "gravity_off_effort_100",
                "gravity_on_effort_250",
            ],
        )
        self.assertFalse(follow_up["pregrasp_rerun_authorized"])
        self.assertFalse(follow_up["candidate_isaac_machine_passed"])
        self.assertFalse(follow_up["candidate_visual_passed"])

    def test_parser_rejects_fabricated_grasp_body_or_wrist_control(self) -> None:
        wrong_body = copy.deepcopy(self.raw)
        wrong_body["grasp_frame"]["left_tip_body_name"] = "Finger_Left_02"
        with self.assertRaisesRegex(PregraspPoseError, "Finger_Left_03"):
            parse_pregrasp_pose_config(wrong_body)

        hidden_control = copy.deepcopy(self.raw)
        hidden_control["solver"]["controlled_joint_names"].append(
            "Wrist_Twist_RevoluteJoint"
        )
        with self.assertRaisesRegex(PregraspPoseError, "joint1-joint4"):
            parse_pregrasp_pose_config(hidden_control)

        fake_closing = copy.deepcopy(self.raw)
        fake_closing["target_pose"]["closing_axis_control"] = "controlled"
        with self.assertRaisesRegex(PregraspPoseError, "monitor_only"):
            parse_pregrasp_pose_config(fake_closing)

    def test_frame_rejects_collapsed_or_collinear_fingers(self) -> None:
        with self.assertRaisesRegex(PregraspPoseError, "separation"):
            derive_grasp_frame(
                wrist_position_world_m=(0.0, 0.0, 0.1),
                left_tip_position_world_m=(0.0, 0.0, 0.0),
                right_tip_position_world_m=(0.0, 0.0, 0.0),
                config=self.config.grasp_frame,
            )
        with self.assertRaisesRegex(PregraspPoseError, "collinear"):
            derive_grasp_frame(
                wrist_position_world_m=(-0.05, 0.0, 0.0),
                left_tip_position_world_m=(-0.025, 0.0, 0.0),
                right_tip_position_world_m=(0.025, 0.0, 0.0),
                config=self.config.grasp_frame,
            )

    def test_opposite_direction_error_is_finite_pi_rotation(self) -> None:
        error = direction_error_vector((0.0, 0.0, 1.0), (0.0, 0.0, -1.0))
        self.assertTrue(all(math.isfinite(value) for value in error))
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in error)), math.pi)

    def test_weighted_solver_includes_preferred_posture_bias(self) -> None:
        delta = weighted_pose_delta(
            pose_jacobian=((0.0, 0.0, 0.0, 0.0),) * 6,
            position_error_m=(0.0, 0.0, 0.0),
            approach_error_rad=(0.0, 0.0, 0.0),
            current_angles_deg=(90.0, 90.0, 90.0, 90.0),
            solver=self.config.solver,
        )
        self.assertAlmostEqual(delta[0], 0.0)
        self.assertLess(delta[1], 0.0)
        self.assertLess(delta[2], 0.0)
        self.assertAlmostEqual(delta[3], 0.0)

    def test_pose_command_limits_delta_velocity_acceleration_and_margin(self) -> None:
        frame = self._frame(origin=(0.0, 0.23, 0.215))
        command = next_pose_command(
            frame=frame,
            pose_jacobian=(
                (0.10, 0.00, 0.00, 0.00),
                (0.00, 0.10, 0.00, 0.00),
                (0.00, 0.00, 0.10, 0.05),
                (0.00, 0.50, 0.00, 0.00),
                (0.00, 0.00, 0.50, 0.20),
                (0.30, 0.00, 0.00, 0.30),
            ),
            current_angles_deg=(90.0, 90.0, 90.0, 90.0),
            previous_velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
            solver=self.config.solver,
            target=self.config.target_pose,
        )
        self.assertTrue(any(abs(value) > 0.0 for value in command.raw_delta_deg))
        self.assertTrue(
            all(
                abs(after - before) <= self.config.solver.maximum_joint_delta_deg
                for after, before in zip(
                    command.angles_deg,
                    (90.0, 90.0, 90.0, 90.0),
                    strict=True,
                )
            )
        )
        acceleration_step_velocity = (
            self.config.solver.maximum_joint_acceleration_deg_s2
            * self.config.solver.control_dt_s
        )
        self.assertTrue(
            all(
                abs(value) <= acceleration_step_velocity + 1e-9
                for value in command.velocities_deg_s
            )
        )
        self.assertTrue(all(68.0 <= value <= 112.0 for value in command.angles_deg))
        quantized = quantize_pose_command(
            command,
            previous_command_angles_deg=(90.0, 90.0, 90.0, 90.0),
            previous_velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
            solver=self.config.solver,
        )
        self.assertTrue(all(value.is_integer() for value in quantized.angles_deg))
        self.assertTrue(
            all(
                abs(value) / self.config.solver.control_dt_s
                <= self.config.solver.maximum_joint_acceleration_deg_s2 + 1e-9
                for value in quantized.velocities_deg_s
            )
        )

    def test_angled_candidate_reaches_exact_api_target_despite_tracking_lag(
        self,
    ) -> None:
        angled, _ = load_pregrasp_pose_config(ANGLED_POSE_CONFIG_PATH)
        self.assertEqual(
            angled.solver.control_mode,
            VALIDATED_JOINT_CANDIDATE_CONTROL_MODE,
        )
        remote_tracking_lag = (
            89.98016199403266,
            66.32828212931207,
            70.52938976136163,
            71.53466724868787,
        )
        previous_command = (90.0, 90.0, 90.0, 90.0)
        previous_velocity = (0.0, 0.0, 0.0, 0.0)
        trajectory = []
        for _ in range(angled.solver.maximum_steps):
            command = next_pregrasp_command(
                frame=self._frame(origin=(0.0, 0.20, 0.31)),
                pose_jacobian=((0.0, 0.0, 0.0, 0.0),) * 6,
                observed_angles_deg=remote_tracking_lag,
                previous_command_angles_deg=previous_command,
                previous_command_velocities_deg_s=previous_velocity,
                solver=angled.solver,
                target=angled.target_pose,
            )
            trajectory.append(command)
            previous_command = command.angles_deg
            previous_velocity = command.velocities_deg_s
            if validated_joint_candidate_command_reached(
                command_angles_deg=previous_command,
                command_velocities_deg_s=previous_velocity,
                solver=angled.solver,
            ):
                break
        self.assertEqual(trajectory[0].angles_deg, (90.0, 88.0, 88.0, 88.0))
        self.assertEqual(
            trajectory[-1].angles_deg,
            angled.solver.preferred_angles_deg,
        )
        self.assertEqual(
            trajectory[-1].velocities_deg_s,
            (0.0, 0.0, 0.0, 0.0),
        )
        self.assertNotEqual(
            trajectory[-1].angles_deg,
            (90.0, 66.0, 68.0, 69.0),
        )
        self.assertLess(len(trajectory), angled.solver.maximum_steps)

    def test_lower_probe_boundary_target_fails_before_launch(self) -> None:
        lower_probe = json.loads(
            ANGLED_POSE_CONFIG_PATH.read_text(encoding="utf-8")
        )
        lower_probe["solver"]["preferred_angles_deg"] = [
            90.0,
            66.0,
            64.0,
            64.0,
        ]
        with self.assertRaisesRegex(PregraspPoseError, "braking reserve"):
            parse_pregrasp_pose_config(lower_probe)

    def test_direct_next_pose_command_rejects_candidate_mode(self) -> None:
        angled, _ = load_pregrasp_pose_config(ANGLED_POSE_CONFIG_PATH)
        with self.assertRaisesRegex(PregraspPoseError, "cartesian_pose_ik"):
            next_pose_command(
                frame=self._frame(origin=(0.0, 0.20, 0.31)),
                pose_jacobian=((0.0, 0.0, 0.0, 0.0),) * 6,
                current_angles_deg=(90.0, 66.0, 70.0, 72.0),
                previous_velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
                solver=angled.solver,
                target=angled.target_pose,
            )

    def test_candidate_observation_is_safety_input_not_command_state(self) -> None:
        angled, _ = load_pregrasp_pose_config(ANGLED_POSE_CONFIG_PATH)
        common = {
            "frame": self._frame(origin=(0.0, 0.20, 0.31)),
            "pose_jacobian": ((0.0, 0.0, 0.0, 0.0),) * 6,
            "previous_command_angles_deg": (90.0, 72.0, 72.0, 72.0),
            "previous_command_velocities_deg_s": (
                0.0,
                -20.0,
                -20.0,
                -20.0,
            ),
            "solver": angled.solver,
            "target": angled.target_pose,
        }
        first = next_pregrasp_command(
            observed_angles_deg=(90.0, 66.3, 70.5, 71.5),
            **common,
        )
        second = next_pregrasp_command(
            observed_angles_deg=(90.0, 72.0, 75.0, 78.0),
            **common,
        )
        self.assertEqual(first.angles_deg, second.angles_deg)
        self.assertEqual(first.velocities_deg_s, second.velocities_deg_s)
        with self.assertRaisesRegex(PregraspPoseError, "safe envelope"):
            next_pregrasp_command(
                observed_angles_deg=(90.0, 59.9, 70.5, 71.5),
                **common,
            )

    def test_quantizer_brakes_before_api_command_limit(self) -> None:
        desired = PoseCommand(
            angles_deg=(90.0, 60.0, 60.0, 60.0),
            velocities_deg_s=(0.0, -20.0, -20.0, -20.0),
            raw_delta_deg=(0.0, -4.0, -4.0, -4.0),
            position_error_m=(0.0, 0.0, -0.1),
            approach_error_rad=(0.0, 0.0, 0.0),
        )
        braking = quantize_pose_command(
            desired,
            previous_command_angles_deg=(90.0, 72.0, 75.0, 83.0),
            previous_velocities_deg_s=(0.0, -20.0, -20.0, -15.0),
            solver=self.config.solver,
        )
        self.assertEqual(braking.angles_deg, (90.0, 70.0, 72.0, 79.0))
        near_limit = quantize_pose_command(
            desired,
            previous_command_angles_deg=(90.0, 69.0, 69.0, 69.0),
            previous_velocities_deg_s=(0.0, -5.0, -5.0, -5.0),
            solver=self.config.solver,
        )
        self.assertEqual(near_limit.angles_deg, (90.0, 69.0, 69.0, 69.0))

    def test_pose_solver_rejects_wrong_jacobian_or_unsafe_pose(self) -> None:
        with self.assertRaisesRegex(PregraspPoseError, "shape 6x4"):
            weighted_pose_delta(
                pose_jacobian=((1.0, 0.0),) * 6,
                position_error_m=(0.0, 0.0, 0.0),
                approach_error_rad=(0.0, 0.0, 0.0),
                current_angles_deg=(90.0, 90.0, 90.0, 90.0),
                solver=self.config.solver,
            )
        with self.assertRaisesRegex(PregraspPoseError, "safe envelope"):
            next_pose_command(
                frame=self._frame(),
                pose_jacobian=((0.0, 0.0, 0.0, 0.0),) * 6,
                current_angles_deg=(59.0, 90.0, 90.0, 90.0),
                previous_velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
                solver=self.config.solver,
                target=self.config.target_pose,
            )

    def test_safe_synthetic_pregrasp_observation_passes(self) -> None:
        result = self._evaluate()
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["checks"].values()))
        self.assertAlmostEqual(result["position_error_m"], 0.0)
        self.assertAlmostEqual(result["approach_error_deg"], 0.0)
        self.assertAlmostEqual(result["closing_error_deg"], 0.0)

    def test_observed_angles_use_physical_limits_not_command_margin(self) -> None:
        tracking_overshoot = self._evaluate(
            angles_deg=(90.0, 67.5, 64.6, 77.8)
        )
        self.assertTrue(tracking_overshoot["passed"])
        self.assertTrue(
            tracking_overshoot["checks"][
                "joint_angles_remain_within_safe_limits"
            ]
        )
        unsafe = self._evaluate(angles_deg=(90.0, 59.9, 80.0, 90.0))
        self.assertFalse(
            unsafe["checks"]["joint_angles_remain_within_safe_limits"]
        )

    def test_collision_proxy_and_fixed_closing_axis_fail_closed(self) -> None:
        collision_positions = self._body_positions()
        collision_positions["Finger_Left_03"] = (-0.01, 0.25, 0.105)
        collision_positions["Finger_Right_03"] = (0.01, 0.25, 0.105)
        collision = self._evaluate(body_positions=collision_positions)
        self.assertFalse(collision["passed"])
        self.assertFalse(
            collision["checks"]["terminal_finger_centers_remain_precontact"]
        )

        reversed_frame = self._frame(reverse_closing=True)
        reversed_result = self._evaluate(frame=reversed_frame)
        self.assertFalse(reversed_result["passed"])
        self.assertFalse(
            reversed_result["checks"][
                "fixed_closing_axis_is_acceptable_without_wrist_command"
            ]
        )

    def test_contact_reporter_force_fails_closed_before_contact(self) -> None:
        result = self._evaluate(
            maximum_contact_force_n=(
                self.config.collision.maximum_contact_force_n + 0.01
            )
        )
        self.assertFalse(result["passed"])
        self.assertFalse(
            result["checks"][
                "contact_reporter_force_remains_below_threshold"
            ]
        )

    def test_signed_box_distance_distinguishes_clearance_and_penetration(self) -> None:
        self.assertAlmostEqual(
            signed_point_box_distance(
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                (0.1, 0.1, 0.1),
            ),
            -0.05,
        )
        self.assertAlmostEqual(
            signed_point_box_distance(
                (0.0, 0.0, 0.10),
                (0.0, 0.0, 0.0),
                (0.1, 0.1, 0.1),
            ),
            0.05,
        )

    def test_local_preview_passes_without_claiming_remote_or_contact(self) -> None:
        report = build_preview(
            pose_config_path=POSE_CONFIG_PATH,
            scene_config_path=SCENE_CONFIG_PATH,
            asset_contract_path=PROJECT_DIR / "artifacts/dofbot/asset_contract.json",
        )
        self.assertTrue(report["acceptance"]["local_preparation_passed"])
        self.assertEqual(len(report["acceptance"]["checks"]), 27)
        self.assertTrue(all(report["acceptance"]["checks"].values()))
        self.assertEqual(
            report["actuator_runtime"]["selected_case_name"],
            "bounded_gravity_feed_forward",
        )
        self.assertTrue(
            report["acceptance"]["checks"][
                "gravity_feed_forward_applies_after_pd_write_before_step"
            ]
        )
        self.assertFalse(report["acceptance"]["candidate_isaac_machine_passed"])
        self.assertFalse(report["acceptance"]["candidate_visual_passed"])
        self.assertFalse(report["acceptance"]["contact_or_grasp_authorized"])
        self.assertFalse(report["scope"]["gpu_started"])
        self.assertFalse(report["scope"]["isaac_started"])
        self.assertFalse(report["scope"]["wrist_twist_commanded"])
        self.assertFalse(report["scope"]["gripper_commanded"])

    def test_angled_preview_reaches_exact_stopped_candidate(self) -> None:
        report = build_preview(
            pose_config_path=ANGLED_POSE_CONFIG_PATH,
            scene_config_path=ANGLED_SCENE_CONFIG_PATH,
            asset_contract_path=PROJECT_DIR / "artifacts/dofbot/asset_contract.json",
        )
        self.assertTrue(report["acceptance"]["local_preparation_passed"])
        self.assertTrue(
            report["acceptance"]["checks"][
                "validated_candidate_reaches_exact_stopped_api_target"
            ]
        )
        self.assertEqual(
            report["solver_probe"]["command"]["angles_deg"],
            [90.0, 66.0, 66.0, 66.0],
        )
        self.assertEqual(
            report["solver_probe"]["command"]["velocities_deg_s"],
            [0.0, 0.0, 0.0, 0.0],
        )
        self.assertEqual(
            len(report["solver_probe"]["command_trajectory"]),
            1,
        )
        motion = report["solver_probe"]["candidate_backend_motion_contract"]
        self.assertEqual(motion["duration_s"], 2.0)
        self.assertEqual(motion["maximum_peak_velocity_deg_s"], 18.0)
        self.assertEqual(motion["maximum_peak_acceleration_deg_s2"], 36.0)
        checked_in = json.loads(
            COMMAND_SPACE_CONTRACT_PATH.read_text(encoding="utf-8")
        )
        normalized = copy.deepcopy(report)
        for source in normalized["sources"].values():
            source_path = Path(source["path"])
            if source_path.is_absolute():
                source["path"] = str(source_path.relative_to(PROJECT_DIR))
        self.assertEqual(normalized, checked_in)

    def test_cubic_smoothstep_contract_captures_internal_motion(self) -> None:
        contract = cubic_smoothstep_motion_contract(
            start_angles_deg=(90.0, 90.0, 90.0, 90.0),
            goal_angles_deg=(90.0, 66.0, 66.0, 66.0),
            duration_s=2.0,
        )
        self.assertEqual(
            contract["peak_velocity_deg_s"],
            [0.0, 18.0, 18.0, 18.0],
        )
        self.assertEqual(
            contract["peak_acceleration_deg_s2"],
            [0.0, 36.0, 36.0, 36.0],
        )
        velocity, acceleration = cubic_smoothstep_motion_state(
            start_angles_deg=(90.0, 90.0, 90.0, 90.0),
            goal_angles_deg=(90.0, 66.0, 66.0, 66.0),
            duration_s=2.0,
            elapsed_s=1.0,
        )
        self.assertEqual(velocity, (0.0, -18.0, -18.0, -18.0))
        self.assertEqual(acceleration, (0.0, 0.0, 0.0, 0.0))

    def test_cubic_smoothstep_exposes_rejected_200ms_step_profile(self) -> None:
        contract = cubic_smoothstep_motion_contract(
            start_angles_deg=(90.0, 88.0, 88.0, 88.0),
            goal_angles_deg=(90.0, 84.0, 84.0, 84.0),
            duration_s=0.2,
        )
        self.assertEqual(contract["maximum_peak_velocity_deg_s"], 30.0)
        self.assertAlmostEqual(
            contract["maximum_peak_acceleration_deg_s2"],
            600.0,
        )


if __name__ == "__main__":
    unittest.main()
