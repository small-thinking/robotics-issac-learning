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
