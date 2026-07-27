"""Pure-Python safety contract for policy-free DOFBOT joint motion.

This module intentionally has no Isaac Lab or PyTorch dependency. It validates
the recorded Goal 1 asset contract, builds the fixed Goal 2 trajectory, and
evaluates sampled joint observations. The same code is unit-tested locally and
used by the remote Isaac runner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

CONTROLLED_JOINT_NAMES = ("joint1", "joint2", "joint3", "joint4")
OFFICIAL_ASSET_RELATIVE_PATH = "Robots/Yahboom/Dofbot/dofbot.usd"
MAX_AMPLITUDE_RAD = math.radians(5.0)
REQUIRED_LIMIT_MARGIN_RAD = math.radians(10.0)
MIN_OBSERVED_EXCURSION_RAD = math.radians(2.5)
MIN_WAVE_EXCURSION_RAD = math.radians(1.0)
MAX_INACTIVE_JOINT_ERROR_RAD = math.radians(1.0)
MAX_RESET_ERROR_RAD = math.radians(1.0)
MAX_TRACKING_OVERSHOOT_RAD = math.radians(1.0)
MIN_SIGN_AGREEMENT_FRACTION = 0.9
UNBOUNDED_LIMIT_THRESHOLD_RAD = 1.0e6

DEFAULT_PRE_MOTION_HOLD_S = 2.0
SINGLE_JOINT_DURATION_S = 6.0
BETWEEN_JOINT_HOLD_S = 1.0
MULTI_JOINT_WAVE_DURATION_S = 8.0
RESET_HOLD_S = 3.0


class MotionPlanError(ValueError):
    """Raised when the recorded or requested motion is not safe to execute."""


@dataclass(frozen=True)
class JointSafetyContract:
    name: str
    index: int
    default_rad: float
    lower_rad: float
    upper_rad: float

    @property
    def minimum_available_margin_rad(self) -> float:
        return min(
            self.default_rad - self.lower_rad,
            self.upper_rad - self.default_rad,
        )


@dataclass(frozen=True)
class MotionSegment:
    name: str
    kind: str
    duration_s: float
    active_joint: str | None = None


@dataclass(frozen=True)
class MotionSample:
    elapsed_s: float
    segment_name: str
    target_positions_rad: dict[str, float]


@dataclass(frozen=True)
class MotionPlan:
    all_joint_names: tuple[str, ...]
    controlled_joints: tuple[JointSafetyContract, ...]
    segments: tuple[MotionSegment, ...]
    amplitude_rad: float
    required_limit_margin_rad: float

    @property
    def total_duration_s(self) -> float:
        return sum(segment.duration_s for segment in self.segments)

    @property
    def controlled_joint_names(self) -> tuple[str, ...]:
        return tuple(joint.name for joint in self.controlled_joints)

    def target_at(self, elapsed_s: float) -> MotionSample:
        if not math.isfinite(elapsed_s):
            raise MotionPlanError("elapsed time must be finite")

        bounded_elapsed = min(max(elapsed_s, 0.0), self.total_duration_s)
        segment_start = 0.0
        selected_segment = self.segments[-1]
        local_elapsed = selected_segment.duration_s

        for index, segment in enumerate(self.segments):
            segment_end = segment_start + segment.duration_s
            if bounded_elapsed < segment_end or index == len(self.segments) - 1:
                selected_segment = segment
                local_elapsed = min(
                    max(bounded_elapsed - segment_start, 0.0),
                    segment.duration_s,
                )
                break
            segment_start = segment_end

        targets = {joint.name: joint.default_rad for joint in self.controlled_joints}
        progress = local_elapsed / selected_segment.duration_s

        if selected_segment.kind == "single_joint_sine":
            if selected_segment.active_joint is None:
                raise MotionPlanError(f"{selected_segment.name} does not name an active joint")
            targets[selected_segment.active_joint] += self.amplitude_rad * math.sin(
                2.0 * math.pi * progress
            )
        elif selected_segment.kind == "multi_joint_wave":
            envelope = math.sin(math.pi * progress) ** 2
            for index, joint in enumerate(self.controlled_joints):
                phase = index * math.pi / 2.0
                targets[joint.name] += (
                    self.amplitude_rad * envelope * math.sin(4.0 * math.pi * progress + phase)
                )
        elif selected_segment.kind not in {"hold_default", "reset_default"}:
            raise MotionPlanError(f"unknown motion segment kind: {selected_segment.kind}")

        _validate_target_positions(self, targets)
        return MotionSample(
            elapsed_s=bounded_elapsed,
            segment_name=selected_segment.name,
            target_positions_rad=targets,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "controlled_joint_names": list(self.controlled_joint_names),
            "amplitude_rad": self.amplitude_rad,
            "amplitude_deg": math.degrees(self.amplitude_rad),
            "required_limit_margin_rad": self.required_limit_margin_rad,
            "required_limit_margin_deg": math.degrees(self.required_limit_margin_rad),
            "total_duration_s": self.total_duration_s,
            "joint_contracts": [
                {
                    "name": joint.name,
                    "index": joint.index,
                    "default_rad": joint.default_rad,
                    "lower_rad": joint.lower_rad,
                    "upper_rad": joint.upper_rad,
                    "minimum_available_margin_rad": (joint.minimum_available_margin_rad),
                    "target_margin_rad": (joint.minimum_available_margin_rad - self.amplitude_rad),
                }
                for joint in self.controlled_joints
            ],
            "segments": [
                {
                    "name": segment.name,
                    "kind": segment.kind,
                    "duration_s": segment.duration_s,
                    "active_joint": segment.active_joint,
                }
                for segment in self.segments
            ],
        }


def _require_finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MotionPlanError(f"{label} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise MotionPlanError(f"{label} must be finite")
    return converted


def _validate_duration(value: float, label: str) -> float:
    converted = _require_finite_number(value, label)
    if converted <= 0.0:
        raise MotionPlanError(f"{label} must be positive")
    return converted


def _validate_target_positions(
    plan: MotionPlan,
    target_positions_rad: dict[str, float],
) -> None:
    if set(target_positions_rad) != set(plan.controlled_joint_names):
        raise MotionPlanError("target joint set does not match the controlled joint set")

    for joint in plan.controlled_joints:
        target = _require_finite_number(
            target_positions_rad[joint.name],
            f"target for {joint.name}",
        )
        lower_target_bound = joint.lower_rad + plan.required_limit_margin_rad
        upper_target_bound = joint.upper_rad - plan.required_limit_margin_rad
        if target < lower_target_bound or target > upper_target_bound:
            raise MotionPlanError(
                f"target for {joint.name} violates the required joint-limit margin"
            )
        if abs(target - joint.default_rad) > plan.amplitude_rad + 1.0e-12:
            raise MotionPlanError(
                f"target for {joint.name} exceeds the {math.degrees(plan.amplitude_rad):g}"
                " degree amplitude"
            )


def build_motion_plan(
    asset_contract: dict[str, Any],
    *,
    amplitude_rad: float = MAX_AMPLITUDE_RAD,
    pre_motion_hold_s: float = DEFAULT_PRE_MOTION_HOLD_S,
) -> MotionPlan:
    """Validate a Goal 1 contract and construct the fixed safe trajectory."""

    amplitude = _require_finite_number(amplitude_rad, "amplitude_rad")
    if amplitude <= 0.0 or amplitude > MAX_AMPLITUDE_RAD + 1.0e-12:
        raise MotionPlanError(f"amplitude must be in (0, {MAX_AMPLITUDE_RAD}] radians")
    pre_motion_hold = _validate_duration(
        pre_motion_hold_s,
        "pre_motion_hold_s",
    )

    articulation = asset_contract.get("articulation")
    if not isinstance(articulation, dict):
        raise MotionPlanError("asset contract is missing articulation data")

    names = articulation.get("joint_names")
    defaults = articulation.get("default_joint_positions_rad")
    limits = articulation.get("joint_position_limits_rad")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise MotionPlanError("joint_names must be a list of strings")
    if len(names) != len(set(names)):
        raise MotionPlanError("joint_names contains duplicates")
    if not isinstance(defaults, list) or len(defaults) != len(names):
        raise MotionPlanError("default joint positions do not match joint_names")
    if not isinstance(limits, list) or len(limits) != len(names):
        raise MotionPlanError("joint limits do not match joint_names")

    name_to_index = {name: index for index, name in enumerate(names)}
    missing = [name for name in CONTROLLED_JOINT_NAMES if name not in name_to_index]
    if missing:
        raise MotionPlanError(f"controlled joints missing from asset contract: {missing}")

    controlled_joints: list[JointSafetyContract] = []
    for name in CONTROLLED_JOINT_NAMES:
        index = name_to_index[name]
        default = _require_finite_number(defaults[index], f"default for {name}")
        raw_limit = limits[index]
        if not isinstance(raw_limit, list) or len(raw_limit) != 2:
            raise MotionPlanError(f"limits for {name} must contain [lower, upper]")
        lower = _require_finite_number(raw_limit[0], f"lower limit for {name}")
        upper = _require_finite_number(raw_limit[1], f"upper limit for {name}")

        if (
            abs(lower) >= UNBOUNDED_LIMIT_THRESHOLD_RAD
            or abs(upper) >= UNBOUNDED_LIMIT_THRESHOLD_RAD
        ):
            raise MotionPlanError(f"{name} reports an unbounded sentinel limit")
        if not lower < default < upper:
            raise MotionPlanError(f"default for {name} must be strictly inside its joint limits")

        joint = JointSafetyContract(
            name=name,
            index=index,
            default_rad=default,
            lower_rad=lower,
            upper_rad=upper,
        )
        required_space = amplitude + REQUIRED_LIMIT_MARGIN_RAD
        if joint.minimum_available_margin_rad < required_space - 1.0e-12:
            raise MotionPlanError(
                f"{name} does not have enough range for the requested motion and margin"
            )
        controlled_joints.append(joint)

    segments: list[MotionSegment] = [
        MotionSegment(
            name="hold_default",
            kind="hold_default",
            duration_s=pre_motion_hold,
        )
    ]
    for name in CONTROLLED_JOINT_NAMES:
        segments.extend(
            (
                MotionSegment(
                    name=f"{name}_sine",
                    kind="single_joint_sine",
                    duration_s=SINGLE_JOINT_DURATION_S,
                    active_joint=name,
                ),
                MotionSegment(
                    name=f"{name}_settle",
                    kind="hold_default",
                    duration_s=BETWEEN_JOINT_HOLD_S,
                ),
            )
        )
    segments.extend(
        (
            MotionSegment(
                name="multi_joint_wave",
                kind="multi_joint_wave",
                duration_s=MULTI_JOINT_WAVE_DURATION_S,
            ),
            MotionSegment(
                name="reset_default",
                kind="reset_default",
                duration_s=RESET_HOLD_S,
            ),
        )
    )

    plan = MotionPlan(
        all_joint_names=tuple(names),
        controlled_joints=tuple(controlled_joints),
        segments=tuple(segments),
        amplitude_rad=amplitude,
        required_limit_margin_rad=REQUIRED_LIMIT_MARGIN_RAD,
    )
    plan.target_at(0.0)
    plan.target_at(plan.total_duration_s)
    return plan


def validate_recorded_asset_contract(
    asset_contract: dict[str, Any],
) -> MotionPlan:
    """Require the accepted, policy-free Goal 1 official-asset contract."""

    if asset_contract.get("schema_version") != 1:
        raise MotionPlanError("recorded asset contract schema_version must be 1")
    if asset_contract.get("experiment") != "02_dofbot_goal_1_asset_load":
        raise MotionPlanError("recorded asset contract has the wrong experiment")
    if asset_contract.get("learning_algorithm") is not None:
        raise MotionPlanError("recorded asset contract must be policy-free")

    asset = asset_contract.get("asset")
    if (
        not isinstance(asset, dict)
        or asset.get("relative_usd_path") != OFFICIAL_ASSET_RELATIVE_PATH
    ):
        raise MotionPlanError("recorded asset contract is not the official DOFBOT USD")

    acceptance = asset_contract.get("acceptance")
    checks = acceptance.get("checks") if isinstance(acceptance, dict) else None
    if (
        not isinstance(checks, dict)
        or not checks
        or not all(value is True for value in checks.values())
        or acceptance.get("passed") is not True
    ):
        raise MotionPlanError("recorded Goal 1 asset acceptance did not pass")
    return build_motion_plan(asset_contract)


def assert_compatible_asset_contracts(
    recorded_contract: dict[str, Any],
    live_contract: dict[str, Any],
    *,
    tolerance_rad: float = 1.0e-5,
) -> MotionPlan:
    """Fail if the live articulation differs from the recorded Goal 1 contract."""

    recorded_plan = validate_recorded_asset_contract(recorded_contract)
    live_plan = build_motion_plan(live_contract)
    if recorded_plan.all_joint_names != live_plan.all_joint_names:
        raise MotionPlanError("live joint ordering differs from the recorded contract")

    for recorded, live in zip(
        recorded_plan.controlled_joints,
        live_plan.controlled_joints,
        strict=True,
    ):
        if recorded.index != live.index:
            raise MotionPlanError(f"live joint index changed for {recorded.name}")
        for field_name in ("default_rad", "lower_rad", "upper_rad"):
            if abs(getattr(recorded, field_name) - getattr(live, field_name)) > tolerance_rad:
                raise MotionPlanError(
                    f"live {field_name} differs from the recorded contract for {recorded.name}"
                )
    return live_plan


def iter_plan_samples(
    plan: MotionPlan,
    *,
    sample_hz: float,
) -> list[MotionSample]:
    """Return deterministic samples including both trajectory endpoints."""

    frequency = _require_finite_number(sample_hz, "sample_hz")
    if frequency <= 0.0:
        raise MotionPlanError("sample_hz must be positive")
    sample_count = math.ceil(plan.total_duration_s * frequency)
    return [
        plan.target_at(min(index / frequency, plan.total_duration_s))
        for index in range(sample_count + 1)
    ]


def evaluate_motion_observations(
    plan: MotionPlan,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate machine-observable safety and reset gates for one full cycle."""

    if not observations:
        raise MotionPlanError("motion observations must not be empty")

    joint_names = plan.controlled_joint_names
    required_segments = {segment.name for segment in plan.segments}
    observed_segments: set[str] = set()
    finite_values = True
    targets_within_margin = True
    observations_within_margin = True
    observations_within_command_envelope = True
    target_isolation = True
    inactive_joint_hold = True
    simultaneous_wave_observed = False

    per_joint: dict[str, dict[str, float | int]] = {}
    for joint in plan.controlled_joints:
        per_joint[joint.name] = {
            "single_joint_observed_min_delta_rad": math.inf,
            "single_joint_observed_max_delta_rad": -math.inf,
            "maximum_inactive_error_rad": 0.0,
            "maximum_reset_error_rad": 0.0,
            "wave_observed_max_abs_delta_rad": 0.0,
            "sign_comparison_count": 0,
            "sign_agreement_count": 0,
            "sign_agreement_fraction": 0.0,
        }

    reset_rows: list[dict[str, Any]] = []
    for row in observations:
        segment_name = row.get("segment")
        targets = row.get("target_positions_rad")
        observed = row.get("observed_positions_rad")
        if (
            not isinstance(segment_name, str)
            or not isinstance(targets, dict)
            or not isinstance(observed, dict)
        ):
            raise MotionPlanError("observation row has an invalid schema")
        if set(targets) != set(joint_names) or set(observed) != set(joint_names):
            raise MotionPlanError("observation row joint set does not match the plan")

        observed_segments.add(segment_name)
        active_joint = (
            segment_name.removesuffix("_sine") if segment_name.endswith("_sine") else None
        )
        if segment_name == "reset_default":
            reset_rows.append(row)

        wave_active_joint_count = 0
        for joint in plan.controlled_joints:
            target = targets[joint.name]
            actual = observed[joint.name]
            if (
                isinstance(target, bool)
                or not isinstance(target, (int, float))
                or isinstance(actual, bool)
                or not isinstance(actual, (int, float))
            ):
                raise MotionPlanError("observation positions must be numeric")
            target = float(target)
            actual = float(actual)
            if not math.isfinite(target) or not math.isfinite(actual):
                finite_values = False
                continue

            safe_lower = joint.lower_rad + plan.required_limit_margin_rad
            safe_upper = joint.upper_rad - plan.required_limit_margin_rad
            if (
                target < safe_lower
                or target > safe_upper
                or abs(target - joint.default_rad) > plan.amplitude_rad + 1.0e-9
            ):
                targets_within_margin = False
            if actual < safe_lower or actual > safe_upper:
                observations_within_margin = False
            if abs(actual - joint.default_rad) > plan.amplitude_rad + MAX_TRACKING_OVERSHOOT_RAD:
                observations_within_command_envelope = False
            if segment_name == "multi_joint_wave":
                wave_delta = abs(actual - joint.default_rad)
                per_joint[joint.name]["wave_observed_max_abs_delta_rad"] = max(
                    per_joint[joint.name]["wave_observed_max_abs_delta_rad"],
                    wave_delta,
                )
                if wave_delta >= MIN_WAVE_EXCURSION_RAD:
                    wave_active_joint_count += 1

            if active_joint in joint_names:
                if joint.name == active_joint:
                    target_delta = target - joint.default_rad
                    delta = actual - joint.default_rad
                    metrics = per_joint[joint.name]
                    metrics["single_joint_observed_min_delta_rad"] = min(
                        metrics["single_joint_observed_min_delta_rad"],
                        delta,
                    )
                    metrics["single_joint_observed_max_delta_rad"] = max(
                        metrics["single_joint_observed_max_delta_rad"],
                        delta,
                    )
                    if abs(target_delta) >= MIN_OBSERVED_EXCURSION_RAD:
                        metrics["sign_comparison_count"] += 1
                        if target_delta * delta > 0.0:
                            metrics["sign_agreement_count"] += 1
                else:
                    target_error = abs(target - joint.default_rad)
                    actual_error = abs(actual - joint.default_rad)
                    if target_error > 1.0e-9:
                        target_isolation = False
                    if actual_error > MAX_INACTIVE_JOINT_ERROR_RAD:
                        inactive_joint_hold = False
                    per_joint[joint.name]["maximum_inactive_error_rad"] = max(
                        per_joint[joint.name]["maximum_inactive_error_rad"],
                        actual_error,
                    )
        if segment_name == "multi_joint_wave" and wave_active_joint_count >= 2:
            simultaneous_wave_observed = True

    bidirectional_motion = True
    commanded_sign_followed = True
    for joint in plan.controlled_joints:
        metrics = per_joint[joint.name]
        minimum = metrics["single_joint_observed_min_delta_rad"]
        maximum = metrics["single_joint_observed_max_delta_rad"]
        if minimum == math.inf or maximum == -math.inf:
            bidirectional_motion = False
            metrics["single_joint_observed_min_delta_rad"] = 0.0
            metrics["single_joint_observed_max_delta_rad"] = 0.0
        elif minimum > -MIN_OBSERVED_EXCURSION_RAD or maximum < MIN_OBSERVED_EXCURSION_RAD:
            bidirectional_motion = False
        comparison_count = int(metrics["sign_comparison_count"])
        if comparison_count:
            sign_fraction = int(metrics["sign_agreement_count"]) / comparison_count
            metrics["sign_agreement_fraction"] = sign_fraction
        else:
            commanded_sign_followed = False
            sign_fraction = 0.0
        if sign_fraction < MIN_SIGN_AGREEMENT_FRACTION:
            commanded_sign_followed = False

    multi_joint_wave_observed = simultaneous_wave_observed and all(
        metrics["wave_observed_max_abs_delta_rad"] >= MIN_WAVE_EXCURSION_RAD
        for metrics in per_joint.values()
    )

    reset_to_default = bool(reset_rows)
    if reset_rows:
        final_observed = reset_rows[-1]["observed_positions_rad"]
        for joint in plan.controlled_joints:
            error = abs(float(final_observed[joint.name]) - joint.default_rad)
            per_joint[joint.name]["maximum_reset_error_rad"] = error
            if not math.isfinite(error) or error > MAX_RESET_ERROR_RAD:
                reset_to_default = False

    checks = {
        "all_segments_observed": required_segments.issubset(observed_segments),
        "finite_targets_and_observations": finite_values,
        "targets_within_limit_margin": targets_within_margin,
        "observations_within_limit_margin": observations_within_margin,
        "observations_within_command_envelope": (observations_within_command_envelope),
        "single_joint_targets_are_isolated": target_isolation,
        "inactive_joints_hold_default": inactive_joint_hold,
        "each_joint_moves_both_directions": bidirectional_motion,
        "observed_sign_follows_command": commanded_sign_followed,
        "multi_joint_wave_observed": multi_joint_wave_observed,
        "reset_to_default_within_tolerance": reset_to_default,
    }
    return {
        "thresholds": {
            "minimum_observed_excursion_rad": MIN_OBSERVED_EXCURSION_RAD,
            "minimum_wave_excursion_rad": MIN_WAVE_EXCURSION_RAD,
            "maximum_inactive_joint_error_rad": MAX_INACTIVE_JOINT_ERROR_RAD,
            "maximum_reset_error_rad": MAX_RESET_ERROR_RAD,
            "maximum_tracking_overshoot_rad": MAX_TRACKING_OVERSHOOT_RAD,
            "minimum_sign_agreement_fraction": MIN_SIGN_AGREEMENT_FRACTION,
        },
        "per_joint": per_joint,
        "checks": checks,
        "machine_passed": all(checks.values()),
    }
