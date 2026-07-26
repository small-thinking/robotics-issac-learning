#!/usr/bin/env python3
"""Summarize fixed-seed episode records into the Phase 1 evaluation schema."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    episodes = payload["episodes"]
    if not episodes:
        raise ValueError("evaluation contains no episodes")

    rewards = [float(episode["reward"]) for episode in episodes]
    lengths = [float(episode["length"]) for episode in episodes]
    reasons = Counter(str(episode.get("termination_reason", "unknown")) for episode in episodes)

    return {
        "policy": payload["policy"],
        "task": payload["task"],
        "checkpoint": payload.get("checkpoint"),
        "episode_count": len(episodes),
        "seeds": payload["seeds"],
        "mean_episode_reward": statistics.fmean(rewards),
        "std_episode_reward": statistics.pstdev(rewards),
        "mean_episode_length": statistics.fmean(lengths),
        "std_episode_length": statistics.pstdev(lengths),
        "termination_reason_counts": dict(sorted(reasons.items())),
        "episodes": episodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text())
    result = summarize(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
