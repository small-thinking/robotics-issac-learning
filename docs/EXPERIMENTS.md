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

## 2026-07-26 — Fresh manager-based skrl PPO passed Phase 1

- Git commit: `c0ae102` at remote sync
- Environment: Isaac Launchable `3.0.0-beta2-post1`, 1x L4
- Task: `Isaac-Cartpole-v0` (manager-based)
- Model: skrl PPO using the installed official task config
- Provenance: trained locally from scratch; no resume or pretrained checkpoint
- Training configuration: seed `42`, 4096 environments, rollout length `16`,
  2400 vector steps, 9,830,400 transitions, learning rate `3e-4`
- Runtime: `68.43` seconds
- Run:
  `logs/skrl/cartpole/2026-07-26_16-09-30_ppo_torch`
- Evaluated checkpoint:
  `logs/skrl/cartpole/2026-07-26_16-09-30_ppo_torch/checkpoints/best_agent.pt`
- Evaluation protocol: 25 episodes; seeds `101, 202, 303, 404, 505`; five
  episodes per seed
- Mean reward: `4.380518758296967`
- Reward standard deviation: `1.4007005185494263`
- Mean episode length: `269.44`
- Length standard deviation: `82.78844363798609`
- Termination reasons: `time_limit=22`, `out_of_bounds=3`
- Comparison: the official checkpoint produced mean reward `3.8111`, mean
  length `268.88`, and the same `22/25` time-limit count
- Visual result: the user confirmed stable balancing and observed fewer, more
  anticipatory cart movements that kept the pole close to vertical
- Summary artifact:
  `artifacts/evaluations/phase1_reproduction_summary.json`
- Conclusion: the local-from-scratch checkpoint passed every quantitative and
  visual Phase 1 gate

## 2026-07-26 — Manager-based PPO checkpoint learning curve

- Git source at remote sync: `b9e7589`
- Environment: Isaac Launchable `3.0.0-beta2-post1`, 1x L4
- Task: `Isaac-Cartpole-v0` (manager-based)
- Training run:
  `logs/skrl/cartpole/2026-07-26_16-09-30_ppo_torch`
- Checkpoints: `agent_240.pt` through `agent_2400.pt`
- Evaluation protocol: 25 episodes per checkpoint; seeds
  `101, 202, 303, 404, 505`; five episodes per seed; 64 parallel evaluation
  environments; 60 Hz control; five-second episode limit
- Random reference: 3.125 mean balance seconds, `0/25` time-limit episodes
- 0.98M transitions: 0.234 seconds, `0/25`
- 1.97M transitions: 0.253 seconds, `0/25`
- 2.95M transitions: 0.935 seconds, `0/25`
- 3.93M transitions: 3.861 seconds, `18/25`
- 4.92M transitions: 4.491 seconds, `22/25`
- 5.90M transitions: 4.487 seconds, `22/25`
- 6.88M transitions: 4.824 seconds, `24/25`
- 7.86M transitions: 4.500 seconds, `22/25`
- 8.85M transitions: 4.825 seconds, `24/25`
- 9.83M transitions: 4.823 seconds, `24/25`
- Machine-readable artifact:
  `artifacts/evaluations/phase1_learning_curve.json`
- Plot: `artifacts/plots/phase1_learning_curve.svg`
- Training evidence: `artifacts/training/phase1/`
- Conclusion: learning was initially worse than random, transitioned sharply
  around 3-5M transitions, and plateaued near 4.8 seconds after about 6.9M.
  The temporary 7.86M dip demonstrates non-monotonic checkpoint quality.

## 2026-07-26 — Phase 2 controlled CartPole study

- Git source at formal remote sync:
  `a2ddcc55747b6b0e1a46451369a371734315ebff`
- Environment: Isaac Launchable `3.0.0-beta2-post1`, 1x NVIDIA L4
- Task: `Isaac-Cartpole-v0` (manager-based)
- Algorithm: official Isaac Lab skrl PPO entry point
- Matrix: 9 variants × training seeds `42`, `7`, `123`
- Training per policy: 4096 environments, 2400 vector steps, 9,830,400
  transitions
- Formal training cells: 27 succeeded, 0 failed
- Screening: 10 numbered checkpoints × 9 seed-42 variants × 25 fixed
  five-second episodes
- Final evaluation: 3 trained policies × 9 variants × 25 fixed 30-second
  episodes
- Final episode rows: 675
- Evaluation seed/environment contract: seed `101`, environment IDs `0..24`
- Baseline robust success: `100% ± 0%`
- Position-only robust success: `1.3% ± 2.3%`
- Four-frame history robust success: `66.7% ± 57.7%`
- Reward levels `0`, `-0.01`, `-0.02`: all `100%` mean robust success; stronger
  penalty reduced mean absolute cart velocity
- Action scales `50`, `100`, `200`: `97.3%`, `100%`, `100%` mean robust
  success
- Training bounds `1.5`, `3`, `6`: `98.7%`, `100%`, `65.3%` mean robust
  success
- Main interpretation: observation information dominated reliability; reward
  and action mostly changed control style; the wide boundary created
  seed-sensitive failure
- Data archive SHA-256:
  `932d4b3dfae43e58ffc44f9c57f19e112f085744acd373a333660538aec73c59`
- Checkpoint archive SHA-256:
  `de37fa34962c20fa421917e9adb9e7a99af407bea91fb41a0d733c71949362b5`
- Tracked evidence: `artifacts/phase2/`
- Report: `artifacts/phase2/report/README.md`
- Compute lifecycle: downloaded and validated locally, then instance
  `isaac-launchable-f150a5` confirmed `STOPPED`; persistent disk retained
- Conclusion: CartPole controlled-study workflow is complete; advance to a
  state-based Franka reach task rather than extending the parameter sweep
