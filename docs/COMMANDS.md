# Operator Command Visibility

This file covers platform operations and debugging. The learning-oriented
workflow is in `docs/ROBOTICS_ML_COMMANDS.md`.

Codex operates the remote simulator through the CLI. It does not require VS
Code and normally does not type commands into an interactive shell.

## Execution layers

```text
local Mac
  -> brev exec <instance> --host
    -> Brev VM host
      -> docker exec ... vscode bash -lc '<command>'
        -> Isaac Lab container at /workspace/isaaclab
```

`brev shell <instance>` would open an interactive VM shell. The checked-in
workflow instead uses `brev exec` so every operation can be printed, repeated,
logged, and reviewed.

## Preview before execution

These targets print the complete local and container commands but do not
connect to the VM:

```bash
make show-sync
make show-remote-setup
make show-smoke
make show-train
make show-play
make show-eval
```

For example, `make show-train` reveals both the outer `brev exec` invocation
and the inner Isaac command:

```bash
./isaaclab.sh -p scripts/reinforcement_learning/train.py \
  --rl_library=skrl \
  --task=Isaac-Cartpole-v0 \
  --algorithm=PPO \
  --seed=42 \
  --num_envs=4096 \
  --viz none
```

The exact installed task configuration supplies the training horizon unless
`ISAAC_MAX_ITERATIONS` is deliberately set.

Before a real Phase 1 session, select the exact existing instance and pushed
branch:

```bash
export BREV_INSTANCE_NAME=isaac-launchable-f150a5
export PROJECT_GIT_BRANCH=codex/phase1-observable-ppo
```

## Show internal shell execution

Set `REMOTE_TRACE=1` to prepend `set -x` inside the container:

```bash
REMOTE_TRACE=1 make train
```

This is useful for debugging shell control flow. It does not expose internal
Python operations; the training program's own stdout provides learning
metrics, iteration progress, and checkpoint messages.

Do not enable tracing for commands that contain credentials or other secrets.

## Save a local command transcript

The display block can also be appended to an ignored local file:

```bash
REMOTE_COMMAND_LOG=artifacts/commands/phase1.log make train
```

Training stdout is simultaneously streamed to the local terminal and saved on
the remote persistent disk by `tee`. Phase 1 uses:

```text
/workspace/phase1/artifacts/logs/train_cartpole_manager.log
```

Command transcripts are operational scratch data. After reviewing them, record
the canonical command, Git commit, task, resolved config, checkpoint, metrics,
and conclusion in `docs/EXPERIMENTS.md`.

Preview the checkpoint sweep without starting remote work:

```bash
make show-learning-curve
```

Run it only after the instance has been explicitly approved and started:

```bash
ISAAC_CHECKPOINT_DIR=logs/skrl/cartpole/<run>/checkpoints \
make learning-curve
```

## Preview the DOFBOT actuator diagnostic

The local plan and the exact future remote matrix are inspectable without
starting Brev:

```bash
make dofbot-actuator-calibration-dry-run
make show-dofbot-actuator-calibration
```

The remote command intentionally runs three isolated headless cases and prints
`[MATRIX_EXIT_CODE]`. The outer Brev transport exits successfully to prevent an
automatic retry of this paid stateful experiment; operators must require
`[MATRIX_EXIT_CODE] 0` and retrieve
`artifacts/dofbot/actuator_calibration_contract.json`. No Viewer command exists
for this diagnostic.

## Optional interactive learning

If a human wants to explore the VM manually, the equivalent sequence is:

```bash
brev shell isaac-launchable-f150a5
docker exec -it -u ubuntu:ubuntu -w /workspace/isaaclab vscode bash
```

Interactive commands can drift from the repository and are therefore not the
canonical experiment path. Exit without changing or deleting infrastructure.
