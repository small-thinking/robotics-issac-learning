"""Run policy-free, pose-aware DOFBOT pre-grasp validation in Isaac Lab.

The controller commands joint1-joint4 through Yahboom's documented
``Arm_serial_servo_write`` boundary. It controls terminal-finger midpoint
position and approach direction. Wrist twist and gripper remain uncommanded;
the fixed closing-axis alignment is a monitored acceptance gate.
"""

# Isaac Lab modules must be imported after AppLauncher starts Kit.
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from isaaclab.app import AppLauncher

from dofbot_pregrasp_pose import (
    POSE_IK_CONTROL_MODE,
    PregraspPoseConfig,
    PregraspPoseError,
    derive_grasp_frame,
    evaluate_pregrasp_observation,
    load_pregrasp_pose_config,
    maximum_joint_tracking_error_deg,
    next_pregrasp_command,
    validated_joint_candidate_command_reached,
)
from dofbot_reaching import DofbotReachingConfig, load_reaching_config

parser = argparse.ArgumentParser(
    description="Run fail-closed pose-aware DOFBOT pre-grasp validation."
)
parser.add_argument(
    "--asset-contract",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/artifacts/dofbot/asset_contract.json"
    ),
)
parser.add_argument(
    "--scene-config",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/configs/dofbot/reaching/"
        "goal5_angled_pregrasp_scene_candidate.json"
    ),
)
parser.add_argument(
    "--pose-config",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/configs/dofbot/pregrasp/"
        "goal5_angled_pregrasp.json"
    ),
)
parser.add_argument(
    "--output",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/artifacts/dofbot/"
        "pregrasp_machine_contract.json"
    ),
)
parser.add_argument(
    "--cycles",
    type=int,
    default=1,
    help="Number of complete cycles; use -1 for repeated Viewer playback.",
)
parser.add_argument(
    "--viewer-connection-hold-seconds",
    type=float,
    default=None,
)
parser.add_argument("--git-commit", default=None)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

if args_cli.cycles == 0 or args_cli.cycles < -1:
    raise PregraspPoseError("--cycles must be a positive integer or -1")
preflight_scene, preflight_scene_sha256 = load_reaching_config(
    args_cli.scene_config
)
preflight_pose, preflight_pose_sha256 = load_pregrasp_pose_config(
    args_cli.pose_config
)
preflight_asset_sha256 = hashlib.sha256(args_cli.asset_contract.read_bytes()).hexdigest()
if preflight_scene_sha256 != preflight_pose.source_contracts.scene_config_sha256:
    raise PregraspPoseError("pose config does not match the candidate scene config")
if preflight_asset_sha256 != preflight_pose.source_contracts.asset_contract_sha256:
    raise PregraspPoseError("pose config does not match the recorded asset contract")
if preflight_pose.target_pose.position_world_m != preflight_scene.approach_target_world_m:
    raise PregraspPoseError("pose target does not match the scene approach waypoint")
viewer_connection_hold_seconds = (
    float(preflight_pose.acceptance.viewer_connection_hold_seconds)
    if args_cli.viewer_connection_hold_seconds is None
    else args_cli.viewer_connection_hold_seconds
)
if (
    isinstance(viewer_connection_hold_seconds, bool)
    or not isinstance(viewer_connection_hold_seconds, (int, float))
    or not math.isfinite(float(viewer_connection_hold_seconds))
    or not 0.0 <= float(viewer_connection_hold_seconds) <= 60.0
):
    raise PregraspPoseError(
        "--viewer-connection-hold-seconds must be finite and in [0, 60]"
    )

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch
from pxr import PhysicsSchemaTools, UsdPhysics

import isaaclab.sim as sim_utils
import omni.physx
from isaaclab.scene import InteractiveScene

from dofbot_control_api import (
    CONTROLLED_JOINT_NAMES,
    DofbotArm,
    JointPositionCommand,
    YahboomServoApiAdapter,
)
from dofbot_contact_report import maximum_monitored_contact_force_n
from dofbot_motion_config import NEUTRAL_ANGLES_DEG
from dofbot_motion_plan import (
    assert_compatible_asset_contracts,
    validate_recorded_asset_contract,
)
from dofbot_pregrasp_scene_cfg import (
    CONTACT_BODY_NAMES,
    CONTACT_BODY_PATHS,
    DofbotPregraspSceneCfg,
)


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PregraspPoseError(f"{path} must contain a JSON object")
    return value


