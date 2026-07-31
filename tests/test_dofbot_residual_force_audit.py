from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.audit_dofbot_residual_force import (
    drive_limit_equivalent_force,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/residual_force_audit_2026-07-30.json"
)


class DofbotResidualForceAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    def test_impulse_equivalent_force_uses_physics_timestep(self) -> None:
        self.assertEqual(drive_limit_equivalent_force(5.2, 1 / 60), 312)
        self.assertEqual(drive_limit_equivalent_force(100, 1 / 60), 6000)
        with self.assertRaisesRegex(ValueError, "positive"):
            drive_limit_equivalent_force(0, 1 / 60)
        with self.assertRaisesRegex(ValueError, "positive"):
            drive_limit_equivalent_force(5.2, 0)

    def test_audit_binds_reviewed_raw_evidence(self) -> None:
        analysis = self.audit["drive_limit_analysis"]
        self.assertEqual(analysis["selected_physical_sample_count"], 647)
        self.assertTrue(analysis["physical_sequences_identical"])
        self.assertTrue(analysis["pose_summaries_identical"])
        self.assertAlmostEqual(
            analysis[
                "if_limits_are_impulses_equivalent_force_per_second"
            ]["force_authored_tuning"],
            312,
        )
        sources = self.audit["source_evidence"]
        self.assertEqual(
            sources["force_damping_53_raw"]["sha256"],
            "36e8d9bfcfb344b5ec7d31063cb35d68c99f344e498eaaba98d05fb937c33b81",
        )
        self.assertEqual(
            sources["force_authored_tuning_raw"]["sha256"],
            "4f7daf0ff07e28aacb5b79d7b6e2ae6ed40727112fa3c0c7762382761fa3ee86",
        )

    def test_audit_keeps_inference_boundary_explicit(self) -> None:
        semantics = self.audit["official_semantics"]
        self.assertFalse(semantics["runtime_flag_directly_recorded"])
        ranking = {
            item["candidate"]: item
            for item in self.audit["residual_cause_ranking"]
        }
        self.assertEqual(
            ranking["drive_limit_impulse_semantics"]["status"],
            "high_confidence_explanation_of_limit_invariance",
        )
        self.assertEqual(
            ranking["runtime_joint_frame_or_sign_error"]["status"],
            "rejected_as_primary_cause",
        )
        self.assertEqual(
            ranking["full_explicit_pd_actuator"]["status"],
            "fallback_not_first_change",
        )

    def test_next_machine_test_is_single_factor_and_fail_closed(self) -> None:
        next_test = self.audit["selected_next_machine_experiment"]
        self.assertEqual(next_test["name"], "bounded_gravity_feed_forward")
        self.assertEqual(
            next_test["baseline"],
            {
                "drive_type": "force",
                "stiffness": 1048.0,
                "damping": 53.0,
                "effort_limit_sim": 100.0,
                "enable_external_forces_every_iteration": True,
            },
        )
        self.assertIn(
            "ArticulationView.get_gravity_compensation_forces",
            next_test["required_runtime_apis"],
        )
        self.assertIn(
            "maximum gravity-on tracking error is at most 1 degree",
            next_test["fail_closed_requirements"],
        )

    def test_audit_passes_but_does_not_authorize_gpu_or_viewer(self) -> None:
        self.assertTrue(self.audit["audit_passed"])
        self.assertTrue(all(self.audit["checks"].values()))
        self.assertFalse(self.audit["paid_gpu_run_authorized"])
        self.assertFalse(self.audit["pregrasp_authorized"])
        self.assertFalse(self.audit["viewer_authorized"])
        self.assertFalse(self.audit["contact_or_grasp_authorized"])
        self.assertEqual(
            self.audit["gate_order"],
            [
                "implement_and_review_bounded_gravity_feed_forward",
                "headless_gravity_on_calibration_at_most_1_degree",
                "headless_pregrasp_machine_gate",
                "viewer_visual_acceptance",
            ],
        )
