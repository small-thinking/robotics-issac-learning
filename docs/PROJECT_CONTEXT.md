# Project Context

The user has strong machine-learning and PyTorch experience and is learning
robotics through simulation-first experiments.

The initial workflow is cloud-based and visually inspectable. Codex orchestrates
Brev and Isaac through CLI tools; the user intervenes only for account or billing
approval and visual validation.

The long-term target is robotics ML focused on:

- VLA post-training;
- reinforcement learning;
- robot-data preparation;
- modeling;
- closed-loop evaluation;
- failure-driven data collection.

The concrete robot target is the user's Yahboom DOFBOT with Jetson Nano. The
current high-level objective is to reach simple, measurable,
camera-closed-loop tabletop manipulation in simulation and later behind safety
gates on the real robot. Software controls the real arm through vendor-level
servo angle/time commands; it does not assume access to motor-current control
or the servos' internal loops.

Transferable robot-learning concepts matter more than mastering NVIDIA-specific
APIs. Later phases progress toward manipulation, vision, imitation learning,
lightweight VLA post-training, and optional real hardware.

## Current verified state

- Phase 0 simulator/pretrained-policy acceptance: complete.
- Phase 1 PPO-from-scratch reproduction: complete.
- Phase 2 controlled RL study: complete; 27/27 trained-policy cells succeeded.
- Canonical task: `Isaac-Cartpole-v0` (manager-based).
- RL stack: skrl PPO on Isaac Launchable `3.0.0-beta2-post1`.
- Local training seed: `42`; parallel environments: `4096`.
- Local checkpoint result: `269.44` mean control steps, about `4.49` seconds
  at 60 Hz, with `22/25` episodes reaching the five-second time limit.
- Visual acceptance: complete; the policy balanced stably with relatively
  sparse cart corrections.
- Checkpoint learning curve: complete; ten checkpoints show a sharp improvement
  around 3-5M transitions and a plateau near 4.8 seconds after about 6.9M.
- Final numbered checkpoint: `24/25` time-limit episodes, outperforming the
  trainer-selected `best_agent.pt` under the fixed-seed acceptance metric.
- Phase 2 final evidence: 675 fixed 30-second episodes across 9 variants and 3
  training seeds, plus 90 checkpoint evaluations.
- Phase 2 main result: direct velocity observation was essential; four-frame
  history recovered two of three seeds but remained brittle. Reward/action
  variants largely retained success, while a wide training boundary produced
  one catastrophic seed.
- Brev `isaac-launchable-f150a5`: stopped; persistent disk retained.
- DOFBOT Goals 1-3 plus the vendor-shaped ActionChunk extension: machine- and
  Viewer-accepted.
- Goal 4 fixed-tabletop reaching: corrected physical-front v2 passed local,
  remote Isaac machine, and user Viewer gates for safe no-contact reaching.
  Scene depth/height and motion quality remain explicit pre-grasp limitations.
- The first lower/farther terminal-finger pre-grasp candidate failed its remote
  pose gates safely. A subsequent evidence-calibrated exhaustive local search
  proved that the strict world-down target is incompatible with the calibrated
  chain geometry and established angle envelopes.
- A joint-first task-space search now supplies a revised local candidate:
  `[90,66,66,66]°`, a horizontal table top at `z=0.26160 m`, and an angled
  front/up approach. The exact API endpoint passed remotely, but Isaac settled
  up to `4.64°` away and left `0.03213 m` Cartesian error. The isolated
  gravity/effort matrix subsequently showed that gravity-off effort-100 tracks
  within `0.0032°`, while both gravity-on effort-100 and effort-250 follow the
  same trajectory and miss by `4.976°`. Raising only the effort limit is
  therefore not a fix. Raw TGS `joint_vel` also disagrees materially with
  nearly stationary position samples. The local follow-up now measures
  settling from a `100 ms` position difference, reproduces a
  `16.444°/s` gravity-on raw/derived mismatch while preserving the real
  `4.974°` tracking error. The completed four-case TGS/drive comparison shows
  that external-force iteration repairs velocity telemetry but not tracking;
  two velocity iterations have no material effect; and damping 50 remains at
  `4.883°`. Force `1048/53/100` reduces that residual to `1.73936°`. The
  bounded gravity feed-forward machine treatment now passes at `0.002391°`
  after a fail-closed Torch/Warp setter incompatibility was repaired with
  native Warp arrays. No pre-grasp, Viewer, contact, or grasp is authorized
  because the accepted actuator runtime contract is not yet wired into the
  pre-grasp runner.

The manager-based task and `Isaac-Cartpole-Direct-v0` are different MDP and
checkpoint contracts. Do not reuse checkpoints, reward comparisons, or PPO
settings across them.

## Immediate next work

The CartPole stage is complete. The canonical next-stage plan is
`experiments/02_dofbot/README.md`.

1. Goal 1: complete — official USD asset and stationary Viewer contract.
2. Goal 2: complete — hard-coded joint motion, limits, sign, and reset.
3. Goal 2 extension: complete — versioned ActionChunk through the shared
   Yahboom API, with machine and Viewer acceptance.
