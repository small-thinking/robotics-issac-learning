from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_dofbot_context_transfer import (
    CURRENT_SHARED_RUNTIME_PATHS,
    _source_bundle,
)
from tools.dofbot_actuator_calibration import load_actuator_calibration_config
from tools.dofbot_reaching import load_reaching_config
from tools.dofbot_scene_decomposition import (
    SceneDecompositionError,
    classify_scene_decomposition_results,
    load_scene_decomposition_config,
    next_scene_decomposition_cell,
)
from tools.prepare_dofbot_scene_decomposition import build_scene_decomposition_plan
from tools.summarize_dofbot_scene_decomposition_matrix import (
    SceneDecompositionMatrixError,
    summarize_scene_decomposition_matrix,
)
from tools.verify_dofbot_scene_decomposition_case import (
    SceneDecompositionCaseError,
    verify_scene_decomposition_case,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/dofbot/calibration/goal5_scene_decomposition.json"
COMMIT = "test-scene-decomposition-commit"


def _runtime_object(planned: dict) -> dict:
    center = planned["center_world_m"]
    size = planned["size_m"]
    return {
        **planned,
        "prim_present": True,
        "root_prim_type": "Cube",
        "descendant_prim_count": 1,
        "descendant_prim_types": ["Cube"],
        "collision_api_paths": (
            [planned["prim_path"]] if planned["collision_enabled"] else []
        ),
        "collision_enabled_readback": planned["collision_enabled"],
        "rigid_body_api_paths": [],
        "static_readback": True,
        "translation_world_m_readback": center,
        "axis_aligned_world_bounds_readback": {
            "minimum_world_m": [
                center[index] - size[index] / 2.0 for index in range(3)
            ],
            "maximum_world_m": [
                center[index] + size[index] / 2.0 for index in range(3)
            ],
        },
    }


def artifact_for(cell_id: str, *, tracking_passed: bool = True) -> dict:
    config, config_sha = load_scene_decomposition_config(CONFIG_PATH)
    cell = config.cell(cell_id)
    calibration_path = ROOT / config.calibration_config
    calibration, calibration_sha = load_actuator_calibration_config(calibration_path)
    scene_path = ROOT / config.source_scene_config
    scene, scene_sha = load_reaching_config(scene_path)
    spawn_plan = []
    for name in cell.objects:
        box = scene.table if name == "table" else scene.target_cube
        spawn_plan.append(
            {
                "name": name,
                "prim_path": box.prim_path,
                "center_world_m": [
                    box.center_world_m[index]
                    + cell.translation_offset_world_m[index]
                    for index in range(3)
                ],
                "size_m": list(box.size_m),
                "collision_enabled": cell.collision_enabled,
                "rigid_body_authored": False,
            }
        )
    maximum_tracking = 0.25 if tracking_passed else 4.2
    return {
        "schema_version": 1,
        "experiment": "dofbot_actuator_diagnostic_case",
        "git_commit": COMMIT,
        "runtime_source_bundle": _source_bundle(
            project_dir=ROOT,
            paths=CURRENT_SHARED_RUNTIME_PATHS,
        ),
        "asset_contract": {"sha256": "0" * 64},
        "calibration_config": {"sha256": calibration_sha},
        "context_scene_config": {"sha256": scene_sha},
        "scene_decomposition": {
            "config_sha256": config_sha,
            "cell": cell.to_dict(),
            "spawn_plan": spawn_plan,
            "runtime_readback": [_runtime_object(value) for value in spawn_plan],
            "clearance": {
                "objects": {
                    value["name"]: {
                        "minimum_terminal_body_center_aabb_distance_m": 0.02,
                        "closest_terminal_body": "Finger_Left_03",
                        "closest_pose": "pregrasp_candidate",
                        "evaluated_body_samples": 12,
                    }
                    for value in spawn_plan
                },
                "body_center_proxy_is_not_mesh_clearance": True,
            },
        },
        "case": {
            "name": "bounded_gravity_feed_forward",
            "gravity_enabled": True,
            "effort_limit_sim": 100.0,
            "stiffness": 1048.0,
            "damping": 53.0,
            "solver_position_iteration_count": 8,
            "solver_velocity_iteration_count": 0,
            "enable_external_forces_every_iteration": True,
            "drive_type": "force",
            "gravity_compensation_feed_forward": True,
            "gravity_compensation_effort_limit": 5.2,
        },
        "physics_snapshot": {
            "joint_names": [f"joint-{index}" for index in range(11)],
            "body_names": [f"body-{index}" for index in range(12)],
            "controlled_joint_ids": [0, 1, 2, 3],
            "terminal_body_ids": {
                "Wrist_Twist": 5,
                "Finger_Left_03": 10,
                "Finger_Right_03": 11,
            },
            "root_physx_view_shape": {"count": 1, "max_links": 12, "max_dofs": 11},
        },
        "telemetry": {
            "contact_events": {
                "callback_count": 0,
                "contact_header_count": 0,
                "monitored_actor_pairs": [],
            }
        },
        "measurement": {
            "pose_summaries": [
                {
                    "name": pose.name,
                    "command_angles_deg": list(pose.angles_deg),
                    "maximum_tracking_error_deg": maximum_tracking,
                }
                for pose in calibration.poses
            ],
            "samples": [{"pose_step": 0}],
        },
        "evaluation": {
            "checks": {"telemetry_complete": True},
            "diagnostic_complete": True,
            "tracking_gate_passed": tracking_passed,
            "maximum_settled_tracking_error_deg": maximum_tracking,
        },
        "scope": {
            "table_or_cube_spawned": bool(cell.objects),
            "viewer_started": False,
            "camera_tensor_captured": False,
            "real_hardware_commanded": False,
            "policy_or_checkpoint_loaded": False,
            "contact_or_grasp_authorized": False,
        },
    }


class SceneDecompositionConfigTest(unittest.TestCase):
    def test_exact_single_factor_cell_contract(self) -> None:
        config, _ = load_scene_decomposition_config(CONFIG_PATH)
        self.assertEqual(len(config.cells), 10)
        self.assertEqual(config.maximum_executed_cells, 6)
        self.assertFalse(config.viewer_authorized)

    def test_mutated_cell_or_paid_window_fails_closed(self) -> None:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        mutations = []
        changed_cell = copy.deepcopy(raw)
        changed_cell["cells"][1]["objects"] = ["table", "target_cube"]
        mutations.append(changed_cell)
        changed_gate = copy.deepcopy(raw)
        changed_gate["acceptance"]["maximum_settled_tracking_error_deg"] = 5
        mutations.append(changed_gate)
        changed_scope = copy.deepcopy(raw)
        changed_scope["paid_window"]["viewer_authorized"] = True
        mutations.append(changed_scope)
        with tempfile.TemporaryDirectory() as directory:
            for index, mutation in enumerate(mutations):
                path = Path(directory) / f"mutation-{index}.json"
                path.write_text(json.dumps(mutation), encoding="utf-8")
                with self.subTest(index=index), self.assertRaises(SceneDecompositionError):
                    load_scene_decomposition_config(path)

    def test_adaptive_paths_stop_after_one_completed_branch(self) -> None:
        paths = (
            ({"S0": False}, "current_source_regression"),
            (
                {"S0": True, "T1": False, "T0": True, "TF": True},
                "near_table_collision_context_is_causal",
            ),
            (
                {
                    "S0": True,
                    "T1": True,
                    "Q1": False,
                    "Q0": False,
                    "QF": True,
                },
                "near_cube_spawn_geometry_is_causal",
            ),
            (
                {
                    "S0": True,
                    "T1": True,
                    "Q1": True,
                    "P1": False,
                    "P0": True,
                    "PF": True,
                },
                "near_pair_collision_context_is_causal",
            ),
        )
        for results, expected in paths:
            with self.subTest(expected=expected):
                self.assertIsNone(next_scene_decomposition_cell(results))
                self.assertEqual(classify_scene_decomposition_results(results), expected)


class SceneDecompositionPreparationTest(unittest.TestCase):
    def test_plan_binds_df046_and_blocks_paid_scope(self) -> None:
        result = build_scene_decomposition_plan(
            project_dir=ROOT,
            config_path=CONFIG_PATH,
            context_matrix_path=ROOT / "artifacts/dofbot/context_transfer_matrix_contract.json",
            taskspace_path=ROOT / "artifacts/dofbot/pregrasp_taskspace_candidate.json",
        )
        self.assertTrue(result["preflight_passed"])
        self.assertEqual(result["ledger_discriminator"], "DF-047")
        self.assertFalse(result["authorization"]["paid_run"])
        self.assertEqual(result["adaptive_execution"]["maximum_executed_cells"], 6)
        self.assertTrue(
            result["offline_scene_spawn_audit"]
            ["historical_df_046_changed_two_objects_together"]
        )


class SceneDecompositionCaseVerifierTest(unittest.TestCase):
    def verify(self, artifact: dict, cell_id: str, **kwargs: object) -> dict:
        return verify_scene_decomposition_case(
            artifact,
            cell_id=cell_id,
            project_dir=ROOT,
            config_path=CONFIG_PATH,
            expected_git_commit=COMMIT,
            **kwargs,
        )

    def test_every_cell_has_a_strict_machine_contract(self) -> None:
        config, _ = load_scene_decomposition_config(CONFIG_PATH)
        for cell in config.cells:
            with self.subTest(cell=cell.id):
                self.assertTrue(self.verify(artifact_for(cell.id), cell.id)["integrity_passed"])

    def test_sentinel_fails_fast_but_scientific_cells_may_fail_tracking(self) -> None:
        with self.assertRaisesRegex(SceneDecompositionCaseError, "sentinel"):
            self.verify(artifact_for("S0", tracking_passed=False), "S0")
        result = self.verify(artifact_for("T1", tracking_passed=False), "T1")
        self.assertFalse(result["tracking_gate_passed"])

    def test_runtime_collision_and_index_mutations_fail_closed(self) -> None:
        wrong_collision = artifact_for("T1")
        wrong_collision["scene_decomposition"]["runtime_readback"][0][
            "collision_enabled_readback"
        ] = False
        wrong_index = artifact_for("S0")
        wrong_index["physics_snapshot"]["controlled_joint_ids"] = [1, 2, 3, 4]
        for artifact, cell_id in ((wrong_collision, "T1"), (wrong_index, "S0")):
            with self.subTest(cell=cell_id), self.assertRaises(SceneDecompositionCaseError):
                self.verify(artifact, cell_id)


class SceneDecompositionMatrixTest(unittest.TestCase):
    def test_summarizer_accepts_only_the_selected_adaptive_branch(self) -> None:
        branch = {"S0": True, "T1": False, "T0": True, "TF": True}
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            for cell_id, passed in branch.items():
                (input_dir / f"cell_{cell_id.lower()}.json").write_text(
                    json.dumps(artifact_for(cell_id, tracking_passed=passed)),
                    encoding="utf-8",
                )
            result = summarize_scene_decomposition_matrix(
                input_dir=input_dir,
                project_dir=ROOT,
                config_path=CONFIG_PATH,
                expected_git_commit=COMMIT,
            )
        self.assertEqual(result["matrix"]["executed_cells"], list(branch))
        self.assertEqual(
            result["matrix"]["decision"],
            "near_table_collision_context_is_causal",
        )
        self.assertFalse(result["authorization"]["viewer"])

    def test_summarizer_rejects_extra_nonadaptive_cells(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            for cell_id in ("S0", "T1", "T0", "TF", "Q1"):
                passed = cell_id not in {"T1"}
                (input_dir / f"cell_{cell_id.lower()}.json").write_text(
                    json.dumps(artifact_for(cell_id, tracking_passed=passed)),
                    encoding="utf-8",
                )
            with self.assertRaisesRegex(SceneDecompositionMatrixError, "outside"):
                summarize_scene_decomposition_matrix(
                    input_dir=input_dir,
                    project_dir=ROOT,
                    config_path=CONFIG_PATH,
                    expected_git_commit=COMMIT,
                )


if __name__ == "__main__":
    unittest.main()
