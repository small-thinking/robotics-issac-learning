from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.dofbot_camera_config import (
    CameraConfigError,
    evaluate_camera_observations,
    load_camera_config,
    parse_camera_config,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
CAMERA_CONFIG_PATH = PROJECT_DIR / "configs/dofbot/camera/goal3_onboard_rgb.json"


class DofbotCameraConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_config = json.loads(CAMERA_CONFIG_PATH.read_text(encoding="utf-8"))
        cls.config, cls.source_sha256 = load_camera_config(CAMERA_CONFIG_PATH)

    def _valid_samples(self) -> list[dict[str, object]]:
        return [
            {
                "frame": frame,
                "simulation_time_s": 1.0 + index * 0.1,
                "shape": [1, 480, 640, 3],
                "dtype": "torch.uint8",
                "min": 2,
                "max": 247,
                "mean": 92.5,
                "std": 31.0,
            }
            for index, frame in enumerate(range(10, 15))
        ]

    def _valid_projections(self) -> list[dict[str, object]]:
        return [
            {
                "prim_path": target.prim_path,
                "center_in_frame": True,
            }
            for target in self.config.targets
        ]

    def _valid_binding_metrics(self) -> dict[str, float]:
        return {
            "calibration_roundtrip_position_error_m": 1e-9,
            "calibration_roundtrip_orientation_error_deg": 1e-7,
            "maximum_applied_position_error_m": 0.0002,
            "maximum_applied_orientation_error_deg": 0.1,
            "maximum_dynamic_translation_m": 0.02,
            "maximum_dynamic_rotation_deg": 12.0,
        }

    def test_baseline_contract_is_rgb_640x480_at_ten_hz(self) -> None:
        self.assertEqual(
            self.config.prim_path,
            "/World/envs/env_0/Dofbot/link4/Camera",
        )
        self.assertEqual(self.config.data_types, ("rgb",))
        self.assertEqual((self.config.width, self.config.height), (640, 480))
        self.assertEqual(self.config.update_period_s, 0.1)
        self.assertEqual(self.config.nominal_frequency_hz, 10.0)
        self.assertEqual(
            self.config.pose_binding.mode,
            "explicit_link4_world_pose_sync",
        )
        self.assertEqual(self.config.pose_binding.parent_body, "link4")
        self.assertEqual(
            self.config.pose_binding.orientation_convention,
            "opengl",
        )
        self.assertEqual(len(self.config.targets), 3)
        self.assertEqual(len(self.source_sha256), 64)

    def test_target_scene_has_three_diagnostic_shapes_and_colors(self) -> None:
        self.assertEqual(
            [target.name for target in self.config.targets],
            ["red_cube", "green_cylinder", "blue_cuboid"],
        )
        self.assertEqual(
            [target.shape for target in self.config.targets],
            ["cuboid", "cylinder", "cuboid"],
        )
        self.assertEqual(
            [target.lateral_index for target in self.config.targets],
            [-1, 0, 1],
        )

    def test_parser_rejects_camera_scope_expansion(self) -> None:
        for data_types in (["rgb", "depth"], ["distance_to_camera"], []):
            broken = copy.deepcopy(self.raw_config)
            broken["camera"]["data_types"] = data_types
            with self.subTest(data_types=data_types):
                with self.assertRaisesRegex(CameraConfigError, "only the rgb"):
                    parse_camera_config(broken)

    def test_parser_rejects_wrong_camera_prim_or_unbounded_rate(self) -> None:
        broken_prim = copy.deepcopy(self.raw_config)
        broken_prim["camera"]["prim_path"] = "/World/Camera"
        with self.assertRaisesRegex(CameraConfigError, "camera.prim_path"):
            parse_camera_config(broken_prim)

        for period in (0.0, 1 / 30, 0.2, True):
            broken_rate = copy.deepcopy(self.raw_config)
            broken_rate["camera"]["update_period_s"] = period
            with self.subTest(period=period):
                with self.assertRaises(CameraConfigError):
                    parse_camera_config(broken_rate)

    def test_parser_rejects_extra_keys_and_invalid_target_geometry(self) -> None:
        extra = copy.deepcopy(self.raw_config)
        extra["camera"]["renderer"] = "magic"
        with self.assertRaisesRegex(CameraConfigError, "keys must match"):
            parse_camera_config(extra)

        wrong_shape = copy.deepcopy(self.raw_config)
        wrong_shape["target_scene"]["targets"][0]["shape"] = "mesh"
        with self.assertRaisesRegex(CameraConfigError, "shape"):
            parse_camera_config(wrong_shape)

        too_large = copy.deepcopy(self.raw_config)
        too_large["target_scene"]["targets"][0]["size_m"] = [1.0, 1.0, 1.0]
        with self.assertRaisesRegex(CameraConfigError, "size_m"):
            parse_camera_config(too_large)

    def test_parser_rejects_weakened_or_wrong_pose_binding(self) -> None:
        for field, value in (
            ("mode", "automatic_parenting"),
            ("parent_body", "wrist"),
            ("orientation_convention", "ros"),
            ("position_tolerance_m", 0.1),
            ("orientation_tolerance_deg", 20.0),
            ("minimum_dynamic_translation_m", 0.0),
            ("minimum_dynamic_rotation_deg", 0.0),
        ):
            broken = copy.deepcopy(self.raw_config)
            broken["pose_binding"][field] = value
            with self.subTest(field=field):
                with self.assertRaises(CameraConfigError):
                    parse_camera_config(broken)

    def test_synthetic_remote_observation_passes_all_machine_checks(self) -> None:
        result = evaluate_camera_observations(
            self.config,
            camera_prim_is_usdgeom_camera=True,
            sensor_initialized=True,
            physics_dt_s=1 / 60,
            frame_samples=self._valid_samples(),
            target_projections=self._valid_projections(),
            saved_png_sha256="a" * 64,
            binding_metrics=self._valid_binding_metrics(),
        )
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["checks"].values()))

    def test_constant_or_wrong_shape_frame_fails(self) -> None:
        constant = self._valid_samples()
        constant[-1]["min"] = 42
        constant[-1]["max"] = 42
        constant[-1]["std"] = 0.0
        result = evaluate_camera_observations(
            self.config,
            camera_prim_is_usdgeom_camera=True,
            sensor_initialized=True,
            physics_dt_s=1 / 60,
            frame_samples=constant,
            target_projections=self._valid_projections(),
            saved_png_sha256="b" * 64,
            binding_metrics=self._valid_binding_metrics(),
        )
        self.assertFalse(result["checks"]["rgb_is_nonconstant"])
        self.assertFalse(result["passed"])

        wrong_shape = self._valid_samples()
        wrong_shape[-1]["shape"] = [1, 240, 320, 3]
        result = evaluate_camera_observations(
            self.config,
            camera_prim_is_usdgeom_camera=True,
            sensor_initialized=True,
            physics_dt_s=1 / 60,
            frame_samples=wrong_shape,
            target_projections=self._valid_projections(),
            saved_png_sha256="c" * 64,
            binding_metrics=self._valid_binding_metrics(),
        )
        self.assertFalse(result["checks"]["rgb_shape_is_1x480x640x3"])

    def test_rate_and_target_visibility_are_machine_gates(self) -> None:
        wrong_rate = self._valid_samples()
        for index, sample in enumerate(wrong_rate):
            sample["simulation_time_s"] = 1.0 + index * 0.2
        projections = self._valid_projections()
        projections[-1]["center_in_frame"] = False
        result = evaluate_camera_observations(
            self.config,
            camera_prim_is_usdgeom_camera=True,
            sensor_initialized=True,
            physics_dt_s=1 / 60,
            frame_samples=wrong_rate,
            target_projections=projections,
            saved_png_sha256="d" * 64,
            binding_metrics=self._valid_binding_metrics(),
        )
        self.assertFalse(result["checks"]["simulation_time_cadence_is_10_hz"])
        self.assertFalse(result["checks"]["all_target_centers_project_inside_frame"])
        self.assertFalse(result["passed"])

    def test_missing_png_or_uninitialized_sensor_fails(self) -> None:
        result = evaluate_camera_observations(
            self.config,
            camera_prim_is_usdgeom_camera=True,
            sensor_initialized=False,
            physics_dt_s=1 / 60,
            frame_samples=self._valid_samples(),
            target_projections=self._valid_projections(),
            saved_png_sha256=None,
            binding_metrics=self._valid_binding_metrics(),
        )
        self.assertFalse(result["checks"]["sensor_initialized"])
        self.assertFalse(result["checks"]["png_saved_with_sha256"])

    def test_pose_binding_is_a_machine_gate(self) -> None:
        broken_binding = self._valid_binding_metrics()
        broken_binding["maximum_applied_position_error_m"] = 0.02
        broken_binding["maximum_dynamic_translation_m"] = 0.0
        broken_binding["maximum_dynamic_rotation_deg"] = 0.0
        result = evaluate_camera_observations(
            self.config,
            camera_prim_is_usdgeom_camera=True,
            sensor_initialized=True,
            physics_dt_s=1 / 60,
            frame_samples=self._valid_samples(),
            target_projections=self._valid_projections(),
            saved_png_sha256="e" * 64,
            binding_metrics=broken_binding,
        )
        self.assertFalse(result["checks"]["camera_world_pose_matches_binding"])
        self.assertFalse(result["checks"]["camera_pose_changes_with_link4"])
        self.assertFalse(result["passed"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
