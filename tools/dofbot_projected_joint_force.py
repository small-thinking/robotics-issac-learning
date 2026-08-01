"""Pure validation and summary helpers for PhysX projected joint force."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

PROJECTED_JOINT_FORCE_SEMANTICS = (
    "PhysX get_dof_projected_joint_forces projects each link incoming joint "
    "force onto the corresponding DOF motion direction. It is the active "
    "component of the measured joint force, not an isolated drive-torque "
    "sensor. Interpret it beside gravity feed-forward and the implicit "
    "actuator PD estimates."
)

IMPLICIT_ACTUATOR_TORQUE_SEMANTICS = (
    "Isaac Lab ImplicitActuator computed_torque and applied_torque are "
    "approximate PD estimates; they are not measured PhysX solver effort."
)


def _finite_vector(value: Any, width: int) -> list[float] | None:
    if not isinstance(value, list) or len(value) != width:
        return None
    converted: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        converted.append(number)
    return converted


def _per_joint_extreme(
    rows: Sequence[Sequence[float]],
    *,
    reducer: str,
) -> list[float]:
    if reducer == "maximum_absolute":
        return [
            max(abs(row[index]) for row in rows)
            for index in range(len(rows[0]))
        ]
    if reducer == "minimum":
        return [
            min(row[index] for row in rows)
            for index in range(len(rows[0]))
        ]
    if reducer == "maximum":
        return [
            max(row[index] for row in rows)
            for index in range(len(rows[0]))
        ]
    raise ValueError(f"unknown reducer: {reducer}")


def summarize_projected_joint_force_telemetry(
    *,
    observations: Any,
    controlled_joint_names: Sequence[str],
) -> dict[str, Any]:
    """Summarize the DF-030 discriminator without changing control.

    Malformed or missing per-observation telemetry becomes a failed
    availability check rather than an exception. This preserves the rest of a
    machine-failure artifact for diagnosis.
    """
    joint_names = list(controlled_joint_names)
    if not joint_names or any(
        not isinstance(name, str) or not name for name in joint_names
    ):
        raise ValueError("controlled_joint_names must be non-empty strings")
    if len(set(joint_names)) != len(joint_names):
        raise ValueError("controlled_joint_names must be unique")
    if not isinstance(observations, list) or not observations:
        raise ValueError("observations must be a non-empty list")

    width = len(joint_names)
    projected_rows: list[list[float]] = []
    computed_rows: list[list[float]] = []
    applied_rows: list[list[float]] = []
    issues: list[dict[str, Any]] = []
    for observation_index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            issues.append(
                {
                    "observation_index": observation_index,
                    "step_index": None,
                    "invalid_fields": ["observation"],
                }
            )
            continue
        invalid_fields: list[str] = []
        projected = _finite_vector(
            observation.get("physx_projected_joint_forces"), width
        )
        computed = _finite_vector(observation.get("computed_torque"), width)
        applied = _finite_vector(observation.get("applied_torque"), width)
        if projected is None:
            invalid_fields.append("physx_projected_joint_forces")
        else:
            projected_rows.append(projected)
        if computed is None:
            invalid_fields.append("computed_torque")
        else:
            computed_rows.append(computed)
        if applied is None:
            invalid_fields.append("applied_torque")
        else:
            applied_rows.append(applied)
        if invalid_fields:
            issues.append(
                {
                    "observation_index": observation_index,
                    "step_index": observation.get("step_index"),
                    "invalid_fields": invalid_fields,
                }
            )

    observation_count = len(observations)
    projected_complete = len(projected_rows) == observation_count
    pd_estimates_complete = (
        len(computed_rows) == observation_count
        and len(applied_rows) == observation_count
    )
    comparable = projected_complete and pd_estimates_complete

    projected_minus_computed = (
        [
            [
                projected - computed
                for projected, computed in zip(p_row, c_row, strict=True)
            ]
            for p_row, c_row in zip(projected_rows, computed_rows, strict=True)
        ]
        if comparable
        else None
    )
    projected_minus_applied = (
        [
            [
                projected - applied
                for projected, applied in zip(p_row, a_row, strict=True)
            ]
            for p_row, a_row in zip(projected_rows, applied_rows, strict=True)
        ]
        if comparable
        else None
    )

    return {
        "controlled_joint_names": joint_names,
        "observation_count": observation_count,
        "physx_projected_joint_force_sample_count": len(projected_rows),
        "implicit_actuator_pd_estimate_sample_count": min(
            len(computed_rows), len(applied_rows)
        ),
        "checks": {
            "physx_projected_joint_force_telemetry_available_for_every_observation": (
                projected_complete
            ),
            "implicit_actuator_pd_estimate_telemetry_available_for_every_observation": (
                pd_estimates_complete
            ),
            "projected_force_and_pd_estimates_are_sample_aligned": comparable,
        },
        "telemetry_issues": issues,
        "final_physx_projected_joint_forces": (
            projected_rows[-1] if projected_complete else None
        ),
        "maximum_absolute_physx_projected_joint_forces": (
            _per_joint_extreme(projected_rows, reducer="maximum_absolute")
            if projected_complete
            else None
        ),
        "minimum_physx_projected_joint_forces": (
            _per_joint_extreme(projected_rows, reducer="minimum")
            if projected_complete
            else None
        ),
        "maximum_physx_projected_joint_forces": (
            _per_joint_extreme(projected_rows, reducer="maximum")
            if projected_complete
            else None
        ),
        "final_implicit_actuator_computed_torque": (
            computed_rows[-1] if pd_estimates_complete else None
        ),
        "final_implicit_actuator_applied_torque": (
            applied_rows[-1] if pd_estimates_complete else None
        ),
        "maximum_absolute_implicit_actuator_computed_torque": (
            _per_joint_extreme(computed_rows, reducer="maximum_absolute")
            if pd_estimates_complete
            else None
        ),
        "maximum_absolute_implicit_actuator_applied_torque": (
            _per_joint_extreme(applied_rows, reducer="maximum_absolute")
            if pd_estimates_complete
            else None
        ),
        "maximum_absolute_projected_minus_computed": (
            _per_joint_extreme(
                projected_minus_computed, reducer="maximum_absolute"
            )
            if projected_minus_computed is not None
            else None
        ),
        "maximum_absolute_projected_minus_applied": (
            _per_joint_extreme(
                projected_minus_applied, reducer="maximum_absolute"
            )
            if projected_minus_applied is not None
            else None
        ),
        "semantics": {
            "physx_projected_joint_forces": PROJECTED_JOINT_FORCE_SEMANTICS,
            "implicit_actuator_torque_buffers": (
                IMPLICIT_ACTUATOR_TORQUE_SEMANTICS
            ),
            "interpretation_boundary": (
                "The projected force can discriminate the active joint-force "
                "balance, but it does not by itself isolate or prove the "
                "implicit drive torque applied by PhysX."
            ),
        },
    }
