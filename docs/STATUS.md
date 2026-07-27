# Status

- Updated: 2026-07-26 America/Los_Angeles
- Completed phase: Phase 2 — 27-cell controlled RL study
- Current experiment: Phase 3 / `02_dofbot`, Goal 1 — load and inspect the
  official DOFBOT USD; Goals 2–3 are planned but not yet authorized to run
- Brev instance: `isaac-launchable-f150a5` (`92xbacz46`)
- Instance state: `STOPPED`, verified with `brev ls --json` after artifact
  download
- Billable GPU compute still running: no
- Remaining resource: 256 GiB persistent disk, approximately `$0.04/hour`
  from the deployment quote
- Deletion status: not requested; instance and disk preserved
- Latest live L4 quote: existing AWS `g6.4xlarge` class is `$1.58784/hour`
  compute; checked 2026-07-26 before any restart

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

## Phase 2 result

- Study matrix: complete, 9 variants × 3 training seeds = 27 succeeded cells
- Failed/partial formal runs: none
- Factors: observation, cart-velocity reward, action effort scale, and training
  out-of-bounds threshold
- Evaluation: 25 fixed parallel environment IDs under deterministic seed 101;
  final common 30-second stress profile
- Final episode rows: 675; screening checkpoint evaluations: 90
- Baseline robust 30-second success: `100% ± 0%`
- Position-only robust success: `1.3% ± 2.3%`
- Four-frame history robust success: `66.7% ± 57.7%`; two seeds succeeded and
  one failed
- Reward variants: `100%` mean robust success at all three levels, with
  control-style differences
- Wide-boundary result: `65.3% ± 56.6%`, driven by one catastrophic seed
- Local evidence: 27 manifests, screening/final JSON, 7 CSV datasets, 5 SVG
  figures, and a paper-style report under `artifacts/phase2/`
- Local archive checksums:
  - data: `932d4b3dfae43e58ffc44f9c57f19e112f085744acd373a333660538aec73c59`
  - 27 checkpoints:
    `de37fa34962c20fa421917e9adb9e7a99af407bea91fb41a0d733c71949362b5`
- Validation: 18 unit tests, targeted Ruff, 27/27 manifest status, 9/9
  screening files, 9/9 final files, per-file episode counts, matching local and
  remote archive checksums, and browser-rendered SVG QA passed

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

Run the locally validated, policy-free Goal 1 inspector against the retained
Isaac environment, save `artifacts/dofbot/asset_contract.json`, and confirm the
stationary robot in the secure Viewer. Stop the GPU immediately after visual
confirmation. Do not execute hard-coded motion (Goal 2) or camera capture
(Goal 3) during this paid window.
