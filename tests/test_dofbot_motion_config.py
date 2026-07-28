from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from tools.dofbot_motion_config import (
    MAX_POSE_DELTA_DEG,
    NEUTRAL_ANGLES_DEG,
    MotionConfigError,
    compile_motion_config,
    evaluate_motion_config_observations,
    load_motion_config,
    parse_motion_config,
)
from tools.preview_dofbot_motion_config import build_preview

PROJECT_DIR = Path(__file__).resolve().parents[1]
MOTION_CONFIG_PATH = (
    PROJECT_DIR / "configs/dofbot/motions/safe_api_wave.json"
)
ISAAC_RUNNER_PATH = PROJECT_DIR / "tools/run_dofbot_motion_config.py"


class DofbotMotionConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_config = json.loads(MOTION_CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, cls.source_sha256 = load_motion_config(MOTION_CONFIG_PATH)
        cls.samples = compile_motion_config(cls.config)

    def _synthetic_observations(self) -> list[dict[str, object]]:
        return [
            {
                "sequence_index": sample.sequence_index,
                "target_angles_deg": list(sample.angles_deg),
                "observed_angles_deg": list(sample.angles_deg),
            }
            for sample in self.samples
        ]

    def test_example_compiles_to_expected_timeline_and_api_calls(self) -> None:
        self.assertEqual(self.config.name, "safe_api_wave")
        self.assertEqual(self.config.control_hz, 10)
        self.assertEqual(self.config.total_duration_ms, 12_400)
        self.assertEqual(len(self.samples), 124)
        self.assertEqual(
            sum(len(sample.api_writes()) for sample in self.samples),
            496,
        )
        self.assertEqual(self.samples[0].angles_deg, NEUTRAL_ANGLES_DEG)
        self.assertEqual(self.samples[-1].angles_deg, NEUTRAL_ANGLES_DEG)
        self.assertEqual(
            self.config.steps[1].angles_deg,
            (100, 76, 104, 104),
        )
        self.assertEqual(
            self.config.steps[3].angles_deg,
            (80, 104, 76, 76),
        )
        self.assertEqual(len(self.source_sha256), 64)

    def test_compiled_samples_move_no_more_than_one_degree_at_10_hz(self) -> None:
        previous = NEUTRAL_ANGLES_DEG
        for sample in self.samples:
            maximum_delta = max(
                abs(current - old)
                for current, old in zip(sample.angles_deg, previous, strict=True)
            )
            self.assertLessEqual(maximum_delta, 1)
            previous = sample.angles_deg

    def test_compiled_sample_expands_to_exact_yahboom_single_servo_shape(self) -> None:
        sample = next(sample for sample in self.samples if sample.angles_deg != (90,) * 4)
        writes = sample.api_writes()
        self.assertEqual([write.servo_id for write in writes], [1, 2, 3, 4])
        self.assertTrue(
            all(write.method == "Arm_serial_servo_write" for write in writes)
        )
        self.assertTrue(all(write.duration_ms == 100 for write in writes))

    def test_schema_rejects_missing_and_extra_top_level_keys(self) -> None:
        for broken in (
            {key: value for key, value in self.raw_config.items() if key != "steps"},
            {**self.raw_config, "backend": "hardware"},
        ):
            with self.subTest(keys=sorted(broken)):
                with self.assertRaisesRegex(MotionConfigError, "keys must match"):
                    parse_motion_config(broken)

    def test_schema_version_and_control_rate_are_fixed(self) -> None:
        for field, invalid in (
            ("schema_version", True),
            ("schema_version", 2),
            ("control_hz", True),
            ("control_hz", 20),
        ):
            broken = copy.deepcopy(self.raw_config)
            broken[field] = invalid
            with self.subTest(field=field, invalid=invalid):
                with self.assertRaises(MotionConfigError):
                    parse_motion_config(broken)

    def test_step_names_must_be_unique_lowercase_identifiers(self) -> None:
        broken_name = copy.deepcopy(self.raw_config)
        broken_name["steps"][1]["name"] = "Pose Positive"
        with self.assertRaisesRegex(MotionConfigError, "lowercase snake_case"):
            parse_motion_config(broken_name)

        duplicate = copy.deepcopy(self.raw_config)
        duplicate["steps"][1]["name"] = duplicate["steps"][0]["name"]
        with self.assertRaisesRegex(MotionConfigError, "duplicate step name"):
            parse_motion_config(duplicate)

    def test_angles_must_be_four_safe_integers(self) -> None:
        invalid_values = (
            [90, 90, 90],
            [90, 90, 90, 106],
            [90, 90, 90, 74],
            [90, 90, 90, 90.0],
            [90, 90, 90, True],
        )
        for invalid in invalid_values:
            broken = copy.deepcopy(self.raw_config)
            broken["steps"][1]["angles_deg"] = invalid
            with self.subTest(invalid=invalid):
                with self.assertRaises(MotionConfigError):
                    parse_motion_config(broken)

    def test_durations_are_bounded_and_aligned_to_control_interval(self) -> None:
        for field, invalid in (
            ("duration_ms", 0),
            ("duration_ms", 550),
            ("duration_ms", 5_100),
            ("duration_ms", True),
            ("hold_ms", -100),
            ("hold_ms", 50),
            ("hold_ms", 5_100),
        ):
            broken = copy.deepcopy(self.raw_config)
            broken["steps"][1][field] = invalid
            with self.subTest(field=field, invalid=invalid):
                with self.assertRaises(MotionConfigError):
                    parse_motion_config(broken)

    def test_first_and_last_steps_must_be_neutral(self) -> None:
        for step_index in (0, -1):
            broken = copy.deepcopy(self.raw_config)
            broken["steps"][step_index]["angles_deg"] = [91, 90, 90, 90]
            with self.subTest(step_index=step_index):
                with self.assertRaisesRegex(MotionConfigError, "neutral pose"):
                    parse_motion_config(broken)

    def test_config_requires_non_neutral_motion(self) -> None:
        broken = copy.deepcopy(self.raw_config)
        for step in broken["steps"]:
            step["angles_deg"] = [90, 90, 90, 90]
        with self.assertRaisesRegex(MotionConfigError, "non-neutral"):
            parse_motion_config(broken)

    def test_pose_transition_above_fifteen_degrees_fails_closed(self) -> None:
        broken = copy.deepcopy(self.raw_config)
        broken["steps"][2]["angles_deg"] = [84, 90, 90, 90]
        self.assertGreater(
            abs(
                broken["steps"][2]["angles_deg"][0]
                - broken["steps"][1]["angles_deg"][0]
            ),
            MAX_POSE_DELTA_DEG,
        )
        with self.assertRaisesRegex(MotionConfigError, "more than 15 degrees"):
            parse_motion_config(broken)

    def test_total_duration_above_sixty_seconds_fails_closed(self) -> None:
        broken = copy.deepcopy(self.raw_config)
        neutral_step = {
            "angles_deg": [90, 90, 90, 90],
            "duration_ms": 5_000,
            "hold_ms": 5_000,
        }
        extra_steps = [
            {**neutral_step, "name": f"neutral_extra_{index}"}
            for index in range(6)
        ]
        broken["steps"] = [
            broken["steps"][0],
            broken["steps"][1],
            broken["steps"][2],
            *extra_steps,
            broken["steps"][-1],
        ]
        with self.assertRaisesRegex(MotionConfigError, "total duration"):
            parse_motion_config(broken)

    def test_synthetic_execution_passes_machine_checks(self) -> None:
        result = evaluate_motion_config_observations(
            self.config,
            self.samples,
            self._synthetic_observations(),
        )
        self.assertTrue(result["machine_passed"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["maximum_checkpoint_error_deg"], 0.0)
        self.assertEqual(result["maximum_final_neutral_error_deg"], 0.0)

    def test_observation_count_and_schema_fail_closed(self) -> None:
        observations = self._synthetic_observations()
        with self.assertRaisesRegex(MotionConfigError, "count"):
            evaluate_motion_config_observations(
                self.config,
                self.samples,
                observations[:-1],
            )
        observations[0]["observed_angles_deg"] = [90, 90, 90]
        with self.assertRaisesRegex(MotionConfigError, "four values"):
            evaluate_motion_config_observations(
                self.config,
                self.samples,
                observations,
            )

    def test_nonfinite_or_out_of_envelope_observations_fail_acceptance(self) -> None:
        nonfinite = self._synthetic_observations()
        nonfinite[10]["observed_angles_deg"][0] = math.nan
        result = evaluate_motion_config_observations(
            self.config,
            self.samples,
            nonfinite,
        )
        self.assertFalse(result["machine_passed"])
        self.assertFalse(result["checks"]["all_observations_finite"])

        out_of_envelope = self._synthetic_observations()
        out_of_envelope[10]["observed_angles_deg"][0] = 107.0
        result = evaluate_motion_config_observations(
            self.config,
            self.samples,
            out_of_envelope,
        )
        self.assertFalse(result["checks"]["observations_within_safe_envelope"])

    def test_missed_step_target_and_final_reset_fail_acceptance(self) -> None:
        missed_target = self._synthetic_observations()
        final_positive_index = max(
            index
            for index, sample in enumerate(self.samples)
            if sample.step_name == "pose_positive"
        )
        missed_target[final_positive_index]["observed_angles_deg"][0] = 92.0
        result = evaluate_motion_config_observations(
            self.config,
            self.samples,
            missed_target,
        )
        self.assertFalse(result["checks"]["step_targets_reached"])

        failed_reset = self._synthetic_observations()
        failed_reset[-1]["observed_angles_deg"][0] = 92.0
        result = evaluate_motion_config_observations(
            self.config,
            self.samples,
            failed_reset,
        )
        self.assertFalse(result["checks"]["returned_to_neutral"])

    def test_preview_passes_compile_only_and_never_claims_sim_or_hardware(self) -> None:
        preview = build_preview(motion_config_path=MOTION_CONFIG_PATH)
        self.assertTrue(preview["acceptance"]["software_compile_passed"])
        self.assertFalse(preview["acceptance"]["simulator_machine_passed"])
        self.assertFalse(preview["acceptance"]["visual_passed"])
        self.assertFalse(preview["acceptance"]["physical_hardware_passed"])
        self.assertFalse(preview["scope"]["real_hardware_commanded"])
        self.assertFalse(preview["scope"]["gpu_started"])

    def test_isaac_runner_validates_config_before_starting_kit(self) -> None:
        source = ISAAC_RUNNER_PATH.read_text(encoding="utf-8")
        self.assertLess(
            source.index("preflight_config, preflight_config_sha256"),
            source.index("app_launcher = AppLauncher(args_cli)"),
        )


if __name__ == "__main__":
    unittest.main()
