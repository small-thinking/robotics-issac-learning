"""Validate and visualize a lower, farther DOFBOT pre-grasp scene locally.

This tool deliberately proves only geometry-level necessary conditions. It
anchors the candidate scene to the immutable Goal 4 Isaac artifact, but it
cannot prove candidate-scene inverse kinematics, collision-free motion, or
Viewer appearance without a later Isaac run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

try:
    from .dofbot_reaching import DofbotReachingConfig, load_reaching_config
except ImportError:
    from dofbot_reaching import DofbotReachingConfig, load_reaching_config

MINIMUM_TABLE_LOWERING_M = 0.03
MINIMUM_TABLE_FRONT_SHIFT_M = 0.05
MINIMUM_TARGET_FORWARD_SHIFT_M = 0.06
MAXIMUM_INCREMENTAL_WAYPOINT_SHIFT_M = 0.12
MINIMUM_NOMINAL_RADIAL_MARGIN_M = 0.015
MINIMUM_TABLE_TOP_Z_M = 0.05
MAXIMUM_TABLE_TOP_Z_M = 0.10
MINIMUM_CUBE_EDGE_INSET_M = 0.03


class SceneCalibrationError(ValueError):
    """Raised when evidence or candidate geometry fails closed."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and render a local DOFBOT pre-grasp scene candidate."
    )
    parser.add_argument(
        "--baseline-config",
        type=Path,
        default=Path("configs/dofbot/reaching/goal4_fixed_tabletop.json"),
    )
    parser.add_argument(
        "--candidate-config",
        type=Path,
        default=Path("configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json"),
    )
    parser.add_argument(
        "--isaac-artifact",
        type=Path,
        default=Path("artifacts/dofbot/reaching_viewer_contract.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("/tmp/dofbot-pregrasp-scene-calibration.json"),
    )
    parser.add_argument(
        "--output-svg",
        type=Path,
        default=Path("/tmp/dofbot-pregrasp-scene-calibration.svg"),
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vector3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise SceneCalibrationError(f"{label} must contain exactly three values")
    result: list[float] = []
    for index, item in enumerate(value):
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
        ):
            raise SceneCalibrationError(f"{label}[{index}] must be finite numeric")
        result.append(float(item))
    return tuple(result)


def _vector4(value: Any, label: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise SceneCalibrationError(f"{label} must contain exactly four values")
    result: list[float] = []
    for index, item in enumerate(value):
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
        ):
            raise SceneCalibrationError(f"{label}[{index}] must be finite numeric")
        result.append(float(item))
    return tuple(result)


def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b, strict=True)))


def _front_shift(
    baseline: tuple[float, float, float],
    candidate: tuple[float, float, float],
    front: tuple[float, float, float],
) -> float:
    return sum(
        (candidate[index] - baseline[index]) * front[index] for index in range(3)
    )


