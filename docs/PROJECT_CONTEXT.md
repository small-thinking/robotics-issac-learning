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
  front/up approach. It passes the residual-aware local design contract but
  has not run in Isaac or the Viewer. No contact or grasp is authorized.

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
   all-branch search. A revised angled pre-grasp candidate now passes its local
   design gate; Isaac machine and Viewer gates remain pending.

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

The exact next step, after review and merge, is a freshly quoted and explicitly
approved Isaac headless gate for this revised candidate. Open the Viewer only
if every machine gate passes. Contact and grasping remain out of scope.

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
