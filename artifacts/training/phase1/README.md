# Phase 1 Training Evidence

These are the compact training records from the fresh seed-42 manager-based
PPO run on `Isaac-Cartpole-v0`.

| File | Purpose | SHA-256 |
| --- | --- | --- |
| `train_console.log` | exact streamed training console, including runtime and checkpoint writes | `6f37d32260e72a1c63ad4a28dcd89853120ed04df79196c569ec5b7cfcecd07c` |
| `events.out.tfevents.1785082190.brev-92xbacz46.605.0` | raw TensorBoard scalar event stream | `96f327ad5ef78d9a916b62032f4f5eab33dffbb17fe86381fbc0bf41171b329e` |
| `agent.yaml` | resolved skrl PPO agent configuration | `122f724260011cbf9a7573486183bfc8f4553e2c3429b4416c1b87f29ed09f06` |
| `env.yaml` | resolved manager-based CartPole environment configuration | `cc8b0f992a66bd4674da43606d010497de36c99146c62fbe688d6e2bb16951d7` |

The event stream contains 100 samples for each of 22 scalar tags, including
reward components, episode reward and length, policy/value losses, policy
standard deviation, learning rate, inference time, environment stepping time,
and update time.

Inspect the full training curves locally with:

```bash
uv run --with tensorboard tensorboard \
  --logdir artifacts/training/phase1 \
  --port 6006
```

The independently evaluated checkpoint curve lives in
`artifacts/evaluations/phase1_learning_curve.json`; it is the behavioral source
of truth. TensorBoard metrics help explain optimization but do not replace the
fixed-seed evaluator.
