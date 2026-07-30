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

1. Merge the reviewed actuator-diagnostic branch.
2. Verify the retained Brev instance is `STOPPED`.
3. Regenerate the local plan and inspect the exact remote matrix:

   ```bash
   make dofbot-actuator-calibration-dry-run
   make show-dofbot-actuator-calibration
   ```

   `artifacts/dofbot/actuator_calibration_plan.json` must pass every local
   check and list exactly gravity-on/effort-100,
   gravity-off/effort-100, and gravity-on/effort-250. The default DOFBOT scene
   must still use effort 100.

4. Obtain a fresh live quote and explicit approval for the existing instance.
   Do not create, resize, or delete an instance or disk.

After approval, synchronize the approved commit and run the isolated diagnostic
before the task scene:

```bash
export BREV_INSTANCE_NAME=isaac-launchable-f150a5
make sync
make dofbot-actuator-calibration
```

The wrapper runs three separate Isaac processes and prints
`[MATRIX_EXIT_CODE]`. The outer command intentionally exits zero so Brev cannot
automatically retry a paid stateful matrix; the local wrapper parses the marker
and fails `make` if it is not zero. Require `[MATRIX_EXIT_CODE] 0`,
retrieve the three files under
`artifacts/dofbot/actuator_calibration_cases/`, and retrieve
`artifacts/dofbot/actuator_calibration_contract.json`.
Each case has a 300-second default timeout. Existing case/summary files are
moved into a timestamped archive before execution, and every result must match
the current Git commit and calibration-config SHA; a failed process therefore
cannot be masked by stale evidence.

Use Brev's container-aware copy command while the approved instance is still
running:

```bash
brev copy \
  isaac-launchable-f150a5:/workspace/robotics-issac-learning/artifacts/dofbot/actuator_calibration_cases/ \
  artifacts/dofbot/actuator_calibration_cases/
brev copy \
  isaac-launchable-f150a5:/workspace/robotics-issac-learning/artifacts/dofbot/actuator_calibration_contract.json \
  artifacts/dofbot/actuator_calibration_contract.json
```

Retrieve the matrix artifacts, then stop the instance and poll
`brev ls --json` to terminal `STOPPED` before implementing a correction. Do
not append a pre-grasp attempt or Viewer session to this diagnostic window:
the matrix decision must first be reviewed and the corresponding local change
must pass the same offline gates.

Inspect, for every pose:

- exact API request and backend interpolated target;
- Isaac `joint_pos_target` versus backend target;
- observed `joint_pos` and actual `joint_vel`;
- actual-velocity settling for the configured hold period;
- stiffness, damping, and effort-limit buffers;
- computed/applied torque only when the contract marks them meaningful;
- contact force and body positions;
- `physics_snapshot.optional_probe_errors` whenever an optional PhysX field is
  null.

Follow only the matrix decision:

- target-buffer mismatch: repair the API/backend/Isaac target path;
- meaningful applied torque reaches the configured limit with a
  computed/applied gap: treat saturation as directly observed;
- gravity-off resolves the error: isolate gravity/load and tune the lowest
  stable effort or gain;
- effort-250 resolves the error: validate the lowest sufficient effort;
- neither control resolves it: inspect drive gains, axes, solver settings,
  self-collision, mass/inertia, and an explicit command-to-settled-state map;
- missing telemetry or failure to settle: repair instrumentation/runtime
  compatibility before task control.

After applying the decision-specific change, rerun the same calibration matrix.
Only a complete calibration with the selected baseline meeting the `1°`
tracking gate authorizes the unchanged task-scene headless command:

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
```

Retrieve and inspect `artifacts/dofbot/pregrasp_machine_contract.json`.
Confirm `validated_joint_candidate_command_reached`,
`final_api_joint_tracking_within_tolerance`, the unchanged `0.025 m / 12°`
Cartesian gates, collision/contact gates, exact API count, and neutral reset.
Merely remaining inside the broad physical envelope is not enough, and
observed state never substitutes for the exact API endpoint. Servo 5, wrist
twist, gripper closing, target motion, camera controller input, policy,
checkpoint, and real hardware remain out of scope.

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
