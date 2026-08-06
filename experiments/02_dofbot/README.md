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

## Failure-ledger gate

The canonical cross-run index is
[`FAILURE_LEDGER.md`](FAILURE_LEDGER.md). Read it before changing a controller,
scene, simulator setting, measurement, or remote wrapper. Every failed gate,
falsified or partial correction, superseded diagnosis, runtime/telemetry
incompatibility, artifact/transport defect, and paid-window failure must update
that ledger in the same pull request.

The current scientific item is `DF-047`. `DF-046` completed the source-bound
A/B/C matrix: both no-box paths passed within `0.0024 degrees`, while adding
the exact table/cube pair restored a `4.199411-degree` residual. The GPU-free
follow-up found that the historical spawner changed both objects together and
always authored collision. The next paid gate, after merge, fresh quote, and
explicit approval, is therefore one adaptive table/cube/pair, collision-off,
and far-away branch behind a new-source S0 sentinel—not another parameter tune
or integrated Viewer attempt.

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

### Free local pre-grasp scene calibration

The first follow-up keeps the accepted Goal 4 config and machine artifact
immutable. The separate candidate
`configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json` changes scene
positions only:

- table center `(0.00,+0.31,0.06) m`, giving a horizontal top at
  `z=0.08 m` instead of `z=0.12 m`;
- nearest table edge `y=0.16 m` instead of `y=0.10 m`;
- static cube center `(0.00,+0.25,0.105) m` instead of
  `(0.00,+0.18,0.145) m`;
- `Wrist_Twist` approach waypoint `(0.00,+0.25,0.195) m`.

Run the free gate with:

```bash
make dofbot-pregrasp-dry-run
```

The tool verifies the immutable Goal 4 config SHA and all 14 recorded Isaac
machine checks, proves that the table is lower and farther, that the cube rests
on the tabletop with `0.065 m` minimum edge inset, and that the candidate
waypoint remains incremental and inside a conservative radial envelope. The
candidate radius is `0.31706 m`; the recorded neutral `Wrist_Twist` radius is
`0.33865 m`, leaving `0.02159 m`.

That radial check is deliberately not a controller-reuse claim. The accepted
Goal 4 final observation already put one recorded joint at `59.50°`, within
the machine gate's 1° tolerance around the 60° lower safety boundary. The
existing translation-only controller is therefore explicitly **not
certified** for the lower/farther waypoint; pose-aware IK must establish a
safe joint-space solution before remote execution.

The machine-readable report is
`artifacts/dofbot/pregrasp_scene_calibration.json`; the side/top comparison is
`artifacts/dofbot/pregrasp_scene_calibration.svg`. All 20 local checks and all
119 repository tests pass. This is only a necessary geometry gate: the report
explicitly leaves candidate Isaac machine and Viewer acceptance pending and
does not authorize contact or grasping. Pose-aware IK, finger grasp frame,
collision clearance, preferred posture, and trajectory smoothness remain the
next free local design work.

### Pose-aware terminal-finger pre-grasp preparation

The next free gate replaces the `Wrist_Twist`-only position target with a
derived terminal-finger grasp frame. The official asset has no single grasp
center body, so the contract uses:

- origin: midpoint of `Finger_Left_03` and `Finger_Right_03`;
- closing axis: left terminal finger to right terminal finger;
- approach axis: `Wrist_Twist` to the terminal-finger midpoint,
  orthogonalized against the closing axis.

The desired pre-grasp origin is `(0.00,+0.25,0.195) m`, 6.5 cm above the
5 cm cube's top. The desired approach axis is world `-Z`; the desired closing
axis is world `+X`. Position, approach, and closing tolerances are `0.025 m`,
`12°`, and `20°`.

Only `joint1` through `joint4` are available through the accepted Yahboom API
boundary. The runner therefore optimizes position plus approach direction
using the averaged terminal-finger `6x4` link Jacobian and treats closing-axis
alignment as a monitor-only gate. It does not silently command wrist twist,
servo 5, or the gripper. If the fixed closing orientation is incompatible, the
machine gate fails.

The 5 Hz controller adds a preferred `[90,78,78,90]°` posture, `[68,112]°`
command range inside the established `[60,120]°` safe envelope, integer-degree
API quantization, maximum 4° step, 20°/s velocity, and 60°/s² acceleration.
Local signed-distance proxies reject critical body centers approaching the
table or cube. The remote scene enables Isaac contact reporting on all DOFBOT
rigid bodies and rejects force above `0.5 N`.

Run the free local gate with:

```bash
make dofbot-pregrasp-pose-dry-run
make show-dofbot-pregrasp
make show-dofbot-pregrasp-view
```

The first command produces
`artifacts/dofbot/pregrasp_pose_contract.json`; the checked-in artifact passes
21/21 local preparation checks. Deliberate terminal-finger collision, excess
contact force, and reversed fixed-closing-axis probes all fail closed. All 139
repository tests pass, including 27 focused pose/runner tests. The other two
commands print the future remote commands without starting Isaac or Brev.

