"""Isaac scene helpers for contact-reported DOFBOT pre-grasp validation.

Import only after AppLauncher starts Kit.

The installed Isaac Lab 3.0 ContactSensor tensor wrapper cannot reconstruct
nested DOFBOT rigid-body paths. The runner therefore consumes PhysX contact
report events for these complete actor paths instead.
"""

from typing import Any

import isaaclab.sim as sim_utils
from dofbot_scene_cfg import DOFBOT_CFG, DofbotAssetSceneCfg
from pxr import Usd, UsdGeom, UsdPhysics

DIRECT_CONTACT_BODIES = ("link2", "link3", "link4")
NESTED_CONTACT_BODIES = (
    "Wrist_Twist",
    "Finger_Left_01",
    "Finger_Right_01",
    "Finger_Left_02",
    "Finger_Right_02",
    "Finger_Left_03",
    "Finger_Right_03",
)
CONTACT_BODY_NAMES = DIRECT_CONTACT_BODIES + NESTED_CONTACT_BODIES
CONTACT_BODY_PATHS = (
    *(f"/World/envs/env_0/Dofbot/{name}" for name in DIRECT_CONTACT_BODIES),
    *(
        f"/World/envs/env_0/Dofbot/link5/{name}"
        for name in NESTED_CONTACT_BODIES
    ),
)


class DofbotPregraspSceneCfg(DofbotAssetSceneCfg):
    """Official DOFBOT with contact-report APIs activated on rigid bodies."""

    dofbot = DOFBOT_CFG.replace(
        prim_path="{ENV_REGEX_NS}/Dofbot",
        spawn=DOFBOT_CFG.spawn.replace(activate_contact_sensors=True),
    )


def spawn_static_reaching_boxes(config: Any) -> None:
    """Spawn the exact static table/cube pair from a reaching config."""
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


def spawn_reaching_scene_cell(config: Any, cell: Any) -> list[dict[str, Any]]:
    """Spawn exactly the objects and collision state named by one DF-047 cell."""
    spawned: list[dict[str, Any]] = []
    for object_name in cell.objects:
        box = config.table if object_name == "table" else config.target_cube
        center = tuple(
            float(box.center_world_m[index])
            + float(cell.translation_offset_world_m[index])
            for index in range(3)
        )
        kwargs: dict[str, Any] = {
            "size": box.size_m,
            "visual_material": sim_utils.PreviewSurfaceCfg(
                diffuse_color=box.color_rgb,
                roughness=0.8,
                metallic=0.0,
            ),
        }
        if cell.collision_enabled:
            kwargs["collision_props"] = sim_utils.CollisionPropertiesCfg()
        spawn_cfg = sim_utils.CuboidCfg(**kwargs)
        spawn_cfg.func(
            box.prim_path,
            spawn_cfg,
            translation=center,
        )
        spawned.append(
            {
                "name": object_name,
                "prim_path": box.prim_path,
                "center_world_m": list(center),
                "size_m": list(box.size_m),
                "collision_enabled": bool(cell.collision_enabled),
                "rigid_body_authored": False,
            }
        )
    return spawned


def inspect_spawned_reaching_objects(
    stage: Any,
    spawned: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Read back prim, collision, rigid-body, transform, and world bounds."""
    cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )
    snapshots: list[dict[str, Any]] = []
    for planned in spawned:
        prim = stage.GetPrimAtPath(planned["prim_path"])
        if not prim.IsValid():
            snapshots.append({**planned, "prim_present": False})
            continue
        descendants = list(Usd.PrimRange(prim))
        collision_paths = [
            str(value.GetPath())
            for value in descendants
            if value.HasAPI(UsdPhysics.CollisionAPI)
        ]
        rigid_body_paths = [
            str(value.GetPath())
            for value in descendants
            if value.HasAPI(UsdPhysics.RigidBodyAPI)
        ]
        transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        translation = transform.ExtractTranslation()
        aligned = cache.ComputeWorldBound(prim).ComputeAlignedBox()
        minimum = aligned.GetMin()
        maximum = aligned.GetMax()
        snapshots.append(
            {
                **planned,
                "prim_present": True,
                "root_prim_type": prim.GetTypeName(),
                "descendant_prim_count": len(descendants),
                "descendant_prim_types": sorted(
                    {value.GetTypeName() for value in descendants}
                ),
                "collision_api_paths": collision_paths,
                "collision_enabled_readback": bool(collision_paths),
                "rigid_body_api_paths": rigid_body_paths,
                "static_readback": not rigid_body_paths,
                "translation_world_m_readback": [
                    float(translation[index]) for index in range(3)
                ],
                "axis_aligned_world_bounds_readback": {
                    "minimum_world_m": [float(minimum[index]) for index in range(3)],
                    "maximum_world_m": [float(maximum[index]) for index in range(3)],
                },
            }
        )
    return snapshots
