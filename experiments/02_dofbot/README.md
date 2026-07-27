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

Status: **in progress**

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

### Goal 2 — Hard-coded, safe joint motion

Status: **planned; do not execute during Goal 1**

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

### Goal 3 — Read the onboard camera

Status: **planned; do not execute during Goal 1**

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