After branch review and merge, the separately approved paid gate is:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp-view
```

The headless run must pass live asset compatibility, physical prim/static
target, pose, fixed closing-axis, joint margin, velocity, acceleration,
collision proxy, contact reporter, improvement, exact API count, and neutral
reset checks. Viewer acceptance then requires the user to see a smooth
front/up angled approach toward the raised-table candidate, with the gripper
open, cube stationary, and no visible contact. Until both gates pass,
candidate Isaac and visual status remain pending and Goal 5 is not complete.

The first remote candidate was run on 2026-07-29 at commit `05ececc` and
failed closed before Viewer launch. It improved terminal-finger position error
from `0.33035 m` to `0.07212 m`, preserved every motion/contact/API/reset
safety gate, and reported `0 N` maximum contact force. However, the controller
braked at the lower API command margin and did not satisfy the `0.025 m`
position or `12°` top-down approach gates; final approach error was `103.21°`.

The concise failure record is
`artifacts/dofbot/pregrasp_machine_failure_2026-07-29.json`; the full retrieved
machine artifact was 326,627 bytes with SHA-256
`bc0ff9942be17fb542c9b56dc8cd04aa9bf2af4093ec97be4488fb7c34c7b8e5`.
This establishes failure of the current controller path, not global
infeasibility of the pose. The next free task is a local reachable-pose search
over alternate posture branches, followed by safety-preserving pose/scene
recalibration. Do not restart Brev or open the Viewer until that local gate
passes.

The follow-up local gate is now
`make dofbot-pregrasp-reachability`. It fits a planar three-pitch-chain model
to twelve observations from the failed Isaac artifact. Maximum position and
approach residuals are `0.00203 m` and `0.00246°`. It then evaluates all
`226,981` integer-degree physical-envelope combinations and all `91,125`
command-margin combinations, retaining the best candidate from every visible
workspace-front posture branch.

No candidate meets the current `0.025 m` position and `12°` world-down
approach tolerances. More strongly, the continuous orientation lower bounds
are `88.41°` and `112.41°` for the physical and command envelopes. Coupled
position/orientation geometry is also impossible before angle bounds: the
world-down pose requires `0.35791 m` of proximal reach, while the fitted first
two links provide at most `0.19656 m`.

The machine-readable result is
`artifacts/dofbot/pregrasp_reachability.json`. Its search contract passes, but
`current_target_feasible`, `revised_candidate_ready_for_remote_validation`,
`paid_gpu_run_authorized`, and `viewer_authorized` are all false. This rejects
the current pose rather than Goal 5 itself. The next design choice is either
to preserve the current safety envelope and revise the scene/approach pose, or
to establish a separately calibrated wider envelope before searching again.

### Joint-first angled pre-grasp candidate

The safety envelope is preserved. The free follow-up starts from every
integer-degree pitch posture, predicts the terminal-finger midpoint and
approach axis with the calibrated planar model, and derives a compatible cube
and horizontal table from each posture. This avoids guessing another
Cartesian target that the four commanded joints cannot realize.

Run:

```bash
make dofbot-pregrasp-taskspace
make dofbot-pregrasp-pose-dry-run
make show-dofbot-pregrasp
make show-dofbot-pregrasp-view
```

The search evaluates `61^3 = 226,981` physical-envelope postures and
`53^3 = 148,877` candidate-envelope postures. It binds the accepted asset,
machine-passed ActionChunk, rejected world-down result, and calibrated model
by SHA-256. The physical scan proves that a meaningful front/up approach
cannot retain the requested table top at or below `0.12 m`; its minimum is
`0.17945 m` at the zero-margin `[90,60,60,60]°` boundary.

Exactly one posture passes the strict residual-aware filters:

- preferred joint pose: `[90,66,66,66]°`;
- terminal-finger midpoint:
  `(-0.00071,+0.22052,0.28278) m`;
- approach/closing axes:
  `(0,+0.94213,+0.33526)` and world `+X`;
- cube center:
  `(-0.00071,+0.29589,0.28660) m`;
- horizontal table top: `z=0.26160 m`;
- physical/candidate angle margins: `6° / 2°`;
- minimum residual-aware clearance reserve: `0.00415 m`.

The inputs are
`configs/dofbot/pregrasp/goal5_taskspace_search.json`,
`configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json`, and
`configs/dofbot/pregrasp/goal5_angled_pregrasp.json`. The output
`artifacts/dofbot/pregrasp_taskspace_candidate.json` passes all 30 local
checks, and the generalized pose preview passes 21/21 checks. The remote
wrappers now default to this candidate. All 154 repository tests, targeted
Ruff, shell syntax, Git LFS attributes, remote command previews, and
`git diff --check` pass.

Acceptance is **local design passed / Isaac machine pending / Viewer
pending**. This is a no-contact upper-side angled pre-grasp candidate, not
grasp success. A later paid run must still prove live Isaac kinematics,
self-collision/contact gates, command tracking, reset, and user-visible motion
before Goal 5 can complete.

### Angled candidate machine result and direct joint-candidate correction

The first headless run of the joint-first scene used merged
`main@7b4591f` and failed closed. It improved terminal-finger position error
from `0.25660 m` to `0.03382 m`, but did not meet the unchanged `0.025 m`
position gate; its `13.568°` approach error also missed the unchanged `12°`
gate. Closing error was `0.321°`.

All sixteen remaining safety/API/reset checks passed: physical table and static
cube, observed joint envelope, API margin, velocity, acceleration, collision
proxies, no contact, static target, controller improvement, exact `248/248`
official API calls, and neutral reset within `0.0613°`. Maximum contact force
was `0 N`. The Viewer was not opened.

The failure is specific: the scene was derived from candidate
`[90,66,66,66]°`, but Cartesian DLS settled at API command
`[90,65,67,76]°` and observed
`[89.989,65.073,68.603,77.889]°`. The controller traded away from the
selected joint branch. Raising the offline candidate boundary reserve from 2°
to 3° leaves zero candidates, so tightening that margin is not a valid fix.

The local correction makes the control mode explicit. The angled config uses
`validated_joint_candidate`, which smoothly tracks the selected pose through
the same bounded, integer-degree, four-call Yahboom API. The historical
world-down config retains `cartesian_pose_ik`. Cartesian position/axis gates,
the scene, collision/contact checks, command/velocity/acceleration limits,
exact API count, and neutral reset remain unchanged.

Evidence:
`artifacts/dofbot/pregrasp_angled_machine_failure_2026-07-29.json` summarizes
the retrieved 327,197-byte artifact with SHA-256
`396e19b56805f7771aeee284e9722b49be3bf2006c999d42d32baaafc0ecd555`.
The regenerated task-space artifact SHA-binds that failure and passes 33/33
checks; the generalized dry-run passes 21/21; all 155 repository tests,
targeted Ruff, Git LFS checks, remote command previews, and
`git diff --check` pass.

Acceptance is **local correction passed / corrected Isaac machine pending /
Viewer blocked pending machine pass**. Contact and grasp remain unauthorized.
The paid window ran approximately 20:02-21:17 PDT, exceeding its intended
30-minute cap. Stop was requested as soon as a 21:12 clock audit detected the
overrun, and `brev ls --json` later verified explicit `STOPPED`; no resource
was deleted or resized.

### Direct-candidate command-space regression and correction

The corrected direct-candidate controller was remotely tested at merged
`main@150fa5d`. It failed only the unchanged Cartesian position gate:
`0.03243 m > 0.025 m`. Approach and closing errors were `10.397°` and
`0.313°`; all remaining safety/API/reset gates passed with `0 N` contact,
`248/248` official API calls, a static cube, and `0.0689°` neutral-reset
error. The Viewer was not started.

The failure located a more specific controller defect. The configured
candidate was `[90,66,66,66]°`, but the final API command was
`[90,66,68,69]°` and the final observed joints were
`[89.980,66.328,70.529,71.535]°`. A bounded diagnostic that changed the
preferred endpoint to `[90,66,64,64]°` instead stopped at API command
`[90,66,70,67]°`. Lowering the configured target therefore did not
consistently lower the command.

The controller computed the direct-candidate delta from live observed joint
angles while its integer quantizer computed velocity, acceleration, and
braking from the previous API command. Isaac drive tracking lag therefore
mixed observation space and command space. The prior regression checked only
the direction of one float step; it never executed the full quantized sequence
or asserted the final stopped API endpoint.

The local correction on
`codex/dofbot-command-space-tracking-fix` separates those roles:

- direct-candidate motion advances only from the previous API command to the
  configured integer-degree endpoint;
- live observed joints remain authoritative for physical-envelope,
  Cartesian, collision, contact, and target-static gates;
- the machine contract independently requires
  `validated_joint_candidate_command_reached`;
- candidate configs at the command-margin boundary are rejected before Kit
  launch because they cannot retain the existing one-degree braking reserve;
- Cartesian IK retains its observation-feedback path and existing stall gate.

Run the free regression gate with:

```bash
make dofbot-pregrasp-pose-dry-run
make show-dofbot-pregrasp
make show-dofbot-pregrasp-view
```

Evidence:
`artifacts/dofbot/pregrasp_joint_candidate_machine_failure_2026-07-29.json`
binds the two retrieved remote artifacts, while
`artifacts/dofbot/pregrasp_command_space_contract.json` injects the failed
run's tracking-lag neighborhood and reaches a stopped
`[90,66,66,66]°` API endpoint in eight bounded steps. All 22 local contract
checks pass.

Validation: `make test` passes all 159 repository tests, targeted Ruff passes,
the local artifact regenerates byte-identically, both remote wrappers pass
dry-run preview, both new JSON artifacts parse, and `git diff --check` passes.
Full-repository Ruff remains blocked only by the pre-existing unrelated
`tools/collect_environment_info.py:47` line-length finding.

Acceptance remains **local command-space correction passed / corrected Isaac
machine pending / Viewer blocked pending machine pass**. This correction does
not loosen the `0.025 m / 12°` Cartesian gates, authorize contact or grasp,
or claim that local replay is Isaac proof.

### Exact API endpoint passed; simulated joint tracking failed

The command-space correction was remotely tested at merged
`main@54b25ed98d325f5079daf5d34bec3ad1629ee136` with:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
```