def _live_asset_contract(scene: InteractiveScene) -> dict[str, Any]:
    robot = scene["dofbot"]
    joint_limits = getattr(robot.data, "joint_pos_limits", None)
    if joint_limits is None:
        joint_limits = robot.data.soft_joint_pos_limits
    return {
        "articulation": {
            "joint_names": list(robot.joint_names),
            "default_joint_positions_rad": (
                robot.data.default_joint_pos[0].detach().cpu().tolist()
            ),
            "joint_position_limits_rad": (
                joint_limits[0].detach().cpu().tolist()
            ),
        }
    }


def _controlled_joint_ids(scene: InteractiveScene) -> list[int]:
    names = list(scene["dofbot"].joint_names)
    name_to_index = {name: index for index, name in enumerate(names)}
    missing = [name for name in CONTROLLED_JOINT_NAMES if name not in name_to_index]
    if missing:
        raise PregraspPoseError(f"live articulation is missing joints: {missing}")
    return [name_to_index[name] for name in CONTROLLED_JOINT_NAMES]


def _body_ids(
    scene: InteractiveScene,
    body_names: set[str],
) -> dict[str, int]:
    names = list(scene["dofbot"].body_names)
    name_to_index = {name: index for index, name in enumerate(names)}
    missing = sorted(body_names - set(name_to_index))
    if missing:
        raise PregraspPoseError(f"live articulation is missing bodies: {missing}")
    return {name: name_to_index[name] for name in body_names}


class _IsaacJointPositionBackend:
    """Smoothly execute complete four-joint targets in Isaac."""

    def __init__(
        self,
        *,
        scene: InteractiveScene,
        controlled_joint_ids: list[int],
        device: str,
    ) -> None:
        self._robot = scene["dofbot"]
        self._joint_ids = controlled_joint_ids
        self._device = device
        self._pending_goal: tuple[float, ...] | None = None
        self._pending_duration_s: float | None = None
        self._start: tuple[float, ...] | None = None
        self._goal: tuple[float, ...] | None = None
        self._duration_s = 0.0
        self._elapsed_s = 0.0

    def command_joint_positions(self, command: JointPositionCommand) -> None:
        self._pending_goal = tuple(command.positions_rad)
        self._pending_duration_s = command.duration_ms / 1000.0

    def advance(self, physics_dt: float) -> None:
        if self._pending_goal is not None:
            current = (
                self._robot.data.joint_pos[0, self._joint_ids]
                .detach()
                .cpu()
                .tolist()
            )
            self._start = tuple(float(value) for value in current)
            self._goal = self._pending_goal
            self._duration_s = self._pending_duration_s or physics_dt
            self._elapsed_s = 0.0
            self._pending_goal = None
            self._pending_duration_s = None
        if self._start is None or self._goal is None:
            return
        self._elapsed_s = min(self._elapsed_s + physics_dt, self._duration_s)
        progress = self._elapsed_s / self._duration_s
        smooth = progress * progress * (3.0 - 2.0 * progress)
        target = [
            start + (goal - start) * smooth
            for start, goal in zip(self._start, self._goal, strict=True)
        ]
        self._robot.set_joint_position_target(
            torch.tensor(
                [target],
                device=self._device,
                dtype=torch.float32,
            ),
            joint_ids=self._joint_ids,
        )

    def read_joint_positions(self) -> dict[str, float]:
        values = (
            self._robot.data.joint_pos[0, self._joint_ids]
            .detach()
            .cpu()
            .tolist()
        )
        return dict(zip(CONTROLLED_JOINT_NAMES, values, strict=True))


def _spawn_scene_boxes(config: DofbotReachingConfig) -> None:
    for box in (config.table, config.target_cube):
        spawn_cfg = sim_utils.CuboidCfg(
            size=box.size_m,
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(
                diffuse_color=box.color_rgb,
                roughness=0.8,
                metallic=0.0,
            ),
        )
        spawn_cfg.func(
            box.prim_path,
            spawn_cfg,
            translation=box.center_world_m,
        )


