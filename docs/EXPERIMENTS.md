# Experiments

## 2026-07-25 — Random visual smoke

- Git commit: `977c9af`
- Environment: Isaac Launchable `3.0.0-beta2-post1`, 1x L4
- Task: `Isaac-Cartpole-Direct-v0`
- Policy: uniform random actions
- Configuration: one rendered environment, secure Viewer
- Seed: `42`
- Command: official `scripts/environments/random_agent.py` through
  `make smoke`
- Checkpoint: none
- Fixed-seed metrics: mean reward `-6.7537`, mean episode length `23.0`
- Visual result: the user confirmed that the pole repeatedly fell/reset,
  commonly within roughly three seconds
- Conclusion: simulator, secure streaming, and random baseline were working

## 2026-07-25 — Short Direct skrl PPO did not converge

- Git commit: `977c9af`
- Task: `Isaac-Cartpole-Direct-v0`
- Model: skrl PPO, installed official task config
- Configuration: 4096 environments, rollout length 32, 150 iterations,
  19,660,800 transitions
- Seed: `42`
- Command: `make train` with the Direct task
- Runtime: `97.01` seconds
- Checkpoints:
  - `logs/skrl/cartpole_direct/2026-07-26_05-35-30_ppo_torch/checkpoints/best_agent.pt`
  - `logs/skrl/cartpole_direct/2026-07-26_05-35-30_ppo_torch/checkpoints/agent_4800.pt`
- Best fixed-seed result: mean reward `-6.8404`, mean episode length `22.72`
- Conclusion: did not beat the Direct random baseline; transition count alone
  was not evidence of convergence

## 2026-07-25 — Continued Direct skrl PPO did not converge

- Git commit: `5948898`
- Task: `Isaac-Cartpole-Direct-v0`
- Model: skrl PPO resumed from `agent_4800.pt`
- Configuration: 4096 environments, 600 additional iterations,
  78,643,200 additional transitions
- Seed: `42`
- Runtime: `383.66` seconds
- Final checkpoint:
  `logs/skrl/cartpole_direct/2026-07-26_05-46-25_ppo_torch/checkpoints/agent_19200.pt`
- Fixed-seed result: mean reward `-5.8618`, mean episode length `22.44`
- Training log trend: reported mean episode length increased from about `34.46`
  to `37.86`, but the independent evaluator did not confirm improvement
- Conclusion: longer optimization still failed the acceptance test; do not keep
  scaling this mismatched baseline without inspecting the resolved config

## 2026-07-25 — Direct RL-Games comparison did not establish convergence

- Git commit: `5948898`
- Task: `Isaac-Cartpole-Direct-v0`
- Model: RL-Games PPO
- Configuration: 4096 environments, 150 epochs
- Seed: `42`
- Runtime: `102.63` seconds
- Best checkpoint:
  `logs/rl_games/cartpole_direct/2026-07-26_05-55-09/nn/cartpole_direct.pth`
- Training statistic: final reward about `8.76`, best reported about `12.84`
- Conclusion: training-log rewards were not validated under the canonical
  fixed-seed evaluator and did not justify a convergence claim

## 2026-07-25 — Legacy Direct checkpoint compatibility was insufficient

- Git commit: `36bccd8`
- Task: `Isaac-Cartpole-Direct-v0`
- Model: official pretrained skrl PPO checkpoint for the Direct task
- Compatibility issue: checkpoint stored `state_preprocessor`; installed skrl
  `2.1.0` expected `observation_preprocessor`
- Result after compatibility loading: mean episode length `22.76`
- Conclusion: making a checkpoint deserialize does not prove semantic or
  behavioral compatibility across versions

## 2026-07-25 — Official manager-based PPO passed Phase 0

- Git commit: `5948898`
- Task: `Isaac-Cartpole-v0` (manager-based)
- Model: official pretrained skrl PPO
- Configuration: 25 episodes; seeds `101, 202, 303, 404, 505`; five episodes
  per seed; same evaluator for random and trained policies
- Checkpoint:
  `/workspace/isaaclab/.pretrained_checkpoints/skrl/Isaac-Cartpole-v0/Assets/Isaac/6.0/Isaac/IsaacLab/PretrainedCheckpoints/skrl/Isaac-Cartpole-v0/checkpoint.pt`
- Random:
  - mean reward `-12.534867067337036`
  - reward standard deviation `5.660519020312892`
  - mean episode length `188.44`
  - length standard deviation `49.97925969839889`
  - termination reasons: `out_of_bounds=25`
- Official pretrained PPO:
  - mean reward `3.8110712456703184`
  - reward standard deviation `1.251255186768159`
  - mean episode length `268.88`
  - length standard deviation `84.3124285025642`
  - termination reasons: `out_of_bounds=3`, `time_limit=22`
- Visual result: the user confirmed the pole was almost continuously balanced
- Summary artifact: `artifacts/evaluations/phase0_acceptance_summary.json`
- Conclusion: Phase 0 plumbing and behavior acceptance passed; PPO-from-scratch
  reproduction remains Phase 1