The earlier command-space defect is fixed: the controller reached and stopped
at the exact `[90,66,66,66]°` Yahboom API candidate. Isaac nevertheless
settled at observed joints `[90.093,66.987,70.641,69.828]°`, so the maximum
observed/API tracking error was `4.641°`. The Cartesian endpoint improved
`0.25660 -> 0.03213 m` but still missed the unchanged `0.025 m` gate.
Approach and closing passed at `9.465° / 0.412°`; every collision,
static-target, no-contact, API-count, command-margin, and neutral-reset gate
passed with `0 N` contact. The Viewer was therefore not started.

This failure is distinct from the previous one. The final API state is now
correct, while the simulated articulation does not hold that target under
load. The configured stiffness times the measured error is compatible with
effort clipping, but the artifact recorded planned command velocity rather
than actual `joint_vel` and omitted `joint_pos_target`, resolved drive
buffers, and computed/applied torque. It therefore cannot distinguish effort
clipping from target-path, settling, drive, solver, collision, axis, or
mass/inertia causes.

The local follow-up preserves the original effort-100 baseline and the
independent
`final_api_joint_tracking_within_tolerance <= 1°` pre-grasp gate. It adds:

- `configs/dofbot/calibration/goal5_actuator_diagnostic.json`;
- `make dofbot-actuator-calibration-dry-run`;
- `make show-dofbot-actuator-calibration`;
- the future separately approved
  `make dofbot-actuator-calibration` machine matrix.

The matrix uses the same neutral, mid-load, `[90,66,66,66]°` candidate, and
neutral-return poses under three orthogonal cases:

1. gravity on, effort limit 100;
2. gravity off, effort limit 100;
3. gravity on, effort limit 250.

Each pose is dispatched once through sixteen total official API calls per
case. The runner samples every physics step and records the API target, backend
interpolated target, Isaac `joint_pos_target`, observed `joint_pos`, actual
`joint_vel`, resolved stiffness/damping/effort limits, torque buffers when
meaningful, optional PhysX mass/inertia/DOF properties, terminal body
positions, and contact. Missing optional APIs are recorded as null instead of
aborting. Settling requires actual velocity below `0.1°/s` for `0.5 s`; zero
planned command velocity is not accepted as a proxy. The two-second smoothstep
peaks at 18°/s and 36°/s² for the largest transition, preserving the existing
20°/s and 60°/s² bounds.

The matrix decision tree checks contact, settling, target-buffer agreement,
and telemetry/runtime completeness before comparing gravity and effort.
Implicit-actuator torque buffers are approximate PD estimates, not measured
PhysX solver torque. A nonzero gap may show that the software-side estimate
reached its configured clip, but it does not prove physical saturation.
Tracking failure still writes a complete case artifact.
The outer Brev transport exits zero and prints `[MATRIX_EXIT_CODE]` so a
nonzero internal result cannot trigger an automatic paid retry.
The local wrapper then parses that marker and returns nonzero to `make` if the
internal matrix did not complete.

The historical full 327,442-byte artifact remains bound by SHA-256
`50efb65e1b31299e3e39fb517f024b4762ea68773d6c7a58e2a62df6e0d57033`
in
`artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json`.
The deterministic local preparation evidence is
`artifacts/dofbot/actuator_calibration_plan.json`.
All 171 repository tests pass, including synthetic decision branches and
remote preview checks. Targeted Ruff, Python compilation, shell syntax,
deterministic plan regeneration, JSON parsing, and `git diff --check` pass.
`brev ls --json` remained `STOPPED`; no GPU or Isaac runtime was started.

The paid window began at 22:42:05 PDT. Evidence was retrieved before stop,
and `brev ls --json` explicitly returned `STOPPED` at 22:55:05 PDT. No
instance or disk was created, resized, or deleted.

Acceptance is **remote exact API endpoint passed / simulated joint tracking
and Cartesian position failed / isolated actuator diagnostic prepared /
diagnostic matrix and Viewer pending**. The next paid command is the diagnostic
matrix, not pre-grasp. Contact, closing, grasping, lifting, and placing remain
unauthorized.

### Remote actuator diagnostic matrix

