# Artifacts

Large checkpoints, videos, and caches remain in the Brev persistent workspace
and are not committed.

Small evaluation summaries may be recorded under `artifacts/evaluations/`.
`phase0_acceptance_summary.json` contains only aggregate metrics captured from
the remote evaluator; it intentionally does not reconstruct or invent
per-episode records that were not copied before the instance stopped.

Compact, reviewed training evidence may be stored under `artifacts/training/`.
Phase 1 preserves the exact console log, raw TensorBoard scalar stream, and
resolved agent/environment configs. Checkpoints remain remote because they are
large model binaries.

Reviewed learning-curve figures may be stored under `artifacts/plots/`. The
corresponding JSON remains the source of truth; plots must be rendered from
that artifact rather than edited by hand.

## Image storage

Binary image assets are tracked by Git LFS according to the repository's
`.gitattributes`. Run `git lfs install` once on each development machine; after
that, normal `git add`, `git commit`, and `git push` commands store matching
images through LFS automatically.

SVG files remain in regular Git because they are text, compact, and reviewable
as diffs. If a matching binary image was already committed before an extension
was added to `.gitattributes`, stage its current version again with:

```bash
git add --renormalize path/to/image
```

This converts the file at the current tip without rewriting repository history.
History rewrites require separate review and coordination.

Optional live command transcripts may be written below `artifacts/commands/`.
They are ignored by Git because they can be verbose and environment-specific.
Copy only reviewed, non-secret canonical commands into `docs/EXPERIMENTS.md`.
