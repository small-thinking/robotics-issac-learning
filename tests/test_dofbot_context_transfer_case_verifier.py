from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_dofbot_context_transfer import (
    CURRENT_SHARED_RUNTIME_PATHS,
    _source_bundle,
)
from tools.dofbot_actuator_calibration import (
    load_actuator_calibration_config,
)
from tools.summarize_dofbot_context_transfer_matrix import (
    summarize_context_transfer_matrix,
)
from tools.verify_dofbot_context_transfer_case import (
    CELL_SPECS,
    ContextTransferCaseError,
    verify_context_transfer_case,
)

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "test-context-transfer-commit"


def artifact_for(cell_id: str, *, tracking_passed: bool = True) -> dict:
    spec = CELL_SPECS[cell_id]
    config_path = ROOT / str(spec["config"])
    config, config_sha256 = load_actuator_calibration_config(config_path)
    scene_path = spec["scene"]
    return {
        "schema_version": 1,
        "experiment": "dofbot_actuator_diagnostic_case",
        "git_commit": COMMIT,
        "runtime_source_bundle": _source_bundle(
            project_dir=ROOT,
            paths=CURRENT_SHARED_RUNTIME_PATHS,
        ),
        "calibration_config": {"sha256": config_sha256},
        "context_scene_config": (
            {
                "sha256": hashlib.sha256(
                    (ROOT / str(scene_path)).read_bytes()
                ).hexdigest()
            }
            if scene_path is not None
            else None
        ),
        "case": {
            "name": "bounded_gravity_feed_forward",
            "gravity_enabled": True,
            "effort_limit_sim": 100.0,
            "stiffness": 1048.0,
            "damping": 53.0,
            "solver_position_iteration_count": 8,
            "solver_velocity_iteration_count": 0,
            "enable_external_forces_every_iteration": True,
            "drive_type": "force",
            "gravity_compensation_feed_forward": True,
            "gravity_compensation_effort_limit": 5.2,
        },
        "measurement": {
            "pose_summaries": [
                {
                    "name": pose.name,
                    "command_angles_deg": list(pose.angles_deg),
                    "maximum_tracking_error_deg": 0.25,
                }
                for pose in config.poses
            ],
            "samples": [{"pose_step": 0}],
        },
        "evaluation": {
            "checks": {"telemetry_complete": True},
            "diagnostic_complete": True,
            "tracking_gate_passed": tracking_passed,
            "maximum_settled_tracking_error_deg": 0.25,
        },
        "scope": {
            "table_or_cube_spawned": scene_path is not None,
            "viewer_started": False,
            "camera_tensor_captured": False,
            "real_hardware_commanded": False,
            "policy_or_checkpoint_loaded": False,
            "contact_or_grasp_authorized": False,
        },
    }


class DofbotContextTransferCaseVerifierTest(unittest.TestCase):
    def verify(self, artifact: dict, cell_id: str, **kwargs: object) -> dict:
        return verify_context_transfer_case(
            artifact,
            cell_id=cell_id,
            project_dir=ROOT,
            expected_git_commit=COMMIT,
            **kwargs,
        )

    def test_all_cells_bind_their_exact_protocol(self) -> None:
        for cell_id in CELL_SPECS:
            with self.subTest(cell_id=cell_id):
                result = self.verify(artifact_for(cell_id), cell_id)
                self.assertTrue(result["integrity_passed"])

    def test_cell_a_is_a_fail_fast_regression_sentinel(self) -> None:
        failed = artifact_for("A", tracking_passed=False)
        with self.assertRaisesRegex(
            ContextTransferCaseError,
            "regression sentinel",
        ):
            self.verify(failed, "A")
        result = self.verify(
            failed,
            "A",
            enforce_tracking_policy=False,
        )
        self.assertFalse(result["tracking_gate_passed"])

    def test_diagnostic_cells_may_record_a_scientific_failure(self) -> None:
        for cell_id in ("B", "C"):
            with self.subTest(cell_id=cell_id):
                result = self.verify(
                    artifact_for(cell_id, tracking_passed=False),
                    cell_id,
                )
                self.assertFalse(result["tracking_gate_passed"])

    def test_stale_or_confounded_artifacts_fail_closed(self) -> None:
        mutations = []
        stale_bundle = artifact_for("A")
        stale_bundle["runtime_source_bundle"]["sha256"] = "0" * 64
        mutations.append(stale_bundle)
        empty_samples = artifact_for("A")
        empty_samples["measurement"]["samples"] = []
        mutations.append(empty_samples)
        false_check = artifact_for("A")
        false_check["evaluation"]["checks"]["telemetry_complete"] = False
        mutations.append(false_check)
        wrong_scope = artifact_for("A")
        wrong_scope["scope"]["viewer_started"] = True
        mutations.append(wrong_scope)
        wrong_case = artifact_for("A")
        wrong_case["case"]["damping"] = 54.0
        mutations.append(wrong_case)
        for mutation in mutations:
            with self.subTest():
                with self.assertRaises(ContextTransferCaseError):
                    self.verify(mutation, "A")

    def test_cell_c_requires_the_exact_static_scene(self) -> None:
        stale = copy.deepcopy(artifact_for("C"))
        stale["context_scene_config"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ContextTransferCaseError, "scene SHA"):
            self.verify(stale, "C")

    def test_matrix_stops_after_a_current_runtime_regression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            (input_dir / "cell_a.json").write_text(
                json.dumps(artifact_for("A", tracking_passed=False)),
                encoding="utf-8",
            )
            result = summarize_context_transfer_matrix(
                input_dir=input_dir,
                project_dir=ROOT,
                expected_git_commit=COMMIT,
                failed_direct_reference=(
                    ROOT
                    / "artifacts/dofbot/"
                    "pregrasp_single_boundary_discriminator_2026-08-01.json"
                ),
            )
        self.assertTrue(result["matrix"]["complete"])
        self.assertTrue(result["matrix"]["fail_fast_triggered"])
        self.assertEqual(result["matrix"]["executed_cells"], ["A"])
        self.assertEqual(
            result["matrix"]["decision"],
            "current_shared_runtime_regression_failed",
        )

    def test_matrix_classifies_single_factor_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            results = {"A": True, "B": False, "C": True}
            for cell_id, passed in results.items():
                (input_dir / f"cell_{cell_id.lower()}.json").write_text(
                    json.dumps(
                        artifact_for(cell_id, tracking_passed=passed)
                    ),
                    encoding="utf-8",
                )
            result = summarize_context_transfer_matrix(
                input_dir=input_dir,
                project_dir=ROOT,
                expected_git_commit=COMMIT,
                failed_direct_reference=(
                    ROOT
                    / "artifacts/dofbot/"
                    "pregrasp_single_boundary_discriminator_2026-08-01.json"
                ),
            )
        self.assertFalse(result["matrix"]["fail_fast_triggered"])
        self.assertEqual(result["matrix"]["executed_cells"], ["A", "B", "C"])
        self.assertEqual(
            result["matrix"]["decision"],
            "direct_transition_or_missing_mid_load_history_is_causal",
        )
        self.assertFalse(result["authorization"]["viewer"])


if __name__ == "__main__":
    unittest.main()
