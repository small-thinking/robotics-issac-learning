"""Isaac scene config for contact-reported DOFBOT pre-grasp validation.

Import only after AppLauncher starts Kit.
"""

from dofbot_scene_cfg import DOFBOT_CFG, DofbotAssetSceneCfg
from isaaclab.sensors import ContactSensorCfg

CONTACT_SENSOR_PRIM_PATHS = {
    "link2": "{ENV_REGEX_NS}/Dofbot/link2",
    "link3": "{ENV_REGEX_NS}/Dofbot/link3",
    "link4": "{ENV_REGEX_NS}/Dofbot/link4",
    "Wrist_Twist": "{ENV_REGEX_NS}/Dofbot/link5/Wrist_Twist",
    "Finger_Left_01": "{ENV_REGEX_NS}/Dofbot/link5/Finger_Left_01",
    "Finger_Right_01": "{ENV_REGEX_NS}/Dofbot/link5/Finger_Right_01",
    "Finger_Left_02": (
        "{ENV_REGEX_NS}/Dofbot/link5/Finger_Left_02/Finger_Left_02"
    ),
    "Finger_Right_02": (
        "{ENV_REGEX_NS}/Dofbot/link5/Finger_Right_02/Finger_Right_02"
    ),
    "Finger_Left_03": (
        "{ENV_REGEX_NS}/Dofbot/link5/Finger_Left_03/Finger_Left_03"
    ),
    "Finger_Right_03": (
        "{ENV_REGEX_NS}/Dofbot/link5/Finger_Right_03/Finger_Right_03"
    ),
}
CONTACT_SENSOR_KEYS_BY_BODY = {
    body_name: f"contact_{body_name.lower()}"
    for body_name in CONTACT_SENSOR_PRIM_PATHS
}


def _contact_sensor(body_name: str) -> ContactSensorCfg:
    return ContactSensorCfg(
        prim_path=CONTACT_SENSOR_PRIM_PATHS[body_name],
        update_period=0.0,
        history_length=1,
        debug_vis=False,
    )


class DofbotPregraspSceneCfg(DofbotAssetSceneCfg):
    """Official DOFBOT plus exact-path critical-body contact reporters."""

    dofbot = DOFBOT_CFG.replace(
        prim_path="{ENV_REGEX_NS}/Dofbot",
        spawn=DOFBOT_CFG.spawn.replace(activate_contact_sensors=True),
    )
    contact_link2 = _contact_sensor("link2")
    contact_link3 = _contact_sensor("link3")
    contact_link4 = _contact_sensor("link4")
    contact_wrist_twist = _contact_sensor("Wrist_Twist")
    contact_finger_left_01 = _contact_sensor("Finger_Left_01")
    contact_finger_right_01 = _contact_sensor("Finger_Right_01")
    contact_finger_left_02 = _contact_sensor("Finger_Left_02")
    contact_finger_right_02 = _contact_sensor("Finger_Right_02")
    contact_finger_left_03 = _contact_sensor("Finger_Left_03")
    contact_finger_right_03 = _contact_sensor("Finger_Right_03")
