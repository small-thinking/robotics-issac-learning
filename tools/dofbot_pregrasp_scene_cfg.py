"""Isaac scene helpers for contact-reported DOFBOT pre-grasp validation.

Import only after AppLauncher starts Kit.

The installed Isaac Lab 3.0 ContactSensor tensor wrapper cannot reconstruct
nested DOFBOT rigid-body paths. The runner therefore consumes PhysX contact
report events for these complete actor paths instead.
"""

import math
from typing import Any

import isaaclab.sim as sim_utils
from dofbot_scene_cfg import DOFBOT_CFG, DofbotAssetSceneCfg
from pxr import Usd, UsdGeom, UsdPhysics

DIRECT_CONTACT_BODIES = ("base_link", "link1", "link2", "link3", "link4")
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


def _json_compatible(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "pathString"):
        return str(value)
    if isinstance(value, (list, tuple)) or hasattr(value, "__iter__"):
        try:
            return [_json_compatible(item) for item in value]
        except TypeError:
            pass
    return str(value)


def _attribute_snapshot(prim: Any, name: str) -> dict[str, Any]:
    attribute = prim.GetAttribute(name)
    if not attribute:
        return {"present": False, "authored": False, "value": None}
    return {
        "present": True,
        "authored": bool(attribute.HasAuthoredValueOpinion()),
        "value": _json_compatible(attribute.Get()),
    }


def _relationship_targets(prim: Any, name: str) -> list[str]:
    relationship = prim.GetRelationship(name)
    if not relationship:
        return []
    return [str(path) for path in relationship.GetTargets()]


def _nearest_rigid_body_ancestor(prim: Any, root: Any) -> Any | None:
    value = prim
    while value and value.IsValid():
        if value.HasAPI(UsdPhysics.RigidBodyAPI):
            return value
        if value == root:
            break
        value = value.GetParent()
    return None


def _aligned_box(value: Any, *, frame: str) -> dict[str, list[float]]:
    aligned = value.ComputeAlignedBox()
    minimum = aligned.GetMin()
    maximum = aligned.GetMax()
    return {
        f"minimum_{frame}_m": [float(minimum[index]) for index in range(3)],
        f"maximum_{frame}_m": [float(maximum[index]) for index in range(3)],
    }


def inspect_collision_shapes(
    stage: Any,
    *,
    root_prim_path: str,
    require_rigid_body_owner: bool,
    known_body_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Inventory every collision prim and its body-relative/world bounds."""
    root = stage.GetPrimAtPath(root_prim_path)
    if not root.IsValid():
        return []
    cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=False,
    )
    result: list[dict[str, Any]] = []
    for prim in Usd.PrimRange(root):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        owner = _nearest_rigid_body_ancestor(prim, root)
        owner_path = str(owner.GetPath()) if owner is not None else None
        owner_name = str(owner.GetName()) if owner is not None else None
        if require_rigid_body_owner and owner is None:
            owner_status = "missing"
        elif (
            owner_name is not None
            and known_body_names is not None
            and owner_name not in known_body_names
        ):
            owner_status = "not_in_articulation_body_names"
        else:
            owner_status = "resolved" if owner is not None else "static"
        local_aabb = (
            _aligned_box(cache.ComputeRelativeBound(prim, owner), frame="body")
            if owner is not None
            else None
        )
        collision_enabled = UsdPhysics.CollisionAPI(
            prim
        ).GetCollisionEnabledAttr().Get()
        result.append(
            {
                "prim_path": str(prim.GetPath()),
                "prim_type": prim.GetTypeName(),
                "applied_schemas": [str(value) for value in prim.GetAppliedSchemas()],
                "owner_body_path": owner_path,
                "owner_body_name": owner_name,
                "owner_status": owner_status,
                "collision_enabled": (
                    True if collision_enabled is None else bool(collision_enabled)
                ),
                "body_local_aabb": local_aabb,
                "world_aabb": _aligned_box(
                    cache.ComputeWorldBound(prim),
                    frame="world",
                ),
                "contact_offset": _attribute_snapshot(
                    prim, "physxCollision:contactOffset"
                ),
                "rest_offset": _attribute_snapshot(
                    prim, "physxCollision:restOffset"
                ),
                "collision_approximation": _attribute_snapshot(
                    prim, "physics:approximation"
                ),
                "filtered_pairs_targets": _relationship_targets(
                    prim, "physics:filteredPairs"
                ),
            }
        )
    return result


def inspect_collision_filter_relationships(stage: Any) -> list[dict[str, Any]]:
    """Capture authored collision-group/filter relationships without inference."""
    result: list[dict[str, Any]] = []
    for prim in stage.Traverse():
        relationships = []
        for relationship in prim.GetRelationships():
            name = str(relationship.GetName())
            if "filter" in name.lower() or "collider" in name.lower():
                relationships.append(
                    {
                        "name": name,
                        "targets": [str(path) for path in relationship.GetTargets()],
                    }
                )
        if relationships:
            result.append(
                {
                    "prim_path": str(prim.GetPath()),
                    "prim_type": prim.GetTypeName(),
                    "relationships": relationships,
                }
            )
    return result
