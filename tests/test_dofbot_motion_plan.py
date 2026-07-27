from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from tools.dofbot_motion_plan import (
    CONTROLLED_JOINT_NAMES,
    MAX_AMPLITUDE_RAD,
    MotionPlanError,
    assert_compatible_asset_contracts,
    build_motion_plan,
    evaluate_motion_observations,
    iter_plan_samples,
    validate_recorded_asset_contract,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
ASSET_CONTRACT_PATH = PROJECT_DIR / "artifacts/dofbot/asset_contract.json"


class DofbotMotionPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.asset_contract = json.loads(ASSET_CONTRACT_PATH.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.plan = build_motion_plan(self.asset_contract)

    def _synthetic_observations(self) -> list[dict[str, object]]:
        return [
            {
                "elapsed_s": sample.elapsed_s,
                "segment": sample.segment_name,
                "target_positions_rad": dict(sample.target_positions_rad),
                "observed_positions_rad": dict(sample.target_positions_rad),
            }
            for sample in iter_plan_samples(self.plan, sample_hz=10.0)
        ]

    def test_plan_uses_only_four_finite_limit_arm_joints(self) -> None:
        validate_recorded_asset_contract(self.asset_contract)
        self.assertEqual(
            self.plan.controlled_joint_names,
            CONTROLLED_JOINT_NAMES,
        )
        self.assertAlmostEqual(self.plan.amplitude_rad, math.radians(5.0))
        self.assertAlmostEqual(self.plan.total_duration_s, 41.0)
        for joint in self.plan.controlled_joints:
            self.assertLess(abs(joint.lower_rad), 10.0)
            self.assertLess(abs(joint.upper_rad), 10.0)
            self.assertGreater(
                joint.minimum_available_margin_rad - self.plan.amplitude_rad,
                self.plan.required_limit_margin_rad,
            )

    def test_each_single_joint_sine_is_isolated_and_reaches_both_signs(self) -> None:
        samples = iter_plan_samples(self.plan, sample_hz=60.0)
        defaults = {joint.name: joint.default_rad for joint in self.plan.controlled_joints}
        for active_joint in CONTROLLED_JOINT_NAMES:
            segment_samples = [
                sample for sample in samples if sample.segment_name == f"{active_joint}_sine"
            ]
            deltas = [
                sample.target_positions_rad[active_joint] - defaults[active_joint]
                for sample in segment_samples
            ]
            self.assertAlmostEqual(max(deltas), MAX_AMPLITUDE_RAD, places=10)
            self.assertAlmostEqual(min(deltas), -MAX_AMPLITUDE_RAD, places=10)
            for sample in segment_samples:
                for inactive_joint in CONTROLLED_JOINT_NAMES:
                    if inactive_joint != active_joint:
                        self.assertEqual(
                            sample.target_positions_rad[inactive_joint],
                            defaults[inactive_joint],
                        )

    def test_synthetic_tracking_passes_all_machine_checks(self) -> None:
        result = evaluate_motion_observations(
            self.plan,
            self._synthetic_observations(),
        )
        self.assertTrue(result["machine_passed"])
        self.assertTrue(all(result["checks"].values()))

    def test_missing_controlled_joint_fails_closed(self) -> None:
        broken = copy.deepcopy(self.asset_contract)
        broken["articulation"]["joint_names"][0] = "renamed_joint"
        with self.assertRaisesRegex(MotionPlanError, "controlled joints missing"):
            build_motion_plan(broken)

    def test_unbounded_controlled_joint_limit_fails_closed(self) -> None:
        broken = copy.deepcopy(self.asset_contract)
        broken["articulation"]["joint_position_limits_rad"][0] = [
            -3.4028234663852886e38,
            3.4028234663852886e38,
        ]
        with self.assertRaisesRegex(MotionPlanError, "unbounded sentinel"):
            build_motion_plan(broken)

    def test_insufficient_limit_margin_fails_closed(self) -> None:
        broken = copy.deepcopy(self.asset_contract)
        broken["articulation"]["joint_position_limits_rad"][2] = [-0.2, 0.2]
        with self.assertRaisesRegex(MotionPlanError, "does not have enough range"):
            build_motion_plan(broken)

    def test_motion_above_five_degrees_fails_closed(self) -> None:
        with self.assertRaisesRegex(MotionPlanError, "amplitude must be"):
            build_motion_plan(
                self.asset_contract,
                amplitude_rad=math.radians(5.01),
            )

    def test_unaccepted_goal_one_contract_fails_closed(self) -> None:
        broken = copy.deepcopy(self.asset_contract)
        broken["acceptance"]["passed"] = False
        with self.assertRaisesRegex(MotionPlanError, "acceptance did not pass"):
            validate_recorded_asset_contract(broken)

    def test_nonofficial_asset_contract_fails_closed(self) -> None:
        broken = copy.deepcopy(self.asset_contract)
        broken["asset"]["relative_usd_path"] = "Robots/Other/robot.usd"
        with self.assertRaisesRegex(MotionPlanError, "not the official DOFBOT"):
            validate_recorded_asset_contract(broken)

    def test_live_contract_drift_fails_closed(self) -> None:
        drifted = copy.deepcopy(self.asset_contract)
        drifted["articulation"]["default_joint_positions_rad"][1] = 0.01
        with self.assertRaisesRegex(MotionPlanError, "live default_rad differs"):
            assert_compatible_asset_contracts(self.asset_contract, drifted)

    def test_reset_error_over_one_degree_fails_machine_acceptance(self) -> None:
        observations = self._synthetic_observations()
        observations[-1]["observed_positions_rad"]["joint1"] = math.radians(1.1)
        result = evaluate_motion_observations(self.plan, observations)
        self.assertFalse(result["machine_passed"])
        self.assertFalse(result["checks"]["reset_to_default_within_tolerance"])

    def test_inactive_joint_drift_fails_machine_acceptance(self) -> None:
        observations = self._synthetic_observations()
        row = next(row for row in observations if row["segment"] == "joint1_sine")
        row["observed_positions_rad"]["joint2"] = math.radians(1.1)
        result = evaluate_motion_observations(self.plan, observations)
        self.assertFalse(result["machine_passed"])
        self.assertFalse(result["checks"]["inactive_joints_hold_default"])

    def test_active_joint_overshoot_fails_machine_acceptance(self) -> None:
        observations = self._synthetic_observations()
        row = next(row for row in observations if row["segment"] == "joint1_sine")
        row["observed_positions_rad"]["joint1"] = math.radians(6.1)
        result = evaluate_motion_observations(self.plan, observations)
        self.assertFalse(result["machine_passed"])
        self.assertFalse(result["checks"]["observations_within_command_envelope"])

    def test_reversed_observed_sign_fails_machine_acceptance(self) -> None:
        observations = self._synthetic_observations()
        for row in observations:
            if row["segment"] == "joint2_sine":
                row["observed_positions_rad"]["joint2"] *= -1.0
        result = evaluate_motion_observations(self.plan, observations)
        self.assertFalse(result["machine_passed"])
        self.assertFalse(result["checks"]["observed_sign_follows_command"])

    def test_missing_multi_joint_wave_fails_machine_acceptance(self) -> None:
        observations = self._synthetic_observations()
        for row in observations:
            if row["segment"] == "multi_joint_wave":
                for joint_name in CONTROLLED_JOINT_NAMES:
                    row["observed_positions_rad"][joint_name] = 0.0
        result = evaluate_motion_observations(self.plan, observations)
        self.assertFalse(result["machine_passed"])
        self.assertFalse(result["checks"]["multi_joint_wave_observed"])

    def test_missing_negative_excursion_fails_machine_acceptance(self) -> None:
        observations = self._synthetic_observations()
        for row in observations:
            if row["segment"] == "joint3_sine":
                row["observed_positions_rad"]["joint3"] = 0.0
        result = evaluate_motion_observations(self.plan, observations)
        self.assertFalse(result["machine_passed"])
        self.assertFalse(result["checks"]["each_joint_moves_both_directions"])


if __name__ == "__main__":
    unittest.main()
