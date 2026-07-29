from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from tools.dofbot_motion_config import compile_motion_config
from tools.dofbot_reaching import (
    ReachingConfigError,
    damped_least_squares_delta,
    evaluate_reaching_observations,
    load_reaching_config,
    next_state_controller_angles,
    parse_reaching_config,
)
from tools.preview_dofbot_reaching import build_preview

PROJECT_DIR = Path(__file__).resolve().parents[1]
REACHING_CONFIG_PATH = PROJECT_DIR / "configs/dofbot/reaching/goal4_fixed_tabletop.json"
ISAAC_RUNNER_PATH = PROJECT_DIR / "tools/run_dofbot_reaching.py"


class DofbotReachingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_config = json.loads(REACHING_CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, cls.source_sha256 = load_reaching_config(REACHING_CONFIG_PATH)

    def _observation(self, index: int, distance: float) -> dict[str, object]:
        target = self.config.approach_target_world_m
        wrist = (target[0] + distance, target[1], target[2])
        return {
            "step_index": index,
            "wrist_position_world_m": list(wrist),
            "target_position_world_m": list(target),
            "distance_m": distance,
            "angles_deg": [90.0, 90.0, 90.0, 90.0],
            "wrist_table_clearance_m": wrist[2] - self.config.table.top_z_m,
        }

    def _passing_result(self) -> dict[str, object]:
        scripted = [
            self._observation(0, 0.18),
            self._observation(1, 0.12),
        ]
        state = [
            self._observation(0, 0.16),
            self._observation(1, 0.08),
            self._observation(2, 0.035),
        ]
        scripted_calls = sum(
            len(sample.api_writes())
            for sample in compile_motion_config(self.config.scripted_baseline)
        )
        return evaluate_reaching_observations(
            self.config,
            end_effector_body_present=True,
            table_prim_present=True,
            target_prim_present=True,
            scripted_observations=scripted,
            state_observations=state,
            official_api_call_count=scripted_calls + 8 + 4,
            maximum_neutral_reset_error_deg=0.2,
        )

    def test_table_and_target_define_a_physical_fixed_scene(self) -> None:
        self.assertAlmostEqual(
            self.config.target_cube.bottom_z_m,
            self.config.table.top_z_m,
        )
        self.assertTrue(self.config.table.collision_enabled)
        self.assertTrue(self.config.target_cube.collision_enabled)
        self.assertTrue(self.config.target_cube.static)
        self.assertEqual(self.config.end_effector_body_name, "Wrist_Twist")
        self.assertGreater(
            self.config.approach_target_world_m[2],
            self.config.target_cube.top_z_m,
        )
        self.assertEqual(len(self.source_sha256), 64)

    def test_scripted_baseline_is_safe_boundary_only_actionchunk(self) -> None:
        samples = compile_motion_config(self.config.scripted_baseline)
        writes = [write for sample in samples for write in sample.api_writes()]
        self.assertEqual(samples[0].angles_deg, (90, 90, 90, 90))
        self.assertEqual(samples[-1].angles_deg, (90, 90, 90, 90))
        self.assertEqual(len(writes), 20)
        self.assertTrue(all(60 <= write.angle_deg <= 120 for write in writes))

    def test_parser_rejects_cube_that_does_not_rest_on_table(self) -> None:
        broken = copy.deepcopy(self.raw_config)
        broken["scene"]["target_cube"]["center_world_m"][2] += 0.01
        with self.assertRaisesRegex(ReachingConfigError, "rest exactly"):
            parse_reaching_config(broken)

    def test_parser_rejects_cube_off_table_or_table_inside_base_keepout(self) -> None:
        off_table = copy.deepcopy(self.raw_config)
        off_table["scene"]["target_cube"]["center_world_m"][0] = 0.3
        with self.assertRaisesRegex(ReachingConfigError, "footprint"):
            parse_reaching_config(off_table)

        overlap = copy.deepcopy(self.raw_config)
        overlap["scene"]["table"]["center_world_m"][1] = -0.2
        with self.assertRaisesRegex(ReachingConfigError, "base keepout"):
            parse_reaching_config(overlap)

    def test_parser_rejects_dynamic_target_or_unvalidated_end_effector(self) -> None:
        dynamic = copy.deepcopy(self.raw_config)
        dynamic["scene"]["target_cube"]["static"] = False
        with self.assertRaisesRegex(ReachingConfigError, "static"):
            parse_reaching_config(dynamic)

        wrong_body = copy.deepcopy(self.raw_config)
        wrong_body["end_effector"]["body_name"] = "Finger_Left_03"
        with self.assertRaisesRegex(ReachingConfigError, "Wrist_Twist"):
            parse_reaching_config(wrong_body)

    def test_parser_locks_control_interval_and_safe_envelope(self) -> None:
        for field, value in (
            ("command_duration_ms", 100),
            ("safe_angle_min_deg", 0),
            ("safe_angle_max_deg", 180),
            ("maximum_joint_delta_deg", 10.0),
        ):
            broken = copy.deepcopy(self.raw_config)
            broken["state_controller"][field] = value
            with self.subTest(field=field):
                with self.assertRaises(ReachingConfigError):
                    parse_reaching_config(broken)

    def test_damped_least_squares_has_expected_direction(self) -> None:
        jacobian = (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
        )
        delta = damped_least_squares_delta(
            jacobian,
            (0.1, -0.2, 0.3),
            damping=0.05,
        )
        self.assertGreater(delta[0], 0)
        self.assertLess(delta[1], 0)
        self.assertGreater(delta[2], 0)
        self.assertAlmostEqual(delta[3], 0.0)

    def test_state_step_is_bounded_and_expressed_as_absolute_api_angles(
        self,
    ) -> None:
        target = next_state_controller_angles(
            current_angles_deg=(90.0, 90.0, 90.0, 90.0),
            translation_jacobian=(
                (0.10, 0.00, 0.00, 0.00),
                (0.00, 0.10, 0.00, 0.00),
                (0.00, 0.00, 0.10, 0.05),
            ),
            position_error_m=(0.03, -0.02, -0.01),
            controller=self.config.state_controller,
        )
        self.assertTrue(all(isinstance(value, int) for value in target))
        self.assertTrue(
            all(
                abs(value - 90) <= math.ceil(self.config.state_controller.maximum_joint_delta_deg)
                for value in target
            )
        )
        self.assertNotEqual(target, (90, 90, 90, 90))

    def test_controller_rejects_bad_shape_nonfinite_or_unsafe_current_pose(
        self,
    ) -> None:
        with self.assertRaisesRegex(ReachingConfigError, "shape 3x4"):
            damped_least_squares_delta(
                ((1.0, 0.0),) * 3,
                (0.0, 0.0, 0.0),
                damping=0.05,
            )
        with self.assertRaisesRegex(ReachingConfigError, "finite"):
            damped_least_squares_delta(
                ((1.0, 0.0, 0.0, 0.0),) * 3,
                (math.nan, 0.0, 0.0),
                damping=0.05,
            )
        with self.assertRaisesRegex(ReachingConfigError, "safe envelope"):
            next_state_controller_angles(
                current_angles_deg=(59.0, 90.0, 90.0, 90.0),
                translation_jacobian=((1.0, 0.0, 0.0, 0.0),) * 3,
                position_error_m=(0.0, 0.0, 0.0),
                controller=self.config.state_controller,
            )

    def test_synthetic_reaching_result_passes_all_machine_checks(self) -> None:
        result = self._passing_result()
        self.assertTrue(result["machine_passed"])
        self.assertTrue(all(result["checks"].values()))
        self.assertAlmostEqual(result["state_final_distance_m"], 0.035)

    def test_reaching_gate_rejects_missed_target_clearance_or_reset(self) -> None:
        scripted = [self._observation(0, 0.18)]
        state = [
            self._observation(0, 0.16),
            self._observation(1, 0.14),
        ]
        state[1]["wrist_table_clearance_m"] = 0.0
        result = evaluate_reaching_observations(
            self.config,
            end_effector_body_present=True,
            table_prim_present=True,
            target_prim_present=True,
            scripted_observations=scripted,
            state_observations=state,
            official_api_call_count=0,
            maximum_neutral_reset_error_deg=2.0,
        )
        self.assertFalse(result["machine_passed"])
        self.assertFalse(result["checks"]["scripted_baseline_improved_distance"])
        self.assertFalse(result["checks"]["state_controller_improved_distance"])
        self.assertFalse(result["checks"]["state_controller_reached_approach_waypoint"])
        self.assertFalse(result["checks"]["wrist_stayed_above_table_clearance"])
        self.assertFalse(result["checks"]["returned_to_neutral"])

    def test_preview_is_local_only_and_never_claims_sim_or_grasp(self) -> None:
        preview = build_preview(reaching_config_path=REACHING_CONFIG_PATH)
        self.assertTrue(preview["acceptance"]["software_preparation_passed"])
        self.assertFalse(preview["acceptance"]["simulator_machine_passed"])
        self.assertFalse(preview["acceptance"]["visual_passed"])
        self.assertFalse(preview["scope"]["gpu_started"])
        self.assertFalse(preview["scope"]["real_hardware_commanded"])
        self.assertFalse(preview["scope"]["gripper_commanded"])
        self.assertFalse(preview["scope"]["target_cube_moved"])

    def test_isaac_runner_keeps_preflight_before_kit_and_uses_api_boundary(
        self,
    ) -> None:
        source = ISAAC_RUNNER_PATH.read_text(encoding="utf-8")
        self.assertLess(
            source.index("preflight_config, preflight_config_sha256"),
            source.index("app_launcher = AppLauncher(args_cli)"),
        )
        self.assertIn("get_jacobians", source)
        self.assertIn("Arm_serial_servo_write", source)
        self.assertNotIn("Arm_Lib", source)
        self.assertNotIn("CameraCfg", source)


if __name__ == "__main__":
    unittest.main()