def _load_isaac_evidence(
    path: Path,
    *,
    baseline_config_sha256: str,
    baseline_target: tuple[float, float, float],
) -> dict[str, Any]:
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SceneCalibrationError(f"cannot read Isaac evidence {path}: {error}") from error
    if not isinstance(artifact, dict) or artifact.get("schema_version") != 1:
        raise SceneCalibrationError("Isaac evidence must use reaching artifact schema 1")
    machine = artifact.get("acceptance", {}).get("machine")
    if not isinstance(machine, dict) or machine.get("machine_passed") is not True:
        raise SceneCalibrationError("Goal 4 Isaac machine evidence must have passed")
    checks = machine.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise SceneCalibrationError("every Goal 4 Isaac machine check must be true")
    recorded_source = artifact.get("reaching_config")
    if (
        not isinstance(recorded_source, dict)
        or recorded_source.get("sha256") != baseline_config_sha256
    ):
        raise SceneCalibrationError(
            "Isaac evidence does not match the immutable baseline config"
        )
    scope = artifact.get("scope")
    if not isinstance(scope, dict):
        raise SceneCalibrationError("Isaac evidence scope is missing")
    for key in (
        "real_hardware_commanded",
        "camera_used_as_controller_input",
        "gripper_commanded",
        "target_cube_moved",
        "policy_or_checkpoint_loaded",
    ):
        if scope.get(key) is not False:
            raise SceneCalibrationError(f"Isaac evidence scope.{key} must be false")
    observations = artifact.get("measurement", {}).get("state_observations")
    if not isinstance(observations, list) or len(observations) < 2:
        raise SceneCalibrationError("Isaac evidence requires state observations")
    first = observations[0]
    final = observations[-1]
    if not isinstance(first, dict) or not isinstance(final, dict):
        raise SceneCalibrationError("Isaac state observations must be objects")
    neutral_wrist = _vector3(
        first.get("wrist_position_world_m"),
        "first wrist_position_world_m",
    )
    final_wrist = _vector3(
        final.get("wrist_position_world_m"),
        "final wrist_position_world_m",
    )
    final_angles = _vector4(
        final.get("angles_deg"),
        "final angles_deg",
    )
    recorded_target = _vector3(
        final.get("target_position_world_m"),
        "final target_position_world_m",
    )
    if _distance(recorded_target, baseline_target) > 1e-9:
        raise SceneCalibrationError("Isaac evidence target differs from baseline config")
    final_distance = final.get("distance_m")
    if (
        isinstance(final_distance, bool)
        or not isinstance(final_distance, (int, float))
        or not math.isfinite(float(final_distance))
    ):
        raise SceneCalibrationError("final Isaac distance must be finite numeric")
    if not math.isclose(
        float(final_distance),
        _distance(final_wrist, recorded_target),
        abs_tol=1e-6,
    ):
        raise SceneCalibrationError("final Isaac distance is internally inconsistent")
    git_commit = artifact.get("git_commit")
    if (
        not isinstance(git_commit, str)
        or len(git_commit) != 40
        or any(character not in "0123456789abcdef" for character in git_commit)
    ):
        raise SceneCalibrationError("Isaac evidence git_commit must be a full SHA")
    return {
        "artifact_sha256": _sha256(path),
        "git_commit": git_commit,
        "machine_check_count": len(checks),
        "neutral_wrist_world_m": neutral_wrist,
        "neutral_wrist_origin_radius_m": math.sqrt(
            sum(component**2 for component in neutral_wrist)
        ),
        "validated_final_wrist_world_m": final_wrist,
        "validated_final_distance_m": float(final_distance),
        "validated_final_angles_deg": final_angles,
    }


def _cube_minimum_edge_inset_m(config: DofbotReachingConfig) -> float:
    insets: list[float] = []
    for axis in (0, 1):
        table_half = config.table.size_m[axis] / 2.0
        cube_half = config.target_cube.size_m[axis] / 2.0
        offset = abs(
            config.target_cube.center_world_m[axis]
            - config.table.center_world_m[axis]
        )
        insets.append(table_half - offset - cube_half)
    return min(insets)


