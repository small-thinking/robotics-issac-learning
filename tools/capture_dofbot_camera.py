"""Capture and validate the official DOFBOT onboard RGB camera.

The runner is policy-free and RGB-only. It reuses the camera prim authored in
NVIDIA's Yahboom DOFBOT USD, places three static diagnostic objects on the
tabletop in the camera's planar forward direction, and writes one PNG plus a
machine-readable contract.
"""

# Isaac Lab modules must be imported after AppLauncher starts Kit.
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from isaaclab.app import AppLauncher

from dofbot_camera_config import (
    CameraConfigError,
    DofbotCameraConfig,
    evaluate_camera_observations,
    load_camera_config,
)
from dofbot_motion_config import load_motion_config

parser = argparse.ArgumentParser(
    description="Capture the official DOFBOT onboard RGB camera."
)
parser.add_argument(
    "--camera-config",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/configs/dofbot/camera/"
        "goal3_onboard_rgb.json"
    ),
)
parser.add_argument(
    "--asset-contract",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/artifacts/dofbot/asset_contract.json"
    ),
)
parser.add_argument(
    "--motion-config",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/configs/dofbot/motions/"
        "safe_api_wave.json"
    ),
    help="Previously accepted ActionChunk used only for safe camera poses.",
)
parser.add_argument(
    "--output",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/artifacts/dofbot/camera_contract.json"
    ),
)
parser.add_argument(
    "--rgb-output",
    type=Path,
    default=Path(
        "/workspace/robotics-issac-learning/artifacts/dofbot/camera_rgb.png"
    ),
)
parser.add_argument(
    "--keep-alive",
    action="store_true",
    help="Keep the secure Viewer alive after writing the first accepted contract.",
)
parser.add_argument("--git-commit", default=None)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

preflight_config, preflight_config_sha256 = load_camera_config(
    args_cli.camera_config
)
preflight_motion_config, preflight_motion_config_sha256 = load_motion_config(
    args_cli.motion_config
)

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch
from PIL import Image
from pxr import Gf, Usd, UsdGeom

import isaaclab.sim as sim_utils
from isaaclab.scene import InteractiveScene

from dofbot_camera_scene_cfg import DofbotCameraSceneCfg
from dofbot_control_api import CONTROLLED_JOINT_NAMES
from dofbot_motion_plan import validate_recorded_asset_contract


def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise CameraConfigError(f"{path} must contain a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _camera_prim(stage: Usd.Stage, path: str) -> Usd.Prim:
    prim = stage.GetPrimAtPath(path)
    if not prim.IsValid():
        raise CameraConfigError(f"camera prim does not exist: {path}")
    return prim


def _world_matrix(prim: Usd.Prim) -> Gf.Matrix4d:
    return UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
        Usd.TimeCode.Default()
    )


def _matrix_from_pose_wxyz(
    position: torch.Tensor,
    quaternion_wxyz: torch.Tensor,
) -> Gf.Matrix4d:
    position_values = position.detach().cpu().tolist()
    quaternion_values = quaternion_wxyz.detach().cpu().tolist()
    quaternion = Gf.Quatd(
        float(quaternion_values[0]),
        Gf.Vec3d(
            float(quaternion_values[1]),
            float(quaternion_values[2]),
            float(quaternion_values[3]),
        ),
    )
    matrix = Gf.Matrix4d(1.0)
    matrix.SetRotate(Gf.Rotation(quaternion))
    matrix.SetTranslateOnly(Gf.Vec3d(*map(float, position_values)))
    return matrix


def _camera_world_from_sensor(camera: Any) -> Gf.Matrix4d:
    quaternion_xyzw = _as_torch(camera.data.quat_w_opengl)[0]
    quaternion_wxyz = quaternion_xyzw[
        torch.tensor([3, 0, 1, 2], device=quaternion_xyzw.device)
    ]
    return _matrix_from_pose_wxyz(
        _as_torch(camera.data.pos_w)[0],
        quaternion_wxyz,
    )


