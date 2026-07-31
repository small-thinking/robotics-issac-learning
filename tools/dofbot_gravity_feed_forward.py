"""Pure safety helpers for bounded DOFBOT gravity feed-forward."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .dofbot_actuator_calibration import (
        GRAVITY_FEED_FORWARD_CASE_NAMES,
        load_actuator_calibration_config,
    )
    from .dofbot_control_api import CONTROLLED_JOINT_NAMES
except ImportError:
    from dofbot_actuator_calibration import (
        GRAVITY_FEED_FORWARD_CASE_NAMES,
        load_actuator_calibration_config,
    )
    from dofbot_control_api import CONTROLLED_JOINT_NAMES

REQUIRED_GRAVITY_RUNTIME_APIS = (
    "get_gravity_compensation_forces",
    "set_dof_actuation_forces",
    "get_link_incoming_joint_force",
)
ACCEPTED_GRAVITY_FEED_FORWARD_CONFIG_SHA256 = (
    "59a4a0ece5bb78f6e54cc8f871980fbb14c8ada96f87ffdba4f4386a0bd1efef"
)
ACCEPTED_GRAVITY_FEED_FORWARD_RESULT_SHA256 = (
    "a837f2b77ba32bd10d357f9c6b36db826affab1174fbfd05bbdfe2427617a42f"
)


class GravityFeedForwardError(ValueError):
    """Raised when gravity feed-forward data is incomplete or unsafe."""


@dataclass(frozen=True)
class AcceptedGravityFeedForwardRuntime:
    """Machine-evidence-bound actuator settings selected for pre-grasp."""

    calibration_config_sha256: str
    machine_result_sha256: str
    machine_runtime_fix_commit: str
    selected_case_name: str
    gravity_enabled: bool
    drive_type: str
    stiffness: float
    damping: float
    effort_limit_sim: float
    solver_position_iteration_count: int
    solver_velocity_iteration_count: int
    enable_external_forces_every_iteration: bool
    gravity_compensation_feed_forward: bool
    gravity_compensation_effort_limit: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration_config_sha256": self.calibration_config_sha256,
            "machine_result_sha256": self.machine_result_sha256,
            "machine_runtime_fix_commit": self.machine_runtime_fix_commit,
            "selected_case_name": self.selected_case_name,
            "gravity_enabled": self.gravity_enabled,
            "drive_type": self.drive_type,
            "stiffness": self.stiffness,
            "damping": self.damping,
            "effort_limit_sim": self.effort_limit_sim,
            "solver_position_iteration_count": (
                self.solver_position_iteration_count
            ),
            "solver_velocity_iteration_count": (
                self.solver_velocity_iteration_count
            ),
            "enable_external_forces_every_iteration": (
                self.enable_external_forces_every_iteration
            ),
            "gravity_compensation_feed_forward": (
                self.gravity_compensation_feed_forward
            ),
            "gravity_compensation_effort_limit": (
                self.gravity_compensation_effort_limit
            ),
        }


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GravityFeedForwardError(f"{label} must be an object")
    return value


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GravityFeedForwardError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise GravityFeedForwardError(f"{label} must be finite")
    return number


def load_accepted_gravity_feed_forward_runtime(
    *,
    calibration_config_path: Path,
    machine_result_path: Path,
) -> AcceptedGravityFeedForwardRuntime:
    """Bind the selected runtime to the checked-in successful machine result.

    The machine result intentionally does not authorize pre-grasp by itself.
    This loader only promotes its actuator settings after checking the complete
    matrix decision, treatment metrics, safety telemetry, and exact agreement
    with the independently parsed calibration config.
    """
    config, config_sha256 = load_actuator_calibration_config(
        calibration_config_path
    )
    if config_sha256 != ACCEPTED_GRAVITY_FEED_FORWARD_CONFIG_SHA256:
        raise GravityFeedForwardError(
            "calibration config SHA-256 differs from the accepted machine input"
        )
    if config.case_names != GRAVITY_FEED_FORWARD_CASE_NAMES:
        raise GravityFeedForwardError(
            "calibration config is not the accepted gravity feed-forward matrix"
        )
    selected = config.case("bounded_gravity_feed_forward")

    raw_result = machine_result_path.read_bytes()
    try:
        result = _object(json.loads(raw_result), "machine result")
    except json.JSONDecodeError as error:
        raise GravityFeedForwardError(
            f"{machine_result_path} is not valid JSON"
        ) from error
    result_sha256 = hashlib.sha256(raw_result).hexdigest()
    if result_sha256 != ACCEPTED_GRAVITY_FEED_FORWARD_RESULT_SHA256:
        raise GravityFeedForwardError(
            "machine result SHA-256 differs from the accepted evidence"
        )
    if result.get("schema_version") != 1 or result.get("experiment") != (
        "dofbot_bounded_gravity_feed_forward_machine_result"
    ):
        raise GravityFeedForwardError(
            "machine result is not the accepted gravity feed-forward experiment"
        )

    matrix = _object(result.get("matrix"), "machine result matrix")
    expected_matrix = {
        "matrix_exit_code": 0,
        "matrix_complete": True,
        "decision": "bounded_gravity_feed_forward_resolves_tracking",
        "tracking_identity_validated": True,
        "pregrasp_authorized_by_matrix": False,
        "viewer_authorized": False,
    }
    mismatched_matrix = [
        name for name, expected in expected_matrix.items()
        if matrix.get(name) != expected
    ]
    if mismatched_matrix:
        raise GravityFeedForwardError(
            "machine result matrix is incomplete or rejected: "
            + ", ".join(mismatched_matrix)
        )

    cases = _object(result.get("cases"), "machine result cases")
    baseline = _object(
        cases.get("force_damping_53_baseline"),
        "machine baseline case",
    )
    treatment = _object(
        cases.get("bounded_gravity_feed_forward"),
        "machine treatment case",
    )
    if (
        baseline.get("gravity_compensation_feed_forward") is not False
        or baseline.get("diagnostic_complete") is not True
        or baseline.get("tracking_gate_passed") is not False
        or treatment.get("gravity_compensation_feed_forward") is not True
        or treatment.get("diagnostic_complete") is not True
        or treatment.get("tracking_gate_passed") is not True
    ):
        raise GravityFeedForwardError(
            "machine result does not preserve the accepted baseline/treatment outcome"
        )

    metric_limits = {
        "maximum_settled_tracking_error_deg": (
            config.acceptance.maximum_settled_tracking_error_deg
        ),
        "maximum_target_buffer_error_deg": (
            config.acceptance.maximum_target_buffer_error_deg
        ),
        "maximum_overshoot_deg": config.acceptance.maximum_overshoot_deg,
        "maximum_contact_force_n": config.acceptance.maximum_contact_force_n,
    }
    failed_metrics = [
        name
        for name, limit in metric_limits.items()
        if _finite_number(treatment.get(name), f"treatment {name}") > limit
    ]
    if failed_metrics:
        raise GravityFeedForwardError(
            "machine treatment no longer passes: " + ", ".join(failed_metrics)
        )

    if selected.gravity_compensation_effort_limit is None:
        raise GravityFeedForwardError(
            "selected calibration case is missing its feed-forward limit"
        )
    feed_forward_limit = float(selected.gravity_compensation_effort_limit)
    for name in (
        "maximum_absolute_raw_gravity_effort",
        "maximum_absolute_applied_feed_forward_effort",
    ):
        if _finite_number(treatment.get(name), f"treatment {name}") > (
            feed_forward_limit + 1.0e-9
        ):
            raise GravityFeedForwardError(
                f"machine treatment {name} exceeds the accepted bound"
            )
    if (
        _finite_number(
            treatment.get("configured_feed_forward_effort_limit"),
            "treatment configured feed-forward effort limit",
        )
        != feed_forward_limit
        or treatment.get("clipped_sample_count") != 0
        or not isinstance(treatment.get("feed_forward_sample_count"), int)
        or treatment["feed_forward_sample_count"] <= 0
    ):
        raise GravityFeedForwardError(
            "machine treatment feed-forward telemetry is incomplete or drifted"
        )

    shared = _object(
        result.get("shared_runtime_contract"),
        "machine shared runtime contract",
    )
    expected_shared = {
        "drive_type": selected.drive_type,
        "stiffness": selected.stiffness,
        "damping": selected.damping,
        "effort_limit_sim": selected.effort_limit_sim,
        "enable_external_forces_every_iteration": (
            selected.enable_external_forces_every_iteration
        ),
        "controlled_joints": list(CONTROLLED_JOINT_NAMES),
        "uncontrolled_dof_external_actuation": 0.0,
    }
    mismatched_shared = [
        name for name, expected in expected_shared.items()
        if shared.get(name) != expected
    ]
    if mismatched_shared:
        raise GravityFeedForwardError(
            "machine shared runtime differs from calibration config: "
            + ", ".join(mismatched_shared)
        )

    provenance = _object(result.get("provenance"), "machine provenance")
    runtime_fix_commit = provenance.get("runtime_fix_commit")
    if not isinstance(runtime_fix_commit, str) or len(runtime_fix_commit) != 40:
        raise GravityFeedForwardError(
            "machine result is missing its runtime-fix commit"
        )
    if (
        selected.gravity_enabled is not True
        or selected.drive_type != "force"
        or selected.gravity_compensation_feed_forward is not True
        or selected.enable_external_forces_every_iteration is not True
    ):
        raise GravityFeedForwardError(
            "selected calibration case is not the accepted force/feed-forward runtime"
        )

    return AcceptedGravityFeedForwardRuntime(
        calibration_config_sha256=config_sha256,
        machine_result_sha256=result_sha256,
        machine_runtime_fix_commit=runtime_fix_commit,
        selected_case_name=selected.name,
        gravity_enabled=selected.gravity_enabled,
        drive_type=selected.drive_type,
        stiffness=selected.stiffness,
        damping=selected.damping,
        effort_limit_sim=selected.effort_limit_sim,
        solver_position_iteration_count=(
            selected.solver_position_iteration_count
        ),
        solver_velocity_iteration_count=(
            selected.solver_velocity_iteration_count
        ),
        enable_external_forces_every_iteration=(
            selected.enable_external_forces_every_iteration
        ),
        gravity_compensation_feed_forward=bool(
            selected.gravity_compensation_feed_forward
        ),
        gravity_compensation_effort_limit=feed_forward_limit,
    )


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