The approved 2026-07-30 paid window reused
`isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4, at the
rechecked `$1.58784/hour` compute quote. It ran only the isolated matrix: no
table, cube, camera, Viewer, pre-grasp, contact, gripper, policy, checkpoint,
or real hardware.

The first attempt exposed a runtime compatibility defect after every pose had
executed: an optional PhysX array reached `json.dumps` without conversion and
raised `TypeError: Object of type array is not JSON serializable`. The Isaac
launcher still returned zero, so the absence of artifacts was the only
fail-closed signal. Commit `abd109f` performs tensor/NumPy-to-list
normalization, writes a durable per-case log, and independently requires a
non-empty case artifact. All 171 local tests, targeted Ruff, shell syntax, and
the remote preview passed before resynchronization.

The repaired matrix completed with `[MATRIX_EXIT_CODE] 0`:

| Case | Tracking error | Terminal reported velocity | Target-buffer error | Contact | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| gravity off / effort 100 | `0.00316°` | `0.04567°/s` | `0.000000851°` | `0 N` | tracking pass |
| gravity on / effort 100 | `4.97619°` | `16.34411°/s` | `0.000001271°` | `0 N` | fail |
| gravity on / effort 250 | `4.97619°` | `16.34411°/s` | `0.000001271°` | `0 N` | fail |

The effort-250 case is not a configuration no-op: both the Isaac effort
buffers and PhysX DOF maximum forces are `250`, and the implicit PD estimate
reaches the corresponding software-side clip. Nevertheless, the complete selected sequence of
API target, backend target, Isaac target, observed position, and reported
velocity is identical to gravity-on effort-100. Increasing only
`effort_limit_sim` is therefore falsified as a sufficient fix.

Gravity-off passing establishes that the API/backend/Isaac target path works
and that the failure is load-dependent. The target buffer agrees within
`0.0000013°`, no optional PhysX probes failed, and every case records `0 N`
monitored contact.

One instrumentation problem remains before a drive conclusion is safe. During
the last `0.183 s` of the gravity-on candidate, each observed joint position
varies by at most `0.0000103°`, while the raw Isaac `joint_vel` buffer reports
up to `16.344°/s`. The runtime log also warns that TGS with
`enable_external_forces_every_iteration=False` may produce noisy velocities.
The automatic `settling_or_drive_stability_failure` label is retained as the
matrix output, but raw velocity cannot remain the sole acceptance signal.

The tracked evidence is
`artifacts/dofbot/actuator_calibration_contract.json` plus the reviewed
`artifacts/dofbot/actuator_calibration_result_2026-07-30.json`. The latter
binds all retrieved full JSON/log files by size and SHA-256; the multi-megabyte
raw payloads remain ignored.

Acceptance is **matrix execution complete / gravity dependence established /
effort-250-only fix rejected / raw velocity instrumentation requires
correction / pre-grasp and Viewer blocked**. The next free local step adds
finite-difference position velocity beside raw `joint_vel`, routes material
disagreement as a runtime compatibility failure, and prepares a focused
solver/drive matrix. Another paid run requires review, a fresh quote, and
explicit approval. Stop was requested 20 minutes 24 seconds after start;
standard `brev ls --json` reached explicit `STOPPED` at 08:50:21 PDT after the
asynchronous shutdown and list refresh. The existing instance and disk remain
preserved.

### Position-derived velocity and focused solver/drive preparation

The free local follow-up replays the exact retrieved actuator samples without
reconstructing or modifying them. Source byte counts and SHA-256 values must
match the promoted remote result. A `100 ms` finite difference of observed
joint position is now the physical settling signal; raw `joint_vel` remains a
separate required compatibility signal and disagreement above `1°/s` fails
closed.

The replay passes. Both gravity-on cases settle on all four poses by position
difference with at most `0.041972°/s` derived speed, while raw velocity reaches
`16.363141°/s` and differs by as much as `16.444165°/s`. Their
`4.974117°` position error remains. The gravity-off record ends below the
derived threshold with only `0.085753°/s` mismatch, but is explicitly marked
right-censored because its historical collection stopped before a complete
new `500 ms` derived hold.

The next matrix contains four gravity-on, effort-100 cases:

1. the unchanged TGS baseline;
2. external forces applied on every TGS position iteration;
3. two solver velocity iterations;
4. implicit damping reduced from 100 to 50.

Each step changes exactly one field. Stiffness stays `10000`, position
iterations stay `8`, and effort 250 is not repeated. The command preview and
local plan pass, but `paid_gpu_run_authorized`, `viewer_authorized`, and
`pregrasp_authorized` remain false.

```bash
make dofbot-actuator-velocity-reanalysis
make dofbot-solver-drive-dry-run
make show-dofbot-solver-drive
```

Evidence is
`artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json` and
`artifacts/dofbot/solver_drive_diagnostic_plan.json`. Acceptance is **offline
velocity diagnosis passed / focused matrix prepared / remote Isaac pending /
pre-grasp and Viewer blocked**.

### Solver/drive remote result

The approved headless matrix ran on merged
`main@02f27d259d271a5bb01a9739c1c270db702de9f7` and completed with
`[MATRIX_EXIT_CODE] 0`. The automatic decision is
`external_force_iteration_repairs_velocity_telemetry_only`.

Enabling external-force application every TGS position iteration reduces the
maximum raw/position velocity mismatch from `16.44402°/s` to `0.09921°/s`.
It does not reduce position error: worst-case tracking changes from
`4.97412°` to `5.04065°`. Adding two velocity iterations is materially
identical at `5.04064°`. Damping 50 reaches `4.88333°`, only `0.09079°`
better than baseline and still far outside the one-degree gate.

Every case settles by position difference, matches the target buffer within
`0.0000017°`, and records zero monitored contact. Joint 3 remains the
dominant error at the candidate. Thus the TGS velocity warning is not the
cause of the position error, and neither velocity iterations nor damping 50 is
accepted as a fix.

The reviewed evidence is
`artifacts/dofbot/solver_drive_diagnostic_result_2026-07-30.json`. The raw
case JSON and logs remain ignored but are bound by byte size and SHA-256.
Acceptance is **machine matrix complete / velocity telemetry repair found /
tracking unresolved / pre-grasp and Viewer blocked**. Before another paid
window, audit the official asset's per-joint drive force, axes/transmission,
mass, and inertia with particular attention to joint 3.

### Official drive audit and force-drive diagnostic preparation

The GPU-free audit downloaded NVIDIA's official Isaac 6.0
`Robots/Yahboom/Dofbot/dofbot.usd` to temporary storage only. The source is
104,922,919 bytes with SHA-256
`52c524ebb26c38a3d164daee10f6cac0f15487fce5408a38c0c94199a37f1303`;
it is not committed and does not need a Git LFS rule.

The asset is meter-scaled and Z-up. Controlled joints 1-4 form the expected
serial body chain, every joint uses axis X, and every angular drive is authored
as `acceleration` with uniform stiffness `1048`, damping `53`, maximum force
`5.2`, and zero joint friction. The runtime mass snapshot totals
`1.03481 kg`. Therefore joint 3 remains the largest observed error, but it
does not have a unique official axis, drive type, or tuning.

The audit also corrects a diagnostic interpretation. Isaac Lab implicit
actuator `computed_effort` and `applied_effort` are approximate PD
calculations, not measured PhysX solver torque. The earlier effort comparison
still proves that effort-limit and PhysX maximum-force writes changed and the
trajectory did not; it does not prove actual torque saturation.

The next five-case matrix treats force-drive semantics as a hypothesis:

1. reproduce acceleration drive with current `10000/100/100` runtime tuning;
2. switch only drive type to `force`;
3. restore official stiffness `1048`;
4. restore official damping `53`;
5. restore official maximum force `5.2`.

Every transition changes one field. Gravity, poses, trajectory, external-force
iteration, and solver settings remain fixed. Before motion, the runner reads
back the composed drive type, axis, connected bodies, gains, and maximum force
for joints 1-4 and fails closed on a mismatch.

```bash
make dofbot-drive-model-dry-run
BREV_INSTANCE_NAME=preview-only make show-dofbot-drive-model
```

Evidence is `artifacts/dofbot/asset_drive_audit_2026-07-30.json` and
`artifacts/dofbot/drive_model_diagnostic_plan.json`. Acceptance is
**official-asset audit passed / five-case local plan passed / drive-type
hypothesis unproven / GPU, pre-grasp, and Viewer blocked**. After review,
merge, a fresh quote, and explicit approval, run only:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-drive-model
```

All `185` repository tests, targeted Ruff, Python compilation, shell syntax,
JSON parsing, Git LFS checks, deterministic plan regeneration, and the
headless remote-command preview pass.

The matrix result must be reviewed before adopting a drive configuration. The
selected configuration then has to pass gravity-on calibration and the
headless pre-grasp machine gate. Only those two machine passes authorize the
Viewer.

### Drive-model remote result

The approved headless matrix ran on merged
`main@d2abb247a188c23889778cfdd1f211f2bc8dd1a1` and completed all five
cases with `[MATRIX_EXIT_CODE] 0`.

| Case | Tracking error | Interpretation |
| --- | ---: | --- |
| acceleration / 10000 / 100 / 100 | `5.04065°` | baseline failure |
| force / 10000 / 100 / 100 | `221160.35°` | unstable; rejected |
| force / 1048 / 100 / 100 | `3.22899°` | stable but outside gates |
| force / 1048 / 53 / 100 | `1.73936°` | best stable; tracking fail |
| force / 1048 / 53 / 5.2 | `1.73936°` | identical physical result; fail |

Force semantics with official-scale stiffness and damping therefore explain a
material part of the gravity-on error: the best stable case improves by
`3.30129°` or `65.49%`. It still misses the independent one-degree gate by
`0.73936°`, so it is not adopted for pre-grasp.

The high-gain force case did not suffer missing telemetry; its positions and
position-derived velocities diverged without settling. The machine classifier
incorrectly routed this as `position_velocity_instrumentation_incomplete`.
The local decision now rejects unstable cases separately while continuing the
ladder, yielding `drive_model_ladder_no_resolution`.

The final maximum-force comparison is also decisive. Runtime PhysX values
change from `100` to `5.2`, but all 647 selected physical samples and every
pose summary are identical. That parameter change does not repair tracking in
this runtime.

Reviewed evidence is
`artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json`; the raw
11.7 MB JSON/log set remains ignored and is bound by size and SHA-256. Brev
reached explicit `STOPPED` at `20:05:30 PDT`; no resource was created,
resized, or deleted.

All `187` repository tests, 23 focused tests, targeted Ruff, JSON parsing,
source byte/SHA verification, Git LFS checks, remote-command previews, and
`git diff --check` pass.

Acceptance is **remote matrix complete / force-drive direction materially
improves tracking / no case passes / pre-grasp and Viewer blocked**. The next
work is GPU-free: explain the maximum-force invariance and compare explicit
actuator, gravity-compensation, and runtime joint-frame semantics before
designing another paid run.

### Residual-force semantics audit

The GPU-free audit replays the exact retrieved
`force_damping_53` and `force_authored_tuning` JSON sources after verifying
their promoted byte counts and SHA-256 values:

```bash
make dofbot-residual-force-audit
```

All 647 selected API, backend-target, Isaac-target, observed-position,
raw/derived-velocity, body-position, and contact samples remain identical;
all pose summaries are also identical. The cases ran at 60 Hz. PhysX documents
articulation `maxForce` as a force/torque only when
`eDRIVE_LIMITS_ARE_FORCES` is set and as an impulse otherwise. Under the latter
semantics, `5.2` corresponds to `312` force units per second and `100` to
`6000`. This is the high-confidence explanation for the non-binding limit
change. The recorded USD and tensor telemetry do not directly expose the
runtime articulation flag, so the audit does not claim a direct flag readback.