def _camera_world_from_articulation(
    scene: InteractiveScene,
    camera_local_to_link4: Gf.Matrix4d,
) -> Gf.Matrix4d:
    robot = scene["dofbot"]
    link4_index = robot.body_names.index("link4")
    link4_world = _matrix_from_pose_wxyz(
        robot.data.body_pos_w[0, link4_index],
        robot.data.body_quat_w[0, link4_index],
    )
    return camera_local_to_link4 * link4_world


def _matrix_rows(matrix: Gf.Matrix4d) -> list[list[float]]:
    return [
        [float(matrix[row][column]) for column in range(4)]
        for row in range(4)
    ]


def _camera_optics(camera_prim: Usd.Prim) -> dict[str, Any]:
    camera = UsdGeom.Camera(camera_prim)

    def value(attribute: Any) -> Any:
        result = attribute.Get()
        if isinstance(result, Gf.Vec2f):
            return [float(result[0]), float(result[1])]
        return result

    focal_length = float(camera.GetFocalLengthAttr().Get())
    horizontal_aperture = float(camera.GetHorizontalApertureAttr().Get())
    vertical_aperture = float(camera.GetVerticalApertureAttr().Get())
    return {
        "projection": value(camera.GetProjectionAttr()),
        "focal_length": focal_length,
        "horizontal_aperture": horizontal_aperture,
        "vertical_aperture": vertical_aperture,
        "horizontal_aperture_offset": float(
            camera.GetHorizontalApertureOffsetAttr().Get()
        ),
        "vertical_aperture_offset": float(
            camera.GetVerticalApertureOffsetAttr().Get()
        ),
        "clipping_range": value(camera.GetClippingRangeAttr()),
        "focus_distance": float(camera.GetFocusDistanceAttr().Get()),
        "f_stop": float(camera.GetFStopAttr().Get()),
        "derived_horizontal_fov_deg": math.degrees(
            2.0 * math.atan(horizontal_aperture / (2.0 * focal_length))
        ),
        "derived_vertical_fov_deg": math.degrees(
            2.0 * math.atan(vertical_aperture / (2.0 * focal_length))
        ),
    }


def _planar_target_world_positions(
    config: DofbotCameraConfig,
    camera_world: Gf.Matrix4d,
) -> dict[str, tuple[float, float, float]]:
    camera_position = camera_world.ExtractTranslation()
    camera_forward = camera_world.TransformDir(Gf.Vec3d(0.0, 0.0, -1.0))
    camera_right = camera_world.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0))
    forward_xy_norm = math.hypot(float(camera_forward[0]), float(camera_forward[1]))
    right_xy_norm = math.hypot(float(camera_right[0]), float(camera_right[1]))
    if forward_xy_norm < 1e-6 or right_xy_norm < 1e-6:
        raise CameraConfigError(
            "camera forward/right vectors cannot define a tabletop placement"
        )
    forward_xy = (
        float(camera_forward[0]) / forward_xy_norm,
        float(camera_forward[1]) / forward_xy_norm,
    )
    right_xy = (
        float(camera_right[0]) / right_xy_norm,
        float(camera_right[1]) / right_xy_norm,
    )
    center_x = float(camera_position[0]) + config.forward_distance_m * forward_xy[0]
    center_y = float(camera_position[1]) + config.forward_distance_m * forward_xy[1]
    return {
        target.prim_path: (
            center_x
            + target.lateral_index * config.lateral_spacing_m * right_xy[0],
            center_y
            + target.lateral_index * config.lateral_spacing_m * right_xy[1],
            config.tabletop_z_m + target.height_m / 2.0,
        )
        for target in config.targets
    }


def _controlled_joint_ids(scene: InteractiveScene) -> list[int]:
    robot = scene["dofbot"]
    name_to_index = {name: index for index, name in enumerate(robot.joint_names)}
    missing = [name for name in CONTROLLED_JOINT_NAMES if name not in name_to_index]
    if missing:
        raise CameraConfigError(f"live articulation is missing joints: {missing}")
    return [name_to_index[name] for name in CONTROLLED_JOINT_NAMES]


