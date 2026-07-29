# Status

- Updated: 2026-07-29 America/Los_Angeles
- Completed phase: Phase 2 — 27-cell controlled RL study
- Current experiment: Phase 3 / `02_dofbot`; Goal 4 corrected front-side,
  no-contact reaching passed local, remote machine, and user Viewer gates
- Brev instance: `isaac-launchable-f150a5` (`92xbacz46`)
- Instance state: `STOPPED`, verified with `brev ls --json` at 2026-07-29
  08:44 PDT after corrected Goal 4 validation
- Billable GPU compute still running: no
- Remaining resource: 256 GiB persistent disk, approximately `$0.04/hour`
  from the deployment quote
- Deletion status: not requested; instance and disk preserved
- Latest live L4 quote: existing AWS `g6.4xlarge` class was
  `$1.58784/hour` compute; checked 2026-07-29 before restart

## DOFBOT Goal 4 fixed-tabletop reaching gate

- Branch: `codex/dofbot-goal4-jacobian-compat`; corrected remote commit
  `eb7a266`; PR #21
- Historical rear-side remote commit: `d12b987`
- Scope: safe reach/approach/retract only; no target contact, pushing, grasping,
  lifting, placing, gripper command, camera controller input, learning, or real
  hardware
- Scene contract:
  `configs/dofbot/reaching/goal4_fixed_tabletop.json`
- Corrected v2 base-frame contract: world `+Y` is workspace front and world
  `-Y` is the Jetson/electronics rear. The complete official robot asset stays
  fixed.
- Corrected v2 physical composition: collision-enabled static table centered
  at `(0.00, +0.25, 0.10) m`, with top at `z=0.12 m`; collision-enabled static
  5 cm red cube centered at `(0.00, +0.18, 0.145) m` and resting exactly on
  the table; the nearest tabletop edge remains 10 cm in front of the base
- End-effector contract: `Wrist_Twist`; approach waypoint
  `(0.00, +0.18, 0.235) m`, nine centimeters above the cube center
- Corrected v2 scripted comparison: five ActionChunk poses, with the three
  non-neutral poses mirrored around 90° to
  `[90,82,80,82]`, `[90,76,75,79]`, and `[90,82,80,82]`; 20 official
  pose-boundary `Arm_serial_servo_write(id, angle, time)` calls, neutral
  start/end, and 60°-120° safe angles
- State controller: 5 Hz damped-least-squares translation Jacobian, at most 30
  steps, at most 4° per joint per step, same absolute-angle Yahboom API
- Corrected v2 local fail-closed gates: fixed `+Y` work-front and `-Y`
  electronics-rear vectors, rejection of a rear-side table or relabeled
  frame, physical table/cube geometry, static target, keepout, end-effector
  body, controller cadence and safe envelope, Jacobian shape/finite math,
  bounded API output, synthetic pass/failure evaluation, reset, no
  hardware/Isaac use in dry-run, and mirrored Viewer-camera wiring
- Corrected v2 local validation: all 112 repository tests pass, including 15
  focused Goal 4 tests, Git LFS checks, and remote command previews; targeted
  Ruff, shell syntax, the local dry-run, and both reach command previews also
  pass
- Corrected v2 remote Viewer evidence:
  `artifacts/dofbot/reaching_viewer_contract.json`, cycle 27, SHA-256
  `87faa5f892553c093dc190e331967990676672e4b383587e21a298cd8446d893`
- Machine gates: physical prims and static target present,
  live asset compatibility, angle envelope, four-centimeter table clearance,
  at least three-centimeter distance improvement for both the scripted and
  state-based approaches, final state distance at most four centimeters, exact
  API call count, neutral reset within one degree, the fixed front/rear frame,
  and table/cube placement on the physical work side
- Viewer contract: 20-second neutral connection hold followed by a loop of the
  scripted comparison and state-based approach
- Corrected v2 remote machine result: **passed**. All fourteen checks passed;
  the headless scripted distance improved from `0.18821 m` to `0.07579 m`,
  the state controller improved from `0.21226 m` to `0.02037 m`, minimum
  wrist/table clearance was `0.13258 m`, 52/52 official API calls were
  accounted for, and neutral reset error was `0.2295 deg`
