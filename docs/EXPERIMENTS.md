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

## 2026-07-26 — DOFBOT Goal 1 passed machine and visual gates

- Git source at remote sync: `f9a44ee`
- Environment: Isaac Launchable `3.0.0-beta2-post1`, Isaac Sim `6.0.1`,
  AWS `g6.4xlarge`, 1x NVIDIA L4
- Live compute quote before restart: `$1.58784/hour`; existing persistent disk
  remains approximately `$0.04/hour`
- Policy/learning provenance: none; the run was intentionally policy-free
- Commands:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
  PROJECT_GIT_BRANCH=codex/dofbot-asset-smoke \
  make sync

  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-inspect
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-view
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make stop
  brev ls --json
  ```

- Official USD:
  `Robots/Yahboom/Dofbot/dofbot.usd`
- Resolved USD:
  `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0/Isaac/Robots/Yahboom/Dofbot/dofbot.usd`
- Robot/articulation-root prim: `/World/envs/env_0/Dofbot`
- Result: initialized fixed-base articulation, 11 ordered joints, 12 ordered
  bodies, three configured actuator groups, and one onboard camera prim at
  `/World/envs/env_0/Dofbot/link4/Camera`
- Acceptance checks: articulation initialized, expected joint count, expected
  body count, articulation root present, and onboard camera present all passed
- Machine artifact: `artifacts/dofbot/asset_contract.json`
- Asset contract SHA-256:
  `1c0d806e4c61206355bddea738481496c45a98d789b5f64f269ec1d3f574a2b2`
- Viewer log: `Simulation App Startup Complete`, `app ready`, Kit visualizer
  registered, and WebRTC extension started; the reviewed local log is ignored
  by Git as machine-specific evidence
- Visual result: passed at 2026-07-26 22:34 PDT; the user confirmed the
  stationary green DOFBOT in the secure Viewer
- Scope audit: no hard-coded joint motion, RGB tensor capture, PPO, checkpoint,
  SFT, imitation learning, or CV pipeline was executed
- Compute lifecycle: final artifact and Viewer log were downloaded; stop was
  requested without deleting the instance or persistent disk, and terminal
  `STOPPED` verification is recorded in `docs/STATUS.md`
- Conclusion: Goal 1 passed both the machine contract and the explicit user
  visual gate; Goal 2 remains planned and requires a separate approved run

## 2026-07-26 — DOFBOT Goal 2 local safety harness passed

- Branch: `codex/dofbot-safe-motion`
- Runtime used: local pure Python and remote-command dry-runs only
- Billable GPU started: no
- Controlled joint set: `joint1`, `joint2`, `joint3`, `joint4`
- Command contract: position targets bounded to `±5°` around the recorded
  defaults with a required `10°` limit margin
- Planned sequence: two-second default hold; one six-second sinusoid and
  one-second settle for each joint; eight-second multi-joint wave; three-second
  reset hold
- Machine thresholds: at least `±2.5°` single-joint excursion, at most `1°`
  inactive-joint drift, at most `1°` active-joint overshoot, at least 90%
  command/observation sign agreement, at least `1°` per joint in the
  simultaneous wave, and at most `1°` final reset error
- Local failure-path coverage: missing joint, unbounded sentinel, insufficient
  range, amplitude above `5°`, unaccepted/nonofficial Goal 1 input,
  live-contract drift, inactive-joint drift, active-joint overshoot, reversed
  observed sign, missing bidirectional excursion, missing multi-joint wave, and
  reset outside tolerance
- Validation commands:

  ```bash
  make show-dofbot-motion
  make show-dofbot-motion-view
  make test
  uv run --python 3.12 ruff check \
    tools/dofbot_motion_plan.py tools/dofbot_scene_cfg.py \
    tools/inspect_dofbot_asset.py tools/move_dofbot_joints.py \
    tests/test_dofbot_motion_plan.py
  ```

- Local result: all Goal 2 safety tests and command-preview checks passed
- Remote result: not run; `motion_contract.json`, physical simulator tracking,
  Viewer axis/sign confirmation, and reset confirmation remain pending
- Conclusion: the local harness is ready for a separately quoted and approved
  remote validation window, but Goal 2 is not complete

## 2026-07-27 — DOFBOT Goal 2 remote window stopped before motion

- Approved resource: existing `isaac-launchable-f150a5` (`92xbacz46`), AWS
  `g6.4xlarge`, NVIDIA L4 at the checked `$1.58784/hour` compute quote
- Scope: sync the merged safe-motion harness, run the headless motion contract,
  then request Viewer confirmation; no learning, camera capture, or resource
  creation/deletion
- Start: 18:06:06 PDT
- Remote sync result: passed; repository reached `main@e7307b8`
- Sync safeguard: checkout initially refused to overwrite the untracked Goal 1
  asset contract. Its expected SHA-256
  `1c0d806e4c61206355bddea738481496c45a98d789b5f64f269ec1d3f574a2b2`
  was verified, then the file was retained under
  `/workspace/goal1-evidence/` before the successful retry.
- Stop decision: when sync completed, the paid window had reached about
  59 minutes 51 seconds, beyond the approved 30-minute maximum. Stop was
  requested at 19:05:57 PDT before invoking `make dofbot-motion`.
- Machine result: not run; no `artifacts/dofbot/motion_contract.json`
- Visual result: not run; no Viewer confirmation
- Final infrastructure result: `STOPPED` verified with `brev ls --json`;
  instance and persistent disk retained
- Conclusion: this is an aborted infrastructure window, not a Goal 2 motion
  result. Goal 2 remains incomplete and requires a freshly quoted and approved
  window.

## 2026-07-27 — DOFBOT Goal 2 passed machine and visual gates

- Approved resource: reused only `isaac-launchable-f150a5` (`92xbacz46`), AWS
  `g6.4xlarge`, NVIDIA L4; no create, resize, reset, delete, camera, learning,
  checkpoint, or real-hardware action
- Checked compute quote: `$1.58784/hour`, plus the existing approximately
  `$0.04/hour` persistent disk
- Paid-window start: 19:16:55 PDT
- Remote source: `codex/dofbot-goal2-validation@c151777`
- Runtime: Isaac Launchable `3.0.0-beta2-post1`, Isaac Sim `6.0.1`
- Compatibility result: CUDA target-tensor stepping exited in the installed
  runtime for this one-robot scene. The articulation/physics target device was
  set to CPU while the L4 continued rendering the secure Viewer.
- Evaluation correction: initial `hold_default` settling samples remain
  recorded and limit-checked but are excluded from the post-settle
  command-envelope comparison.
- Machine command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-motion
  ```

- Machine result: passed all 11 checks in
  `artifacts/dofbot/motion_contract.json`
- Per-joint result: `joint1` through `joint4` each moved in both directions,
  achieved `40/40` command/observation sign agreement, stayed within the
  documented margin, participated in the simultaneous wave, and reset within
  tolerance
- Observed single-joint delta ranges:
  - `joint1`: `[-5.00°, 5.00°]`
  - `joint2`: `[-5.34°, 5.40°]`
  - `joint3`: `[-5.56°, 5.87°]`
  - `joint4`: `[-5.07°, 5.33°]`
- Maximum inactive-joint error: below `1°`; maximum reset error:
  approximately `0.16°`
- Motion contract SHA-256:
  `6107ea36dd81c848889c05a6413196d4e873f0cd44f407415bb82302c60d3cab`
- Viewer command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-motion-view
  ```

- Viewer machine result: six complete repeated cycles reported
  `machine_passed=True`; the stop request interrupted cycle seven
- User visual result: passed at 19:54 PDT. The user confirmed visible
  small-amplitude DOFBOT movement and rocking/wave behavior; the subtle motion
  is expected from the deliberate `±5°` bound.
- Visual evidence handling: an 8.875-second user screen recording was reviewed
  locally and not committed because repository policy excludes videos
- Compute lifecycle: stop requested immediately after the visual confirmation;
  `brev ls --json` confirmed terminal `STOPPED` at 20:04:45 PDT. The existing
  instance and persistent disk were retained.
- Conclusion: Goal 2 passed the policy-free machine contract and explicit user
  visual gate. Goal 3 camera capture remains out of scope for this experiment.

## 2026-07-27 — DOFBOT shared Yahboom API bridge passed local dry-run

- Branch: `codex/dofbot-yahboom-control-api`
- Runtime: local pure Python only
- Shared application API: Yahboom's documented
  `Arm_serial_servo_write(id, angle, time)` and
  `Arm_serial_servo_read(id)` method shapes
- Normalized command: named `joint1` through `joint4` positions in radians and
  a positive duration in milliseconds
- Isaac integration: the existing Goal 2 runner now sends targets through the
  vendor-shaped adapter and normalized `DofbotArm` interface
- Yahboom integration: the hardware adapter exposes the official
  `Arm_serial_servo_write(id, angle, time)` and
  `Arm_serial_servo_read(id)` boundary
- Candidate mapping: servo IDs `1` through `4` correspond to `joint1` through
  `joint4`; zero radians maps to the documented 90-degree centered pose
- Dry-run command:

  ```bash
  make dofbot-api-dry-run
  ```

- Dry-run result: 411 samples at 10 Hz encoded to 1,644 official single-servo
  calls; each servo remained within `[85°, 95°]`
- Failure-path coverage: incomplete/extra/non-finite commands, invalid
  durations, out-of-range angles, malformed calibration, failed servo reads,
  and unverified real-hardware reads/writes
- Safety result: `Arm_Lib` was not imported, no GPU was started, no hardware
  was commanded, and the physical backend made zero writes when calibration
  was unverified
- Physical result: not run; direction and per-device zero offsets must be
  calibrated on the user's arm before setting `hardware_verified=true`
- Conclusion: the common software API and translation are locally validated;
  physical sim-to-real calibration remains a separate safety-gated experiment

## 2026-07-27 — DOFBOT ActionChunk v1 config passed local compilation

- Branch: `codex/dofbot-motion-config`
- Runtime: local pure Python and remote-command dry-runs only
- Input:
  `configs/dofbot/motions/safe_api_wave.json`
- Schema: five complete absolute four-servo poses at 10 Hz, with integer
  angles, movement duration, and hold duration
- Safety bounds: servo IDs `1` through `4` only, `[85°, 95°]` angle envelope,
  at most `5°` between configured poses, neutral start and finish, and at most
  60 seconds total duration
- Compiler result: 9 seconds, 90 complete-pose samples, and 360 official
  `Arm_serial_servo_write(id, angle, time)` calls
- Maximum compiled change: `1°` per 100-millisecond sample
- Validation command:

  ```bash
  make dofbot-motion-config-dry-run \
    MOTION=configs/dofbot/motions/safe_api_wave.json
  ```

- Failure-path coverage: schema drift, unsupported control rate, invalid or
  partial poses, non-integer and out-of-envelope angles, misaligned or
  excessive durations, duplicate steps, non-neutral start/end, missing
  motion, more than `5°` configured jump, excessive total runtime, observation
  schema/count drift, non-finite/out-of-envelope observations, missed targets,
  and failed final reset
- Local result: 71 Python tests, remote-command previews, targeted Ruff, shell
  syntax, and `git diff --check` passed
- Preview-test repair: macOS Bash did not reliably exit on failed top-level
  `[[ ... ]]` assertions under `set -e`. The remote preview suite now uses
  explicit assertion helpers, and finite Isaac motion wrappers pass
  `--headless` explicitly.
- Scope: the config is validated before Kit starts; no Brev connection, GPU,
  Isaac execution, Viewer, camera tensor, policy, checkpoint, physical
  `Arm_Lib`, or real-hardware command was used
- Conclusion: the ActionChunk software contract is ready for review. It is not
  simulator-accepted until a separately approved headless run passes, and it
  is not visually accepted until the user confirms the configured sequence in
  the secure Viewer.

## 2026-07-27 — DOFBOT ActionChunk small profile passed machine but failed visual amplitude

- Approved resource: reused only `isaac-launchable-f150a5` (`92xbacz46`), AWS
  `g6.4xlarge`, NVIDIA L4; no create, resize, reset, delete, camera, policy,
  checkpoint, learning, `Arm_Lib`, or real-hardware command
- Live compute quote: `$1.58784/hour`, plus the existing approximately
  `$0.04/hour` persistent disk
- Paid-window start: 22:47:04 PDT
- Remote source: `main@8e98aa9`, the merge commit for PR #15
- Headless command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-motion-config \
    MOTION=configs/dofbot/motions/safe_api_wave.json
  ```

