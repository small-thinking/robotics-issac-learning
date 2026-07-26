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
