# Step 00: Task Sanity and Random Baseline

## Question

Does the environment expose the expected MDP and behave sensibly before
learning?

## Key commands

Inspect registered task identity:

```bash
./isaaclab.sh -p scripts/environments/list_envs.py --keyword Cartpole
```

Run one visible random policy:

```bash
./isaaclab.sh -p scripts/environments/random_agent.py \
  --task=Isaac-Cartpole-v0 \
  --num_envs=1
```

Measure the random baseline under fixed seeds:

```bash
./isaaclab.sh -p /workspace/robotics-issac-learning/tools/evaluate_cartpole.py \
  --policy=random \
  --task=Isaac-Cartpole-v0 \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=64 \
  --output=/workspace/robotics-issac-learning/artifacts/evaluations/random_policy.json \
  --viz none
```

## Result

The accepted manager-based random baseline reached `188.44` mean control steps,
equivalent to about `3.14` seconds at 60 Hz, with `0/25` episodes reaching the
five-second time limit.
