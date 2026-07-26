# Stage 01: CartPole PPO

This stage develops one complete reinforcement-learning workflow on the same
manager-based CartPole MDP. Its numbered folders are sub-experiments, not
separate top-level robotics milestones.

| Sub-experiment | Question | Status |
| --- | --- | --- |
| [`01_reproduction`](01_reproduction/README.md) | Can PPO learn the accepted behavior from scratch? | complete |
| [`02_checkpoint_learning_curve`](02_checkpoint_learning_curve/README.md) | How does ability change during that same training run? | complete |
| [`03_reward_ablation`](03_reward_ablation/README.md) | How does one reward term change the learned control style? | planned |

The stage is complete only after we can reproduce learning, measure how it
develops, and explain at least one controlled behavior change.
