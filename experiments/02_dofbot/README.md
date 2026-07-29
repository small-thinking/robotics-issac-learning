# 02 — DOFBOT: from official asset to camera-closed-loop control

This stage replaces the generic Franka-first manipulation step with the
Yahboom DOFBOT that can later be connected to the user's Jetson Nano hardware.
The near-term work is deliberately policy-free: first establish a trustworthy
asset, action, and camera contract; only then choose a controller or learning
algorithm.

## Long-term objective

Build a reproducible path from the official simulated DOFBOT to a
safety-gated real robot that can use camera feedback for simple tabletop
reaching and manipulation. The first perception baseline will reuse an
off-the-shelf CV model. PPO, imitation learning, SFT, VLA post-training, and
agentic task planning remain optional later choices rather than assumptions in
the infrastructure.

The control boundary is the vendor's servo API: software may choose sequences
of target joint angles and durations, but it does not assume access to motor
current control or the servo's internal feedback loop. Application code can
use the same official-shaped single-servo method in simulation and on the
physical-arm backend; neither path exposes its underlying runtime directly.

## First stage: asset, motion, and camera

### Goal 1 — Load and inspect the official USD

Status: **complete**

Load NVIDIA's `Robots/Yahboom/Dofbot/dofbot.usd` as one Isaac Lab
articulation. Do not load a policy, checkpoint, task reward, or learning
framework.

Record a machine-readable asset contract containing:

- resolved USD source and robot prim;
- ordered body and joint names;
- physical joint-position limits and default pose;
- actuator groups configured by the current Isaac Lab example;
- articulation-root, USD joint, and onboard-camera prim paths.

Acceptance requires an initialized fixed-base articulation with the cataloged
11 joints, 12 bodies, at least one articulation root, and at least one onboard
camera prim. The stationary green robot must also be visible in the secure
Viewer before the goal is marked complete.

Transferable commands:

```bash
make show-dofbot-inspect  # preview the exact simulator command
make dofbot-inspect       # headless load + machine-readable contract
make dofbot-view          # stationary robot in the secure Viewer
```

Expected evidence:

```text
artifacts/dofbot/asset_contract.json
artifacts/dofbot/viewer.log
```

#### Verified machine result — 2026-07-26

The policy-free inspector ran on the retained AWS `g6.4xlarge` L4 instance
against Isaac Launchable `3.0.0-beta2-post1` / Isaac Sim `6.0.1`. The remote
source was Git commit `f9a44ee`.

- Official asset:
  `Robots/Yahboom/Dofbot/dofbot.usd`
- Resolved asset:
  `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0/Isaac/Robots/Yahboom/Dofbot/dofbot.usd`
- Robot and articulation-root prim: `/World/envs/env_0/Dofbot`
- Initialized articulation: yes; fixed base: yes
- Joint count: 11; body count: 12
- Onboard camera prim: `/World/envs/env_0/Dofbot/link4/Camera`
- Configured actuator groups: `front_joints`, `joint3_act`, `joint4_act`
- Machine acceptance: all five checks passed
- Contract artifact: `artifacts/dofbot/asset_contract.json`
- Contract SHA-256:
  `1c0d806e4c61206355bddea738481496c45a98d789b5f64f269ec1d3f574a2b2`

The ordered joint names are:

```text
joint1
joint2
joint3
joint4
Wrist_Twist_RevoluteJoint
Finger_Left_01_RevoluteJoint
Finger_Right_01_RevoluteJoint
Finger_Left_02_RevoluteJoint
Finger_Right_02_RevoluteJoint
Finger_Left_03_RevoluteJoint
Finger_Right_03_RevoluteJoint
```

The ordered body names are:

```text
base_link
link1
link2
link3
link4
Wrist_Twist
Finger_Left_01
Finger_Right_01
Finger_Left_02
Finger_Right_02
Finger_Left_03
Finger_Right_03
```

Every default joint position is `0` radians. `joint1` through `joint4` each
report limits `[-1.5707999468, 1.5707999468]` radians.
`Finger_Left_03_RevoluteJoint` reports
`[-2.4260077477, 3.7350046635]` radians. The other six joints report Isaac's
floating-point unbounded sentinel
`[-3.4028234664e38, 3.4028234664e38]`; later motion work must not interpret
that sentinel as a safe physical range.