def _step_simulation(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    backend: _IsaacJointPositionBackend,
    physics_steps: int,
    render: bool,
) -> bool:
    for _ in range(physics_steps):
        if not simulation_app.is_running():
            return False
        try:
            backend.advance(sim.get_physics_dt())
            scene.write_data_to_sim()
            sim.step(render=render)
        except SystemExit as error:
            raise RuntimeError("Isaac requested process exit during pre-grasp") from error
        scene.update(sim.get_physics_dt())
    return True


def _hold(
    *,
    seconds: float,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    backend: _IsaacJointPositionBackend,
    render: bool,
) -> bool:
    if seconds <= 0.0:
        return True
    return _step_simulation(
        scene=scene,
        sim=sim,
        backend=backend,
        physics_steps=max(1, round(seconds / sim.get_physics_dt())),
        render=render,
    )


def _observed_angles_deg(arm: DofbotArm) -> tuple[float, float, float, float]:
    positions = arm.read_joint_positions()
    return tuple(
        90.0 + math.degrees(positions[name]) for name in CONTROLLED_JOINT_NAMES
    )  # type: ignore[return-value]


def _body_positions(
    scene: InteractiveScene,
    body_ids: dict[str, int],
) -> dict[str, tuple[float, float, float]]:
    result: dict[str, tuple[float, float, float]] = {}
    for name, body_id in body_ids.items():
        values = (
            scene["dofbot"].data.body_pos_w[0, body_id].detach().cpu().tolist()
        )
        result[name] = tuple(float(value) for value in values)  # type: ignore[assignment]
    return result


def _body_jacobian(
    *,
    scene: InteractiveScene,
    body_id: int,
    controlled_joint_ids: list[int],
) -> torch.Tensor:
    robot = scene["dofbot"]
    jacobian_body_id = body_id - 1 if robot.is_fixed_base else body_id
    if jacobian_body_id < 0:
        raise PregraspPoseError("grasp body cannot be the fixed articulation root")
    return robot.data.body_link_jacobian_w.torch[
        0,
        jacobian_body_id,
        0:6,
        controlled_joint_ids,
    ]


def _terminal_midpoint_jacobian(
    *,
    scene: InteractiveScene,
    left_tip_body_id: int,
    right_tip_body_id: int,
    controlled_joint_ids: list[int],
) -> list[list[float]]:
    jacobian = (
        _body_jacobian(
            scene=scene,
            body_id=left_tip_body_id,
            controlled_joint_ids=controlled_joint_ids,
        )
        + _body_jacobian(
            scene=scene,
            body_id=right_tip_body_id,
            controlled_joint_ids=controlled_joint_ids,
        )
    ) / 2.0
    return [
        [float(value) for value in row]
        for row in jacobian.detach().cpu().tolist()
    ]


class _CriticalContactReporter:
    """Accumulate contact impulses for explicit nested DOFBOT actor paths."""

    def __init__(self, physics_dt: float) -> None:
        self._physics_dt = physics_dt
        self._critical_paths = frozenset(CONTACT_BODY_PATHS)
        self._maximum_force_n_since_read = 0.0
        self._subscription = (
            omni.physx.get_physx_simulation_interface()
            .subscribe_contact_report_events(self._on_contact_report)
        )

    def _on_contact_report(
        self,
        headers: Any,
        contact_data: Any,
    ) -> None:
        force_n = maximum_monitored_contact_force_n(
            headers=headers,
            contact_data=contact_data,
            critical_paths=self._critical_paths,
            physics_dt=self._physics_dt,
            decode_path=lambda value: str(
                PhysicsSchemaTools.intToSdfPath(value)
            ),
        )
        self._maximum_force_n_since_read = max(
            self._maximum_force_n_since_read,
            force_n,
        )

    def maximum_force_n(self) -> float:
        maximum = self._maximum_force_n_since_read
        self._maximum_force_n_since_read = 0.0
        return maximum


