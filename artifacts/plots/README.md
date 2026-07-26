# Plots

`phase1_learning_curve.svg` is the real fixed-seed checkpoint learning curve
from the fresh seed-42 PPO run.

It was rendered from the reviewed
`artifacts/evaluations/phase1_learning_curve.json` after evaluating all ten
numbered checkpoints from `agent_240.pt` through `agent_2400.pt`. Every point
uses seeds `101, 202, 303, 404, 505`, five episodes per seed, and the same
manager-based `Isaac-Cartpole-v0` contract.

The upper panel reports mean balance seconds at 60 Hz. The lower panel reports
the fraction of episodes reaching the five-second time limit. The dashed random
baseline was measured under the same protocol and is not a synthetic
checkpoint.