The residual ranking is now narrower:

- gravity/load is selected: gravity-off effort-100 tracks within `0.0032°`,
  while the matched gravity-on case misses by `4.9762°`; force tuning reduces
  the residual to `1.73936°` but does not remove it;
- a static joint-frame/sign correction is rejected as the primary fix because
  the same joint chain and target-buffer path passes with gravity off;
- a full explicit PD actuator remains a fallback because it adds new
  discrete-time controller dynamics.

The next implementation keeps the stable force `1048/53/100` baseline and
adds bounded PhysX gravity-compensation values as external actuation on
`joint1`-`joint4` only. The future runner must fail before motion unless
gravity-compensation, external-DOF-actuation, and incoming-joint-force APIs are
available; record all compensation, applied effort, incoming force, target,
position, derived-velocity, and contact signals.

Evidence is
`artifacts/dofbot/residual_force_audit_2026-07-30.json`. Acceptance is
**local residual audit passed / gravity feed-forward selected for
implementation / paid GPU, pre-grasp, and Viewer blocked**. After the
implementation is reviewed and merged, a paid run still requires a fresh quote
and explicit approval. Its order is isolated gravity-on `<=1°` calibration,
then the unchanged headless pre-grasp gate, then and only then Viewer
acceptance.

Validation: all `192` repository tests, five focused residual-audit tests,
targeted Ruff, deterministic artifact regeneration, source SHA/size replay,
JSON parsing, Git LFS attributes, and `git diff --check` pass.

### Bounded gravity feed-forward preparation

The selected correction is now implemented as a two-case, headless diagnostic:

1. stable force `1048/53/100` with zero external DOF actuation;
2. the identical case with bounded gravity compensation enabled.

The feed-forward enable flag is the only changed field. Both cases keep
gravity on, use external-force iteration, run the unchanged
`[90,90,90,90] → [90,78,78,78] → [90,66,66,66] → [90,90,90,90]`
trajectory through the Yahboom API, and retain the one-degree tracking gate.
Before any pose command, the runner requires
`get_gravity_compensation_forces`, `set_dof_actuation_forces`, and
`get_link_incoming_joint_force`. Each step reads generalized gravity effort,
clamps only joints 1-4 to `±5.2`, forces all other DOF actuation to zero, then
records the raw/applied effort and controlled-child incoming 6D joint forces.
Missing APIs, wrong shapes, non-finite values, unbounded effort, uncontrolled
DOF actuation, target mismatch, settling failure, or contact fail closed.

```bash
make dofbot-gravity-feed-forward-dry-run
BREV_INSTANCE_NAME=preview-only make show-dofbot-gravity-feed-forward
```

Evidence is `artifacts/dofbot/gravity_feed_forward_plan.json`. All `200`
repository tests, eight focused feed-forward tests, targeted Ruff, Python
compilation, shell syntax, JSON parsing, Git LFS checks, deterministic plan
generation, and the headless remote-command preview pass. `brev ls --json`
reconfirmed the retained `g6.4xlarge` L4 instance `92xbacz46` as `STOPPED`;
no resource was started, created, resized, stopped, or deleted.

Acceptance is **local implementation and safety contract passed / isolated
Isaac machine calibration pending / pre-grasp and Viewer blocked**. After
review and merge, a fresh quote and explicit approval are still required
before `make dofbot-gravity-feed-forward`. A machine `<=1°` pass advances only
to the separate headless pre-grasp gate; Viewer remains third.

### Bounded gravity feed-forward machine result

The approved machine attempt first exercised the fail-closed compatibility
probe on merged `main@7539585`. It correctly stopped before any pose command,
but located a runtime boundary omitted by GPU-free tests: the installed raw
PhysX articulation view uses a Warp tensor frontend, while the runner supplied
Torch tensors to `set_dof_actuation_forces`. Both cases raised
`TypeError: issubclass() arg 1 must be a class`, wrote no case JSON, and the
summary selected `incomplete_case_matrix`.

Commit `1cf25a0` changed only that boundary: it uses `root_view` and native
Warp `float32` actuation data with `int32` indices. The same matrix then
completed with `[MATRIX_EXIT_CODE] 0`:

| Case | Maximum settled error | Maximum overshoot | Contact | Gate |
| --- | ---: | ---: | ---: | --- |
| stable force `1048/53/100`, FF disabled | `1.73936°` | `1.74808°` | `0 N` | fail |
| identical drive, bounded gravity FF enabled | `0.002391°` | `0.03611°` | `0 N` | pass |

All four treatment poses settled by the `100 ms` position-difference signal;
target-buffer error remained below `0.000000854°`. All required APIs returned
finite data. Across 645 treatment samples the maximum raw/applied gravity
effort was `0.363701`, no sample reached the `5.2` clamp, and all uncontrolled
DOFs stayed at zero external actuation.

The reviewed evidence is
`artifacts/dofbot/gravity_feed_forward_runtime_failure_2026-07-31.json` and
`artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json`; together they
bind the failed logs, successful raw case JSON/log files, and both matrix
contracts by exact byte size and SHA-256.

All evidence was retrieved before stop. Standard `brev ls --json` reached
explicit `STOPPED` at 09:15:35 PDT; the existing instance and disk were
retained, and no resource was created, resized, reset, or deleted.

At this machine-result checkpoint, acceptance was **isolated actuator tracking
passed / pre-grasp integration pending / pre-grasp machine and Viewer
blocked**. The then-current pre-grasp runner still configured acceleration
drive `10000/100`; the following section records its replacement with the
accepted runtime.

### Pre-grasp actuator-runtime integration

The GPU-free integration now replaces that blocked path. The pre-grasp runner
loads the accepted calibration config and promoted machine result before Kit,
cross-checks their successful matrix decision, treatment metrics, and exact
force `1048/53/100` runtime, then records both SHA-256 values in its output.
Calibration and pre-grasp import one shared native-Warp implementation, so the
previous Torch-to-Warp boundary cannot diverge between the two runners.

Before the first Yahboom pose, the integrated runner reads back the composed
controlled-joint drives, probes all three required PhysX APIs, and writes zero
external actuation. Every physics step executes in this order:

1. write the interpolated position target;
2. read, clamp, and apply gravity effort only on joints 1-4;
3. step physics;
4. read the controlled child links' incoming 6D forces.

The output retains every feed-forward sample and classifies failures as
actuator/runtime telemetry, joint tracking, contact safety, Yahboom API
accounting, neutral reset, or task-space failure. This prevents another failed
machine attempt from collapsing into an undifferentiated debug loop.

```bash
make dofbot-pregrasp-pose-dry-run
BREV_INSTANCE_NAME=preview-only make show-dofbot-pregrasp
```

Evidence is `artifacts/dofbot/pregrasp_command_space_contract.json`; its local
integration gate passes `27/27`. All `205` repository tests, changed-file
Ruff, Python compilation, shell syntax, JSON generation, Git LFS checks,
remote-command previews, and `git diff --check` pass. Full-repository Ruff has
one pre-existing unrelated long line in `tools/collect_environment_info.py:47`.

Acceptance is **pre-grasp runtime integration passed locally / separate
headless pre-grasp machine gate pending / Viewer blocked**. There are no known
remaining integration bugs from GPU-free validation, but the number of
runtime-only issues is unknowable until the installed Isaac task scene runs.
After review and merge, a fresh quote and explicit approval are required for
`make dofbot-pregrasp`. `make dofbot-pregrasp-view` remains blocked until that
machine artifact passes. Contact, gripper closing, grasp, lift, place, and real
hardware remain out of scope.

