"""Pure contact-report reduction for DOFBOT pre-grasp safety gates."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from typing import Any


def resolve_monitored_path(path: str, monitored_paths: frozenset[str]) -> str | None:
    """Map a rigid-body or descendant collider path to its monitored owner."""
    matches = [
        candidate
        for candidate in monitored_paths
        if path == candidate or path.startswith(f"{candidate}/")
    ]
    return max(matches, key=len, default=None)


def normalized_contact_pair(
    actor0: str,
    actor1: str,
    monitored_paths: frozenset[str],
) -> tuple[str | None, str | None]:
    """Preserve pair ordering while normalizing descendant shape paths."""
    return (
        resolve_monitored_path(actor0, monitored_paths),
        resolve_monitored_path(actor1, monitored_paths),
    )


def maximum_monitored_contact_force_n(
    *,
    headers: Iterable[Any],
    contact_data: Sequence[Any],
    critical_paths: frozenset[str],
    physics_dt: float,
    decode_path: Callable[[Any], str],
) -> float:
    """Reduce per-contact impulses to the largest monitored actor force."""
    if not math.isfinite(physics_dt) or physics_dt <= 0.0:
        raise ValueError("physics_dt must be finite and positive")
    impulses_by_path: dict[str, list[float]] = {}
    for header in headers:
        actor0 = decode_path(header.actor0)
        actor1 = decode_path(header.actor1)
        owner0, owner1 = normalized_contact_pair(actor0, actor1, critical_paths)
        monitored = (
            (owner0, 1.0) if owner0 is not None else None,
            (owner1, -1.0) if owner1 is not None else None,
        )
        monitored = tuple(value for value in monitored if value is not None)
        if not monitored:
            continue
        impulse = [0.0, 0.0, 0.0]
        begin = header.contact_data_offset
        end = begin + header.num_contact_data
        for index in range(begin, end):
            sample = contact_data[index].impulse
            for axis in range(3):
                impulse[axis] += float(sample[axis])
        for path, sign in monitored:
            total = impulses_by_path.setdefault(path, [0.0, 0.0, 0.0])
            for axis in range(3):
                total[axis] += sign * impulse[axis]
    return max(
        (
            math.sqrt(sum(value * value for value in impulse)) / physics_dt
            for impulse in impulses_by_path.values()
        ),
        default=0.0,
    )
