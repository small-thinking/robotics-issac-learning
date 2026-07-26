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

Phase 1 is complete. A fresh manager-based `Isaac-Cartpole-v0` skrl PPO run
from seed 42 reached `269.44` mean control steps, `22/25` time-limit episodes,
and passed user visual inspection. Its exact checkpoint and aggregate metrics
are recorded under `docs/PHASE1_PPO_REPRODUCTION.md` and
`artifacts/evaluations/phase1_reproduction_summary.json`.

The Brev instance is stopped; persistent storage is retained. Checkpoint
learning-curve tooling is prepared, but the actual remote sweep has not run.
The immediate zero-cost task is control telemetry. The next paid window
requires fresh explicit approval.

## Session startup

At the start of a new Codex session:

1. Read `docs/PROJECT_CONTEXT.md`, `docs/STATUS.md`, `docs/ROADMAP.md`,
   `docs/LESSONS_LEARNED.md`, and `experiments/README.md`.
2. Inspect `git status --short --branch` before editing.
3. Treat committed evaluation artifacts as evidence and do not reconstruct
   missing episode data.
4. Verify live Brev state with `brev ls`; never infer it from an older document.
5. Continue the numbered experiment sequence instead of rerunning a completed
   phase unless a regression or explicit reproduction requires it.

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
make learning-curve
make status
make stop
```

The canonical training/evaluation task is the manager-based
`Isaac-Cartpole-v0`; the RL backend is skrl PPO. `Isaac-Cartpole-Direct-v0` is
a separate environment implementation and must not be used as a drop-in
checkpoint or metric comparison. Keep wrappers aligned with the installed
Isaac Launchable rather than old tutorial syntax.

## Command visibility

- Surface the commands that teach transferable robotics-ML workflow:
  task/MDP inspection, random baseline, PPO training, checkpoint selection,
  fixed-seed evaluation, and policy playback.
- Summarize Brev, Docker, sync, and other platform plumbing unless it is itself
  under diagnosis; do not make it the learning narrative.
- Use the checked-in remote wrappers for operational reproducibility.
- Use `REMOTE_DRY_RUN=1` or `make show-*` when previewing without remote access.
- Stream training output and preserve exact commands, configs, checkpoints,
  metrics, and conclusions in durable project records.
- Keep transferable commands and experiment logic in numbered folders under
  `experiments/`; keep Brev/Docker plumbing out of those learning steps.
- Do not include credentials or secrets in command transcripts.

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