4. Goal 3: complete — deterministic onboard RGB contract and explicit
   `link4`-camera binding, with machine and Viewer acceptance.
5. Goal 4: complete for safe no-contact reaching — the collision-enabled
   tabletop, static cube, corrected physical-front frame, safe scripted
   approach, and Jacobian state-controller approach passed local, remote
   machine, and visual gates through the same Yahboom API.
6. Goal 5 first candidate: rejected — the terminal-finger frame, pose-aware
   controller, smoothness, collision, and contact gates worked fail-closed, but
   the world-down pose failed remotely and is rejected by the calibrated
   all-branch search. A revised angled pre-grasp candidate reaches its exact API
   endpoint, but the gravity-on articulation fails the one-degree tracking
   gate. The completed actuator matrix proves gravity sensitivity, falsifies
   effort 250 as a sufficient fix, and the local position-derived velocity
   contract plus four-stage solver/drive plan passed offline review. The
   focused remote matrix then repaired raw velocity telemetry without repairing
   tracking. The completed official-asset audit found uniform X-axis
   acceleration drives on joints 1-4 and corrected the earlier interpretation
   of implicit-actuator torque buffers: they are PD estimates, not measured
   PhysX solver torque. The completed five-case acceleration/force matrix then
   rejected the prior high-gain force drive as unstable and reduced the best
   stable error from `5.04065°` to `1.73936°` with official-scale stiffness
   and damping. No case passed the unchanged one-degree gate, so pre-grasp and
   Viewer remain blocked. The follow-up residual-force audit explains the
   `100`/`5.2` invariance at high confidence as a non-binding
   force-versus-impulse limit and rejects a static joint-frame error as the
   primary cause. The bounded gravity-compensation feed-forward implementation
   now passes its isolated machine gate at `0.002391°` worst settled error,
   with zero contact and zero clipped samples. Its first attempt failed before
   motion at the installed Warp frontend boundary and is preserved separately.
   The next free step is pre-grasp runtime integration; pre-grasp machine and
   Viewer gates remain pending.

Do not introduce PPO, SFT, imitation learning, a CV training pipeline, grasping,
or real hardware commands during Goal 4. The older
OmniIsaacGymEnvs DOFBOT Reacher project is a design reference only.

The first `z=0.08 m` tabletop plus strict world-down pre-grasp remains a
historical rejected candidate. The revised candidate is derived from safe
joint postures rather than a guessed Cartesian target. Exhaustive 1° searches
show that a meaningful front/up approach cannot place the table top at or
below `0.12 m`; the physical-envelope minimum is `0.17945 m` at a zero-margin
boundary pose. The strict residual-aware filters admit one robust candidate:
`[90,66,66,66]°`, terminal-finger midpoint
`(-0.00071,+0.22052,0.28278) m`, cube center
`(-0.00071,+0.29589,0.28660) m`, and table top `z=0.26160 m`.

The revised pose controls the midpoint of official terminal-finger bodies
`Finger_Left_03` and `Finger_Right_03`, not `Wrist_Twist` alone. Its desired
approach axis is `(0,+0.94213,+0.33526)`, closing remains monitor-only world
`+X`, and only `joint1`-`joint4` cross the Yahboom API. Wrist twist and the
gripper remain uncommanded.

The residual-force audit is complete. At the recorded 60 Hz timestep, a PhysX
`maxForce` value of `5.2` corresponds to `312` force units per second if the
articulation uses impulse-limit semantics. That is a high-confidence
explanation for why limits `100` and `5.2` left all 647 selected physical
samples identical, but the runtime articulation flag was not directly exposed
by the recorded USD or tensor telemetry and the audit preserves that boundary.

The bounded gravity-compensation feed-forward experiment is complete. Its
matched baseline remains at `1.73936°`, while the treatment passes at
`0.002391°`; maximum compensation is `0.363701`, far below the `5.2` bound,
with zero clipping, zero uncontrolled-DOF effort, and zero contact. The
initial native-frontend failure and repaired success have separate SHA-bound
records. The next step is free local integration of the selected force
`1048/53/100`, external-force-iteration, native-Warp feed-forward, API-probe,
effort-isolation, and telemetry contract into the pre-grasp runner. Do not run
the existing acceleration `10000/100` pre-grasp path or open the Viewer until
that integration is reviewed and its separate headless machine gate passes.
Contact and grasping remain out of scope.

## Sources of truth

- `AGENTS.md`: automatic operating rules for Codex.
- `docs/STATUS.md`: latest infrastructure and milestone status.
- `experiments/README.md`: numbered learning sequence and key commands.
- `docs/EXPERIMENTS.md`: append-only successful and failed run record.
- `docs/LESSONS_LEARNED.md`: pitfalls that must not be repeated.
- `artifacts/evaluations/`: small reviewed machine-readable results.
- `artifacts/phase2/`: manifests, episode data, derived tables, figures, and
  the controlled-study report.
- `experiments/02_dofbot/README.md`: DOFBOT goals, gates, and later milestones.
