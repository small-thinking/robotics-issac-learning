# Experiment Steps

This directory is the learning path through the repository. Each numbered
folder contains the transferable robotics-ML commands, hypothesis, outputs, and
acceptance rule for one experiment.

Cloud provisioning, Docker, repository sync, and secure Viewer plumbing remain
in `scripts/brev/` and `docs/COMMANDS.md`; they are deliberately not the
learning narrative.

| Step | Question | Status |
| --- | --- | --- |
| [`00_task_sanity`](00_task_sanity/README.md) | Is the MDP wired correctly, and what does random behavior look like? | complete |
| [`01_ppo_reproduction`](01_ppo_reproduction/README.md) | Can the official PPO recipe be reproduced from scratch? | complete |
| [`02_checkpoint_learning_curve`](02_checkpoint_learning_curve/README.md) | How does fixed-seed ability change with training transitions? | prepared; remote evaluation pending |
| [`03_reward_ablation`](03_reward_ablation/README.md) | Does cart-velocity shaping explain the learned control style? | planned |

Every step should leave:

- exact task/config/checkpoint provenance;
- a machine-readable result;
- a human-readable conclusion;
- a clear pass/fail or hypothesis decision.
