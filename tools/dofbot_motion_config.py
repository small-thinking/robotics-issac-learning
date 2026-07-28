"""Fail-closed ActionChunk v1 contract for scripted DOFBOT motion.

The JSON schema expresses complete four-servo poses in Yahboom's documented
integer-degree units. A validated pose sequence is compiled to deterministic
10 Hz single-servo API calls that can later be consumed by either Isaac or a
calibrated physical backend.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .dofbot_control_api import YahboomServoWrite
except ImportError:
    from dofbot_control_api import YahboomServoWrite

SCHEMA_VERSION = 1
CONTROL_HZ = 10
CONTROL_INTERVAL_MS = 100
SERVO_IDS = (1, 2, 3, 4)
NEUTRAL_ANGLES_DEG = (90, 90, 90, 90)
SAFE_MIN_ANGLE_DEG = 75
SAFE_MAX_ANGLE_DEG = 105
MAX_POSE_DELTA_DEG = 15
MIN_MOVE_DURATION_MS = 500
MAX_MOVE_DURATION_MS = 5_000
MAX_HOLD_MS = 5_000
MAX_STEPS = 64
MAX_TOTAL_DURATION_MS = 60_000
MAX_CHECKPOINT_TRACKING_ERROR_DEG = 2.0
MAX_FINAL_NEUTRAL_ERROR_DEG = 1.0
MAX_OBSERVED_ENVELOPE_OVERSHOOT_DEG = 1.0
MIN_VISIBLE_EXCURSION_DEG = 10.0
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class MotionConfigError(ValueError):
    """Raised when an ActionChunk config or observation is unsafe."""


@dataclass(frozen=True)
class MotionConfigStep:
    """One complete, absolute four-servo pose."""

    name: str
    angles_deg: tuple[int, int, int, int]
    duration_ms: int
    hold_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "angles_deg": list(self.angles_deg),
            "duration_ms": self.duration_ms,
            "hold_ms": self.hold_ms,
        }


@dataclass(frozen=True)
class MotionConfig:
    """Validated ActionChunk v1 document."""

    name: str
    control_hz: int
    steps: tuple[MotionConfigStep, ...]

    @property
    def total_duration_ms(self) -> int:
        return sum(step.duration_ms + step.hold_ms for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "control_hz": self.control_hz,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class CompiledMotionSample:
    """One 10 Hz complete pose that expands to four official API writes."""

    sequence_index: int
    elapsed_ms: int
    step_index: int
    step_name: str
    phase: str
    angles_deg: tuple[int, int, int, int]
    duration_ms: int = CONTROL_INTERVAL_MS

    def api_writes(self) -> tuple[YahboomServoWrite, ...]:
        return tuple(
            YahboomServoWrite(
                servo_id=servo_id,
                angle_deg=angle_deg,
                duration_ms=self.duration_ms,
            )
            for servo_id, angle_deg in zip(
                SERVO_IDS,
                self.angles_deg,
                strict=True,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_index": self.sequence_index,
            "elapsed_ms": self.elapsed_ms,
            "step_index": self.step_index,
            "step_name": self.step_name,
            "phase": self.phase,
            "angles_deg": list(self.angles_deg),
            "duration_ms": self.duration_ms,
        }


def _require_exact_keys(
    value: dict[str, Any],
    *,
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise MotionConfigError(
            f"{label} keys must match the schema; missing={missing}, extra={extra}"
        )


def _require_integer(
    value: Any,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MotionConfigError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise MotionConfigError(f"{label} must be in [{minimum}, {maximum}]")
    return value


def _require_aligned_milliseconds(value: Any, *, label: str, allow_zero: bool) -> int:
    minimum = 0 if allow_zero else MIN_MOVE_DURATION_MS
    maximum = MAX_HOLD_MS if allow_zero else MAX_MOVE_DURATION_MS
    converted = _require_integer(
        value,
        label=label,
        minimum=minimum,
        maximum=maximum,
    )
    if converted % CONTROL_INTERVAL_MS != 0:
        raise MotionConfigError(
            f"{label} must be a multiple of {CONTROL_INTERVAL_MS} ms"
        )
    return converted


def parse_motion_config(value: Any) -> MotionConfig:
    """Validate one decoded ActionChunk v1 JSON value."""

    if not isinstance(value, dict):
        raise MotionConfigError("motion config must be a JSON object")
    _require_exact_keys(
        value,
        expected={"schema_version", "name", "control_hz", "steps"},
        label="motion config",
    )
    _require_integer(
        value["schema_version"],
        label="schema_version",
        minimum=SCHEMA_VERSION,
        maximum=SCHEMA_VERSION,
    )

    name = value["name"]
    if not isinstance(name, str) or _NAME_PATTERN.fullmatch(name) is None:
        raise MotionConfigError("name must be a lowercase snake_case identifier")
    control_hz = _require_integer(
        value["control_hz"],
        label="control_hz",
        minimum=CONTROL_HZ,
        maximum=CONTROL_HZ,
    )

    raw_steps = value["steps"]
    if not isinstance(raw_steps, list):
        raise MotionConfigError("steps must be a list")
    if len(raw_steps) < 3 or len(raw_steps) > MAX_STEPS:
        raise MotionConfigError(f"steps must contain between 3 and {MAX_STEPS} entries")

    steps: list[MotionConfigStep] = []
    step_names: set[str] = set()
    for index, raw_step in enumerate(raw_steps):
        label = f"steps[{index}]"
        if not isinstance(raw_step, dict):
            raise MotionConfigError(f"{label} must be an object")
        _require_exact_keys(
            raw_step,
            expected={"name", "angles_deg", "duration_ms", "hold_ms"},
            label=label,
        )

        step_name = raw_step["name"]
        if not isinstance(step_name, str) or _NAME_PATTERN.fullmatch(step_name) is None:
            raise MotionConfigError(f"{label}.name must be lowercase snake_case")
        if step_name in step_names:
            raise MotionConfigError(f"duplicate step name: {step_name}")
        step_names.add(step_name)

        raw_angles = raw_step["angles_deg"]
        if not isinstance(raw_angles, list) or len(raw_angles) != len(SERVO_IDS):
            raise MotionConfigError(f"{label}.angles_deg must contain four values")
        angles = tuple(
            _require_integer(
                angle,
                label=f"{label}.angles_deg[{angle_index}]",
                minimum=SAFE_MIN_ANGLE_DEG,
                maximum=SAFE_MAX_ANGLE_DEG,
            )
            for angle_index, angle in enumerate(raw_angles)
        )
        duration_ms = _require_aligned_milliseconds(
            raw_step["duration_ms"],
            label=f"{label}.duration_ms",
            allow_zero=False,
        )
        hold_ms = _require_aligned_milliseconds(
            raw_step["hold_ms"],
            label=f"{label}.hold_ms",
            allow_zero=True,
        )
        steps.append(
            MotionConfigStep(
                name=step_name,
                angles_deg=angles,
                duration_ms=duration_ms,
                hold_ms=hold_ms,
            )
        )

    if steps[0].angles_deg != NEUTRAL_ANGLES_DEG:
        raise MotionConfigError("the first step must use the neutral pose")
    if steps[-1].angles_deg != NEUTRAL_ANGLES_DEG:
        raise MotionConfigError("the final step must return to the neutral pose")
    if not any(step.angles_deg != NEUTRAL_ANGLES_DEG for step in steps[1:-1]):
        raise MotionConfigError("the config must include at least one non-neutral pose")

    previous_angles = NEUTRAL_ANGLES_DEG
    for step in steps:
        maximum_delta = max(
            abs(current - previous)
            for current, previous in zip(
                step.angles_deg,
                previous_angles,
                strict=True,
            )
        )
        if maximum_delta > MAX_POSE_DELTA_DEG:
            raise MotionConfigError(
                f"step {step.name} changes a servo by more than "
                f"{MAX_POSE_DELTA_DEG} degrees"
            )
        previous_angles = step.angles_deg

    config = MotionConfig(
        name=name,
        control_hz=control_hz,
        steps=tuple(steps),
    )
    if config.total_duration_ms > MAX_TOTAL_DURATION_MS:
        raise MotionConfigError(
            f"total duration exceeds {MAX_TOTAL_DURATION_MS} ms"
        )
    return config


def load_motion_config(path: Path) -> tuple[MotionConfig, str]:
    """Load, hash, decode, and validate a motion config file."""

    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise MotionConfigError(f"{path} is not valid JSON") from error
    return parse_motion_config(value), hashlib.sha256(raw).hexdigest()


def _round_positive_degrees(value: float) -> int:
    return int(math.floor(value + 0.5))


def compile_motion_config(
    config: MotionConfig,
) -> tuple[CompiledMotionSample, ...]:
    """Linearly compile complete poses to deterministic 10 Hz API samples."""

    samples: list[CompiledMotionSample] = []
    previous_angles = NEUTRAL_ANGLES_DEG
    elapsed_ms = 0

    for step_index, step in enumerate(config.steps):
        move_sample_count = step.duration_ms // CONTROL_INTERVAL_MS
        for move_index in range(1, move_sample_count + 1):
            progress = move_index / move_sample_count
            angles = tuple(
                _round_positive_degrees(start + (target - start) * progress)
                for start, target in zip(
                    previous_angles,
                    step.angles_deg,
                    strict=True,
                )
            )
            elapsed_ms += CONTROL_INTERVAL_MS
            samples.append(
                CompiledMotionSample(
                    sequence_index=len(samples),
                    elapsed_ms=elapsed_ms,
                    step_index=step_index,
                    step_name=step.name,
                    phase="move",
                    angles_deg=angles,
                )
            )

        hold_sample_count = step.hold_ms // CONTROL_INTERVAL_MS
        for _ in range(hold_sample_count):
            elapsed_ms += CONTROL_INTERVAL_MS
            samples.append(
                CompiledMotionSample(
                    sequence_index=len(samples),
                    elapsed_ms=elapsed_ms,
                    step_index=step_index,
                    step_name=step.name,
                    phase="hold",
                    angles_deg=step.angles_deg,
                )
            )
        previous_angles = step.angles_deg

    if not samples or samples[-1].elapsed_ms != config.total_duration_ms:
        raise MotionConfigError("compiled timeline does not match config duration")
    return tuple(samples)


def evaluate_motion_config_observations(
    config: MotionConfig,
    samples: tuple[CompiledMotionSample, ...],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate machine-observable execution of one compiled config cycle."""

    if len(observations) != len(samples):
        raise MotionConfigError("observation count does not match compiled samples")

    sample_contract_matches = True
    all_observations_finite = True
    observations_within_envelope = True
    step_targets_reached = True
    maximum_checkpoint_error_deg = 0.0
    maximum_observed_excursion_deg = 0.0
    final_observed: tuple[float, ...] | None = None

    final_sample_index_by_step: dict[int, int] = {}
    for sample_index, sample in enumerate(samples):
        final_sample_index_by_step[sample.step_index] = sample_index

    for sample_index, (expected, observation) in enumerate(
        zip(samples, observations, strict=True)
    ):
        if not isinstance(observation, dict):
            raise MotionConfigError("each observation must be an object")
        target = observation.get("target_angles_deg")
        observed = observation.get("observed_angles_deg")
        if (
            observation.get("sequence_index") != expected.sequence_index
            or target != list(expected.angles_deg)
        ):
            sample_contract_matches = False
        if not isinstance(observed, list) or len(observed) != len(SERVO_IDS):
            raise MotionConfigError("observed_angles_deg must contain four values")

        converted_observed: list[float] = []
        for value in observed:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MotionConfigError("observed angles must be numeric")
            converted = float(value)
            if not math.isfinite(converted):
                all_observations_finite = False
            converted_observed.append(converted)
            if (
                converted < SAFE_MIN_ANGLE_DEG - MAX_OBSERVED_ENVELOPE_OVERSHOOT_DEG
                or converted
                > SAFE_MAX_ANGLE_DEG + MAX_OBSERVED_ENVELOPE_OVERSHOOT_DEG
            ):
                observations_within_envelope = False
            maximum_observed_excursion_deg = max(
                maximum_observed_excursion_deg,
                abs(converted - 90.0),
            )

        if sample_index == final_sample_index_by_step[expected.step_index]:
            checkpoint_error = max(
                abs(actual - target_angle)
                for actual, target_angle in zip(
                    converted_observed,
                    expected.angles_deg,
                    strict=True,
                )
            )
            maximum_checkpoint_error_deg = max(
                maximum_checkpoint_error_deg,
                checkpoint_error,
            )
            if checkpoint_error > MAX_CHECKPOINT_TRACKING_ERROR_DEG:
                step_targets_reached = False
        final_observed = tuple(converted_observed)

    if final_observed is None:
        raise MotionConfigError("no final observation was recorded")
    maximum_final_neutral_error_deg = max(
        abs(actual - neutral)
        for actual, neutral in zip(
            final_observed,
            NEUTRAL_ANGLES_DEG,
            strict=True,
        )
    )
    returned_to_neutral = (
        maximum_final_neutral_error_deg <= MAX_FINAL_NEUTRAL_ERROR_DEG
    )
    non_neutral_motion_observed = (
        maximum_observed_excursion_deg >= MIN_VISIBLE_EXCURSION_DEG
    )
    checks = {
        "sample_contract_matches": sample_contract_matches,
        "all_observations_finite": all_observations_finite,
        "observations_within_safe_envelope": observations_within_envelope,
        "step_targets_reached": step_targets_reached,
        "non_neutral_motion_observed": non_neutral_motion_observed,
        "returned_to_neutral": returned_to_neutral,
    }
    return {
        "checks": checks,
        "maximum_checkpoint_error_deg": maximum_checkpoint_error_deg,
        "maximum_observed_excursion_deg": maximum_observed_excursion_deg,
        "maximum_final_neutral_error_deg": maximum_final_neutral_error_deg,
        "machine_passed": all(checks.values()),
        "config_name": config.name,
    }