The static Viewer reached `Simulation App Startup Complete`, `app ready`, and
registered the Kit visualizer and WebRTC extension. At 2026-07-26 22:34 PDT,
the user confirmed that the green DOFBOT was visible and stationary in the
secure Viewer. Goal 1 therefore passed both its machine and human gates. No
joint target, image tensor, policy, checkpoint, or learning code was executed.

### Goal 2 — Hard-coded, safe joint motion

Status: **complete — remote machine and user visual gates passed**

Starting from the recorded joint ordering and limits:

1. hold the default pose;
2. move one arm joint at a time with a small `±5°` sinusoid;
3. confirm the visible axis and sign of each commanded joint;
4. run one slow multi-joint wave;
5. return to the default pose.

The controller will send joint-position targets directly. It will not use PPO,
inverse kinematics, a downloaded checkpoint, or the old all-ones dummy action
from the DOFBOT Reacher repository.

Acceptance requires every selected joint to move on the intended axis, remain
inside a documented safety margin, and return to its starting pose.

The local harness deliberately controls only `joint1` through `joint4`. These
are the four actuator-backed arm joints whose recorded position limits are
finite (`±90°`). Wrist and finger joints remain uncommanded because most of
their USD limits are floating-point unbounded sentinels, not trustworthy
physical safety limits.

The fixed headless sequence lasts 41 seconds:

1. hold the all-zero default for two seconds;
2. run one six-second `±5°` sinusoid on one joint while the other three hold
   zero;
3. settle at zero for one second and repeat for all four joints;
4. run an eight-second, smoothly enveloped multi-joint wave;
5. hold the zero reset target for three seconds.

The plan fails closed before simulation if a controlled joint is missing or
renamed, its limit is a sentinel, the Goal 1 contract was not accepted or does
not name NVIDIA's official DOFBOT USD, the live asset differs from the recorded
contract, the command exceeds `5°`, or an extreme target would leave less than
`10°` to a limit. Machine acceptance additionally requires at least `±2.5°`
observed motion in each single-joint segment, no more than `1°` drift in an
inactive arm joint, no more than `1°` active-joint overshoot, at least 90%
command/observation sign agreement, finite samples inside the safety envelope,
at least `1°` observed motion per joint with at least two joints moving
simultaneously during the wave, and reset error no greater than `1°`.

Local and preview commands:

```bash
make show-dofbot-motion       # finite headless machine run
make show-dofbot-motion-view  # 30-second connection hold, then repeated cycles
make dofbot-api-dry-run       # encode the plan as official Yahboom API calls
make test                     # pure safety and remote-command contracts
```

The remote commands, reserved for a separately approved paid window, are:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-motion
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-motion-view
```

Expected machine evidence:

```text
artifacts/dofbot/motion_contract.json
artifacts/dofbot/motion_viewer.log
```

The motion artifact can pass only the machine gate. Goal 2 also requires the
user to confirm visible safe motion in the secure Viewer.

An approved remote attempt on 2026-07-27 synced the existing instance to
`main@e7307b8`, but stopped before `make dofbot-motion`: after resolving a
fail-closed checkout conflict around the untracked Goal 1 contract, the paid
window had already exceeded its 30-minute maximum. The original contract was
hash-verified and retained under `/workspace/goal1-evidence/`; no motion
artifact or Viewer result was produced. `brev ls --json` then confirmed the
instance `STOPPED`. This event is an infrastructure-window abort, not machine
or visual evidence for Goal 2.

The fresh approved window on 2026-07-27 reused only
`isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4. The
remote repository ran `codex/dofbot-goal2-validation@c151777` with Isaac
Launchable `3.0.0-beta2-post1` and Isaac Sim `6.0.1`.

Two narrow compatibility fixes were required. Isaac exited during the first
physics step when this single articulation's target tensor used the CUDA
device, so the one-robot articulation/physics target was moved to CPU while
the L4 continued rendering the Viewer. The evaluator also excluded only the
initial `hold_default` settling samples from the command-envelope comparison;
those samples remain recorded and continue to be checked for finiteness and
joint-limit margin.

