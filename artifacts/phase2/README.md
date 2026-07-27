# Phase 2 Artifact Contract

This directory will contain compact, reviewed evidence from the preregistered
CartPole controlled study. The protocol is
[`docs/PHASE2_STUDY_PROTOCOL.md`](../../docs/PHASE2_STUDY_PROTOCOL.md).
Each attempted run follows
[`run_manifest.schema.json`](../../experiments/01_cartpole_ppo/run_manifest.schema.json).

Expected committed layout after execution:

```text
phase2/
  manifests/              one immutable JSON manifest per attempted run
  data/
    run_registry.csv
    episode_metrics.csv
    training_curves.csv
    run_metrics.csv
    paired_effects.csv
    condition_summary.csv
    trace_selection.csv
  plots/                  figures generated only from phase2/data
  report/                 paper-style study report
```

Large checkpoints, complete per-step traces, and unreviewed logs are not
committed. Their persistent-storage/archive locations and SHA-256 checksums
belong in the run manifests. Failed and partial attempts remain in
`run_registry.csv`; charts must show missing data rather than silently dropping
it.
