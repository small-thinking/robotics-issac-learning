# Phase 2 Chart Map

| Figure | Analytical question | Form and fields | Supported reading |
| --- | --- | --- | --- |
| `learning_dynamics.svg` | How did seed-42 checkpoint quality change with training? | 3×3 small-multiple line; x=`training_transitions`, y=`mean_upright_fraction_12deg` | Learning is non-monotonic; position-only degrades after an early peak, while history improves |
| `observation_ablation.svg` | How does state information affect reliability? | Categorical x=`observation design`; y=`robust_success_fraction` and `mean_upright_fraction_12deg`; seed points + mean | Direct velocity is reliable; position-only fails; history is seed-sensitive |
| `reward_ablation.svg` | How does cart-velocity reward weight affect the result? | x=`cart_velocity_reward_weight`; y=`robust_success_fraction` and `mean_abs_cart_velocity`; seed points + mean | Survival stays at ceiling while motion style changes |
| `action_ablation.svg` | How does effort scale affect the result? | x=`effort_scale`; y=`robust_success_fraction` and `mean_abs_requested_effort`; seed points + mean | PPO compensates for authority; scale 200 uses the least mean requested effort |
| `termination_ablation.svg` | How does the training boundary affect reliability? | x=`training_cart_position_bound`; y=`robust_success_fraction` and `mean_upright_fraction_12deg`; seed points + mean | The wide boundary creates a catastrophic seed-level failure |
| `effort_error_tradeoff.svg` | Do failed policies occupy a different control regime? | Log-log scatter; x=`mean_abs_requested_effort`, y=`mean_pole_angle_rms_radians`, color=`factor` | Failed observation/wide-boundary policies combine high effort and high error |

Palette policy is one stable factor color plus neutral axes. Shape, faceting,
and direct labels preserve meaning without relying only on color. All figures
are generated from tracked CSV files by `tools/build_phase2_artifacts.py`.

The preregistered representative-trace figure is omitted because the formal run
did not collect full per-step traces. No trace is reconstructed from aggregate
episode metrics.
