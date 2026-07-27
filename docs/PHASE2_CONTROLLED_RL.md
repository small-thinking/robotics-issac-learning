# Phase 2: Controlled RL Understanding

The original one-reward-term proposal has been expanded into a preregistered,
paper-style sensitivity study. The canonical plan, 9-variant matrix, metrics,
data contract, charts, execution waves, and cost gates are in
[`PHASE2_STUDY_PROTOCOL.md`](PHASE2_STUDY_PROTOCOL.md). The machine-readable
matrix is
[`experiments/01_cartpole_ppo/variants.json`](../experiments/01_cartpole_ppo/variants.json).

## Completion

Phase 2 is complete: all 27 trained-policy cells, 9 screening sweeps, and 9
final stress evaluations succeeded. The reviewed report and figures are in
[`artifacts/phase2/`](../artifacts/phase2/README.md). The main result is that
direct velocity observation was essential; four-frame position history
recovered two of three seeds but remained brittle. Reward/action changes mostly
altered control style, while the wide training boundary produced one
catastrophic seed.

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

## Step 3: Run the controlled factor study

The installed manager-based CartPole config contains:

```python
cart_vel = RewTerm(
    func=mdp.joint_vel_l1,
    weight=-0.01,
    ...
)
```

The reward comparison remains part of the study:

- baseline: `cart_vel.weight = -0.01`;
- ablation: `cart_vel.weight = 0.0`.

Hypothesis: removing the cart-velocity penalty will preserve much of the
balancing success while increasing cart velocity and corrective activity.

It is joined by controlled observation, action-authority, and training-boundary
comparisons. Each factor has three levels including the shared baseline, and
all final results use three training seeds. The hypothesis fails if the
telemetry does not show a consistent movement increase across seeds. A more
active Viewer clip alone is not enough.

Source:
[Isaac Lab v3.0.0-beta2.patch1 manager-based CartPole config](https://github.com/isaac-sim/IsaacLab/blob/v3.0.0-beta2.patch1/source/isaaclab_tasks/isaaclab_tasks/manager_based/classic/cartpole/cartpole_env_cfg.py)

## Acceptance

Phase 2 is complete when:

- the unchanged baseline has results from three training seeds;
- all nine variants use the preregistered common evaluation protocol;
- the new control metrics are saved in machine-readable artifacts;
- the observed difference is reported with per-seed values, not only an
  aggregate mean;
- failed/missing runs remain visible in the run registry;
- every chart can be regenerated from committed derived data;
- one Viewer comparison is used to interpret, not replace, the measurements.

## Cost gate

Implement and test telemetry locally before restarting Brev. The next paid
window should first run one override/telemetry smoke test. The complete matrix
starts only after that smoke passes, a live price is checked, and the user gives
new explicit approval. Stop compute immediately after artifact validation.

This gate was satisfied for the completed run. The L4 instance was stopped
after local archive checksums matched the remote checksums. Any Phase 3 compute
requires a new approval; the Phase 2 approval does not carry forward.
