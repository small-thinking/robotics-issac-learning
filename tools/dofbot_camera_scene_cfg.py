"""Isaac Lab scene configuration for the Goal 3 onboard RGB sensor."""

from dofbot_scene_cfg import DofbotAssetSceneCfg
from isaaclab.sensors import CameraCfg


class DofbotCameraSceneCfg(DofbotAssetSceneCfg):
    """The official DOFBOT plus its already-authored onboard camera prim."""

    camera = CameraCfg(
        prim_path="{ENV_REGEX_NS}/Dofbot/link4/Camera",
        update_period=0.1,
        height=480,
        width=640,
        data_types=["rgb"],
        spawn=None,
        update_latest_camera_pose=True,
    )
