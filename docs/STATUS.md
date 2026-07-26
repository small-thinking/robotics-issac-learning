# Status

- Updated: 2026-07-26 America/Los_Angeles
- Completed phase: Phase 0 — visible random-to-pretrained CartPole loop
- Next phase: Phase 1 — reproduce manager-based skrl PPO from scratch
- Brev instance: `isaac-launchable-f150a5` (`92xbacz46`)
- Instance state: `STOPPED`, verified after `brev refresh`
- Billable GPU compute still running: no
- Remaining resource: 256 GiB persistent disk, approximately `$0.04/hour`
  from the deployment quote
- Deletion status: not requested; instance and disk preserved

## Phase 1 preparation

- Observable remote-command wrapper: implemented and locally tested
- Dry-run previews: `make show-inspect-config`, `make show-train`,
  `make show-eval`
- Reproduction contract:
  `docs/PHASE1_PPO_REPRODUCTION.md`
- Official source comparison: manager-based config uses rollout 16,
  2400 vector steps, learning rate `3e-4`, no state/value scaler, and reward
  scale `1.0`
- Existing stopped hardware live price checked 2026-07-26:
  `$1.59/hour` compute plus approximately `$0.04/hour` persistent storage
- Proposed paid window: at most 30 minutes, approximately `$0.80` compute
  (`$0.82` including a half hour of storage)
- Restart approval for this new paid window: pending

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
- Locally trained manager-based checkpoint: not yet produced

## Persistent remote artifacts

- Official accepted checkpoint:
  `/workspace/isaaclab/.pretrained_checkpoints/skrl/Isaac-Cartpole-v0/Assets/Isaac/6.0/Isaac/IsaacLab/PretrainedCheckpoints/skrl/Isaac-Cartpole-v0/checkpoint.pt`
- Direct skrl logs/checkpoints: `/workspace/isaaclab/logs/skrl/cartpole_direct/`
- Direct RL-Games logs/checkpoints:
  `/workspace/isaaclab/logs/rl_games/cartpole_direct/`
- Phase 0 logs: `/workspace/phase0/artifacts/logs/`

## Exact next action

Obtain explicit approval to restart the stopped L4 instance, inspect the exact
installed manager-based skrl config, then run the locked reproduction in
`docs/PHASE1_PPO_REPRODUCTION.md`. Do not restart or create billable compute
without that approval.
