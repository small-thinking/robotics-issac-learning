from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.dofbot_actuator_calibration import (
    DRIVE_MODEL_CASE_NAMES,
    ActuatorCalibrationError,
    classify_calibration_matrix,
    load_actuator_calibration_config,
    parse_actuator_calibration_config,
)
from tools.preview_dofbot_drive_model_diagnostic import (
    build_drive_model_preview,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/calibration/goal5_drive_model_diagnostic.json"
)
ASSET_AUDIT_PATH = (
    PROJECT_DIR / "artifacts/dofbot/asset_drive_audit_2026-07-30.json"
)
SOLVER_RESULT_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/solver_drive_diagnostic_result_2026-07-30.json"
)
RUNNER_PATH = PROJECT_DIR / "tools/run_dofbot_actuator_calibration.py"
RUN_SCRIPT_PATH = (
    PROJECT_DIR / "scripts/isaac/run_dofbot_actuator_calibration.sh"
)


def _evaluation(*, tracking_passed: bool = False) -> dict[str, object]:
    return {
        "checks": {
            "contact_force_below_threshold": True,
            "target_buffer_telemetry_available": True,
            "target_buffer_matches_backend_target": True,
            "position_derived_velocity_available": True,
            "all_poses_settled_by_position_derived_velocity": True,
        },
        "tracking_gate_passed": tracking_passed,
    }


class DofbotDriveModelDiagnosticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, _ = load_actuator_calibration_config(CONFIG_PATH)
        cls.audit = json.loads(ASSET_AUDIT_PATH.read_text(encoding="utf-8"))

    def test_official_asset_drive_audit_is_uniform_and_meter_scaled(self) -> None:
        self.assertEqual(self.audit["source_asset"]["meters_per_unit"], 1)
        self.assertFalse(self.audit["source_asset"]["committed_to_repository"])
        drives = self.audit["controlled_joint_drives"]
        self.assertEqual(
            [drive["name"] for drive in drives],
            ["joint1", "joint2", "joint3", "joint4"],
        )
        self.assertTrue(all(drive["axis"] == "X" for drive in drives))
        self.assertTrue(
            all(drive["drive_type"] == "acceleration" for drive in drives)
        )
        self.assertTrue(
            all(
                (
                    drive["stiffness"],
                    drive["damping"],
                    drive["max_force"],
                )
                == (1048, 53, 5.2)
                for drive in drives
            )
        )
        self.assertAlmostEqual(
            sum(self.audit["runtime_mass_snapshot_kg"]["masses"]),
            self.audit["runtime_mass_snapshot_kg"]["total_mass_kg"],
        )
        self.assertFalse(
            self.audit["torque_evidence_correction"][
                "physical_saturation_proven"
            ]
        )

    def test_drive_model_ladder_changes_one_factor_at_a_time(self) -> None:
        self.assertEqual(self.config.case_names, DRIVE_MODEL_CASE_NAMES)
        cases = [case.to_dict() for case in self.config.cases]
        changes = []
        for previous, current in zip(cases, cases[1:], strict=False):
            changes.append(
                sorted(
                    key
                    for key in set(previous) | set(current)
                    if key != "name" and previous.get(key) != current.get(key)
                )
            )
        self.assertEqual(
            changes,
            [
                ["drive_type"],
                ["stiffness"],
                ["damping"],
                ["effort_limit_sim"],
            ],
        )
        self.assertTrue(
            all(case.enable_external_forces_every_iteration for case in self.config.cases)
        )
        self.assertEqual(self.config.cases[0].drive_type, "acceleration")
        self.assertEqual(self.config.cases[-1].drive_type, "force")
        self.assertEqual(self.config.cases[-1].effort_limit_sim, 5.2)

    def test_drive_model_schema_rejects_confounded_stage(self) -> None:
        confounded = copy.deepcopy(self.raw)
        confounded["cases"][1]["stiffness"] = 1048
        with self.assertRaisesRegex(
            ActuatorCalibrationError,
            "drive-model cases",
        ):
            parse_actuator_calibration_config(confounded)

        invalid_type = copy.deepcopy(self.raw)
        invalid_type["cases"][1]["drive_type"] = "velocity"
        with self.assertRaisesRegex(
            ActuatorCalibrationError,
            "drive_type",
        ):
            parse_actuator_calibration_config(invalid_type)

    def test_preview_binds_asset_audit_and_blocks_viewer(self) -> None:
        result = build_drive_model_preview(
            config_path=CONFIG_PATH,
            asset_audit_path=ASSET_AUDIT_PATH,
            solver_result_path=SOLVER_RESULT_PATH,
        )
        self.assertTrue(result["local_preparation_passed"])
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(result["paid_gpu_run_authorized"])
        self.assertFalse(result["viewer_authorized"])
        self.assertFalse(result["pregrasp_authorized"])

    def test_classifier_selects_first_passing_drive_stage(self) -> None:
        all_fail = {
            name: _evaluation() for name in DRIVE_MODEL_CASE_NAMES
        }
        self.assertEqual(
            classify_calibration_matrix(self.config, all_fail)["decision"],
            "drive_model_ladder_no_resolution",
        )
        force_pass = copy.deepcopy(all_fail)
        force_pass["force_runtime_tuning"]["tracking_gate_passed"] = True
        result = classify_calibration_matrix(self.config, force_pass)
        self.assertEqual(result["decision"], "force_drive_resolves_tracking")
        self.assertTrue(result["tracking_identity_validated"])
        self.assertFalse(result["pregrasp_authorized"])

    def test_runner_reads_back_drive_type_and_downgrades_torque_claim(self) -> None:
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        run_script = RUN_SCRIPT_PATH.read_text(encoding="utf-8")
        for value in (
            "JointDrivePropertiesCfg",
            "_controlled_joint_drive_snapshot",
            "UsdPhysics.DriveAPI.Get",
            "requested_drive_type",
            "composed_controlled_drive_types",
            "implicit_pd_estimate_not_measured_solver_torque",
            "implicit_torque_buffers_are_pd_estimates_not_solver_measurements",
        ):
            self.assertIn(value, runner)
        for case_name in DRIVE_MODEL_CASE_NAMES:
            self.assertIn(case_name, run_script)
        self.assertIn('matrix_profile" == "drive_model"', run_script)


if __name__ == "__main__":
    unittest.main()
