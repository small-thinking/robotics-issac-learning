from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.calibrate_dofbot_pregrasp_scene import (
    SceneCalibrationError,
    build_scene_calibration,
    render_scene_calibration_svg,
)
from tools.dofbot_reaching import load_reaching_config

PROJECT_DIR = Path(__file__).resolve().parents[1]
BASELINE_CONFIG_PATH = (
    PROJECT_DIR / "configs/dofbot/reaching/goal4_fixed_tabletop.json"
)
CANDIDATE_CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json"
)
ISAAC_ARTIFACT_PATH = (
    PROJECT_DIR / "artifacts/dofbot/reaching_viewer_contract.json"
)


class DofbotPregraspSceneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline, _ = load_reaching_config(BASELINE_CONFIG_PATH)
        cls.candidate, _ = load_reaching_config(CANDIDATE_CONFIG_PATH)
        cls.report = build_scene_calibration(
            baseline_config_path=BASELINE_CONFIG_PATH,
            candidate_config_path=CANDIDATE_CONFIG_PATH,
            isaac_artifact_path=ISAAC_ARTIFACT_PATH,
        )

    def test_candidate_table_is_lower_horizontal_and_farther(self) -> None:
        self.assertEqual(self.candidate.table.center_world_m, (0.0, 0.31, 0.06))
        self.assertAlmostEqual(self.candidate.table.top_z_m, 0.08)
        self.assertAlmostEqual(self.candidate.table_front_clearance_m, 0.16)
        self.assertEqual(
            self.candidate.target_cube.center_world_m,
            (0.0, 0.25, 0.105),
        )
        self.assertEqual(
            self.candidate.approach_target_world_m,
            (0.0, 0.25, 0.195),
        )
        self.assertAlmostEqual(
            self.candidate.target_cube.bottom_z_m,
            self.candidate.table.top_z_m,
        )

    def test_candidate_changes_scene_only(self) -> None:
        self.assertEqual(
            self.candidate.robot_frame,
            self.baseline.robot_frame,
        )
        self.assertEqual(
            self.candidate.scripted_baseline,
            self.baseline.scripted_baseline,
        )
        self.assertEqual(
            self.candidate.state_controller,
            self.baseline.state_controller,
        )
        self.assertEqual(
            self.candidate.end_effector_body_name,
            self.baseline.end_effector_body_name,
        )

    def test_report_anchors_candidate_to_real_goal4_evidence(self) -> None:
        self.assertTrue(self.report["acceptance"]["local_geometry_passed"])
        self.assertTrue(all(self.report["acceptance"]["checks"].values()))
        self.assertEqual(
            self.report["sources"]["goal4_isaac_artifact"]["sha256"],
            "87faa5f892553c093dc190e331967990676672e4b383587e21a298cd8446d893",
        )
        self.assertEqual(
            self.report["sources"]["goal4_isaac_artifact"]["machine_check_count"],
            14,
        )
        self.assertGreaterEqual(
            self.report["delta"]["table_top_lowering_m"],
            0.03,
        )
        self.assertGreaterEqual(
            self.report["delta"]["target_forward_shift_m"],
            0.06,
        )
        self.assertGreaterEqual(
            self.report["delta"]["nominal_radial_margin_m"],
            0.015,
        )
        diagnostic = self.report["controller_reuse_diagnostic"]
        self.assertLess(
            diagnostic["baseline_final_observed_joint_envelope_margin_deg"],
            0.0,
        )
        self.assertFalse(
            diagnostic[
                "existing_translation_only_controller_certified_for_candidate"
            ]
        )

    def test_local_gate_never_claims_candidate_sim_or_grasp_pass(self) -> None:
        acceptance = self.report["acceptance"]
        self.assertFalse(acceptance["candidate_isaac_machine_passed"])
        self.assertFalse(acceptance["candidate_visual_passed"])
        self.assertFalse(acceptance["contact_or_grasp_authorized"])
        self.assertFalse(self.report["scope"]["gpu_started"])
        self.assertFalse(self.report["scope"]["isaac_started"])
        self.assertFalse(self.report["scope"]["real_hardware_commanded"])
        self.assertFalse(self.report["scope"]["gripper_commanded"])
        self.assertFalse(self.report["scope"]["target_cube_moved"])

    def test_gate_rejects_an_unchanged_close_high_scene(self) -> None:
        with self.assertRaisesRegex(
            SceneCalibrationError,
            "table_top_lowered_at_least_3cm",
        ):
            build_scene_calibration(
                baseline_config_path=BASELINE_CONFIG_PATH,
                candidate_config_path=BASELINE_CONFIG_PATH,
                isaac_artifact_path=ISAAC_ARTIFACT_PATH,
            )

    def test_gate_rejects_tampered_or_failed_isaac_evidence(self) -> None:
        artifact = json.loads(ISAAC_ARTIFACT_PATH.read_text(encoding="utf-8"))
        artifact["acceptance"]["machine"]["machine_passed"] = False
        with tempfile.TemporaryDirectory() as directory:
            tampered_path = Path(directory) / "tampered.json"
            tampered_path.write_text(
                json.dumps(artifact),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                SceneCalibrationError,
                "machine evidence must have passed",
            ):
                build_scene_calibration(
                    baseline_config_path=BASELINE_CONFIG_PATH,
                    candidate_config_path=CANDIDATE_CONFIG_PATH,
                    isaac_artifact_path=tampered_path,
                )

    def test_svg_contains_both_views_and_explicit_proof_limit(self) -> None:
        svg = render_scene_calibration_svg(self.report)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("Side view (world Y–Z)", svg)
        self.assertIn("Top view (world X–Y)", svg)
        self.assertIn("not an IK proof", svg)
        self.assertIn("current controller reuse: NOT CERTIFIED", svg)
        self.assertIn("Isaac/Viewer: PENDING", svg)
        self.assertIn('clip-path="url(#side-plot-clip)"', svg)


if __name__ == "__main__":
    unittest.main()