def _issue_angles(
    *,
    yahboom_api: YahboomServoApiAdapter,
    angles_deg: tuple[float, float, float, float],
    duration_ms: int,
) -> int:
    for servo_id, angle in enumerate(angles_deg, start=1):
        if not float(angle).is_integer():
            raise PregraspPoseError("Yahboom pose command must use integer degrees")
        yahboom_api.Arm_serial_servo_write(
            servo_id,
            int(angle),
            duration_ms,
        )
    return len(angles_deg)


def _observation(
    *,
    scene: InteractiveScene,
    arm: DofbotArm,
    pose: PregraspPoseConfig,
    scene_config: DofbotReachingConfig,
    body_ids: dict[str, int],
    contact_reporter: _CriticalContactReporter,
    velocities_deg_s: tuple[float, float, float, float],
    accelerations_deg_s2: tuple[float, float, float, float],
    step_index: int,
) -> dict[str, Any]:
    positions = _body_positions(scene, body_ids)
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
    if tuple(pose.collision.critical_body_names) != CONTACT_BODY_NAMES:
        raise PregraspPoseError(
            "pose contract critical bodies do not match the PhysX contact views"
        )
    contact_force = contact_reporter.maximum_force_n()
    angles = _observed_angles_deg(arm)
    evaluation = evaluate_pregrasp_observation(
        config=pose,
        frame=frame,
        body_positions_world_m=positions,
        table_center_world_m=scene_config.table.center_world_m,
        table_size_m=scene_config.table.size_m,
        target_center_world_m=scene_config.target_cube.center_world_m,
        target_size_m=scene_config.target_cube.size_m,
        target_is_static=scene_config.target_cube.static,
        angles_deg=angles,
        velocities_deg_s=velocities_deg_s,
        accelerations_deg_s2=accelerations_deg_s2,
        maximum_contact_force_n=contact_force,
    )
    return {
        "step_index": step_index,
        "grasp_frame": frame.to_dict(),
        "angles_deg": list(angles),
        "command_velocities_deg_s": list(velocities_deg_s),
        "command_accelerations_deg_s2": list(accelerations_deg_s2),
        "maximum_critical_contact_force_n": contact_force,
        "contact_report_body_names": list(CONTACT_BODY_NAMES),
        "body_positions_world_m": {
            name: list(position) for name, position in positions.items()
        },
        "evaluation": evaluation,
    }


def _precommand_safety_checks(observation: dict[str, Any]) -> None:
    checks = observation["evaluation"]["checks"]
    safety_keys = (
        "joint_angles_remain_within_safe_limits",
        "joint_velocity_limit_respected",
        "joint_acceleration_limit_respected",
        "critical_body_centers_clear_table_proxy",
        "nonfinger_body_centers_clear_target_proxy",
        "terminal_finger_centers_remain_precontact",
        "contact_reporter_force_remains_below_threshold",
        "target_remains_static",
        "contact_remains_unauthorized",
    )
    failed = [name for name in safety_keys if checks[name] is not True]
    if failed:
        raise PregraspPoseError(
            "pre-grasp safety gate failed before command: " + ", ".join(failed)
        )


