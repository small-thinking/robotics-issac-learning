from __future__ import annotations

import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_dofbot_pregrasp_machine_contract import (
    EXPECTED_MACHINE_CHECKS,
    PregraspContractVerificationError,
    load_contract,
    verify_machine_contract,
)

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = ROOT / "artifacts/dofbot/pregrasp_command_space_contract.json"
EXPECTED_COMMIT = "4b4fc8ab80db6a9f0260627cc7b93190b8e73c05"


def _source_hashes(preflight: dict[str, object]) -> dict[str, object]:
    sources = preflight["sources"]  # type: ignore[index]
    names = (
        "asset_contract",
        "scene_config",
        "pose_config",
        "actuator_config",
        "actuator_machine_result",
    )
    return {
        name: {
            "path": f"/workspace/{name}",
            "sha256": sources[name]["sha256"],  # type: ignore[index]
        }
        for name in names
    }


def passing_contract(preflight: dict[str, object]) -> dict[str, object]:
    motion = preflight["solver_probe"][  # type: ignore[index]
        "candidate_backend_motion_contract"
    ]
    goal = motion["goal_angles_deg"]  # type: ignore[index]
    actuator = preflight["actuator_runtime"]  # type: ignore[index]
    return {
        "schema_version": 1,
        "experiment": "dofbot_goal5_angled_pregrasp",
        "git_commit": EXPECTED_COMMIT,
        "sources": _source_hashes(preflight),
        "control": {
            "application_api": "Arm_serial_servo_write(id, angle, time)",
            "algorithm": "validated_joint_candidate",
            "controlled_joint_names": ["joint1", "joint2", "joint3", "joint4"],
            "target_joint_candidate_angles_deg": goal,
            "final_controller_api_command_angles_deg": goal,
            "validated_joint_candidate_command_reached": True,
            "policy_free": True,
            "actuator_runtime": actuator,
        },
        "measurement": {
            "observations": [{"step_index": 1}],
            "gravity_feed_forward_samples": [{"step_index": 1}],
            "gravity_feed_forward": {
                "sample_count": 1,
                "telemetry_complete": True,
            },
        },
        "acceptance": {
            "machine": {
                "checks": {name: True for name in EXPECTED_MACHINE_CHECKS},
                "machine_passed": True,
                "decision": "pregrasp_machine_passed",
                "failed_checks": [],
                "initial_position_error_m": 0.06,
                "final_position_error_m": 0.02,
                "position_improvement_m": 0.04,
                "final_approach_error_deg": 5.0,
                "final_closing_error_deg": 5.0,
                "maximum_contact_force_n": 0.0,
                "official_api_call_count": 12,
                "expected_official_api_call_count": 12,
                "candidate_backend_motion_contract": motion,
                "final_observed_angles_deg": goal,
                "final_backend_interpolated_target_angles_deg": goal,
                "final_joint_position_target_angles_deg": goal,
                "projected_joint_force_telemetry": {
                    "observation_count": 1,
                    "checks": {
                        (
                            "physx_projected_joint_force_telemetry_"
                            "available_for_every_observation"
                        ): True,
                        (
                            "implicit_actuator_pd_estimate_telemetry_"
                            "available_for_every_observation"
                        ): True,
                        "projected_force_and_pd_estimates_are_sample_aligned": True,
                    },
                },
                "maximum_backend_target_api_error_deg": 0.0,
                "maximum_target_buffer_backend_error_deg": 0.0,
                "maximum_allowed_target_buffer_alignment_error_deg": 0.05,
                "maximum_final_joint_tracking_error_deg": 0.5,
                "maximum_allowed_final_joint_tracking_error_deg": 1.0,
                "maximum_neutral_reset_error_deg": 0.5,
            },
            "visual": {"status": "pending_user_confirmation"},
            "goal5_complete": False,
        },
        "scope": {
            "real_hardware_commanded": False,
            "camera_used_as_controller_input": False,
            "wrist_twist_commanded": False,
            "gripper_commanded": False,
            "target_cube_moved": False,
            "contact_authorized": False,
            "policy_or_checkpoint_loaded": False,
        },
    }


