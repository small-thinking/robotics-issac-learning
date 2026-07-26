# Phase 0 Runbook

## Operator flow

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
10. Train a short PPO run headlessly and save its checkpoint.
11. Evaluate fixed seeds and start trained-policy playback.
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