- Corrected v2 Viewer machine result: **passed**. The downloaded cycle-27
  artifact again passed 14/14 checks; its state-controller final distance was
  `0.02037 m`, minimum clearance was `0.13258 m`, and neutral reset error was
  `0.2028 deg`
- Corrected v2 Viewer result: **passed for safe no-contact reaching**. The user
  confirmed that the table/cube and Jetson/electronics are on opposite sides
  and that the arm approaches in the correct direction. The open gripper and
  static cube were visible, and four screenshots were reviewed but not
  committed.
- Motion-quality limitation: the user correctly observed only roughly
  30°-45° of required visible bending and an awkward motion. The target/table
  are close and high, the controlled point is `Wrist_Twist` rather than the
  fingertip grasp frame, and the 5 Hz translation-only damped-least-squares
  controller does not constrain gripper orientation or prefer a natural elbow
  posture. These are expected baseline limitations, not evidence of grasp
  readiness.
- Current acceptance: **local passed / corrected remote machine passed /
  corrected user Viewer passed**. Goal 4 is complete for safe, policy-free,
  no-contact reaching only.
- Next free local gate: recalibrate table height and target reach distance,
  define a fingertip/grasp pose frame, and design pose-aware IK with preferred
  posture and smoother velocity/acceleration before any contact, pushing,
  grasping, or placing experiment.
- Compute lifecycle: the existing instance was started after the unchanged
  `$1.58784/hour` quote was verified. Stop was requested at approximately
  08:35 PDT after artifact retrieval and human review; Brev reported
  `STOPPING` during asynchronous cleanup and terminal `STOPPED` at 08:44 PDT.
  The instance and persistent disk were retained; neither was deleted or
  resized.

## DOFBOT Goal 3 camera gate

- Branch: `codex/dofbot-camera-contract`
- Official camera prim retained:
  `/World/envs/env_0/Dofbot/link4/Camera`; the baseline sets
  `CameraCfg.spawn=None` rather than creating a replacement sensor prim
- Input contract:
  `configs/dofbot/camera/goal3_onboard_rgb.json`
- Baseline output: RGB only, `640x480`, `torch.uint8`, `NHWC`, one camera
  instance; no depth, segmentation, CV model, policy, or checkpoint
- Timing contract: `update_period_s=0.1`, nominally 10 Hz in simulation time.
  This is an explicit simulator observation rate, not a claim about the
  unresolved physical camera model, exposure, transport latency, or measured
  hardware FPS.
- Deterministic static scene: a red cube, green cylinder, and blue cuboid in a
  world-fixed optical calibration plane `0.32 m` in front of the settled
  neutral camera, with `0.08 m` lateral spacing. The objects intentionally
  float above the robot; this validates camera geometry and dynamic binding,
  not a physically realistic tabletop scene.
- Planned remote inspection: authored focal length, horizontal and vertical
  aperture, aperture offsets, clipping range, focus distance, f-stop, derived
  field of view, world transform, ROS/OpenGL pose, and the effective intrinsic
  matrix
- Planned machine artifacts:
  `artifacts/dofbot/camera_contract.json` and
  `artifacts/dofbot/camera_rgb.png`; the PNG is covered by Git LFS
- Machine gates: original prim is a `UsdGeom.Camera`, sensor initializes,
  five distinct frames advance at 10 Hz simulation time, every tensor is
  non-empty/non-constant `1x480x640x3 uint8`, all three target centers project
  inside the image, the fixed `link4`-to-camera extrinsic round-trips within
  tolerance, the applied camera world pose matches that extrinsic, the camera
  pose changes with `link4`, and the PNG is saved with a SHA-256
- Local validation: `make test` passed all 97 tests; targeted Ruff, Python
  compilation, and `git diff --check` passed
- Remote static sensor facts on Isaac Sim `6.0.1`: the official prim is a
  `UsdGeom.Camera`; the sensor initializes; RGB is
  `torch.uint8[1,480,640,3]`; five frames advance at the exact configured
  `0.1 s` simulation cadence; the effective intrinsic matrix has
  `fx=fy=732.9993`, `cx=320`, and `cy=240`
- Remote binding result at `dbd09a7`: the official camera remained the sensor
  prim, while the explicit adapter followed live `link4` motion. Maximum
  dynamic translation was `0.065636 m` and maximum dynamic rotation was
  `57.4071 deg`; maximum applied position/orientation errors were
  `1.46e-8 m` and `1.12e-5 deg`.
