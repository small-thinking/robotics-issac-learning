from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from tools.build_phase2_artifacts import (
    render_action_ablation,
    render_learning_dynamics,
    render_observation_ablation,
    render_reward_ablation,
    render_termination_ablation,
    render_tradeoff,
)


def _run_row(variant_id: str, factor: str, offset: float) -> dict[str, object]:
    return {
        "variant_id": variant_id,
        "factor": factor,
        "training_seed": int(offset * 100),
        "robust_success_fraction": 0.8 + offset,
        "mean_upright_fraction_12deg": 0.9 + offset / 2,
        "mean_pole_angle_rms_radians": 0.08 - offset / 4,
        "mean_abs_requested_effort": 1.0 + offset,
        "mean_abs_cart_velocity": 0.2 + offset,
        "mean_cart_position_rms": 0.5 + offset,
    }


class Phase2SvgTest(unittest.TestCase):
    def setUp(self) -> None:
        variants = [
            ("B0", "baseline"),
            ("O_POS", "observation"),
            ("O_H4", "observation"),
            ("R_CV0", "reward"),
            ("R_CV2", "reward"),
            ("A_E50", "action"),
            ("A_E200", "action"),
            ("T_B15", "termination"),
            ("T_B60", "termination"),
        ]
        self.run_rows = [
            _run_row(variant_id, factor, seed_offset)
            for variant_id, factor in variants
            for seed_offset in (0.0, 0.02, 0.04)
        ]
        self.curve_rows = [
            {
                "variant_id": variant_id,
                "training_transitions": step * 4096,
                "mean_upright_fraction_12deg": 0.1 * step / 240,
            }
            for variant_id, _ in variants
            for step in range(240, 2401, 240)
        ]

    def test_all_phase2_figures_are_valid_svg(self) -> None:
        figures = [
            render_learning_dynamics(self.curve_rows),
            render_observation_ablation(self.run_rows),
            render_reward_ablation(self.run_rows),
            render_action_ablation(self.run_rows),
            render_termination_ablation(self.run_rows),
            render_tradeoff(self.run_rows),
        ]
        for figure in figures:
            self.assertEqual(
                ET.fromstring(figure).tag,
                "{http://www.w3.org/2000/svg}svg",
            )

    def test_factor_figures_expose_one_variable_and_seed_contract(self) -> None:
        figures = {
            "Observation supplied to policy": render_observation_ablation(self.run_rows),
            "Cart-velocity reward weight": render_reward_ablation(self.run_rows),
            "Maximum requested effort scale": render_action_ablation(self.run_rows),
            "Training cart-position bound": render_termination_ablation(self.run_rows),
        }
        for x_label, svg in figures.items():
            self.assertIn(x_label, svg)
            self.assertIn("30-second robust success", svg)
            self.assertIn("individual PPO seed", svg)
            self.assertIn("mean of 3 seeds", svg)


if __name__ == "__main__":
    unittest.main()
