"""Isaac scene config for contact-reported DOFBOT pre-grasp validation.

Import only after AppLauncher starts Kit.

The installed Isaac Lab 3.0 ContactSensor wrapper cannot reconstruct nested
DOFBOT rigid-body paths. The runner therefore creates hierarchy-aware PhysX
contact views directly from these two complete glob expressions.
"""

from dofbot_scene_cfg import DOFBOT_CFG, DofbotAssetSceneCfg

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
CONTACT_BODY_GLOBS = (
    "/World/envs/env_*/Dofbot/(link2|link3|link4)",
    (
        "/World/envs/env_*/Dofbot/link5/"
        "(Wrist_Twist|Finger_Left_01|Finger_Right_01|"
        "Finger_Left_02|Finger_Right_02|Finger_Left_03|Finger_Right_03)"
    ),
)


class DofbotPregraspSceneCfg(DofbotAssetSceneCfg):
    """Official DOFBOT with contact-report APIs activated on rigid bodies."""

    dofbot = DOFBOT_CFG.replace(
        prim_path="{ENV_REGEX_NS}/Dofbot",
        spawn=DOFBOT_CFG.spawn.replace(activate_contact_sensors=True),
    )
