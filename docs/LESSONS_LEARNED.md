# Phase 0 Lessons Learned

This file records traps that already cost time or cloud compute. Read it before
changing the task, image, RL backend, checkpoint, or evaluation protocol.

## Manager-based and Direct are different tasks

`Isaac-Cartpole-v0` is manager-based. `Isaac-Cartpole-Direct-v0` implements a
similar physical problem through the Direct workflow, but task identity is part
of the model interface. Observation ordering, action processing, rewards,
terminations, episode horizons, network config, and checkpoint preprocessing
may differ.

Never use a checkpoint from one task to claim performance on the other. Never
compare their reward numbers as if they share a metric definition. Record the
exact task ID beside every checkpoint and evaluation.

## A pretrained checkpoint validates plumbing, not our training

The nearly stable policy was NVIDIA's official manager-based skrl PPO
checkpoint. It proves that the simulator, task, policy loader, evaluator,
secure Viewer, and selected L4 hardware can produce the desired behavior. It
does not prove that our short local training converged.

The next milestone explicitly requires a newly produced checkpoint.

## A large transition count does not guarantee learning

4096 environments make data collection fast. They do not fix an incompatible
config, weak learning signal, bad normalization, or insufficient optimization
progress. The first 150-iteration Direct run collected 19,660,800 transitions
in about 97 seconds and still did not beat random under fixed-seed evaluation.

Treat iteration caps as experimental variables. First inspect the resolved
official config, learning curve, resets, advantage statistics, and checkpoint
evaluation; do not assume that “millions of samples” means convergence.

## Compare policies with one evaluation contract

Viewer behavior is useful but qualitative. Random and trained policies must use:

- the same exact task ID and environment config;
- the same simulator/software image;
- the same fixed seeds and episode count;
- the same termination and time-limit definitions;
- a recorded checkpoint path and training provenance.

For Phase 1 the canonical protocol is five seeds, five episodes per seed, with
episode reward, length, and termination reason recorded.

## Version drift can silently invalidate checkpoints

The official Direct skrl checkpoint used legacy `state_preprocessor` keys while
the installed skrl 2.1.0 agent expected `observation_preprocessor`. A compatibility
loader can make the file load, but successful deserialization is not proof of
behavioral compatibility. Always evaluate after loading and prefer checkpoints
produced by the exact installed image.

## Isaac wrappers hide important interfaces

The Gym wrapper did not expose the single-environment action shape at the level
initially queried. The evaluator needed
`raw_env.unwrapped.single_action_space`. When a wrapper changes observation,
action, reset, or termination semantics, inspect the unwrapped environment and
the RL-library adapter before patching around an error.

## Save metrics before Kit shuts down

In the installed Isaac Lab 3.0 beta image, teardown can terminate or disrupt
late Python work. The evaluator now writes its JSON while the simulation
context is still active and only then closes the environment. Do not defer
essential artifact writes until after Kit shutdown.

## Viewer processes need exact process selection

An early `pkill -f` pattern matched the remote shell command containing that
same pattern and killed the operator process with exit 143. Playback scripts now
select only Python processes whose arguments match Isaac random/play scripts.
Keep a single playback process and one Viewer tab.

## Launchable health signals are layered

VM state, lifecycle build state, SSH readiness, Docker healthchecks, Isaac app
startup, and Viewer readiness are distinct. A stale container healthcheck does
not necessarily mean Isaac is unusable, and a running VM does not mean the
simulation is ready. Confirm the specific layer required by the next action.

## Cost and persistence are separate

Stopping the instance ends GPU compute billing, but the 256 GiB persistent disk
continues at roughly $0.04/hour based on the deployment quote. Deleting the
instance or disk is a separate destructive action and requires explicit
approval. Checkpoint paths on the stopped disk are persistent but not a Git
backup.
