# Robotics Isaac Learning

Small, CLI-driven robotics-learning experiments using NVIDIA Brev, Isaac Sim,
Isaac Lab, PyTorch, and a supported reinforcement-learning backend.

The repository name intentionally preserves the historical spelling
`robotics-issac-learning`. Source code and documentation use the correct
spelling **Isaac**.

## Current milestone

Phase 0 is complete. One Brev L4 instance ran the official Isaac Launchable,
showed a visibly unstable random CartPole policy, and then showed a nearly
stable policy from NVIDIA's official skrl PPO checkpoint. The fixed-seed
manager-based evaluation measured:

| Policy | Mean episode length | Time-limit episodes |
| --- | ---: | ---: |
| random | 188.44 | 0 / 25 |
| official pretrained PPO | 268.88 | 22 / 25 |

The successful task was `Isaac-Cartpole-v0`, a **manager-based** environment.
It is not checkpoint-compatible or directly metric-comparable with
`Isaac-Cartpole-Direct-v0`. Short local PPO attempts on the Direct task did not
converge and are recorded as failed experiments rather than presented as the
trained result.

## Current milestone

Phase 1 trained skrl PPO from scratch on the same manager-based
`Isaac-Cartpole-v0` task. The local checkpoint reached `269.44` mean episode
steps, `22/25` time-limit episodes, and `4.3805` mean reward in the fixed-seed
evaluation, closely matching the official checkpoint.

The user also confirmed stable behavior in the Viewer: this locally trained
policy kept the pole close to vertical with comparatively sparse, anticipatory
cart corrections. Phase 1 is complete. The next short verification is to repeat
training with two more seeds before changing the learning problem in Phase 2.

## Long-term learning path

Isaac CartPole is only the entry point. The repository is intended to build a
transferable robotics-ML workflow that progresses from reinforcement learning
fundamentals to manipulation, imitation learning, vision, and VLA
post-training.

| Phase | Goal | Deliverable |
| --- | --- | --- |
| 0 — Simulator loop | Prove Brev, Isaac, evaluation, and Viewer plumbing | Random-versus-pretrained CartPole result — complete |
| 1 — PPO reproduction | Train the manager-based CartPole policy from scratch | Local checkpoint passed quantitative and visual gates — complete |
| 2 — Controlled RL | Change one reward, observation, action, or termination at a time | Reproducible ablations and regression thresholds |
| 3 — Robot-arm control | Move from CartPole to Franka reach and cube lift | State-based manipulation baseline |
| 4 — Imitation learning | Build a demonstration pipeline and train BC, ACT, or Diffusion Policy | Versioned demonstrations and closed-loop success evaluation |
| 5 — Vision and multimodality | Add RGB observations and visual representations | Vision-policy baseline with failure analysis |
| 6 — VLA post-training | Add language-conditioned tasks and a lightweight VLA/action head | Reproducible VLA fine-tuning and checkpoint provenance |
| 7 — Failure-driven iteration | Mine rollout failures and target the next data/training round | Held-out scenario suite and measurable improvement |
| 8 — Real-robot bridge | Add hardware only after simulation behavior is reliable | Safety-gated, optional low-cost sim-to-real experiment |

The detailed [roadmap](docs/ROADMAP.md) defines the acceptance gate for each
phase. We do not advance based only on an attractive Viewer clip.

## Local commands

```bash
make doctor     # inspect local tools, GitHub, Brev, and current instances
make search     # non-billable live search for the approved MVP hardware
make provision  # fail-closed billable creation; requires explicit approval
make sync       # clone or fast-forward the feature branch inside Isaac container
make remote-setup # sync and collect container environment metadata
make smoke      # start random CartPole through the secure viewer
make train      # run headless skrl PPO and save a checkpoint
make play       # stream the latest or explicitly selected trained checkpoint
make eval       # fixed-seed random/trained evaluation; exact checkpoint required
make status     # show Brev instance state
make stop       # stop, but never delete, the configured instance
make show-train # print the exact remote training command without running it
make show-eval  # print the exact evaluation commands without running them
```

Set `BREV_INSTANCE_NAME` to the exact active instance name. Training and
playback default to the installed `Isaac-Cartpole-v0` task and its official
skrl PPO configuration. `ISAAC_MAX_ITERATIONS` is empty by default so the
installed task config controls the training horizon; set it only for an
intentional bounded experiment. Set `ISAAC_CHECKPOINT` to an exact checkpoint
path before `make eval`.

## Project records

- [Roadmap](docs/ROADMAP.md): detailed phases and acceptance gates
- [Runbook](docs/RUNBOOK.md): exact operator and user-intervention flow
- [Transferable robotics-ML commands](docs/ROBOTICS_ML_COMMANDS.md): the
  task-to-baseline-to-training-to-evaluation workflow worth learning
- [Phase 1 PPO reproduction](docs/PHASE1_PPO_REPRODUCTION.md): locked
  manager-based config, diagnosis, commands, and acceptance gates
- [Phase 2 controlled RL](docs/PHASE2_CONTROLLED_RL.md): seed robustness,
  control telemetry, and the first single-reward ablation
- [Operator command visibility](docs/COMMANDS.md): Brev/container preview and
  transcript details
- [Lessons learned](docs/LESSONS_LEARNED.md): traps already encountered
- [Experiments](docs/EXPERIMENTS.md): successful and failed runs
- [Environment](docs/ENVIRONMENT.md): pinned local and remote versions
- [Status](docs/STATUS.md): current infrastructure and milestone state
