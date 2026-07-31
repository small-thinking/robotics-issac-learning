"""Pure safety helpers for bounded DOFBOT gravity feed-forward."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

REQUIRED_GRAVITY_RUNTIME_APIS = (
    "get_gravity_compensation_forces",
    "set_dof_actuation_forces",
    "get_link_incoming_joint_force",
)


class GravityFeedForwardError(ValueError):
    """Raised when gravity feed-forward data is incomplete or unsafe."""


def _finite_numbers(values: Any, label: str) -> list[float]:
    if not isinstance(values, (list, tuple)):
        raise GravityFeedForwardError(f"{label} must be a list")
    converted: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise GravityFeedForwardError(
                f"{label}[{index}] must be numeric"
            )
        number = float(value)
        if not math.isfinite(number):
            raise GravityFeedForwardError(
                f"{label}[{index}] must be finite"
            )
        converted.append(number)
    return converted


def prepare_bounded_gravity_feed_forward(
    *,
    gravity_compensation_efforts: Any,
    dof_count: int,
    controlled_joint_ids: Sequence[int],
    enabled: bool,
    maximum_effort: float,
) -> dict[str, Any]:
    """Isolate, clamp, and zero-fill one articulation's feed-forward vector."""
    if isinstance(dof_count, bool) or not isinstance(dof_count, int):
        raise GravityFeedForwardError("dof_count must be an integer")
    if dof_count <= 0:
        raise GravityFeedForwardError("dof_count must be positive")
    if not isinstance(enabled, bool):
        raise GravityFeedForwardError("enabled must be boolean")
    if (
        isinstance(maximum_effort, bool)
        or not isinstance(maximum_effort, (int, float))
        or not math.isfinite(float(maximum_effort))
        or not 0.0 < float(maximum_effort) <= 5.2
    ):
        raise GravityFeedForwardError(
            "maximum_effort must be finite and in (0, 5.2]"
        )
    raw = _finite_numbers(
        gravity_compensation_efforts,
        "gravity_compensation_efforts",
    )
    if len(raw) != dof_count:
        raise GravityFeedForwardError(
            "gravity compensation width does not match articulation DOFs"
        )
    ids = list(controlled_joint_ids)
    if (
        not ids
        or len(set(ids)) != len(ids)
        or any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= dof_count
            for index in ids
        )
    ):
        raise GravityFeedForwardError(
            "controlled_joint_ids must be unique valid DOF indices"
        )

    limit = float(maximum_effort)
    applied = [0.0] * dof_count
    clipped_joint_ids: list[int] = []
    for index in ids:
        bounded = max(-limit, min(limit, raw[index]))
        if bounded != raw[index]:
            clipped_joint_ids.append(index)
        if enabled:
            applied[index] = bounded

    return {
        "enabled": enabled,
        "maximum_effort": limit,
        "raw_all_dof_efforts": raw,
        "raw_controlled_efforts": [raw[index] for index in ids],
        "applied_all_dof_efforts": applied,
        "applied_controlled_efforts": [applied[index] for index in ids],
        "clipped_controlled_joint_ids": clipped_joint_ids,
    }