- Headless result: all six machine checks passed. Maximum configured-pose
  tracking error was `0.667°`, maximum observed excursion was `5.430°`, and
  final neutral error was `0.076°`.
- Machine artifact:
  `artifacts/dofbot/motion_config_small_amplitude_2026-07-27.json`
- Machine artifact SHA-256:
  `4fe7d73b7ee778aacfe5cf20cec3b653bd6f45b387533706b84407e0b2ad3d8b`
- Viewer command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-motion-config-view \
    MOTION=configs/dofbot/motions/safe_api_wave.json
  ```

- Viewer machine result: at least 117 complete repeated cycles reported
  `machine_passed=True` before monitoring ended.
- User visual result: failed the amplitude gate. The user saw that the arm
  moved and repeated, but judged the `±5°` behavior too small and not the
  expected obvious bend.
- Stop request: 23:14:41 PDT, about 27 minutes 37 seconds after start and
  within the 30-minute cap; a second idempotent stop request was issued while
  the Brev control plane still reported `STOPPING`.
- Final resource state: `STOPPED` verified with `brev ls --json` at 23:23:08
  PDT; instance and persistent disk retained
- Conclusion: this config is machine-pass/visual-fail and must not be marked
  complete. The machine artifact remains immutable; the later human result is
  recorded here.

## 2026-07-27 — DOFBOT ActionChunk visible profile passed local fail-closed gates

- Branch: `codex/dofbot-motion-config-validation`
- Motivation: make arm bending visibly obvious rather than relying on subtle
  base-dominated rocking
- Revised poses after the first remote overshoot check: neutral
  `[90, 90, 90, 90]`, positive `[100, 76, 104, 104]`, neutral, negative
  `[80, 104, 76, 76]`, neutral
- Safety envelope: `[75°, 105°]`; at most `15°` between configured poses,
  `1°` between compiled 100-millisecond samples, and at least `10°` observed
  excursion required by the machine gate
- Compiler result: 12.4 seconds, 124 complete-pose samples, and 496 official
  `Arm_serial_servo_write(id, angle, time)` calls
- Local result: all 71 Python and shell/preview tests passed; the dry-run
  reported all compile-time acceptance checks true
- Physical safety boundary: Yahboom's documented API range is `0–180°`, but
  the real backend remains disabled because direction and per-device offsets
  are not calibrated
- Conclusion: software gate passed only. The revised profile needs a fresh
  approved Isaac headless run and explicit user Viewer confirmation.

## 2026-07-28 — visible profile passed machine gate but failed motion-quality gate

- Approved target: reused only `isaac-launchable-f150a5` (`92xbacz46`), AWS
  `g6.4xlarge`, NVIDIA L4 at `$1.58784/hour` plus the existing disk; no
  instance creation, resize, reset, or deletion
- Paid-window start: 08:20:57 PDT
- Remote source: `83f24c6dc521927247d3f76ba4fec4b6358c2df1`
- Headless command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-motion-config \
    MOTION=configs/dofbot/motions/safe_api_wave.json
  ```

- First attempt at exact `±15°` reached the poses but exceeded the observation
  envelope on joint 3 (`16.293°` excursion), so it failed closed. The command
  was reduced to `±14°` without relaxing the acceptance threshold.
- Revised machine result: all six checks true, 124 observations, 496 official
  calls, maximum checkpoint error `0.866°`, maximum observed excursion
  `15.175°`, and final neutral error `0.114°`
- Contract SHA-256:
  `2af0a94931ebd8c580611584a91ff4252742953723fc813672a85fc5fe93346b`
- Viewer command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-motion-config-view \
    MOTION=configs/dofbot/motions/safe_api_wave.json
  ```

- Viewer result: `Simulation App Startup Complete`; cycles 1 through 13 each
  reported `machine_passed=True`
- User visual result: failed. The larger range was visible, but the arm moved
  slowly through stair-step targets, shook between them, and still did not look
  decisive enough. This is explicitly not an ActionChunk visual pass.
- Root cause: the compiler expanded every movement into 10 Hz intermediate
  targets and replayed four vendor-shaped API calls for every sample. This
  conflated application commands with simulator observation cadence.
- Stop: requested immediately after the visual rejection; terminal `STOPPED`
  verified with `brev ls --json` at 08:40 PDT. Instance and disk retained.

## 2026-07-28 — pose-boundary API dispatch passed local fail-closed gates

- Branch: `codex/dofbot-visible-envelope-fix`
- Application semantics: each of five poses dispatches exactly one
  `Arm_serial_servo_write(id, angle, time)` per controlled servo, for 20 calls
  total; 10 Hz observations remain separate from API dispatch
- Isaac semantics: the backend models the servo's `duration_ms` at physics rate
  with a smoothstep trajectory rather than application-level 100 ms commands
- Revised poses: neutral, `[110, 62, 118, 118]`, neutral,
  `[70, 118, 62, 62]`, neutral
- Safety profile: `[60°, 120°]`, at most `30°` between configured poses,
  two degrees of configured envelope margin, and a `20°` minimum observed
  excursion
- Timing: 0.7-second main transitions; complete loop 5.6 seconds; 56
  observation checkpoints
- Local result: all 71 tests, Git LFS checks, remote-command previews, targeted
  Ruff, `git diff --check`, and dry-run acceptance passed
- Scope: no GPU, real hardware, camera tensor, policy, or checkpoint used
- Conclusion: software gate passed only. A fresh approved paid window must
  prove both Isaac machine acceptance and visibly smooth, decisive motion.

## 2026-07-28 — pose-boundary ActionChunk passed machine and Viewer gates

- Approved target: reused only `isaac-launchable-f150a5` (`92xbacz46`), AWS
  `g6.4xlarge`, NVIDIA L4 at the checked `$1.59/hour` compute quote plus the
  existing disk; no instance creation, resize, reset, or deletion
- Paid-window start: 19:18:06 PDT
- Remote source: `main@ce3f8eb438cc6969b61fccfde4f6b648da3a2253`
- Headless command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-motion-config \
    MOTION=configs/dofbot/motions/safe_api_wave.json
  ```

- Headless result: all six checks true. The 5.6-second config produced 56
  observations and only 20 official
  `Arm_serial_servo_write(id, angle, time)` calls using
  `once_per_servo_per_pose` dispatch.
- Machine metrics: maximum checkpoint error `1.243°`, maximum observed
  excursion `29.319°`, and final neutral error `0.141°`
- Per-joint observed ranges:
  - servo 1: `[69.984°, 110.008°]`
  - servo 2: `[61.866°, 118.157°]`
  - servo 3: `[60.924°, 119.319°]`
  - servo 4: `[61.034°, 119.178°]`
- Machine artifact: `artifacts/dofbot/motion_config_contract.json`
- Machine artifact SHA-256:
  `8a9da487d8eae33be56398f17616a1ffa1204ac809f3c6f51d64d68b2f929ea5`