The canonical machine command passed:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-motion
```

`artifacts/dofbot/motion_contract.json` records all eleven machine checks as
true. Every joint followed the commanded sign in all 40 comparisons. The
single-joint observed ranges were approximately `[-5.00°, 5.00°]` for
`joint1`, `[-5.34°, 5.40°]` for `joint2`, `[-5.56°, 5.87°]` for `joint3`, and
`[-5.07°, 5.33°]` for `joint4`. Maximum inactive-joint error stayed below
`1°`, the wave moved every joint, and maximum reset error was approximately
`0.16°`. The downloaded artifact SHA-256 is
`6107ea36dd81c848889c05a6413196d4e873f0cd44f407415bb82302c60d3cab`.

The secure Viewer then repeated the same sequence. Six complete
Viewer cycles reported `machine_passed=True`. At 19:54 PDT the user confirmed
visible small-amplitude DOFBOT movement and the rocking/wave behavior. The
subtle appearance is expected because the safety contract intentionally limits
commands to `±5°`. An 8.875-second screen recording was reviewed locally but
was not committed. The machine contract independently verifies each controlled
joint's direction, wave excursion, and final reset. No camera tensor, policy,
checkpoint, learning algorithm, or real hardware command was used.

The stop request was sent immediately after the visual gate. At 20:04:45 PDT,
`brev ls --json` confirmed `STOPPED`; the instance and persistent disk were
retained.

#### Shared simulator/real-arm control API

The Goal 2 runner now sends every target through
`YahboomServoApiAdapter.Arm_serial_servo_write(id, angle, time)`. That adapter
normalizes the vendor call to four named positions in radians plus
`duration_ms`. The Isaac backend translates the normalized command to the
already validated articulation position target. A physical backend delegates
it to `Arm_Lib`; reads use the matching `Arm_serial_servo_read(id)` shape.

Yahboom's official documentation establishes that the bottom servo is ID 1,
IDs increase upward, servos 1 through 4 correspond to the first four arm
joints, and 90 degrees is the centered/upright example pose:

- [control one servo](https://www.yahboom.net/public/upload/upload-html/1705545949/Control%20single%20servo.html)
- [read one servo](https://www.yahboom.net/public/upload/upload-html/1705545963/Read%20servo%20current%20position.html)
- [control all servos](https://www.yahboom.net/public/upload/upload-html/1768386858/Control%20All%20Servos.html)
- [ROS control bridge](https://www.yahboom.net/public/upload/upload-html/1768353104/Robotic%20Arm%20ROS%20Control.html)
- [MoveIt joint/servo ordering](https://www.yahboom.net/public/upload/upload-html/1713873254/MoveIt%20control%20the%20real%20machine.html)

The current candidate conversion is
`servo_angle_deg = 90 + degrees(sim_joint_rad)`, mapping `joint1` through
`joint4` to servo IDs 1 through 4. A full 10 Hz dry-run of the 41-second Goal 2
plan produced 411 samples and 1,644 official single-servo calls. Every servo
angle stayed in 85 through 95 degrees. The six-servo call is deliberately not
used because servo 5 (wrist) and servo 6 (gripper) are outside the validated
simulation contract.

This proves the software boundary and command translation, not the physical
sign and zero-offset calibration of the user's individual arm. The real
`Arm_Lib` backend therefore rejects both writes and reads while
`hardware_verified` is false. Before first hardware motion, each servo must be
calibrated one at a time at low amplitude, the direction/offset must be
recorded, and the calibration must be explicitly marked verified.

#### ActionChunk v1 — configured scripted motion

Status: **complete; pose-boundary API dispatch passed machine and Viewer
acceptance**

`configs/dofbot/motions/safe_api_wave.json` is the first versioned motion input.
It contains five complete absolute poses for servo IDs 1 through 4. The first
`±5°` Viewer profile looked like subtle rocking. A later `±14°` profile passed
all machine checks, but the user rejected its slow, stair-step, shaking motion.
The root cause was architectural: the compiler replayed four vendor-shaped API
calls at every 10 Hz observation sample instead of issuing one timed command
per pose.

The accepted revision separates those boundaries. Five poses compile to
20 calls shaped as `Arm_serial_servo_write(id, angle, time)`, exactly one per
servo per pose. The Isaac backend models the specified movement duration at
physics rate with smoothstep interpolation; 10 Hz samples are observations,
not extra application commands. The 5.6-second profile uses `[60°, 120°]` as
its fail-closed envelope, moves the base `±20°`, moves the other controlled
joints `±28°`, and leaves two configured degrees for dynamic overshoot. The
sequence still starts and ends at `[90°, 90°, 90°, 90°]`.

Transferable commands:

```bash
# Local schema, safety, and API-call compilation only
make dofbot-motion-config-dry-run \
  MOTION=configs/dofbot/motions/safe_api_wave.json

