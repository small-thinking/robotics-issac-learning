# Experiment Hierarchy

This directory is the learning path through the repository. Top-level numbered
folders are major stages. A stage may contain numbered sub-experiments with
their own commands, hypothesis, outputs, and acceptance rules.

Cloud provisioning, Docker, repository sync, and secure Viewer plumbing remain
in `scripts/brev/` and `docs/COMMANDS.md`; they are deliberately not the
learning narrative.

| Stage | Question | Status |
| --- | --- | --- |
| [`00_task_sanity`](00_task_sanity/README.md) | Is the MDP wired correctly, and what does random behavior look like? | complete |
| [`01_cartpole_ppo`](01_cartpole_ppo/README.md) | Can we reproduce, measure, and explain PPO learning on one MDP? | in progress; reproduction and learning curve complete |

Every sub-experiment should leave:

- exact task/config/checkpoint provenance;
- a machine-readable result;
- a human-readable conclusion;
- a clear pass/fail or hypothesis decision.