def _set_arm_angles(
    scene: InteractiveScene,
    controlled_joint_ids: list[int],
    angles_deg: tuple[int, ...],
) -> None:
    positions_rad = [
        math.radians(float(angle_deg) - 90.0) for angle_deg in angles_deg
    ]
    target = torch.tensor(
        [positions_rad],
        device=scene["dofbot"].device,
        dtype=torch.float32,
    )
    scene["dofbot"].set_joint_position_target(
        target,
        joint_ids=controlled_joint_ids,
    )


def _write_arm_angles_for_camera_setup(
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    controlled_joint_ids: list[int],
    angles_deg: tuple[int, ...],
) -> None:
    robot = scene["dofbot"]
    joint_positions = robot.data.default_joint_pos.clone()
    joint_velocities = torch.zeros_like(joint_positions)
    joint_positions[0, controlled_joint_ids] = torch.tensor(
        [
            math.radians(float(angle_deg) - 90.0)
            for angle_deg in angles_deg
        ],
        device=robot.device,
        dtype=torch.float32,
    )
    robot.write_joint_state_to_sim(joint_positions, joint_velocities)
    sim.forward()
    sim.step(render=True)
    scene.update(sim.get_physics_dt())


def _step_scene(
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    steps: int,
) -> None:
    for _ in range(steps):
        if not simulation_app.is_running():
            raise CameraConfigError("simulation stopped during camera pose setup")
        try:
            scene.write_data_to_sim()
            sim.step(render=True)
        except SystemExit as error:
            raise RuntimeError(
                "Isaac requested process exit during camera pose setup"
            ) from error
        scene.update(sim.get_physics_dt())


def _ray_tabletop_target_positions(
    config: DofbotCameraConfig,
    camera_world: Gf.Matrix4d,
) -> dict[str, tuple[float, float, float]]:
    camera_position = camera_world.ExtractTranslation()
    camera_forward = camera_world.TransformDir(Gf.Vec3d(0.0, 0.0, -1.0))
    forward_z = float(camera_forward[2])
    if forward_z >= -1e-3:
        raise CameraConfigError("camera optical axis does not point toward tabletop")
    lateral_xy = (-float(camera_forward[1]), float(camera_forward[0]))
    lateral_norm = math.hypot(*lateral_xy)
    if lateral_norm < 1e-6:
        camera_right = camera_world.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0))
        lateral_xy = (float(camera_right[0]), float(camera_right[1]))
        lateral_norm = math.hypot(*lateral_xy)
    if lateral_norm < 1e-6:
        raise CameraConfigError("camera ray cannot define a tabletop lateral axis")
    lateral_xy = (
        lateral_xy[0] / lateral_norm,
        lateral_xy[1] / lateral_norm,
    )
    positions: dict[str, tuple[float, float, float]] = {}
    for target in config.targets:
        target_z = config.tabletop_z_m + target.height_m / 2.0
        ray_distance = (target_z - float(camera_position[2])) / forward_z
        if ray_distance < 0.15 or ray_distance > 0.60:
            raise CameraConfigError(
                f"{target.name} tabletop ray distance {ray_distance:.3f} m "
                "is outside [0.15, 0.60]"
            )
        positions[target.prim_path] = (
            float(camera_position[0])
            + ray_distance * float(camera_forward[0])
            + target.lateral_index * config.lateral_spacing_m * lateral_xy[0],
            float(camera_position[1])
            + ray_distance * float(camera_forward[1])
            + target.lateral_index * config.lateral_spacing_m * lateral_xy[1],
            target_z,
        )
    return positions


