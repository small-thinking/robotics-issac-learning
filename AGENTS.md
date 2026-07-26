# Codex Instructions

This repository is operated primarily by Codex through command-line tools.
VS Code is not required.

## Project intent

- Brev is replaceable, stoppable cloud compute.
- Isaac Lab is the initial closed-loop learning environment, not the research goal.
- The user is experienced with ML and PyTorch and is new to robotics.
- The long-term focus is VLA post-training, reinforcement learning, robot data,
  modeling, evaluation, and failure-driven iteration.
- Preserve the repository spelling `robotics-issac-learning`; use the correct
  spelling `Isaac` everywhere else.

## Current phase

Phase 0: prove a visually inspectable random-policy to trained-policy CartPole
loop using the official Isaac Launchable.

## Canonical commands

```bash
make doctor
make search
make provision
make sync
make remote-setup
make smoke
make train
make play
make eval
make status
make stop
```

The verified Phase 0 task is `Isaac-Cartpole-Direct-v0`; the RL backend is skrl
PPO. Keep wrappers aligned with the installed Isaac Launchable rather than old
tutorial syntax.

## Safety boundaries

- Never create a billable instance without explicit cost approval.
- `make provision` must fail closed without approval and region confirmation.
- Never create multiple instances for Phase 0.
- Stop billable resources immediately after the requested work is complete.
- Do not delete instances or persistent disks without separate approval.
- Do not expose unauthenticated streaming endpoints publicly.
- Never commit secrets, `.env`, credentials, large checkpoints, caches, or videos.

## Durable records

- Update `docs/STATUS.md` after every material infrastructure transition.
- Append verified experiments to `docs/EXPERIMENTS.md`.
- Record architectural trade-offs in `docs/DECISIONS.md`.
- Record exact remote versions and commands in `docs/ENVIRONMENT.md` and
  `docs/RUNBOOK.md`.
