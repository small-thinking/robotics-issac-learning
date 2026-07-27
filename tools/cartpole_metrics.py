"""Pure-Python metrics for CartPole evaluation and learning curves."""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def fixed_episode_env_ids(num_envs: int, episodes_per_seed: int) -> tuple[int, ...]:
    """Select environments whose first episode forms the evaluation sample.

    Preselecting IDs avoids bias toward whichever parallel environments fail
    first. Each selected environment must contribute exactly one episode.
    """

    if num_envs <= 0:
        raise ValueError("num_envs must be positive")
    if episodes_per_seed <= 0:
        raise ValueError("episodes_per_seed must be positive")
    if num_envs < episodes_per_seed:
        raise ValueError("num_envs must be at least episodes_per_seed")
    return tuple(range(episodes_per_seed))


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

    aggregate_metrics = {
        "mean_upright_fraction_12deg": "upright_fraction_12deg",
        "mean_longest_upright_seconds": "longest_upright_seconds",
        "mean_pole_angle_rms_radians": "pole_angle_rms_radians",
        "mean_cart_position_rms": "cart_position_rms",
        "mean_max_abs_cart_position": "max_abs_cart_position",
        "mean_abs_cart_velocity": "mean_abs_cart_velocity",
        "mean_pole_angular_velocity_rms": "pole_angular_velocity_rms",
        "mean_abs_normalized_action": "mean_abs_normalized_action",
        "mean_abs_requested_effort": "mean_abs_requested_effort",
        "mean_abs_action_delta": "mean_abs_action_delta",
        "mean_action_total_variation": "action_total_variation",
        "mean_action_sign_changes_per_second": "action_sign_changes_per_second",
        "mean_action_saturation_fraction": "action_saturation_fraction",
    }
    for output_name, episode_name in aggregate_metrics.items():
        if all(episode_name in record for record in records):
            result[output_name] = statistics.fmean(
                float(record[episode_name]) for record in records
            )
    if all("robust_success" in record for record in records):
        result["robust_success_fraction"] = statistics.fmean(
            float(record["robust_success"]) for record in records
        )

    if checkpoint is not None:
        vector_steps = checkpoint_vector_steps(checkpoint)
        result["checkpoint_vector_steps"] = vector_steps
        if vector_steps is not None and training_num_envs is not None:
            result["training_transitions"] = vector_steps * training_num_envs

    return result
