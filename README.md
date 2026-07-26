# Robotics Isaac Learning

Small, CLI-driven robotics-learning experiments using NVIDIA Brev, Isaac Sim,
Isaac Lab, PyTorch, and a supported reinforcement-learning backend.

The repository name intentionally preserves the historical spelling
`robotics-issac-learning`. Source code and documentation use the correct
spelling **Isaac**.

## Current milestone

Phase 0 proves the smallest visible learning loop:

1. launch the official Isaac environment on one Brev GPU;
2. view an untrained/random CartPole policy through the streamed Isaac Sim UI;
3. train a minimal PPO policy headlessly;
4. view the trained policy and confirm the behavioral difference;
5. save the commands, versions, logs, checkpoint path, and evaluation summary;
6. stop the billable instance.

No custom robot, camera pipeline, VLA, or Hugging Face integration is included
in Phase 0.

## Local commands

```bash
make doctor     # inspect local tools, GitHub, Brev, and current instances
make search     # non-billable live search for the approved MVP hardware
make provision  # fail-closed billable creation; requires explicit approval
make status     # show Brev instance state
make stop       # stop, but never delete, the configured instance
```

See [the runbook](docs/RUNBOOK.md) for the operator and user-visible flow.