- Rejected diagnostic: a 180-degree optical-frame flip made all target centers
  project inside the image but rendered five all-zero frames because the view
  pointed into the robot body. This is not a valid camera calibration and was
  removed from the current branch.
- Local remediation: the runner now calibrates one fixed
  `T_link4_camera` from the official neutral pose, computes
  `T_world_camera = T_world_link4 * T_link4_camera`, and calls the Isaac
  Camera world-pose API with the OpenGL convention before each rendered
  capture and Viewer step. The same path records calibration, applied-pose,
  and dynamic-motion errors in `camera_contract.json`. Isaac Lab 3.0's public
  `(x,y,z,w)` quaternion boundary is explicitly converted to the internal
  scalar-first transform representation; the adapter does not create a
  replacement camera or change the official optics.
- Current acceptance: **complete**. All machine checks passed, including
  non-constant RGB, exact 10 Hz simulation cadence, three in-frame target
  centers, fixed-extrinsic round-trip, applied-pose accuracy, and dynamic
  camera motion. At 2026-07-28 22:13 PDT the user confirmed the onboard view
  contained the red cube, green cylinder, and blue cuboid, then switched to
  Perspective and confirmed their expected world-relative placement above the
  moving DOFBOT.
- Machine evidence: `artifacts/dofbot/camera_contract.json`; captured RGB:
  `artifacts/dofbot/camera_rgb.png` through Git LFS.
- Compute lifecycle: stop requested immediately after visual acceptance;
  terminal `STOPPED` was verified with `brev ls --json` at 22:22 PDT.
  Instance and persistent disk were retained, with no deletion or resize.

## DOFBOT Goal 1 machine result

- Git source at remote sync: `f9a44ee`
- Environment: Isaac Launchable `3.0.0-beta2-post1`, Isaac Sim `6.0.1`,
  1x NVIDIA L4
- Official USD:
  `Robots/Yahboom/Dofbot/dofbot.usd`
- Resolved source:
  `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0/Isaac/Robots/Yahboom/Dofbot/dofbot.usd`
- Robot/articulation root prim: `/World/envs/env_0/Dofbot`
- Articulation: initialized, fixed base, 11 joints, 12 bodies
- Onboard camera prim: `/World/envs/env_0/Dofbot/link4/Camera`
- Actuator groups: `front_joints`, `joint3_act`, `joint4_act`
- Machine acceptance: passed; every required contract check is `true`
- Machine-readable evidence: `artifacts/dofbot/asset_contract.json`
- Asset contract SHA-256:
  `1c0d806e4c61206355bddea738481496c45a98d789b5f64f269ec1d3f574a2b2`
- Viewer process: reached `Simulation App Startup Complete` and `app ready`
  with the Kit visualizer and WebRTC extension
- User visual result: passed at 2026-07-26 22:34 PDT; the user confirmed the
  stationary green DOFBOT in the secure Viewer
- Scope audit: no joint motion, RGB tensor capture, policy, checkpoint, PPO,
  SFT, or CV pipeline was run

## DOFBOT Goal 2 result

- Branch: `codex/dofbot-goal2-validation`
- Remote source: `c151777`
- Environment: Isaac Launchable `3.0.0-beta2-post1`, Isaac Sim `6.0.1`,
  1x NVIDIA L4
- Controlled joint set: `joint1`, `joint2`, `joint3`, `joint4`; these are the
  four actuator-backed arm joints with recorded finite limits
- Maximum command: `±5°` (`±0.0872665 rad`) around each recorded default
- Required target-to-limit margin: at least `10°`; the recorded contract leaves
  approximately `85°` from each extreme target to the corresponding limit
- Sequence: default hold, one six-second sinusoid and one-second settle per
  joint, eight-second multi-joint wave, three-second reset hold
- Headless duration: `41` seconds; Viewer mode adds a 30-second connection hold
  and repeats complete cycles so the user cannot miss the motion
- Fail-closed local checks: missing/renamed joints, sentinel limits, insufficient
  range, command above `5°`, unaccepted/nonofficial Goal 1 input, live-contract
  drift, non-finite samples, limit margin, single-joint isolation,
  inactive-joint drift, bidirectional excursion, and final reset error
