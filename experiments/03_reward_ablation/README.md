# Step 03: Cart-Velocity Reward Ablation

## Question

Does the cart-velocity penalty explain why one successful policy makes sparse,
anticipatory corrections while another moves more continuously?

## Controlled change

Keep the task, observations, actions, terminations, PPO config, seeds, training
horizon, and evaluation protocol fixed. Change only:

```text
baseline: cart_vel.weight = -0.01
ablation: cart_vel.weight = 0.0
```

## Measurements

- mean balance seconds;
- five-second time-limit fraction;
- mean absolute pole angle;
- mean absolute cart velocity;
- mean absolute action and action change;
- action sign changes per second.

## Hypothesis

Removing the cart-velocity penalty increases movement and corrective activity
without necessarily improving survival. The hypothesis is accepted only if the
control telemetry changes consistently across training seeds.

## Current status

The experiment design is locked, but the reward override and control telemetry
are not yet implemented. Do not start a paid run until both are locally tested.
