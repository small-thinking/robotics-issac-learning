# Roadmap

Each phase ends in a reproducible artifact and evaluation gate. Moving forward
is based on evidence, not only on a convincing Viewer clip.

## Project objective

Build from simulator fundamentals toward a camera-closed-loop Yahboom DOFBOT
that can perform measurable tabletop reaching and manipulation in simulation
and, behind explicit safety gates, on the user's Jetson Nano robot. The project
will establish asset, action, camera, data, and evaluation contracts before
choosing a learning method. Existing CV models are the default first perception
baseline; PPO, imitation learning, SFT, VLA post-training, and agentic planning
are introduced only where the task evidence justifies them.

## Phase 0 — Visible simulator loop (complete)

- Provision one stoppable L4 instance with explicit cost approval.
- Compare random behavior with an official pretrained skrl PPO policy.
- Record the exact software image, checkpoint, fixed-seed metrics, and visual
  confirmation.
- Stop GPU compute without deleting the persistent disk.

Acceptance evidence: on `Isaac-Cartpole-v0`, the official checkpoint reached
268.88 mean episode steps and 22/25 time-limit episodes versus 188.44 and 0/25
for random. The user confirmed the trained pole was almost continuously
balanced.

## Phase 1 — Reproduce PPO from scratch (one-seed MVP complete)

Goal: prove that our own training run, not a downloaded checkpoint, reaches the
same behavior.

1. Pin the same Launchable image and task: `Isaac-Cartpole-v0`.
2. Capture the resolved environment and skrl PPO config before training.
3. Evaluate random policy with the existing 25-episode fixed-seed protocol.
4. Train one seed headlessly with 4096 vectorized environments, using the
   installed manager-based task's official PPO config rather than carrying over
   Direct-task rollout, normalization, reward-scale, or learning-rate settings.
5. Evaluate every retained checkpoint on the same task and seeds.
6. Play only the best qualifying checkpoint in the secure Viewer.
7. Repeat with two more training seeds after the one-seed MVP passes.

One-seed acceptance gates:

- mean episode length at least 250 steps;
- at least 20/25 episodes reach the time limit;
- mean reward greater than zero;
- checkpoint provenance points to the new local training run;
- visually stable behavior confirmed in the secure Viewer.

The target is equivalent behavior, not identical weights or an identical
learning curve. The seed-42 run passed with mean episode length `269.44`,
`22/25` time-limit episodes, positive mean reward, local provenance, and user
visual confirmation. The remaining robustness check is to repeat unchanged
training with two additional seeds.

Before the seed repetitions, evaluate the retained numbered checkpoints to
produce a fixed-seed learning curve. Plot mean balance seconds and time-limit
success against training transitions. This is a follow-up measurement, not a
reason to revoke the completed one-seed acceptance gate.

### What 4096 parallel environments means

It is 4096 independent simulator states sharing one policy, not a batch of 4096
pre-existing examples and not 4096 separately trained models. With the
manager-based skrl rollout length of 16, one collection cycle yields
`4096 x 16 = 65,536` transitions. PPO computes returns/advantages along each
environment's time axis with termination masks, flattens the transitions,
shuffles them into minibatches, and applies all gradient updates to one shared
actor-critic.

## Phase 2 — Controlled RL understanding

- Run a shared-baseline, one-factor-at-a-time study over observation
  information, cart-velocity reward, action authority, and training
  termination.
- Screen all nine configurations with training seed 42 and checkpoint learning
  curves, then confirm final policies with seeds 7 and 123.
- Evaluate final checkpoints for 30 seconds using fixed environment IDs and
  common canonical termination semantics.
- Measure upright robustness, pole/cart motion, action/effort, and failure
  composition rather than relying on task reward or Viewer impressions.
- Record every planned, successful, partial, and failed run with immutable
  manifests, raw episode rows, derived tables, and checksums.
- Publish a paper-style report with individual training seeds, mean ± SD,
  paired effects, representative traces, trade-off plots, and limitations.

The locked matrix and report contract are in
`docs/PHASE2_STUDY_PROTOCOL.md`. Phase 2 ends when every plotted value is
regenerable from saved data and the study gives an evidence-based reason either
to refine one controller or move to Franka state-based manipulation.

## Phase 3 — DOFBOT asset and control foundations

The detailed first-stage contract lives in
`experiments/02_dofbot/README.md`.

1. Load NVIDIA's official DOFBOT USD and inspect its articulation, joint
   limits, body ordering, and onboard camera prim. This goal is policy-free.
2. Drive each arm joint with small, hard-coded position targets and verify
   axis, sign, limits, and reset behavior.
3. Render and save an onboard RGB observation from a deterministic test scene.
   The strict RGB-only config, three-object calibration scene, explicit
   `link4` binding, timing contract, and artifact schema passed both remote
   machine and user Viewer gates.
4. Expose the vendor-shaped single-servo API over one backend-neutral
   named-joint core. The documented `joint1`-through-`joint4` to servo-ID
   mapping, local dry-run bridge, and fail-closed JSON ActionChunk compiler are
   implemented and passed Isaac machine and Viewer validation. Physical
   direction and zero-offset calibration remain a separate fail-closed
   real-hardware gate.
5. Establish scripted and state-based reaching baselines before adding vision
   or choosing a learning algorithm. The corrected physical-front,
   collision-enabled tabletop, static cube, scripted comparison,
   damped-least-squares controller, Yahboom API boundary, and fail-closed tests
   passed local, remote machine, and user Viewer gates for safe no-contact
   reaching. Scene calibration and posture-aware pose control are required
   before contact or grasping.
