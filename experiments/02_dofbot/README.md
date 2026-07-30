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
Implicit-actuator torque buffers that are zero or unavailable are explicitly
marked non-evidence. When meaningful buffers are nonzero, applied effort at
least 98% of the configured limit plus a computed/applied gap becomes direct
saturation evidence. Tracking failure still writes a complete case artifact.
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
