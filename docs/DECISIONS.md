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

## 2026-07-27 — Put a backend-neutral API above Isaac and Arm_Lib

Motion plans and later policies issue one complete command: named positions for
`joint1` through `joint4` in radians plus a duration in milliseconds.
`DofbotArm` delegates that command to either an Isaac articulation backend or a
Yahboom hardware backend. This keeps planning, safety checks, and evaluation
independent of whether the arm is simulated or physical.

The hardware adapter uses Yahboom's documented
`Arm_serial_servo_write(id, angle, time)` and
`Arm_serial_servo_read(id)` methods. It uses single-servo writes for the four
validated arm joints rather than `Arm_serial_servo_write6`, because the wrist
and gripper are not yet in the safe simulation contract.

Official documentation supports servo IDs 1 through 4 matching the first four
arm joints and 90 degrees as the centered/upright example pose. It does not
prove the physical direction and per-device zero offset of the user's arm.
Consequently, the checked-in `90 + degrees(radians)` conversion is explicitly
unverified and the real backend refuses all reads and writes until a physical
calibration is marked verified.
