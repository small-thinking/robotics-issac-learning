# Status

- Updated: 2026-07-26 America/Los_Angeles
- Completed phase: Phase 1 — fresh manager-based PPO reproduction and
  checkpoint learning curve
- Next experiment: one paid Phase 2 override/telemetry smoke test, then the
  preregistered controlled study after review
- Brev instance: `isaac-launchable-f150a5` (`92xbacz46`)
- Instance state: `STOPPED`, verified after `brev refresh`
- Billable GPU compute still running: no
- Remaining resource: 256 GiB persistent disk, approximately `$0.04/hour`
  from the deployment quote
- Deletion status: not requested; instance and disk preserved

## Phase 1 result

- Observable remote-command wrapper: implemented and locally tested
- Dry-run previews: `make show-inspect-config`, `make show-train`,
  `make show-eval`
- Fresh training: complete, seed `42`, no resume checkpoint
- Configuration: 4096 environments, rollout 16, 2400 vector steps,
  9,830,400 transitions, learning rate `3e-4`
- Runtime: `68.43` seconds
- Checkpoint:
  `logs/skrl/cartpole/2026-07-26_16-09-30_ppo_torch/checkpoints/best_agent.pt`
- Fixed-seed result: mean reward `4.3805`, mean length `269.44`,
  `time_limit=22`, `out_of_bounds=3`
- Quantitative gate: passed
- User visual confirmation: passed; stable balancing with comparatively sparse,
  anticipatory cart corrections
- Compute price: `$1.59/hour` plus approximately `$0.04/hour` persistent
  storage

## Checkpoint learning curve

- Numbered checkpoints retained remotely: `agent_240.pt` through
  `agent_2400.pt`
- Fixed-seed sweep: complete; 25 episodes per checkpoint using the canonical
  five seeds
- Plot metrics: mean balance seconds and five-second time-limit fraction
- Random policy treatment: horizontal reference baseline, not a synthetic
  step-zero checkpoint
- Learning transition: from 0.935 seconds at 2.95M transitions to 4.491 seconds
  at 4.92M transitions
- Plateau: approximately 4.8 seconds and `24/25` time-limit episodes from
  6.88M transitions onward, with one temporary dip
- Actual sweep JSON:
  `artifacts/evaluations/phase1_learning_curve.json`
- Actual plot: `artifacts/plots/phase1_learning_curve.svg`
- Preserved training logs and configs: `artifacts/training/phase1/`
- GPU requirement now: none; the instance remains stopped

## Phase 2 preparation

- Study design: preregistered, 9 variants × 3 training seeds = 27 cells
- Existing reusable cell: `B0`, seed `42`; planned new training runs: 26
- Factors: observation, cart-velocity reward, action effort scale, and training
  out-of-bounds threshold
- Evaluation: 25 fixed parallel environment IDs under deterministic seed 101;
  final common 30-second stress profile
- Evaluator: control telemetry implemented; first-completion sampling bias
  removed
- Run provenance: allowlisted override registry, deterministic run IDs, and
  manifest schema implemented
- Reporting contract: derived tables and nine planned figure families locked
- Local validation: 14 tests, targeted Ruff, JSON parsing, shell syntax, and
  command previews passed
- Remote validation: not yet performed; Hydra overrides, joint telemetry, and
  30-second execution require one smoke run

## Phase 0 acceptance

- Hardware: AWS `g6.4xlarge`, 1x NVIDIA L4, 16 vCPU, 64 GiB RAM
- Canonical accepted task: `Isaac-Cartpole-v0` (manager-based)
- RL backend and algorithm: skrl PPO
- Policy provenance: official pretrained checkpoint, not locally trained
- Random evaluation: mean reward `-12.534867067337036`, mean length `188.44`,
  `out_of_bounds=25`
- Official checkpoint evaluation: mean reward `3.8110712456703184`, mean
  length `268.88`, `time_limit=22`, `out_of_bounds=3`
- Evaluation protocol: 25 episodes using seeds `101, 202, 303, 404, 505`
- User visual confirmation: complete; official PPO policy almost continuously
  balanced the pole
- Summary artifact:
  `artifacts/evaluations/phase0_acceptance_summary.json`

## Honest training status

- Local Direct skrl PPO, 150 iterations: did not beat random
- Resumed Direct skrl PPO, 600 more iterations: did not pass evaluation
- Direct RL-Games PPO, 150 epochs: did not establish fixed-seed convergence
- Official legacy Direct checkpoint: loaded with compatibility handling but did
  not produce the expected behavior
- Locally trained manager-based checkpoint: produced and passed the independent
  fixed-seed quantitative gates

## Persistent remote artifacts

- Official accepted checkpoint:
  `/workspace/isaaclab/.pretrained_checkpoints/skrl/Isaac-Cartpole-v0/Assets/Isaac/6.0/Isaac/IsaacLab/PretrainedCheckpoints/skrl/Isaac-Cartpole-v0/checkpoint.pt`
- Direct skrl logs/checkpoints: `/workspace/isaaclab/logs/skrl/cartpole_direct/`
- Direct RL-Games logs/checkpoints:
  `/workspace/isaaclab/logs/rl_games/cartpole_direct/`
- Phase 0 logs: `/workspace/phase0/artifacts/logs/`
- Phase 1 training log:
  `/workspace/phase1/artifacts/logs/train_cartpole_manager.log`

## Exact next action

Review the Phase 2 planning PR. After it is merged, recheck the live Brev price
and request explicit approval for a short paid smoke window. The smoke must
verify resolved config diffs, observation shape, checkpoint compatibility,
telemetry fields, fixed-environment episode collection, and artifact
persistence before the 26-run matrix starts.
