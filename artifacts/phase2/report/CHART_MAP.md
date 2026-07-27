# Phase 2 Chart Map

| Figure | Analytical question | Form and fields | Supported reading |
| --- | --- | --- | --- |
| `learning_dynamics.svg` | How did seed-42 checkpoint quality change with training? | 3×3 small-multiple line; x=`training_transitions`, y=`mean_upright_fraction_12deg` | Learning is non-monotonic; position-only degrades after an early peak, while history improves |
| `final_performance.svg` | Which final variants are reliable across training seeds? | Three dot-and-interval panels; category=`variant_id`, individual dots=`training_seed`, mean ± sample SD | Observation and wide-boundary variants expose seed-level failures |
| `factor_sensitivity.svg` | How do numeric factor levels change upright outcomes? | Three one-factor lines; y=`robust_success_fraction` and `mean_upright_fraction_12deg` | Reward/action remain near ceiling; wide termination bound is brittle |
| `control_sensitivity.svg` | How do the same factors change movement and effort? | Three one-factor dot-line panels; reward→cart velocity, action→requested effort, termination→cart RMS | Similar survival can hide different control styles |
| `effort_error_tradeoff.svg` | Do failed policies occupy a different control regime? | Log-log scatter; x=`mean_abs_requested_effort`, y=`mean_pole_angle_rms_radians`, color=`factor` | Failed observation/wide-boundary policies combine high effort and high error |

Palette policy is one stable factor color plus neutral axes. Shape, faceting,
and direct labels preserve meaning without relying only on color. All figures
are generated from tracked CSV files by `tools/build_phase2_artifacts.py`.

The preregistered representative-trace figure is omitted because the formal run
did not collect full per-step traces. No trace is reconstructed from aggregate
episode metrics.
