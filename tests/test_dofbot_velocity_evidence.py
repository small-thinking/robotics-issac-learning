from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_dofbot_velocity_reanalysis_evidence import build_evidence_audit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dofbot/calibration/goal5_solver_drive_diagnostic.json"
REMOTE_RESULT = ROOT / "artifacts/dofbot/actuator_calibration_result_2026-07-30.json"
REANALYSIS = ROOT / "artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json"


class DofbotVelocityEvidenceTests(unittest.TestCase):
    def test_promoted_reanalysis_bindings_pass(self) -> None:
        audit = build_evidence_audit(
            config_path=CONFIG,
            remote_result_path=REMOTE_RESULT,
            reanalysis_path=REANALYSIS,
        )
        self.assertTrue(audit["audit_passed"])
        self.assertTrue(all(audit["checks"].values()))
        self.assertFalse(audit["raw_payloads_required"])

    def test_tampered_source_binding_fails_closed(self) -> None:
        reanalysis = json.loads(REANALYSIS.read_text(encoding="utf-8"))
        reanalysis["cases"]["gravity_on_effort_100"]["source"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            tampered = Path(temp_dir) / "tampered.json"
            tampered.write_text(json.dumps(reanalysis), encoding="utf-8")
            audit = build_evidence_audit(
                config_path=CONFIG,
                remote_result_path=REMOTE_RESULT,
                reanalysis_path=tampered,
            )

        self.assertFalse(audit["audit_passed"])
        self.assertFalse(
            audit["checks"]["gravity_on_effort_100_sha256_binding_matches"]
        )


if __name__ == "__main__":
    unittest.main()
