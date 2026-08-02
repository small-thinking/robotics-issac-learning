from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.audit_dofbot_context_transfer import (
    CURRENT_INTEGRATED_CONSUMER_PATHS,
    ContextTransferAuditError,
    _machine_source_bundle_bound,
    _normalized_function_ast,
    _source_bundle,
    build_context_transfer_audit,
)
from tools.dofbot_actuator_calibration import (
    calibration_trajectory_extrema,
    load_actuator_calibration_config,
)

ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_CONFIG = (
    ROOT
    / "configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json"
)
POSE_CONFIG = ROOT / "configs/dofbot/pregrasp/goal5_angled_pregrasp.json"
SCENE_CONFIG = (
    ROOT
    / "configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json"
)
ACCEPTED_RESULT = (
    ROOT / "artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json"
)
DIRECT_RESULT = (
    ROOT
    / "artifacts/dofbot/pregrasp_single_boundary_discriminator_2026-08-01.json"
)
DIRECT_CALIBRATION_CONFIG = (
    ROOT
    / "configs/dofbot/calibration/"
    "goal5_gravity_feed_forward_direct_diagnostic.json"
)


def build(
    *,
    calibration_config: Path = CALIBRATION_CONFIG,
    accepted_result: Path = ACCEPTED_RESULT,
) -> dict[str, object]:
    return build_context_transfer_audit(
        project_dir=ROOT,
        calibration_config_path=calibration_config,
        pregrasp_pose_config_path=POSE_CONFIG,
        pregrasp_scene_config_path=SCENE_CONFIG,
        accepted_machine_result_path=accepted_result,
        direct_machine_result_path=DIRECT_RESULT,
    )


