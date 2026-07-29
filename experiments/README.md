# Experiment Hierarchy

This directory is the learning path through the repository. Top-level numbered
folders are major stages. Short sub-experiments remain numbered sections in the
stage README; add another folder only when an experiment has enough code or
artifacts to justify an independent unit.

Cloud provisioning, Docker, repository sync, and secure Viewer plumbing remain
in `scripts/brev/` and `docs/COMMANDS.md`; they are deliberately not the
learning narrative.

| Stage | Question | Status |
| --- | --- | --- |
| [`00_task_sanity`](00_task_sanity/README.md) | Is the MDP wired correctly, and what does random behavior look like? | complete |
| [`01_cartpole_ppo`](01_cartpole_ppo/README.md) | Can we reproduce, measure, and explain PPO learning on one MDP? | complete; reproduction, curve, and controlled study complete |
| [`02_dofbot`](02_dofbot/README.md) | Can the user's robot asset, joints, and camera be made trustworthy before learning? | Goals 1-3 and ActionChunk extension complete; official onboard RGB camera binding machine- and Viewer-accepted |

Every experiment section should leave:

- exact task/config/checkpoint provenance;
- a machine-readable result;
- a human-readable conclusion;
- a clear pass/fail or hypothesis decision.
