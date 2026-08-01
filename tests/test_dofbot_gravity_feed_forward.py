from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.dofbot_actuator_calibration import (
    GRAVITY_FEED_FORWARD_CASE_NAMES,
    ActuatorCalibrationError,
    classify_calibration_matrix,
    load_actuator_calibration_config,
    parse_actuator_calibration_config,
)
from tools.dofbot_gravity_feed_forward import (
    ACCEPTED_GRAVITY_FEED_FORWARD_CONFIG_SHA256,
    ACCEPTED_GRAVITY_FEED_FORWARD_RESULT_SHA256,
    REQUIRED_GRAVITY_RUNTIME_APIS,
    GravityFeedForwardError,
    evaluate_gravity_feed_forward_telemetry,
    load_accepted_gravity_feed_forward_runtime,
    prepare_bounded_gravity_feed_forward,
)
from tools.preview_dofbot_gravity_feed_forward import (
    build_gravity_feed_forward_preview,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    PROJECT_DIR
    / "configs/dofbot/calibration/"
    "goal5_gravity_feed_forward_diagnostic.json"
)
AUDIT_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/residual_force_audit_2026-07-30.json"
)
RUNNER_PATH = PROJECT_DIR / "tools/run_dofbot_actuator_calibration.py"
PREGRASP_RUNNER_PATH = PROJECT_DIR / "tools/run_dofbot_pregrasp.py"
RUNTIME_PATH = PROJECT_DIR / "tools/dofbot_gravity_feed_forward_runtime.py"
MACHINE_RESULT_PATH = (
    PROJECT_DIR
    / "artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json"
)
RUN_SCRIPT_PATH = (
    PROJECT_DIR
    / "scripts/isaac/run_dofbot_actuator_calibration.sh"
)


def _matrix_evaluation(*, tracking_passed: bool) -> dict[str, object]:
    return {
        "checks": {
            "gravity_compensation_runtime_apis_available": True,
            "gravity_compensation_values_finite": True,
            "feed_forward_effort_bounded": True,
            "only_controlled_joints_receive_feed_forward": True,
            "contact_force_below_threshold": True,
            "target_buffer_telemetry_available": True,
            "target_buffer_matches_backend_target": True,
            "position_derived_velocity_available": True,
            "all_poses_settled_by_position_derived_velocity": True,
        },
        "diagnostic_complete": True,
        "tracking_gate_passed": tracking_passed,
    }


class DofbotGravityFeedForwardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, cls.config_sha256 = load_actuator_calibration_config(
            CONFIG_PATH
        )

    def test_config_is_a_two_case_single_factor_comparison(self) -> None:
        self.assertEqual(
            self.config.case_names,
            GRAVITY_FEED_FORWARD_CASE_NAMES,
        )
        baseline, treatment = self.config.cases
        self.assertFalse(baseline.gravity_compensation_feed_forward)
        self.assertTrue(treatment.gravity_compensation_feed_forward)
        for case in self.config.cases:
            self.assertTrue(case.gravity_enabled)
            self.assertEqual(case.drive_type, "force")
            self.assertEqual(case.stiffness, 1048.0)
            self.assertEqual(case.damping, 53.0)
            self.assertEqual(case.effort_limit_sim, 100.0)
            self.assertTrue(case.enable_external_forces_every_iteration)
            self.assertEqual(case.gravity_compensation_effort_limit, 5.2)
        baseline_dict = baseline.to_dict()
        treatment_dict = treatment.to_dict()
        changed = {
            key
            for key in baseline_dict
            if key != "name"
            and baseline_dict[key] != treatment_dict[key]
        }
        self.assertEqual(
            changed,
            {"gravity_compensation_feed_forward"},
        )
        self.assertEqual(len(self.config_sha256), 64)

    def test_schema_rejects_confounded_or_unbounded_cases(self) -> None:
        confounded = copy.deepcopy(self.raw)
        confounded["cases"][1]["stiffness"] = 1100
        with self.assertRaisesRegex(
            ActuatorCalibrationError,
            "change only gravity_compensation_feed_forward",
        ):
            parse_actuator_calibration_config(confounded)

        excessive = copy.deepcopy(self.raw)
        excessive["cases"][1]["gravity_compensation_effort_limit"] = 5.3
        with self.assertRaisesRegex(
            ActuatorCalibrationError,
            r"\[0.1, 5.2\]",
        ):
            parse_actuator_calibration_config(excessive)

        missing = copy.deepcopy(self.raw)
        del missing["cases"][0]["gravity_compensation_feed_forward"]
        with self.assertRaisesRegex(ActuatorCalibrationError, "keys must match"):
            parse_actuator_calibration_config(missing)

    def test_bounding_clamps_controlled_and_zeros_every_other_dof(self) -> None:
        result = prepare_bounded_gravity_feed_forward(
            gravity_compensation_efforts=[
                0.1,
                8.0,
                -6.0,
                1.5,
                2.0,
                3.0,
            ],
            dof_count=6,
            controlled_joint_ids=[0, 1, 2, 3],
            enabled=True,
            maximum_effort=5.2,
        )
        self.assertEqual(
            result["applied_all_dof_efforts"],
            [0.1, 5.2, -5.2, 1.5, 0.0, 0.0],
        )
        self.assertEqual(result["clipped_controlled_joint_ids"], [1, 2])

        baseline = prepare_bounded_gravity_feed_forward(
            gravity_compensation_efforts=[0.1] * 6,
            dof_count=6,
            controlled_joint_ids=[0, 1, 2, 3],
            enabled=False,
            maximum_effort=5.2,
        )
        self.assertEqual(
            baseline["applied_all_dof_efforts"],
            [0.0] * 6,
        )

    def test_bounding_rejects_nonfinite_shape_and_bad_joint_ids(self) -> None:
        with self.assertRaisesRegex(GravityFeedForwardError, "finite"):
            prepare_bounded_gravity_feed_forward(
                gravity_compensation_efforts=[0.0, float("nan")],
                dof_count=2,
                controlled_joint_ids=[0],
                enabled=True,
                maximum_effort=5.2,
            )
        with self.assertRaisesRegex(GravityFeedForwardError, "width"):
            prepare_bounded_gravity_feed_forward(
                gravity_compensation_efforts=[0.0],
                dof_count=2,
                controlled_joint_ids=[0],
                enabled=True,
                maximum_effort=5.2,
            )
        with self.assertRaisesRegex(GravityFeedForwardError, "unique valid"):
            prepare_bounded_gravity_feed_forward(
                gravity_compensation_efforts=[0.0, 0.0],
                dof_count=2,
                controlled_joint_ids=[0, 0],
                enabled=True,
                maximum_effort=5.2,
            )

    def test_telemetry_gate_requires_all_apis_bounds_and_isolation(self) -> None:
        prepared = prepare_bounded_gravity_feed_forward(
            gravity_compensation_efforts=[
                0.1,
                8.0,
                -6.0,
                1.5,
                2.0,
                3.0,
            ],
            dof_count=6,
            controlled_joint_ids=[0, 1, 2, 3],
            enabled=True,
            maximum_effort=5.2,
        )
        prepared["controlled_incoming_joint_forces"] = [
            [0.0] * 6 for _ in range(4)
        ]
        result = evaluate_gravity_feed_forward_telemetry(
            samples=[prepared],
            runtime_api_availability={
                name: True for name in REQUIRED_GRAVITY_RUNTIME_APIS
            },
            controlled_joint_ids=[0, 1, 2, 3],
            feed_forward_enabled=True,
            maximum_effort=5.2,
        )
        self.assertTrue(result["telemetry_complete"])
        self.assertEqual(result["clipped_sample_count"], 1)
        self.assertEqual(
            result["maximum_absolute_applied_feed_forward_effort"],
            5.2,
        )

        unavailable = evaluate_gravity_feed_forward_telemetry(
            samples=[prepared],
            runtime_api_availability={
                name: name != "get_link_incoming_joint_force"
                for name in REQUIRED_GRAVITY_RUNTIME_APIS
            },
            controlled_joint_ids=[0, 1, 2, 3],
            feed_forward_enabled=True,
            maximum_effort=5.2,
        )
        self.assertFalse(unavailable["telemetry_complete"])
        self.assertFalse(
            unavailable["checks"][
                "gravity_compensation_runtime_apis_available"
            ]
        )

    def test_matrix_only_advances_after_machine_tracking_gate(self) -> None:
        evaluations = {
            name: _matrix_evaluation(tracking_passed=False)
            for name in GRAVITY_FEED_FORWARD_CASE_NAMES
        }
        failed = classify_calibration_matrix(self.config, evaluations)
        self.assertEqual(
            failed["decision"],
            "bounded_gravity_feed_forward_no_resolution",
        )
        self.assertFalse(failed["tracking_identity_validated"])
        self.assertFalse(failed["pregrasp_authorized"])

        evaluations["bounded_gravity_feed_forward"][
            "tracking_gate_passed"
        ] = True
        passed = classify_calibration_matrix(self.config, evaluations)
        self.assertEqual(
            passed["decision"],
            "bounded_gravity_feed_forward_resolves_tracking",
        )
        self.assertTrue(passed["tracking_identity_validated"])
        self.assertFalse(passed["pregrasp_authorized"])

        evaluations["bounded_gravity_feed_forward"]["checks"][
            "feed_forward_effort_bounded"
        ] = False
        unsafe = classify_calibration_matrix(self.config, evaluations)
        self.assertEqual(
            unsafe["decision"],
            "gravity_feed_forward_safety_contract_failed",
        )
        self.assertFalse(unsafe["tracking_identity_validated"])

    def test_gpu_free_plan_binds_audit_runner_and_blocked_gates(self) -> None:
        result = build_gravity_feed_forward_preview(
            config_path=CONFIG_PATH,
            residual_force_audit_path=AUDIT_PATH,
            runner_path=RUNNER_PATH,
        )
        self.assertTrue(result["local_preparation_passed"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(
            result["single_factor_comparison"]["changed_fields"],
            ["gravity_compensation_feed_forward"],
        )
        self.assertFalse(result["paid_gpu_run_authorized"])
        self.assertFalse(result["pregrasp_authorized"])
        self.assertFalse(result["viewer_authorized"])

    def test_accepted_machine_result_selects_exact_pregrasp_runtime(self) -> None:
        runtime = load_accepted_gravity_feed_forward_runtime(
            calibration_config_path=CONFIG_PATH,
            machine_result_path=MACHINE_RESULT_PATH,
        )
        self.assertEqual(runtime.selected_case_name, "bounded_gravity_feed_forward")
        self.assertEqual(runtime.drive_type, "force")
        self.assertEqual(runtime.stiffness, 1048.0)
        self.assertEqual(runtime.damping, 53.0)
        self.assertEqual(runtime.effort_limit_sim, 100.0)
        self.assertEqual(runtime.solver_position_iteration_count, 8)
        self.assertEqual(runtime.solver_velocity_iteration_count, 0)
        self.assertTrue(runtime.enable_external_forces_every_iteration)
        self.assertTrue(runtime.gravity_compensation_feed_forward)
        self.assertEqual(runtime.gravity_compensation_effort_limit, 5.2)
        self.assertEqual(runtime.trajectory_duration_ms, 2000)
        self.assertEqual(runtime.calibration_config_sha256, self.config_sha256)
        self.assertEqual(
            runtime.calibration_config_sha256,
            ACCEPTED_GRAVITY_FEED_FORWARD_CONFIG_SHA256,
        )
        self.assertEqual(
            runtime.machine_result_sha256,
            hashlib.sha256(MACHINE_RESULT_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            runtime.machine_result_sha256,
            ACCEPTED_GRAVITY_FEED_FORWARD_RESULT_SHA256,
        )

    def test_machine_result_tampering_fails_closed(self) -> None:
        result = json.loads(MACHINE_RESULT_PATH.read_text(encoding="utf-8"))
        mutations = (
            ("matrix", "matrix_complete", False),
            (
                "cases",
                "bounded_gravity_feed_forward",
                {
                    **result["cases"]["bounded_gravity_feed_forward"],
                    "maximum_settled_tracking_error_deg": 1.01,
                },
            ),
            (
                "shared_runtime_contract",
                "stiffness",
                10000.0,
            ),
        )
        for section, key, value in mutations:
            tampered = copy.deepcopy(result)
            tampered[section][key] = value
            with self.subTest(section=section, key=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "machine-result.json"
                path.write_text(json.dumps(tampered), encoding="utf-8")
                with self.assertRaises(GravityFeedForwardError):
                    load_accepted_gravity_feed_forward_runtime(
                        calibration_config_path=CONFIG_PATH,
                        machine_result_path=path,
                    )

    def test_runner_probes_then_applies_after_pd_write(self) -> None:
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        runtime = RUNTIME_PATH.read_text(encoding="utf-8")
        run_script = RUN_SCRIPT_PATH.read_text(encoding="utf-8")
        for value in (
            "get_gravity_compensation_forces",
            "set_dof_actuation_forces",
            "get_link_incoming_joint_force",
            "prepare_bounded_gravity_feed_forward",
            "controlled_incoming_joint_forces",
            "evaluate_gravity_feed_forward_telemetry",
        ):
            self.assertIn(value, runner + runtime)
        self.assertLess(
            runner.index("scene.write_data_to_sim()"),
            runner.index("gravity_feed_forward.apply_before_step()"),
        )
        self.assertLess(
            runner.index("gravity_feed_forward.apply_before_step()"),
            runner.index("sim.step(render=False)"),
        )
        self.assertIn(
            'matrix_profile" == "gravity_feed_forward"',
            run_script,
        )
        for case_name in GRAVITY_FEED_FORWARD_CASE_NAMES:
            self.assertIn(case_name, run_script)

    def test_runner_uses_native_warp_arrays_for_raw_physx_setter(self) -> None:
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        pregrasp_runner = PREGRASP_RUNNER_PATH.read_text(encoding="utf-8")
        runtime = RUNTIME_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "from dofbot_gravity_feed_forward_runtime import (",
            runner,
        )
        self.assertIn(
            "from dofbot_gravity_feed_forward_runtime import (",
            pregrasp_runner,
        )
        self.assertIn("import warp as wp", runtime)
        self.assertIn('getattr(self._robot, "root_view", None)', runtime)
        self.assertIn("self._indices = wp.array(", runtime)
        self.assertIn("dtype=wp.int32", runtime)
        self.assertIn("def _write_actuation_forces(", runtime)
        self.assertIn("dtype=wp.float32", runtime)
        self.assertNotIn(
            'getattr(self._robot, "root_physx_view", None)',
            runtime,
        )


if __name__ == "__main__":
    unittest.main()
