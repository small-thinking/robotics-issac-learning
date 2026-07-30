# Decisions

## 2026-07-25 — Use the official Isaac Launchable

Prefer the official preconfigured environment over a manual Isaac Sim and Isaac
Lab installation. This minimizes time to the first visible result and preserves
the official streaming stack.

## 2026-07-25 — Override the default GPU for Phase 0

The official Launchable recommends AWS `g6e.4xlarge` with one L40S at
approximately `$3.605088/hour`. For the simple CartPole MVP, use AWS
`g6.4xlarge` with one L4 and 64 GiB RAM at the last observed price of
`$1.59/hour` for compute.

This is a cost optimization outside the Launchable's recommended instance
configuration. If the L4 configuration fails due to a verified hardware or
memory constraint, stop it before considering the default L40S.

## 2026-07-25 — Use Boardman, Oregon for the MVP

Use AWS `us-west-2` (shown by Brev as Boardman, Oregon) to minimize interactive
streaming latency from the user's US West Coast location. The selected
configuration is stoppable and has flexible storage and ports.

The deployment UI reports approximately `$1.62-$1.63/hour` total: `$1.59/hour`
compute plus about `$0.04/hour` for the 256 GiB persistent disk. Stopping the
instance ends compute charges but the disk continues at about `$0.04/hour`.

## 2026-07-25 — Treat task identity as part of the checkpoint interface

Use `Isaac-Cartpole-v0` as the canonical Phase 1 training/evaluation task.
Manager-based and Direct CartPole solve similar physics problems but do not
share an assumed observation, reward, termination, preprocessing, or checkpoint
contract. Task IDs must match across random baseline, training, evaluation, and
playback.

## 2026-07-25 — Use the official checkpoint only for Phase 0 acceptance

The official manager-based skrl PPO checkpoint is allowed to validate the
end-to-end simulator, loader, evaluator, and Viewer. It is not evidence that our
own PPO run learned the behavior. Phase 1 therefore requires a checkpoint
created by a fresh local training run on the same manager-based task.

This preserves the useful result without hiding the failed Direct training
attempts.

## 2026-07-25 — Gate progress with fixed-seed evaluation

Visual inspection remains a required human check, but it is not the sole
success criterion. Phase 1 uses the same 25-episode fixed-seed protocol for
random and trained policies and requires at least 250 mean steps, 20/25
time-limit episodes, and positive mean reward.

## 2026-07-25 — Use the installed official training horizon by default

The former 150-iteration override is retained only in the experiment record; it
is not the canonical convergence budget. `ISAAC_MAX_ITERATIONS` is empty by
default so the installed task's official PPO config controls the run. A manual
cap must be labeled as a bounded experiment and evaluated independently.

## 2026-07-26 — Reproduce the manager-based PPO recipe before tuning

The first Phase 1 run uses `Isaac-Cartpole-v0`, skrl PPO, seed 42, 4096
environments, and the installed manager-based YAML with no iteration override
or resume checkpoint.

The earlier Direct runs differed in rollout length, learning rate,
normalization, reward scale, trainer horizon, and task semantics. Increasing
their duration did not test the accepted manager-based recipe. Configuration
inspection and checkpoint provenance therefore precede any new tuning.

## 2026-07-26 — Treat the failed Direct runs as a contract mismatch

The clean manager-based reproduction passed its quantitative gates in 68.43
seconds without hyperparameter tuning. This establishes that the earlier
failure was not evidence that PPO, the L4, 4096 parallel environments, or the
overall Isaac training path was broken.

Future debugging starts by matching task ID, observation/action interface,
reward and termination semantics, preprocessing, rollout length, and training
horizon. More compute is considered only after those contracts match.

## 2026-07-26 — Use fixed-seed checkpoint sweeps for learning curves

Plot independently evaluated numbered checkpoints rather than treating noisy
trainer-console statistics as the final behavioral curve. The primary metric
is mean balance seconds, with five-second time-limit fraction as a second
panel.

A uniform-random policy is a horizontal reference baseline. It is not labeled
as training step zero because it is not the freshly initialized PPO network.

