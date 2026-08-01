from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_dofbot_pregrasp_machine_contract import (
    PregraspContractVerificationError,
    load_contract,
    verify_machine_contract,
)

EXPECTED_COMMIT = "4b4fc8ab80db6a9f0260627cc7b93190b8e73c05"


def passing_contract() -> dict[str, object]:
    return {
        "git_commit": EXPECTED_COMMIT,
        "acceptance": {
            "machine": {
                "machine_passed": True,
                "decision": "pregrasp_machine_passed",
                "failed_checks": [],
            }
        },
    }


class DofbotPregraspContractVerifierTest(unittest.TestCase):
    def test_accepts_matching_machine_pass(self) -> None:
        verify_machine_contract(
            passing_contract(),
            expected_git_commit=EXPECTED_COMMIT,
        )

    def test_rejects_failed_machine_gate_even_when_launcher_returned_zero(self) -> None:
        contract = passing_contract()
        machine = contract["acceptance"]["machine"]  # type: ignore[index]
        machine["machine_passed"] = False
        machine["decision"] = "joint_tracking_failed"
        machine["failed_checks"] = [
            "grasp_origin_reached_pregrasp_position",
            "final_api_joint_tracking_within_tolerance",
        ]
        with self.assertRaisesRegex(
            PregraspContractVerificationError,
            "joint_tracking_failed",
        ):
            verify_machine_contract(
                contract,
                expected_git_commit=EXPECTED_COMMIT,
            )

    def test_rejects_stale_commit(self) -> None:
        with self.assertRaisesRegex(
            PregraspContractVerificationError,
            "git commit mismatch",
        ):
            verify_machine_contract(
                passing_contract(),
                expected_git_commit="different-commit",
            )

    def test_rejects_missing_machine_payload(self) -> None:
        with self.assertRaisesRegex(
            PregraspContractVerificationError,
            "acceptance.machine",
        ):
            verify_machine_contract(
                {"git_commit": EXPECTED_COMMIT},
                expected_git_commit=EXPECTED_COMMIT,
            )

    def test_load_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps([]), encoding="utf-8")
            with self.assertRaisesRegex(
                PregraspContractVerificationError,
                "JSON object",
            ):
                load_contract(path)


if __name__ == "__main__":
    unittest.main()
