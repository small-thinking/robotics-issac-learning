# Project Runbook

## Phase 0 acceptance flow

1. Run `make doctor`.
2. Run `make search` and record the live candidate and price.
3. Verify provider, region, GPU, RAM, storage, stoppability, ports, and cost cap.
4. Obtain explicit user approval.
5. Provision exactly one official Isaac Launchable.
6. Verify `nvidia-smi`, driver, CUDA, OS, Python, PyTorch, Isaac Sim, Isaac Lab,
   and installed RL backends.
7. Discover the installed CartPole task and supported random, train, and play
   commands. Do not rely on stale paths.
8. Start random-policy playback and the authenticated/restricted viewer.
9. Ask the user to confirm the scene is visible, updating, and visibly unstable.
10. Load the official manager-based PPO checkpoint to validate the pipeline.
11. Evaluate fixed seeds on the same manager-based task and start playback.
12. Ask the user to confirm the trained behavior is visibly different.
13. Save small results and exact commands, then stop the instance.

## User intervention checkpoints

Codex sends a message when one of these is required:

1. **Billing approval:** exact hardware, region, hourly price, and session cap.
2. **Random-policy visual check:** open the provided secure URL, keep one viewer
   tab open, confirm that the scene updates and the pole falls/resets.
3. **Trained-policy visual check:** refresh or reopen the same viewer, confirm
   that the pole remains upright longer and the cart actively corrects.

The user does not need to type remote commands or operate VS Code.

## Phase 1 PPO-from-scratch flow

Before spending:

1. Read `docs/LESSONS_LEARNED.md`.
2. Read `docs/ROBOTICS_ML_COMMANDS.md`.
3. Read `docs/PHASE1_PPO_REPRODUCTION.md`.
4. Preview the commands with `make show-inspect-config`, `make show-train`, and
   `make show-eval`.
5. Confirm the instance is stopped with `make status`.
6. Record an explicit restart approval and session cost cap.
7. Restart only `isaac-launchable-f150a5`; never create a second instance for
   this experiment.

On the running instance:

```bash
export BREV_INSTANCE_NAME=isaac-launchable-f150a5
export PROJECT_GIT_BRANCH=codex/phase1-observable-ppo
export REMOTE_COMMAND_LOG=artifacts/commands/phase1.log

make sync
make remote-setup
make inspect-config
ISAAC_TASK=Isaac-Cartpole-v0 make smoke
ISAAC_TASK=Isaac-Cartpole-v0 \
ISAAC_NUM_ENVS=4096 \
ISAAC_TRAIN_LOG=/workspace/phase1/artifacts/logs/train_cartpole_manager.log \
make train
```

Leave `ISAAC_MAX_ITERATIONS` unset to use the installed task's official
training horizon. If a paid-session cap requires a shorter run, set it
explicitly and label the result as a bounded experiment, not a convergence
baseline.

For each candidate checkpoint:

```bash
ISAAC_TASK=Isaac-Cartpole-v0 \
ISAAC_CHECKPOINT=/absolute/remote/checkpoint.pt \
make eval

ISAAC_TASK=Isaac-Cartpole-v0 \
ISAAC_CHECKPOINT=/absolute/remote/checkpoint.pt \
make play
```

Accept the from-scratch run only when:

- the checkpoint belongs to the new local run;
- mean episode length is at least 250;
- at least 20/25 evaluation episodes reach the time limit;
- mean reward is positive;
- the user confirms stable corrective behavior in the secure Viewer.

Save the resolved config, log path, checkpoint path, metrics, elapsed time,
transition count, and Git commit. Then run `make stop` and verify `STOPPED`.

Every remote wrapper prints the outer Brev command and inner container command
before execution. See `docs/COMMANDS.md` for preview, tracing, transcript, and
optional interactive-shell usage.

## Checkpoint provenance labels

Every experiment must use one of these labels:

- `random`: no learned checkpoint;
- `official_pretrained`: downloaded Isaac Lab checkpoint;
- `local_trained`: checkpoint produced by this repository's training run;
- `resumed_local`: local checkpoint plus explicit resume provenance.

Do not use the generic word “trained” without one of these provenance labels.

## DOFBOT pose-aware pre-grasp flow

Before spending:

1. Merge the reviewed pose-aware pre-grasp branch.
2. Verify the retained Brev instance is `STOPPED`.
3. Run the local contract and remote command previews:

   ```bash
   make dofbot-pregrasp-pose-dry-run
   make show-dofbot-pregrasp
   make show-dofbot-pregrasp-view
   ```

   Inspect the generated local contract before spending. For
   `validated_joint_candidate`, it must show the complete bounded API command
   trajectory ending exactly at the configured integer-degree candidate with
   zero command velocity. A candidate on the command-margin boundary without
   one degree of braking reserve must fail during config preflight.

4. Obtain a fresh live quote and explicit approval for the existing instance.
   Do not create, resize, or delete an instance or disk.

After approval, synchronize the approved commit and run the machine gate first:

```bash
export BREV_INSTANCE_NAME=isaac-launchable-f150a5
make sync
make dofbot-pregrasp
```

Retrieve and inspect `artifacts/dofbot/pregrasp_machine_contract.json`. Do not
open the Viewer unless every machine check passes, including
`validated_joint_candidate_command_reached`. Confirm that
`final_controller_api_command_angles_deg` exactly matches
`target_joint_candidate_angles_deg`; observed joint tracking lag is permitted
only inside the physical envelope and never substitutes for the exact API
endpoint. The experiment remains open-gripper and no-contact: servo 5, wrist
twist, gripper closing, target motion, camera controller input, policy,
checkpoint, and real hardware are out of scope.

If the machine gate passes:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp-view
```

Tell the user what to look for: the arm should move smoothly toward the
lower/farther cube from above, stop at the pre-grasp offset, preserve a natural
posture, leave the gripper open, avoid visible contact, keep the cube
stationary, then return to neutral and repeat. Retrieve the Viewer artifact
after visual feedback, stop the instance immediately, and poll
`brev ls --json` until it reports terminal `STOPPED`.
