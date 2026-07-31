"""Build the GPU-free DOFBOT pose-aware pre-grasp preparation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

try:
    from .dofbot_gravity_feed_forward import (
        load_accepted_gravity_feed_forward_runtime,
    )
    from .dofbot_pregrasp_pose import (
        VALIDATED_JOINT_CANDIDATE_CONTROL_MODE,
        derive_grasp_frame,
        evaluate_pregrasp_observation,
        load_pregrasp_pose_config,
        next_pregrasp_command,
        validated_joint_candidate_command_reached,
    )
    from .dofbot_reaching import load_reaching_config
except ImportError:
    from dofbot_gravity_feed_forward import (
        load_accepted_gravity_feed_forward_runtime,
    )
    from dofbot_pregrasp_pose import (
        VALIDATED_JOINT_CANDIDATE_CONTROL_MODE,
        derive_grasp_frame,
        evaluate_pregrasp_observation,
        load_pregrasp_pose_config,
        next_pregrasp_command,
        validated_joint_candidate_command_reached,
    )
    from dofbot_reaching import load_reaching_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed local preview of pose-aware DOFBOT pre-grasp."
    )
    parser.add_argument(
        "--pose-config",
        type=Path,
        default=Path("configs/dofbot/pregrasp/goal5_angled_pregrasp.json"),
    )
    parser.add_argument(
        "--scene-config",
        type=Path,
        default=Path(
            "configs/dofbot/reaching/"
            "goal5_angled_pregrasp_scene_candidate.json"
        ),
    )
    parser.add_argument(
        "--asset-contract",
        type=Path,
        default=Path("artifacts/dofbot/asset_contract.json"),
    )
    parser.add_argument(
        "--actuator-config",
        type=Path,
        default=Path(
            "configs/dofbot/calibration/"
            "goal5_gravity_feed_forward_diagnostic.json"
        ),
    )
    parser.add_argument(
        "--actuator-result",
        type=Path,
        default=Path(
            "artifacts/dofbot/"
            "gravity_feed_forward_result_2026-07-31.json"
        ),
    )
    parser.add_argument(
        "--runner",
        type=Path,
        default=Path("tools/run_dofbot_pregrasp.py"),
    )
    parser.add_argument(
        "--gravity-runtime",
        type=Path,
        default=Path("tools/dofbot_gravity_feed_forward_runtime.py"),
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


def _shift(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    distance: float,
) -> tuple[float, float, float]:
    return tuple(
        origin[index] + distance * direction[index] for index in range(3)
    )  # type: ignore[return-value]


def _close_vector(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> bool:
    return all(
        math.isclose(
            left_value,
            right_value,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for left_value, right_value in zip(left, right, strict=True)
    )


def _target_body_positions(pose) -> dict[str, tuple[float, float, float]]:
    origin = pose.target_pose.position_world_m
    approach = pose.target_pose.approach_axis_world_unit
    closing = pose.target_pose.closing_axis_world_unit
    left_tip = _shift(origin, closing, -0.025)
    right_tip = _shift(origin, closing, 0.025)
    left_02 = _shift(_shift(origin, approach, -0.02), closing, -0.023)
    right_02 = _shift(_shift(origin, approach, -0.02), closing, 0.023)
    left_01 = _shift(_shift(origin, approach, -0.04), closing, -0.02)
    right_01 = _shift(_shift(origin, approach, -0.04), closing, 0.02)
    return {
        "link2": _shift(_shift(origin, approach, -0.19), (0.0, 0.0, 1.0), 0.04),
        "link3": _shift(_shift(origin, approach, -0.14), (0.0, 0.0, 1.0), 0.02),
        "link4": _shift(origin, approach, -0.09),
        "Wrist_Twist": _shift(origin, approach, -0.06),
        "Finger_Left_01": left_01,
        "Finger_Right_01": right_01,
        "Finger_Left_02": left_02,
        "Finger_Right_02": right_02,
        "Finger_Left_03": left_tip,
        "Finger_Right_03": right_tip,
    }


def build_preview(
    *,
    pose_config_path: Path,
    scene_config_path: Path,
    asset_contract_path: Path,
    actuator_config_path: Path | None = None,
    actuator_result_path: Path | None = None,
    runner_path: Path | None = None,
    gravity_runtime_path: Path | None = None,
) -> dict[str, Any]:
    project_dir = Path(__file__).resolve().parents[1]
    actuator_config_path = actuator_config_path or (
        project_dir
        / "configs/dofbot/calibration/"
        "goal5_gravity_feed_forward_diagnostic.json"
    )
    actuator_result_path = actuator_result_path or (
        project_dir
        / "artifacts/dofbot/"
        "gravity_feed_forward_result_2026-07-31.json"
    )
    runner_path = runner_path or project_dir / "tools/run_dofbot_pregrasp.py"
    gravity_runtime_path = gravity_runtime_path or (
        project_dir / "tools/dofbot_gravity_feed_forward_runtime.py"
    )
    actuator_runtime = load_accepted_gravity_feed_forward_runtime(
        calibration_config_path=actuator_config_path,
        machine_result_path=actuator_result_path,
    )
    runner_source = runner_path.read_text(encoding="utf-8")
    gravity_runtime_source = gravity_runtime_path.read_text(encoding="utf-8")
    pose, pose_sha256 = load_pregrasp_pose_config(pose_config_path)
    scene, scene_sha256 = load_reaching_config(scene_config_path)
    asset, asset_sha256 = _read_json(asset_contract_path)
    body_names = asset.get("articulation", {}).get("body_names")
    asset_passed = asset.get("acceptance", {}).get("passed") is True
    if not isinstance(body_names, list) or not all(
        isinstance(name, str) for name in body_names
    ):
        raise ValueError("asset contract body_names are missing")

    positions = _target_body_positions(pose)
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
    offset_origin = _shift(
        pose.target_pose.position_world_m,
        pose.target_pose.approach_axis_world_unit,
        -0.02,
    )
    offset_frame = derive_grasp_frame(
        wrist_position_world_m=_shift(
            offset_origin,
            pose.target_pose.approach_axis_world_unit,
            -0.06,
        ),
        left_tip_position_world_m=_shift(
            offset_origin,
            pose.target_pose.closing_axis_world_unit,
            -0.025,
        ),
        right_tip_position_world_m=_shift(
            offset_origin,
            pose.target_pose.closing_axis_world_unit,
            0.025,
        ),
        config=pose.grasp_frame,
    )
    zero = (0.0, 0.0, 0.0, 0.0)
    previous_command = (90.0, 90.0, 90.0, 90.0)
    previous_velocity = zero
    synthetic_tracking_lag = tuple(
        min(
            pose.solver.safe_angle_max_deg,
            max(
                pose.solver.safe_angle_min_deg,
                preferred + lag,
            ),
        )
        for preferred, lag in zip(
            pose.solver.preferred_angles_deg,
            (0.0, 0.3, 4.5, 5.5),
            strict=True,
        )
    )
    command_trajectory = []
    trajectory_steps = (
        pose.solver.maximum_steps
        if (
            pose.solver.control_mode
            == VALIDATED_JOINT_CANDIDATE_CONTROL_MODE
        )
        else 1
    )
    for _ in range(trajectory_steps):
        command = next_pregrasp_command(
            frame=offset_frame,
            pose_jacobian=pose_jacobian,
            observed_angles_deg=synthetic_tracking_lag,
            previous_command_angles_deg=previous_command,
            previous_command_velocities_deg_s=previous_velocity,
            solver=pose.solver,
            target=pose.target_pose,
        )
        command_trajectory.append(command)
        previous_command = command.angles_deg
        previous_velocity = command.velocities_deg_s
        if validated_joint_candidate_command_reached(
            command_angles_deg=previous_command,
            command_velocities_deg_s=previous_velocity,
            solver=pose.solver,
        ):
            break
    command = command_trajectory[-1]
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
    collision_positions[pose.grasp_frame.left_tip_body_name] = _shift(
        scene.target_cube.center_world_m,
        pose.target_pose.closing_axis_world_unit,
        -0.01,
    )
    collision_positions[pose.grasp_frame.right_tip_body_name] = _shift(
        scene.target_cube.center_world_m,
        pose.target_pose.closing_axis_world_unit,
        0.01,
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
        wrist_position_world_m=positions[pose.grasp_frame.wrist_body_name],
        left_tip_position_world_m=positions[
            pose.grasp_frame.right_tip_body_name
        ],
        right_tip_position_world_m=positions[
            pose.grasp_frame.left_tip_body_name
        ],
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
    write_index = runner_source.find("scene.write_data_to_sim()")
    apply_index = runner_source.find(
        "gravity_sample = gravity_feed_forward.apply_before_step()"
    )
    step_index = runner_source.find("sim.step(render=render)")
    probe_index = runner_source.find(
        "gravity_feed_forward = BoundedGravityFeedForward("
    )
    first_pose_index = runner_source.find(
        "initialization_api_calls = _issue_angles("
    )
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
            _close_vector(
                pose.target_pose.position_world_m,
                scene.approach_target_world_m,
            )
        ),
        "target_cube_is_static": scene.target_cube.static,
        "grasp_origin_is_terminal_finger_midpoint": (
            _close_vector(
                frame.origin_world_m,
                pose.target_pose.position_world_m,
            )
        ),
        "approach_axis_matches_target": (
            _close_vector(
                frame.approach_axis_world_unit,
                pose.target_pose.approach_axis_world_unit,
            )
        ),
        "closing_axis_matches_target": (
            _close_vector(
                frame.closing_axis_world_unit,
                pose.target_pose.closing_axis_world_unit,
            )
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
            command_min <= value <= command_max
            for trajectory_command in command_trajectory
            for value in trajectory_command.angles_deg
        ),
        "synthetic_pose_command_respects_velocity_limit": all(
            abs(value) <= pose.solver.maximum_joint_velocity_deg_s
            for trajectory_command in command_trajectory
            for value in trajectory_command.velocities_deg_s
        ),
        "synthetic_pose_command_respects_acceleration_ramp": all(
            abs(after - before) / pose.solver.control_dt_s
            <= pose.solver.maximum_joint_acceleration_deg_s2 + 1e-9
            for before_command, after_command in zip(
                [zero, *[
                    item.velocities_deg_s
                    for item in command_trajectory[:-1]
                ]],
                [
                    item.velocities_deg_s
                    for item in command_trajectory
                ],
                strict=True,
            )
            for before, after in zip(
                before_command,
                after_command,
                strict=True,
            )
        ),
        "validated_candidate_reaches_exact_stopped_api_target": (
            validated_joint_candidate_command_reached(
                command_angles_deg=command.angles_deg,
                command_velocities_deg_s=command.velocities_deg_s,
                solver=pose.solver,
            )
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
        "accepted_actuator_machine_result_bound": (
            actuator_runtime.selected_case_name
            == "bounded_gravity_feed_forward"
            and actuator_runtime.drive_type == "force"
            and actuator_runtime.stiffness == 1048.0
            and actuator_runtime.damping == 53.0
            and actuator_runtime.effort_limit_sim == 100.0
            and actuator_runtime.gravity_compensation_feed_forward
            and actuator_runtime.gravity_compensation_effort_limit == 5.2
        ),
        "actuator_runtime_probe_occurs_before_first_pose": (
            -1 < probe_index < first_pose_index
        ),
        "gravity_feed_forward_applies_after_pd_write_before_step": (
            -1 < write_index < apply_index < step_index
        ),
        "native_warp_setter_is_shared_with_calibration": all(
            value in gravity_runtime_source
            for value in (
                'getattr(self._robot, "root_view", None)',
                "dtype=wp.float32",
                "dtype=wp.int32",
            )
        ),
        "pregrasp_runner_records_actuator_failure_classification": (
            '"failed_checks": failed_checks' in runner_source
            and '"decision": _failure_decision(failed_checks)'
            in runner_source
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
            "actuator_config": {
                "path": str(actuator_config_path),
                "sha256": actuator_runtime.calibration_config_sha256,
            },
            "actuator_machine_result": {
                "path": str(actuator_result_path),
                "sha256": actuator_runtime.machine_result_sha256,
            },
            "pregrasp_runner": {
                "path": str(runner_path),
                "sha256": hashlib.sha256(runner_source.encode()).hexdigest(),
            },
            "gravity_feed_forward_runtime": {
                "path": str(gravity_runtime_path),
                "sha256": hashlib.sha256(
                    gravity_runtime_source.encode()
                ).hexdigest(),
            },
        },
        "actuator_runtime": actuator_runtime.to_dict(),
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
            "algorithm": pose.solver.control_mode,
            "pose_jacobian_shape": [6, 4],
            "preferred_angles_deg": list(pose.solver.preferred_angles_deg),
            "synthetic_observed_tracking_lag_angles_deg": list(
                synthetic_tracking_lag
            ),
            "command_trajectory": [
                item.to_dict() for item in command_trajectory
            ],
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
        actuator_config_path=args.actuator_config,
        actuator_result_path=args.actuator_result,
        runner_path=args.runner,
        gravity_runtime_path=args.gravity_runtime,
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
