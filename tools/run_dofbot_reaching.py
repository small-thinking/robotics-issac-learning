"""Run the Goal 4 fixed-tabletop DOFBOT reaching comparison in Isaac Lab.

The experiment first executes a fixed ActionChunk baseline, then uses the live
``Wrist_Twist`` translational Jacobian for a damped-least-squares approach to a
static cube. Every arm target crosses the same documented Yahboom
``Arm_serial_servo_write`` API boundary. The gripper, camera, policies, and
physical hardware are deliberately out of scope.
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

from dofbot_motion_config import (
    CONTROL_INTERVAL_MS,
    NEUTRAL_ANGLES_DEG,
    CompiledMotionSample,
    MotionConfigError,
    compile_motion_config,
)
from dofbot_reaching import (
    DofbotReachingConfig,
    ReachingConfigError,
    evaluate_reaching_observations,
    load_reaching_config,
    next_state_controller_angles,
)

parser = argparse.ArgumentParser(description="Run the fail-closed Goal 4 fixed-tabletop reach.")
parser.add_argument(
    "--asset-contract",
    type=Path,
    default=Path("/workspace/robotics-issac-learning/artifacts/dofbot/asset_contract.json"),
)
parser.add_argument(
    "--reaching-config",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/configs/dofbot/reaching/goal4_fixed_tabletop.json"
    ),
)
parser.add_argument(
    "--output",
    type=Path,
    default=Path("/workspace/robotics-issac-learning/artifacts/dofbot/reaching_contract.json"),
)
parser.add_argument(
    "--cycles",
    type=int,
    default=1,
    help="Number of complete comparisons; use -1 for Viewer repetition.",
)
parser.add_argument(
    "--viewer-connection-hold-seconds",
    type=float,
    default=None,
    help="Neutral-pose render hold before the first Viewer cycle.",
)
parser.add_argument("--git-commit", default=None)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

if args_cli.cycles == 0 or args_cli.cycles < -1:
    raise ReachingConfigError("--cycles must be a positive integer or -1")
preflight_config, preflight_config_sha256 = load_reaching_config(args_cli.reaching_config)
viewer_connection_hold_seconds = (
    float(preflight_config.viewer_connection_hold_seconds)
    if args_cli.viewer_connection_hold_seconds is None
    else args_cli.viewer_connection_hold_seconds
)
if (
    isinstance(viewer_connection_hold_seconds, bool)
    or not isinstance(viewer_connection_hold_seconds, (int, float))
    or not math.isfinite(float(viewer_connection_hold_seconds))
    or viewer_connection_hold_seconds < 0.0
    or viewer_connection_hold_seconds > 60.0
):
    raise ReachingConfigError("--viewer-connection-hold-seconds must be finite and in [0, 60]")
preflight_samples = compile_motion_config(preflight_config.scripted_baseline)

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch
from pxr import UsdPhysics

import isaaclab.sim as sim_utils
from isaaclab.scene import InteractiveScene

from dofbot_control_api import (
    CONTROLLED_JOINT_NAMES,
    DofbotArm,
    JointPositionCommand,
    YahboomServoApiAdapter,
)
from dofbot_motion_plan import (
    assert_compatible_asset_contracts,
    validate_recorded_asset_contract,
)
from dofbot_scene_cfg import DofbotAssetSceneCfg


def _first_env_row(tensor: torch.Tensor) -> list[Any]:
    return tensor[0].detach().cpu().tolist()


def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ReachingConfigError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _live_asset_contract(scene: InteractiveScene) -> dict[str, Any]:
    robot = scene["dofbot"]
    joint_pos_limits = getattr(robot.data, "joint_pos_limits", None)
    if joint_pos_limits is None:
        joint_pos_limits = robot.data.soft_joint_pos_limits
    return {
        "articulation": {
            "joint_names": list(robot.joint_names),
            "default_joint_positions_rad": _first_env_row(robot.data.default_joint_pos),
            "joint_position_limits_rad": _first_env_row(joint_pos_limits),
        }
    }


def _controlled_joint_ids(scene: InteractiveScene) -> list[int]:
    robot = scene["dofbot"]
    name_to_index = {name: index for index, name in enumerate(robot.joint_names)}
    missing = [name for name in CONTROLLED_JOINT_NAMES if name not in name_to_index]
    if missing:
        raise ReachingConfigError(f"live articulation is missing joints: {missing}")
    return [name_to_index[name] for name in CONTROLLED_JOINT_NAMES]


def _body_id(scene: InteractiveScene, body_name: str) -> int:
    body_names = list(scene["dofbot"].body_names)
    if body_name not in body_names:
        raise ReachingConfigError(f"live articulation is missing body: {body_name}")
    return body_names.index(body_name)


class _IsaacJointPositionBackend:
    """Adapt normalized four-joint commands to one smooth Isaac trajectory."""

    def __init__(
        self,
        *,
        scene: InteractiveScene,
        controlled_joint_ids: list[int],
        device: str,
    ) -> None:
        self._robot = scene["dofbot"]
        self._controlled_joint_ids = controlled_joint_ids
        self._device = device
        self._pending_goal: tuple[float, ...] | None = None
        self._pending_duration_s: float | None = None
        self._trajectory_start: tuple[float, ...] | None = None
        self._trajectory_goal: tuple[float, ...] | None = None
        self._trajectory_duration_s = 0.0
        self._trajectory_elapsed_s = 0.0

    def command_joint_positions(self, command: JointPositionCommand) -> None:
        self._pending_goal = tuple(command.positions_rad)
        self._pending_duration_s = command.duration_ms / 1000.0

    def advance(self, physics_dt: float) -> None:
        if self._pending_goal is not None:
            current = (
                self._robot.data.joint_pos[0, self._controlled_joint_ids].detach().cpu().tolist()
            )
            self._trajectory_start = tuple(float(value) for value in current)
            self._trajectory_goal = self._pending_goal
            self._trajectory_duration_s = self._pending_duration_s or physics_dt
            self._trajectory_elapsed_s = 0.0
            self._pending_goal = None
            self._pending_duration_s = None

        if self._trajectory_start is None or self._trajectory_goal is None:
            return
        self._trajectory_elapsed_s = min(
            self._trajectory_elapsed_s + physics_dt,
            self._trajectory_duration_s,
        )
        progress = self._trajectory_elapsed_s / self._trajectory_duration_s
        smooth_progress = progress * progress * (3.0 - 2.0 * progress)
        target = [
            start + (goal - start) * smooth_progress
            for start, goal in zip(
                self._trajectory_start,
                self._trajectory_goal,
                strict=True,
            )
        ]
        self._robot.set_joint_position_target(
            torch.tensor(
                [target],
                device=self._device,
                dtype=torch.float32,
            ),
            joint_ids=self._controlled_joint_ids,
        )

    def read_joint_positions(self) -> dict[str, float]:
        values = self._robot.data.joint_pos[0, self._controlled_joint_ids].detach().cpu().tolist()
        return dict(zip(CONTROLLED_JOINT_NAMES, values, strict=True))


def _spawn_physical_scene(config: DofbotReachingConfig) -> None:
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


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _step_simulation(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    backend: _IsaacJointPositionBackend,
    physics_steps: int,
    render: bool,
) -> bool:
    for _ in range(physics_steps):
        if render and not simulation_app.is_running():
            return False
        try:
            backend.advance(sim.get_physics_dt())
            scene.write_data_to_sim()
            sim.step(render=render)
        except SystemExit as error:
            raise RuntimeError("Isaac requested process exit during reaching") from error
        scene.update(sim.get_physics_dt())
    return True


def _observed_angles_deg(arm: DofbotArm) -> list[float]:
    positions = arm.read_joint_positions()
    return [90.0 + math.degrees(positions[name]) for name in CONTROLLED_JOINT_NAMES]


def _wrist_position(
    scene: InteractiveScene,
    wrist_body_id: int,
) -> tuple[float, float, float]:
    values = scene["dofbot"].data.body_pos_w[0, wrist_body_id].detach().cpu().tolist()
    return tuple(float(value) for value in values)


def _observation(
    *,
    scene: InteractiveScene,
    arm: DofbotArm,
    config: DofbotReachingConfig,
    wrist_body_id: int,
    step_index: int,
) -> dict[str, Any]:
    wrist = _wrist_position(scene, wrist_body_id)
    target = config.approach_target_world_m
    return {
        "step_index": step_index,
        "wrist_position_world_m": list(wrist),
        "target_position_world_m": list(target),
        "distance_m": math.dist(wrist, target),
        "angles_deg": _observed_angles_deg(arm),
        "wrist_table_clearance_m": wrist[2] - config.table.top_z_m,
    }


def _issue_sample(
    *,
    yahboom_api: YahboomServoApiAdapter,
    sample: CompiledMotionSample,
) -> int:
    writes = sample.api_writes()
    for write in writes:
        yahboom_api.Arm_serial_servo_write(
            write.servo_id,
            write.angle_deg,
            write.duration_ms,
        )
    return len(writes)


def _run_scripted_baseline(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    arm: DofbotArm,
    yahboom_api: YahboomServoApiAdapter,
    backend: _IsaacJointPositionBackend,
    samples: tuple[CompiledMotionSample, ...],
    config: DofbotReachingConfig,
    wrist_body_id: int,
    render: bool,
) -> tuple[list[dict[str, Any]], int] | None:
    physics_dt = sim.get_physics_dt()
    sample_duration_s = CONTROL_INTERVAL_MS / 1000.0
    physics_steps_per_sample = round(sample_duration_s / physics_dt)
    if physics_steps_per_sample <= 0 or not math.isclose(
        physics_steps_per_sample * physics_dt,
        sample_duration_s,
        abs_tol=physics_dt / 2.0,
    ):
        raise ReachingConfigError("physics timestep cannot represent the scripted 10 Hz interval")
    observations: list[dict[str, Any]] = []
    api_calls = 0
    current_step_name: str | None = None
    for index, sample in enumerate(samples):
        if sample.step_name != current_step_name:
            current_step_name = sample.step_name
            print(
                f"[REACH] scripted step={sample.step_name}",
                flush=True,
            )
        api_calls += _issue_sample(
            yahboom_api=yahboom_api,
            sample=sample,
        )
        if not _step_simulation(
            scene=scene,
            sim=sim,
            backend=backend,
            physics_steps=physics_steps_per_sample,
            render=render,
        ):
            return None
        observations.append(
            _observation(
                scene=scene,
                arm=arm,
                config=config,
                wrist_body_id=wrist_body_id,
                step_index=index,
            )
        )
    return observations, api_calls


def _translation_jacobian(
    *,
    scene: InteractiveScene,
    wrist_body_id: int,
    controlled_joint_ids: list[int],
) -> list[list[float]]:
    robot = scene["dofbot"]
    if robot.is_fixed_base:
        jacobian_body_id = wrist_body_id - 1
    else:
        jacobian_body_id = wrist_body_id
    if jacobian_body_id < 0:
        raise ReachingConfigError("end-effector body cannot be the fixed articulation root")
    jacobian = robot.data.body_link_jacobian_w.torch[
        0,
        jacobian_body_id,
        0:3,
        controlled_joint_ids,
    ]
    return [[float(value) for value in row] for row in jacobian.detach().cpu().tolist()]


def _issue_angles(
    *,
    yahboom_api: YahboomServoApiAdapter,
    angles_deg: tuple[int, int, int, int],
    duration_ms: int,
) -> int:
    for servo_id, angle_deg in enumerate(angles_deg, start=1):
        yahboom_api.Arm_serial_servo_write(
            servo_id,
            angle_deg,
            duration_ms,
        )
    return len(angles_deg)


def _run_state_controller(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    arm: DofbotArm,
    yahboom_api: YahboomServoApiAdapter,
    backend: _IsaacJointPositionBackend,
    config: DofbotReachingConfig,
    wrist_body_id: int,
    controlled_joint_ids: list[int],
    render: bool,
) -> tuple[list[dict[str, Any]], int] | None:
    controller = config.state_controller
    physics_dt = sim.get_physics_dt()
    physics_steps = round((controller.command_duration_ms / 1000.0) / physics_dt)
    if physics_steps <= 0 or not math.isclose(
        physics_steps * physics_dt,
        controller.command_duration_ms / 1000.0,
        abs_tol=physics_dt / 2.0,
    ):
        raise ReachingConfigError("physics timestep cannot represent the state-control interval")

    observations = [
        _observation(
            scene=scene,
            arm=arm,
            config=config,
            wrist_body_id=wrist_body_id,
            step_index=0,
        )
    ]
    api_calls = 0
    for step_index in range(1, controller.maximum_steps + 1):
        prior = observations[-1]
        if prior["distance_m"] <= controller.success_distance_m:
            break
        wrist = tuple(prior["wrist_position_world_m"])
        error = tuple(
            target - actual
            for target, actual in zip(
                config.approach_target_world_m,
                wrist,
                strict=True,
            )
        )
        current_angles = tuple(prior["angles_deg"])
        next_angles = next_state_controller_angles(
            current_angles_deg=current_angles,
            translation_jacobian=_translation_jacobian(
                scene=scene,
                wrist_body_id=wrist_body_id,
                controlled_joint_ids=controlled_joint_ids,
            ),
            position_error_m=error,
            controller=controller,
        )
        rounded_current = tuple(int(round(value)) for value in current_angles)
        if next_angles == rounded_current:
            raise ReachingConfigError("state controller stalled before reaching the waypoint")
        api_calls += _issue_angles(
            yahboom_api=yahboom_api,
            angles_deg=next_angles,
            duration_ms=controller.command_duration_ms,
        )
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
            config=config,
            wrist_body_id=wrist_body_id,
            step_index=step_index,
        )
        observations.append(observation)
        print(
            f"[REACH] state step={step_index} distance_m={observation['distance_m']:.5f}",
            flush=True,
        )
    return observations, api_calls


def _reset_to_neutral(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    arm: DofbotArm,
    yahboom_api: YahboomServoApiAdapter,
    backend: _IsaacJointPositionBackend,
    duration_ms: int,
    render: bool,
) -> tuple[float, int] | None:
    api_calls = _issue_angles(
        yahboom_api=yahboom_api,
        angles_deg=NEUTRAL_ANGLES_DEG,
        duration_ms=duration_ms,
    )
    if not _step_simulation(
        scene=scene,
        sim=sim,
        backend=backend,
        physics_steps=max(
            1,
            round((duration_ms / 1000.0) / sim.get_physics_dt()),
        ),
        render=render,
    ):
        return None
    maximum_error = max(
        abs(angle - neutral)
        for angle, neutral in zip(
            _observed_angles_deg(arm),
            NEUTRAL_ANGLES_DEG,
            strict=True,
        )
    )
    return maximum_error, api_calls


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


def main() -> None:
    recorded_contract, asset_contract_sha256 = _load_json_object(args_cli.asset_contract)
    validate_recorded_asset_contract(recorded_contract)
    config = preflight_config
    samples = preflight_samples

    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(device=args_cli.device))
    sim.set_camera_view(
        eye=[0.55, 0.55, 0.45],
        target=[0.0, -0.20, 0.20],
    )
    scene = InteractiveScene(DofbotAssetSceneCfg(num_envs=1, env_spacing=2.0))
    _spawn_physical_scene(config)
    stage = sim_utils.get_current_stage()
    table_prim = stage.GetPrimAtPath(config.table.prim_path)
    target_prim = stage.GetPrimAtPath(config.target_cube.prim_path)
    table_present = bool(table_prim and table_prim.IsValid())
    target_present = bool(target_prim and target_prim.IsValid())
    target_is_static = target_present and not target_prim.HasAPI(UsdPhysics.RigidBodyAPI)

    sim.reset()
    scene.update(sim.get_physics_dt())
    assert_compatible_asset_contracts(
        recorded_contract,
        _live_asset_contract(scene),
    )

    controlled_joint_ids = _controlled_joint_ids(scene)
    wrist_body_id = _body_id(scene, config.end_effector_body_name)
    backend = _IsaacJointPositionBackend(
        scene=scene,
        controlled_joint_ids=controlled_joint_ids,
        device=args_cli.device,
    )
    arm = DofbotArm(backend)
    yahboom_api = YahboomServoApiAdapter(arm)
    render = args_cli.cycles < 0

    if viewer_connection_hold_seconds > 0.0:
        _issue_angles(
            yahboom_api=yahboom_api,
            angles_deg=NEUTRAL_ANGLES_DEG,
            duration_ms=CONTROL_INTERVAL_MS,
        )
        print(
            f"[REACH] viewer_connection_hold_seconds={viewer_connection_hold_seconds:g}",
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
        scripted_result = _run_scripted_baseline(
            scene=scene,
            sim=sim,
            arm=arm,
            yahboom_api=yahboom_api,
            backend=backend,
            samples=samples,
            config=config,
            wrist_body_id=wrist_body_id,
            render=render,
        )
        if scripted_result is None:
            break
        scripted_observations, scripted_api_calls = scripted_result

        state_result = _run_state_controller(
            scene=scene,
            sim=sim,
            arm=arm,
            yahboom_api=yahboom_api,
            backend=backend,
            config=config,
            wrist_body_id=wrist_body_id,
            controlled_joint_ids=controlled_joint_ids,
            render=render,
        )
        if state_result is None:
            break
        state_observations, state_api_calls = state_result

        if render and not _hold(
            seconds=float(config.viewer_success_hold_seconds),
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
            duration_ms=config.scripted_baseline.steps[-1].duration_ms,
            render=render,
        )
        if reset_result is None:
            break
        maximum_reset_error, reset_api_calls = reset_result
        official_api_call_count = scripted_api_calls + state_api_calls + reset_api_calls
        evaluation = evaluate_reaching_observations(
            config,
            end_effector_body_present=True,
            table_prim_present=table_present,
            target_prim_present=target_present and target_is_static,
            scripted_observations=scripted_observations,
            state_observations=state_observations,
            official_api_call_count=official_api_call_count,
            maximum_neutral_reset_error_deg=maximum_reset_error,
        )
        result = {
            "schema_version": 1,
            "experiment": "dofbot_goal4_fixed_tabletop_reaching",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": args_cli.git_commit,
            "asset_contract": {
                "path": str(args_cli.asset_contract),
                "sha256": asset_contract_sha256,
            },
            "reaching_config": {
                "path": str(args_cli.reaching_config),
                "sha256": preflight_config_sha256,
                "value": config.to_dict(),
            },
            "scene": {
                "table": config.table.to_dict(),
                "target_cube": config.target_cube.to_dict(),
                "target_prim_has_rigid_body_api": not target_is_static,
                "approach_target_world_m": list(config.approach_target_world_m),
                "end_effector_body_name": config.end_effector_body_name,
            },
            "control": {
                "application_api": ("Arm_serial_servo_write(id, angle, time)"),
                "scripted_control_hz": (config.scripted_baseline.control_hz),
                "state_control_hz": config.state_controller.control_hz,
                "state_algorithm": ("damped_least_squares_translation_jacobian"),
                "official_api_call_count": official_api_call_count,
                "policy_free": True,
            },
            "measurement": {
                "cycle_index": cycle_index,
                "physics_dt_s": sim.get_physics_dt(),
                "scripted_observations": scripted_observations,
                "state_observations": state_observations,
            },
            "acceptance": {
                "machine": evaluation,
                "visual": {
                    "status": "pending_user_confirmation",
                    "table_and_static_cube_visible": None,
                    "scripted_and_state_approaches_visible": None,
                    "gripper_remained_open": None,
                    "target_remained_stationary": None,
                },
                "goal4_complete": False,
            },
            "scope": {
                "real_hardware_commanded": False,
                "camera_used_as_controller_input": False,
                "gripper_commanded": False,
                "target_cube_moved": False,
                "policy_or_checkpoint_loaded": False,
            },
        }
        _write_result(args_cli.output, result)
        print(
            f"[INFO] cycle={cycle_index} "
            f"machine_passed={evaluation['machine_passed']} "
            f"output={args_cli.output}",
            flush=True,
        )
        if not evaluation["machine_passed"]:
            failed = [name for name, passed in evaluation["checks"].items() if not passed]
            raise RuntimeError("DOFBOT reaching machine acceptance failed: " + ", ".join(failed))
        cycle_index += 1


if __name__ == "__main__":
    failure: BaseException | None = None
    try:
        main()
    except MotionConfigError as error:
        failure = ReachingConfigError(str(error))
    except BaseException as error:
        failure = error
    try:
        simulation_app.close()
    except SystemExit as error:
        if failure is None:
            failure = error
    if failure is not None:
        raise failure
