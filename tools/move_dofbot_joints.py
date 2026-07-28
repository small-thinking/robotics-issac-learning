"""Run the policy-free Goal 2 DOFBOT safe-motion sequence in Isaac Lab.

The motion plan is fixed and validated by :mod:`dofbot_motion_plan`. Only
joint1 through joint4 are commanded. Machine-observable trajectory and reset
checks are written to a JSON artifact; visible axis/sign confirmation remains a
separate human gate.
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


parser = argparse.ArgumentParser(description="Run the safe DOFBOT joint-motion contract.")
parser.add_argument(
    "--asset-contract",
    type=Path,
    default=Path("/workspace/robotics-issac-learning/artifacts/dofbot/asset_contract.json"),
    help="Goal 1 asset contract to validate before commanding any target.",
)
parser.add_argument(
    "--output",
    type=Path,
    default=Path("/workspace/robotics-issac-learning/artifacts/dofbot/motion_contract.json"),
    help="Path for the machine-readable Goal 2 motion result.",
)
parser.add_argument(
    "--cycles",
    type=int,
    default=1,
    help="Number of complete motion cycles; use -1 for Viewer repetition.",
)
parser.add_argument(
    "--pre-motion-hold-seconds",
    type=float,
    default=2.0,
    help="Default-pose hold before each cycle starts.",
)
parser.add_argument(
    "--sample-hz",
    type=float,
    default=10.0,
    help="Artifact sampling frequency; physics still runs at the simulator rate.",
)
parser.add_argument(
    "--git-commit",
    default=None,
    help="Git commit synced to the remote runtime.",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch

import isaaclab.sim as sim_utils
from isaaclab.scene import InteractiveScene

from dofbot_motion_plan import (
    CONTROLLED_JOINT_NAMES,
    MotionPlan,
    MotionPlanError,
    assert_compatible_asset_contracts,
    build_motion_plan,
    evaluate_motion_observations,
    validate_recorded_asset_contract,
)
from dofbot_scene_cfg import DofbotAssetSceneCfg


def _first_env_row(tensor: torch.Tensor) -> list[Any]:
    return tensor[0].detach().cpu().tolist()


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise MotionPlanError(f"{path} must contain a JSON object")
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
        raise MotionPlanError(f"live articulation is missing controlled joints: {missing}")
    return [name_to_index[name] for name in CONTROLLED_JOINT_NAMES]


def _run_cycle(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    plan: MotionPlan,
    controlled_joint_ids: list[int],
    cycle_index: int,
    sample_hz: float,
    stop_when_app_closes: bool,
) -> tuple[list[dict[str, Any]], float] | None:
    robot = scene["dofbot"]
    physics_dt = sim.get_physics_dt()
    sample_stride = max(1, round(1.0 / (sample_hz * physics_dt)))
    step_count = math.ceil(plan.total_duration_s / physics_dt)
    observations: list[dict[str, Any]] = []
    current_segment: str | None = None

    for step in range(step_count + 1):
        # Finite machine-validation cycles do not render. On the Isaac
        # Launchable 3.0 / Isaac Sim 6 stack, processing a rendered Kit update
        # in default headless mode handles the app's quit event after the first
        # step and exits cleanly before an artifact can be written. Viewer
        # cycles render and still honor the app lifecycle.
        if stop_when_app_closes and not simulation_app.is_running():
            return None

        elapsed_s = min(step * physics_dt, plan.total_duration_s)
        sample = plan.target_at(elapsed_s)
        if sample.segment_name != current_segment:
            current_segment = sample.segment_name
            print(
                f"[MOTION] cycle={cycle_index} segment={current_segment}",
                flush=True,
            )

        target_values = [sample.target_positions_rad[name] for name in CONTROLLED_JOINT_NAMES]
        target_tensor = torch.tensor(
            [target_values],
            device=robot.data.default_joint_pos.device,
            dtype=robot.data.default_joint_pos.dtype,
        )
        if step == 0:
            print("[MOTION] checkpoint=target_tensor_ready", flush=True)
        robot.set_joint_position_target(
            target_tensor,
            joint_ids=controlled_joint_ids,
        )
        if step == 0:
            print("[MOTION] checkpoint=joint_target_set", flush=True)
        scene.write_data_to_sim()
        if step == 0:
            print("[MOTION] checkpoint=scene_data_written", flush=True)
        try:
            sim.step(render=stop_when_app_closes)
        except SystemExit as error:
            raise RuntimeError(
                "Isaac requested process exit during the DOFBOT physics step"
            ) from error
        if step == 0:
            print("[MOTION] checkpoint=physics_step_complete", flush=True)
        scene.update(physics_dt)
        if step == 0:
            print("[MOTION] checkpoint=scene_update_complete", flush=True)

        if step % sample_stride == 0 or step == step_count:
            observed_values = robot.data.joint_pos[0, controlled_joint_ids].detach().cpu().tolist()
            observations.append(
                {
                    "elapsed_s": elapsed_s,
                    "segment": sample.segment_name,
                    "target_positions_rad": dict(sample.target_positions_rad),
                    "observed_positions_rad": dict(
                        zip(
                            CONTROLLED_JOINT_NAMES,
                            observed_values,
                            strict=True,
                        )
                    ),
                }
            )

    return observations, physics_dt


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def main() -> None:
    if args_cli.cycles == 0 or args_cli.cycles < -1:
        raise MotionPlanError("--cycles must be a positive integer or -1")
    if not math.isfinite(args_cli.sample_hz) or args_cli.sample_hz <= 0.0:
        raise MotionPlanError("--sample-hz must be positive and finite")

    recorded_contract, asset_contract_sha256 = _load_json(args_cli.asset_contract)
    validate_recorded_asset_contract(recorded_contract)
    build_motion_plan(
        recorded_contract,
        pre_motion_hold_s=args_cli.pre_motion_hold_seconds,
    )

    sim_cfg = sim_utils.SimulationCfg(device=args_cli.device)
    sim = sim_utils.SimulationContext(sim_cfg)
    sim.set_camera_view(
        eye=[0.65, 0.65, 0.55],
        target=[0.0, 0.0, 0.25],
    )

    scene = InteractiveScene(DofbotAssetSceneCfg(num_envs=1, env_spacing=2.0))
    sim.reset()
    scene.update(sim.get_physics_dt())

    live_contract = _live_asset_contract(scene)
    assert_compatible_asset_contracts(recorded_contract, live_contract)
    plan = build_motion_plan(
        live_contract,
        pre_motion_hold_s=args_cli.pre_motion_hold_seconds,
    )
    controlled_joint_ids = _controlled_joint_ids(scene)

    cycle_index = 1
    while (args_cli.cycles < 0 and simulation_app.is_running()) or (
        args_cli.cycles > 0 and cycle_index <= args_cli.cycles
    ):
        cycle_result = _run_cycle(
            scene=scene,
            sim=sim,
            plan=plan,
            controlled_joint_ids=controlled_joint_ids,
            cycle_index=cycle_index,
            sample_hz=args_cli.sample_hz,
            stop_when_app_closes=args_cli.cycles < 0,
        )
        if cycle_result is None:
            break
        observations, physics_dt = cycle_result
        evaluation = evaluate_motion_observations(plan, observations)
        result = {
            "schema_version": 1,
            "experiment": "02_dofbot_goal_2_safe_joint_motion",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "learning_algorithm": None,
            "git_commit": args_cli.git_commit,
            "asset_contract": {
                "path": str(args_cli.asset_contract),
                "sha256": asset_contract_sha256,
            },
            "control": {
                "mode": "joint_position_target",
                "policy_free": True,
                "plan": plan.to_dict(),
            },
            "measurement": {
                "cycle_index": cycle_index,
                "physics_dt_s": physics_dt,
                "sample_hz": args_cli.sample_hz,
                "samples": observations,
            },
            "acceptance": {
                "machine": evaluation,
                "visual": {
                    "status": "pending_user_confirmation",
                    "required_joint_axis_sign_checks": list(CONTROLLED_JOINT_NAMES),
                    "multi_joint_wave_visible": None,
                    "returned_to_default_pose_visible": None,
                },
                "goal_2_complete": False,
            },
            "scope": {
                "real_hardware_commanded": False,
                "camera_tensor_captured": False,
                "policy_or_checkpoint_loaded": False,
            },
        }
        _write_result(args_cli.output, result)
        print(
            f"[INFO] cycle={cycle_index} machine_passed="
            f"{evaluation['machine_passed']} output={args_cli.output}",
            flush=True,
        )
        if not evaluation["machine_passed"]:
            failed = [name for name, passed in evaluation["checks"].items() if not passed]
            raise RuntimeError(f"DOFBOT motion machine acceptance failed: {', '.join(failed)}")
        cycle_index += 1


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
