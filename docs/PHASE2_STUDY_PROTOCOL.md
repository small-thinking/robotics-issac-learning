# Phase 2 Preregistered CartPole Control Study

## Research question

When PPO can already solve the simple CartPole task, how do controlled changes
to observation, reward, action authority, and training termination change:

1. whether the policy remains upright for 30 seconds; and
2. how the policy moves while doing so?

This is a reproduction and sensitivity study, not a claim of a novel RL
algorithm. The contribution is a clean experimental contract, complete run
provenance, and a paper-style analysis of control trade-offs.

The machine-readable source of truth is
[`experiments/01_cartpole_ppo/variants.json`](../experiments/01_cartpole_ppo/variants.json).
Changing the matrix after seeing results requires a dated protocol amendment.

## Experimental matrix

Every row changes one factor relative to the official manager-based
`Isaac-Cartpole-v0` PPO configuration.

| ID | Factor | Level | Primary contrast | Hypothesis |
| --- | --- | --- | --- | --- |
| `B0` | baseline | official config | — | Reference for all one-factor comparisons |
| `O_POS` | observation | position only | `B0` | Removing velocity makes control partially observable |
| `O_H4` | observation | 4 position frames | `O_POS` | History recovers some velocity information |
| `R_CV0` | reward | cart-velocity weight `0` | `B0` | More cart motion without a necessary survival gain |
| `R_CV2` | reward | cart-velocity weight `-0.02` | `B0` | Less motion, possibly slower recovery |
| `A_E50` | action | effort scale `50` | `B0` | Less authority causes slower recovery |
| `A_E200` | action | effort scale `200` | `B0` | More authority causes overshoot/boundary failures |
| `T_B15` | termination | train bounds `[-1.5, 1.5]` | `B0` | A narrow boundary encourages centered control |
| `T_B60` | termination | train bounds `[-6, 6]` | `B0` | A wide boundary permits more drift |

The observation comparison is categorical. `O_H4` must be compared with
`O_POS`, because both omit instantaneous velocity. Reward, effort scale, and
training boundary are three-point sensitivity plots using their real numeric
values; no smooth fitted curve is implied by three levels.

## Two-wave execution

### Wave 1: screening and learning dynamics

- Training seed: `42`.
- Reuse the existing `B0` seed-42 run after re-evaluating it with the corrected
  fixed-environment sampler.
- Train the remaining eight variants.
- Evaluate all ten numbered checkpoints under the canonical five-second
  profile.
- Evaluate `agent_2400.pt` under the 30-second stress profile.
- Stop and diagnose only a crash, NaN, unapplied override, incompatible policy
  interface, or missing artifact. Poor performance is a valid result.

### Wave 2: seed confirmation

- Training seeds: `7` and `123`.
- Train all nine variants.
- Evaluate the preregistered final checkpoint `agent_2400.pt` under the
  30-second stress profile.
- Do not replace it with `best_agent.pt` after viewing results.

The final design contains 27 trained-policy cells: 9 variants × 3 training
seeds. One existing cell is reusable, leaving 26 new training runs. At the
Phase 1 observed training speed of 68.43 seconds per run, pure training is
approximately 29.7 minutes; startup, evaluation, artifact transfer, and one
smoke test are additional. A live price check and explicit paid-window
approval are still required before starting Brev.

## Locked training and evaluation contract

- Task: manager-based `Isaac-Cartpole-v0`.
- PPO implementation: Isaac Lab's official skrl training entry point.
- Training environments: `4096`.
- Training horizon: five seconds.
- Training seeds: `42`, `7`, `123`.
- Final checkpoint: numbered vector step `2400`.
- Evaluation seeds: `101`, `202`, `303`, `404`, `505`.
- Episodes: five per evaluation seed.
- Statistical unit: one trained policy, identified by its training seed.
- Screening: canonical five-second evaluation at each numbered checkpoint.
- Final comparison: common 30-second stress evaluation.
- Upright: wrapped pole angle within `12°`.
- Robust success: at least 95% of steps upright and no out-of-bounds
  termination.
- Action sign deadband: `0.05`.

Evaluation preselects environment IDs `0..4` and records exactly the first
episode from each. It must not take the first five environments that happen to
finish, because that selects early failures in long stress tests.

Interface changes (observation and action) apply during both training and
evaluation. Objective changes (reward and training boundary) apply only during
training. Every final policy is evaluated under the canonical `[-3, 3]`
boundary and common 30-second horizon so the termination study measures what
the learned policy can do, not merely the rule under which it trained.

## Measurements

### Primary outcomes

- robust 30-second success;
- upright fraction within `12°`;
- longest continuous upright interval in seconds;
- wrapped pole-angle RMS;
- out-of-bounds fraction.

