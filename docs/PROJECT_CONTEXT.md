# Project Context

The user has strong machine-learning and PyTorch experience and is learning
robotics through simulation-first experiments.

The initial workflow is cloud-based and visually inspectable. Codex orchestrates
Brev and Isaac through CLI tools; the user intervenes only for account or billing
approval and visual validation.

The long-term target is robotics ML focused on:

- VLA post-training;
- reinforcement learning;
- robot-data preparation;
- modeling;
- closed-loop evaluation;
- failure-driven data collection.

The concrete robot target is the user's Yahboom DOFBOT with Jetson Nano. The
current high-level objective is to reach simple, measurable,
camera-closed-loop tabletop manipulation in simulation and later behind safety
gates on the real robot. Software controls the real arm through vendor-level
servo angle/time commands; it does not assume access to motor-current control
or the servos' internal loops.

Transferable robot-learning concepts matter more than mastering NVIDIA-specific
APIs. Later phases progress toward manipulation, vision, imitation learning,
lightweight VLA post-training, and optional real hardware.

## Current verified state

- Phase 0 simulator/pretrained-policy acceptance: complete.
- Phase 1 PPO-from-scratch reproduction: complete.
- Phase 2 controlled RL study: complete; 27/27 trained-policy cells succeeded.
- Canonical task: `Isaac-Cartpole-v0` (manager-based).
- RL stack: skrl PPO on Isaac Launchable `3.0.0-beta2-post1`.
- Local training seed: `42`; parallel environments: `4096`.
- Local checkpoint result: `269.44` mean control steps, about `4.49` seconds
  at 60 Hz, with `22/25` episodes reaching the five-second time limit.
- Visual acceptance: complete; the policy balanced stably with relatively
  sparse cart corrections.
- Checkpoint learning curve: complete; ten checkpoints show a sharp improvement
  around 3-5M transitions and a plateau near 4.8 seconds after about 6.9M.
- Final numbered checkpoint: `24/25` time-limit episodes, outperforming the
  trainer-selected `best_agent.pt` under the fixed-seed acceptance metric.
- Phase 2 final evidence: 675 fixed 30-second episodes across 9 variants and 3
  training seeds, plus 90 checkpoint evaluations.
- Phase 2 main result: direct velocity observation was essential; four-frame
  history recovered two of three seeds but remained brittle. Reward/action
  variants largely retained success, while a wide training boundary produced
  one catastrophic seed.
- Brev `isaac-launchable-f150a5`: stopped; persistent disk retained.

The manager-based task and `Isaac-Cartpole-Direct-v0` are different MDP and
checkpoint contracts. Do not reuse checkpoints, reward comparisons, or PPO
settings across them.

## Immediate next work

The CartPole stage is complete. The canonical next-stage plan is
`experiments/02_dofbot/README.md`.

1. Goal 1: load and inspect NVIDIA's official DOFBOT USD, save the asset
   contract, and confirm the stationary model in the secure Viewer.
2. Goal 2: command small, hard-coded joint movements and verify axis, sign,
   limit margin, and reset.
3. Goal 3: read and save one deterministic onboard RGB observation.

Do not introduce PPO, SFT, imitation learning, a CV training pipeline, or real
hardware commands during these three infrastructure goals. The older
OmniIsaacGymEnvs DOFBOT Reacher project is a design reference only.

No GPU should be started for local code, tests, documentation, or chart
rendering. Any remote run requires a new cost quote, explicit approval, and
prompt shutdown after validation.

## Sources of truth

- `AGENTS.md`: automatic operating rules for Codex.
- `docs/STATUS.md`: latest infrastructure and milestone status.
- `experiments/README.md`: numbered learning sequence and key commands.
- `docs/EXPERIMENTS.md`: append-only successful and failed run record.
- `docs/LESSONS_LEARNED.md`: pitfalls that must not be repeated.
- `artifacts/evaluations/`: small reviewed machine-readable results.
- `artifacts/phase2/`: manifests, episode data, derived tables, figures, and
  the controlled-study report.
- `experiments/02_dofbot/README.md`: DOFBOT goals, gates, and later milestones.
