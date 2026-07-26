# CartPole Runbook

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
2. Confirm the instance is stopped with `make status`.
3. Record an explicit restart approval and session cost cap.
4. Restart only `isaac-launchable-f150a5`; never create a second instance for
   this experiment.

On the running instance:

```bash
make sync
make remote-setup
ISAAC_TASK=Isaac-Cartpole-v0 make smoke
ISAAC_TASK=Isaac-Cartpole-v0 \
ISAAC_NUM_ENVS=4096 \
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

## Checkpoint provenance labels

Every experiment must use one of these labels:

- `random`: no learned checkpoint;
- `official_pretrained`: downloaded Isaac Lab checkpoint;
- `local_trained`: checkpoint produced by this repository's training run;
- `resumed_local`: local checkpoint plus explicit resume provenance.

Do not use the generic word “trained” without one of these provenance labels.