## 2026-07-26 — Select checkpoints with the acceptance evaluator

Use the canonical fixed-seed behavioral evaluator when choosing the checkpoint
for comparison or playback. Preserve `best_agent.pt` as trainer output, but do
not assume its internal selection metric matches mean balance time or
time-limit success.

In the seed-42 run, `best_agent.pt` reached `22/25` time-limit episodes, while
the final numbered checkpoint reached `24/25` under the same evaluation
contract. Both remain valid artifacts; claims about “best” must name the metric
used.

## 2026-07-26 — Use the user's DOFBOT as the manipulation target

Replace the generic Franka-first Phase 3 with a Yahboom DOFBOT path because the
user owns the matching arm and Jetson Nano. Use NVIDIA's maintained official
USD as the simulation asset; treat the older OmniIsaacGymEnvs DOFBOT Reacher
repository as a design reference rather than a compatible runtime dependency.

Phase 3 starts with three policy-free gates: load and inspect the articulation,
drive small hard-coded joint movements, and capture the onboard camera. Do not
choose PPO, imitation learning, SFT, or a VLA method until the asset, action,
and camera interfaces are measured and reproducible.

## 2026-07-27 — Expose Yahboom's API over backend-neutral joint commands

Motion plans and later policies can issue Yahboom's documented
`Arm_serial_servo_write(id, angle, time)` call against the simulator or
physical backend. `YahboomServoApiAdapter` normalizes those calls to complete
named positions for `joint1` through `joint4` in radians plus a duration in
milliseconds. `DofbotArm` then delegates to either an Isaac articulation
backend or a Yahboom hardware backend.

This preserves the vendor's application-level API while keeping safety checks
and evaluation backend-neutral. It uses single-servo writes for the four
validated arm joints rather than `Arm_serial_servo_write6`, because the wrist
and gripper are not yet in the safe simulation contract.

Official documentation supports servo IDs 1 through 4 matching the first four
arm joints and 90 degrees as the centered/upright example pose. It does not
prove the physical direction and per-device zero offset of the user's arm.
Consequently, the checked-in `90 + degrees(radians)` conversion is explicitly
unverified and the real backend refuses all reads and writes until a physical
calibration is marked verified.

## 2026-07-27 — Start ActionChunk v1 with complete absolute poses

The first configured-motion schema uses complete absolute integer-degree poses
for servo IDs 1 through 4 at a fixed 10 Hz control rate. It does not begin with
relative actions, sparse joint updates, variable control frequency, wrist or
gripper control, force targets, or a hardware-backend selector.

Absolute complete poses make a scripted run reproducible from a known neutral
state and prevent an omitted joint from silently retaining stale state.
Configured poses are restricted to `[85°, 95°]`, adjacent configured poses may
differ by at most `5°`, and every sequence must start and finish at the
90-degree neutral pose.

Each configured movement is linearly compiled to 100-millisecond samples, and
each sample expands to four documented `Arm_serial_servo_write` calls. This
compiled representation is the stable boundary that later scripts, state
machines, policies, or VLA action decoders can produce without changing the
Isaac or physical backends.

## 2026-07-28 — Separate camera optical forward from robot workspace front

Goal 3 placed diagnostic objects in the neutral camera's optical plane. That
proved camera geometry and link binding, but it deliberately did not define a
physical tabletop or robot-base frame. Goal 4 incorrectly reused the optical
plane's world `-Y` side as the work side and even made the parser reject tables
outside that half-plane.

The remote machine gate still passed because Cartesian distance, clearance,
API-call accounting, and reset checks are invariant to whether a reachable
target is in front of or behind the base. The Viewer exposed the missing
semantic contract: the world `-Y` table was visibly on the same side as the
Jetson/electronics carrier.

Future tabletop tasks must declare a base-frame workspace-front direction and
an electronics-rear direction independently of the moving camera optical
axis. The complete robot asset, Jetson carrier, and base frame stay fixed;
scene placement and safe joint/servo mapping are corrected relative to that
frame. A local parser test must reject a rear-side table before any renewed
GPU validation.

