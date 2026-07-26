# Phase 1: Manager-Based PPO Reproduction

## Goal

Produce a new local skrl PPO checkpoint on `Isaac-Cartpole-v0` that matches the
behavioral standard established by the official pretrained checkpoint.

This is a reproduction, not a hyperparameter search. The first run must use the
installed manager-based task and its official skrl config without carrying over
Direct-task settings.

## Why the earlier training did not answer this question

The earlier runs trained `Isaac-Cartpole-Direct-v0`. The accepted official
checkpoint runs `Isaac-Cartpole-v0`. These are separate Gym task registrations
with separate environment and agent contracts.

The official `v3.0.0-beta2.patch1` source shows:

| Field | Manager-based | Direct |
| --- | ---: | ---: |
| task | `Isaac-Cartpole-v0` | `Isaac-Cartpole-Direct-v0` |
| rollout length | 16 | 32 |
| trainer vector steps | 2400 | 4800 |
| learning rate | `3e-4` | `5e-4` |
| state/value scaler | none | `RunningStandardScaler` |
| reward shaping scale | `1.0` | `0.1` |
| log directory | `cartpole` | `cartpole_direct` |

Thus “both used PPO” does not make the runs interchangeable. The Direct result
cannot establish whether the manager-based official recipe reproduces.

## Locked first-run contract

- image: existing Isaac Launchable `3.0.0-beta2-post1`
- task: `Isaac-Cartpole-v0`
- RL library: skrl
- algorithm: PPO
- training seed: `42`
- parallel environments: `4096`
- agent config: installed `skrl_ppo_cfg.yaml`
- manual max-iteration override: none
- resume checkpoint: none
- visualizer during training: none
- command transcript:
  `artifacts/commands/phase1.log` on the local Mac
- training log:
  `/workspace/phase1/artifacts/logs/train_cartpole_manager.log`

With the expected 2400 vector steps, 4096 environments generate
`2400 x 4096 = 9,830,400` transitions. Rollout length 16 means 150 PPO
collection/update cycles.

## Preflight

After the stopped instance is explicitly approved and restarted:

1. Sync the exact Phase 1 Git branch.
2. Run `make inspect-config`.
3. Record the installed Isaac Lab Git commit and config SHA-256.
4. Compare the printed config with the expected table above.
5. Confirm there is no `--max_iterations` argument in `make show-train`.
6. Confirm the output directory is a new manager-based `cartpole` run.

Any mismatch pauses training until it is explained.

## Training command

```bash
BREV_INSTANCE_NAME=isaac-launchable-f150a5 \
PROJECT_GIT_BRANCH=codex/phase1-observable-ppo \
ISAAC_TASK=Isaac-Cartpole-v0 \
ISAAC_NUM_ENVS=4096 \
ISAAC_TRAIN_SEED=42 \
ISAAC_TRAIN_LOG=/workspace/phase1/artifacts/logs/train_cartpole_manager.log \
REMOTE_COMMAND_LOG=artifacts/commands/phase1.log \
make train
```

The wrapper prints the complete local and container command, streams stdout,
and writes the remote log with `tee`.

## Evaluation and acceptance

Evaluate random and local-trained policies on the same task, using five
episodes for each of seeds `101, 202, 303, 404, 505`.

The local checkpoint passes when:

- mean episode length is at least 250;
- at least 20/25 episodes reach `time_limit`;
- mean reward is positive;
- checkpoint provenance is `local_trained`;
- the user confirms stable corrective behavior in the secure Viewer.

## Failure ladder

If the locked first run fails:

1. Verify the evaluated checkpoint belongs to the new `cartpole` run.
2. Compare training and evaluation task IDs.
3. Inspect episode-length and reward curves, not only final trainer output.
4. Compare the installed config hash and fields with the recorded preflight.
5. Check termination counts and action/observation shapes in evaluation.
6. Re-run one clean seed only after identifying a concrete mismatch.

Do not switch to Direct, change RL libraries, add a legacy preprocessor, resume
an old checkpoint, or increase the horizon until the locked reproduction has
been correctly executed and diagnosed.

## Reproduction result

The locked first run completed on 2026-07-26 without changing the task,
algorithm, installed config, or training horizon.

| Field | Result |
| --- | ---: |
| training time | 68.43 seconds |
| transitions | 9,830,400 |
| evaluated episodes | 25 |
| mean reward | 4.3805 |
| mean episode length | 269.44 |
| time-limit episodes | 22 / 25 |
| out-of-bounds episodes | 3 / 25 |

The evaluated local checkpoint is:

```text
logs/skrl/cartpole/2026-07-26_16-09-30_ppo_torch/checkpoints/best_agent.pt
```

All quantitative gates passed. The result closely matched the official
checkpoint's mean length of `268.88` and identical `22/25` time-limit count.
The user then confirmed stable behavior in the Viewer, with comparatively
sparse, anticipatory cart corrections that kept the pole close to vertical.
Phase 1 passed.

## Learning-curve follow-up

The run also retained numbered checkpoints from `agent_240.pt` through
`agent_2400.pt`. All ten were independently evaluated under the same fixed-seed
protocol.

The sweep loaded all numbered checkpoints in one Isaac process. At 60 Hz, mean
episode length converts to balance time with
`seconds = control steps / 60`. The graph shows:

- mean balance seconds versus training transitions;
- fraction of episodes reaching the five-second time limit;
- a horizontal random-policy reference.

The policy improved sharply between about 3 and 5 million transitions and
plateaued near 4.8 seconds after about 6.9 million transitions. The final
numbered checkpoint reached `24/25` time-limit episodes, versus `22/25` for the
trainer-selected `best_agent.pt`. Trainer-console metrics and the trainer's
checkpoint-ranking criterion remain useful diagnostics, but neither substitutes
for the controlled behavioral comparison.