### Control-style outcomes

- cart-position RMS and maximum absolute displacement;
- mean absolute cart velocity;
- pole angular-velocity RMS;
- mean absolute normalized action;
- mean absolute requested effort (`normalized action × effort scale`);
- mean absolute action delta and action total variation;
- action sign changes per second using the locked deadband;
- action saturation fraction.

Raw reward is retained for debugging but is not compared across reward
variants, because those variants change its definition.

## Data contract

Each attempted training run gets an immutable `run_id`:

```text
phase2_cartpole_controlled_ablation__<variant_id>__seed<training_seed>
```

A rerun gets a new suffixed ID and never overwrites the previous attempt.
Before a command starts, its `manifest.json` is written with status `planned`;
it progresses through `running` to `succeeded`, `partial`, or `failed`.
The exact pre-run record can be previewed with:

```bash
VARIANT=A_E50 TRAINING_SEED=7 make show-manifest
```

The manifest records:

- study, run, variant, factor, level, training seed, and evaluation profile;
- Git commit and dirty flag;
- Isaac Sim, Isaac Lab, skrl, task, GPU, and image identity;
- exact command, start/end timestamps, wall time, exit code;
- resolved environment and agent config hashes;
- registry hash and variant/interface contract hash;
- expected baseline value and exact override;
- checkpoint paths and SHA-256 checksums;
- paths/checksums for console log, TensorBoard events, raw telemetry, and
  derived tables;
- failure stage, message, and last completed training step.

Per-episode JSONL records identity, outcome, termination, upright metrics,
motion metrics, and control metrics. Optional compressed per-step JSONL records
simulation time, state, policy observation, normalized action, requested
effort, reward terms, termination flags, and any disturbance.

Large checkpoints and full step traces remain on persistent storage or in a
downloaded archive. Git retains their checksums and locations, all manifests,
full episode rows, derived tables, representative traces, and every plotted
value. Missing and failed runs remain explicit in the run registry.

Derived datasets:

- `run_registry.csv`: every planned/reused/succeeded/failed run;
- `episode_metrics.csv`: one row per fixed environment episode;
- `training_curves.csv`: checkpoint-level evaluation;
- `run_metrics.csv`: one row per trained policy;
- `paired_effects.csv`: within-training-seed contrasts;
- `condition_summary.csv`: mean, SD, and sample count across training seeds;
- `trace_selection.csv`: rule and identity for representative traces.

## Figure and table plan

1. **Learning dynamics:** transitions vs upright fraction for all nine seed-42
   variants.
2. **Observation:** individual-seed dots and mean ± SD for `B0`, `O_POS`,
   `O_H4`.
3. **Reward sensitivity:** weight `0`, `-0.01`, `-0.02` vs upright quality,
   cart velocity, and action change.
4. **Action sensitivity:** scale `50`, `100`, `200` vs upright quality,
   requested effort, and action variation.
5. **Termination sensitivity:** training bound `1.5`, `3`, `6` vs common-stress
   success and cart drift.
6. **Representative traces:** aligned pole angle, cart position, normalized
   action, and requested effort.
7. **Trade-off scatter:** control effort vs upright quality, one point per
   trained policy.
8. **Effect heatmap:** baseline-normalized, training-seed-paired effects.
9. **Failure composition:** 100% stacked termination outcomes.
10. **Exact result table:** all primary/control metrics and per-seed deltas.

Fraction axes are fixed to `[0, 1]`; absolute bars start at zero; comparable
panels share scales; no dual axes are used. Individual seed points remain
visible because `n=3` is too small to hide behind only a mean. Results are
reported as mean ± sample SD and paired deltas, without overstated statistical
significance.

## Paper-style report structure

The final report will contain: technical summary, task and metric definitions,
preregistered hypotheses, methods, factor-by-factor results, trade-offs and
traces, negative/failed runs, limitations, reproducibility, and an exit
decision for the next robotics task.

The main limitation is deliberate: CartPole is a ceiling-prone educational
system. This study is valuable for learning controlled RL experimentation, but
its conclusions must not be generalized to contact-rich or high-dimensional
robotics.

## Quality and cost gates

Before paid compute:

1. validate the registry and 27-cell run matrix locally;
2. unit-test allowlisted overrides and train/evaluation scoping;
3. verify fixed-environment episode sampling;
4. run one remote smoke variant and inspect the resolved config diff,
   observation shape, checkpoint compatibility, and 30-second step count;
5. verify manifest/log/telemetry persistence on a forced short run;
6. recheck current GPU and disk price;
7. obtain explicit approval for the paid window.

After the run, download and validate artifacts before stopping compute. Stop
the GPU immediately after validation; retain or delete persistent storage only
under the separately approved lifecycle decision.