# Remote commands: use only after a fresh quote and explicit approval
BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
  make dofbot-motion-config \
  MOTION=configs/dofbot/motions/safe_api_wave.json

BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
  make dofbot-motion-config-view \
  MOTION=configs/dofbot/motions/safe_api_wave.json
```

The Isaac runner validates the config before starting Kit, verifies the live
asset against the Goal 1 contract, executes each pose boundary through the
Yahboom-compatible API, and records target and observed angles. Machine
acceptance checks the sample contract, finite observations, the safe envelope,
configured-pose tracking, visible non-neutral excursion, and final neutral
reset. The Viewer repeats the same 5.6-second sequence after a 30-second
neutral connection hold.

The JSON file is an action input, not a machine result. Local compilation does
not prove Isaac execution or visual motion. In the 2026-07-27 paid window, the
original small-amplitude config passed all six Isaac machine checks with a
maximum observed excursion of `5.43°` and a final neutral error of `0.076°`.
The user saw the repeated sequence but rejected the amplitude as too subtle, so
the first visual gate failed. The immutable result is preserved as
`artifacts/dofbot/motion_config_small_amplitude_2026-07-27.json`; the revised
`±14°` profile then passed all six machine checks on 2026-07-28, but the user
rejected its slow, shaking motion. The pose-boundary dispatch revision then
passed all six machine checks on `main@ce3f8eb`: 56 observations, 20 official
API calls, `29.319°` maximum observed excursion, `1.243°` maximum checkpoint
error, and `0.141°` final neutral error. The user confirmed two clearly larger,
much smoother main motions in the Viewer. Small between-pose motion remains
documented as the deliberate neutral return plus possible actuator settling.
The immutable result is
`artifacts/dofbot/motion_config_contract.json`; the hardware backend remains
disabled.

### Goal 3 — Read the onboard camera

Status: **complete; explicit link4-camera binding passed machine and Viewer
gates**

The baseline reuses the exact camera prim discovered in Goal 1:
`/World/envs/env_0/Dofbot/link4/Camera`. It binds `CameraCfg` with
`spawn=None`, so it does not silently replace the camera or overwrite the
official USD optics. Only if this binding fails in the installed runtime may a
separate adapter camera be considered, and that would require an explicit
contract change.

The strict input is
`configs/dofbot/camera/goal3_onboard_rgb.json`:

- one authored onboard camera;
- RGB only at `640x480`;
- a `0.1 s` update period, or nominal 10 Hz in simulation time;
- three world-fixed optical-plane diagnostics: a red cube, green cylinder,
  and blue cuboid.

The three shapes and colors make orientation, mirroring, cropping, field of
view, and basic color failures visible without introducing a CV pipeline. They
are spawned once in a plane `0.32 m` in front of the settled neutral camera,
with `0.08 m` lateral spacing. Their actual world centers and projected pixel
centers are recorded in the result. They intentionally float above the robot,
so this sparse scene is a camera-geometry fixture, not domain randomization, a
tabletop claim, or a finished photorealistic environment.

The sensor's conceptual inputs are scene radiance, the link-mounted camera
pose, authored USD optics, and simulation timing. Its Goal 3 output is
`rgb: torch.uint8[1, 480, 640, 3]` in `NHWC` RGB order. The 10 Hz setting is
our reproducible simulator observation contract, not an unverified claim about
the physical Yahboom camera. Hardware resolution/FPS, exposure, rolling
shutter, transport latency, lens distortion, and color response remain unknown
until the physical camera is identified and measured.

The machine run is:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-camera
```

It must read and preserve the camera's authored focal length, apertures,
aperture offsets, clipping range, focus distance, f-stop, local-to-world
transform, ROS/OpenGL frame poses, effective intrinsic matrix, five distinct
frame summaries, simulation-time cadence, and raw/PNG hashes. The immutable
outputs are `artifacts/dofbot/camera_contract.json` and
`artifacts/dofbot/camera_rgb.png`.

