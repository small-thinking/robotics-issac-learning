"""Execute a validated DOFBOT ActionChunk config in Isaac Lab.

Each configured pose is issued once through Yahboom's documented single-servo
API shape. The Isaac backend models the servo's duration internally with a
physics-rate smooth trajectory while the runner records observations at 10 Hz.
No policy, camera tensor, or physical hardware backend is loaded.
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
    evaluate_motion_config_observations,
    load_motion_config,
)

parser = argparse.ArgumentParser(
    description="Run a fail-closed DOFBOT ActionChunk config in Isaac Lab."
)
parser.add_argument(
    "--asset-contract",
    type=Path,
    default=Path("/workspace/robotics-issac-learning/artifacts/dofbot/asset_contract.json"),
)
parser.add_argument(
    "--motion-config",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/configs/dofbot/motions/safe_api_wave.json"
    ),
)
parser.add_argument(
    "--output",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/artifacts/dofbot/motion_config_contract.json"
    ),
)
parser.add_argument(
    "--cycles",
    type=int,
    default=1,
    help="Number of complete cycles; use -1 for Viewer repetition.",
)
parser.add_argument(
    "--viewer-connection-hold-seconds",
    type=float,
    default=0.0,
    help="Neutral-pose render hold before the first Viewer cycle.",
)
parser.add_argument("--git-commit", default=None)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

if args_cli.cycles == 0 or args_cli.cycles < -1:
    raise MotionConfigError("--cycles must be a positive integer or -1")
if (
    not math.isfinite(args_cli.viewer_connection_hold_seconds)
    or args_cli.viewer_connection_hold_seconds < 0.0
    or args_cli.viewer_connection_hold_seconds > 60.0
):
    raise MotionConfigError(
        "--viewer-connection-hold-seconds must be finite and in [0, 60]"
    )
preflight_config, preflight_config_sha256 = load_motion_config(
    args_cli.motion_config
)
preflight_samples = compile_motion_config(preflight_config)

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch

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
        raise MotionConfigError(f"{path} must contain a JSON object")
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
        raise MotionConfigError(f"live articulation is missing joints: {missing}")
    return [name_to_index[name] for name in CONTROLLED_JOINT_NAMES]


class _IsaacJointPositionBackend:
    """Adapt normalized four-joint commands to the Isaac articulation."""

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
        # The four official single-servo calls arrive without simulation steps
        # between them. Keep only the latest complete pose and begin one
        # trajectory when physics advances, mirroring a servo that executes the
        # API's duration internally.
        self._pending_goal = tuple(command.positions_rad)
        self._pending_duration_s = command.duration_ms / 1000.0

    def advance(self, physics_dt: float) -> None:
        if self._pending_goal is not None:
            current = (
                self._robot.data.joint_pos[0, self._controlled_joint_ids]
                .detach()
                .cpu()
                .tolist()
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
        target_tensor = torch.tensor(
            [target],
            device=self._device,
            dtype=torch.float32,
        )
        self._robot.set_joint_position_target(
            target_tensor,
            joint_ids=self._controlled_joint_ids,
        )

    def read_joint_positions(self) -> dict[str, float]:
        values = (
            self._robot.data.joint_pos[0, self._controlled_joint_ids]
            .detach()
            .cpu()
            .tolist()
        )
        return dict(zip(CONTROLLED_JOINT_NAMES, values, strict=True))


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
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
            raise RuntimeError(
                "Isaac requested process exit during config execution"
            ) from error
        scene.update(sim.get_physics_dt())
    return True


def _issue_sample(
    *,
    yahboom_api: YahboomServoApiAdapter,
    sample: CompiledMotionSample,
) -> None:
    for write in sample.api_writes():
        yahboom_api.Arm_serial_servo_write(
            write.servo_id,
            write.angle_deg,
            write.duration_ms,
        )


def _observed_angles_deg(arm: DofbotArm) -> list[float]:
    positions = arm.read_joint_positions()
    return [
        90.0 + math.degrees(positions[name])
        for name in CONTROLLED_JOINT_NAMES
    ]


def _run_cycle(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    arm: DofbotArm,
    yahboom_api: YahboomServoApiAdapter,
    backend: _IsaacJointPositionBackend,
    samples: tuple[CompiledMotionSample, ...],
    physics_steps_per_sample: int,
    cycle_index: int,
    render: bool,
) -> list[dict[str, Any]] | None:
    observations: list[dict[str, Any]] = []
    current_step_name: str | None = None

    for sample in samples:
        if render and not simulation_app.is_running():
            return None
        if sample.step_name != current_step_name:
            current_step_name = sample.step_name
            print(
                f"[CONFIG] cycle={cycle_index} step={current_step_name}",
                flush=True,
            )
        _issue_sample(yahboom_api=yahboom_api, sample=sample)
        if not _step_simulation(
            scene=scene,
            sim=sim,
            backend=backend,
            physics_steps=physics_steps_per_sample,
            render=render,
        ):
            return None
        observations.append(
            {
                "sequence_index": sample.sequence_index,
                "elapsed_ms": sample.elapsed_ms,
                "step_index": sample.step_index,
                "step_name": sample.step_name,
                "phase": sample.phase,
                "target_angles_deg": list(sample.angles_deg),
                "observed_angles_deg": _observed_angles_deg(arm),
            }
        )
    return observations


def main() -> None:
    viewer_hold = args_cli.viewer_connection_hold_seconds

    recorded_contract, asset_contract_sha256 = _load_json_object(
        args_cli.asset_contract
    )
    validate_recorded_asset_contract(recorded_contract)
    config = preflight_config
    config_sha256 = preflight_config_sha256
    samples = preflight_samples

    sim = sim_utils.SimulationContext(
        sim_utils.SimulationCfg(device=args_cli.device)
    )
    sim.set_camera_view(
        eye=[0.65, 0.65, 0.55],
        target=[0.0, 0.0, 0.25],
    )
    scene = InteractiveScene(DofbotAssetSceneCfg(num_envs=1, env_spacing=2.0))
    sim.reset()
    scene.update(sim.get_physics_dt())
    assert_compatible_asset_contracts(
        recorded_contract,
        _live_asset_contract(scene),
    )

    controlled_joint_ids = _controlled_joint_ids(scene)
    backend = _IsaacJointPositionBackend(
        scene=scene,
        controlled_joint_ids=controlled_joint_ids,
        device=args_cli.device,
    )
    arm = DofbotArm(backend)
    yahboom_api = YahboomServoApiAdapter(arm)

    physics_dt = sim.get_physics_dt()
    sample_duration_s = CONTROL_INTERVAL_MS / 1000.0
    physics_steps_per_sample = round(sample_duration_s / physics_dt)
    if physics_steps_per_sample <= 0 or not math.isclose(
        physics_steps_per_sample * physics_dt,
        sample_duration_s,
        abs_tol=physics_dt / 2.0,
    ):
        raise MotionConfigError(
            "physics timestep cannot represent the 10 Hz ActionChunk interval"
        )

    render = args_cli.cycles < 0
    if viewer_hold > 0.0:
        for servo_id, angle_deg in zip(
            range(1, 5),
            NEUTRAL_ANGLES_DEG,
            strict=True,
        ):
            yahboom_api.Arm_serial_servo_write(
                servo_id,
                angle_deg,
                CONTROL_INTERVAL_MS,
            )
        hold_steps = round(viewer_hold / physics_dt)
        print(
            f"[CONFIG] viewer_connection_hold_seconds={viewer_hold:g}",
            flush=True,
        )
        if not _step_simulation(
            scene=scene,
            sim=sim,
            backend=backend,
            physics_steps=hold_steps,
            render=render,
        ):
            return

    cycle_index = 1
    while (args_cli.cycles < 0 and simulation_app.is_running()) or (
        args_cli.cycles > 0 and cycle_index <= args_cli.cycles
    ):
        observations = _run_cycle(
            scene=scene,
            sim=sim,
            arm=arm,
            yahboom_api=yahboom_api,
            backend=backend,
            samples=samples,
            physics_steps_per_sample=physics_steps_per_sample,
            cycle_index=cycle_index,
            render=render,
        )
        if observations is None:
            break
        evaluation = evaluate_motion_config_observations(
            config,
            samples,
            observations,
        )
        result = {
            "schema_version": 1,
            "experiment": "dofbot_action_chunk_v1_simulation",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": args_cli.git_commit,
            "asset_contract": {
                "path": str(args_cli.asset_contract),
                "sha256": asset_contract_sha256,
            },
            "motion_config": {
                "path": str(args_cli.motion_config),
                "sha256": config_sha256,
                "value": config.to_dict(),
            },
            "control": {
                "application_api": "Arm_serial_servo_write(id, angle, time)",
                "control_hz": config.control_hz,
                "api_dispatch_mode": "once_per_servo_per_pose",
                "sample_duration_ms": CONTROL_INTERVAL_MS,
                "sample_count": len(samples),
                "official_api_call_count": sum(
                    len(sample.api_writes()) for sample in samples
                ),
                "policy_free": True,
            },
            "measurement": {
                "cycle_index": cycle_index,
                "physics_dt_s": physics_dt,
                "physics_steps_per_sample": physics_steps_per_sample,
                "samples": observations,
            },
            "acceptance": {
                "machine": evaluation,
                "visual": {
                    "status": "pending_user_confirmation",
                    "configured_step_order_visible": None,
                    "returned_to_neutral_visible": None,
                },
                "config_execution_complete": False,
            },
            "scope": {
                "real_hardware_commanded": False,
                "camera_tensor_captured": False,
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
            failed = [
                name
                for name, passed in evaluation["checks"].items()
                if not passed
            ]
            raise RuntimeError(
                "DOFBOT config machine acceptance failed: "
                + ", ".join(failed)
            )
        cycle_index += 1


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