- Viewer command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-motion-config-view \
    MOTION=configs/dofbot/motions/safe_api_wave.json
  ```

- Viewer machine result: `Simulation App Startup Complete`; cycles 1 through
  15 each reported `machine_passed=True`, and cycle 16 began before stop
- User visual result: passed. The user saw two clearly larger main motions and
  judged them much smoother than the prior stair-step profile. The user also
  noted small motion between the main poses and asked for a somewhat larger
  range in future real tasks.
- Interpretation: the configured sequence deliberately returns to
  `neutral_middle` between its two main poses. Any smaller residual movement
  around a target is simulator actuator settling, not replayed 10 Hz
  application commands. Larger future ranges must be task-, collision-, and
  camera-validated rather than globally enabled here.
- Scope: no camera tensor, policy, checkpoint, physical `Arm_Lib`, or real
  hardware command was used
- Evidence retrieval: headless contract, Viewer contract, and Viewer log were
  copied from the container before stop; generated machine evidence was not
  reconstructed or edited
- Stop request: 19:25:41 PDT; a second idempotent stop request was issued while
  Brev remained `STOPPING`; terminal `STOPPED` verified at 19:33 PDT. Instance
  and persistent disk retained.
- Conclusion: ActionChunk v1 pose-boundary execution is complete. Machine and
  user visual gates passed; Goal 3 onboard RGB capture is next.

## 2026-07-28 — onboard RGB camera contract passed local gates

- Branch: `codex/dofbot-camera-contract`
- Scope: Goal 3 RGB preparation only; no GPU, arm motion, depth, segmentation,
  CV model, policy, checkpoint, or real hardware
- Source camera:
  `/World/envs/env_0/Dofbot/link4/Camera`; the sensor config uses `spawn=None`
  to retain the camera authored by NVIDIA's Yahboom DOFBOT USD
- Input config:
  `configs/dofbot/camera/goal3_onboard_rgb.json`
- Observation contract: one `torch.uint8` RGB tensor in
  `[1, 480, 640, 3]` `NHWC` layout, sampled every `0.1 s` of simulation time
  for a nominal 10 Hz simulator rate
- Timing boundary: the 10 Hz baseline is not a claim about the unresolved
  physical camera FPS, exposure, lens distortion, or transport latency
- Static calibration fixture: red cube, green cylinder, and blue cuboid on
  the tabletop, deterministically placed from the authored camera frame before
  simulation starts
- Remote machine gates: original `UsdGeom.Camera`, initialized sensor, five
  advancing frames, exact shape/dtype, non-constant RGB, 10 Hz simulation-time
  cadence, all target centers geometrically inside the image, and a hashed PNG
- Planned machine evidence:
  `artifacts/dofbot/camera_contract.json` plus the Git-LFS-tracked
  `artifacts/dofbot/camera_rgb.png`
- Viewer contract: switch the secure viewport to the same onboard camera prim
  and keep the scene alive until the user compares it with the saved PNG
- Local command: `make test`
- Local result: all 80 tests passed, including strict camera config,
  synthetic failure cases, Git LFS rules, and remote command previews;
  targeted Ruff, Python compilation, shell syntax, and `git diff --check`
  also passed
- Conclusion: local software gate passed only. Goal 3 remains remote machine
  pending and visual pending; a fresh price check and explicit paid-window
  approval are required before starting the existing Brev instance.

## 2026-07-28 — onboard RGB remote gate found dynamic-pose blocker

- Branch: `codex/dofbot-camera-contract`; latest remote diagnostic commit:
  `db701ba`
- Approved infrastructure: reused only `isaac-launchable-f150a5`
  (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4; no instance creation, resize,
  deletion, disk deletion, policy, checkpoint, CV model, or real hardware
- Command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-camera
  ```

- Confirmed sensor contract: official
  `/World/envs/env_0/Dofbot/link4/Camera` is a `UsdGeom.Camera`; initialized
  RGB output is `torch.uint8[1,480,640,3]` in NHWC order; five distinct
  frames advanced at exact `0.1 s` simulation-time intervals
- Confirmed optics: perspective projection, focal length `0.24`, horizontal
  aperture `0.20955`, vertical aperture `0.152908`, derived FOV
  `47.1686 x 35.3394` degrees, and effective intrinsics
  `fx=fy=732.9993`, `cx=320`, `cy=240`
- Failure: after direct accepted-pose writes, rendered synchronization, and a
  wait longer than the configured camera period, the sensor world position
  and OpenGL quaternion remained at the neutral authored pose. The
  prim-bound Camera `FrameView` did not follow the live PhysX articulation
  link, so the requested changing onboard view could not be honestly shown.
- Rejected diagnostic: a simulation-only 180-degree optical-frame flip put
  all three target centers inside the geometric image bounds, but every
  captured pixel was zero in all five frames. The camera was looking into the
  robot body; the flip was removed and is not an accepted calibration.
- Machine result: **failed** (`rgb_is_nonconstant=false` in the flip
  diagnostic; dynamic pose remained fixed in the official-prim diagnostic)
- Visual result: **not run**. A static or black Viewer would not satisfy the
  requested acceptance and was intentionally not presented.
- Next hypothesis: retain the official optical parameters but explicitly
  synchronize sensor world pose from live `link4` pose using a neutral
  camera-to-link extrinsic. Record this as adapter behavior, then rerun the
  immutable machine contract before opening Viewer.
- Resource lifecycle: stop requested immediately after diagnosis; a second
  idempotent stop was issued while Brev remained `STOPPING`; terminal
  `STOPPED` was verified with `brev ls --json` at 21:11 PDT. Instance and
  existing persistent disk were retained.
- Conclusion: Goal 3 remains incomplete: local pass / remote machine fail /
  visual not run.

## 2026-07-28 — explicit link4-camera binding passed local gates

- Branch: `codex/dofbot-camera-contract`
- Scope: local Goal 3 remediation only; no GPU, depth, segmentation, CV
  model, policy, checkpoint, real hardware, or billable-resource transition
- Root-cause response: retain the official
  `/World/envs/env_0/Dofbot/link4/Camera` prim and its optics, calibrate a
  fixed `T_link4_camera` at neutral, and explicitly compute
  `T_world_camera = T_world_link4 * T_link4_camera` from the live PhysX body
  state
- Runtime behavior: static capture, accepted-pose selection, and the looping
  secure Viewer all call the Isaac Camera world-pose API in the `opengl`
  convention; Isaac Lab 3.0 `(x,y,z,w)` articulation/camera quaternions cross
  an explicit boundary into the scalar-first transform math, and no
  replacement camera prim is created
- New fail-closed gates: calibration round-trip position/orientation error,
  maximum applied world-pose error, and minimum observed camera
  translation/rotation as `link4` moves
- Durable evidence schema: `camera_contract.json` now names the explicit
  adapter behavior, fixed extrinsic, neutral calibration poses, synchronization
  timing, per-candidate desired/actual poses, and aggregate binding metrics
- Local command: `make test`
- Local result: all 94 tests passed, including pure rigid-transform
  composition/inversion, quaternion sign equivalence, strict binding config,
  machine-gate failure cases, and AST checks that both capture and Viewer
  invoke the public pose API; targeted Ruff, Python compilation, and
  `git diff --check` also passed
- Conclusion: local remediation passes, but Goal 3 remains incomplete. A
  fresh approved GPU window must produce a passing machine artifact before
  the Viewer is opened for the user's changing-view confirmation.

## 2026-07-28 — onboard RGB camera passed machine and Viewer gates