For the current official USD and the user-reviewed Perspective layout, this
contract is world `+Y = workspace front` and world
`-Y = Jetson/electronics rear`. Goal 4 schema v2 locks those calibrated
vectors, computes each box's nearest front-side clearance by projection, and
rejects a relabeled frame or rear-side workspace before Isaac starts. The
previously machine-accepted `-Y` scripted poses are mirrored around the 90°
neutral servo angle rather than rotating the complete robot asset. This is a
simulation-frame correction only; it does not claim the physical-servo
direction/offset mapping has been hardware-calibrated.

## 2026-07-29 — Calibrate the actuator layer before tuning the task

The offline pre-grasp model was fitted in observed-joint space, while the
selected `[90,66,66,66]°` vector was later issued in API-command space. The
corrected controller now reaches that exact API endpoint, but Isaac settles up
to `4.64°` away. Moving the cube, loosening the Cartesian gate, or repeatedly
changing the controller would hide this command-to-observation mismatch.

Keep the default official-asset actuator configuration at effort 100 until an
isolated diagnostic distinguishes causes. The next paid run removes the task
scene and compares gravity-on/effort-100, gravity-off/effort-100, and
gravity-on/effort-250 with identical poses and per-physics-step telemetry.
Actual joint velocity defines settling. The Isaac target buffer must match the
backend interpolated target before a drive-dynamics conclusion is allowed.

Computed/applied torque is optional evidence for implicit actuators: present,
nonzero buffers may support a saturation conclusion, while zero or unavailable
buffers are explicitly inconclusive. Tracking failure is a valid calibration
result and must still be written. Pre-grasp may resume only after the matrix
selects a cause-specific correction and the chosen baseline passes the
independent one-degree tracking gate.

## 2026-07-30 — Do not treat effort 250 or raw TGS velocity as the actuator fix

The isolated remote matrix confirmed that gravity-off effort-100 tracks the
same API poses within `0.0032°`, while gravity-on effort-100 misses by
`4.976°`. This establishes a load-dependent actuator/model problem without
task contact or a target-buffer mismatch.

Effort 250 is not accepted as the correction. Isaac effort buffers, PhysX DOF
maximum forces, and the applied-torque clamp all changed from 100 to 250, but
the complete selected gravity-on target, position, and reported-velocity
sequence did not change. A higher configured clamp that leaves the measured
trajectory byte-identical is not evidence of improved control.

Raw `joint_vel` also cannot remain the sole settling authority in this runtime.
The final position samples vary only by microdegrees while the buffer reports
multi-degree-per-second motion, and Isaac logs a TGS noisy-velocity warning.
Preserve both signals: add finite-difference position velocity, retain raw
velocity as a compatibility diagnostic, and fail closed when they materially
disagree.

The remaining gravity-on position error is unresolved. The next experiment
must isolate solver/drive behavior after the telemetry contract is repaired;
it must not move the task scene, loosen the one-degree gate, jump directly to
pre-grasp, or assume that additional effort alone will help.

## 2026-07-30 — Use position difference for settling and a staged TGS/drive ladder

Physical settling is determined from a `100 ms` finite difference of observed
joint position, not from raw TGS `joint_vel` alone. Raw velocity is still
required and compared joint-by-joint; disagreement above `1°/s` during the
settling hold fails closed as a runtime compatibility problem. This keeps the
physical and telemetry claims separate without discarding either signal.

The next remote experiment changes one control at a time while gravity,
effort 100, stiffness 10000, and eight position iterations remain fixed:
enable external-force application on every TGS position iteration, then add
two velocity iterations, then reduce implicit damping from 100 to 50. Isaac
Lab 3.0 exposes the first setting through
`PhysxCfg.enable_external_forces_every_iteration`; its documentation describes
the option as improving velocity accuracy under TGS. Implicit actuator
stiffness and damping are physics P and D gains, so damping is treated as a
drive change rather than an arbitrary motion-profile adjustment.

The ladder does not authorize pre-grasp. A tracking improvement must still
pass the independent one-degree position gate; a telemetry-only improvement
is recorded separately and cannot substitute for tracking.
