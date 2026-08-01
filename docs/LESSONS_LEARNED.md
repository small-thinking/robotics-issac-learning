# Lessons Learned

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

The clean manager-based reproduction sharpened this lesson: 9,830,400
transitions under the matching task/config contract passed in 68.43 seconds,
while the longer Direct runs did not. The meaning of the data is determined by
the MDP and optimizer contract, not by transition count alone.

## Early PPO checkpoints can be worse than random

In the fixed-seed manager-based learning curve, the 0.98M- and 1.97M-transition
checkpoints balanced for only about 0.24-0.25 seconds, compared with 3.13
seconds for uniform random actions. The policy had already learned a
coordinated but harmful action pattern before it learned to balance.

Always include a measured random baseline and intermediate checkpoints. A
single final checkpoint cannot reveal this initial degradation or the sharp
improvement between roughly 3 and 5 million transitions.

## PPO checkpoint quality is not monotonic

The curve reached `24/25` time-limit episodes at 6.88M transitions, dropped to
`22/25` at 7.86M, then returned to `24/25`. Optimization noise and a finite
evaluation sample make temporary regressions normal. Do not select a deployment
checkpoint solely because it is the last one or because its training step is
higher.

The trainer-selected `best_agent.pt` also reached `22/25`, while the final
numbered checkpoint reached `24/25` under the independent evaluator. The
trainer's internal ranking metric is not identical to the acceptance metric.

## Compare policies with one evaluation contract

Viewer behavior is useful but qualitative. Random and trained policies must use:

- the same exact task ID and environment config;
- the same simulator/software image;
- the same fixed seeds and episode count;
- the same termination and time-limit definitions;
- a recorded checkpoint path and training provenance.

For Phase 1 the canonical protocol is five seeds, five episodes per seed, with
episode reward, length, and termination reason recorded.

## Parallel evaluation must not select the first failures

The original evaluator launched 64 parallel environments and retained the
first five episodes that finished. In a long stress evaluation, policies that
fail early finish before successful environments, so this creates a
failure-selection bias.

The study evaluator preselects fixed environment IDs and records exactly the
first episode from each selected environment. It waits for all of those IDs,
even if non-selected environments terminate earlier. Phase 1 learning-curve
numbers remain historical evidence, but the Phase 2 baseline must be
re-evaluated under the corrected sampler before comparison.

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

## A mean can hide a binary seed-level failure

The four-frame observation variant averaged `66.7%` robust success, but the
three trained policies were `0%`, `100%`, and `100%`. The wide-boundary variant
showed a similar split. Reporting only the mean would incorrectly suggest
uniformly mediocre policies rather than a training-reliability problem.

Keep individual training-seed points visible and treat the trained policy—not
the many evaluation episodes—as the statistical unit.

## Evaluation layout is part of the cost model

The original five-seed-by-five-environment stress evaluation took roughly 90
seconds for one stable policy. Before formal cross-variant results were
collected, the protocol was amended to one deterministic seed with 25 fixed
parallel environment IDs. It preserved 25 episodes and eliminated sequential
seed batches, making the complete study affordable.

Benchmark one realistic final evaluation during smoke testing. Training time
alone is not a reliable estimate for a controlled-study GPU window.

## Observation history needs evaluator state management

Four-frame observation history introduced state that must be copied and reset
inside inference mode. An evaluator that loads the right checkpoint but fails
to reset its history buffer can silently contaminate episodes or trigger
PyTorch inference-tensor errors.

Interface ablations must be exercised end to end in both training and
evaluation; validating only the Hydra string is insufficient.

## A batch runner must fail closed on missing artifacts

One early smoke returned from the evaluator without the expected JSON. A zero
or tolerated shell status is not enough: the runner must verify the output
exists, parse it, hash it, and only then advance the manifest to a successful
state.

Resumability should key off verified artifacts and checkpoint hashes. This
allowed the formal run to stop at its 44-minute budget and resume only the nine
missing final evaluations.

## Remote CLIs can retry failed commands