- Branch: `codex/dofbot-camera-contract`; accepted remote commit: `dbd09a7`
- Approved infrastructure: reused only `isaac-launchable-f150a5`
  (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4 at `$1.58784/hour`; no instance
  creation, resize, deletion, disk deletion, policy, checkpoint, CV model, or
  real-hardware command
- Machine command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-camera
  ```

- Machine result: **passed**. The official
  `/World/envs/env_0/Dofbot/link4/Camera` remained the `UsdGeom.Camera`;
  RGB was `torch.uint8[1,480,640,3]` NHWC; five frames advanced at exact
  `0.1 s` simulation cadence; RGB was non-constant; all three target centers
  were in frame; and the PNG was hashed.
- Dynamic binding: maximum observed camera translation/rotation across the
  accepted ActionChunk poses was `0.065636 m` / `57.4071 deg`. Maximum
  applied position/orientation error was `1.46e-8 m` / `1.12e-5 deg`.
- Fixture: red cube, green cylinder, and blue cuboid were spawned once in a
  world-fixed optical plane `0.32 m` in front of the settled neutral camera.
  Their floating placement is deliberately diagnostic and is not a realistic
  tabletop or physical-mount claim.
- Viewer command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-camera-view
  ```

- Visual result: **passed** at 2026-07-28 22:13 PDT. The user saw all three
  targets from the onboard camera, switched the viewport to Perspective, and
  confirmed the same world-fixed fixture above the moving DOFBOT.
- Evidence: `artifacts/dofbot/camera_contract.json` and the Git-LFS-tracked
  `artifacts/dofbot/camera_rgb.png`; the user screenshot was reviewed but is
  not committed because it is supporting human evidence rather than the
  canonical machine artifact.
- Resource lifecycle: stop was requested immediately after visual acceptance;
  `brev ls --json` verified terminal `STOPPED` at 2026-07-28 22:22 PDT.
  Instance and existing persistent disk were retained.
- Conclusion: Goal 3 is complete for simulated RGB observation and explicit
  `link4` camera binding. Realistic tabletop composition and physical camera
  calibration remain future work.

## 2026-07-28 — Goal 4 fixed-tabletop reaching passed local preparation

- Branch: `codex/dofbot-goal4-reaching-prep`
- Scope: local preparation only; no GPU, Isaac execution, real hardware,
  gripper command, target contact/motion, camera controller input, policy, or
  checkpoint
- Config:
  `configs/dofbot/reaching/goal4_fixed_tabletop.json`
- Scene: a collision-enabled static table with top at `z=0.12 m`; a
  collision-enabled static 5 cm red cube resting on the table; and a
  `Wrist_Twist` approach waypoint nine centimeters above the cube center
- Scripted baseline: five safe absolute poses, neutral start/end, 60°-120°
  envelope, and 20 official pose-boundary
  `Arm_serial_servo_write(id, angle, time)` calls
- State baseline: 5 Hz damped-least-squares translation-Jacobian controller,
  maximum 4° joint change per step, maximum 30 steps, and the same Yahboom API
  boundary
- Machine criteria prepared: physical prim/static-target presence, live asset
  compatibility, safe angles, wrist/table clearance, distance improvement,
  approach tolerance, exact API-call count, and neutral reset
- Commands:

  ```bash
  make dofbot-reach-dry-run
  make show-dofbot-reach
  make show-dofbot-reach-view
  ```

- Local result: all 110 repository tests passed, including 13 focused Goal 4
  tests, Git LFS checks, and remote command previews. Targeted Ruff, shell
  syntax, the pure local dry-run, and both reach command previews also passed.
- Acceptance: local software preparation passed; simulator machine and user
  visual gates remain pending. Goal 4 is not complete.
- Resource lifecycle: the retained Brev instance was not started;
  `brev ls --json` verified it `STOPPED` at 22:59 PDT.

## 2026-07-28 — Goal 4 machine gate passed but physical front/back Viewer gate failed

- Branch: `codex/dofbot-goal4-jacobian-compat`; remote commit: `d12b987`
- Approved infrastructure: reused only `isaac-launchable-f150a5`
  (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4 at `$1.58784/hour`; no instance
  creation, resize, deletion, disk deletion, physical-hardware command,
  gripper command, camera controller input, policy, or checkpoint
- Machine command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-reach
  ```

- Installed-runtime fixes: use Isaac Lab 3.0's public
  `robot.data.body_link_jacobian_w.torch` link Jacobian instead of the direct
  PhysX view; preserve nonzero failure exits; add safe state-command headroom;
  and allow the neutral trajectory to settle before evaluating reset
- Machine result: **passed**. Scripted distance improved from `0.20392 m` to
  `0.06898 m`; state distance improved from `0.20660 m` to `0.02035 m`;
  minimum wrist/table clearance was `0.12693 m`; 48/48 official API calls were
  accounted for; maximum neutral reset error was `0.6012 deg`; and every one
  of the eleven machine checks passed
- Viewer command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-reach-view
  ```

- Viewer runtime: `Simulation App Startup Complete`, `app ready`, and 32
  complete logged cycles with `machine_passed=True`; the downloaded immutable
  contract records cycle 31
- Human result: **failed physical front/back composition**. The user saw the
  intended safe downward approach, open gripper, no cube contact, and
  stationary cube, but observed that the table and target were on the same
  visible side as the Jetson/electronics carrier. The motion strategy itself
  was accepted.
- Root cause: the Goal 4 parser explicitly forced the table into world `-Y`.
  Goal 3's neutral camera optical fixture also occupied `-Y`, but its contract
  explicitly disclaimed any realistic tabletop or physical-mount meaning.
  Camera optical forward was therefore incorrectly reused as robot workspace
  front.
- Evidence: `artifacts/dofbot/reaching_viewer_contract.json`, SHA-256
  `37d40d45fcbf1c1e6aadaabf0d42b005d809f5aa61080d1f2ff07327d23cdf49`.
  The three user screenshots and full Viewer log were reviewed but remain
  uncommitted supporting evidence.
- Resource lifecycle: stop was requested at approximately 23:33 PDT, after the
  active run and visual review. Brev remained `STOPPING` with shell access
  unavailable during control-plane cleanup; `brev ls --json` reported terminal
  `STOPPED` at 23:47 PDT. The instance and existing disk were retained.
- Conclusion: Goal 4 is **not complete**. Local and remote machine gates pass,
  but a new base-frame front/rear contract, corrected work-side scene, and
  fresh machine plus Viewer validation are required.

## 2026-07-28 — Goal 4 physical-front correction passed local preparation

- Branch: `codex/dofbot-goal4-jacobian-compat`; PR #21 remains Draft
- Scope: local correction only; no Brev/GPU start, Isaac execution, real
  hardware, gripper command, cube contact/motion, camera controller input,
  policy, checkpoint, PPO, or VLA
- Root-frame contract: the user-reviewed Isaac Perspective layout defines
  world `+Y` as the workspace front and world `-Y` as the
  Jetson/electronics rear; the official robot asset remains unrotated
- Corrected scene: table center `(0.00, +0.25, 0.10) m`, target cube center
  `(0.00, +0.18, 0.145) m`, approach waypoint
  `(0.00, +0.18, 0.235) m`, and exactly `0.10 m` clearance from the base to
  the nearest table edge
- Corrected scripted comparison: the accepted rear-side poses were mirrored
  around neutral to `[90,82,80,82]`, `[90,76,75,79]`, and
  `[90,82,80,82]`; neutral start/end, 20 Yahboom-shaped pose-boundary API
  calls, and the 60°-120° envelope are unchanged
- Fail-closed additions: schema v2 requires the known front/rear vectors,
  rejects a relabeled frame and any rear-side table or target, records both
  front clearances, adds three orientation checks to the machine contract,
  and mirrors the default Perspective camera across world `Y`
- Commands:

  ```bash
  make test
  make dofbot-reach-dry-run
  make show-dofbot-reach
  make show-dofbot-reach-view
  ```

- Local result: all 112 repository tests passed, including 15 focused Goal 4
  tests; the dry-run reported every preparation check true and
  `gpu_started=false`; targeted Ruff, shell syntax, and both remote command
  previews passed
- Acceptance: **corrected v2 local preparation passed / corrected v2 remote
  machine pending / corrected v2 Viewer pending**. The historical v1 remote
  artifact remains immutable evidence but cannot satisfy the corrected gate.
  Goal 4 is not complete.

## 2026-07-29 — Goal 4 corrected physical-front reaching passed remote and Viewer gates

- Branch: `codex/dofbot-goal4-jacobian-compat`; commit: `eb7a266`; PR #21
- Approved infrastructure: reused only `isaac-launchable-f150a5`
  (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4 at the unchanged live quote of
  `$1.58784/hour`; no instance creation, resize, deletion, disk deletion,
  physical-hardware command, gripper command, camera controller input, policy,
  checkpoint, PPO, or VLA
- Corrected frame and scene: world `+Y` workspace front, world `-Y`
  Jetson/electronics rear, table center `(0.00, +0.25, 0.10) m`, static cube
  center `(0.00, +0.18, 0.145) m`, and `Wrist_Twist` approach waypoint
  `(0.00, +0.18, 0.235) m`
- Machine command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-reach
  ```

- Headless result: **passed 14/14 checks**. Scripted distance improved from
  `0.18821 m` to `0.07579 m`; state-controller distance improved from
  `0.21226 m` to `0.02037 m`; minimum wrist/table clearance was `0.13258 m`;
  52/52 Yahboom-shaped calls matched; and neutral reset error was
  `0.2295 deg`
- Viewer command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-reach-view
  ```

- Viewer runtime: `Simulation App Startup Complete`, `app ready`, and repeated
  `machine_passed=True` cycles. The byte-identical downloaded cycle-27
  artifact again passed 14/14 checks and has SHA-256
  `87faa5f892553c093dc190e331967990676672e4b383587e21a298cd8446d893`.
- Human result: **passed the corrected physical-front, safe no-contact reaching
  gate**. The user confirmed that the table/cube and Jetson/electronics are on
  opposite sides and that the arm bends toward the correct work side. The open
  gripper and static cube remained visible. Four user screenshots were
  reviewed but intentionally not committed.
- Limitation: the user observed only roughly 30°-45° of needed visible bending
  and an awkward motion. The table/cube are close and high, the controlled
  point is `Wrist_Twist` rather than a fingertip grasp frame, and the 5 Hz
  translation-only damped-least-squares controller has no orientation target,
  preferred elbow posture, collision-aware task geometry, or acceleration
  smoothing. This is acceptable for Goal 4 approach validation but is not
  grasp readiness.
- Local regression after evidence update: `make test` passed all 112 tests;
  the tracked artifact's commit, cycle, 14 checks, and machine pass were
  verified with `jq`; `git diff --check` passed
- Resource lifecycle: stop was requested at approximately 08:35 PDT; terminal
  `STOPPED` was verified with `brev ls --json` at 08:44 PDT. The instance and
  persistent disk were retained; neither was deleted or resized.
- Conclusion: Goal 4 is **complete for safe, policy-free, no-contact reaching**.
  Before any contact or grasping experiment, recalibrate table height and
  target distance, define the finger grasp pose, and add pose-aware IK,
  preferred-posture, collision, and trajectory-smoothness constraints.

## 2026-07-29 — Lower/farther pre-grasp scene passed local geometry gate

- Branch: `codex/dofbot-pregrasp-scene-calibration`
- Scope: free local scene calibration only; no Brev/GPU start, Isaac
  execution, new arm motion, real hardware, gripper command, cube
  contact/motion, camera control input, policy, checkpoint, PPO, or VLA
- Evidence anchor:
  `artifacts/dofbot/reaching_viewer_contract.json`, SHA-256
  `87faa5f892553c093dc190e331967990676672e4b383587e21a298cd8446d893`,
  commit `eb7a266`, with all 14 Goal 4 machine checks true
- Candidate config:
  `configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json`
- Scene change: horizontal table top `z=0.12 → 0.08 m`; nearest table edge
  `y=0.10 → 0.16 m`; cube center
  `(0.00,+0.18,0.145) → (0.00,+0.25,0.105) m`; approach waypoint
  `(0.00,+0.18,0.235) → (0.00,+0.25,0.195) m`
- Evidence-bounded reach sanity: candidate waypoint origin radius
  `0.31706 m` versus the recorded neutral-wrist radius `0.33865 m`, leaving
  `0.02159 m`. This is a necessary radial geometry condition, not sufficient
  IK or collision evidence.
- Controller-reuse diagnostic: the accepted Goal 4 final observation already
  recorded one joint at `59.50°`, inside the machine gate's 1° tolerance
  around the 60° lower boundary. The old translation-only controller is
  explicitly **not certified** for the candidate; safe joint-space reach
  remains a pose-aware IK task.
- Command:

  ```bash
  make dofbot-pregrasp-dry-run
  ```

- Local result: **passed 20/20 checks**. The gate verifies the baseline config
  SHA, all prior machine checks, unchanged frame/controller/actions/API
  boundary, lower/farther geometry, tabletop support and edge inset, base
  keepout, approach clearance, incremental displacement, and radial margin.
  All 119 repository tests passed, including seven focused calibration tests.
- Outputs: `artifacts/dofbot/pregrasp_scene_calibration.json` and
  `artifacts/dofbot/pregrasp_scene_calibration.svg`
- Acceptance: **local geometry passed / candidate Isaac machine pending /
  candidate Viewer pending**. Contact and grasp remain unauthorized. The next
  free task is finger-frame and pose-aware controller design with orientation,
  preferred posture, collision clearance, and trajectory smoothness.

## 2026-07-29 — Pose-aware terminal-finger pre-grasp passed local preparation

- Branch: `codex/dofbot-pose-aware-pregrasp`
- Scope: free local design, dry-run, tests, wrappers, and documentation only;
  no Brev/GPU start, Isaac execution, real hardware, wrist-twist or gripper
  command, target contact/motion, camera controller input, policy, checkpoint,
  PPO, or VLA
- Sources: Goal 1 asset contract SHA-256
  `1c0d806e4c61206355bddea738481496c45a98d789b5f64f269ec1d3f574a2b2`;
  lower/farther scene config SHA-256
  `ddfed9b2208c972cc97e5f32c21c8c519cac7e08aeb36e4571281178b4322119`
- Frame contract: midpoint of `Finger_Left_03` and `Finger_Right_03`,
  `Wrist_Twist`-to-midpoint approach axis, left-to-right closing axis
- Target contract: origin `(0.00,+0.25,0.195) m`, world `-Z` approach,
  world `+X` closing, `0.025 m` / `12°` / `20°` tolerances
- Control contract: 5 Hz weighted damped-least-squares over the averaged
  terminal-finger `6x4` link Jacobian; position plus approach error; preferred
  `[90,78,78,90]°` posture; only `joint1`-`joint4` through
  `Arm_serial_servo_write(id, angle, time)`
- Safety contract: integer commands in `[68,112]°`, at most 4° per step,
  20°/s, 60°/s²; body-center/table/target signed-distance proxies; Isaac
  contact reporter threshold `0.5 N`; static target; contact unauthorized;
  wrist twist and gripper uncommanded
- Commands:

  ```bash
  make test
  make dofbot-pregrasp-pose-dry-run
  make show-dofbot-pregrasp
  make show-dofbot-pregrasp-view
  ```

- Local result: **passed**. All 21 contract checks and all 139 repository
  tests passed, including deliberate collision, excessive contact-force, and
  reversed fixed-closing-axis rejection; targeted Ruff, shell syntax, Git LFS
  checks, and remote command previews passed
- Evidence: `artifacts/dofbot/pregrasp_pose_contract.json`
- Acceptance: **local preparation passed / Isaac machine pending / Viewer
  pending**. The report does not claim live kinematic reach, full collision
  geometry, contact sensing, motion quality, or visual acceptance. Goal 5 is
  not complete and contact/grasp remain unauthorized.

## 2026-07-29 — First pose-aware pre-grasp candidate failed closed remotely

- Branch: `codex/dofbot-pregrasp-remote-validation`; machine commit:
  `05ececc`
- Infrastructure: reused only `isaac-launchable-f150a5` (`92xbacz46`), AWS
  `g6.4xlarge`, NVIDIA L4, at the unchanged `$1.58784/hour` live quote; no
  instance creation, resize, deletion, or disk deletion
- Command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
  ```

- Compatibility fixes: preserved the original exception instead of allowing
  Isaac teardown to mask it; settled the arm at vendor-neutral before the
  first observation; separated observed physical limits from API command
  margins; planned velocity/acceleration in API-command space; and added
  stopping-distance braking before a command limit
- Trajectory result: position error improved by `0.25823 m`, from `0.33035 m`
  to `0.07212 m`. The API trajectory safely braked to `[90,69,69,69]°`;
  observed final angles were
  `[89.99996,65.96283,60.67178,64.98386]°`.
- Failed gates: terminal-finger position remained outside the `0.025 m`
  tolerance and the approach axis remained `103.21°` away from world `-Z`,
  outside the `12°` tolerance.
- Passed gates: closing axis, observed angle envelope, command margin,
  velocity, acceleration, collision proxies, physical table/static cube,
  no-contact/static-target, controller improvement, exact 248 API calls, and
  neutral reset. Maximum contact force was `0 N`; neutral reset error was
  `0.2886°`.
- Evidence:
  `artifacts/dofbot/pregrasp_machine_failure_2026-07-29.json`; the retrieved
  full 326,627-byte remote artifact had SHA-256
  `bc0ff9942be17fb542c9b56dc8cd04aa9bf2af4093ec97be4488fb7c34c7b8e5`
- Viewer: not started because the headless gate failed. No visual claim was
  made.
- Interpretation: this run proves that the current controller path stalls near
  its lower command margin; it does not prove the pose is globally
  unreachable. Before another paid run, perform a local reachability search
  over alternate posture branches and recalibrate the pose/scene without
  weakening the existing safety envelope.
- Resource lifecycle: stop was requested immediately after evidence retrieval;
  terminal `STOPPED` was verified with `brev ls --json` at approximately
  19:35 PDT. The instance and persistent disk were retained.

## 2026-07-29 — Exhaustive local reachability gate rejected the first pre-grasp pose

- Branch: `codex/dofbot-multistart-reachability`
- Scope: local pure Python only; no Brev start, GPU, Isaac runtime, policy,
  real-hardware command, contact, or grasp authorization
- Calibration source: steps 0-11 from the retrieved failed machine artifact
  generated at commit `05ececc`, full artifact SHA-256
  `bc0ff9942be17fb542c9b56dc8cd04aa9bf2af4093ec97be4488fb7c34c7b8e5`
- Model: three serial pitch links with a fixed 90° base branch, fitted directly
  from recorded terminal-finger midpoint positions and approach axes
- Fit quality: maximum/RMS position residual
  `0.00203 m / 0.00136 m`; maximum approach residual `0.00246°`
- Command:

  ```bash
  make dofbot-pregrasp-reachability
  ```

- Search coverage: `226,981` physical-envelope combinations over
  `[60,120]°` and `91,125` command-margin combinations over `[68,112]°`,
  at 1° resolution; nineteen workspace-front posture branches retained ranked
  candidates
- Result: zero candidates met the `0.025 m` position and `12°` world-down
  approach tolerances in either search
- Orientation proof: the continuous lower bound on approach error is
  `88.41°` over the physical envelope and `112.41°` over the command-margin
  envelope, before applying the workspace-front constraint
- Coupled geometry proof: the world-down target places the modeled wrist anchor
  `0.35791 m` from the proximal base, while the first two fitted links can span
  at most `0.19656 m`; the target misses even the unbounded-angle reach by
  `0.16134 m`
- Evidence: `artifacts/dofbot/pregrasp_reachability.json`; all sixteen
  provenance, calibration, exhaustive-search, rejection, and no-runtime-action
  checks pass
- Decision: reject the current lower/farther world-down pose. This result is a
  calibrated local model bound, not Isaac dynamics/collision acceptance. A
  revised scene/approach contract or a separately calibrated wider safety
  envelope is required before another paid run.

## 2026-07-29 — Joint-first task-space search produced one angled pre-grasp candidate

- Branch: `codex/dofbot-taskspace-candidate-search`
- Scope: local pure Python only; no Brev start, GPU, Isaac runtime, policy,
  hardware command, wrist-twist/gripper command, contact, or grasp
  authorization
- Commands:

  ```bash
  make dofbot-pregrasp-taskspace
  make dofbot-pregrasp-pose-dry-run
  make show-dofbot-pregrasp
  make show-dofbot-pregrasp-view
  ```

- Provenance: SHA-bound accepted Goal 1 asset contract, machine-passed
  ActionChunk contract, calibrated reachability config, and immutable rejected
  world-down reachability artifact
- Search coverage: `226,981` `[60,120]°` physical-envelope postures and
  `148,877` `[64,116]°` candidate-envelope postures at 1° resolution
- Low-table result: minimum meaningful derived table top `0.17945 m` at
  `[90,60,60,60]°`; the requested `<=0.12 m` table is infeasible without
  leaving the calibrated contract
- Selected candidate: the only strict pass is `[90,66,66,66]°`, with
  terminal-finger midpoint `(-0.00071,+0.22052,0.28278) m`, approach axis
  `(0,+0.94213,+0.33526)`, cube center
  `(-0.00071,+0.29589,0.28660) m`, and table top `z=0.26160 m`
- Safety margins: 6° physical, 2° candidate-envelope, `0.02118 m` raw
  terminal/table clearance, `0.05037 m` raw terminal/cube clearance, and
  `0.00415 m` minimum reserve after the 2.03 mm fitted-model residual and
  clearance thresholds
- Evidence: `artifacts/dofbot/pregrasp_taskspace_candidate.json`; all 30 local
  provenance, search, linkage, margin, and no-runtime checks pass
- Dry-run result: the generalized terminal-finger pose preview passes 21/21
  checks for the new angled candidate while retaining the historical
  world-down fixture as a passing local parser/controller regression case
- Validation: all 154 repository tests, targeted Ruff, shell syntax, Git LFS
  attributes, remote command previews, and `git diff --check` pass
- Infrastructure: `brev ls --json` verified
  `isaac-launchable-f150a5` (`92xbacz46`) remained `STOPPED` at 20:31 PDT;
  no instance or disk was created, resized, started, or deleted
- Decision: accept the revised candidate for future Isaac machine validation,
  not as Isaac, visual, contact, or grasp success. A fresh quote and explicit
  approval remain required before a paid headless run.

## 2026-07-29 — Angled candidate failed narrowly; direct joint-candidate correction prepared

- Remote source: merged `main@7b4591f`; existing
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4,
  `$1.58784/hour`; no create, resize, delete, real-hardware command, gripper
  command, contact authorization, policy, or checkpoint
- Command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
  ```

- Headless result: **failed closed**. Position improved
  `0.25660 -> 0.03382 m` against the unchanged `0.025 m` gate; approach error
  was `13.568°` against the unchanged `12°` gate; closing error was `0.321°`.
- Safety result: all sixteen remaining machine checks passed, with `0 N`
  contact force, `248/248` official API calls, and `0.0613°` maximum neutral
  reset error. Viewer was not started.
- Root cause: although the task-space scene was derived from joint candidate
  `[90,66,66,66]°`, Cartesian DLS settled at API command `[90,65,67,76]°`
  and observed `[89.989,65.073,68.603,77.889]°`. The controller optimized a
  Cartesian compromise instead of executing the selected joint branch.
- Machine evidence:
  `artifacts/dofbot/pregrasp_angled_machine_failure_2026-07-29.json`;
  full retrieved artifact: 327,197 bytes, SHA-256
  `396e19b56805f7771aeee284e9722b49be3bf2006c999d42d32baaafc0ecd555`.
- Free local correction:
  `codex/dofbot-isaac-tracking-calibration`. The angled config uses
  `validated_joint_candidate`; the historical world-down regression config
  keeps `cartesian_pose_ik`. Both use the same bounded/quantized official
  Yahboom four-servo API path.
- Fail-closed boundary: raising the candidate's search-boundary reserve from
  2° to 3° produces zero candidates, so the correction does not pretend that a
  stricter offline joint margin solves the controller mismatch.
- Preserved acceptance: unchanged Cartesian pose/axis tolerances, scene,
  collision/contact gates, command envelope, 4° maximum step, 20°/s,
  60°/s², exact API count, neutral reset, static cube, open gripper, and
  no-contact scope.
- Local evidence: `artifacts/dofbot/pregrasp_taskspace_candidate.json` now
  SHA-binds the angled machine failure and passes `33/33` checks; generalized
  pose dry-run passes `21/21`.
- Validation: Git LFS attributes, remote command previews, all `155`
  repository tests, targeted Ruff, and `git diff --check` pass.
- Current acceptance: **local correction passed / corrected Isaac machine
  pending / Viewer blocked pending machine pass**. Goal 5, contact, and grasp
  remain incomplete/unauthorized.
- Resource lifecycle: the paid window ran approximately 20:02-21:17 PDT. The
  intended 30-minute cap was exceeded; a 21:12 clock audit triggered immediate
  stop, and `brev ls --json` later returned explicit `STOPPED`. The instance
  and disk were preserved. This overrun is an operational failure, not a
  successful short-window validation.

## 2026-07-29 — Direct candidate exposed command/observation state mix

- Remote source: merged `main@150fa5d`; existing
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4,
  `$1.58784/hour`
- Official command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
  ```

- Official result: **failed closed only on position**. Position improved
  `0.25660 -> 0.03243 m` against the unchanged `0.025 m` gate. Approach and
  closing passed at `10.397°` and `0.313°`. Every safety/API/reset check
  passed with `0 N` contact, static cube, `248/248` official calls, and
  `0.0689°` neutral reset. Viewer was not started.
- Endpoint mismatch: configured `[90,66,66,66]°`; final API
  `[90,66,68,69]°`; observed
  `[89.980,66.328,70.529,71.535]°`
- Diagnostic probe: temporary preferred `[90,66,64,64]°` produced final API
  `[90,66,70,67]°`, observed `[89.982,66.168,72.067,69.270]°`,
  `0.03211 m` position error, `9.510°` approach error, and `0 N` contact.
  This falsified the assumption that the direct-candidate implementation
  tracked its configured endpoint.
- Root cause: the direct-candidate float delta was based on live observed
  angles, while integer command velocity, acceleration, and braking were based
  on the previous API command. Persistent Isaac drive lag therefore mixed two
  state spaces. The prior test covered one float step, not the complete
  quantized endpoint.
- Promoted evidence:
  `artifacts/dofbot/pregrasp_joint_candidate_machine_failure_2026-07-29.json`;
  official full artifact SHA-256
  `d1657332164f7ba9f3fb33d691041f29a2c43c81e838967a705d871924c07cfe`,
  diagnostic SHA-256
  `d2c61cc0331b2ed4cec4963379bdc68c2873f299820aeba4372d1482c6a61e1b`
- Free correction branch:
  `codex/dofbot-command-space-tracking-fix`
- Correction:
  - generate direct-candidate motion from previous API command state only;
  - keep observed joints authoritative for physical, Cartesian, collision,
    contact, and static-target gates;
  - require the final API command to equal the selected integer candidate with
    zero command velocity;
  - reject command-margin boundary candidates without braking reserve before
    launching Kit;
  - preserve the historical Cartesian IK observation-feedback path.
- Local evidence:
  `artifacts/dofbot/pregrasp_command_space_contract.json`; the injected
  tracking-lag observation `[90,66.3,70.5,71.5]°` does not alter the direct
  command trajectory, which reaches stopped `[90,66,66,66]°` in eight steps.
  All 22 local contract checks pass.
- Validation: `make test` passes 159/159; targeted Ruff, byte-identical local
  artifact regeneration, remote command previews, JSON parsing, and
  `git diff --check` pass. Full-repository Ruff reports only the pre-existing
  unrelated line-length finding at `tools/collect_environment_info.py:47`.
- Current acceptance: **local command-space correction passed / corrected
  Isaac machine pending / Viewer blocked pending machine pass**. No
  Cartesian, safety, contact, reset, or no-grasp gate was loosened.
- Resource lifecycle: approved start at 21:40:39 PDT; evidence retrieved before
  stop; stale `STOPPING` list state was refreshed; explicit `STOPPED` verified
  at 21:55 PDT. No instance or disk was created, resized, or deleted.

## 2026-07-29 — Exact pre-grasp API command exposed implicit-drive tracking error

- Remote source: merged
  `main@54b25ed98d325f5079daf5d34bec3ad1629ee136`; existing
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4,
  quoted `$1.58784/hour`
- Official command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
  ```

- Command result: the corrected controller reached the exact stopped
  `[90,66,66,66]°` API endpoint. This passes the specific regression that
  failed at `main@150fa5d`.
- Observed result: joints settled at
  `[90.093,66.987,70.641,69.828]°`; maximum observed/API error was `4.641°`.
  Position improved `0.25660 -> 0.03213 m` but failed the unchanged
  `0.025 m` gate. Approach and closing passed at `9.465° / 0.412°`.
- Safety result: all joint-envelope, velocity, acceleration, table/cube
  clearance, static-target, no-contact, API-count, command-margin, exact
  command-endpoint, and reset gates passed. Maximum contact was `0 N`.
  Viewer, gripper, contact, and grasp were not authorized.
- Evidence: the retrieved full artifact was 327,442 bytes, SHA-256
  `50efb65e1b31299e3e39fb517f024b4762ea68773d6c7a58e2a62df6e0d57033`;
  the promoted concise record is
  `artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json`.
- Diagnosis boundary: the stiffness-times-error values
  `[16.15,172.28,809.96,668.14]` are compatible with effort clipping, but the
  artifact recorded only planned command velocity. It omitted actual
  `joint_vel`, `joint_pos_target`, resolved drive buffers, and torque
  telemetry, so clipping is not yet distinguished from target-path, settling,
  drive, axis, collision, solver, or mass/inertia causes.
- Local branch:
  `codex/dofbot-command-space-remote-validation`
  - retain `maximum_final_joint_tracking_error_deg=1.0` and
    `final_api_joint_tracking_within_tolerance`;
  - preserve the default effort-100 scene until discriminating evidence exists;
  - prepare an isolated gravity/effort calibration matrix before another
    pre-grasp command.
- Resource lifecycle: start approved at 22:42:05 PDT; stop requested after
  evidence retrieval; terminal `STOPPED` verified at 22:55:05 PDT. The
  existing instance and disk were preserved.
- Current acceptance: **exact API endpoint passed remotely / joint tracking
  and Cartesian position failed / diagnostic preparation pending local
  completion / Viewer blocked**.

## 2026-07-29 — Prepare an isolated actuator diagnostic before another paid pre-grasp

- Scope: local code, schema, deterministic plan artifact, tests, and remote
  command preview only. No Brev start, Isaac execution, Viewer, table, cube,
  camera, policy, real hardware, contact, or grasp.
- Historical input:
  `artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json`; exact API
  endpoint `[90,66,66,66]°`, observed endpoint
  `[90.093,66.987,70.641,69.828]°`, maximum tracking error `4.641°`.
- Config:
  `configs/dofbot/calibration/goal5_actuator_diagnostic.json`.
- Fixed pose sequence: neutral start `[90,90,90,90]°`, mid-load
  `[90,78,78,78]°`, failed candidate `[90,66,66,66]°`, and neutral return.
- Orthogonal cases:
  - gravity on / effort 100 preserves the historical baseline;
  - gravity off / effort 100 isolates gravity/load;
  - gravity on / effort 250 isolates the earlier effort hypothesis.
- Per-physics-step telemetry: vendor-shaped API request, backend interpolated
  target, Isaac `joint_pos_target`, actual `joint_pos` and `joint_vel`,
  `joint_stiffness`, `joint_damping`, `joint_effort_limits`, computed/applied
  torque when meaningful, optional PhysX mass/inertia/DOF properties, critical
  contact force, and body positions. Optional PhysX probe failures retain the
  accessor name and exception text instead of silently producing an unexplained
  null.
- Settling contract: actual velocity no greater than `0.1°/s` continuously for
  `0.5 s`, with a bounded timeout. Planned command velocity is not used as a
  stability proxy. A two-second smoothstep bounds the largest transition to
  18°/s peak velocity and 36°/s² peak acceleration, below the existing
  20°/s and 60°/s² limits.
- Torque contract correction: implicit-actuator computed/applied buffers are
  approximate PD estimates, not measured PhysX solver torque. A nonzero gap
  may show that the software-side estimate reached its configured clip, but
  neither nonzero nor missing buffers establish physical saturation.
- Failure routing order: contact/self-collision, actual-velocity settling,
  target-buffer mismatch, telemetry/runtime compatibility, baseline identity,
  gravity sensitivity, effort sensitivity, then drive/axis/solver/model
  mapping.
- Operational safety: each tracking failure still writes its case artifact.
  The wrapper runs all three cases and summary, prints `[MATRIX_EXIT_CODE]`,
  and returns outer success so Brev cannot automatically retry a paid
  stateful experiment. The local wrapper parses the marker and fails `make`
  when the matrix itself failed.
- Local commands:

  ```bash
  make dofbot-actuator-calibration-dry-run
  make show-dofbot-actuator-calibration
  ```

- Evidence: `artifacts/dofbot/actuator_calibration_plan.json`.
- Local validation: 171/171 repository tests, targeted Ruff, Python
  compilation, shell syntax, deterministic plan regeneration, JSON parsing,
  remote-command preview, and `git diff --check` passed.
- Infrastructure: read-only `brev ls --json` returned explicit `STOPPED`;
  no GPU, Isaac process, Viewer, instance, disk, or hardware was started,
  created, resized, or deleted.
- Paid command remains unauthorized in this local record. After merge, a fresh
  quote and explicit approval are required before:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-actuator-calibration
  ```

- Next gate: retrieve all three case artifacts and the matrix summary, require
  `[MATRIX_EXIT_CODE] 0`, apply only the decision-specific correction, and
  rerun calibration. Pre-grasp and Viewer remain blocked until the selected
  actuator baseline passes the independent `1°` tracking gate.

## 2026-07-30 — Actuator matrix established gravity dependence and rejected effort 250 alone

- Scope: one approved paid matrix on the existing
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4.
  Rechecked compute quote: `$1.58784/hour`; existing disk approximately
  `$0.04/hour`. No Viewer, task scene, pre-grasp, contact, gripper, policy,
  checkpoint, hardware command, new instance, resize, or deletion.
- Provenance: merged `main@95b0ab1`; repaired machine commit
  `abd109f38dba838557910ed1ab439749cbd53120`; config SHA-256
  `e3be35ad14617c252151cdbf9d6090fd7655f9e96ba3600bb659cc9f577cf6f9`.
- Initial result: all poses executed, but optional PhysX array serialization
  raised `TypeError: Object of type array is not JSON serializable`. Because
  the Isaac launcher returned zero despite the traceback, the matrix failed
  closed on missing case artifacts.
- Minimal compatibility fix: normalize optional tensor/NumPy values to JSON
  lists, persist one `.log` per case, and require each case artifact to be
  non-empty independently of launcher exit status. Before remote rerun,
  171/171 local tests, targeted Ruff, shell syntax, remote preview, and
  `git diff --check` passed.
- Official command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-actuator-calibration
  ```

- Matrix result: `[MATRIX_EXIT_CODE] 0`, `matrix_complete=true`, automatic
  decision `settling_or_drive_stability_failure`, and pre-grasp, Viewer,
  contact, and grasp authorization all false.
- Gravity off / effort 100: diagnostic and one-degree tracking gates passed;
  maximum tracking error `0.0031647°`, maximum terminal reported velocity
  `0.0456728°/s`, maximum target-buffer error `0.000000851°`, contact `0 N`.
- Gravity on / effort 100: diagnostic and tracking gates failed; maximum
  tracking error `4.976193°`, maximum terminal reported velocity
  `16.344113°/s`, maximum target-buffer error `0.000001271°`, contact `0 N`;
  the implicit PD estimate reached its configured `100` clip.
- Gravity on / effort 250: the effort buffer and PhysX maximum force changed
  to `250`, and the implicit PD estimate reached the corresponding clip, but
  every selected target, observed
  position, and reported-velocity sample was identical to effort 100. Maximum
  tracking error remained `4.976193°`; contact remained `0 N`.
- Established: the API/backend/Isaac target path agrees; gravity removal
  resolves tracking; the gravity-on error is repeatable and contact-free.
  Falsified: increasing only `effort_limit_sim` from 100 to 250 changes or
  fixes the gravity-on trajectory.
- Instrumentation finding: over the last `0.183 s` of the gravity-on candidate,
  per-joint positions span at most `0.0000103°` while raw `joint_vel` reports
  as much as `16.344°/s`. The runtime simultaneously warns that this TGS
  configuration may produce noisy velocities. This is an evidence-bounded
  inference that raw velocity is not a trustworthy sole settling criterion,
  not proof that the remaining position error is solved.
- Evidence:
  `artifacts/dofbot/actuator_calibration_contract.json` and
  `artifacts/dofbot/actuator_calibration_result_2026-07-30.json`.
  The concise result binds the retrieved full case JSON, logs, and archive by
  exact size and SHA-256.
- Resource lifecycle: paid window began at 08:16:04 PDT; artifacts were
  retrieved and stop requested at 08:36:28 PDT, 20 minutes 24 seconds after
  start. Brev's asynchronous transition reached explicit `STOPPED` in standard
  `brev ls --json` at 08:50:21 PDT, 34 minutes 17 seconds after start. No
  instance or disk was created, resized, or deleted.
- Conclusion: **machine matrix complete / gravity dependence established /
  effort-250-only fix rejected / velocity instrumentation correction required /
  pre-grasp and Viewer blocked**. The next work is free local instrumentation
  and solver/drive experiment design, not another task-scene retry.

## 2026-07-30 — Position-derived settling and solver/drive matrix passed local preparation

- Scope: local replay, contract implementation, and remote-command dry-run
  only. No Brev, Isaac, Viewer, camera, pre-grasp, contact, gripper, real
  hardware, policy, or checkpoint command was issued.
- Source integrity: the replay loaded the three ignored retrieved case JSON
  files and required their exact byte counts and SHA-256 hashes to match
  `artifacts/dofbot/actuator_calibration_result_2026-07-30.json`.
- Velocity contract: physical settling is a `100 ms` finite difference of
  observed joint position held below `0.1°/s` for `500 ms`. Raw `joint_vel`
  remains a required compatibility signal; mismatch above `1°/s` fails
  diagnostic completeness rather than being interpreted as physical motion.
- Offline result:

  | Case | Max derived speed | Max raw speed | Max mismatch | Tracking error | Derived hold |
  | --- | ---: | ---: | ---: | ---: | --- |
  | gravity off / effort 100 | `0.025304°/s` | `0.045673°/s` | `0.085753°/s` | `0.003165°` | right-censored |
  | gravity on / effort 100 | `0.041972°/s` | `16.363141°/s` | `16.444165°/s` | `4.974117°` | pass |
  | gravity on / effort 250 | `0.041972°/s` | `16.363141°/s` | `16.444165°/s` | `4.974117°` | pass |

- Interpretation: the gravity-on articulation is physically settled, so the
  old raw-velocity-based stability diagnosis is rejected. The nearly
  five-degree gravity-on position error is unchanged and remains the actual
  control problem. Gravity-off's historical record ended on the former raw
  gate before a complete new derived hold, so the replay marks that detail
  rather than inventing missing samples.
- Follow-up plan: four gravity-on, effort-100 cases change one factor per
  stage: baseline TGS; `enable_external_forces_every_iteration=true`;
  `solver_velocity_iteration_count=2`; and damping `100 -> 50`. Stiffness
  remains `10000` and solver position iterations remain `8`.
- Commands:

  ```bash
  make dofbot-actuator-velocity-reanalysis
  make dofbot-solver-drive-dry-run
  make show-dofbot-solver-drive
  ```

- Evidence:
  `artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json` and
  `artifacts/dofbot/solver_drive_diagnostic_plan.json`.
- Validation: `178/178` repository tests, Git LFS attributes, remote-command
  previews, targeted Ruff, Python compilation, shell syntax, JSON parsing, and
  `git diff --check` passed.
- Result: **offline reanalysis passed / four-stage dry-run passed / paid GPU
  run not authorized / pre-grasp and Viewer blocked**. A future
  `make dofbot-solver-drive` requires branch review, a fresh live quote, and
  explicit approval.

## 2026-07-30 — Solver/drive matrix repaired telemetry but not gravity-on tracking

- Scope: one approved headless window on the retained
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4.
  The live compute quote remained `$1.58784/hour`; the existing disk remained
  approximately `$0.04/hour`. No instance or disk was created, resized, or
  deleted.
- Provenance: merged
  `main@02f27d259d271a5bb01a9739c1c270db702de9f7`; config SHA-256
  `5ae01f684857f78fb3eb973cf32655617a18eb3ec8d3847e20631140a0bb018d`.
- Command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-solver-drive
  ```

- Result: `[MATRIX_EXIT_CODE] 0`, `matrix_complete=true`, decision
  `external_force_iteration_repairs_velocity_telemetry_only`.

  | Case | Tracking error | Derived speed | Raw speed | Raw/derived mismatch | Tracking gate |
  | --- | ---: | ---: | ---: | ---: | --- |
  | baseline TGS | `4.97412°` | `0.04190°/s` | `16.36310°/s` | `16.44402°/s` | fail |
  | external forces each iteration | `5.04065°` | `0.04259°/s` | `0.02504°/s` | `0.09921°/s` | fail |
  | two velocity iterations | `5.04064°` | `0.04252°/s` | `0.02507°/s` | `0.09914°/s` | fail |
  | damping 50 | `4.88333°` | `0.05761°/s` | `0.05792°/s` | `0.10186°/s` | fail |

- All poses in all cases settled by position difference. All target-buffer
  errors were below `0.0000017°`; all monitored contact forces were `0 N`.
- Enabling external-force application on every TGS position iteration repairs
  the raw velocity signal, but does not improve position tracking. Adding two
  velocity iterations changes worst-case tracking by less than `0.000004°`.
  Halving damping improves the baseline by only `0.09079°`, leaving the result
  far outside the unchanged `1°` gate.
- Joint 3 remains the dominant error at the candidate: approximately
  `-4.97°` to `-5.04°`, or `-4.88°` under damping 50. This focuses the next
  local audit on per-joint drive force, axis/transmission semantics, and
  official-asset mass/inertia rather than another generic solver retry.
- Evidence:
  `artifacts/dofbot/solver_drive_diagnostic_result_2026-07-30.json`; it
  SHA/size-binds the four ignored raw JSON files, four logs, and matrix
  contract.
- Resource lifecycle: artifacts were retrieved before stop and standard
  `brev ls --json` reached explicit `STOPPED` at 18:12:50 PDT. No instance or
  disk was created, resized, or deleted.
- Validation: `179/179` repository tests, Git LFS attributes, remote command
  previews, targeted Ruff, promoted source SHA/size bindings, JSON parsing,
  and `git diff --check` passed.
- Acceptance: **remote matrix complete / velocity telemetry repaired /
  tracking unresolved / pre-grasp and Viewer blocked**. The next work is a
  GPU-free asset/drive audit before designing another paid matrix.

## 2026-07-30 — Official-asset drive audit and force-drive matrix passed local preparation

- Scope: temporary download and read-only inspection of NVIDIA's official
  Isaac 6.0 DOFBOT USD, diagnostic implementation, local dry-run, and remote
  command preview only. No GPU, Isaac runtime, Viewer, task scene, contact,
  gripper, real hardware, policy, or checkpoint ran.
- Source:
  `Robots/Yahboom/Dofbot/dofbot.usd`, 104,922,919 bytes, SHA-256
  `52c524ebb26c38a3d164daee10f6cac0f15487fce5408a38c0c94199a37f1303`.
  The 100 MB source and its schema layer were inspected from temporary
  storage and were not added to the repository or Git LFS.
- Established: the asset is meter-scaled and Z-up. Joints 1-4 form the
  expected serial body chain, all use axis X, and all author an angular
  `acceleration` drive with stiffness `1048`, damping `53`, maximum force
  `5.2`, and joint friction `0`. Runtime body masses total approximately
  `1.03481 kg`.
- Falsified: joint 3 has a unique official axis or drive tuning; the asset is
  centimeter-scaled; or implicit-actuator `computed_effort` and
  `applied_effort` are measured solver torque.
- Evidence correction: the prior 100-to-250 run still proves that the
  effort-limit and PhysX maximum-force writes changed and that the full
  gravity-on trajectory did not. Its implicit torque buffers are approximate
  PD estimates and cannot prove physical saturation.
- Hypothesis, not conclusion: changing composed drive type from
  `acceleration` to `force` repairs or materially reduces gravity-on tracking
  error.
- The new matrix holds gravity, poses, trajectory, external-force iteration,
  and solver settings fixed. It first reproduces acceleration with current
  runtime tuning, switches only drive type to force, then restores official
  stiffness, damping, and maximum force one field per stage. Before motion,
  the runtime reads back the composed drive type, axis, connected bodies,
  gains, and maximum force for every controlled joint and fails closed on a
  mismatch.
- Local commands:

  ```bash
  make dofbot-drive-model-dry-run
  BREV_INSTANCE_NAME=preview-only make show-dofbot-drive-model
  ```

- Evidence:
  `artifacts/dofbot/asset_drive_audit_2026-07-30.json` and
  `artifacts/dofbot/drive_model_diagnostic_plan.json`.
- Validation: `185/185` repository tests, targeted Ruff, Python compilation,
  shell syntax, JSON parsing, Git LFS attribute checks, deterministic dry-run,
  and headless remote preview pass.
- Resource lifecycle: standard `brev ls --json` returned explicit `STOPPED`
  at 19:29 PDT. No instance or disk was created, started, resized, or deleted.
- Acceptance: **official-asset audit passed / single-factor matrix prepared /
  drive-type root cause unproven / paid GPU, pre-grasp, and Viewer blocked**.
  After review, merge, a fresh quote, and explicit approval, the next paid
  command is
  `BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-drive-model`.

## 2026-07-30 — Drive-model matrix improved tracking but selected no passing configuration

- Scope: one approved headless window on the retained
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4.
  The fresh quote remained `$1.58784/hour`; no Viewer, table, cube, pre-grasp,
  gripper, contact task, hardware, policy, or checkpoint ran.
- Provenance: merged
  `main@d2abb247a188c23889778cfdd1f211f2bc8dd1a1`; config SHA-256
  `7644ca7f88f0fbcda2b041fc4eb5fd79f4aa21560dbf054c6da4e453f118bddd`.
- Command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-drive-model
  ```

- Result: all five case artifacts and logs plus the matrix contract were
  generated with `[MATRIX_EXIT_CODE] 0` and `matrix_complete=true`.

  | Case | Tracking error | Settled | Overshoot gate | Tracking gate |
  | --- | ---: | --- | --- | --- |
  | acceleration / 10000 / 100 / 100 | `5.04065°` | yes | fail | fail |
  | force / 10000 / 100 / 100 | `221160.35°` | no | fail | fail |
  | force / 1048 / 100 / 100 | `3.22899°` | yes | fail | fail |
  | force / 1048 / 53 / 100 | `1.73936°` | yes | pass | fail |
  | force / 1048 / 53 / 5.2 | `1.73936°` | yes | pass | fail |

- Established: the unchanged high-gain force drive is genuinely unstable and
  rejected. Restoring stiffness `1048` stabilizes it; restoring damping `53`
  reduces the stable error by another `1.48963°`. The best force-drive result
  improves on acceleration by `3.30129°` or `65.49%`, but no case passes the
  independent one-degree gate.
- Every case matched its requested composed drive type, the backend and Isaac
  targets agreed, and monitored contact remained `0 N`.
- Runtime-force comparison: the final two cases read back controlled PhysX
  maximum forces of `100` and `5.2` respectively. Nevertheless, all 647 API,
  backend-target, Isaac-target, observed-position, raw/derived-velocity, and
  contact samples plus all pose summaries are identical. A lower maximum force
  is falsified as a correction in this runtime.
- Machine-summary correction: `force_runtime_tuning` supplied position-derived
  telemetry but never settled because its drive state diverged. Therefore
  `position_velocity_instrumentation_incomplete` is not the correct matrix
  interpretation. The classifier now records the unstable case separately and
  continues evaluating later cases; the reviewed decision is
  `drive_model_ladder_no_resolution`.
- Evidence:
  `artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json`, which
  binds the ignored 11 raw files by exact byte size and SHA-256.
- Resource lifecycle: start at `19:51:11 PDT`, matrix summary at
  `19:54:41 PDT`, explicit `STOPPED` at `20:05:30 PDT`. The
  14-minute-19-second window cost approximately `$0.379` at the quoted rate.
  No instance or disk was created, resized, or deleted.
- Validation: `187/187` repository tests, 23 focused drive/actuator/solver
  tests, targeted Ruff, JSON parsing, all raw source byte/SHA bindings, Git LFS
  checks, remote-command previews, and `git diff --check` pass.
- Acceptance: **machine matrix complete / stable tracking materially improved /
  no passing drive configuration / pre-grasp and Viewer blocked**. The next
  work is a GPU-free residual-force-semantics audit, not another broad paid
  sweep.

## 2026-07-30 — Residual-force audit selected bounded gravity feed-forward

- Scope: local replay and official semantics/source review only. No Brev
  start, GPU, Isaac runtime, Viewer, pre-grasp, task scene, contact, gripper,
  real hardware, policy, or checkpoint ran.
- Command:

  ```bash
  make dofbot-residual-force-audit
  ```

- Source integrity: the replay verifies the exact promoted byte counts and
  SHA-256 values for the ignored `force_damping_53` and
  `force_authored_tuning` raw JSON files before analysis.
- Machine evidence replay: all 647 selected physical samples and all pose
  summaries are identical between runtime maximum-force readbacks `100` and
  `5.2`.
- Official semantics: PhysX release 109 scales articulation `maxForce` by the
  timestep only when `eDRIVE_LIMITS_ARE_FORCES` is set; without it, the value
  is an impulse. At the recorded 60 Hz, `5.2` is equivalent to `312` force
  units per second and `100` to `6000`. This is recorded as a high-confidence
  explanation, not a direct runtime-flag readback.
- Cause ranking: gravity/load remains the selected cause because the matched
  gravity-off case tracks within `0.0032°`. Static joint-frame/sign error is
  rejected as the primary cause; the full explicit PD actuator remains a
  fallback.
- Selected next hypothesis: keep force `1048/53/100` unchanged and add bounded
  PhysX gravity-compensation values as external actuation on joints 1-4. The
  future runner must require and record gravity-compensation, actuation-force,
  and incoming-joint-force APIs and preserve all target, settling, contact, and
  one-degree gates.
- Evidence:
  `artifacts/dofbot/residual_force_audit_2026-07-30.json`.
- Validation: all `192` repository tests, five focused audit tests, targeted
  Ruff, deterministic artifact regeneration, source byte/SHA replay, JSON
  parsing, Git LFS attributes, and `git diff --check` pass.
- Acceptance: **local audit passed / implementation selected / paid GPU,
  pre-grasp, and Viewer blocked**. The next paid gate, after implementation,
  review, merge, fresh quote, and approval, is isolated headless gravity-on
  calibration. Viewer remains third in the gate order after headless pre-grasp.

## 2026-07-30 — Bounded gravity feed-forward passed local preparation

- Scope: local implementation, fail-closed tests, deterministic plan
  generation, and remote-command preview only. No GPU, remote Isaac runtime,
  Viewer, pre-grasp, task scene, contact, gripper, hardware, policy, or
  checkpoint ran.
- Single-factor contract: both cases keep gravity on, force drive
  `1048/53/100`, external-force iteration, the four-pose Yahboom API
  trajectory, and the independent one-degree gate. Only
  `gravity_compensation_feed_forward` changes from false to true.
- Safety boundary: before any pose command, the runner requires
  `get_gravity_compensation_forces`, `set_dof_actuation_forces`, and
  `get_link_incoming_joint_force`. Every step clamps controlled-joint effort
  to `±5.2`, zeroes all uncontrolled DOFs, and records raw/applied effort plus
  the controlled child links' incoming 6D joint forces.
- Commands:

  ```bash
  make dofbot-gravity-feed-forward-dry-run
  BREV_INSTANCE_NAME=preview-only make show-dofbot-gravity-feed-forward
  ```

- Evidence: `artifacts/dofbot/gravity_feed_forward_plan.json`.
- Validation: `200/200` repository tests, eight focused feed-forward tests,
  targeted Ruff, Python compilation, shell syntax, deterministic artifact
  generation, JSON parsing, Git LFS checks, remote-command previews, and
  `git diff --check` pass.
- Resource state: `brev ls --json` returned retained instance
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4, as
  explicit `STOPPED`. No resource mutation occurred.
- Acceptance: **local implementation passed / machine calibration pending /
  pre-grasp and Viewer blocked**. After review and merge, a fresh quote and
  explicit approval are required before
  `BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-gravity-feed-forward`.
  A `<=1°` calibration pass advances only to the separate headless pre-grasp
  gate. Full explicit PD remains the fallback if feed-forward fails.

## 2026-07-31 — Bounded gravity feed-forward passed the machine gate

- Scope: one approved headless window on the retained
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4. The
  fresh quote displayed `$1.59/hour` compute plus the existing approximately
  `$0.04/hour` disk. No Viewer, table/cube task, pre-grasp, gripper, contact,
  hardware, policy, checkpoint, instance creation, resize, or deletion ran.
- Initial merged provenance: `main@7539585`. The first matrix failed closed
  before any Yahboom pose command. Both cases raised
  `TypeError: issubclass() arg 1 must be a class` when a Torch tensor reached
  the installed Warp-backed `ArticulationView.set_dof_actuation_forces`.
  No case JSON was written; the summary correctly selected
  `incomplete_case_matrix`.
- Failure evidence:
  `artifacts/dofbot/gravity_feed_forward_runtime_failure_2026-07-31.json`.
  It binds both retrieved logs and the incomplete matrix contract and records
  which hypotheses were not tested.
- Minimal compatibility repair: branch
  `codex/dofbot-gravity-ff-warp-compat`, commit `1cf25a0`; use the
  non-deprecated `root_view` and native Warp `float32` actuation data plus
  `int32` indices. No controller, trajectory, effort bound, single-factor
  comparison, or acceptance gate changed.
- Repaired command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
    make dofbot-gravity-feed-forward
  ```

- Result: `[MATRIX_EXIT_CODE] 0`, `matrix_complete=true`, decision
  `bounded_gravity_feed_forward_resolves_tracking`.

  | Case | Worst settled error | Worst overshoot | Contact | Result |
  | --- | ---: | ---: | ---: | --- |
  | force `1048/53/100`, FF off | `1.73936°` | `1.74808°` | `0 N` | tracking fail |
  | same drive, bounded gravity FF on | `0.002391°` | `0.03611°` | `0 N` | tracking pass |

- All four treatment poses settled by position difference. Target-buffer
  error stayed below `0.000000854°`; all three required runtime APIs were
  available; all uncontrolled DOFs received zero external actuation. Across
  645 samples, raw and applied gravity effort both peaked at `0.363701`, well
  below the `5.2` bound, with zero clipped samples.
- Established: the remaining isolated gravity-on tracking residual is resolved
  by bounded generalized-gravity feed-forward on the stable force drive.
  Falsified: the earlier `1.73936°` residual is an unavoidable property of the
  pose or target path.
- Not established: task-space pre-grasp, Viewer, contact, grasp, lift, place,
  or real-hardware behavior. The current pre-grasp runner still uses the old
  acceleration `10000/100` scene configuration, so running it unchanged would
  not test the selected actuator contract.
- Success evidence:
  `artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json`, which binds
  the two ignored multi-megabyte case JSON files, both logs, and the matrix
  contract by exact byte size and SHA-256.
- Validation before repaired machine run: `201/201` repository tests, nine
  focused feed-forward tests, targeted Ruff, Python compilation, JSON parsing,
  deterministic plan regeneration, Git LFS checks, remote-command preview,
  and `git diff --check` passed.
- Resource lifecycle: all failed and successful artifacts were retrieved before
  stop. Standard `brev ls --json` reached explicit `STOPPED` at 09:15:35 PDT;
  the instance and persistent disk were retained and no resource was created,
  resized, reset, or deleted.
- Acceptance: **isolated actuator machine gate passed / pre-grasp integration
  pending / pre-grasp machine gate and Viewer blocked**. The next work is
  GPU-free: reuse this exact runtime contract inside the pre-grasp runner and
  fail closed on its API and effort-isolation telemetry. Only after review,
  merge, fresh quote, and approval should the separate headless pre-grasp run.