class DofbotContextTransferAuditTest(unittest.TestCase):
    def test_static_scene_spawner_matches_integrated_runner(self) -> None:
        self.assertEqual(
            _normalized_function_ast(
                ROOT / "tools/run_dofbot_pregrasp.py",
                "_spawn_scene_boxes",
            ),
            _normalized_function_ast(
                ROOT / "tools/dofbot_pregrasp_scene_cfg.py",
                "spawn_static_reaching_boxes",
            ),
        )

    def test_direct_isolated_config_changes_only_candidate_entry_history(self) -> None:
        split, _ = load_actuator_calibration_config(CALIBRATION_CONFIG)
        direct, _ = load_actuator_calibration_config(DIRECT_CALIBRATION_CONFIG)
        split_value = split.to_dict()
        direct_value = direct.to_dict()
        split_value["name"] = direct_value["name"]
        split_value["poses"][1] = direct_value["poses"][1]
        self.assertEqual(split_value, direct_value)
        self.assertEqual(
            direct.poses[1].angles_deg,
            (90, 90, 90, 90),
        )
        self.assertEqual(
            calibration_trajectory_extrema(direct),
            {
                "maximum_transition_delta_deg": 24.0,
                "smoothstep_peak_velocity_deg_s": 18.0,
                "smoothstep_peak_acceleration_deg_s2": 36.0,
            },
        )

    def test_audit_rejects_false_protocol_equivalence(self) -> None:
        result = build()
        self.assertTrue(result["analysis"]["audit_complete"])  # type: ignore[index]
        self.assertFalse(
            result["analysis"]["df_035_equivalence_claim_valid"]  # type: ignore[index]
        )
        self.assertTrue(
            result["analysis"][  # type: ignore[index]
                "df_039_falsifies_direct_90_to_66_transition"
            ]
        )
        self.assertFalse(
            result["analysis"][  # type: ignore[index]
                "df_039_falsifies_safe_90_to_78_to_66_path"
            ]
        )
        isolated = result["protocols"][  # type: ignore[index]
            "accepted_isolated_calibration"
        ]
        integrated = result["protocols"][  # type: ignore[index]
            "failed_integrated_direct_pregrasp"
        ]
        self.assertEqual(
            isolated["candidate_start_angles_deg"],
            [90.0, 78.0, 78.0, 78.0],
        )
        self.assertEqual(
            isolated["candidate_motion_contract"][  # type: ignore[index]
                "maximum_peak_velocity_deg_s"
            ],
            9.0,
        )
        self.assertEqual(
            isolated["candidate_motion_contract"][  # type: ignore[index]
                "maximum_peak_acceleration_deg_s2"
            ],
            18.0,
        )
        self.assertEqual(
            isolated["full_sequence_extrema"][  # type: ignore[index]
                "maximum_transition_delta_deg"
            ],
            24.0,
        )
        self.assertEqual(
            integrated["candidate_start_angles_deg"],
            [90.0, 90.0, 90.0, 90.0],
        )
        self.assertEqual(
            integrated["candidate_motion_contract"][  # type: ignore[index]
                "maximum_peak_velocity_deg_s"
            ],
            18.0,
        )

    def test_old_machine_result_cannot_validate_current_source_bundle(self) -> None:
        result = build()
        provenance = result["runtime_provenance"]
        self.assertFalse(  # type: ignore[index]
            provenance["accepted_machine_result_contains_source_bundle"]
        )
        self.assertFalse(  # type: ignore[index]
            provenance["current_runtime_machine_regression_validated"]
        )
        self.assertFalse(
            result["analysis"]["integrated_pregrasp_authorized"]  # type: ignore[index]
        )
        bundle = provenance["current_integrated_consumer_bundle"]  # type: ignore[index]
        self.assertEqual(
            set(bundle["files"]),
            set(CURRENT_INTEGRATED_CONSUMER_PATHS),
        )
        self.assertRegex(bundle["sha256"], r"^[0-9a-f]{64}$")

    def test_machine_result_requires_explicit_source_bundle_fields(self) -> None:
        self.assertFalse(_machine_source_bundle_bound({"sha256": "0" * 64}))
        current = build()["runtime_provenance"][  # type: ignore[index]
            "current_shared_runtime_bundle"
        ]
        self.assertTrue(_machine_source_bundle_bound(current))
        tampered = copy.deepcopy(current)
        tampered["files"][CURRENT_INTEGRATED_CONSUMER_PATHS[0]] = "0" * 64
        self.assertFalse(_machine_source_bundle_bound(tampered))

    def test_missing_runtime_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative_path in CURRENT_INTEGRATED_CONSUMER_PATHS:
                destination = root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = ROOT / relative_path
                destination.write_bytes(source.read_bytes())
            (root / CURRENT_INTEGRATED_CONSUMER_PATHS[0]).unlink()
            with self.assertRaisesRegex(
                ContextTransferAuditError,
                "runtime source is missing",
            ):
                _source_bundle(
                    project_dir=root,
                    paths=CURRENT_INTEGRATED_CONSUMER_PATHS,
                )

    def test_matrix_is_fail_fast_and_does_not_repeat_direct_cell(self) -> None:
        result = build()
        matrix = result["next_machine_matrix"]
        cells = {cell["id"]: cell for cell in matrix["cells"]}  # type: ignore[index]
        self.assertEqual(set(cells), {"A", "B", "C", "D"})
        self.assertTrue(cells["A"]["fail_fast"])
        self.assertEqual(cells["B"]["requires"], "A passes")
        self.assertEqual(cells["C"]["requires"], "A passes")
        self.assertIn("do not rerun", cells["D"]["role"])
        self.assertTrue(
            matrix["paid_run_requires_fresh_quote_and_explicit_approval"]  # type: ignore[index]
        )
        self.assertTrue(matrix["viewer_blocked"])  # type: ignore[index]

    def test_source_bundle_digest_is_content_bound(self) -> None:
        result = build()
        bundle = result["runtime_provenance"][  # type: ignore[index]
            "current_integrated_consumer_bundle"
        ]
        canonical = "".join(
            f"{path}\0{sha256}\n"
            for path, sha256 in sorted(bundle["files"].items())
        ).encode()
        self.assertEqual(bundle["sha256"], hashlib.sha256(canonical).hexdigest())


if __name__ == "__main__":
    unittest.main()
