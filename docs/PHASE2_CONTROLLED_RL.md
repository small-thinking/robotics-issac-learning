# Phase 2: Controlled RL Understanding

## Goal

Turn a visible policy-style difference into a controlled experiment about how
reward shaping changes learned feedback control.

The Phase 1 local policy balanced successfully with comparatively sparse,
anticipatory cart corrections. The official policy also balanced successfully
but appeared to correct more continuously. Similar task success does not imply
identical control behavior.

## Step 1: Measure the behavior seen in the Viewer

Extend evaluation with aggregate control metrics:

- mean absolute pole angle;
- mean absolute cart velocity;
- mean absolute action;
- mean absolute action change;
- action sign changes per second;
- maximum absolute cart displacement.

Episode survival says whether the controller succeeds. These metrics describe
*how* it succeeds and make “moves less” or “corrects continuously” testable.

Implement and test the aggregation locally before starting another GPU.

## Step 2: Check training-seed robustness

Repeat the locked Phase 1 recipe with two additional training seeds. Do not
change the task, PPO config, number of environments, horizon, or evaluation
seeds.

For each run, record:

- exact training seed and checkpoint;
- fixed-seed reward, episode length, and termination counts;
- whether it meets the existing Phase 1 gates;
- the control-style telemetry defined above.

This separates a repeatable effect from one seed's policy style before changing
the reward.

## Step 3: Run one reward ablation

The installed manager-based CartPole config contains:

```python
cart_vel = RewTerm(
    func=mdp.joint_vel_l1,
    weight=-0.01,
    ...
)
```

Keep every other setting fixed and compare:

- baseline: `cart_vel.weight = -0.01`;
- ablation: `cart_vel.weight = 0.0`.

Hypothesis: removing the cart-velocity penalty will preserve much of the
balancing success while increasing cart velocity and corrective activity.

The hypothesis fails if the telemetry does not show a consistent movement
increase across seeds. A more active Viewer clip alone is not enough.

Source:
[Isaac Lab v3.0.0-beta2.patch1 manager-based CartPole config](https://github.com/isaac-sim/IsaacLab/blob/v3.0.0-beta2.patch1/source/isaaclab_tasks/isaaclab_tasks/manager_based/classic/cartpole/cartpole_env_cfg.py)

## Acceptance

Phase 2A is complete when:

- the unchanged baseline has results from three training seeds;
- baseline and ablation use the same evaluation protocol;
- the new control metrics are saved in machine-readable artifacts;
- the observed difference is reported with per-seed values, not only an
  aggregate mean;
- one Viewer comparison is used to interpret, not replace, the measurements.

## Cost gate

Implement and test telemetry locally before restarting Brev. The next paid
window should run the prepared seed repetitions and ablation only after a new
explicit approval, then stop the instance immediately after validation.