def build_scene_calibration(
    *,
    baseline_config_path: Path,
    candidate_config_path: Path,
    isaac_artifact_path: Path,
) -> dict[str, Any]:
    baseline, baseline_sha256 = load_reaching_config(baseline_config_path)
    candidate, candidate_sha256 = load_reaching_config(candidate_config_path)
    evidence = _load_isaac_evidence(
        isaac_artifact_path,
        baseline_config_sha256=baseline_sha256,
        baseline_target=baseline.approach_target_world_m,
    )

    front = baseline.robot_frame.workspace_front_world_unit
    table_lowering = baseline.table.top_z_m - candidate.table.top_z_m
    table_front_shift = candidate.table_front_clearance_m - baseline.table_front_clearance_m
    target_forward_shift = _front_shift(
        baseline.target_cube.center_world_m,
        candidate.target_cube.center_world_m,
        front,
    )
    waypoint_shift = _distance(
        baseline.approach_target_world_m,
        candidate.approach_target_world_m,
    )
    candidate_radius = math.sqrt(
        sum(component**2 for component in candidate.approach_target_world_m)
    )
    nominal_radial_margin = (
        evidence["neutral_wrist_origin_radius_m"] - candidate_radius
    )
    observed_joint_envelope_margin = min(
        min(evidence["validated_final_angles_deg"])
        - baseline.state_controller.safe_angle_min_deg,
        baseline.state_controller.safe_angle_max_deg
        - max(evidence["validated_final_angles_deg"]),
    )
    cube_edge_inset = _cube_minimum_edge_inset_m(candidate)
    checks = {
        "baseline_artifact_machine_passed": True,
        "baseline_artifact_matches_config_sha256": True,
        "baseline_artifact_all_machine_checks_passed": (
            evidence["machine_check_count"] > 0
        ),
        "frame_contract_unchanged": (
            candidate.robot_frame == baseline.robot_frame
        ),
        "table_is_axis_aligned_and_horizontal": True,
        "table_top_lowered_at_least_3cm": (
            table_lowering >= MINIMUM_TABLE_LOWERING_M - 1e-9
        ),
        "table_top_remains_in_conservative_height_band": (
            MINIMUM_TABLE_TOP_Z_M - 1e-9
            <= candidate.table.top_z_m
            <= MAXIMUM_TABLE_TOP_Z_M + 1e-9
        ),
        "table_near_edge_shifted_forward_at_least_5cm": (
            table_front_shift >= MINIMUM_TABLE_FRONT_SHIFT_M - 1e-9
        ),
        "table_remains_outside_base_keepout": (
            candidate.table_front_clearance_m
            >= candidate.robot_base_keepout_radius_m - 1e-9
        ),
        "target_shifted_forward_at_least_6cm": (
            target_forward_shift >= MINIMUM_TARGET_FORWARD_SHIFT_M - 1e-9
        ),
        "target_rests_exactly_on_table": (
            math.isclose(
                candidate.target_cube.bottom_z_m,
                candidate.table.top_z_m,
                abs_tol=1e-9,
            )
        ),
        "target_has_at_least_3cm_table_edge_inset": (
            cube_edge_inset >= MINIMUM_CUBE_EDGE_INSET_M - 1e-9
        ),
        "approach_remains_incremental_from_validated_goal4": (
            waypoint_shift <= MAXIMUM_INCREMENTAL_WAYPOINT_SHIFT_M + 1e-9
        ),
        "approach_fits_inside_neutral_wrist_radial_envelope_with_15mm_margin": (
            nominal_radial_margin >= MINIMUM_NOMINAL_RADIAL_MARGIN_M - 1e-9
        ),
        "wrist_table_clearance_contract_preserved": (
            candidate.approach_target_world_m[2] - candidate.table.top_z_m
            >= candidate.state_controller.minimum_wrist_table_clearance_m - 1e-9
        ),
        "scripted_actions_unchanged": (
            candidate.scripted_baseline == baseline.scripted_baseline
        ),
        "state_controller_unchanged": (
            candidate.state_controller == baseline.state_controller
        ),
        "end_effector_anchor_unchanged": (
            candidate.end_effector_body_name == baseline.end_effector_body_name
            and candidate.approach_offset_from_cube_center_m
            == baseline.approach_offset_from_cube_center_m
        ),
        "real_hardware_not_commanded": True,
        "gpu_not_started": True,
    }
    local_geometry_passed = all(checks.values())
    if not local_geometry_passed:
        failed = [name for name, passed in checks.items() if not passed]
        raise SceneCalibrationError(
            f"candidate scene failed local checks: {', '.join(failed)}"
        )
    return {
        "schema_version": 1,
        "experiment": "dofbot_pregrasp_scene_calibration_local",
        "sources": {
            "baseline_config": {
                "path": str(baseline_config_path),
                "sha256": baseline_sha256,
            },
            "candidate_config": {
                "path": str(candidate_config_path),
                "sha256": candidate_sha256,
            },
            "goal4_isaac_artifact": {
                "path": str(isaac_artifact_path),
                "sha256": evidence["artifact_sha256"],
                "git_commit": evidence["git_commit"],
                "machine_check_count": evidence["machine_check_count"],
            },
        },
        "baseline": {
            "table_center_world_m": list(baseline.table.center_world_m),
            "table_top_z_m": baseline.table.top_z_m,
            "table_front_clearance_m": baseline.table_front_clearance_m,
            "target_cube_center_world_m": list(
                baseline.target_cube.center_world_m
            ),
            "approach_target_world_m": list(baseline.approach_target_world_m),
            "validated_neutral_wrist_world_m": list(
                evidence["neutral_wrist_world_m"]
            ),
            "validated_neutral_wrist_origin_radius_m": (
                evidence["neutral_wrist_origin_radius_m"]
            ),
            "validated_final_wrist_world_m": list(
                evidence["validated_final_wrist_world_m"]
            ),
            "validated_final_distance_m": evidence["validated_final_distance_m"],
            "validated_final_angles_deg": list(
                evidence["validated_final_angles_deg"]
            ),
        },
        "candidate": {
            "table_center_world_m": list(candidate.table.center_world_m),
            "table_size_m": list(candidate.table.size_m),
            "table_top_z_m": candidate.table.top_z_m,
            "table_front_clearance_m": candidate.table_front_clearance_m,
            "target_cube_center_world_m": list(
                candidate.target_cube.center_world_m
            ),
            "target_cube_size_m": list(candidate.target_cube.size_m),
            "target_front_clearance_m": candidate.target_front_clearance_m,
            "approach_target_world_m": list(candidate.approach_target_world_m),
            "approach_origin_radius_m": candidate_radius,
            "approach_table_clearance_m": (
                candidate.approach_target_world_m[2] - candidate.table.top_z_m
            ),
            "cube_minimum_table_edge_inset_m": cube_edge_inset,
        },
        "delta": {
            "table_top_lowering_m": table_lowering,
            "table_near_edge_forward_shift_m": table_front_shift,
            "target_forward_shift_m": target_forward_shift,
            "approach_waypoint_shift_m": waypoint_shift,
            "nominal_radial_margin_m": nominal_radial_margin,
        },
        "controller_reuse_diagnostic": {
            "baseline_final_observed_joint_envelope_margin_deg": (
                observed_joint_envelope_margin
            ),
            "existing_translation_only_controller_certified_for_candidate": False,
            "reason": (
                "The accepted Goal 4 final observation already reached the "
                "60-degree lower safety boundary within its 1-degree measurement "
                "tolerance. Radial geometry cannot prove safe joint-space reach "
                "for the lower/farther candidate; pose-aware IK must be designed "
                "and tested before the next Isaac gate."
            ),
        },
        "acceptance": {
            "checks": checks,
            "local_geometry_passed": True,
            "candidate_isaac_machine_passed": False,
            "candidate_visual_passed": False,
            "contact_or_grasp_authorized": False,
        },
        "scope": {
            "gpu_started": False,
            "isaac_started": False,
            "real_hardware_commanded": False,
            "gripper_commanded": False,
            "target_cube_moved": False,
            "policy_or_checkpoint_loaded": False,
            "proof_limit": (
                "Necessary geometry checks only; candidate IK, collision-free "
                "trajectory, posture quality, and Viewer appearance remain remote."
            ),
        },
    }