def _run_pose_controller(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    arm: DofbotArm,
    yahboom_api: YahboomServoApiAdapter,
    backend: _IsaacJointPositionBackend,
    pose: PregraspPoseConfig,
    scene_config: DofbotReachingConfig,
    body_ids: dict[str, int],
    contact_reporter: _CriticalContactReporter,
    controlled_joint_ids: list[int],
    render: bool,
) -> tuple[list[dict[str, Any]], int, list[list[float]]] | None:
    dt = pose.solver.control_dt_s
    physics_steps = round(dt / sim.get_physics_dt())
    if physics_steps <= 0 or not math.isclose(
        physics_steps * sim.get_physics_dt(),
        dt,
        abs_tol=sim.get_physics_dt() / 2.0,
    ):
        raise PregraspPoseError(
            "physics timestep cannot represent the pose-control interval"
        )
    zero = (0.0, 0.0, 0.0, 0.0)
    observations = [
        _observation(
            scene=scene,
            arm=arm,
            pose=pose,
            scene_config=scene_config,
            body_ids=body_ids,
            contact_reporter=contact_reporter,
            velocities_deg_s=zero,
            accelerations_deg_s2=zero,
            step_index=0,
        )
    ]
    initial = observations[0]
    print(
        "[PREGRASP] "
        "step=0 "
        f"angles_deg={initial['angles_deg']} "
        f"position_error_m={initial['evaluation']['position_error_m']:.5f} "
        f"contact_force_n={initial['maximum_critical_contact_force_n']:.4f}",
        flush=True,
    )
    previous_velocity = zero
    previous_command_angles = tuple(float(value) for value in NEUTRAL_ANGLES_DEG)
    api_calls = 0
    api_command_angles_deg: list[list[float]] = []
    for step_index in range(1, pose.solver.maximum_steps + 1):
        prior = observations[-1]
        command_trajectory_settled = validated_joint_candidate_command_reached(
            command_angles_deg=previous_command_angles,
            command_velocities_deg_s=previous_velocity,
            solver=pose.solver,
        )
        if prior["evaluation"]["passed"] and command_trajectory_settled:
            break
        _precommand_safety_checks(prior)
        current_angles = _observed_angles_deg(arm)
        frame_value = prior["grasp_frame"]
        frame = derive_grasp_frame(
            wrist_position_world_m=prior["body_positions_world_m"][
                pose.grasp_frame.wrist_body_name
            ],
            left_tip_position_world_m=prior["body_positions_world_m"][
                pose.grasp_frame.left_tip_body_name
            ],
            right_tip_position_world_m=prior["body_positions_world_m"][
                pose.grasp_frame.right_tip_body_name
            ],
            config=pose.grasp_frame,
        )
        if frame.to_dict() != frame_value:
            raise PregraspPoseError("recorded grasp frame is internally inconsistent")
        command = next_pregrasp_command(
            frame=frame,
            pose_jacobian=_terminal_midpoint_jacobian(
                scene=scene,
                left_tip_body_id=body_ids[
                    pose.grasp_frame.left_tip_body_name
                ],
                right_tip_body_id=body_ids[
                    pose.grasp_frame.right_tip_body_name
                ],
                controlled_joint_ids=controlled_joint_ids,
            ),
            observed_angles_deg=current_angles,
            previous_command_angles_deg=previous_command_angles,
            previous_command_velocities_deg_s=previous_velocity,
            solver=pose.solver,
            target=pose.target_pose,
        )
        accelerations = tuple(
            (velocity - previous) / dt
            for velocity, previous in zip(
                command.velocities_deg_s,
                previous_velocity,
                strict=True,
            )
        )
        if (
            pose.solver.control_mode == POSE_IK_CONTROL_MODE
            and command.angles_deg
            == tuple(round(value) for value in current_angles)
        ):
            raise PregraspPoseError(
                "pose controller stalled before satisfying the pose gate"
            )
        api_calls += _issue_angles(
            yahboom_api=yahboom_api,
            angles_deg=command.angles_deg,
            duration_ms=round(dt * 1000),
        )
        api_command_angles_deg.append(list(command.angles_deg))
        if not _step_simulation(
            scene=scene,
            sim=sim,
            backend=backend,
            physics_steps=physics_steps,
            render=render,
        ):
            return None
        observation = _observation(
            scene=scene,
            arm=arm,
            pose=pose,
            scene_config=scene_config,
            body_ids=body_ids,
            contact_reporter=contact_reporter,
            velocities_deg_s=command.velocities_deg_s,
            accelerations_deg_s2=accelerations,  # type: ignore[arg-type]
            step_index=step_index,
        )
        observations.append(observation)
        previous_command_angles = command.angles_deg
        previous_velocity = command.velocities_deg_s
        print(
            "[PREGRASP] "
            f"step={step_index} "
            f"command_angles_deg={command.angles_deg} "
            f"command_velocities_deg_s={command.velocities_deg_s} "
            f"angles_deg={observation['angles_deg']} "
            f"position_error_m={observation['evaluation']['position_error_m']:.5f} "
            f"approach_error_deg={observation['evaluation']['approach_error_deg']:.2f} "
            f"closing_error_deg={observation['evaluation']['closing_error_deg']:.2f} "
            f"contact_force_n={observation['maximum_critical_contact_force_n']:.4f}",
            flush=True,
        )
    return observations, api_calls, api_command_angles_deg


