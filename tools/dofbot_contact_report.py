"""Pure contact-report reduction for DOFBOT pre-grasp safety gates."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from typing import Any


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
        monitored = (
            (actor0, 1.0) if actor0 in critical_paths else None,
            (actor1, -1.0) if actor1 in critical_paths else None,
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
