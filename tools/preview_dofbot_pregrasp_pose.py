"""Build the GPU-free DOFBOT pose-aware pre-grasp preparation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .dofbot_pregrasp_pose import (
        derive_grasp_frame,
        evaluate_pregrasp_observation,
        load_pregrasp_pose_config,
        next_pose_command,
        quantize_pose_command,
    )
    from .dofbot_reaching import load_reaching_config
except ImportError:
    from dofbot_pregrasp_pose import (
        derive_grasp_frame,
        evaluate_pregrasp_observation,
        load_pregrasp_pose_config,
        next_pose_command,
        quantize_pose_command,
    )
    from dofbot_reaching import load_reaching_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed local preview of pose-aware DOFBOT pre-grasp."
    )
    parser.add_argument(
        "--pose-config",
        type=Path,
        default=Path("configs/dofbot/pregrasp/goal5_pose_aware_pregrasp.json"),
    )
    parser.add_argument(
        "--scene-config",
        type=Path,
        default=Path(
            "configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json"
        ),
    )
    parser.add_argument(
        "--asset-contract",
        type=Path,
        default=Path("artifacts/dofbot/asset_contract.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/dofbot-pregrasp-pose-contract.json"),
    )
    return parser.parse_args()


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _body_positions() -> dict[str, tuple[float, float, float]]:
    return {
        "link2": (0.0, 0.08, 0.30),
        "link3": (0.0, 0.12, 0.28),
        "link4": (0.0, 0.18, 0.27),
        "Wrist_Twist": (0.0, 0.25, 0.255),
        "Finger_Left_01": (-0.02, 0.24, 0.24),
        "Finger_Right_01": (0.02, 0.24, 0.24),
        "Finger_Left_02": (-0.023, 0.245, 0.215),
        "Finger_Right_02": (0.023, 0.245, 0.215),
        "Finger_Left_03": (-0.025, 0.25, 0.195),
        "Finger_Right_03": (0.025, 0.25, 0.195),
    }


def build_preview(
    *,
    pose_config_path: Path,
    scene_config_path: Path,
    asset_contract_path: Path,
) -> dict[str, Any]:
    pose, pose_sha256 = load_pregrasp_pose_config(pose_config_path)
    scene, scene_sha256 = load_reaching_config(scene_config_path)
    asset, asset_sha256 = _read_json(asset_contract_path)
    body_names = asset.get("articulation", {}).get("body_names")
    asset_passed = asset.get("acceptance", {}).get("passed") is True
    if not isinstance(body_names, list) or not all(
        isinstance(name, str) for name in body_names
    ):
        raise ValueError("asset contract body_names are missing")

    positions = _body_positions()
    frame = derive_grasp_frame(
        wrist_position_world_m=positions[pose.grasp_frame.wrist_body_name],
        left_tip_position_world_m=positions[
            pose.grasp_frame.left_tip_body_name
        ],
        right_tip_position_world_m=positions[
            pose.grasp_frame.right_tip_body_name
        ],
        config=pose.grasp_frame,
    )
    pose_jacobian = (
        (0.10, 0.00, 0.00, 0.00),
        (0.00, 0.10, 0.00, 0.00),
        (0.00, 0.00, 0.10, 0.05),
        (0.00, 0.50, 0.00, 0.00),
        (0.00, 0.00, 0.50, 0.20),
        (0.30, 0.00, 0.00, 0.30),
    )
    offset_frame = derive_grasp_frame(
        wrist_position_world_m=(0.0, 0.23, 0.275),
        left_tip_position_world_m=(-0.025, 0.23, 0.215),
        right_tip_position_world_m=(0.025, 0.23, 0.215),
        config=pose.grasp_frame,
    )
    float_command = next_pose_command(
        frame=offset_frame,
        pose_jacobian=pose_jacobian,
        current_angles_deg=(90.0, 90.0, 90.0, 90.0),
        previous_velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
        solver=pose.solver,
        target=pose.target_pose,
    )
    command = quantize_pose_command(
        float_command,
        previous_command_angles_deg=(90.0, 90.0, 90.0, 90.0),
        previous_velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
        solver=pose.solver,
    )
    safe_evaluation = evaluate_pregrasp_observation(
        config=pose,
        frame=frame,
        body_positions_world_m=positions,
        table_center_world_m=scene.table.center_world_m,
        table_size_m=scene.table.size_m,
        target_center_world_m=scene.target_cube.center_world_m,
        target_size_m=scene.target_cube.size_m,
        target_is_static=scene.target_cube.static,
        angles_deg=(90.0, 80.0, 80.0, 90.0),
        velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
        accelerations_deg_s2=(0.0, 0.0, 0.0, 0.0),
        maximum_contact_force_n=0.0,
    )
    collision_positions = dict(positions)
    collision_positions[pose.grasp_frame.left_tip_body_name] = (
        -0.01,
        0.25,
        0.105,
    )
    collision_positions[pose.grasp_frame.right_tip_body_name] = (
        0.01,
        0.25,
        0.105,
    )
    collision_evaluation = evaluate_pregrasp_observation(
        config=pose,
        frame=frame,
        body_positions_world_m=collision_positions,
        table_center_world_m=scene.table.center_world_m,
        table_size_m=scene.table.size_m,
        target_center_world_m=scene.target_cube.center_world_m,
        target_size_m=scene.target_cube.size_m,
        target_is_static=True,
        angles_deg=(90.0, 80.0, 80.0, 90.0),
        velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
        accelerations_deg_s2=(0.0, 0.0, 0.0, 0.0),
        maximum_contact_force_n=5.0,
    )
    reversed_frame = derive_grasp_frame(
        wrist_position_world_m=(0.0, 0.25, 0.255),
        left_tip_position_world_m=(0.025, 0.25, 0.195),
        right_tip_position_world_m=(-0.025, 0.25, 0.195),
        config=pose.grasp_frame,
    )
    reversed_evaluation = evaluate_pregrasp_observation(
        config=pose,
        frame=reversed_frame,
        body_positions_world_m=positions,
        table_center_world_m=scene.table.center_world_m,
        table_size_m=scene.table.size_m,
        target_center_world_m=scene.target_cube.center_world_m,
        target_size_m=scene.target_cube.size_m,
        target_is_static=True,
        angles_deg=(90.0, 80.0, 80.0, 90.0),
        velocities_deg_s=(0.0, 0.0, 0.0, 0.0),
        accelerations_deg_s2=(0.0, 0.0, 0.0, 0.0),
        maximum_contact_force_n=0.0,
    )
    command_min = (
        pose.solver.safe_angle_min_deg + pose.solver.command_limit_margin_deg
    )
    command_max = (
        pose.solver.safe_angle_max_deg - pose.solver.command_limit_margin_deg
    )
    required_bodies = {
        pose.grasp_frame.wrist_body_name,
        pose.grasp_frame.left_tip_body_name,
        pose.grasp_frame.right_tip_body_name,
        *pose.collision.critical_body_names,
    }
    checks = {
        "asset_contract_sha256_matches": (
            asset_sha256 == pose.source_contracts.asset_contract_sha256
        ),
        "asset_contract_passed": asset_passed,
        "required_grasp_and_collision_bodies_present": (
            required_bodies.issubset(set(body_names))
        ),
        "scene_config_sha256_matches": (
            scene_sha256 == pose.source_contracts.scene_config_sha256
        ),
        "target_position_matches_scene_waypoint": (
            pose.target_pose.position_world_m == scene.approach_target_world_m
        ),
        "target_cube_is_static": scene.target_cube.static,
        "grasp_origin_is_terminal_finger_midpoint": (
            frame.origin_world_m == pose.target_pose.position_world_m
        ),
        "approach_axis_is_world_down": (
            frame.approach_axis_world_unit
            == pose.target_pose.approach_axis_world_unit
        ),
        "closing_axis_is_world_positive_x": (
            frame.closing_axis_world_unit
            == pose.target_pose.closing_axis_world_unit
        ),
        "frame_axes_are_orthogonal": (
            abs(
                sum(
                    left * right
                    for left, right in zip(
                        frame.approach_axis_world_unit,
                        frame.closing_axis_world_unit,
                        strict=True,
                    )
                )
            )
            <= 1e-9
        ),
        "only_joint1_through_joint4_are_controlled": (
            pose.solver.controlled_joint_names
            == ("joint1", "joint2", "joint3", "joint4")
        ),
        "wrist_twist_closing_axis_is_monitor_only": (
            pose.target_pose.closing_axis_control
            == "monitor_only_wrist_twist_uncontrolled"
        ),
        "synthetic_pose_command_preserves_joint_margin": all(
            command_min <= value <= command_max for value in command.angles_deg
        ),
        "synthetic_pose_command_respects_velocity_limit": all(
            abs(value) <= pose.solver.maximum_joint_velocity_deg_s
            for value in command.velocities_deg_s
        ),
        "synthetic_pose_command_respects_acceleration_ramp": all(
            abs(value) / pose.solver.control_dt_s
            <= pose.solver.maximum_joint_acceleration_deg_s2 + 1e-9
            for value in command.velocities_deg_s
        ),
        "safe_synthetic_pregrasp_observation_passed": safe_evaluation["passed"],
        "collision_probe_rejected": (
            collision_evaluation["checks"][
                "terminal_finger_centers_remain_precontact"
            ]
            is False
            and collision_evaluation["checks"][
                "contact_reporter_force_remains_below_threshold"
            ]
            is False
        ),
        "reversed_fixed_closing_axis_rejected": (
            reversed_evaluation["checks"][
                "fixed_closing_axis_is_acceptable_without_wrist_command"
            ]
            is False
        ),
        "contact_remains_unauthorized": (
            pose.collision.contact_authorized is False
        ),
        "real_hardware_not_commanded": True,
        "gpu_not_started": True,
    }
    return {
        "schema_version": 1,
        "experiment": "dofbot_pose_aware_pregrasp_local_preparation",
        "sources": {
            "pose_config": {
                "path": str(pose_config_path),
                "sha256": pose_sha256,
            },
            "scene_config": {
                "path": str(scene_config_path),
                "sha256": scene_sha256,
            },
            "asset_contract": {
                "path": str(asset_contract_path),
                "sha256": asset_sha256,
            },
        },
        "grasp_frame": frame.to_dict(),
        "target_pose": {
            "position_world_m": list(pose.target_pose.position_world_m),
            "approach_axis_world_unit": list(
                pose.target_pose.approach_axis_world_unit
            ),
            "closing_axis_world_unit": list(
                pose.target_pose.closing_axis_world_unit
            ),
            "closing_axis_control": pose.target_pose.closing_axis_control,
        },
        "solver_probe": {
            "algorithm": (
                "weighted_damped_least_squares_position_plus_approach_axis"
            ),
            "pose_jacobian_shape": [6, 4],
            "preferred_angles_deg": list(pose.solver.preferred_angles_deg),
            "command": command.to_dict(),
        },
        "collision_probe": {
            "mode": "body_center_signed_box_distance_proxy",
            "safe_evaluation": safe_evaluation,
            "deliberate_terminal_finger_collision_passed": (
                collision_evaluation["passed"]
            ),
            "reversed_closing_axis_passed": reversed_evaluation["passed"],
            "limitation": (
                "Body-center distance is a local proxy. Isaac contact reports "
                "and full collision geometry remain required remotely."
            ),
        },
        "acceptance": {
            "checks": checks,
            "local_preparation_passed": all(checks.values()),
            "candidate_isaac_machine_passed": False,
            "candidate_visual_passed": False,
            "contact_or_grasp_authorized": False,
        },
        "scope": {
            "gpu_started": False,
            "isaac_started": False,
            "real_hardware_commanded": False,
            "wrist_twist_commanded": False,
            "gripper_commanded": False,
            "target_cube_moved": False,
            "camera_used_as_controller_input": False,
            "policy_or_checkpoint_loaded": False,
        },
    }


def main() -> None:
    args = _parse_args()
    result = build_preview(
        pose_config_path=args.pose_config,
        scene_config_path=args.scene_config,
        asset_contract_path=args.asset_contract,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[INFO] "
        f"config={result['sources']['pose_config']['path']} "
        f"checks={sum(result['acceptance']['checks'].values())}/"
        f"{len(result['acceptance']['checks'])} "
        f"output={args.output}",
        flush=True,
    )
    if not result["acceptance"]["local_preparation_passed"]:
        failed = [
            name
            for name, passed in result["acceptance"]["checks"].items()
            if not passed
        ]
        raise SystemExit(
            "DOFBOT pose-aware pre-grasp local preparation failed: "
            + ", ".join(failed)
        )


if __name__ == "__main__":
    main()
