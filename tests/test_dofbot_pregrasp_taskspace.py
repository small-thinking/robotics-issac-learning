from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.design_dofbot_pregrasp_taskspace import build_report
from tools.dofbot_pregrasp_reachability import (
    fit_planar_model,
    load_reachability_config,
)
from tools.dofbot_pregrasp_taskspace import (
    TaskspaceSearchError,
    load_taskspace_config,
    parse_taskspace_config,
    search_taskspace,
)
from tools.dofbot_reaching import (
    ReachingConfigError,
    load_reaching_config,
    parse_reaching_config,
)
from tools.preview_dofbot_pregrasp_pose import build_preview

PROJECT_DIR = Path(__file__).resolve().parents[1]
TASKSPACE_CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/pregrasp/goal5_taskspace_search.json"
)
REACHABILITY_CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/pregrasp/goal5_planar_reachability.json"
)
REJECTED_REACHABILITY_ARTIFACT_PATH = (
    PROJECT_DIR / "artifacts/dofbot/pregrasp_reachability.json"
)
MOTION_CONFIG_CONTRACT_PATH = (
    PROJECT_DIR / "artifacts/dofbot/motion_config_contract.json"
)
ASSET_CONTRACT_PATH = (
    PROJECT_DIR / "artifacts/dofbot/asset_contract.json"
)
SCENE_CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/reaching/"
    "goal5_angled_pregrasp_scene_candidate.json"
)
POSE_CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/pregrasp/goal5_angled_pregrasp.json"
)


class DofbotPregraspTaskspaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(
            TASKSPACE_CONFIG_PATH.read_text(encoding="utf-8")
        )
        cls.config, cls.config_sha256 = load_taskspace_config(
            TASKSPACE_CONFIG_PATH
        )
        reachability, _ = load_reachability_config(
            REACHABILITY_CONFIG_PATH
        )
        cls.model = fit_planar_model(reachability)
        cls.searches = search_taskspace(cls.model, cls.config)
        cls.report = build_report(
            taskspace_config_path=TASKSPACE_CONFIG_PATH,
            reachability_config_path=REACHABILITY_CONFIG_PATH,
            rejected_reachability_artifact_path=(
                REJECTED_REACHABILITY_ARTIFACT_PATH
            ),
            motion_config_contract_path=MOTION_CONFIG_CONTRACT_PATH,
            asset_contract_path=ASSET_CONTRACT_PATH,
            candidate_scene_config_path=SCENE_CONFIG_PATH,
            candidate_pose_config_path=POSE_CONFIG_PATH,
        )

    def test_config_is_strict_and_fail_closed(self) -> None:
        self.assertEqual(self.config.name, "goal5_taskspace_search")
        self.assertEqual(
            (
                self.config.search.physical_angle_min_deg,
                self.config.search.physical_angle_max_deg,
                self.config.search.validated_command_angle_min_deg,
                self.config.search.validated_command_angle_max_deg,
                self.config.search.search_angle_min_deg,
                self.config.search.search_angle_max_deg,
            ),
            (60, 120, 62, 118, 64, 116),
        )
        for mutation, message in (
            (
                lambda value: value["source_contracts"].__setitem__(
                    "asset_contract_sha256",
                    "bad",
                ),
                "lowercase SHA-256",
            ),
            (
                lambda value: value["search"].__setitem__(
                    "search_angle_min_deg",
                    63,
                ),
                "angle contracts",
            ),
            (
                lambda value: value["search"].__setitem__(
                    "minimum_model_residual_reserve_m",
                    0.0,
                ),
                "model residual reserve",
            ),
        ):
            tampered = copy.deepcopy(self.raw)
            mutation(tampered)
            with self.assertRaisesRegex(TaskspaceSearchError, message):
                parse_taskspace_config(tampered)

    def test_search_rejects_low_table_and_selects_one_robust_pose(self) -> None:
        physical = self.searches["physical_envelope"]
        candidate_search = self.searches["candidate_search"]
        self.assertEqual(physical["evaluated_count"], 61**3)
        self.assertFalse(physical["requested_low_table_feasible"])
        self.assertAlmostEqual(
            physical["minimum_derived_table_top_m"],
            0.17945184067910003,
        )
        self.assertEqual(candidate_search["evaluated_count"], 53**3)
        self.assertEqual(candidate_search["passed_candidate_count"], 1)
        selected = candidate_search["ranked_candidates"][0]
        self.assertEqual(selected["angles_deg"], [90, 66, 66, 66])
        self.assertAlmostEqual(
            selected["scene"]["table_top_m"],
            0.2616040440464413,
        )
        self.assertEqual(
            selected["margins"]["physical_angle_margin_deg"],
            6,
        )
        self.assertEqual(
            selected["margins"]["search_angle_margin_deg"],
            2,
        )
        self.assertGreaterEqual(
            selected["margins"]["minimum_clearance_reserve_m"],
            0.003,
        )
        self.assertTrue(all(selected["checks"].values()))

    def test_candidate_configs_and_local_preview_match_search(self) -> None:
        scene, _ = load_reaching_config(SCENE_CONFIG_PATH)
        selected = self.searches["candidate_search"][
            "ranked_candidates"
        ][0]
        self.assertEqual(
            scene.end_effector_body_name,
            "terminal_finger_midpoint",
        )
        self.assertEqual(
            scene.approach_target_world_m,
            tuple(selected["target_pose"]["origin_world_m"]),
        )
        preview = build_preview(
            pose_config_path=POSE_CONFIG_PATH,
            scene_config_path=SCENE_CONFIG_PATH,
            asset_contract_path=ASSET_CONTRACT_PATH,
        )
        self.assertTrue(preview["acceptance"]["local_preparation_passed"])
        self.assertTrue(all(preview["acceptance"]["checks"].values()))
        self.assertFalse(preview["scope"]["gpu_started"])

    def test_goal5_scene_requires_terminal_frame_and_bounded_standoff(self) -> None:
        raw = json.loads(SCENE_CONFIG_PATH.read_text(encoding="utf-8"))
        wrong_body = copy.deepcopy(raw)
        wrong_body["end_effector"]["body_name"] = "Wrist_Twist"
        with self.assertRaisesRegex(
            ReachingConfigError,
            "terminal_finger_midpoint",
        ):
            parse_reaching_config(wrong_body)

        wrong_offset = copy.deepcopy(raw)
        wrong_offset["end_effector"][
            "approach_offset_from_cube_center_m"
        ] = [0.0, -0.01, 0.0]
        with self.assertRaisesRegex(ReachingConfigError, "front-side"):
            parse_reaching_config(wrong_offset)

    def test_report_links_provenance_without_authorizing_paid_run(self) -> None:
        acceptance = self.report["acceptance"]
        self.assertTrue(acceptance["local_design_passed"])
        self.assertTrue(
            acceptance[
                "revised_candidate_ready_for_isaac_machine_validation"
            ]
        )
        self.assertTrue(all(acceptance["checks"].values()))
        self.assertFalse(acceptance["paid_gpu_run_authorized"])
        self.assertFalse(acceptance["viewer_authorized"])
        self.assertFalse(acceptance["contact_or_grasp_authorized"])
        self.assertFalse(self.report["scope"]["gpu_started"])
        self.assertFalse(self.report["scope"]["isaac_started"])
        self.assertFalse(
            self.report["scope"]["real_hardware_command_sent"]
        )


if __name__ == "__main__":
    unittest.main()