The secure visual run is:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-camera-view
```

It binds the Viewer to the same onboard camera prim and keeps the static view
alive. Acceptance requires all machine checks to pass and the user to confirm
that the Viewer shows the same red cube, green cylinder, and blue cuboid as the
saved RGB PNG. Depth, segmentation, feature extraction, CV training, arm
motion, policies, checkpoints, and real hardware are out of scope.

Final local preparation passed all 97 repository tests plus targeted Ruff, Python
compilation, shell syntax, remote-command preview, Git LFS, and diff checks.
The first remote window confirmed the expected RGB tensor shape, dtype,
intrinsics, advancing frames, and 10 Hz simulation-time cadence. It also found
that the `CameraCfg(spawn=None)` sensor pose remained fixed at its neutral USD
pose while accepted ActionChunk poses moved the PhysX articulation. Waiting a
full sensor update period did not change that result. A static Viewer would
therefore not demonstrate an onboard view changing with the arm and was not
started.

A 180-degree optical-axis flip was tested and rejected: although its geometric
projection placed all target centers inside the frame, the camera looked into
the robot body and returned five all-zero RGB frames. The current direction is
now implemented locally as an explicit dynamic pose synchronizer. It derives a
fixed camera-to-`link4` extrinsic at neutral, computes
`T_world_camera = T_world_link4 * T_link4_camera` from the live articulation,
and drives the original sensor through Isaac's public world-pose API in the
OpenGL convention before every capture and Viewer step. Isaac Lab 3.0's
public `(x,y,z,w)` quaternion order is converted explicitly at the boundary
to the scalar-first order used by the pure transform math. The contract names
this as adapter behavior and records calibration, desired/actual pose error,
and observed dynamic motion rather than claiming automatic prim following.
Pure transform, strict config, machine-gate, and runner-wiring tests passed
locally. The remote run at `dbd09a7` then passed every machine check: five
non-constant `uint8[1,480,640,3]` RGB frames arrived at exact `0.1 s`
simulation intervals; all three target centers projected inside the image;
maximum camera motion across accepted ActionChunk poses was `0.065636 m` and
`57.4071 deg`; and maximum applied binding error was `1.46e-8 m` and
`1.12e-5 deg`. At 2026-07-28 22:13 PDT the user saw the three targets in the
onboard view, switched to Perspective, and confirmed the corresponding
world-fixed fixture above the moving DOFBOT. Goal 3 therefore passed both
machine and visual gates. A realistic tabletop composition remains a later
physical-mount/joint-calibration task.

### Goal 4 — Fixed-tabletop reaching baseline

Status: **corrected front-side v2 passed local, remote machine, and user Viewer
gates for safe no-contact reaching**

Goal 4 replaces the floating camera-calibration fixture with the first
physically composed task scene:

- an explicit base-frame contract: world `+Y` is workspace front, world `-Y`
  is the Jetson/electronics rear, and the complete official robot asset stays
  fixed;
- a `0.50 x 0.30 x 0.04 m` collision-enabled static tabletop centered at
  `(0.00, +0.25, 0.10) m`, whose top is at world `z=0.12 m` and whose near
  edge remains outside a `0.10 m` robot-base keepout;
- one collision-enabled static red `0.05 m` cube centered at
  `(0.00, +0.18, 0.145) m`, so its bottom rests exactly on the table;
- a `Wrist_Twist` approach waypoint at `(0.00, +0.18, 0.235) m`, nine
  centimeters above the cube center.

This is reaching, not manipulation. The cube remains world-fixed, the gripper
stays open and uncommanded, and the baseline must not touch, push, grasp, lift,
or place an object. The physical robot backend, onboard RGB controller input,
policy, checkpoint, PPO, and VLA are also excluded.

The strict input is
`configs/dofbot/reaching/goal4_fixed_tabletop.json`. It contains two
comparisons:

1. a five-pose ActionChunk scripted approach/retract sequence whose three
   non-neutral poses are `[90,82,80,82]`, `[90,76,75,79]`, and
   `[90,82,80,82]`; it compiles to exactly 20 pose-boundary calls shaped as
   `Arm_serial_servo_write(id, angle, time)`;
2. a 5 Hz state controller that reads the live `Wrist_Twist` position and
   translational Jacobian, computes a damped-least-squares joint delta, clamps
   each step to at most `4°`, and sends the resulting absolute 60°-120°
   servo-angle target through the same Yahboom API.

Local preparation and command previews:

```bash
make dofbot-reach-dry-run
make show-dofbot-reach
make show-dofbot-reach-view
```

After a fresh quote and explicit paid-window approval, the remote gates are:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-reach
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-reach-view
```