### First integrated headless pre-grasp result

The approved headless run used the retained `isaac-launchable-f150a5`
(`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4 at the unchanged live quote of
`$1.58784/hour` plus the existing approximately `$0.04/hour` disk. It synced
merged `main@56fddc5` and ran:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
```

The first fail-closed probe stopped before any Yahboom pose because the
integration compared the official USD drive's authored `maxForce` directly
with the Isaac implicit actuator's runtime effort limit. The exact live values
showed that these are separate layers: all four composed USD drives were
`force`, stiffness `1048`, damping `53`, and `maxForce=5.199999809`; the live
articulation effort-limit buffer was `[100,100,100,100]`. Commit `7ce2276`
therefore keeps the USD type/gain gate and independently checks the runtime
effort buffer. It does not relax a physics or acceptance threshold.

After that repair, the complete controller ran with zero monitored contact and
passed the actuator-evidence, runtime API, finite/bounded feed-forward,
uncontrolled-DOF isolation, collision-clearance, static-target, API-accounting,
command-margin, exact-candidate-command, and neutral-reset gates. Its final
machine result was still a failure:

| Metric | Result | Gate |
| --- | ---: | ---: |
| position error | `0.0318076 m` | `<=0.025 m` |
| joint tracking error | `4.16578 deg` | `<=1 deg` |
| approach error | `7.88737 deg` | pass |
| closing-axis error | `0.339104 deg` | pass |
| maximum contact force | `0 N` | pass |
| neutral reset error | `0.002216 deg` | pass |

The exact final API target was `[90,66,66,66] deg`; observed joints were
`[90.0083,68.5085,70.1658,67.2060] deg`. All 248 expected API calls were
recorded, 900 gravity samples were finite, feed-forward effort peaked at
`0.330320`, and no sample clipped at `5.2`. Commit `fc48a2c` preserves this
complete machine-failure artifact instead of overwriting it with a short
runtime exception record. The retrieved raw artifact is 2,237,400 bytes with
SHA-256 `b970b2e90c90274c86e334a392c15f58fe4de1bd497f410887e38c090230f57b`;
the reviewed concise record is
`artifacts/dofbot/pregrasp_live_actuator_gate_result_2026-07-31.json`.

Comparing that run with the exact accepted calibration payload identifies the
next control defect without another GPU sweep. Calibration sent the candidate
once, held its target, and reached maximum error `0.001261 deg` after
`2.65 s`. Pre-grasp reached the same stopped command at step 8 but, because the
task-space check had not yet passed, sent the same four servo commands again
every `0.2 s` through step 60. Each call reset the smoothstep start to the
current measured position, maintaining a load-dependent lag instead of holding
the completed target. The local follow-up now enters a bounded physics-settle
phase after the exact candidate command and performs no additional Yahboom API
write until success, timeout, or a safety failure. API accounting counts only
actual writes.

All 205 repository tests, the 45 focused pre-grasp/gravity tests, changed-file
Ruff, Python compilation, deterministic `27/27` command-space regeneration,
remote previews, Git LFS checks, and `git diff --check` pass. Acceptance is
**live actuator integration passed / first task run classified / candidate
settle fix passed locally / repaired headless gate pending / Viewer blocked**.
No contact, gripper, target motion, grasp, lift, place, policy, camera control,
or real hardware was authorized. Stop was requested after evidence retrieval;
after a temporarily stale ordinary listing, `brev ls --all --json` confirmed
explicit `STOPPED` at 11:56:36 PDT. The instance and disk were retained.

### Remote process-status hardening before the repaired rerun

The first failed headless probe also exposed an orchestration defect: Isaac
could exit nonzero and print a traceback while the enclosing `brev exec`
reported zero. The machine artifact prevented a false scientific conclusion,
but a shell caller could still see a misleading green Make result.

The pre-grasp wrapper now emits exactly one `[PREGRASP_EXIT_CODE] N` from the
remote shell, separately verifies the Brev transport exit, and accepts only a
single well-formed marker with `N=0`. A nonzero, missing, duplicate, or
malformed marker fails closed. The dry-run path remains display-only. Six
fixture cases, remote command preview, shell syntax, Git LFS checks, and all
205 Python tests pass locally. No GPU or Isaac runtime was used for this
hardening. `brev ls --all --json` re-confirmed the retained L4 instance as
explicit `STOPPED` at 20:43 PDT. The repaired headless rerun and Viewer remain
gated exactly as above.

### No-reissue machine rerun

The merged `main@4b4fc8a` rerun proved that the local settle branch executed as
designed. The candidate trajectory completed at step 8; steps 9-60 advanced
physics for 52 observations without another Yahboom API call. Exact API
accounting was 40/40 rather than the previous 248/248.

That repair was not sufficient. The exact `[90,66,66,66]°` API target settled
at `[89.999642,68.493213,70.177019,67.221305]°`, leaving `4.177019°` maximum
tracking error and `0.0318089 m` position error. Both exceed the unchanged
`1°` and `0.025 m` gates. Approach, closing, collision, zero-contact,
static-target, safe-envelope, gravity, API, and neutral-reset checks all
passed. Feed-forward peaked at `0.330318`, with no sample clipped at `5.2`.

The full retrieved artifact is 2,231,658 bytes with SHA-256
`4674c83d58f187363720741a71b933a205f99c87951191eeb4ca44ce02cd0c3f`;
the concise record is
`artifacts/dofbot/pregrasp_no_reissue_machine_result_2026-07-31.json`.
Python raised `PregraspMachineAcceptanceError`, but `isaaclab.sh` returned zero,
so the first sentinel-only hardening also proved incomplete.

The GPU-free follow-up removes the old output before launch, verifies the new
artifact is commit-matched and machine-passing, and only then permits a zero
sentinel. It also adds per-observation backend target, Isaac
`joint_pos_target`, computed-torque, and applied-torque evidence. Those fields
are the missing discriminator between an API/backend write problem and a
post-write actuator residual. No pose, gain, effort, or acceptance threshold
changes. The real failed artifact is rejected by the semantic verifier;
focused tests pass 14/14, all repository Python tests pass 210/210, and the
27/27 command-space artifact regenerates deterministically. Changed-file Ruff,
Python compilation, shell syntax, remote preview, JSON, Git LFS, and
`git diff --check` pass. The instance was explicitly `STOPPED` at 21:23 PDT;
Viewer remains blocked.

### Target/torque rerun blocked before compute

The first approved attempt to collect the `DF-028` discriminator used only the
retained `isaac-launchable-f150a5` (`92xbacz46`), whose AWS `g6.4xlarge` L4
identity and live `$1.58784/hour` price matched approval. A foreground start
request at 09:55:03 PDT and one detached retry did not move the authoritative
state from `STOPPED`. The shell stayed `NOT READY`; the read-only SSH probe
timed out; and repeated `brev ls --all --json` polls remained stopped. Because
this CLI has previously exposed stale list state, `brev refresh` was run before
the final 10:04:53 PDT poll; the result was still `STOPPED`.

Repository sync, Isaac, `make dofbot-pregrasp`, Viewer, and artifact generation
therefore never started. This attempt makes no claim about command
propagation, live target buffers, torque, tracking, or task-space behavior.
The concise operational record is
`artifacts/dofbot/pregrasp_startup_operational_2026-08-01.json`, indexed as
`DF-029`. `DF-028` remains the unresolved scientific discriminator and Viewer
remains blocked. A future attempt must obtain a fresh quote and approval,
reach both `RUNNING` and shell `READY` after one detached start plus stale-state
refresh, and only then run the unchanged headless command.
A second refresh and delayed-start safety audit at 10:08:11 PDT again returned
explicit `STOPPED`.

### Target propagation passed; measured PhysX effort remains open

The later approved, time-only retry used the same retained instance and the
same `$1.58784/hour` quote. One detached start reached shell `READY`, and the
host GPU probe returned `NVIDIA L4, 23034 MiB`; this resolves the earlier AWS
zone-capacity event as transient without creating or changing infrastructure.

The unchanged `main@d6f5597` headless run generated a fresh artifact. The
final `[90,66,66,66]°` API target reached the backend exactly and live
`joint_pos_target` within `0.000000668°`, but the observed articulation still
ended at `[89.999642,68.493213,70.177019,67.221305]°`. The unchanged
`4.177019°` joint and `0.0318089 m` task-space errors reject API/backend target
loss as the remaining explanation.

The equal `computed_torque` and `applied_torque` buffers peak at `76.4262`, but
Isaac Lab's ImplicitActuator documentation identifies them as approximate PD
torque because PhysX does not expose that torque directly. They are not proof
of measured solver effort. `DF-030` therefore keeps all controls fixed and
makes PhysX `get_dof_projected_joint_forces` the next discriminator.

The same run exposed `DF-031`: `isaaclab.sh` masked the expected acceptance
exception, then the verifier called missing container executable `python3`
and emitted sentinel `127`. The local wrapper now uses the installed
`./_isaac_sim/python.sh`; the runner records projected PhysX joint effort and
fails the telemetry gate if it is unavailable. Both repairs remain remote
pending. The promoted summary is
`artifacts/dofbot/pregrasp_target_torque_discriminator_2026-08-01.json`.
Viewer, contact, gripper closing, grasp, lift, and place remain blocked. The
artifact was retrieved before `brev ls --all --json` confirmed the retained
instance explicit `STOPPED` at 14:44 PDT.

### DF-030 projected-force local contract hardening

The GPU-free follow-up reread all 31 historical ledger entries before changing
the measurement path. It preserves the exact scene, `[90,66,66,66]°` pose,
force `1048/53/100` drive, bounded gravity feed-forward, solver settings, and
acceptance gates. No previously falsified controller or tuning case is
repeated.

Official PhysX tensor documentation refines the measurement boundary:
`get_dof_projected_joint_forces` is the active component obtained by
projecting each link's incoming joint force onto its DOF motion direction. It
is measured joint-force balance, but it is not an isolated sensor for the
implicit drive torque. `DF-032` records this partial semantic result so the
next artifact cannot overclaim what the new number proves.

The runner now requires finite, width-correct projected force and
ImplicitActuator computed/applied PD estimates on every controller
observation. Its machine summary records per-joint final values, signed minima
and maxima, maximum absolute values, and maximum projected-minus-computed and
projected-minus-applied differences. The raw observations and gravity
feed-forward samples remain present, so the next diagnosis can compare the
complete active joint-force balance rather than one final sample.

The remote wrapper also checks that `./_isaac_sim/python.sh` exists and is
executable before semantic verification; a missing interpreter emits sentinel
`126` instead of an ambiguous shell failure. This is local preparation only.
The retained L4 remains stopped, installed-runtime compatibility remains
unverified, and Viewer/contact/grasp remain blocked. Deterministic 27/27
contract regeneration, all 222 repository tests, targeted Ruff, Python
compilation, shell syntax, remote preview, Git LFS, and `git diff --check`
pass.

### DF-032 remote result and single-boundary trajectory preparation

The merged `main@d4da9c0` headless run completed the projected-force
discriminator. Every one of 61 observations contained finite, aligned PhysX
projected force and approximate implicit-actuator PD estimates. The projection
peaked at only `[0.001136,0.505431,0.342836,0.165914]`, while the PD estimate
peaked at `[0.045059,45.798676,76.426231,22.747814]`. That is valid active
joint-force-balance telemetry, but not an isolated drive-torque measurement.
The same loaded residual remained: `4.177019 degrees` joint error and
`0.0318089 m` position error. Target propagation, contact, safety, gravity,
API accounting, and reset all passed; Viewer remains blocked.

The same run proved the installed-Python semantic wrapper: the failed artifact
produced sentinel 1 and nonzero outer Make, resolving `DF-031` through
`DF-033`. Promoted evidence is
`artifacts/dofbot/pregrasp_projected_force_discriminator_2026-08-01.json`.
The retained instance is explicit `STOPPED`; no Viewer ran.

The free post-run audit then found `DF-035`. A 4-degree cubic smoothstep over
200 ms peaks at `30 degrees/s` and `600 degrees/s2`; the old 5-Hz boundary
metadata therefore understated internal motion and falsely passed the 20/60
gate. The runner now reuses the accepted calibration duration and sends the
complete `[90,66,66,66]` pose once over 2000 ms. Its analytic peaks are
`18 degrees/s` and `36 degrees/s2`, and observations no longer cause API
reissue. The dry-run records one candidate command and 12 expected total API
calls. This local correction still requires one headless machine validation
before any Viewer, contact, or grasp attempt.

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

## DF-035 single-boundary machine discriminator

The merged `main@2e7f7aa` run used the retained
`isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4 at the
fresh `$1.58784/hour` quote. The new remote GPU admission gate passed before
Isaac. The only changed scientific factor was the candidate trajectory: one
`[90,66,66,66] / 2000 ms` Yahboom pose boundary replaced the old segmented
200-ms commands. Scene, actuator, feed-forward, solver, safety, and acceptance
contracts stayed fixed.

The machine result failed only
`grasp_origin_reached_pregrasp_position` and
`final_api_joint_tracking_within_tolerance`. The exact API/backend target and
live target buffer passed, but observed joints settled at
`[90.008511,68.467499,70.196145,67.246695] degrees`, leaving
`4.196145 degrees > 1 degree` tracking error and
`0.0318115 m > 0.025 m` position error. This is essentially unchanged from
the prior `4.177019 degrees / 0.0318089 m` result, so `DF-039` falsifies the
trajectory-only hypothesis as a sufficient repair.

All other 35 checks passed: 12/12 API calls, analytic
`18.000943 degrees/s / 36.001886 degrees/s2` peaks inside the unchanged
`20/60` envelope, approach and closing gates, target-buffer alignment,
61/61 projected-force and PD-estimate observations, 900 bounded gravity
samples with no clipping, collision clearance, zero contact, static target,
and `0.002216-degree` neutral reset. The semantic verifier emitted sentinel 1
and outer Make failed as intended. Viewer did not start.

The raw 2,283,434-byte artifact is retained locally at
`artifacts/dofbot/pregrasp_df035_single_boundary_raw_2026-08-01.json`,
SHA-256
`62edc78fa2491ac07670222cac093f92e0e0c90e5974743bd627c68d2fdddbd3`;
the tracked promotion is
`artifacts/dofbot/pregrasp_single_boundary_discriminator_2026-08-01.json`.
The run also exposed `DF-040`: exact comparison with an ideal 90-degree start
would reject the real, self-consistent motion because observation zero was
within `0.0023 degrees`, not byte-identical. The local verifier now binds the
start to observation zero, enforces the one-degree neutral gate, recomputes
all derivatives, and retains the `20/60` safety envelope.

The artifact was retrieved before stop, and `brev ls --all --json` confirmed
the retained instance explicit `STOPPED`; no instance or disk was created,
deleted, resized, or reset. There is no next paid run yet. The next free step
is a controlled offline comparison of the successful isolated calibration
and failed integrated task contexts, followed by one newly named ledger
discriminator. Viewer, contact, gripper, grasp, lift, place, hardware, policy,
and checkpoint remain blocked.

## DF-041/DF-042 offline context-transfer audit

The deterministic audit in
`artifacts/dofbot/pregrasp_context_transfer_audit.json` SHA-binds the accepted
isolated config/result, failed direct integrated result, current shared runtime,
and integrated consumer. It proves the candidate-entry histories differ and
that the historical pass cannot validate the refactored source bundle.

The prepared paid protocol is deliberately fail-fast:

1. A: current shared runtime, original `90 -> 78 -> 66` path, no boxes.
2. B: same runtime and no boxes, direct `90 -> 66` path; run only after A.
3. C: original split path plus the exact static table/cube; run only after A.
4. D: existing DF-039 integrated failure, referenced but never rerun.

Every new artifact carries the exact runtime source bundle and is checked for
commit, config/scene hashes, actuator factors, full pose sequence, telemetry,
scope, and tracking verdict. `make dofbot-pregrasp` and
`make dofbot-pregrasp-view` now fail closed while this evidence is absent.
No GPU or Isaac runtime was started for this audit.

## DF-042 source-bound context-transfer machine result

The approved headless matrix ran on merged `main@4b88d07` using the retained
`isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4 at the
fresh `$1.58784/hour` quote. It executed only A/B/C; existing failed reference
D was hash-bound and not rerun. No Viewer, camera capture, contact task,
gripper command, hardware command, policy, or checkpoint ran.

| Cell | Candidate path | Static scene | Maximum settled error | Result |
| --- | --- | --- | ---: | --- |
| A | `90 -> 78 -> 66` | none | `0.002391 degrees` | pass |
| B | direct `90 -> 66` | none | `0.002211 degrees` | pass |
| C | `90 -> 78 -> 66` | exact table + cube | `4.199411 degrees` | tracking fail |

All three cells passed artifact integrity, source/config bindings, API count,
target-buffer, settling, velocity-consistency, overshoot, runtime API,
bounded-feed-forward, and zero-contact checks. Cell C alone failed the
unchanged one-degree tracking gate at the candidate pose; it returned to
neutral within `0.002212 degrees`. This rejects both current-runtime regression
and candidate-entry history as the remaining primary cause. It localizes the
residual to the static-scene context, not yet to a particular table/cube,
collision, or spawn-side-effect mechanism.

Promoted evidence is
`artifacts/dofbot/context_transfer_matrix_contract.json`. It SHA-binds the
ignored raw A/B/C artifacts (`3,124,556`, `3,091,114`, and `3,261,631` bytes)
and exact current runtime bundle `0aeeb044...`. The reviewed matrix decision is
`static_scene_context_is_causal`.

Acceptance is **current shared runtime passed / direct path passed / static
scene context reproduced the residual / integrated pre-grasp and Viewer still
blocked**. The next work is GPU-free: audit the exact scene-spawn composition
and prepare the smallest table/cube/collision-or-spawn decomposition before
proposing another paid run. Drive, trajectory, API-target, feed-forward, and
acceptance parameters must remain unchanged.

## DF-047 GPU-free adaptive scene decomposition

The offline audit closes the experiment-design gap left by DF-046. The exact
historical helper iterated over table and cube together, constructed
`CollisionPropertiesCfg()` unconditionally, and did not read an independent
collision setting. Therefore DF-046 proves the static-scene family is causal,
but not which object or mechanism is responsible.

The strict config is
`configs/dofbot/calibration/goal5_scene_decomposition.json`. Its ten declared
cells are candidates for one adaptive branch, not a sweep:

1. S0: current-source split path with no scene; fail-fast regression sentinel.
2. T1: near table only with collision. If it fails, run T0 collision-off and
   TF collision-on at a fixed 1.25-meter offset, then stop.
3. If T1 passes, Q1 tests the near cube only. If it fails, run Q0/QF, then stop.
4. If both single objects pass, P1 reproduces the near pair. If it fails, run
   P0/PF, then stop. If it passes, record non-reproduction and stop.

The maximum path contains six cells. Each cell has a 180-second timeout and the
remote matrix has a 1200-second internal deadline. Every cell retains the
split `90 -> 78 -> 66` path, force `1048/53/100`, external-force iteration,
bounded gravity feed-forward, one-degree tracking threshold, and `0.5 N`
contact threshold.

The machine contract requires source/config hashes; authored and runtime prim,
collision, static, transform, and AABB readback; articulation joint/body names,
controlled DOF indices, and PhysX view shape; target/position/velocity/gravity
telemetry; complete contact event counts and actor pairs; and terminal-body-
center/AABB clearance. Analytical clearance and zero monitored contact remain
explicitly insufficient to rule out broadphase, registration, indexing, or
another spawn side effect.

GPU-free command:

```bash
make dofbot-scene-decomposition-dry-run
BREV_INSTANCE_NAME=preview-only make show-dofbot-scene-decomposition-matrix
```

Prepared future command, still blocked on merge, authenticated `brev ls`, a
fresh matching quote/state check, and explicit approval:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
  make dofbot-scene-decomposition-matrix
```

Evidence: `artifacts/dofbot/scene_decomposition_plan.json`. Preparation is
**local passed / paid run unauthorized / Viewer blocked**. Integrated pre-
grasp, contact, closing, grasping, lifting, placing, hardware, policy, and
checkpoint remain out of scope.

## DF-048 machine result: near collision-on table context is causal

The retained `isaac-launchable-f150a5` (`92xbacz46`) matched AWS
`g6.4xlarge`, NVIDIA L4, explicit `STOPPED`, and the refreshed
`$1.58784/hour` quote before the approved start. Remote source was merged
`main@d5191f5`. The exact command was:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
  make dofbot-scene-decomposition-matrix
```

The adaptive branch stopped after four cells, as designed:

| Cell | Static scene change | Maximum settled error | Tracking gate |
| --- | --- | ---: | --- |
| S0 | no table or cube | `0.002390900°` | pass |
| T1 | near table only, collision on | `4.199411370°` | fail |
| T0 | same near table, collision off | `0.002390900°` | pass |
| TF | collision-on table translated `+1.25 m` in world X | `0.002390900°` | pass |

Every artifact passed commit/config/runtime-source integrity and runtime USD
readback. T1 read back collision API
`/World/ReachScene/Table/geometry/mesh`; T0 read back no collision API; TF read
back the expected 1.25-meter translation. All objects remained static. The
articulation stayed at 11 joints and 12 bodies, controlled IDs `[0,1,2,3]`,
with one PhysX articulation view. Target-buffer, settling, gravity feed-
forward, force, API-count, neutral-return, and all diagnostic checks passed.

T1 reproduced the same candidate residual at observed joints
`[90.010134,68.463674,70.199411,67.249789]°` while target-buffer mismatch
stayed below `0.000000852°`. It reported zero contact callbacks/headers and
zero maximum monitored contact force. The nearest measured terminal-body
center was still `0.0473568 m` outside the table AABB. This proxy covers only
the terminal body centers; it does not exclude another robot collider, collider
extent/contact offset, filter, broadphase, or actor-path reporting defect.

Promoted evidence is
`artifacts/dofbot/scene_decomposition_matrix_contract.json`, SHA-256
`b12d64fcf1939de01eab8bf61850387eaf269e898151e2ca08bcf35561fdc1a4`.
It binds ignored raw S0/T1/T0/TF JSON artifacts of `3,126,493`, `3,265,219`,
`3,128,400`, and `3,128,438` bytes by SHA-256. The four raw JSON files and
four complete logs were retrieved and verified locally before shutdown.

Decision: **`near_table_collision_context_is_causal`**. Cube and pair cells
were correctly skipped. This is a meaningful causal localization, not an
integrated pre-grasp pass. `DF-048` requires a GPU-free audit of every
robot/table collider, world bound, contact offset/filter, and contact actor
path before another paid discriminator. Viewer, contact, closing, grasping,
lifting, placing, hardware, policy, and checkpoints remain blocked.