Brev may retry a remote command after a nonzero exit, which is dangerous for a
paid, stateful experiment. Long study commands wrap their internal return code,
print it explicitly, and make the outer transport exit successfully. The
orchestrator then decides whether to resume.

Do not let an infrastructure client silently convert one failed training or
evaluation attempt into an unplanned duplicate run.

## Shell preview assertions must fail explicitly

On the local macOS Bash, a failed top-level `[[ ... ]]` expression did not
reliably terminate a script even with `set -e`. The remote-command preview
suite could therefore print `passed` after a missing command flag.

Wrap string checks in assertion functions that use an explicit `if` branch and
`exit 1`. Keep finite simulator commands explicit about `--headless` so the
preview tests verify an intentional launch contract rather than an implicit
runtime default.

## Raw PhysX setters use the native tensor frontend

Isaac Lab can expose public articulation state as Torch tensors while its raw
`omni.physics.tensors.ArticulationView` is backed by Warp. Passing Torch data
directly to `set_dof_actuation_forces` then fails inside
`FrontendWarp.as_contiguous_float32` with
`TypeError: issubclass() arg 1 must be a class`.

Probe raw runtime APIs before any robot command, inspect the installed
frontend, and use its native tensor type for both data and indices. Keep this
boundary separate from the backend-neutral Yahboom API and from Torch used for
controller math. A local type-shaped mock cannot substitute for this runtime
probe.

## Brev copy may address the VM rather than the Isaac container

On the retained Launchable, `brev copy` could not resolve an absolute path that
existed inside the `vscode` container. The evidence was still present; the
copy command was looking at the VM host filesystem.

Before concluding that an artifact is missing, verify it inside the container.
Use `brev exec --host "docker cp ..."` to a unique VM `/tmp` path, then run
`brev copy` from that host path. Classify direct-path failure as infrastructure
plumbing and do not rerun Isaac merely to regenerate already existing data.

## DOFBOT debugging must update the failure ledger

Chronological experiment notes preserve detail, but they do not by themselves
prevent an old hypothesis from being retried or a provisional root cause from
being repeated after later evidence supersedes it. The canonical index is
`experiments/02_dofbot/FAILURE_LEDGER.md`.

Before changing a DOFBOT controller, scene, runtime setting, measurement, or
wrapper, read the ledger and cite the unresolved entry being addressed. A new
paid run must introduce a named discriminator and must not bundle unrelated
parameter changes. After any failed, partial, falsifying, superseding, runtime,
artifact, transport, cost-window, or safety result, update the ledger in the
same pull request before another paid run.

Preserve historical verdicts. If a real bug is repaired but a later rerun
shows it was not the full root cause, add a superseding entry rather than
rewriting history. The `DF-026` to `DF-028` sequence is the reference example:
repeated API writes were a real defect, but the no-reissue machine rerun proved
they were insufficient to explain the loaded residual.

## Implicit-actuator torque buffers are not measured PhysX effort

Isaac Lab's `ImplicitActuator` lets PhysX perform the continuous-time PD
control. Its `computed_torque` and `applied_torque` fields are approximate PD
values calculated for consistency because PhysX does not directly expose that
torque. Equality between those two buffers proves neither solver application
nor absence of a lower-level drive/constraint problem.

Use backend and live `joint_pos_target` fields to verify command propagation.
When that path passes but the articulation still stalls, use PhysX projected
joint force beside the incoming wrench and gravity/PD telemetry as the next
discriminator. The projected value is the active component of incoming joint
force along the DOF direction; it is measured joint-force balance, not an
isolated drive-torque sensor. Require finite, DOF-aligned values on every
observation and preserve the distinction in artifact wording. Do not promote
an estimate or a projected total into a different measured physical fact.

## A semantic verifier must use the runtime's installed interpreter

The Isaac Launchable container can run scripts through
`./_isaac_sim/python.sh` while exposing no `python3` command on PATH. A wrapper
that correctly decides to inspect a fresh artifact can still replace the
scientific status with exit 127 if it assumes a generic interpreter.

Use the already proven Isaac interpreter for post-run verification, preserve
the retrieved artifact regardless of wrapper status, and test the emitted
sentinel separately from the launcher exit code.
