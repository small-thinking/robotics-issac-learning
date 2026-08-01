from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
LEDGER_PATH = PROJECT_DIR / "experiments/02_dofbot/FAILURE_LEDGER.md"
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
        self.assertGreaterEqual(len(self.rows), 28)
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

    def test_current_open_discriminator_is_explicit(self) -> None:
        current = next(row for row in self.rows if row[0] == "DF-028")
        self.assertEqual(current[4], "OPEN")
        self.assertIn("backend target", current[6])
        self.assertIn("joint_pos_target", current[6])
        self.assertIn("computed_torque", current[6])
        self.assertIn("applied_torque", current[6])
        self.assertIn("Viewer remains blocked", current[6])
        self.assertIn("must not change the pose, gains, effort limit", self.text)

    def test_repo_policy_links_the_canonical_ledger(self) -> None:
        for relative_path in REQUIRED_POLICY_FILES:
            text = (PROJECT_DIR / relative_path).read_text(encoding="utf-8")
            self.assertIn("FAILURE_LEDGER.md", text, relative_path)
        agents = (PROJECT_DIR / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("same pull request", agents)
        self.assertIn("unresolved ledger ID", agents)


if __name__ == "__main__":
    unittest.main()
