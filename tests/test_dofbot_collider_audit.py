from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from tests.test_dofbot_scene_decomposition import artifact_for
from tools.dofbot_collider_audit import (
    ColliderAuditError,
    evaluate_collider_clearance,
    load_collider_audit_config,
    nearest_path_ancestor,
    signed_aabb_separation,
    summarize_collider_clearance_samples,
    transform_local_aabb,
)
from tools.prepare_dofbot_collider_audit import build_collider_audit_plan
from tools.summarize_dofbot_collider_audit import summarize_collider_audit
from tools.verify_dofbot_collider_audit_case import (
    ColliderAuditCaseError,
    verify_collider_audit_case,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dofbot/calibration/goal5_collider_audit.json"


def _robot_collider() -> dict:
    return {
        "prim_path": "/World/Dofbot/link2/collisions/mesh",
        "owner_body_name": "link2",
        "body_local_aabb": {
            "minimum_body_m": [-0.1, -0.05, -0.02],
            "maximum_body_m": [0.1, 0.05, 0.02],
        },
    }


def _table(minimum_y: float) -> dict:
    return {
        "prim_path": "/World/Table/geometry/mesh",
        "world_aabb": {
            "minimum_world_m": [-0.3, minimum_y, -0.1],
            "maximum_world_m": [0.3, minimum_y + 0.1, 0.1],
        },
    }


class ColliderAuditConfigTest(unittest.TestCase):
    def test_exact_two_cell_fail_closed_contract(self) -> None:
        config, sha256 = load_collider_audit_config(CONFIG)
        self.assertEqual(config.allowed_cells, ("S0", "T1"))
        self.assertEqual(config.maximum_executed_cells, 2)
        self.assertFalse(config.viewer_authorized)
        self.assertEqual(len(sha256), 64)

    def test_scope_or_evidence_weakening_is_rejected(self) -> None:
        original = json.loads(CONFIG.read_text(encoding="utf-8"))
        mutations = []
        extra_cell = copy.deepcopy(original)
        extra_cell["cells"].append("T0")
        mutations.append(extra_cell)
        viewer = copy.deepcopy(original)
        viewer["paid_window"]["viewer_authorized"] = True
        mutations.append(viewer)
        missing_evidence = copy.deepcopy(original)
        missing_evidence["required_evidence"][
            "per_step_closest_collider_pair"
        ] = False
        mutations.append(missing_evidence)
        with tempfile.TemporaryDirectory() as directory:
            for index, mutation in enumerate(mutations):
                path = Path(directory) / f"mutation-{index}.json"
                path.write_text(json.dumps(mutation), encoding="utf-8")
                with self.subTest(index=index), self.assertRaises(ColliderAuditError):
                    load_collider_audit_config(path)

    def test_gpu_free_plan_binds_completed_df048_result(self) -> None:
        result = build_collider_audit_plan(project_dir=ROOT, config_path=CONFIG)
        self.assertTrue(result["preflight_passed"])
        self.assertEqual(result["unresolved_ledger_id"], "DF-048")
        self.assertEqual(result["new_discriminator"]["cells"], ["S0", "T1"])
        self.assertFalse(result["authorization"]["paid_run"])


class ColliderAuditGeometryTest(unittest.TestCase):
    def test_quaternion_transform_rotates_conservative_aabb(self) -> None:
        root_half = math.sqrt(0.5)
        result = transform_local_aabb(
            minimum_body_m=[-0.1, -0.05, -0.02],
            maximum_body_m=[0.1, 0.05, 0.02],
            body_position_world_m=[1.0, 2.0, 3.0],
            body_quaternion_wxyz=[root_half, 0.0, 0.0, root_half],
        )
        for actual, expected in zip(
            result["minimum_world_m"], [0.95, 1.9, 2.98], strict=True
        ):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(
            result["maximum_world_m"], [1.05, 2.1, 3.02], strict=True
        ):
            self.assertAlmostEqual(actual, expected)

    def test_signed_separation_distinguishes_gap_and_overlap(self) -> None:
        a = {"minimum_world_m": [0, 0, 0], "maximum_world_m": [1, 1, 1]}
        gap = {"minimum_world_m": [1.3, 0, 0], "maximum_world_m": [2, 1, 1]}
        overlap = {
            "minimum_world_m": [0.8, 0.5, 0.5],
            "maximum_world_m": [2, 1.5, 1.5],
        }
        self.assertAlmostEqual(signed_aabb_separation(a, gap), 0.3)
        self.assertAlmostEqual(signed_aabb_separation(a, overlap), -0.2)

    def test_per_step_clearance_names_closest_collider_and_owner(self) -> None:
        result = evaluate_collider_clearance(
            robot_colliders=[_robot_collider()],
            table_colliders=[_table(0.2)],
            body_poses={
                "link2": {
                    "position_world_m": [0.0, 0.0, 0.0],
                    "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                }
            },
        )
        self.assertAlmostEqual(result["minimum_signed_aabb_separation_m"], 0.15)
        self.assertEqual(
            result["closest_pair"]["robot_owner_body_name"], "link2"
        )
        self.assertEqual(result["evaluated_pair_count"], 1)

    def test_summary_retains_first_overlap_and_closest_sample(self) -> None:
        samples = [
            {
                "pose_name": "mid_load",
                "pose_step": 4,
                "minimum_signed_aabb_separation_m": 0.02,
            },
            {
                "pose_name": "pregrasp_candidate",
                "pose_step": 9,
                "minimum_signed_aabb_separation_m": -0.004,
            },
        ]
        result = summarize_collider_clearance_samples(samples)
        self.assertTrue(result["overlap_observed"])
        self.assertEqual(result["first_overlap_sample"]["pose_step"], 9)
        self.assertEqual(result["closest_sample"]["pose_name"], "pregrasp_candidate")

    def test_nearest_path_ancestor_prefers_nested_body(self) -> None:
        self.assertEqual(
            nearest_path_ancestor(
                "/World/Dofbot/link5/Finger_Left_03/collisions/mesh",
                ["/World/Dofbot/link5", "/World/Dofbot/link5/Finger_Left_03"],
            ),
            "/World/Dofbot/link5/Finger_Left_03",
        )


def collider_artifact(cell_id: str, *, tracking_passed: bool) -> dict:
    artifact = artifact_for(cell_id, tracking_passed=tracking_passed)
    config, config_sha = load_collider_audit_config(CONFIG)
    robot = [
        {
            **_robot_collider(),
            "prim_type": "Mesh",
            "applied_schemas": ["PhysicsCollisionAPI"],
            "owner_body_path": "/World/Dofbot/link2",
            "owner_status": "resolved",
            "collision_enabled": True,
            "world_aabb": {
                "minimum_world_m": [-0.1, -0.05, -0.02],
                "maximum_world_m": [0.1, 0.05, 0.02],
            },
            "contact_offset": {"present": True, "authored": False, "value": -1},
            "rest_offset": {"present": True, "authored": False, "value": -1},
            "collision_approximation": {
                "present": False,
                "authored": False,
                "value": None,
            },
            "filtered_pairs_targets": [],
        }
    ]
    table = [] if cell_id == "S0" else [
        {
            **_table(0.2),
            "prim_type": "Cube",
            "applied_schemas": ["PhysicsCollisionAPI"],
            "owner_body_path": None,
            "owner_body_name": None,
            "owner_status": "static",
            "collision_enabled": True,
            "body_local_aabb": None,
            "contact_offset": {"present": True, "authored": False, "value": -1},
            "rest_offset": {"present": True, "authored": False, "value": -1},
            "collision_approximation": {
                "present": False,
                "authored": False,
                "value": None,
            },
            "filtered_pairs_targets": [],
        }
    ]
    clearance = evaluate_collider_clearance(
        robot_colliders=robot,
        table_colliders=table,
        body_poses={
            "link2": {
                "position_world_m": [0.0, 0.0, 0.0],
                "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
            }
        },
    )
    collider_sample = {
        "pose_name": "neutral_start",
        "pose_step": 0,
        "elapsed_s": 1 / 60,
        **clearance,
    }
    artifact["measurement"]["samples"] = [
        {"pose_step": 0, "collider_audit": collider_sample}
    ]
    artifact["telemetry"]["contact_events"].update(
        {
            "path_matching_mode": "same_or_descendant_of_monitored_rigid_body",
            "monitored_rigid_body_paths": ["/World/Dofbot/link2"],
            "all_actor_pairs": [],
            "normalized_monitored_actor_pairs": [],
        }
    )
    artifact["collider_audit"] = {
        "config_path": str(CONFIG),
        "config_sha256": config_sha,
        "config": config.to_dict(),
        "robot_colliders": robot,
        "table_colliders": table,
        "collision_filter_relationships": [],
        "clearance_summary": summarize_collider_clearance_samples(
            [collider_sample]
        ),
        "body_pose_source": "Isaac ArticulationData body_pos_w/body_quat_w",
        "aabb_method": "test",
        "aabb_is_conservative_not_exact_shape_distance": True,
    }
    return artifact


class ColliderAuditMachineContractTest(unittest.TestCase):
    def verify(self, artifact: dict, cell_id: str) -> dict:
        return verify_collider_audit_case(
            artifact,
            cell_id=cell_id,
            project_dir=ROOT,
            scene_config_path=(
                ROOT / "configs/dofbot/calibration/goal5_scene_decomposition.json"
            ),
            collider_config_path=CONFIG,
            expected_git_commit="test-scene-decomposition-commit",
        )

    def test_s0_and_t1_require_complete_collider_telemetry(self) -> None:
        s0 = self.verify(collider_artifact("S0", tracking_passed=True), "S0")
        t1 = self.verify(collider_artifact("T1", tracking_passed=False), "T1")
        self.assertEqual(s0["table_collider_count"], 0)
        self.assertEqual(t1["table_collider_count"], 1)
        self.assertAlmostEqual(t1["minimum_signed_aabb_separation_m"], 0.15)

    def test_unresolved_owner_fails_closed(self) -> None:
        artifact = collider_artifact("T1", tracking_passed=False)
        artifact["collider_audit"]["robot_colliders"][0]["owner_status"] = "missing"
        with self.assertRaisesRegex(ColliderAuditCaseError, "owner"):
            self.verify(artifact, "T1")

    def test_two_cell_summary_selects_remaining_mechanism_layer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            (input_dir / "cell_s0.json").write_text(
                json.dumps(collider_artifact("S0", tracking_passed=True)),
                encoding="utf-8",
            )
            (input_dir / "cell_t1.json").write_text(
                json.dumps(collider_artifact("T1", tracking_passed=False)),
                encoding="utf-8",
            )
            result = summarize_collider_audit(
                input_dir=input_dir,
                project_dir=ROOT,
                scene_config_path=(
                    ROOT / "configs/dofbot/calibration/goal5_scene_decomposition.json"
                ),
                collider_config_path=CONFIG,
                expected_git_commit="test-scene-decomposition-commit",
            )
        self.assertEqual(
            result["result"]["decision"],
            "no_aabb_overlap_contact_offset_filter_or_registration_remains",
        )
        self.assertFalse(result["authorization"]["viewer"])


if __name__ == "__main__":
    unittest.main()
