from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.dofbot_pregrasp_pose import load_pregrasp_pose_config
from tools.dofbot_pregrasp_reachability import (
    ReachabilityError,
    fit_planar_model,
    load_reachability_config,
    minimum_approach_error_over_bounds,
    parse_reachability_config,
    predict_planar_frame,
    search_planar_pose,
    terminal_pose_proximal_reach,
)
from tools.search_dofbot_pregrasp_reachability import build_report

PROJECT_DIR = Path(__file__).resolve().parents[1]
REACHABILITY_CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/pregrasp/goal5_planar_reachability.json"
)
POSE_CONFIG_PATH = (
    PROJECT_DIR / "configs/dofbot/pregrasp/goal5_pose_aware_pregrasp.json"
)
FAILURE_SUMMARY_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/pregrasp_machine_failure_2026-07-29.json"
)


class DofbotPregraspReachabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(REACHABILITY_CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, cls.config_sha256 = load_reachability_config(
            REACHABILITY_CONFIG_PATH
        )
        cls.pose, cls.pose_sha256 = load_pregrasp_pose_config(POSE_CONFIG_PATH)
        cls.model = fit_planar_model(cls.config)

    def test_strict_config_and_source_provenance(self) -> None:
        self.assertEqual(self.config.name, "goal5_planar_reachability")
        self.assertEqual(
            self.config.source.sample_step_indices,
            tuple(range(12)),
        )
        self.assertEqual(len(self.config.samples), 12)
        self.assertEqual(
            (
                self.config.search.physical_angle_min_deg,
                self.config.search.physical_angle_max_deg,
                self.config.search.command_angle_min_deg,
                self.config.search.command_angle_max_deg,
            ),
            (60, 120, 68, 112),
        )
        for mutation, message in (
            (
                lambda value: value["source"].__setitem__(
                    "failure_summary_sha256", "bad"
                ),
                "lowercase SHA-256",
            ),
            (
                lambda value: value["search"].__setitem__(
                    "physical_angle_min_deg", 59
                ),
                "search bounds",
            ),
            (
                lambda value: value["source"].__setitem__(
                    "sample_step_indices", list(reversed(range(12)))
                ),
                "sorted and unique",
            ),
            (
                lambda value: value["model"].__setitem__(
                    "maximum_fit_position_error_m", 0.1
                ),
                "position residual",
            ),
        ):
            tampered = copy.deepcopy(self.raw)
            mutation(tampered)
            with self.assertRaisesRegex(ReachabilityError, message):
                parse_reachability_config(tampered)

    def test_planar_fit_is_bounded_by_recorded_isaac_samples(self) -> None:
        self.assertLessEqual(self.model.maximum_position_residual_m, 0.003)
        self.assertLessEqual(self.model.maximum_approach_residual_deg, 0.01)
        self.assertAlmostEqual(
            sum(self.model.link_lengths_m),
            0.3290431958262349,
            places=9,
        )
        self.assertAlmostEqual(
            self.model.approach_angle_offset_deg,
            -1.5882676481759879,
            places=9,
        )
        for sample in self.config.samples:
            origin, approach = predict_planar_frame(self.model, sample.angles_deg)
            position_error = sum(
                (predicted - observed) ** 2
                for predicted, observed in zip(
                    origin, sample.origin_world_m, strict=True
                )
            ) ** 0.5
            self.assertLessEqual(position_error, 0.003)
            self.assertAlmostEqual(
                sum(value * value for value in approach),
                1.0,
                places=9,
            )

    def test_world_down_orientation_is_outside_both_safe_bounds(self) -> None:
        target = self.pose.target_pose.approach_axis_world_unit
        physical_lower_bound = minimum_approach_error_over_bounds(
            self.model,
            target,
            angle_min_deg=60,
            angle_max_deg=120,
        )
        command_lower_bound = minimum_approach_error_over_bounds(
            self.model,
            target,
            angle_min_deg=68,
            angle_max_deg=112,
        )
        self.assertAlmostEqual(physical_lower_bound, 88.41175841741459)
        self.assertAlmostEqual(command_lower_bound, 112.4113446626637)
        self.assertGreater(
            physical_lower_bound,
            self.pose.target_pose.approach_tolerance_deg,
        )
        self.assertGreater(
            command_lower_bound,
            self.pose.target_pose.approach_tolerance_deg,
        )

    def test_coupled_world_down_pose_exceeds_unbounded_chain_reach(self) -> None:
        result = terminal_pose_proximal_reach(
            self.model,
            target_position_world_m=self.pose.target_pose.position_world_m,
            target_approach_axis_world_unit=(
                self.pose.target_pose.approach_axis_world_unit
            ),
        )
        self.assertFalse(result["reachable_without_angle_bounds"])
        self.assertAlmostEqual(
            result["required_proximal_reach_m"],
            0.3579061549881061,
        )
        self.assertAlmostEqual(
            result["maximum_proximal_reach_m"],
            0.19656206745950533,
        )
        self.assertAlmostEqual(
            result["maximum_reach_margin_m"],
            -0.16134408752860074,
        )

    def test_search_can_accept_a_reachable_synthetic_pose(self) -> None:
        target_angles = (90, 80, 80, 80)
        target_origin, target_approach = predict_planar_frame(
            self.model,
            target_angles,
        )
        result = search_planar_pose(
            self.model,
            target_position_world_m=target_origin,
            target_approach_axis_world_unit=target_approach,
            position_tolerance_m=0.001,
            approach_tolerance_deg=0.1,
            angle_min_deg=78,
            angle_max_deg=82,
            grid_step_deg=1,
            minimum_workspace_front_y_m=0.0,
            maximum_ranked_candidates=5,
        )
        self.assertTrue(result["target_feasible"])
        self.assertGreaterEqual(result["passed_candidate_count"], 1)
        self.assertEqual(result["evaluated_count"], 125)
        self.assertEqual(
            result["ranked_branch_candidates"][0]["angles_deg"],
            list(target_angles),
        )

    def test_report_rejects_current_target_without_starting_gpu(self) -> None:
        report = build_report(
            reachability_config_path=REACHABILITY_CONFIG_PATH,
            pose_config_path=POSE_CONFIG_PATH,
            failure_summary_path=FAILURE_SUMMARY_PATH,
        )
        self.assertTrue(report["acceptance"]["search_contract_passed"])
        self.assertFalse(report["acceptance"]["current_target_feasible"])
        self.assertFalse(
            report["acceptance"]["revised_candidate_ready_for_remote_validation"]
        )
        self.assertFalse(report["acceptance"]["paid_gpu_run_authorized"])
        self.assertFalse(report["acceptance"]["viewer_authorized"])
        self.assertTrue(all(report["acceptance"]["checks"].values()))
        self.assertEqual(
            report["searches"]["physical_envelope"]["evaluated_count"],
            61**3,
        )
        self.assertEqual(
            report["searches"]["command_margin"]["evaluated_count"],
            45**3,
        )
        self.assertFalse(report["scope"]["gpu_started"])
        self.assertFalse(report["scope"]["isaac_started"])
        self.assertFalse(report["scope"]["real_hardware_command_sent"])
        self.assertFalse(report["scope"]["contact_or_grasp_authorized"])


if __name__ == "__main__":
    unittest.main()