def render_scene_calibration_svg(report: dict[str, Any]) -> str:
    baseline = report["baseline"]
    candidate = report["candidate"]
    neutral = baseline["validated_neutral_wrist_world_m"]
    reached = baseline["validated_final_wrist_world_m"]
    neutral_radius = baseline["validated_neutral_wrist_origin_radius_m"]

    side_left, side_top, side_width, side_height = 60.0, 115.0, 500.0, 440.0
    top_left, top_top, top_width, top_height = 640.0, 115.0, 500.0, 440.0
    y_min, y_max, z_max = -0.12, 0.50, 0.38
    x_min, x_max = -0.30, 0.30

    def side_x(y_value: float) -> float:
        return side_left + (y_value - y_min) / (y_max - y_min) * side_width

    def side_y(z_value: float) -> float:
        return side_top + side_height - z_value / z_max * side_height

    def top_x(x_value: float) -> float:
        return top_left + (x_value - x_min) / (x_max - x_min) * top_width

    def top_y(y_value: float) -> float:
        return top_top + top_height - (y_value - y_min) / (y_max - y_min) * top_height

    def side_box(
        center: list[float],
        size: list[float],
        *,
        css_class: str,
    ) -> str:
        y0 = center[1] - size[1] / 2
        z0 = center[2] - size[2] / 2
        return (
            f'<rect class="{css_class}" x="{side_x(y0):.2f}" '
            f'y="{side_y(z0 + size[2]):.2f}" '
            f'width="{side_x(y0 + size[1]) - side_x(y0):.2f}" '
            f'height="{side_y(z0) - side_y(z0 + size[2]):.2f}"/>'
        )

    def top_box(
        center: list[float],
        size: list[float],
        *,
        css_class: str,
    ) -> str:
        x0 = center[0] - size[0] / 2
        y0 = center[1] - size[1] / 2
        return (
            f'<rect class="{css_class}" x="{top_x(x0):.2f}" '
            f'y="{top_y(y0 + size[1]):.2f}" '
            f'width="{top_x(x0 + size[0]) - top_x(x0):.2f}" '
            f'height="{top_y(y0) - top_y(y0 + size[1]):.2f}"/>'
        )

    baseline_table_size = [0.5, 0.3, 0.04]
    baseline_cube_size = [0.05, 0.05, 0.05]
    candidate_table = candidate["table_center_world_m"]
    candidate_cube = candidate["target_cube_center_world_m"]
    candidate_waypoint = candidate["approach_target_world_m"]
    baseline_table = baseline["table_center_world_m"]
    baseline_cube = baseline["target_cube_center_world_m"]
    baseline_waypoint = baseline["approach_target_world_m"]
    reach_radius_x_px = neutral_radius / (y_max - y_min) * side_width
    reach_radius_y_px = neutral_radius / z_max * side_height
    keepout_radius_px = 0.10 / (x_max - x_min) * top_width

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" viewBox="0 0 1200 680">
  <defs>
    <clipPath id="side-plot-clip">
      <rect x="{side_left}" y="{side_top}" width="{side_width}" height="{side_height}" rx="10"/>
    </clipPath>
  </defs>
  <style>
    .title {{ font: 700 24px -apple-system, BlinkMacSystemFont, sans-serif; fill: #172033; }}
    .subtitle {{ font: 14px -apple-system, BlinkMacSystemFont, sans-serif; fill: #526078; }}
    .panel-title {{ font: 700 17px -apple-system, BlinkMacSystemFont, sans-serif; fill: #172033; }}
    .label {{ font: 13px ui-monospace, SFMono-Regular, monospace; fill: #172033; }}
    .small {{ font: 12px -apple-system, BlinkMacSystemFont, sans-serif; fill: #526078; }}
    .grid {{ stroke: #dbe2ec; stroke-width: 1; }}
    .axis {{ stroke: #6b778d; stroke-width: 1.5; }}
    .old-table {{ fill: #b8c0cc55; stroke: #8994a6; stroke-width: 2; stroke-dasharray: 7 6; }}
    .old-cube {{ fill: #b8c0cc77; stroke: #8994a6; stroke-width: 2; stroke-dasharray: 7 6; }}
    .new-table {{ fill: #d7b47a; stroke: #7b532b; stroke-width: 2; }}
    .new-cube {{ fill: #ef6654; stroke: #a52d24; stroke-width: 2; }}
    .reach {{ fill: none; stroke: #79a8e8; stroke-width: 2; stroke-dasharray: 5 5; }}
    .keepout {{ fill: #ef665422; stroke: #d64a3b; stroke-width: 2; stroke-dasharray: 5 5; }}
    .waypoint-old {{ fill: #8994a6; }}
    .waypoint-new {{ fill: #1769aa; }}
    .evidence {{ fill: #198754; }}
    .origin {{ fill: #172033; }}
  </style>
  <rect width="1200" height="680" fill="#f7f9fc"/>
  <text class="title" x="60" y="42">DOFBOT pre-grasp scene calibration — local geometry preview</text>
  <text class="subtitle" x="60" y="70">Solid = lower/farther candidate · dashed gray = Goal 4 baseline · +Y = physical workspace front</text>

  <rect x="{side_left}" y="{side_top}" width="{side_width}" height="{side_height}" rx="10" fill="white" stroke="#cad3df"/>
  <text class="panel-title" x="{side_left}" y="100">Side view (world Y–Z)</text>
  <line class="grid" x1="{side_left}" y1="{side_y(0.08):.2f}" x2="{side_left + side_width}" y2="{side_y(0.08):.2f}"/>
  <line class="grid" x1="{side_left}" y1="{side_y(0.12):.2f}" x2="{side_left + side_width}" y2="{side_y(0.12):.2f}"/>
  <line class="axis" x1="{side_left}" y1="{side_y(0):.2f}" x2="{side_left + side_width}" y2="{side_y(0):.2f}"/>
  <line class="axis" x1="{side_x(0):.2f}" y1="{side_top}" x2="{side_x(0):.2f}" y2="{side_top + side_height}"/>
  <ellipse class="reach" cx="{side_x(0):.2f}" cy="{side_y(0):.2f}" rx="{reach_radius_x_px:.2f}" ry="{reach_radius_y_px:.2f}" clip-path="url(#side-plot-clip)"/>
  <rect x="{side_x(-0.06):.2f}" y="{side_y(0.03):.2f}" width="{side_x(0.06)-side_x(-0.06):.2f}" height="{side_y(0)-side_y(0.03):.2f}" fill="#525d70"/>
  {side_box(baseline_table, baseline_table_size, css_class="old-table")}
  {side_box(baseline_cube, baseline_cube_size, css_class="old-cube")}
  {side_box(candidate_table, candidate["table_size_m"], css_class="new-table")}
  {side_box(candidate_cube, candidate["target_cube_size_m"], css_class="new-cube")}
  <circle class="waypoint-old" cx="{side_x(baseline_waypoint[1]):.2f}" cy="{side_y(baseline_waypoint[2]):.2f}" r="6"/>
  <circle class="waypoint-new" cx="{side_x(candidate_waypoint[1]):.2f}" cy="{side_y(candidate_waypoint[2]):.2f}" r="7"/>
  <circle class="evidence" cx="{side_x(neutral[1]):.2f}" cy="{side_y(neutral[2]):.2f}" r="6"/>
  <circle class="evidence" cx="{side_x(reached[1]):.2f}" cy="{side_y(reached[2]):.2f}" r="6"/>
  <line x1="{side_x(0):.2f}" y1="{side_y(0):.2f}" x2="{side_x(candidate_waypoint[1]):.2f}" y2="{side_y(candidate_waypoint[2]):.2f}" stroke="#1769aa" stroke-width="2"/>
  <text class="small" x="{side_x(candidate_waypoint[1])+10:.2f}" y="{side_y(candidate_waypoint[2])-8:.2f}">candidate waypoint</text>
  <text class="small" x="{side_x(neutral[1])+10:.2f}" y="{side_y(neutral[2])-8:.2f}">verified neutral wrist</text>
  <text class="small" x="{side_x(reached[1])+10:.2f}" y="{side_y(reached[2])-8:.2f}">Goal 4 reached wrist</text>
  <text class="small" x="{side_left+12}" y="{side_top+24}">dashed arc: neutral wrist radius only (not an IK proof)</text>
  <text class="label" x="{side_left+12}" y="{side_top+side_height-14}">table top 0.12 → 0.08 m · cube y 0.18 → 0.25 m</text>

  <rect x="{top_left}" y="{top_top}" width="{top_width}" height="{top_height}" rx="10" fill="white" stroke="#cad3df"/>
  <text class="panel-title" x="{top_left}" y="100">Top view (world X–Y)</text>
  <line class="axis" x1="{top_x(0):.2f}" y1="{top_top}" x2="{top_x(0):.2f}" y2="{top_top+top_height}"/>
  <line class="axis" x1="{top_left}" y1="{top_y(0):.2f}" x2="{top_left+top_width}" y2="{top_y(0):.2f}"/>
  <circle class="keepout" cx="{top_x(0):.2f}" cy="{top_y(0):.2f}" r="{keepout_radius_px:.2f}"/>
  {top_box(baseline_table, baseline_table_size, css_class="old-table")}
  {top_box(baseline_cube, baseline_cube_size, css_class="old-cube")}
  {top_box(candidate_table, candidate["table_size_m"], css_class="new-table")}
  {top_box(candidate_cube, candidate["target_cube_size_m"], css_class="new-cube")}
  <circle class="origin" cx="{top_x(0):.2f}" cy="{top_y(0):.2f}" r="6"/>
  <line x1="{top_left+top_width-45}" y1="{top_y(0):.2f}" x2="{top_left+top_width-45}" y2="{top_y(0.10):.2f}" stroke="#1769aa" stroke-width="3"/>
  <polygon points="{top_left+top_width-45},{top_y(0.12):.2f} {top_left+top_width-52},{top_y(0.10):.2f} {top_left+top_width-38},{top_y(0.10):.2f}" fill="#1769aa"/>
  <text class="small" x="{top_left+top_width-115}" y="{top_y(0.13):.2f}">+Y front</text>
  <text class="label" x="{top_left+12}" y="{top_top+top_height-14}">near edge 0.10 → 0.16 m · base keepout = 0.10 m</text>

  <text class="label" x="60" y="605">Local geometry: PASS · current controller reuse: NOT CERTIFIED · Isaac/Viewer: PENDING</text>
  <text class="subtitle" x="60" y="634">No GPU, Isaac, gripper, target motion, policy, checkpoint, or real hardware was used.</text>
  <text class="subtitle" x="60" y="656">Next paid gate must verify pose-aware IK, collision clearance, posture quality, and the user-visible scene.</text>
</svg>
"""  # noqa: E501


def main() -> None:
    args = _parse_args()
    report = build_scene_calibration(
        baseline_config_path=args.baseline_config,
        candidate_config_path=args.candidate_config,
        isaac_artifact_path=args.isaac_artifact,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_svg.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output_svg.write_text(
        render_scene_calibration_svg(report),
        encoding="utf-8",
    )
    print(
        "[INFO] "
        f"candidate={report['sources']['candidate_config']['path']} "
        f"table_top_z_m={report['candidate']['table_top_z_m']:.3f} "
        f"target_y_m={report['candidate']['target_cube_center_world_m'][1]:.3f} "
        f"radial_margin_m={report['delta']['nominal_radial_margin_m']:.3f} "
        f"json={args.output_json} svg={args.output_svg}",
        flush=True,
    )


if __name__ == "__main__":
    main()
