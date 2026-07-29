from __future__ import annotations

import math
import unittest

from tools.dofbot_camera_binding import (
    CameraBindingError,
    CameraLinkBinding,
    RigidTransform,
    compose_transforms,
    pose_error,
    relative_transform,
)

CAMERA_PATH = "/World/envs/env_0/Dofbot/link4/Camera"


def _axis_angle_z(degrees: float) -> tuple[float, float, float, float]:
    half_angle = math.radians(degrees) / 2.0
    return (math.cos(half_angle), 0.0, 0.0, math.sin(half_angle))


class DofbotCameraBindingTest(unittest.TestCase):
    def test_compose_rotates_local_translation_with_parent(self) -> None:
        parent = RigidTransform((1.0, 2.0, 3.0), _axis_angle_z(90.0))
        child_local = RigidTransform((0.2, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))

        child_world = compose_transforms(parent, child_local)

        self.assertAlmostEqual(child_world.translation_m[0], 1.0, places=9)
        self.assertAlmostEqual(child_world.translation_m[1], 2.2, places=9)
        self.assertAlmostEqual(child_world.translation_m[2], 3.0, places=9)
        self.assertLess(pose_error(parent, child_world)[1], 1e-9)

    def test_relative_transform_round_trips(self) -> None:
        parent = RigidTransform((0.4, -0.3, 0.2), _axis_angle_z(35.0))
        child_local = RigidTransform((0.02, 0.04, 0.1), _axis_angle_z(-18.0))
        child_world = compose_transforms(parent, child_local)

        recovered_local = relative_transform(parent, child_world)
        recovered_world = compose_transforms(parent, recovered_local)

        position_error_m, rotation_error_deg = pose_error(child_world, recovered_world)
        self.assertLess(position_error_m, 1e-12)
        self.assertLess(rotation_error_deg, 1e-9)

    def test_binding_freezes_extrinsic_and_tracks_new_link_pose(self) -> None:
        calibration_link = RigidTransform(
            (0.1, -0.2, 0.3),
            _axis_angle_z(20.0),
        )
        expected_extrinsic = RigidTransform(
            (0.01, 0.02, 0.08),
            _axis_angle_z(-5.0),
        )
        calibration_camera = compose_transforms(
            calibration_link,
            expected_extrinsic,
        )
        binding = CameraLinkBinding.calibrate(
            camera_prim_path=CAMERA_PATH,
            parent_body="link4",
            link_world=calibration_link,
            camera_world=calibration_camera,
        )
        moved_link = RigidTransform((-0.2, 0.4, 0.5), _axis_angle_z(80.0))

        expected_camera = compose_transforms(moved_link, expected_extrinsic)
        actual_camera = binding.camera_world(moved_link)

        position_error_m, rotation_error_deg = pose_error(
            expected_camera,
            actual_camera,
        )
        self.assertLess(position_error_m, 1e-12)
        self.assertLess(rotation_error_deg, 1e-9)
        self.assertGreater(
            pose_error(calibration_camera, actual_camera)[0],
            0.1,
        )

    def test_quaternion_sign_is_same_rotation(self) -> None:
        positive = RigidTransform((0.0, 0.0, 0.0), _axis_angle_z(45.0))
        negative = RigidTransform(
            (0.0, 0.0, 0.0),
            tuple(-value for value in _axis_angle_z(45.0)),
        )
        self.assertLess(pose_error(positive, negative)[1], 1e-9)

    def test_isaac_xyzw_boundary_round_trips_without_reordering_error(
        self,
    ) -> None:
        transform = RigidTransform.from_xyzw(
            (0.1, 0.2, 0.3),
            (0.0, 0.0, math.sin(math.pi / 4.0), math.cos(math.pi / 4.0)),
        )

        self.assertEqual(
            transform.rotation_xyzw,
            (0.0, 0.0, math.sin(math.pi / 4.0), math.cos(math.pi / 4.0)),
        )
        rotated = compose_transforms(
            transform,
            RigidTransform((0.1, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)),
        )
        self.assertAlmostEqual(rotated.translation_m[0], 0.1, places=9)
        self.assertAlmostEqual(rotated.translation_m[1], 0.3, places=9)

    def test_binding_contract_names_explicit_adapter_behavior(self) -> None:
        identity = RigidTransform(
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
        )
        binding = CameraLinkBinding.calibrate(
            camera_prim_path=CAMERA_PATH,
            parent_body="link4",
            link_world=identity,
            camera_world=identity,
        )
        contract = binding.to_dict()
        self.assertEqual(contract["mode"], "explicit_link4_world_pose_sync")
        self.assertEqual(contract["parent_body"], "link4")
        self.assertEqual(contract["orientation_convention"], "opengl")
        self.assertIn("camera_in_link", contract)

    def test_invalid_quaternion_or_parent_fails_closed(self) -> None:
        with self.assertRaisesRegex(CameraBindingError, "non-zero norm"):
            RigidTransform((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))

        identity = RigidTransform(
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
        )
        with self.assertRaisesRegex(CameraBindingError, "parent_body"):
            CameraLinkBinding.calibrate(
                camera_prim_path=CAMERA_PATH,
                parent_body="wrist",
                link_world=identity,
                camera_world=identity,
            )


if __name__ == "__main__":
    unittest.main()
