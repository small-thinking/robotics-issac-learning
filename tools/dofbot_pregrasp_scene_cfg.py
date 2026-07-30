"""Isaac scene config for contact-reported DOFBOT pre-grasp validation.

Import only after AppLauncher starts Kit.

Isaac Lab 3.0 resolves a contact sensor's final path component as the body
expression.  Keep direct DOFBOT links and the nested link5 bodies in separate
reporters so the backend does not reconstruct nested bodies at the robot root.
"""

from dofbot_scene_cfg import DOFBOT_CFG, DofbotAssetSceneCfg
from isaaclab.sensors import ContactSensorCfg

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
CONTACT_SENSOR_KEYS_BY_BODY = {
    **{body_name: "contact_direct_links" for body_name in DIRECT_CONTACT_BODIES},
    **{body_name: "contact_link5_bodies" for body_name in NESTED_CONTACT_BODIES},
}


def _contact_sensor(parent_path: str, body_names: tuple[str, ...]) -> ContactSensorCfg:
    body_expression = "|".join(body_names)
    return ContactSensorCfg(
        prim_path=f"{parent_path}/({body_expression})",
        update_period=0.0,
        history_length=1,
        debug_vis=False,
    )


class DofbotPregraspSceneCfg(DofbotAssetSceneCfg):
    """Official DOFBOT plus hierarchy-aware critical-body contact reporters."""

    dofbot = DOFBOT_CFG.replace(
        prim_path="{ENV_REGEX_NS}/Dofbot",
        spawn=DOFBOT_CFG.spawn.replace(activate_contact_sensors=True),
    )
    contact_direct_links = _contact_sensor(
        "{ENV_REGEX_NS}/Dofbot",
        DIRECT_CONTACT_BODIES,
    )
    contact_link5_bodies = _contact_sensor(
        "{ENV_REGEX_NS}/Dofbot/link5",
        NESTED_CONTACT_BODIES,
    )