- Machine thresholds: at least `±2.5°` observed excursion, at most `1°`
  inactive-joint error, at most `1°` active-joint overshoot, at least 90%
  command/observation sign agreement, at least `1°` per joint in the
  simultaneous wave, and at most `1°` final reset error
- Compatibility: one-robot articulation/physics targets used CPU because the
  installed Isaac runtime exited during the first step with CUDA targets; the
  L4 still rendered the secure Viewer
- Machine acceptance: passed; all 11 contract checks are true
- Sign agreement: `40/40` samples (`1.0`) for each of the four joints
- Observed single-joint deltas:
  - `joint1`: `[-5.00°, 5.00°]`
  - `joint2`: `[-5.34°, 5.40°]`
  - `joint3`: `[-5.56°, 5.87°]`
  - `joint4`: `[-5.07°, 5.33°]`
- Maximum inactive-joint error: below `1°`; maximum reset error:
  approximately `0.16°`
- Machine-readable evidence: `artifacts/dofbot/motion_contract.json`
- Motion contract SHA-256:
  `6107ea36dd81c848889c05a6413196d4e873f0cd44f407415bb82302c60d3cab`
- Viewer acceptance: six complete cycles reported `machine_passed=True`; the
  stop request interrupted cycle seven
- User visual result: passed at 2026-07-27 19:54 PDT; the user confirmed
  visible small-amplitude movement and rocking/wave behavior. The subtle
  appearance is expected from the intentional `±5°` safety limit.
- Local visual evidence: the supplied 8.875-second screen recording was
  reviewed but not committed
- Scope audit: no camera tensor, policy, checkpoint, PPO, SFT, CV pipeline,
  or real hardware command was used
- Compute lifecycle: stop requested immediately after the user visual gate;
  terminal `STOPPED` verified at 20:04:45 PDT. The instance and persistent disk
  were retained.
- Goal 2 status: complete; machine and visual gates passed

## DOFBOT simulator/hardware API bridge

- Public compatibility API: Yahboom's documented
  `Arm_serial_servo_write(id, angle, time)` and
  `Arm_serial_servo_read(id)`
- Normalized core: named `joint1` through `joint4` positions in radians plus
  `duration_ms`
- Simulator backend: the Goal 2 Isaac runner now calls the vendor-shaped API,
  which delegates through `DofbotArm` before setting articulation targets
- Hardware backend: translates the same command to Yahboom's documented
  `Arm_serial_servo_write(id, angle, time)` and reads with
  `Arm_serial_servo_read(id)`
- Documented candidate mapping: `joint1` through `joint4` map to servo IDs
  `1` through `4`; zero radians maps to the documented 90-degree centered pose
- Local dry-run: 411 trajectory samples at 10 Hz produced 1,644 single-servo
  calls; all mapped angles stayed in `[85°, 95°]`
- Safety boundary: physical direction and per-device offsets are not yet
  calibrated; the real backend refuses reads and writes while
  `hardware_verified` is false
- Runtime scope: local pure Python only; no GPU started and no real hardware
  command sent

## DOFBOT ActionChunk v1 configured-motion result

- Validation source: `main@ce3f8eb438cc6969b61fccfde4f6b648da3a2253`
- Input contract:
  `configs/dofbot/motions/safe_api_wave.json`
- Command schema: complete absolute angles for servo IDs `1` through `4`,
  expressed in integer degrees, plus per-pose movement and hold durations
- Observation rate: `10 Hz`; in the current local revision only pose boundaries
  dispatch `Arm_serial_servo_write(id, angle, time)`, once per controlled servo
- Original remote-tested profile: `[85°, 95°]`, at most `5°` between
  configured poses, 9 seconds, 90 complete-pose samples, and 360 calls
- Original machine result: all six checks passed; maximum checkpoint error
  `0.667°`, maximum observed excursion `5.430°`, and final neutral error
  `0.076°`
- Original visual result: failed. The user saw the repeated motion but judged
  it too subtle and closer to rocking than a clear bend.
- First visible-profile remote result (`83f24c6`): all six machine checks
  passed after reserving one degree for tracking overshoot. The 12.4-second
  sequence recorded 124 samples and made 496 official calls; maximum checkpoint
  error was `0.866°`, maximum observed excursion `15.175°`, and final neutral
  error `0.114°`. Contract SHA-256:
  `2af0a94931ebd8c580611584a91ff4252742953723fc813672a85fc5fe93346b`.
