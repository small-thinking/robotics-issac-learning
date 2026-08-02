from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "cpu-quality-gate.yml"
SCRIPT = ROOT / "scripts" / "local" / "run_cpu_ci.sh"


class CpuCiWorkflowTests(unittest.TestCase):
    def test_workflow_is_bounded_and_reproducible(self) -> None:
        workflow = WORKFLOW.read_text()

        self.assertIn("pull_request:", workflow)
        self.assertRegex(workflow, r"push:\n\s+branches:\n\s+- main")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertIn("timeout-minutes: 20", workflow)
        self.assertIn("run: make ci-cpu", workflow)
        self.assertIn("run: git diff --exit-code", workflow)
        self.assertNotIn("self-hosted", workflow)

        action_references = re.findall(r"uses:\s+[^@\s]+@([^\s]+)", workflow)
        self.assertTrue(action_references)
        for reference in action_references:
            self.assertRegex(reference, r"^[0-9a-f]{40}$")

    def test_cpu_entry_point_covers_every_offline_dofbot_target(self) -> None:
        script = SCRIPT.read_text()
        expected_targets = (
            "dofbot-api-dry-run",
            "dofbot-motion-config-dry-run",
            "dofbot-reach-dry-run",
            "dofbot-pregrasp-dry-run",
            "dofbot-pregrasp-pose-dry-run",
            "dofbot-gpu-preflight",
            "dofbot-pregrasp-reachability",
            "dofbot-pregrasp-taskspace",
            "dofbot-actuator-calibration-dry-run",
            "dofbot-solver-drive-dry-run",
            "dofbot-drive-model-dry-run",
            "dofbot-actuator-velocity-reanalysis",
            "dofbot-actuator-velocity-evidence-audit",
            "dofbot-residual-force-audit",
            "dofbot-residual-force-evidence-audit",
            "dofbot-gravity-feed-forward-dry-run",
        )
        for target in expected_targets:
            self.assertIn(f"make {target}", script)

        self.assertIn("make test", script)
        self.assertIn("make study-validate", script)
        self.assertIn("ruff 0.15.0", script)
        self.assertIn("uvx --from ruff==0.15.0", script)
        self.assertIn("python -m compileall", script)
        self.assertIn("bash -n", script)
        self.assertIn("python -m json.tool", script)
        self.assertIn("pregrasp_command_space_contract.json", script)
        self.assertIn('export UV_TOOL_DIR="${UV_TOOL_DIR:-$ci_tmp_dir/uv-tools}"', script)
        self.assertIn("ACTUATOR_CALIBRATION_CASES", script)
        self.assertIn("Raw velocity payloads are intentionally untracked", script)
        self.assertIn("DRIVE_MODEL_DIAGNOSTIC_CASES", script)
        self.assertIn("Raw residual-force payloads are intentionally untracked", script)

    def test_cpu_entry_point_cannot_start_paid_or_isaac_runtime_work(self) -> None:
        script = SCRIPT.read_text()
        forbidden_commands = (
            "brev start",
            "make provision",
            "make dofbot-inspect",
            "make dofbot-view",
            "make dofbot-pregrasp\n",
            "make dofbot-pregrasp-view",
        )
        for command in forbidden_commands:
            self.assertNotIn(command, script)

        makefile = (ROOT / "Makefile").read_text()
        self.assertRegex(makefile, r"(?m)^ci-cpu:\n\t@\./scripts/local/run_cpu_ci\.sh$")


if __name__ == "__main__":
    unittest.main()
