# CartPole PPO 01: Reproduction

## Question

Can a fresh PPO run reproduce the official manager-based CartPole behavior
without pretrained weights or hidden resume state?

## Key commands

Train from scratch:

```bash
./isaaclab.sh -p scripts/reinforcement_learning/train.py \
  --rl_library=skrl \
  --task=Isaac-Cartpole-v0 \
  --algorithm=PPO \
  --seed=42 \
  --num_envs=4096 \
  --viz none
```

Inspect checkpoint provenance:

```bash
find logs/skrl/cartpole -type f -name 'agent_*.pt' -print
```

Evaluate one exact checkpoint:

```bash
./isaaclab.sh -p /workspace/robotics-issac-learning/tools/evaluate_cartpole.py \
  --policy=trained \
  --task=Isaac-Cartpole-v0 \
  --checkpoint=logs/skrl/cartpole/<run>/checkpoints/best_agent.pt \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=64 \
  --output=/workspace/robotics-issac-learning/artifacts/evaluations/trained_policy.json \
  --viz none
```

Play the evaluated policy:

```bash
./isaaclab.sh -p scripts/reinforcement_learning/play.py \
  --rl_library=skrl \
  --task=Isaac-Cartpole-v0 \
  --algorithm=PPO \
  --num_envs=1 \
  --checkpoint=logs/skrl/cartpole/<run>/checkpoints/best_agent.pt \
  --viz kit
```

## Result

The seed-42 local policy reached `269.44` mean steps, about `4.49` seconds at
60 Hz, with `22/25` episodes reaching the five-second time limit. The user
confirmed stable behavior in the Viewer.
