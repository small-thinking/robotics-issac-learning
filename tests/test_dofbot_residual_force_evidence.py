from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_dofbot_residual_force_evidence import build_evidence_audit

ROOT = Path(__file__).resolve().parents[1]
DRIVE_RESULT = ROOT / "artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json"
ACTUATOR_RESULT = ROOT / "artifacts/dofbot/actuator_calibration_result_2026-07-30.json"
ASSET_AUDIT = ROOT / "artifacts/dofbot/asset_drive_audit_2026-07-30.json"
RESIDUAL_AUDIT = ROOT / "artifacts/dofbot/residual_force_audit_2026-07-30.json"


class DofbotResidualForceEvidenceTests(unittest.TestCase):
    def _audit(self, residual_audit: Path = RESIDUAL_AUDIT) -> dict[str, object]:
        return build_evidence_audit(
            drive_result_path=DRIVE_RESULT,
            actuator_result_path=ACTUATOR_RESULT,
            asset_audit_path=ASSET_AUDIT,
            residual_audit_path=residual_audit,
        )

    def test_promoted_residual_force_bindings_pass(self) -> None:
        audit = self._audit()
        self.assertTrue(audit["audit_passed"])
        self.assertTrue(all(audit["checks"].values()))
        self.assertFalse(audit["raw_payloads_required"])

    def test_tampered_tracked_source_binding_fails_closed(self) -> None:
        residual = json.loads(RESIDUAL_AUDIT.read_text(encoding="utf-8"))
        residual["source_evidence"]["asset_drive_audit"]["bytes"] += 1
        with tempfile.TemporaryDirectory() as temp_dir:
            tampered = Path(temp_dir) / "tampered.json"
            tampered.write_text(json.dumps(residual), encoding="utf-8")
            audit = self._audit(tampered)

        self.assertFalse(audit["audit_passed"])
        self.assertFalse(audit["checks"]["asset_drive_audit_byte_count_matches"])


if __name__ == "__main__":
    unittest.main()
