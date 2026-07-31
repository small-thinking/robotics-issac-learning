"""Isaac/PhysX runtime for the machine-validated DOFBOT gravity feed-forward.

Import this module only after :class:`isaaclab.app.AppLauncher` starts Kit.
Both the isolated calibration runner and the pre-grasp runner use this exact
implementation so the native Warp setter boundary cannot silently diverge.
"""

from __future__ import annotations

import math
from typing import Any

import isaaclab.sim as sim_utils
import torch
import warp as wp
from dofbot_gravity_feed_forward import (
    REQUIRED_GRAVITY_RUNTIME_APIS,
    GravityFeedForwardError,
    prepare_bounded_gravity_feed_forward,
)
from pxr import UsdPhysics

CONTROLLED_CHILD_BODY_NAMES = ("link1", "link2", "link3", "link4")
CONTROLLED_JOINT_PRIM_PATHS = {
    "joint1": "/World/envs/env_0/Dofbot/base_link/joint1",
    "joint2": "/World/envs/env_0/Dofbot/link1/joint2",
    "joint3": "/World/envs/env_0/Dofbot/link2/joint3",
    "joint4": "/World/envs/env_0/Dofbot/link3/joint4",
}


def controlled_joint_drive_snapshot() -> dict[str, dict[str, Any]]:
    """Read back the composed USD drive applied to controlled joints."""
    stage = sim_utils.get_current_stage()
    snapshot: dict[str, dict[str, Any]] = {}
    for name, path in CONTROLLED_JOINT_PRIM_PATHS.items():
        prim = stage.GetPrimAtPath(path)
        joint = UsdPhysics.RevoluteJoint(prim)
        drive = UsdPhysics.DriveAPI.Get(prim, "angular")
        if not prim.IsValid() or not joint or not drive:
            raise GravityFeedForwardError(
                f"missing revolute joint or angular drive at {path}"
            )
        snapshot[name] = {
            "prim_path": path,
            "axis": str(joint.GetAxisAttr().Get()),
            "body0": [str(value) for value in joint.GetBody0Rel().GetTargets()],
            "body1": [str(value) for value in joint.GetBody1Rel().GetTargets()],
            "drive_type": str(drive.GetTypeAttr().Get()),
            "max_force": float(drive.GetMaxForceAttr().Get()),
            "stiffness": float(drive.GetStiffnessAttr().Get()),
            "damping": float(drive.GetDampingAttr().Get()),
        }
    return snapshot


def drive_snapshot_matches_runtime(
    snapshot: dict[str, dict[str, Any]],
    *,
    drive_type: str,
    stiffness: float,
    damping: float,
    effort_limit_sim: float,
) -> bool:
    """Return whether every composed drive matches the selected contract."""
    if set(snapshot) != set(CONTROLLED_JOINT_PRIM_PATHS):
        return False
    return all(
        value.get("drive_type") == drive_type
        and math.isclose(float(value.get("stiffness")), stiffness)
        and math.isclose(float(value.get("damping")), damping)
        and math.isclose(float(value.get("max_force")), effort_limit_sim)
        for value in snapshot.values()
    )


