# Architecture

## Control plane

The user's Mac is the control plane. Codex invokes checked-in shell wrappers,
Git, GitHub CLI, and Brev CLI. No editor or manually operated remote terminal
is part of the workflow.

## Compute plane

One stoppable Brev GPU VM runs the official Isaac Launchable. The Launchable
starts Docker containers for:

- the Isaac Lab and Isaac Sim runtime;
- an nginx gateway;
- the authenticated browser viewer.

Training and evaluation run non-interactively inside the Isaac Lab container.
The viewer is only a human observation surface.

## Data flow

1. Source and documentation are committed to GitHub.
2. The remote checkout is synchronized through Git.
3. Headless training writes logs and checkpoints to persistent Brev storage.
4. Evaluation writes small machine-readable summaries.
5. Representative summaries and exact artifact paths are committed; large
   checkpoints, caches, and videos stay off Git.
6. Playback loads a selected checkpoint and streams through the Brev secure
   link.

## Trust and cost boundaries

- Provisioning requires an explicit cost approval gate.
- Brev secure links protect HTTP access with the user's NVIDIA login.
- No unauthenticated public viewer is created.
- Stopping ends GPU compute charges; persistent storage may continue to incur
  a smaller charge.
- Deletion of the instance or disk is a separate user-approved operation.
