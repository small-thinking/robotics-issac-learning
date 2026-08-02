from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.verify_dofbot_pregrasp_gpu_preflight import (
    EXPECTED_PREFLIGHT_CHECKS,
    PregraspGpuPreflightError,
    verify_gpu_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "artifacts/dofbot/pregrasp_command_space_contract.json"


class DofbotPregraspGpuPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def verify(self, contract: dict[str, object]) -> None:
        verify_gpu_preflight(contract, project_dir=ROOT)

    def test_tracked_gpu_input_bundle_passes(self) -> None:
        self.verify(self.contract)
        self.assertEqual(len(EXPECTED_PREFLIGHT_CHECKS), 27)

    def test_every_preflight_check_is_required_and_strict_boolean(self) -> None:
        for name in EXPECTED_PREFLIGHT_CHECKS:
            with self.subTest(check=name, mutation="missing"):
                contract = copy.deepcopy(self.contract)
                del contract["acceptance"]["checks"][name]
                with self.assertRaisesRegex(PregraspGpuPreflightError, "check set"):
                    self.verify(contract)
            with self.subTest(check=name, mutation="truthy_integer"):
                contract = copy.deepcopy(self.contract)
                contract["acceptance"]["checks"][name] = 1
                with self.assertRaisesRegex(
                    PregraspGpuPreflightError,
                    "acceptance checks failed",
                ):
                    self.verify(contract)

    def test_source_hash_motion_scope_and_collision_mutations_fail_closed(self) -> None:
        mutations = (
            (
                "source_hash",
                lambda value: value["sources"]["pregrasp_runner"].__setitem__(
                    "sha256", "0" * 64
                ),
            ),
            (
                "extra_boundary",
                lambda value: value["solver_probe"]["command_trajectory"].append(
                    copy.deepcopy(value["solver_probe"]["command"])
                ),
            ),
            (
                "short_duration",
                lambda value: value["solver_probe"][
                    "candidate_backend_motion_contract"
                ].__setitem__("duration_s", 0.2),
            ),
            (
                "gpu_started",
                lambda value: value["scope"].__setitem__("gpu_started", True),
            ),
            (
                "collision_accepted",
                lambda value: value["collision_probe"].__setitem__(
                    "deliberate_terminal_finger_collision_passed", True
                ),
            ),
        )
        for name, mutate in mutations:
            with self.subTest(mutation=name):
                contract = copy.deepcopy(self.contract)
                mutate(contract)
                with self.assertRaises(PregraspGpuPreflightError):
                    self.verify(contract)


if __name__ == "__main__":
    unittest.main()
