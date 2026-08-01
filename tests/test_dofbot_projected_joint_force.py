from __future__ import annotations

import math
import unittest

from tools.dofbot_projected_joint_force import (
    PROJECTED_JOINT_FORCE_SEMANTICS,
    summarize_projected_joint_force_telemetry,
)


class ProjectedJointForceTelemetryTest(unittest.TestCase):
    def test_complete_samples_produce_extrema_and_differences(self) -> None:
        result = summarize_projected_joint_force_telemetry(
            observations=[
                {
                    "step_index": 0,
                    "physx_projected_joint_forces": [1.0, -2.0],
                    "computed_torque": [0.75, -1.5],
                    "applied_torque": [0.5, -1.0],
                },
                {
                    "step_index": 1,
                    "physx_projected_joint_forces": [-3.0, 4.0],
                    "computed_torque": [-2.0, 3.0],
                    "applied_torque": [-1.5, 2.0],
                },
            ],
            controlled_joint_names=["joint1", "joint2"],
        )

        self.assertEqual(
            result["checks"],
            {
                "physx_projected_joint_force_telemetry_available_for_every_observation": True,
                "implicit_actuator_pd_estimate_telemetry_available_for_every_observation": True,
                "projected_force_and_pd_estimates_are_sample_aligned": True,
            },
        )
        self.assertEqual(
            result["maximum_absolute_physx_projected_joint_forces"],
            [3.0, 4.0],
        )
        self.assertEqual(
            result["maximum_absolute_projected_minus_computed"],
            [1.0, 1.0],
        )
        self.assertEqual(
            result["maximum_absolute_projected_minus_applied"],
            [1.5, 2.0],
        )
        self.assertEqual(
            result["final_physx_projected_joint_forces"], [-3.0, 4.0]
        )
        self.assertIn(
            "not an isolated drive-torque sensor",
            PROJECTED_JOINT_FORCE_SEMANTICS,
        )

    def test_missing_nonfinite_or_wrong_width_fails_telemetry_gate(self) -> None:
        result = summarize_projected_joint_force_telemetry(
            observations=[
                {
                    "step_index": 0,
                    "physx_projected_joint_forces": None,
                    "computed_torque": [1.0, 2.0],
                    "applied_torque": [1.0, 2.0],
                },
                {
                    "step_index": 1,
                    "physx_projected_joint_forces": [1.0, math.nan],
                    "computed_torque": [1.0],
                    "applied_torque": [True, 2.0],
                },
            ],
            controlled_joint_names=["joint1", "joint2"],
        )

        self.assertFalse(
            result["checks"][
                "physx_projected_joint_force_telemetry_available_for_every_observation"
            ]
        )
        self.assertFalse(
            result["checks"][
                "implicit_actuator_pd_estimate_telemetry_available_for_every_observation"
            ]
        )
        self.assertIsNone(result["final_physx_projected_joint_forces"])
        self.assertEqual(len(result["telemetry_issues"]), 2)

    def test_contract_rejects_invalid_names_or_empty_observations(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            summarize_projected_joint_force_telemetry(
                observations=[{}], controlled_joint_names=[]
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            summarize_projected_joint_force_telemetry(
                observations=[{}],
                controlled_joint_names=["joint1", "joint1"],
            )
        with self.assertRaisesRegex(ValueError, "non-empty list"):
            summarize_projected_joint_force_telemetry(
                observations=[], controlled_joint_names=["joint1"]
            )


if __name__ == "__main__":
    unittest.main()