- First visible-profile visual result: failed. The user saw more range, but
  rejected the slow stair-step motion, residual shaking, and insufficiently
  decisive bend. At least cycles 1 through 13 each reported
  `machine_passed=True`; this is still not a visual pass.
- Accepted profile: every pose contains all four servos, stays within
  `[60°, 120°]`, changes no servo by more than `30°`, starts and ends at
  `[90°, 90°, 90°, 90°]`, and completes in 5.6 seconds. The base targets
  `±20°`; the other joints target `±28°`, leaving two configured degrees inside
  the envelope.
- Dispatch model: five poses produce only 20 official calls (one per
  servo per pose), while 56 independent 10 Hz observations remain available.
  The Isaac-only backend models `duration_ms` with a physics-rate smoothstep;
  the application layer no longer replays 100-millisecond waypoint calls.
- Local acceptance: 71 total Python tests, remote-command previews, targeted
  Ruff, shell syntax, and `git diff --check` passed
- Final machine evidence: `artifacts/dofbot/motion_config_contract.json`;
  SHA-256
  `8a9da487d8eae33be56398f17616a1ffa1204ac809f3c6f51d64d68b2f929ea5`
- Final machine result: all six checks true; 56 observations, 20 official API
  calls, maximum checkpoint error `1.243°`, maximum observed excursion
  `29.319°`, and final neutral error `0.141°`
- Viewer result: `Simulation App Startup Complete`; at least 15 complete
  cycles reported `machine_passed=True`, and cycle 16 started before stop
- User visual result: passed at 2026-07-28 19:25 PDT. The user confirmed two
  obvious, substantially larger main motions with much smoother transitions.
  Small motion between the main poses remains noted as neutral-return behavior
  plus possible actuator settling; future task-specific motion may use a larger
  validated workspace.
- Scope: no camera capture, policy, checkpoint, `Arm_Lib` import, or
  real-hardware command
- Current result: complete. The final pose-boundary revision passed both the
  machine and user Viewer gates; earlier failed profiles remain immutable
  historical evidence.
- Final compute lifecycle: paid window started at 19:18:06 PDT; stop requested
  at 19:25:41 PDT after evidence retrieval; terminal `STOPPED` verified at
  19:33 PDT. No instance or disk was deleted.
- 2026-07-28 compute lifecycle: existing instance started at 08:20:57 PDT;
  stop requested immediately after the failed visual gate; terminal `STOPPED`
  verified at 08:40 PDT. No instance or disk was deleted.
- Latest paid window: started at 22:47:04 PDT; stop requested at 23:14:41 PDT
  within the 30-minute cap. Brev remained in `STOPPING` after a second
  idempotent stop request and reached terminal `STOPPED` at 23:23:08 PDT.

### 2026-07-27 remote validation window

- Approved target: reuse only `isaac-launchable-f150a5` (`92xbacz46`), AWS
  `g6.4xlarge`, NVIDIA L4; no instance creation, resize, reset, or deletion
- Paid-window start: 18:06:06 PDT
- Remote source after sync: `main@e7307b8`
- Sync initially stopped on the untracked Goal 1
  `artifacts/dofbot/asset_contract.json`. Its SHA-256 matched the committed
  contract, and a byte-identical backup was retained at
  `/workspace/goal1-evidence/asset_contract.1c0d806e4c61206355bddea738481496c45a98d789b5f64f269ec1d3f574a2b2.json`
  before retrying the sync.
- Safety stop: at 19:05:57 PDT the elapsed paid window was already about
  59 minutes 51 seconds, beyond the approved 30-minute cap. The run was
  stopped immediately before `make dofbot-motion`.
- Machine result: not run; no `motion_contract.json` was produced
- Viewer result: not run; no visual claim was made
- Final resource state: `STOPPED`, verified with `brev ls --json`; instance and
  persistent disk retained
- Next gate: obtain a fresh quote and approval, then run the already-synced
  headless command before opening the Viewer

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

Keep the Brev instance stopped and review/merge PR #21 after its corrected v2
evidence update. Before another paid run, do the free local design work for the
next task contract: choose a less trivial table height and cube distance,
define the grasp frame at the fingers rather than `Wrist_Twist`, and add
orientation, preferred-posture, collision, and smoothness constraints. Goal 4
does not authorize contact or grasping; those require a new explicit machine
and Viewer gate.
