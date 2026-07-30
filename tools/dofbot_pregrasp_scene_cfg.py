"""Isaac scene config for contact-reported DOFBOT pre-grasp validation.

Import only after AppLauncher starts Kit.

The installed Isaac Lab 3.0 ContactSensor tensor wrapper cannot reconstruct
nested DOFBOT rigid-body paths. The runner therefore consumes PhysX contact
report events for these complete actor paths instead.
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