def _select_camera_observation_pose(
    *,
    config: DofbotCameraConfig,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    camera: Any,
    controlled_joint_ids: list[int],
) -> tuple[
    tuple[int, ...],
    dict[str, tuple[float, float, float]],
    list[dict[str, Any]],
]:
    candidate_records: list[dict[str, Any]] = []
    valid_candidates: list[
        tuple[
            float,
            tuple[int, ...],
            dict[str, tuple[float, float, float]],
        ]
    ] = []
    seen: set[tuple[int, ...]] = set()
    for step in preflight_motion_config.steps:
        angles_deg = tuple(step.angles_deg)
        if angles_deg in seen:
            continue
        seen.add(angles_deg)
        _write_arm_angles_for_camera_setup(
            scene,
            sim,
            controlled_joint_ids,
            angles_deg,
        )
        camera_world = _camera_world_from_sensor(camera)
        camera_forward = camera_world.TransformDir(Gf.Vec3d(0.0, 0.0, -1.0))
        record: dict[str, Any] = {
            "step_name": step.name,
            "angles_deg": list(angles_deg),
            "camera_forward_world": [
                float(component) for component in camera_forward
            ],
            "valid_tabletop_intersection": False,
        }
        try:
            positions = _ray_tabletop_target_positions(config, camera_world)
        except CameraConfigError as error:
            record["rejection_reason"] = str(error)
        else:
            camera_position = camera_world.ExtractTranslation()
            distances = [
                math.dist(
                    tuple(float(component) for component in camera_position),
                    position,
                )
                for position in positions.values()
            ]
            score = sum(
                abs(distance - config.forward_distance_m)
                for distance in distances
            )
            record["valid_tabletop_intersection"] = True
            record["target_ray_distances_m"] = distances
            record["score"] = score
            valid_candidates.append((score, angles_deg, positions))
        candidate_records.append(record)
    if not valid_candidates:
        print(
            "[CAMERA POSE] "
            + json.dumps(candidate_records, separators=(",", ":")),
            flush=True,
        )
        raise CameraConfigError(
            "none of the accepted ActionChunk poses points the camera at the tabletop"
        )
    _, selected_angles, _ = min(valid_candidates, key=lambda item: item[0])
    _write_arm_angles_for_camera_setup(
        scene,
        sim,
        controlled_joint_ids,
        selected_angles,
    )
    selected_positions = _ray_tabletop_target_positions(
        config,
        _camera_world_from_sensor(camera),
    )
    return selected_angles, selected_positions, candidate_records


def _move_targets(
    positions: dict[str, tuple[float, float, float]],
) -> None:
    stage = sim_utils.get_current_stage()
    for prim_path, position in positions.items():
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise CameraConfigError(f"target prim does not exist: {prim_path}")
        UsdGeom.XformCommonAPI(prim).SetTranslate(Gf.Vec3d(*position))


def _spawn_targets(
    config: DofbotCameraConfig,
    positions: dict[str, tuple[float, float, float]],
) -> None:
    for target in config.targets:
        material = sim_utils.PreviewSurfaceCfg(
            diffuse_color=target.color_rgb,
            roughness=0.8,
            metallic=0.0,
        )
        if target.shape == "cuboid":
            spawn_cfg = sim_utils.CuboidCfg(
                size=target.size_m,
                visual_material=material,
            )
        elif target.shape == "cylinder":
            spawn_cfg = sim_utils.CylinderCfg(
                radius=target.size_m[0],
                height=target.size_m[1],
                visual_material=material,
            )
        else:
            raise CameraConfigError(f"unsupported target shape: {target.shape}")
        spawn_cfg.func(
            target.prim_path,
            spawn_cfg,
            translation=positions[target.prim_path],
        )


def _as_torch(value: Any) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        return value
    tensor = getattr(value, "torch", None)
    if isinstance(tensor, torch.Tensor):
        return tensor
    raise CameraConfigError(f"camera buffer is not torch-compatible: {type(value)}")


def _tensor_optional(data: Any, name: str) -> list[Any] | None:
    value = getattr(data, name, None)
    if value is None:
        return None
    tensor = _as_torch(value)
    return tensor[0].detach().cpu().tolist()


def _frame_number(camera: Any) -> int:
    frame = _as_torch(camera.frame)
    return int(frame[0].item())


def _rgb_summary(
    rgb: torch.Tensor,
    *,
    frame: int,
    simulation_time_s: float,
    wall_elapsed_s: float,
) -> dict[str, Any]:
    rgb_cpu = rgb.detach().cpu().contiguous()
    return {
        "frame": frame,
        "simulation_time_s": simulation_time_s,
        "wall_elapsed_s": wall_elapsed_s,
        "shape": list(rgb_cpu.shape),
        "dtype": str(rgb_cpu.dtype),
        "device": str(rgb.device),
        "min": int(rgb_cpu.min().item()),
        "max": int(rgb_cpu.max().item()),
        "mean": float(rgb_cpu.float().mean().item()),
        "std": float(rgb_cpu.float().std().item()),
        "channel_mean_rgb": [
            float(value)
            for value in rgb_cpu.float().mean(dim=(0, 1, 2)).tolist()
        ],
        "raw_sha256": hashlib.sha256(rgb_cpu.numpy().tobytes()).hexdigest(),
    }


