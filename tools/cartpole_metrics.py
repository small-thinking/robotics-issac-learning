"""Pure-Python metrics for CartPole evaluation and learning curves."""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def checkpoint_vector_steps(checkpoint: Path | str) -> int | None:
    """Read skrl's vector-step counter from an ``agent_<step>.pt`` filename."""

    path = Path(checkpoint)
    stem = path.stem
    if not stem.startswith("agent_"):
        return None
    suffix = stem.removeprefix("agent_")
    return int(suffix) if suffix.isdigit() else None


def summarize_episodes(
    *,
    policy: str,
    task: str,
    checkpoint: Path | str | None,
    seeds: list[int],
    episodes: Iterable[dict[str, Any]],
    control_hz: float,
    training_num_envs: int | None = None,
) -> dict[str, Any]:
    """Summarize one policy under one fixed-seed evaluation contract."""

    records = list(episodes)
    if not records:
        raise ValueError("evaluation contains no episodes")
    if control_hz <= 0:
        raise ValueError("control_hz must be positive")

    rewards = [float(episode["reward"]) for episode in records]
    lengths = [float(episode["length"]) for episode in records]
    reasons = Counter(str(episode.get("termination_reason", "unknown")) for episode in records)
    time_limit_count = reasons["time_limit"]
    checkpoint_path = str(Path(checkpoint).resolve()) if checkpoint is not None else None

    result: dict[str, Any] = {
        "policy": policy,
        "task": task,
        "checkpoint": checkpoint_path,
        "episode_count": len(records),
        "seeds": seeds,
        "control_hz": control_hz,
        "mean_episode_reward": statistics.fmean(rewards),
        "std_episode_reward": statistics.pstdev(rewards),
        "mean_episode_length": statistics.fmean(lengths),
        "std_episode_length": statistics.pstdev(lengths),
        "mean_balance_seconds": statistics.fmean(lengths) / control_hz,
        "time_limit_episode_count": time_limit_count,
        "time_limit_fraction": time_limit_count / len(records),
        "termination_reason_counts": dict(sorted(reasons.items())),
        "episodes": records,
    }

    if checkpoint is not None:
        vector_steps = checkpoint_vector_steps(checkpoint)
        result["checkpoint_vector_steps"] = vector_steps
        if vector_steps is not None and training_num_envs is not None:
            result["training_transitions"] = vector_steps * training_num_envs

    return result
