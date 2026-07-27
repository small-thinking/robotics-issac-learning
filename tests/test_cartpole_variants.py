from __future__ import annotations

import copy
import unittest

from tools.cartpole_variants import (
    RegistryError,
    build_planned_manifest,
    build_run_matrix,
    canonical_sha256,
    hydra_tokens,
    load_registry,
    validate_registry,
)


class CartpoleVariantRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()

    def test_registry_has_preregistered_matrix(self) -> None:
        self.assertEqual(len(self.registry["variants"]), 9)
        rows = build_run_matrix(self.registry)
        self.assertEqual(len(rows), 27)
        self.assertEqual(sum(row["status"] == "reused" for row in rows), 1)
        self.assertEqual(sum(row["status"] == "planned" for row in rows), 26)

    def test_train_includes_objective_but_eval_does_not(self) -> None:
        self.assertEqual(
            hydra_tokens(self.registry, "R_CV0", scope="train"),
            ["env.rewards.cart_vel.weight=0.0"],
        )
        self.assertEqual(
            hydra_tokens(self.registry, "R_CV0", scope="eval", profile_id="stress30"),
            ["env.episode_length_s=30.0"],
        )

    def test_interface_override_is_shared_by_train_and_eval(self) -> None:
        expected = ["env.actions.joint_effort.scale=50.0"]
        self.assertEqual(hydra_tokens(self.registry, "A_E50", scope="train"), expected)
        self.assertEqual(
            hydra_tokens(self.registry, "A_E50", scope="eval", profile_id="canonical5"),
            expected,
        )

    def test_array_and_null_serialization(self) -> None:
        self.assertEqual(
            hydra_tokens(self.registry, "T_B15", scope="train"),
            ["env.terminations.cart_out_of_bounds.params.bounds=[-1.5,1.5]"],
        )
        self.assertEqual(
            hydra_tokens(self.registry, "O_POS", scope="train"),
            ["env.observations.policy.joint_vel_rel=null"],
        )

    def test_unknown_path_fails_closed(self) -> None:
        broken = copy.deepcopy(self.registry)
        broken["variants"][1]["interface_overrides"][0]["path"] = "env.not_allowed"
        with self.assertRaisesRegex(RegistryError, "not allowlisted"):
            validate_registry(broken)

    def test_wrong_type_fails_closed(self) -> None:
        broken = copy.deepcopy(self.registry)
        broken["variants"][4]["objective_overrides"][0]["value"] = "strong"
        with self.assertRaisesRegex(RegistryError, "must have type number"):
            validate_registry(broken)

    def test_hash_is_independent_of_dictionary_key_order(self) -> None:
        reversed_registry = dict(reversed(list(self.registry.items())))
        self.assertEqual(
            canonical_sha256(self.registry), canonical_sha256(reversed_registry)
        )

    def test_planned_manifest_preserves_run_identity_and_contract(self) -> None:
        manifest = build_planned_manifest(
            self.registry,
            "A_E50",
            7,
            git_commit="a" * 40,
            git_dirty=False,
        )
        self.assertEqual(
            manifest["run_id"],
            "phase2_cartpole_controlled_ablation__A_E50__seed7",
        )
        self.assertEqual(manifest["status"], "planned")
        self.assertEqual(
            manifest["evaluation"]["fixed_environment_ids"],
            list(range(25)),
        )
        self.assertEqual(
            manifest["variant"]["expected_diff"],
            [{"path": "env.actions.joint_effort.scale", "value": 50.0}],
        )


if __name__ == "__main__":
    unittest.main()