def _project_targets(
    *,
    config: DofbotCameraConfig,
    positions: dict[str, tuple[float, float, float]],
    camera_world: Gf.Matrix4d,
    intrinsic_matrix: list[list[float]],
) -> list[dict[str, Any]]:
    camera_from_world = camera_world.GetInverse()
    fx = intrinsic_matrix[0][0]
    fy = intrinsic_matrix[1][1]
    cx = intrinsic_matrix[0][2]
    cy = intrinsic_matrix[1][2]
    projections: list[dict[str, Any]] = []
    for target in config.targets:
        world_position = positions[target.prim_path]
        camera_position = camera_from_world.Transform(
            Gf.Vec3d(*world_position)
        )
        depth = -float(camera_position[2])
        pixel_x = (
            fx * float(camera_position[0]) / depth + cx
            if depth > 0.0
            else None
        )
        pixel_y = (
            -fy * float(camera_position[1]) / depth + cy
            if depth > 0.0
            else None
        )
        center_in_frame = bool(
            depth > 0.0
            and pixel_x is not None
            and pixel_y is not None
            and 0.0 <= pixel_x < config.width
            and 0.0 <= pixel_y < config.height
        )
        projections.append(
            {
                "name": target.name,
                "prim_path": target.prim_path,
                "world_center_m": list(world_position),
                "camera_center_opengl_m": [
                    float(component) for component in camera_position
                ],
                "depth_m": depth,
                "pixel_center_xy": (
                    [pixel_x, pixel_y]
                    if pixel_x is not None and pixel_y is not None
                    else None
                ),
                "center_in_frame": center_in_frame,
            }
        )
    return projections


def _set_viewport_camera(camera_path: str) -> bool:
    try:
        from omni.kit.viewport.utility import get_active_viewport

        viewport = get_active_viewport()
        if viewport is None:
            return False
        viewport.camera_path = camera_path
        return str(viewport.camera_path) == camera_path
    except Exception as error:  # pragma: no cover - version-specific Kit path
        print(f"[WARN] could not switch active Viewer camera: {error}", flush=True)
        return False


def _save_rgb_png(rgb: torch.Tensor, path: Path) -> str:
    rgb_cpu = rgb[0].detach().cpu().contiguous()
    if rgb_cpu.dtype != torch.uint8:
        raise CameraConfigError(f"expected uint8 RGB tensor, got {rgb_cpu.dtype}")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb_cpu.numpy(), mode="RGB").save(path)
    return _sha256(path)


def _run_viewer_motion(
    *,
    scene: InteractiveScene,
    sim: sim_utils.SimulationContext,
    controlled_joint_ids: list[int],
) -> None:
    while simulation_app.is_running():
        for step in preflight_motion_config.steps:
            if not simulation_app.is_running():
                return
            print(f"[CAMERA VIEW] step={step.name}", flush=True)
            _set_arm_angles(scene, controlled_joint_ids, tuple(step.angles_deg))
            step_count = round(
                ((step.duration_ms + step.hold_ms) / 1000.0)
                / sim.get_physics_dt()
            )
            for _ in range(step_count):
                if not simulation_app.is_running():
                    return
                try:
                    scene.write_data_to_sim()
                    sim.step(render=True)
                except SystemExit as error:
                    raise RuntimeError(
                        "Isaac requested process exit during camera Viewer motion"
                    ) from error
                scene.update(sim.get_physics_dt())


