# Step 02: Checkpoint Learning Curve

## Question

As PPO receives more transitions, how long can the learned policy balance the
pole under one fixed evaluation contract?

## Metrics

The main y-axis is mean balance time in seconds:

```text
mean balance seconds = mean episode control steps / 60 Hz
```

The second panel reports the fraction of episodes that reach the five-second
time limit. Reward remains in the JSON but is not the most intuitive headline
metric.

The x-axis is total training transitions:

```text
training transitions = checkpoint vector steps x 4096 environments
```

For example, `agent_240.pt` represents `983,040` transitions and
`agent_2400.pt` represents `9,830,400` transitions.

## Key command

Evaluate all numbered checkpoints in one Isaac process, using identical seeds:

```bash
./isaaclab.sh -p /workspace/robotics-issac-learning/tools/evaluate_cartpole.py \
  --policy=sweep \
  --task=Isaac-Cartpole-v0 \
  --checkpoint-dir=logs/skrl/cartpole/<run>/checkpoints \
  --training-num-envs=4096 \
  --include-random-baseline \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=64 \
  --output=/workspace/robotics-issac-learning/artifacts/evaluations/phase1_learning_curve.json \
  --viz none
```

Render the reviewed JSON as a dependency-free SVG:

```bash
./isaaclab.sh -p \
  /workspace/robotics-issac-learning/tools/render_learning_curve.py \
  /workspace/robotics-issac-learning/artifacts/evaluations/phase1_learning_curve.json \
  /workspace/robotics-issac-learning/artifacts/plots/phase1_learning_curve.svg
```

The repository wrapper is:

```bash
ISAAC_CHECKPOINT_DIR=logs/skrl/cartpole/<run>/checkpoints \
make learning-curve
```

## Interpretation

The random policy is a horizontal reference, not a fake step-zero checkpoint.
Each connected point is a separately loaded `agent_<vector_step>.pt` policy
evaluated on the same seeds.

Do not assume the curve must rise monotonically. PPO checkpoints can regress
temporarily because optimization and finite-sample evaluation are noisy.

## Current status

The tools and commands are prepared locally. The numbered checkpoints remain
on stopped persistent storage, so the actual JSON and SVG require a newly
approved short GPU window.
