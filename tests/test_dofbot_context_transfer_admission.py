from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_dofbot_context_transfer_admission import (
    ContextTransferAdmissionError,
    verify_context_transfer_admission,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "artifacts/dofbot/pregrasp_context_transfer_audit.json"


class DofbotContextTransferAdmissionTest(unittest.TestCase):
    def test_current_audit_is_fresh_but_blocks_integrated_runner(self) -> None:
        with self.assertRaisesRegex(
            ContextTransferAdmissionError,
            "run and promote the A/B/C",
        ):
            verify_context_transfer_admission(
                contract_path=CONTRACT,
                project_dir=ROOT,
            )

    def test_stale_source_bundle_is_rejected_before_authorization(self) -> None:
        recorded = json.loads(CONTRACT.read_text(encoding="utf-8"))
        recorded["runtime_provenance"]["current_shared_runtime_bundle"][
            "sha256"
        ] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stale.json"
            path.write_text(json.dumps(recorded), encoding="utf-8")
            with self.assertRaisesRegex(
                ContextTransferAdmissionError,
                "stale relative",
            ):
                verify_context_transfer_admission(
                    contract_path=path,
                    project_dir=ROOT,
                )


if __name__ == "__main__":
    unittest.main()
