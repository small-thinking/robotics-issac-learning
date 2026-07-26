# Roadmap

Each phase ends in a reproducible artifact and evaluation gate. Moving forward
is based on evidence, not only on a convincing Viewer clip.

## Phase 0 — Visible simulator loop (complete)

- Provision one stoppable L4 instance with explicit cost approval.
- Compare random behavior with an official pretrained skrl PPO policy.
- Record the exact software image, checkpoint, fixed-seed metrics, and visual
  confirmation.
- Stop GPU compute without deleting the persistent disk.

Acceptance evidence: on `Isaac-Cartpole-v0`, the official checkpoint reached
268.88 mean episode steps and 22/25 time-limit episodes versus 188.44 and 0/25
for random. The user confirmed the trained pole was almost continuously
balanced.

## Phase 1 — Reproduce PPO from scratch (next)

Goal: prove that our own training run, not a downloaded checkpoint, reaches the
same behavior.

1. Pin the same Launchable image and task: `Isaac-Cartpole-v0`.
2. Capture the resolved environment and skrl PPO config before training.
3. Evaluate random policy with the existing 25-episode fixed-seed protocol.
4. Train one seed headlessly with 4096 vectorized environments, using the
   installed manager-based task's official PPO config rather than carrying over
   Direct-task rollout, normalization, reward-scale, or learning-rate settings.
5. Evaluate every retained checkpoint on the same task and seeds.
6. Play only the best qualifying checkpoint in the secure Viewer.
7. Repeat with two more training seeds after the one-seed MVP passes.

One-seed acceptance gates:

- mean episode length at least 250 steps;
- at least 20/25 episodes reach the time limit;
- mean reward greater than zero;
- checkpoint provenance points to the new local training run;
- visually stable behavior confirmed in the secure Viewer.

The target is equivalent behavior, not identical weights or an identical
learning curve. If the first run fails, inspect the learning curve and resolved
config before increasing compute.

### What 4096 parallel environments means

It is 4096 independent simulator states sharing one policy, not a batch of 4096
pre-existing examples and not 4096 separately trained models. With the
observed skrl rollout length of 32, one collection cycle yields
`4096 x 32 = 131,072` transitions. PPO computes returns/advantages along each
environment's time axis with termination masks, flattens the transitions,
shuffles them into minibatches, and applies all gradient updates to one shared
actor-critic.

## Phase 2 — Controlled RL understanding

- Make one observation, action, reward, or termination change at a time.
- Compare PPO learning curves and fixed-seed outcomes against the Phase 1
  baseline.
- Add checkpoint selection and regression thresholds to the CLI workflow.
- Persist compact metrics and config snapshots in Git; keep large checkpoints
  on remote storage or an artifact store.

## Phase 3 — Robot-arm state-based control

- Move to Franka reach, then cube lift, using proprioceptive state first.
- Inspect frames, joint limits, action scaling, resets, contacts, and success
  definitions.
- Establish scripted/random and PPO or imitation baselines before adding
  vision.

## Phase 4 — Demonstrations and imitation learning

- Collect or import a small, versioned demonstration set.
- Validate observation/action alignment and episode boundaries.
- Train behavior cloning, then ACT or Diffusion Policy.
- Evaluate task success and characterize failures, not only training loss.

## Phase 5 — Vision and multimodal policies

- Add calibrated RGB observations and a deterministic data pipeline.
- Compare frozen visual features with end-to-end visual policies.
- Add language task descriptions only after state and vision baselines are
  reliable.

## Phase 6 — Lightweight VLA post-training

- Fine-tune a small open VLA or action head on the validated demonstration
  schema.
- Measure closed-loop success, robustness, latency, and distribution shift.
- Publish checkpoint cards and evaluation provenance to Hugging Face only after
  local artifact semantics are stable.

## Phase 7 — Failure-driven improvement

- Cluster rollout failures and turn them into targeted data or environment
  interventions.
- Retrain with curated failures, corrective demonstrations, or carefully gated
  RL post-training.
- Keep a held-out scenario suite to detect regressions.

## Phase 8 — Optional real-robot bridge

- Choose low-cost hardware only after the simulated manipulation policy and
  safety envelope are measurable.
- Add teleoperation, emergency-stop, rate/force limits, calibration, and
  sim-to-real validation before autonomous execution.