def _reset_to_neutral(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    arm: DofbotArm,
    yahboom_api: YahboomServoApiAdapter,
    backend: _IsaacJointPositionBackend,
    scene_config: DofbotReachingConfig,
    render: bool,
) -> tuple[float, int] | None:
    final_step = scene_config.scripted_baseline.steps[-1]
    api_calls = _issue_angles(
        yahboom_api=yahboom_api,
        angles_deg=tuple(float(value) for value in NEUTRAL_ANGLES_DEG),
        duration_ms=final_step.duration_ms,
    )
    if not _step_simulation(
        scene=scene,
        sim=sim,
        backend=backend,
        physics_steps=max(
            1,
            round(
                ((final_step.duration_ms + final_step.hold_ms) / 1000.0)
                / sim.get_physics_dt()
            ),
        ),
        render=render,
    ):
        return None
    error = max(
        abs(angle - neutral)
        for angle, neutral in zip(
            _observed_angles_deg(arm),
            NEUTRAL_ANGLES_DEG,
            strict=True,
        )
    )
    return error, api_calls


def _write_result(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    recorded_contract = _load_json_object(args_cli.asset_contract)
    validate_recorded_asset_contract(recorded_contract)
    pose = preflight_pose
    scene_config = preflight_scene
    sim = sim_utils.SimulationContext(
        sim_utils.SimulationCfg(device=args_cli.device)
    )
    sim.set_camera_view(
        eye=[0.55, -0.55, 0.38],
        target=[0.0, 0.25, 0.17],
    )
    scene = InteractiveScene(
        DofbotPregraspSceneCfg(num_envs=1, env_spacing=2.0)
    )
    _spawn_scene_boxes(scene_config)
    stage = sim_utils.get_current_stage()
    table_prim = stage.GetPrimAtPath(scene_config.table.prim_path)
    target_prim = stage.GetPrimAtPath(scene_config.target_cube.prim_path)
    table_present = bool(table_prim and table_prim.IsValid())
    target_present = bool(target_prim and target_prim.IsValid())
    target_is_static = target_present and not target_prim.HasAPI(
        UsdPhysics.RigidBodyAPI
    )
    sim.reset()
    scene.update(sim.get_physics_dt())
    contact_reporter = _CriticalContactReporter(sim.get_physics_dt())
    assert_compatible_asset_contracts(
        recorded_contract,
        _live_asset_contract(scene),
    )
    required_bodies = {
        pose.grasp_frame.wrist_body_name,
        pose.grasp_frame.left_tip_body_name,
        pose.grasp_frame.right_tip_body_name,
        *pose.collision.critical_body_names,
    }
    body_ids = _body_ids(scene, required_bodies)
    controlled_joint_ids = _controlled_joint_ids(scene)
    backend = _IsaacJointPositionBackend(
        scene=scene,
        controlled_joint_ids=controlled_joint_ids,
        device=args_cli.device,
    )
    arm = DofbotArm(backend)
    yahboom_api = YahboomServoApiAdapter(arm)
    render = args_cli.cycles < 0

    neutral_step = scene_config.scripted_baseline.steps[-1]
    initialization_api_calls = _issue_angles(
        yahboom_api=yahboom_api,
        angles_deg=tuple(float(value) for value in NEUTRAL_ANGLES_DEG),
        duration_ms=neutral_step.duration_ms,
    )
    if not _hold(
        seconds=(neutral_step.duration_ms + neutral_step.hold_ms) / 1000.0,
        scene=scene,
        sim=sim,
        backend=backend,
        render=render,
    ):
        if args_cli.cycles > 0:
            raise PregraspPoseError(
                "simulation app stopped before initial neutral settle completed"
            )
        return

    if viewer_connection_hold_seconds > 0.0:
        print(
            "[PREGRASP] "
            f"viewer_connection_hold_seconds={viewer_connection_hold_seconds:g}",
            flush=True,
        )
        if not _hold(
            seconds=float(viewer_connection_hold_seconds),
            scene=scene,
            sim=sim,
            backend=backend,
            render=render,
        ):
            return

    cycle_index = 1
    while (args_cli.cycles < 0 and simulation_app.is_running()) or (
        args_cli.cycles > 0 and cycle_index <= args_cli.cycles
    ):
        controller_result = _run_pose_controller(
            scene=scene,
            sim=sim,
            arm=arm,
            yahboom_api=yahboom_api,
            backend=backend,
            pose=pose,
            scene_config=scene_config,
            body_ids=body_ids,
            contact_reporter=contact_reporter,
            controlled_joint_ids=controlled_joint_ids,
            render=render,
        )
        if controller_result is None:
            if args_cli.cycles > 0:
                raise PregraspPoseError(
                    "simulation app stopped before the headless pose "
                    "controller completed"
                )
            break
        observations, controller_api_calls, controller_command_angles = (
            controller_result
        )
        if render and observations[-1]["evaluation"]["passed"]:
            if not _hold(
                seconds=float(
                    pose.acceptance.viewer_success_hold_seconds
                ),
                scene=scene,
                sim=sim,
                backend=backend,
                render=render,
            ):
                break
        reset_result = _reset_to_neutral(
            scene=scene,
            sim=sim,
            arm=arm,
            yahboom_api=yahboom_api,
            backend=backend,
            scene_config=scene_config,
            render=render,
        )
        if reset_result is None:
            if args_cli.cycles > 0:
                raise PregraspPoseError(
                    "simulation app stopped before the headless neutral "
                    "reset completed"
                )
            break
        reset_error, reset_api_calls = reset_result
        initial_position_error = observations[0]["evaluation"]["position_error_m"]
        final_evaluation = observations[-1]["evaluation"]
        final_position_error = final_evaluation["position_error_m"]
        improvement = initial_position_error - final_position_error
        official_api_calls = (
            initialization_api_calls + controller_api_calls + reset_api_calls
        )
        expected_api_calls = 4 + (len(observations) - 1) * 4 + 4
        all_api_command_angles = [
            list(NEUTRAL_ANGLES_DEG),
            *controller_command_angles,
            list(NEUTRAL_ANGLES_DEG),
        ]
        final_controller_command = (
            tuple(controller_command_angles[-1])
            if controller_command_angles
            else tuple(float(value) for value in NEUTRAL_ANGLES_DEG)
        )
        final_controller_velocity = tuple(
            float(value)
            for value in observations[-1]["command_velocities_deg_s"]
        )
        candidate_command_reached = validated_joint_candidate_command_reached(
            command_angles_deg=final_controller_command,
            command_velocities_deg_s=final_controller_velocity,
            solver=pose.solver,
        )
        final_observed_angles = tuple(
            float(value) for value in observations[-1]["angles_deg"]
        )
        maximum_final_joint_tracking_error = maximum_joint_tracking_error_deg(
            observed_angles_deg=final_observed_angles,
            command_angles_deg=final_controller_command,
        )
        command_min = (
            pose.solver.safe_angle_min_deg
            + pose.solver.command_limit_margin_deg
        )
        command_max = (
            pose.solver.safe_angle_max_deg
            - pose.solver.command_limit_margin_deg
        )
        checks = {
            **final_evaluation["checks"],
            "physical_table_prim_present": table_present,
            "static_target_cube_prim_present": (
                target_present and target_is_static
            ),
            "pose_controller_improved_position": (
                improvement
                >= pose.acceptance.minimum_position_improvement_m
            ),
            "official_api_call_count_matches": (
                official_api_calls == expected_api_calls
            ),
            "api_commands_preserve_limit_margin": all(
                command_min <= angle <= command_max
                for command in all_api_command_angles
                for angle in command
            ),
            "validated_joint_candidate_command_reached": (
                candidate_command_reached
            ),
            "final_api_joint_tracking_within_tolerance": (
                maximum_final_joint_tracking_error
                <= pose.acceptance.maximum_final_joint_tracking_error_deg
            ),
            "returned_to_neutral": (
                reset_error
                <= pose.acceptance.maximum_neutral_reset_error_deg
            ),
        }
        machine = {
            "checks": checks,
            "machine_passed": all(checks.values()),
            "initial_position_error_m": initial_position_error,
            "final_position_error_m": final_position_error,
            "position_improvement_m": improvement,
            "final_approach_error_deg": final_evaluation[
                "approach_error_deg"
            ],
            "final_closing_error_deg": final_evaluation[
                "closing_error_deg"
            ],
            "maximum_contact_force_n": max(
                observation["maximum_critical_contact_force_n"]
                for observation in observations
            ),
            "official_api_call_count": official_api_calls,
            "expected_official_api_call_count": expected_api_calls,
            "final_observed_angles_deg": list(final_observed_angles),
            "maximum_final_joint_tracking_error_deg": (
                maximum_final_joint_tracking_error
            ),
            "maximum_allowed_final_joint_tracking_error_deg": (
                pose.acceptance.maximum_final_joint_tracking_error_deg
            ),
            "maximum_neutral_reset_error_deg": reset_error,
        }
        result = {
            "schema_version": 1,
            "experiment": "dofbot_goal5_angled_pregrasp",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": args_cli.git_commit,
            "sources": {
                "asset_contract": {
                    "path": str(args_cli.asset_contract),
                    "sha256": preflight_asset_sha256,
                },
                "scene_config": {
                    "path": str(args_cli.scene_config),
                    "sha256": preflight_scene_sha256,
                },
                "pose_config": {
                    "path": str(args_cli.pose_config),
                    "sha256": preflight_pose_sha256,
                },
            },
            "scene": {
                "robot_frame": scene_config.robot_frame.to_dict(),
                "table": scene_config.table.to_dict(),
                "target_cube": scene_config.target_cube.to_dict(),
            },
            "control": {
                "application_api": (
                    "Arm_serial_servo_write(id, angle, time)"
                ),
                "algorithm": pose.solver.control_mode,
                "jacobian": (
                    "mean_terminal_finger_body_link_jacobian_6x4"
                ),
                "controlled_joint_names": list(
                    pose.solver.controlled_joint_names
                ),
                "target_joint_candidate_angles_deg": (
                    list(pose.solver.preferred_angles_deg)
                ),
                "final_controller_api_command_angles_deg": list(
                    final_controller_command
                ),
                "validated_joint_candidate_command_reached": (
                    candidate_command_reached
                ),
                "api_command_angles_deg": all_api_command_angles,
                "closing_axis_control": (
                    pose.target_pose.closing_axis_control
                ),
                "policy_free": True,
            },
            "measurement": {
                "cycle_index": cycle_index,
                "physics_dt_s": sim.get_physics_dt(),
                "observations": observations,
            },
            "acceptance": {
                "machine": machine,
                "visual": {
                    "status": "pending_user_confirmation",
                    "lower_farther_scene_visible": None,
                    "terminal_finger_midpoint_approaches_cube_from_above": None,
                    "motion_is_smooth_and_posture_is_acceptable": None,
                    "gripper_remained_open": None,
                    "target_remained_stationary": None,
                    "no_visible_contact": None,
                },
                "goal5_complete": False,
            },
            "scope": {
                "real_hardware_commanded": False,
                "camera_used_as_controller_input": False,
                "wrist_twist_commanded": False,
                "gripper_commanded": False,
                "target_cube_moved": False,
                "contact_authorized": False,
                "policy_or_checkpoint_loaded": False,
            },
        }
        _write_result(args_cli.output, result)
        print(
            "[INFO] "
            f"cycle={cycle_index} "
            f"machine_passed={machine['machine_passed']} "
            f"output={args_cli.output}",
            flush=True,
        )
        if not machine["machine_passed"]:
            failed = [
                name for name, passed in checks.items() if passed is not True
            ]
            raise RuntimeError(
                "DOFBOT pre-grasp machine acceptance failed: "
                + ", ".join(failed)
            )
        cycle_index += 1


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        if isinstance(error, SystemExit) and error.code in (None, 0):
            raise RuntimeError(
                "Isaac requested a zero-code exit before pre-grasp completion"
            ) from error
        raise
    else:
        simulation_app.close()
