"""Isaac scene config for contact-reported DOFBOT pre-grasp validation.

Import only after AppLauncher starts Kit.
"""

from dofbot_scene_cfg import DOFBOT_CFG, DofbotAssetSceneCfg
from isaaclab.sensors import ContactSensorCfg


class DofbotPregraspSceneCfg(DofbotAssetSceneCfg):
    """Official DOFBOT plus contact reporting on every rigid body."""

    dofbot = DOFBOT_CFG.replace(
        prim_path="{ENV_REGEX_NS}/Dofbot",
        spawn=DOFBOT_CFG.spawn.replace(activate_contact_sensors=True),
    )
    contact_forces = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Dofbot/.*",
        update_period=0.0,
        history_length=1,
        debug_vis=False,
    )