def _explicit_check_keys(path: Path, function_name: str, marker: str | None = None) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef) or function.name != function_name:
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            is_checks_assignment = any(
                isinstance(target, ast.Name) and target.id == "checks"
                for target in node.targets
            )
            if not is_checks_assignment:
                continue
            keys = {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            if marker is None or marker in keys:
                return keys
    raise AssertionError(f"could not find checks in {path}:{function_name}")


class DofbotPregraspContractVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))

    def verify(self, contract: dict[str, object]) -> None:
        verify_machine_contract(
            contract,
            expected_git_commit=EXPECTED_COMMIT,
            preflight_contract=self.preflight,
            project_dir=ROOT,
        )

    def test_accepts_complete_matching_machine_pass(self) -> None:
        self.verify(passing_contract(self.preflight))

    def test_expected_check_set_matches_all_runner_producers(self) -> None:
        pose = _explicit_check_keys(
            ROOT / "tools/dofbot_pregrasp_pose.py",
            "evaluate_pregrasp_observation",
        )
        gravity = _explicit_check_keys(
            ROOT / "tools/dofbot_gravity_feed_forward.py",
            "evaluate_gravity_feed_forward_telemetry",
        )
        runner = _explicit_check_keys(
            ROOT / "tools/run_dofbot_pregrasp.py",
            "main",
            "accepted_actuator_machine_evidence_bound",
        )
        self.assertEqual(pose | gravity | runner, EXPECTED_MACHINE_CHECKS)
        self.assertEqual(len(EXPECTED_MACHINE_CHECKS), 37)

    def test_rejects_every_missing_or_non_boolean_check(self) -> None:
        for name in EXPECTED_MACHINE_CHECKS:
            with self.subTest(check=name, mutation="missing"):
                contract = passing_contract(self.preflight)
                del contract["acceptance"]["machine"]["checks"][name]  # type: ignore[index]
                with self.assertRaisesRegex(
                    PregraspContractVerificationError,
                    "check set",
                ):
                    self.verify(contract)
            with self.subTest(check=name, mutation="truthy_integer"):
                contract = passing_contract(self.preflight)
                contract["acceptance"]["machine"]["checks"][name] = 1  # type: ignore[index]
                with self.assertRaisesRegex(
                    PregraspContractVerificationError,
                    "non-passing",
                ):
                    self.verify(contract)

    def test_rejects_failed_machine_gate_even_when_launcher_returned_zero(self) -> None:
        contract = passing_contract(self.preflight)
        machine = contract["acceptance"]["machine"]  # type: ignore[index]
        machine["machine_passed"] = False
        machine["decision"] = "joint_tracking_failed"
        machine["failed_checks"] = ["final_api_joint_tracking_within_tolerance"]
        with self.assertRaisesRegex(
            PregraspContractVerificationError,
            "joint_tracking_failed",
        ):
            self.verify(contract)

    def test_rejects_previous_minimal_forged_pass_shape(self) -> None:
        minimal = {
            "git_commit": EXPECTED_COMMIT,
            "acceptance": {
                "machine": {
                    "machine_passed": True,
                    "decision": "pregrasp_machine_passed",
                    "failed_checks": [],
                }
            },
        }
        with self.assertRaises(PregraspContractVerificationError):
            self.verify(minimal)

    def test_rejects_stale_commit_source_motion_api_and_scope(self) -> None:
        mutations = (
            ("commit", lambda value: value.__setitem__("git_commit", "different")),
            (
                "source",
                lambda value: value["sources"]["pose_config"].__setitem__(  # type: ignore[index]
                    "sha256", "0" * 64
                ),
            ),
            (
                "motion",
                lambda value: value["acceptance"]["machine"][  # type: ignore[index]
                    "candidate_backend_motion_contract"
                ].__setitem__("duration_s", 0.2),
            ),
            (
                "api_count",
                lambda value: value["acceptance"]["machine"].__setitem__(  # type: ignore[index]
                    "official_api_call_count", 40
                ),
            ),
            (
                "scope",
                lambda value: value["scope"].__setitem__(  # type: ignore[index]
                    "gripper_commanded", True
                ),
            ),
        )
        for name, mutate in mutations:
            with self.subTest(mutation=name):
                contract = copy.deepcopy(passing_contract(self.preflight))
                mutate(contract)
                with self.assertRaises(PregraspContractVerificationError):
                    self.verify(contract)

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
