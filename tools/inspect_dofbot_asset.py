"""Load NVIDIA's Yahboom DOFBOT USD and record its simulation contract.

This script is intentionally policy-free. It verifies only that the asset can
be loaded as an Isaac Lab articulation and exposes the joints, bodies, limits,
and camera prim needed by later control and perception experiments.
"""

# Isaac Lab modules must be imported after AppLauncher starts Kit.
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from isaaclab.app import AppLauncher


parser = argparse.ArgumentParser(description="Inspect the official DOFBOT USD in Isaac Lab.")
parser.add_argument(
    "--output",
    type=Path,
    default=Path("/workspace/robotics-issac-learning/artifacts/dofbot/asset_contract.json"),
    help="Path for the machine-readable asset contract.",
)
parser.add_argument(
    "--max-steps",
    type=int,
    default=120,
    help="Physics steps after inspection; use -1 to keep the Viewer open.",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch
from pxr import UsdGeom, UsdPhysics

import isaaclab.sim as sim_utils
from isaaclab.scene import InteractiveScene

from dofbot_scene_cfg import (
    ASSET_RELATIVE_PATH,
    ASSET_USD_PATH,
    EXPECTED_BODIES,
    EXPECTED_JOINTS,
    DofbotAssetSceneCfg,
)


def _first_env_row(tensor: torch.Tensor) -> list[Any]:
    return tensor[0].detach().cpu().tolist()


def _stage_paths(stage: Any, schema_type: Any, dofbot_only: bool = True) -> list[str]:
    paths: list[str] = []
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if dofbot_only and "/Dofbot" not in path:
            continue
        if prim.IsA(schema_type):
            paths.append(path)
    return sorted(paths)


def _api_paths(stage: Any, api_type: Any) -> list[str]:
    return sorted(
        str(prim.GetPath())
        for prim in stage.Traverse()
        if "/Dofbot" in str(prim.GetPath()) and prim.HasAPI(api_type)
    )


def build_contract(scene: InteractiveScene) -> dict[str, Any]:
    robot = scene["dofbot"]
    stage = sim_utils.get_current_stage()
    joint_pos_limits = getattr(robot.data, "joint_pos_limits", robot.data.soft_joint_pos_limits)

    camera_paths = _stage_paths(stage, UsdGeom.Camera)
    articulation_root_paths = _api_paths(stage, UsdPhysics.ArticulationRootAPI)
    usd_joint_paths = _stage_paths(stage, UsdPhysics.Joint)

    checks = {
        "articulation_initialized": bool(robot.is_initialized),
        "expected_11_joints": robot.num_joints == EXPECTED_JOINTS,
        "expected_12_bodies": robot.num_bodies == EXPECTED_BODIES,
        "articulation_root_present": bool(articulation_root_paths),
        "onboard_camera_present": bool(camera_paths),
    }

    return {
        "schema_version": 1,
        "experiment": "02_dofbot_goal_1_asset_load",
        "learning_algorithm": None,
        "asset": {
            "vendor": "Yahboom",
            "model": "DOFBOT",
            "source": "NVIDIA Isaac Sim asset catalog",
            "relative_usd_path": ASSET_RELATIVE_PATH,
            "resolved_usd_path": ASSET_USD_PATH,
        },
        "articulation": {
            "initialized": bool(robot.is_initialized),
            "is_fixed_base": bool(robot.is_fixed_base),
            "num_joints": robot.num_joints,
            "joint_names": list(robot.joint_names),
            "num_bodies": robot.num_bodies,
            "body_names": list(robot.body_names),
            "default_joint_positions_rad": _first_env_row(robot.data.default_joint_pos),
            "joint_position_limits_rad": _first_env_row(joint_pos_limits),
            "actuator_groups": sorted(robot.actuators),
            "articulation_root_prim_paths": articulation_root_paths,
            "usd_joint_prim_paths": usd_joint_paths,
        },
        "sensors": {
            "camera_prim_paths": camera_paths,
        },
        "acceptance": {
            "checks": checks,
            "passed": all(checks.values()),
        },
    }


def main() -> None:
    sim_cfg = sim_utils.SimulationCfg(device=args_cli.device)
    sim = sim_utils.SimulationContext(sim_cfg)
    sim.set_camera_view(eye=[1.2, 1.2, 0.8], target=[0.0, 0.0, 0.25])

    scene = InteractiveScene(DofbotAssetSceneCfg(num_envs=1, env_spacing=2.0))
    sim.reset()
    scene.update(sim.get_physics_dt())

    contract = build_contract(scene)
    args_cli.output.parent.mkdir(parents=True, exist_ok=True)
    args_cli.output.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(contract, indent=2))
    print(f"[INFO] DOFBOT asset contract: {args_cli.output}")

    if not contract["acceptance"]["passed"]:
        failed = [name for name, passed in contract["acceptance"]["checks"].items() if not passed]
        raise RuntimeError(f"DOFBOT asset acceptance failed: {', '.join(failed)}")

    step = 0
    while simulation_app.is_running() and (args_cli.max_steps < 0 or step < args_cli.max_steps):
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.get_physics_dt())
        step += 1


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
