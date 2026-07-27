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
current control or the servo's internal feedback loop.

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

Status: **local harness validated; remote machine and visual gates pending**

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

The motion artifact can pass only the machine gate. Goal 2 remains incomplete
until the user confirms the visible axis/sign of all four joints, the slow
multi-joint wave, and return to the default pose. No remote motion was executed
during the local preparation.

### Goal 3 — Read the onboard camera

Status: **planned; out of scope for Goal 2**

First use the camera prim discovered in Goal 1. If the asset camera cannot
produce an Isaac Lab tensor, attach an Isaac Lab `CameraCfg` to the same
physical camera link and document that adaptation.

Place a simple colored target in front of the robot, switch the Viewer to the
onboard perspective, and save one RGB frame plus shape/dtype/prim metadata.
Depth, segmentation, feature extraction, and CV training are out of scope.

Acceptance requires a non-empty, non-constant RGB tensor whose saved image
matches the secure Viewer perspective.

## Later milestones

1. Define the simulated-joint to vendor-servo angle mapping.
2. Establish scripted and state-based reaching baselines in simulation.
3. Evaluate a state-based controller under fixed initial conditions.
4. Execute a few safety-reviewed hard-coded poses on the real DOFBOT.
5. Add an off-the-shelf detector and camera-closed-loop reaching.
6. Compare scripted control, PPO, and imitation learning only when the task and
   data contract make that comparison meaningful.
7. Add language-conditioned skills or VLA post-training only after the
   low-level closed loop is reliable.

The older
[`OmniIsaacGymEnvs-DofbotReacher`](https://github.com/j3soon/OmniIsaacGymEnvs-DofbotReacher)
project is a design reference, not the runtime dependency. It used RL-Games
PPO with state observations and joint-position targets; its sim-to-real bridge
mapped those targets to servo angles. This stage makes no claim that its policy
or old OmniIsaacGymEnvs code is compatible with the current Isaac Lab stack.
