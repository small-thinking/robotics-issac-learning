from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from tools.cartpole_metrics import (
    checkpoint_vector_steps,
    fixed_episode_env_ids,
    summarize_episodes,
)
from tools.render_learning_curve import render_svg


class CartpoleMetricsTest(unittest.TestCase):
    def test_fixed_episode_sample_uses_preselected_environment_ids(self) -> None:
        self.assertEqual(fixed_episode_env_ids(64, 5), (0, 1, 2, 3, 4))
        with self.assertRaisesRegex(ValueError, "at least"):
            fixed_episode_env_ids(4, 5)

    def test_checkpoint_vector_steps(self) -> None:
        self.assertEqual(checkpoint_vector_steps("agent_240.pt"), 240)
        self.assertEqual(checkpoint_vector_steps("agent_2400.pt"), 2400)
        self.assertIsNone(checkpoint_vector_steps("best_agent.pt"))

    def test_summary_converts_steps_to_seconds_and_transitions(self) -> None:
        episodes = [
            {"reward": 2.0, "length": 300, "termination_reason": "time_limit"},
            {"reward": -1.0, "length": 120, "termination_reason": "out_of_bounds"},
        ]
        result = summarize_episodes(
            policy="trained",
            task="Isaac-Cartpole-v0",
            checkpoint="agent_240.pt",
            seeds=[101],
            episodes=episodes,
            control_hz=60.0,
            training_num_envs=4096,
        )

        self.assertAlmostEqual(result["mean_balance_seconds"], 3.5)
        self.assertEqual(result["time_limit_episode_count"], 1)
        self.assertAlmostEqual(result["time_limit_fraction"], 0.5)
        self.assertEqual(result["checkpoint_vector_steps"], 240)
        self.assertEqual(result["training_transitions"], 983_040)

    def test_summary_aggregates_control_metrics_when_present(self) -> None:
        episodes = [
            {
                "reward": 1.0,
                "length": 300,
                "termination_reason": "time_limit",
                "upright_fraction_12deg": 0.98,
                "mean_abs_normalized_action": 0.2,
                "robust_success": True,
            },
            {
                "reward": 1.0,
                "length": 300,
                "termination_reason": "time_limit",
                "upright_fraction_12deg": 0.92,
                "mean_abs_normalized_action": 0.4,
                "robust_success": False,
            },
        ]
        result = summarize_episodes(
            policy="trained",
            task="Isaac-Cartpole-v0",
            checkpoint=None,
            seeds=[101],
            episodes=episodes,
            control_hz=60.0,
        )

        self.assertAlmostEqual(result["mean_upright_fraction_12deg"], 0.95)
        self.assertAlmostEqual(result["mean_abs_normalized_action"], 0.3)
        self.assertAlmostEqual(result["robust_success_fraction"], 0.5)


class LearningCurveSvgTest(unittest.TestCase):
    def test_render_svg_contains_both_control_metrics(self) -> None:
        payload = {
            "episode_limit_seconds": 5.0,
            "random_baseline": {"mean_balance_seconds": 2.0},
            "evaluations": [
                {
                    "training_transitions": 983_040,
                    "mean_balance_seconds": 2.5,
                    "time_limit_fraction": 0.2,
                },
                {
                    "training_transitions": 9_830_400,
                    "mean_balance_seconds": 4.5,
                    "time_limit_fraction": 0.88,
                },
            ],
        }

        svg = render_svg(payload)

        self.assertIn("Mean balance time (s)", svg)
        self.assertIn("Reached time limit", svg)
        self.assertIn("Training transitions (millions)", svg)
        self.assertIn("random baseline 2.00s", svg)
        self.assertEqual(ET.fromstring(svg).tag, "{http://www.w3.org/2000/svg}svg")

    def test_render_svg_rejects_empty_curve(self) -> None:
        with self.assertRaisesRegex(ValueError, "contains no evaluations"):
            render_svg({"evaluations": []})


if __name__ == "__main__":
    unittest.main()