def main() -> None:
    config = preflight_config
    recorded_asset_contract, asset_contract_sha256 = _load_json_object(
        args_cli.asset_contract
    )
    validate_recorded_asset_contract(recorded_asset_contract)

    scene_cfg = DofbotCameraSceneCfg(num_envs=1, env_spacing=2.0)
    scene_cfg.camera.update_period = config.update_period_s
    scene_cfg.camera.height = config.height
    scene_cfg.camera.width = config.width
    scene_cfg.camera.data_types = list(config.data_types)

    sim = sim_utils.SimulationContext(
        sim_utils.SimulationCfg(device=args_cli.device)
    )
    scene = InteractiveScene(scene_cfg)
    stage = sim_utils.get_current_stage()
    camera_prim = _camera_prim(stage, config.prim_path)
    camera_world_at_spawn = _world_matrix(camera_prim)
    target_positions = _planar_target_world_positions(
        config,
        camera_world_at_spawn,
    )
    _spawn_targets(config, target_positions)

    sim.reset()
    scene.update(sim.get_physics_dt())
    camera = scene["camera"]
    controlled_joint_ids = _controlled_joint_ids(scene)
    (
        selected_observation_angles_deg,
        target_positions,
        camera_pose_candidates,
    ) = _select_camera_observation_pose(
        config=config,
        scene=scene,
        sim=sim,
        camera=camera,
        controlled_joint_ids=controlled_joint_ids,
    )
    _move_targets(target_positions)
    sensor_initialized = bool(camera.is_initialized)
    camera_prim_is_usdgeom_camera = bool(camera_prim.IsA(UsdGeom.Camera))
    viewport_camera_selected = False
    if not args_cli.headless:
        viewport_camera_selected = _set_viewport_camera(config.prim_path)

    physics_dt_s = sim.get_physics_dt()
    total_frames_needed = config.warmup_frames + config.capture_frames
    frame_samples: list[dict[str, Any]] = []
    distinct_frame_count = 0
    previous_frame: int | None = None
    latest_rgb: torch.Tensor | None = None
    simulation_time_s = 0.0
    wall_start = time.monotonic()
    maximum_steps = math.ceil(
        (total_frames_needed + 10)
        * config.update_period_s
        / physics_dt_s
    )

    for _ in range(maximum_steps):
        if not simulation_app.is_running():
            break
        scene.write_data_to_sim()
        sim.step(render=True)
        simulation_time_s += physics_dt_s
        scene.update(physics_dt_s)
        camera_output = camera.data.output or {}
        rgb_buffer = camera_output.get("rgb")
        if rgb_buffer is None:
            continue
        rgb = _as_torch(rgb_buffer)
        if rgb.numel() == 0:
            continue
        frame = _frame_number(camera)
        if frame == previous_frame:
            continue
        previous_frame = frame
        distinct_frame_count += 1
        if distinct_frame_count <= config.warmup_frames:
            continue
        latest_rgb = rgb
        frame_samples.append(
            _rgb_summary(
                rgb,
                frame=frame,
                simulation_time_s=simulation_time_s,
                wall_elapsed_s=time.monotonic() - wall_start,
            )
        )
        if len(frame_samples) >= config.capture_frames:
            break

    if latest_rgb is None:
        raise CameraConfigError("camera produced no non-empty RGB tensor")
    saved_png_sha256 = _save_rgb_png(latest_rgb, args_cli.rgb_output)
    camera_world = _camera_world_from_sensor(camera)
    intrinsic_matrix = (
        _as_torch(camera.data.intrinsic_matrices)[0].detach().cpu().tolist()
    )
    target_projections = _project_targets(
        config=config,
        positions=target_positions,
        camera_world=camera_world,
        intrinsic_matrix=intrinsic_matrix,
    )
    machine_acceptance = evaluate_camera_observations(
        config,
        camera_prim_is_usdgeom_camera=camera_prim_is_usdgeom_camera,
        sensor_initialized=sensor_initialized,
        physics_dt_s=physics_dt_s,
        frame_samples=frame_samples,
        target_projections=target_projections,
        saved_png_sha256=saved_png_sha256,
    )
    contract = {
        "schema_version": 1,
        "experiment": "02_dofbot_goal_3_onboard_rgb",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": args_cli.git_commit,
        "asset_contract": {
            "path": str(args_cli.asset_contract),
            "sha256": asset_contract_sha256,
        },
        "camera_config": {
            "path": str(args_cli.camera_config),
            "sha256": preflight_config_sha256,
            "value": config.to_dict(),
        },
        "camera_pose_motion_config": {
            "path": str(args_cli.motion_config),
            "sha256": preflight_motion_config_sha256,
            "selected_angles_deg": list(selected_observation_angles_deg),
            "candidate_measurements": camera_pose_candidates,
            "purpose": "safe deterministic camera-to-tabletop orientation",
        },
        "camera": {
            "prim_path": config.prim_path,
            "prim_type_name": camera_prim.GetTypeName(),
            "reused_authored_prim": True,
            "adapter_camera_created": False,
            "optics_authored_in_usd": _camera_optics(camera_prim),
            "world_transform_matrix": _matrix_rows(camera_world),
            "sensor_pose": {
                "position_world_m": _tensor_optional(camera.data, "pos_w"),
                "quaternion_world_ros_xyzw": _tensor_optional(
                    camera.data, "quat_w_ros"
                ),
                "quaternion_world_opengl_xyzw": _tensor_optional(
                    camera.data, "quat_w_opengl"
                ),
            },
            "intrinsic_matrix": intrinsic_matrix,
            "frame_conventions": {
                "usd_opengl": "forward -Z, up +Y",
                "ros": "forward +Z, up -Y",
            },
        },
        "observation_interface": {
            "input": {
                "scene": "static tabletop targets plus DOFBOT and renderer lighting",
                "camera_pose": "authored link4 child transform from the official USD",
                "intrinsics": "authored USD optics sampled into the Isaac camera",
                "timing": "simulation-time update_period_s",
            },
            "output": {
                "key": "rgb",
                "shape": [1, config.height, config.width, 3],
                "dtype": "torch.uint8",
                "layout": "NHWC",
                "color_order": "RGB",
                "device": frame_samples[-1]["device"],
            },
            "nominal_frequency_hz": config.nominal_frequency_hz,
            "frequency_basis": "simulation time, not a physical-camera claim",
        },
        "target_scene": {
            "static": True,
            "placement": config.placement,
            "targets": target_projections,
        },
        "measurement": {
            "physics_dt_s": physics_dt_s,
            "frame_samples": frame_samples,
            "wall_capture_elapsed_s": time.monotonic() - wall_start,
            "rgb_png": {
                "path": str(args_cli.rgb_output),
                "sha256": saved_png_sha256,
            },
        },
        "viewer": {
            "requested_onboard_camera": not args_cli.headless,
            "active_camera_selected": viewport_camera_selected,
            "visual_status": (
                "pending_user_confirmation"
                if not args_cli.headless
                else "not_requested_in_machine_run"
            ),
        },
        "acceptance": {
            "machine": machine_acceptance,
            "visual": {
                "status": (
                    "pending_user_confirmation"
                    if not args_cli.headless
                    else "not_requested_in_machine_run"
                ),
                "required_view": (
                    "onboard RGB view showing the red cube, green cylinder, "
                    "and blue cuboid"
                ),
            },
        },
        "scope": {
            "rgb_captured": True,
            "accepted_arm_pose_used_for_camera_orientation": True,
            "depth_or_segmentation_captured": False,
            "computer_vision_loaded": False,
            "policy_or_checkpoint_loaded": False,
            "real_hardware_commanded": False,
        },
    }
    _write_json(args_cli.output, contract)
    print(json.dumps(contract, indent=2), flush=True)
    print(f"[INFO] DOFBOT camera contract: {args_cli.output}", flush=True)
    print(f"[INFO] DOFBOT RGB frame: {args_cli.rgb_output}", flush=True)
    if not machine_acceptance["passed"]:
        failed = [
            name
            for name, passed in machine_acceptance["checks"].items()
            if not passed
        ]
        raise RuntimeError(
            "DOFBOT camera machine acceptance failed: " + ", ".join(failed)
        )

    if args_cli.keep_alive:
        if not viewport_camera_selected:
            viewport_camera_selected = _set_viewport_camera(config.prim_path)
        _run_viewer_motion(
            scene=scene,
            sim=sim,
            controlled_joint_ids=controlled_joint_ids,
        )


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
