"""Pure rigid-transform contract for binding the DOFBOT camera to link4.

This module deliberately has no Isaac Lab, Torch, NumPy, or USD dependency so
the camera-to-link extrinsic and its fail-closed checks can be tested locally.
All quaternions use scalar-first ``(w, x, y, z)`` order internally.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

EXPECTED_PARENT_BODY = "link4"
EXPECTED_BINDING_MODE = "explicit_link4_world_pose_sync"
EXPECTED_CAMERA_CONVENTION = "opengl"


class CameraBindingError(ValueError):
    """Raised when the camera-link rigid transform is invalid."""


def _finite_tuple(
    values: tuple[float, ...],
    *,
    length: int,
    name: str,
) -> tuple[float, ...]:
    if len(values) != length:
        raise CameraBindingError(f"{name} must contain {length} values")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise CameraBindingError(f"{name} must contain only finite values")
    return result


def _normalize_quaternion(
    quaternion_wxyz: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    values = _finite_tuple(
        quaternion_wxyz,
        length=4,
        name="rotation_wxyz",
    )
    norm = math.sqrt(sum(value * value for value in values))
    if norm < 1e-12:
        raise CameraBindingError("rotation_wxyz must have non-zero norm")
    return tuple(value / norm for value in values)  # type: ignore[return-value]


def _quat_multiply(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return (
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    )


def _quat_conjugate(
    quaternion: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    w, x, y, z = quaternion
    return (w, -x, -y, -z)


def _rotate_vector(
    quaternion: tuple[float, float, float, float],
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    vector_quaternion = (0.0, *vector)
    rotated = _quat_multiply(
        _quat_multiply(quaternion, vector_quaternion),
        _quat_conjugate(quaternion),
    )
    return (rotated[1], rotated[2], rotated[3])


@dataclass(frozen=True)
class RigidTransform:
    """Position and orientation of one frame expressed in another frame."""

    translation_m: tuple[float, float, float]
    rotation_wxyz: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        translation = _finite_tuple(
            self.translation_m,
            length=3,
            name="translation_m",
        )
        rotation = _normalize_quaternion(self.rotation_wxyz)
        object.__setattr__(self, "translation_m", translation)
        object.__setattr__(self, "rotation_wxyz", rotation)

    @classmethod
    def from_xyzw(
        cls,
        translation_m: tuple[float, float, float],
        rotation_xyzw: tuple[float, float, float, float],
    ) -> RigidTransform:
        """Build from Isaac Lab 3.0's public quaternion order."""

        x, y, z, w = rotation_xyzw
        return cls(
            translation_m=translation_m,
            rotation_wxyz=(w, x, y, z),
        )

    @property
    def rotation_xyzw(self) -> tuple[float, float, float, float]:
        """Return the orientation in Isaac Lab 3.0's public order."""

        w, x, y, z = self.rotation_wxyz
        return (x, y, z, w)

    def to_dict(self) -> dict[str, list[float]]:
        return {
            "translation_m": list(self.translation_m),
            "rotation_wxyz": list(self.rotation_wxyz),
        }


def compose_transforms(
    parent_world: RigidTransform,
    child_in_parent: RigidTransform,
) -> RigidTransform:
    """Return the child's world transform from parent-world and child-local."""

    rotated_translation = _rotate_vector(
        parent_world.rotation_wxyz,
        child_in_parent.translation_m,
    )
    translation = tuple(
        parent_value + local_value
        for parent_value, local_value in zip(
            parent_world.translation_m,
            rotated_translation,
            strict=True,
        )
    )
    rotation = _quat_multiply(
        parent_world.rotation_wxyz,
        child_in_parent.rotation_wxyz,
    )
    return RigidTransform(
        translation_m=translation,  # type: ignore[arg-type]
        rotation_wxyz=rotation,
    )


def relative_transform(
    parent_world: RigidTransform,
    child_world: RigidTransform,
) -> RigidTransform:
    """Return the fixed child transform expressed in the parent frame."""

    parent_inverse_rotation = _quat_conjugate(parent_world.rotation_wxyz)
    translation_delta = tuple(
        child_value - parent_value
        for child_value, parent_value in zip(
            child_world.translation_m,
            parent_world.translation_m,
            strict=True,
        )
    )
    translation = _rotate_vector(
        parent_inverse_rotation,
        translation_delta,  # type: ignore[arg-type]
    )
    rotation = _quat_multiply(
        parent_inverse_rotation,
        child_world.rotation_wxyz,
    )
    return RigidTransform(
        translation_m=translation,
        rotation_wxyz=rotation,
    )


def pose_error(
    expected: RigidTransform,
    actual: RigidTransform,
) -> tuple[float, float]:
    """Return translation error in meters and shortest rotation error in degrees."""

    position_error_m = math.dist(expected.translation_m, actual.translation_m)
    quaternion_dot = abs(
        sum(
            expected_value * actual_value
            for expected_value, actual_value in zip(
                expected.rotation_wxyz,
                actual.rotation_wxyz,
                strict=True,
            )
        )
    )
    quaternion_dot = min(1.0, max(-1.0, quaternion_dot))
    rotation_error_deg = math.degrees(2.0 * math.acos(quaternion_dot))
    return position_error_m, rotation_error_deg


@dataclass(frozen=True)
class CameraLinkBinding:
    """Frozen link4-to-camera extrinsic used for explicit world-pose sync."""

    camera_prim_path: str
    parent_body: str
    camera_in_link: RigidTransform

    @classmethod
    def calibrate(
        cls,
        *,
        camera_prim_path: str,
        parent_body: str,
        link_world: RigidTransform,
        camera_world: RigidTransform,
    ) -> CameraLinkBinding:
        if parent_body != EXPECTED_PARENT_BODY:
            raise CameraBindingError(
                f"parent_body must be {EXPECTED_PARENT_BODY}"
            )
        if not camera_prim_path.endswith("/Dofbot/link4/Camera"):
            raise CameraBindingError(
                "camera_prim_path must identify the official link4 Camera"
            )
        return cls(
            camera_prim_path=camera_prim_path,
            parent_body=parent_body,
            camera_in_link=relative_transform(link_world, camera_world),
        )

    def camera_world(self, link_world: RigidTransform) -> RigidTransform:
        return compose_transforms(link_world, self.camera_in_link)

    def calibration_roundtrip_error(
        self,
        *,
        link_world: RigidTransform,
        camera_world: RigidTransform,
    ) -> tuple[float, float]:
        return pose_error(camera_world, self.camera_world(link_world))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": EXPECTED_BINDING_MODE,
            "parent_body": self.parent_body,
            "camera_prim_path": self.camera_prim_path,
            "orientation_convention": EXPECTED_CAMERA_CONVENTION,
            "camera_in_link": self.camera_in_link.to_dict(),
        }
