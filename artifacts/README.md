# Artifacts

Large checkpoints, videos, caches, and logs remain in the Brev persistent
workspace and are not committed.

Small evaluation summaries may be recorded under `artifacts/evaluations/`.
`phase0_acceptance_summary.json` contains only aggregate metrics captured from
the remote evaluator; it intentionally does not reconstruct or invent
per-episode records that were not copied before the instance stopped.

Reviewed learning-curve figures may be stored under `artifacts/plots/`. The
corresponding JSON remains the source of truth; plots must be rendered from
that artifact rather than edited by hand.

Optional live command transcripts may be written below `artifacts/commands/`.
They are ignored by Git because they can be verbose and environment-specific.
Copy only reviewed, non-secret canonical commands into `docs/EXPERIMENTS.md`.