6. Establish a no-contact terminal-finger pre-grasp pose before any grasp
   attempt. The first lower/farther, world-down candidate passed preparation
   but failed the remote pose gates. The evidence-calibrated local planar model
   fits the recorded Isaac path within 2.03 mm and exhaustively rejects the
   target across both the physical and API-margin angle spaces; its coupled
   wrist anchor also exceeds the unbounded proximal-chain reach by 16.13 cm.
   A follow-up joint-first search preserves the established physical and
   machine-validated angle envelopes, rejects the requested low table, and
   produces one residual-aware angled candidate at `[90,66,66,66]°` with a
   `0.26160 m` table top. Two remote attempts then separated Cartesian IK
   branch drift from a direct-candidate command/observation state mix. A third
   remote attempt proved the corrected command path reaches the exact stopped
   `[90,66,66,66]°` API endpoint, but the implicit actuators settled as much
   as `4.64°` away and left `0.03213 m` Cartesian error. The completed
   three-case matrix now records target, drive, torque, contact, and physics
   telemetry every step. Gravity-off effort-100 passes with `0.0032°` maximum
   error; both gravity-on effort-100 and effort-250 follow an identical
   selected target/position/velocity sequence and miss by `4.976°`, even
   though the effort-limit and PhysX maximum-force writes change from 100 to
   250. The implicit actuator's applied-effort field is a PD estimate, not
   measured solver torque. This establishes load dependence and falsifies
   effort 250 alone as a fix. Nearly stationary
   final position samples disagree with raw TGS `joint_vel`. The GPU-free
   finite-difference velocity contract and focused four-stage solver/drive
   design passed. The remote matrix repairs the raw velocity mismatch when
   external-force iteration is enabled, but leaves `4.883°-5.041°` tracking
   error across all tested solver/damping settings. The completed official-USD
   audit finds uniform X-axis acceleration drives with authored
   `1048/53/5.2` tuning on joints 1-4, so joint 3 has no unique axis or drive
   tuning. The completed five-case matrix rejects the old high-gain force drive
   as unstable and shows that official-scale stiffness/damping reduce the best
   stable error from `5.04065°` to `1.73936°`. Changing runtime maximum force
   from `100` to `5.2` leaves all selected physical samples identical. No case
   passes. The completed GPU-free residual-force audit explains that invariance
   at high confidence through non-binding impulse-limit semantics: at 60 Hz,
   `5.2` corresponds to `312` force units per second if the articulation force
   flag is absent. The runtime flag itself was not directly recorded. The same
   target/frame path passes at `0.0032°` with gravity off, so a static
   joint-frame correction is rejected as the primary fix. The bounded
   gravity-compensation feed-forward implementation on the stable force
   `1048/53/100` baseline now passes the isolated machine gate. Its first
   attempt failed before motion at a Torch-to-Warp raw-setter boundary; the
   native-Warp repair preserved every experimental control. The repaired
   treatment reaches `0.002391°` worst settled tracking error versus
   `1.73936°` for the matched baseline, with zero contact, zero clipping, and
   maximum applied compensation `0.363701`. The actuator hypothesis is now
   accepted. GPU-free integration of this exact runtime contract into
   pre-grasp now passes: the machine evidence and config are SHA-bound, the
   live drive and three APIs are probed before motion, the native-Warp setter
   is shared with calibration, and failures are classified in the artifact.
   The separate single-boundary headless run reproduced the approximately
   4.2-degree integrated residual. The completed GPU-free audit then corrected
   the protocol comparison: the old isolated candidate used a 12-degree
   `90 -> 78 -> 66` entry, while the failed integrated run used direct
   24-degree `90 -> 66`; the old artifact also lacks a current shared-runtime
   source bundle. The completed source-bound matrix reproduces both split and
   direct paths within `0.0024 degrees` without boxes, while adding only the
   exact static table/cube context restores a `4.199411-degree` residual.
   Runtime and path are now rejected as primary causes; static-scene
   composition is causal but still requires a GPU-free one-factor
   decomposition before another paid run. Viewer, wrist
   twist, gripper closing, target motion, contact, and grasp success remain
   unauthorized.

## Phase 4 — Demonstrations and imitation learning

- Collect or import a small, versioned demonstration set.
- Validate observation/action alignment and episode boundaries.
- Train behavior cloning, then ACT or Diffusion Policy.
- Evaluate task success and characterize failures, not only training loss.

## Phase 5 — Vision and multimodal policies

- Add calibrated RGB observations and a deterministic data pipeline.
- Compare frozen visual features with end-to-end visual policies.
- Add language task descriptions only after state and vision baselines are
  reliable.

## Phase 6 — Lightweight VLA post-training

- Fine-tune a small open VLA or action head on the validated demonstration
  schema.
- Measure closed-loop success, robustness, latency, and distribution shift.
- Publish checkpoint cards and evaluation provenance to Hugging Face only after
  local artifact semantics are stable.

## Phase 7 — Failure-driven improvement

- Cluster rollout failures and turn them into targeted data or environment
  interventions.
- Retrain with curated failures, corrective demonstrations, or carefully gated
  RL post-training.
- Keep a held-out scenario suite to detect regressions.

## Phase 8 — Optional real-robot bridge

- Choose low-cost hardware only after the simulated manipulation policy and
  safety envelope are measurable.
- Add teleoperation, emergency-stop, rate/force limits, calibration, and
  sim-to-real validation before autonomous execution.