The headless result is
`artifacts/dofbot/reaching_contract.json`. Corrected v2 machine acceptance
requires the recorded Goal 1 asset to match the live articulation; the table,
static cube, and `Wrist_Twist` body to exist; the frame to remain `+Y`
work-front and `-Y` electronics-rear; the table and cube to remain in the
declared work-front half-plane; the cube target to remain world-fixed; every
observed angle to remain inside the safe envelope; the wrist to stay at least
four centimeters above the tabletop; both the scripted and state-based
approaches to improve distance by at least three centimeters; the state
controller to finish within four centimeters of the approach waypoint; the
official API call count to match exactly; and the arm to return to within one
degree of neutral.

The Viewer waits 20 seconds at neutral and then repeats the scripted comparison
and state-based approach. Visual acceptance requires the user to see the table
and cube, both approaches, an open gripper, a stationary cube, and the final
neutral reset.

The historical rear-side remote run at commit `d12b987` passed all eleven
machine checks.
The state controller reduced the approach-waypoint distance from `0.20660 m`
to `0.02035 m`; the scripted baseline improved by `0.13493 m`; minimum
wrist/table clearance was `0.12693 m`; all 48 Yahboom-shaped calls were
accounted for; and neutral reset error was `0.6012 deg`. The immutable Viewer
artifact is `artifacts/dofbot/reaching_viewer_contract.json`.

The separate human gate did not pass. The user saw the arm make the intended
safe approach without contact, but correctly identified that the tabletop and
target were on the same visible side as the Jetson/electronics carrier. The
config parser had forced the table to world `-Y`, reusing the horizontal side
of Goal 3's camera optical plane as if it were the robot's physical front.
Goal 3 explicitly made no tabletop or physical-mount claim, so that inference
was invalid.

The corrected v2 preparation does not rotate the complete robot asset or its
Jetson carrier. It declares `+Y` as physical work-front and `-Y` as
electronics-rear, moves the table and cube to `+Y`, mirrors the accepted
non-neutral poses around 90°, mirrors the default Viewer camera, and rejects a
rear-side workspace or relabeled frame before Isaac can launch. All 112 local
tests, including 15 focused Goal 4 tests, the pure dry-run, Ruff, shell syntax,
and both remote command previews pass. No GPU or real hardware was started.

This local result did not reuse the rear-side v1 machine pass. The corrected
state controller therefore received a fresh remote machine and Viewer run at
commit `eb7a266` on 2026-07-29. Both headless and downloaded cycle-27 Viewer
artifacts passed all fourteen checks. In the headless run, scripted distance
improved from `0.18821 m` to `0.07579 m`, state-controller distance improved
from `0.21226 m` to `0.02037 m`, minimum wrist/table clearance was
`0.13258 m`, 52/52 official API calls matched, and neutral reset error was
`0.2295 deg`. The Viewer artifact has SHA-256
`87faa5f892553c093dc190e331967990676672e4b383587e21a298cd8446d893`.

The user confirmed that the table/cube and Jetson/electronics are on opposite
sides and that the arm bends toward the corrected work side. The gripper
remained open and the cube remained static. Goal 4 therefore passes for safe,
policy-free, no-contact reaching.

This result is not grasp readiness. The user observed that the table and cube
are close and high enough to require only roughly 30°-45° of visible bending,
and that the movement looks awkward. That behavior is consistent with a 5 Hz
translation-only damped-least-squares controller targeting `Wrist_Twist`: it
does not constrain gripper orientation, define a fingertip grasp frame, or
prefer a natural elbow posture. Before contact or grasping, locally
recalibrate table height and cube distance, define the finger grasp pose, and
add pose-aware IK, preferred-posture, collision, and smoothness constraints.

## Later milestones

1. Physically calibrate and verify the candidate simulated-joint to
   vendor-servo angle mapping.
2. Extend accepted reaching to contact-aware push and then grasp/place, each
   behind separate collision, gripper, and task-success contracts.
3. Execute a few safety-reviewed hard-coded poses on the real DOFBOT.
4. Add an off-the-shelf detector and camera-closed-loop reaching.
5. Compare scripted control, PPO, and imitation learning only when the task and
   data contract make that comparison meaningful.
6. Add language-conditioned skills or VLA post-training only after the
   low-level closed loop is reliable.

The older
[`OmniIsaacGymEnvs-DofbotReacher`](https://github.com/j3soon/OmniIsaacGymEnvs-DofbotReacher)
project is a design reference, not the runtime dependency. It used RL-Games
PPO with state observations and joint-position targets; its sim-to-real bridge
mapped those targets to servo angles. This stage makes no claim that its policy
or old OmniIsaacGymEnvs code is compatible with the current Isaac Lab stack.
