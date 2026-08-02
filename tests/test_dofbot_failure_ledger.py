from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
LEDGER_PATH = PROJECT_DIR / "experiments/02_dofbot/FAILURE_LEDGER.md"
STARTUP_EVIDENCE_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/pregrasp_startup_operational_2026-08-01.json"
)
TARGET_TORQUE_EVIDENCE_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/pregrasp_target_torque_discriminator_2026-08-01.json"
)
PROJECTED_FORCE_EVIDENCE_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/pregrasp_projected_force_discriminator_2026-08-01.json"
)
SINGLE_BOUNDARY_EVIDENCE_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/pregrasp_single_boundary_discriminator_2026-08-01.json"
)
ALLOWED_VERDICTS = {
    "RESOLVED",
    "FALSIFIED",
    "PARTIAL",
    "OPEN",
    "OPERATIONAL",
}
REQUIRED_EVIDENCE = {
    "artifacts/dofbot/motion_contract.json",
    "artifacts/dofbot/motion_config_small_amplitude_2026-07-27.json",
    "artifacts/dofbot/motion_config_contract.json",
    "artifacts/dofbot/camera_contract.json",
    "artifacts/dofbot/reaching_viewer_contract.json",
    "artifacts/dofbot/pregrasp_machine_failure_2026-07-29.json",
    "artifacts/dofbot/pregrasp_reachability.json",
    "artifacts/dofbot/pregrasp_angled_machine_failure_2026-07-29.json",
    "artifacts/dofbot/pregrasp_joint_candidate_machine_failure_2026-07-29.json",
    "artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json",
    "artifacts/dofbot/actuator_calibration_result_2026-07-30.json",
    "artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json",
    "artifacts/dofbot/solver_drive_diagnostic_result_2026-07-30.json",
    "artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json",
    "artifacts/dofbot/residual_force_audit_2026-07-30.json",
    "artifacts/dofbot/gravity_feed_forward_runtime_failure_2026-07-31.json",
    "artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json",
    "artifacts/dofbot/pregrasp_live_actuator_gate_result_2026-07-31.json",
    "artifacts/dofbot/pregrasp_no_reissue_machine_result_2026-07-31.json",
    "artifacts/dofbot/pregrasp_startup_operational_2026-08-01.json",
    "artifacts/dofbot/pregrasp_target_torque_discriminator_2026-08-01.json",
    "artifacts/dofbot/pregrasp_projected_force_discriminator_2026-08-01.json",
    "artifacts/dofbot/pregrasp_single_boundary_discriminator_2026-08-01.json",
    "artifacts/dofbot/pregrasp_context_transfer_audit.json",
}
REQUIRED_POLICY_FILES = (
    "AGENTS.md",
    "docs/LESSONS_LEARNED.md",
    "experiments/README.md",
    "experiments/02_dofbot/README.md",
    "artifacts/dofbot/README.md",
)


def ledger_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith("| DF-"):
            rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def artifact_references(text: str) -> set[str]:
    return set(re.findall(r"`(artifacts/dofbot/[^`]+\.json)`", text))


class DofbotFailureLedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = LEDGER_PATH.read_text(encoding="utf-8")
        cls.rows = ledger_rows(cls.text)

    def test_rows_are_complete_sequential_and_use_known_verdicts(self) -> None:
        self.assertGreaterEqual(len(self.rows), 32)
        ids = []
        for row in self.rows:
            self.assertEqual(len(row), 7, row)
            entry_id, date, area, claim, verdict, evidence, guard = row
            ids.append(int(entry_id.removeprefix("DF-")))
            self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(area)
            self.assertTrue(claim)
            self.assertIn(verdict, ALLOWED_VERDICTS)
            self.assertTrue(evidence)
            self.assertTrue(guard)
        self.assertEqual(ids, list(range(1, len(ids) + 1)))

    def test_all_referenced_artifacts_exist(self) -> None:
        references = artifact_references(self.text)
        self.assertTrue(REQUIRED_EVIDENCE.issubset(references))
        for relative_path in sorted(references):
            self.assertTrue((PROJECT_DIR / relative_path).is_file(), relative_path)

    def test_new_failure_named_artifacts_cannot_bypass_the_ledger(self) -> None:
        references = artifact_references(self.text)
        failure_artifacts = {
            path.relative_to(PROJECT_DIR).as_posix()
            for path in (PROJECT_DIR / "artifacts/dofbot").glob("*failure*.json")
        }
        self.assertTrue(failure_artifacts.issubset(references))

    def test_completed_discriminator_preserves_projected_force_boundary(self) -> None:
        target = next(row for row in self.rows if row[0] == "DF-030")
        semantics = next(row for row in self.rows if row[0] == "DF-032")
        projected_result = next(row for row in self.rows if row[0] == "DF-034")
        trajectory = next(row for row in self.rows if row[0] == "DF-035")
        trajectory_result = next(row for row in self.rows if row[0] == "DF-039")
        self.assertEqual(target[4], "PARTIAL")
        self.assertIn("joint_pos_target", target[3])
        self.assertIn("PD estimates", target[3])
        self.assertEqual(semantics[4], "PARTIAL")
        self.assertIn("active component", semantics[3])
        self.assertIn("not an isolated", semantics[3])
        self.assertEqual(projected_result[4], "PARTIAL")
        self.assertIn("All 61 observations", projected_result[3])
        self.assertIn("does not isolate", projected_result[6])
        self.assertEqual(trajectory[4], "PARTIAL")
        self.assertIn("30 degrees/s", trajectory[3])
        self.assertIn("600 degrees/s2", trajectory[3])
        self.assertIn("2000-ms", trajectory[6])
        self.assertEqual(trajectory_result[4], "FALSIFIED")
        self.assertIn("4.196145 degrees", trajectory_result[3])
        self.assertIn("Do not repeat trajectory-duration", trajectory_result[6])
        self.assertIn("Viewer remains blocked", self.text)
        protocol = next(row for row in self.rows if row[0] == "DF-041")
        provenance = next(row for row in self.rows if row[0] == "DF-042")
        self.assertEqual(protocol[4], "FALSIFIED")
        self.assertIn("12-degree boundary", protocol[3])
        self.assertIn("does not falsify", protocol[6])
        self.assertEqual(provenance[4], "OPEN")
        self.assertIn("no exact source-file bundle", provenance[3])
        self.assertIn("fail-fast cell A", provenance[6])
        ci_isolation = next(row for row in self.rows if row[0] == "DF-043")
        self.assertEqual(ci_isolation[4], "RESOLVED")
        self.assertIn("exported", ci_isolation[3])
        self.assertIn("one Make invocation", ci_isolation[6])
        tested_object = next(row for row in self.rows if row[0] == "DF-044")
        self.assertEqual(tested_object[4], "RESOLVED")
        self.assertIn("source SHA", tested_object[3])
        self.assertIn("byte-identical", tested_object[6])
        publication = next(row for row in self.rows if row[0] == "DF-045")
        self.assertEqual(publication[4], "RESOLVED")
        self.assertIn("Backticks", publication[3])
        self.assertIn("--body-file", publication[6])
        self.assertIn("STOPPED", publication[3])

    def test_remote_verifier_interpreter_defect_is_not_hidden(self) -> None:
        wrapper = next(row for row in self.rows if row[0] == "DF-031")
        self.assertEqual(wrapper[4], "OPERATIONAL")
        self.assertIn("python3", wrapper[3])
        self.assertIn("./_isaac_sim/python.sh", wrapper[6])
        self.assertIn("future remote run", wrapper[6])
        resolution = next(row for row in self.rows if row[0] == "DF-033")
        self.assertEqual(resolution[4], "RESOLVED")
        self.assertIn("[PREGRASP_EXIT_CODE] 1", resolution[3])

    def test_startup_failure_does_not_replace_scientific_discriminator(self) -> None:
        startup = next(row for row in self.rows if row[0] == "DF-029")
        self.assertEqual(startup[4], "OPERATIONAL")
        self.assertIn("never reached compute", startup[3])
        self.assertIn("DF-028", startup[6])
        self.assertIn("RUNNING", startup[6])
        self.assertIn("READY", startup[6])

    def test_startup_evidence_makes_no_scientific_claim(self) -> None:
        evidence = json.loads(STARTUP_EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(evidence["conclusion"]["classification"], "operational_startup_failure")
        self.assertEqual(evidence["conclusion"]["scientific_claim"], "none")
        self.assertEqual(evidence["conclusion"]["df_028_status"], "open")
        self.assertFalse(evidence["scope"]["scientific_command_started"])
        self.assertFalse(evidence["scope"]["viewer_started"])
        self.assertEqual(evidence["attempt"]["final_status"], "STOPPED")

    def test_target_torque_evidence_preserves_measurement_boundary(self) -> None:
        evidence = json.loads(
            TARGET_TORQUE_EVIDENCE_PATH.read_text(encoding="utf-8")
        )
        self.assertFalse(evidence["machine"]["machine_passed"])
        self.assertTrue(
            evidence["target_buffer_discriminator"][
                "command_propagation_passed"
            ]
        )
        self.assertFalse(
            evidence["implicit_actuator_torque_discriminator"][
                "proves_physical_torque_was_applied"
            ]
        )
        self.assertIn(
            "get_dof_projected_joint_forces",
            evidence["conclusion"]["next_discriminator"],
        )
        self.assertEqual(
            evidence["infrastructure"]["terminal_instance_state"],
            "STOPPED",
        )

    def test_projected_force_result_preserves_semantics_and_stop_state(self) -> None:
        evidence = json.loads(
            PROJECTED_FORCE_EVIDENCE_PATH.read_text(encoding="utf-8")
        )
        self.assertFalse(evidence["machine"]["machine_passed"])
        telemetry = evidence["projected_joint_force_telemetry"]
        self.assertEqual(telemetry["observation_count"], 61)
        self.assertTrue(
            telemetry["every_observation_finite_dof_aligned_and_sample_aligned"]
        )
        self.assertFalse(
            evidence["conclusion"][
                "projected_force_isolated_implicit_drive_torque"
            ]
        )
        self.assertTrue(evidence["remote_wrapper"]["df_031_resolved"])
        self.assertEqual(evidence["infrastructure"]["final_status"], "STOPPED")

    def test_single_boundary_result_falsifies_trajectory_only_hypothesis(self) -> None:
        evidence = json.loads(
            SINGLE_BOUNDARY_EVIDENCE_PATH.read_text(encoding="utf-8")
        )
        self.assertFalse(evidence["machine"]["machine_passed"])
        self.assertEqual(evidence["machine"]["official_api_call_count"], 12)
        self.assertLess(
            evidence["machine"]["motion_contract"][
                "maximum_peak_velocity_deg_s"
            ],
            evidence["machine"]["motion_contract"][
                "maximum_allowed_velocity_deg_s"
            ],
        )
        self.assertFalse(
            evidence["conclusion"]["segmented_trajectory_was_sufficient_cause"]
        )
        self.assertFalse(evidence["conclusion"]["viewer_authorized"])
        self.assertEqual(evidence["verifier_follow_up"]["ledger_id"], "DF-040")

    def test_repo_policy_links_the_canonical_ledger(self) -> None:
        for relative_path in REQUIRED_POLICY_FILES:
            text = (PROJECT_DIR / relative_path).read_text(encoding="utf-8")
            self.assertIn("FAILURE_LEDGER.md", text, relative_path)
        agents = (PROJECT_DIR / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("same pull request", agents)
        self.assertIn("unresolved ledger ID", agents)


if __name__ == "__main__":
    unittest.main()
