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

Phase 1 now has one precise goal: train skrl PPO from scratch on the same
manager-based task and pass the same numerical and visual acceptance gates.
No custom robot, camera pipeline, VLA, or Hugging Face integration is part of
that reproduction step.

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
```

Set `BREV_INSTANCE_NAME` to the exact active instance name. Training and
playback default to the installed `Isaac-Cartpole-v0` task and its official
skrl PPO configuration. `ISAAC_MAX_ITERATIONS` is empty by default so the
installed task config controls the training horizon; set it only for an
intentional bounded experiment. Set `ISAAC_CHECKPOINT` to an exact checkpoint
path before `make eval`.

See [the roadmap](docs/ROADMAP.md), [runbook](docs/RUNBOOK.md), and
[lessons learned](docs/LESSONS_LEARNED.md) before the next paid run.
