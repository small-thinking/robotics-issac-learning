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
  native Warp arrays. The accepted force `1048/53/100`, external-force
  iteration, and the exact native-Warp feed-forward implementation are now
  wired into the pre-grasp runner and pass the GPU-free `27/27` integration
  contract. The first integrated machine run then failed at `4.16578°` and
  exposed repeated API reissue; the no-reissue rerun proved that repair active
  but insufficient, still failing at `4.177019°` and `0.0318089 m`. The first
  approved target/torque attempt never left Brev startup (`DF-029`), but a later
  time-only retry reached the same retained L4 and ran the unchanged
  discriminator. The exact API command reached both backend and live
  `joint_pos_target`, rejecting target-write loss. Because Isaac Lab's
  implicit-actuator torque buffers are only approximate PD values, `DF-030`
  required measured PhysX projected joint force with every control factor held
  fixed. `DF-034` completed that run: all 61 observations were valid, but the
  projection is only active joint-force balance and the `4.177019 degrees`
  residual remained. `DF-033` remotely resolved the verifier defect. The
  completed `DF-035` discriminator then ran one accepted 2000-ms pose boundary
  but reproduced `4.196145 degrees / 0.0318115 m`; `DF-039` therefore
  falsifies segmented/fast candidate motion as a sufficient explanation.
  `DF-040` repairs the post-run verifier's exact-neutral false-reject edge.
  The completed offline audit then found that the accepted isolated candidate
  used a 12-degree `90 -> 78 -> 66` entry rather than the direct 24-degree
  DF-039 transition, and that its artifact does not bind the current shared
  runtime. The completed `DF-042` source-bound matrix now proves both split and
  direct no-box paths track within `0.0024 degrees`; adding only the exact
  static table/cube context restores a `4.199411-degree` residual with zero
  monitored contact. `DF-046` therefore localizes the remaining failure family
  to static-scene composition, while its mechanism remains open. Viewer,
  contact, and grasp remain blocked.

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
   GPU-free pre-grasp runtime integration now passes and binds both source
   SHA-256 values, probes the installed runtime before motion, reads back the
   live USD drives, records every physics-step feed-forward sample, and emits
   a failure classification. The separate single-boundary headless gate ran
   and failed only final position and joint tracking. The context-transfer
   matrix is now complete: current runtime and direct path pass without boxes,
   while the exact static scene reproduces the residual. A GPU-free scene-spawn
   audit and one-factor decomposition must precede another paid run. Viewer
   remains blocked.

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
records. The selected force `1048/53/100`, external-force iteration,
native-Warp feed-forward, API probe, effort isolation, live-drive readback,
telemetry, and failure-classification contracts are now shared with the
pre-grasp runner. The target/torque and projected-force reruns proved backend
and live target propagation, complete force telemetry, and reliable remote
semantic failure while reproducing the `4.177019°` residual. The later
single-boundary run preserved that residual at `4.196145°`, closing DF-035
through the falsified DF-039 hypothesis. Before another paid run, compare the
isolated and integrated contexts offline, name one new ledger discriminator,
then obtain a fresh quote and explicit approval. Do not open the Viewer until
a complete machine artifact passes. Contact and grasping remain out of scope.

## Sources of truth

- `AGENTS.md`: automatic operating rules for Codex.
- `docs/STATUS.md`: latest infrastructure and milestone status.
- `experiments/README.md`: numbered learning sequence and key commands.
- `docs/EXPERIMENTS.md`: append-only successful and failed run record.
- `docs/LESSONS_LEARNED.md`: pitfalls that must not be repeated.
- `experiments/02_dofbot/FAILURE_LEDGER.md`: canonical cross-run failure,
  falsification, supersession, and do-not-repeat index.
- `artifacts/evaluations/`: small reviewed machine-readable results.
- `artifacts/phase2/`: manifests, episode data, derived tables, figures, and
  the controlled-study report.
- `experiments/02_dofbot/README.md`: DOFBOT goals, gates, and later milestones.
