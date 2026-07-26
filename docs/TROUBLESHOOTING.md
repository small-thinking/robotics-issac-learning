# Troubleshooting

Read [Phase 0 Lessons Learned](LESSONS_LEARNED.md) before changing tasks or
checkpoints.

## Checkpoint loads but policy performs like random

1. Compare the exact task ID used for training, evaluation, and playback.
2. Confirm manager-based and Direct checkpoints were not mixed.
3. Inspect checkpoint preprocessing keys and the installed skrl version.
4. Evaluate fixed seeds; successful deserialization is not a success metric.

The observed legacy Direct checkpoint used `state_preprocessor`, while skrl
2.1.0 expected `observation_preprocessor`.

## PPO collects millions of transitions but does not improve

4096 vectorized environments accelerate collection but do not guarantee useful
updates. Check the resolved PPO config, rollout length, normalization, reward
terms, termination distribution, and independent checkpoint evaluation.
Do not increase iterations until the task/config/checkpoint identity is correct.

## Evaluator cannot find the action shape

Isaac's Gym and skrl wrappers may not expose the single-environment action
space at the outer level. The repository evaluator uses
`raw_env.unwrapped.single_action_space`.

## Evaluation JSON disappears during shutdown

Write the result while the simulation context is active, then close the
environment. The installed beta image can disrupt Python work scheduled after
Kit teardown.

## Remote playback command exits with code 143

Avoid `pkill -f` with a pattern that also appears in the shell's own command
line. The checked-in scripts enumerate Python processes and match only Isaac
random/play entry points.

## Instance is running but the Launchable is not ready

`brev ls --json` distinguishes VM state, build state, shell readiness, and
health. A running VM can still be executing the Launchable lifecycle script.
Wait for the official script to finish before starting another Docker Compose
operation.

## Viewer does not connect

1. Confirm the Launchable lifecycle script completed successfully.
2. Confirm the nginx, runtime, and web-viewer containers are running.
3. Confirm the secure link on port 80 is healthy.
4. Confirm the Isaac command logged `Simulation App Startup Complete`.
5. Keep only one `/viewer` browser tab open and refresh it after playback
   restarts.

Do not replace the secure link with an unauthenticated public endpoint.

## CLI cannot find the instance

Run `brev refresh`, then `brev ls`. Confirm the active Brev organization and
the exact `BREV_INSTANCE_NAME`.

## GPU is visible on the host but not in the container

Check `nvidia-smi` on the host, container status, and the container's
`NVIDIA_VISIBLE_DEVICES` configuration. Do not reinstall the NVIDIA driver
inside the official image.

## Out of disk

Inspect disk and Docker usage before deleting anything. Isaac images, shader
caches, logs, and checkpoints are large. Deleting the instance or persistent
disk requires separate approval.

## Instance is stopped but a charge remains

Stopping ends compute charges, not persistent-disk charges. The Phase 0 quote
was about `$0.04/hour` for 256 GiB while stopped. Deleting the disk or instance
requires separate explicit approval.