def evaluate_gravity_feed_forward_telemetry(
    *,
    samples: Any,
    runtime_api_availability: Any,
    controlled_joint_ids: Sequence[int],
    feed_forward_enabled: bool,
    maximum_effort: float,
) -> dict[str, Any]:
    """Evaluate the machine telemetry required by the feed-forward gate."""
    if not isinstance(samples, list) or not samples:
        raise GravityFeedForwardError("samples must be a non-empty list")
    if not isinstance(runtime_api_availability, dict):
        raise GravityFeedForwardError(
            "runtime_api_availability must be an object"
        )
    if set(runtime_api_availability) != set(REQUIRED_GRAVITY_RUNTIME_APIS):
        raise GravityFeedForwardError(
            "runtime_api_availability must name all required APIs"
        )
    if any(
        not isinstance(value, bool)
        for value in runtime_api_availability.values()
    ):
        raise GravityFeedForwardError(
            "runtime API availability values must be boolean"
        )

    ids = list(controlled_joint_ids)
    all_applied: list[float] = []
    all_raw_controlled: list[float] = []
    clipped_sample_count = 0
    incoming_values: list[float] = []
    only_controlled = True
    baseline_zero = True
    for sample_index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise GravityFeedForwardError(
                f"samples[{sample_index}] must be an object"
            )
        raw_all = _finite_numbers(
            sample.get("raw_all_dof_efforts"),
            f"samples[{sample_index}].raw_all_dof_efforts",
        )
        applied = _finite_numbers(
            sample.get("applied_all_dof_efforts"),
            f"samples[{sample_index}].applied_all_dof_efforts",
        )
        if len(raw_all) != len(applied):
            raise GravityFeedForwardError(
                "raw and applied gravity effort widths must match"
            )
        if any(index < 0 or index >= len(applied) for index in ids):
            raise GravityFeedForwardError(
                "controlled_joint_ids do not fit telemetry width"
            )
        if sample.get("enabled") is not feed_forward_enabled:
            raise GravityFeedForwardError(
                "sample enabled flag differs from the case contract"
            )
        if float(sample.get("maximum_effort")) != float(maximum_effort):
            raise GravityFeedForwardError(
                "sample maximum effort differs from the case contract"
            )
        clipped = sample.get("clipped_controlled_joint_ids")
        if not isinstance(clipped, list) or any(
            index not in ids for index in clipped
        ):
            raise GravityFeedForwardError(
                "clipped_controlled_joint_ids are invalid"
            )
        clipped_sample_count += bool(clipped)
        all_raw_controlled.extend(raw_all[index] for index in ids)
        all_applied.extend(applied)
        only_controlled = only_controlled and all(
            abs(value) <= 1.0e-12
            for index, value in enumerate(applied)
            if index not in ids
        )
        baseline_zero = baseline_zero and all(
            abs(value) <= 1.0e-12 for value in applied
        )
        incoming_rows = sample.get("controlled_incoming_joint_forces")
        if not isinstance(incoming_rows, list) or len(incoming_rows) != len(ids):
            raise GravityFeedForwardError(
                "controlled incoming joint force rows must match controlled joints"
            )
        for row_index, row in enumerate(incoming_rows):
            values = _finite_numbers(
                row,
                (
                    f"samples[{sample_index}]."
                    f"controlled_incoming_joint_forces[{row_index}]"
                ),
            )
            if len(values) != 6:
                raise GravityFeedForwardError(
                    "each incoming joint force row must contain six values"
                )
            incoming_values.extend(values)

    limit = float(maximum_effort)
    maximum_applied = max((abs(value) for value in all_applied), default=0.0)
    checks = {
        "gravity_compensation_runtime_apis_available": all(
            runtime_api_availability.values()
        ),
        "gravity_compensation_values_finite": True,
        "incoming_joint_force_values_finite": bool(incoming_values),
        "feed_forward_effort_bounded": maximum_applied <= limit + 1.0e-9,
        "only_controlled_joints_receive_feed_forward": only_controlled,
        "baseline_case_applies_zero_feed_forward": (
            feed_forward_enabled or baseline_zero
        ),
    }
    return {
        "runtime_api_availability": dict(runtime_api_availability),
        "sample_count": len(samples),
        "feed_forward_enabled": feed_forward_enabled,
        "maximum_effort": limit,
        "maximum_absolute_raw_controlled_gravity_effort": max(
            (abs(value) for value in all_raw_controlled),
            default=0.0,
        ),
        "maximum_absolute_applied_feed_forward_effort": maximum_applied,
        "clipped_sample_count": clipped_sample_count,
        "checks": checks,
        "telemetry_complete": all(checks.values()),
    }