class BoundedGravityFeedForward:
    """Apply bounded generalized-gravity effort after Isaac writes PD targets."""

    def __init__(
        self,
        *,
        scene: Any,
        controlled_joint_ids: list[int],
        enabled: bool,
        maximum_effort: float,
        device: str,
    ) -> None:
        self._robot = scene["dofbot"]
        self._view = getattr(self._robot, "root_view", None)
        if self._view is None:
            raise GravityFeedForwardError("root_view is unavailable")
        self._controlled_joint_ids = controlled_joint_ids
        body_name_to_index = {
            name: index for index, name in enumerate(self._robot.body_names)
        }
        missing = [
            name
            for name in CONTROLLED_CHILD_BODY_NAMES
            if name not in body_name_to_index
        ]
        if missing:
            raise GravityFeedForwardError(
                f"live articulation is missing controlled child bodies: {missing}"
            )
        self._controlled_child_body_ids = [
            body_name_to_index[name] for name in CONTROLLED_CHILD_BODY_NAMES
        ]
        self._enabled = enabled
        self._maximum_effort = maximum_effort
        self._device = device
        self._dof_count = len(self._robot.joint_names)
        self._body_count = len(self._robot.body_names)
        self.api_availability = {
            name: callable(getattr(self._view, name, None))
            for name in REQUIRED_GRAVITY_RUNTIME_APIS
        }
        if not all(self.api_availability.values()):
            missing = [
                name
                for name, available in self.api_availability.items()
                if not available
            ]
            raise GravityFeedForwardError(
                f"required gravity runtime APIs are unavailable: {missing}"
            )
        # Isaac Lab 3.0's raw PhysX view is Warp-backed even though public
        # articulation state uses Torch. The machine-validated setter therefore
        # requires native Warp data and index arrays.
        self._indices = wp.array(
            [0],
            device=self._device,
            dtype=wp.int32,
        )
        # Probe every required API and write zero before the first Yahboom API
        # pose. An incompatible runtime must fail closed before motion.
        self._gravity_matrix()
        self._incoming_joint_force_matrix()
        self._write_actuation_forces([0.0] * self._dof_count)

    def _write_actuation_forces(self, efforts: list[float]) -> None:
        if len(efforts) != self._dof_count:
            raise GravityFeedForwardError(
                "actuation force width does not match the articulation"
            )
        self._view.set_dof_actuation_forces(
            wp.array(
                [efforts],
                device=self._device,
                dtype=wp.float32,
            ),
            self._indices,
        )

    def _tensor(
        self,
        value: Any,
        *,
        label: str,
        shape: tuple[int, ...],
    ) -> torch.Tensor:
        try:
            if hasattr(value, "detach"):
                tensor = value.detach().to(
                    device=self._device,
                    dtype=torch.float32,
                )
            elif hasattr(value, "numpy"):
                tensor = torch.as_tensor(
                    value.numpy(),
                    device=self._device,
                    dtype=torch.float32,
                )
            elif hasattr(value, "tolist"):
                tensor = torch.tensor(
                    value.tolist(),
                    device=self._device,
                    dtype=torch.float32,
                )
            else:
                tensor = torch.tensor(
                    value,
                    device=self._device,
                    dtype=torch.float32,
                )
            if tensor.numel() != math.prod(shape):
                raise GravityFeedForwardError(
                    f"{label} has {tensor.numel()} values, expected "
                    f"{math.prod(shape)}"
                )
            tensor = tensor.reshape(shape)
            if not bool(torch.isfinite(tensor).all()):
                raise GravityFeedForwardError(
                    f"{label} contains non-finite values"
                )
            return tensor
        except GravityFeedForwardError:
            raise
        except Exception as error:
            raise GravityFeedForwardError(
                f"{label} cannot be converted to a finite tensor: "
                f"{type(error).__name__}: {error}"
            ) from error

    def _gravity_matrix(self) -> torch.Tensor:
        value = self._view.get_gravity_compensation_forces()
        return self._tensor(
            value,
            label="gravity compensation forces",
            shape=(1, self._dof_count),
        )

    def _incoming_joint_force_matrix(self) -> torch.Tensor:
        value = self._view.get_link_incoming_joint_force()
        return self._tensor(
            value,
            label="incoming joint forces",
            shape=(1, self._body_count, 6),
        )

    def apply_before_step(self) -> dict[str, Any]:
        gravity = self._gravity_matrix()[0].detach().cpu().tolist()
        prepared = prepare_bounded_gravity_feed_forward(
            gravity_compensation_efforts=gravity,
            dof_count=self._dof_count,
            controlled_joint_ids=self._controlled_joint_ids,
            enabled=self._enabled,
            maximum_effort=self._maximum_effort,
        )
        self._write_actuation_forces(prepared["applied_all_dof_efforts"])
        return prepared

    def read_controlled_incoming_joint_forces(self) -> list[list[float]]:
        incoming = self._incoming_joint_force_matrix()[0]
        return [
            [
                float(value)
                for value in incoming[body_id].detach().cpu().tolist()
            ]
            for body_id in self._controlled_child_body_ids
        ]
