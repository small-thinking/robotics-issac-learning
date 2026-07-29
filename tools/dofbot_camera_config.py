"""Fail-closed configuration and acceptance checks for DOFBOT Goal 3.

This module deliberately has no Isaac Lab dependency so the camera contract can
be validated locally before a paid GPU window.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__:
    from .dofbot_camera_binding import (
        EXPECTED_BINDING_MODE,
        EXPECTED_CAMERA_CONVENTION,
        EXPECTED_PARENT_BODY,
    )
else:
    from dofbot_camera_binding import (
        EXPECTED_BINDING_MODE,
        EXPECTED_CAMERA_CONVENTION,
        EXPECTED_PARENT_BODY,
    )

CAMERA_CONFIG_SCHEMA_VERSION = 1
EXPECTED_CAMERA_PRIM_PATH = "/World/envs/env_0/Dofbot/link4/Camera"
SUPPORTED_DATA_TYPES = ("rgb",)
SUPPORTED_TARGET_SHAPES = ("cuboid", "cylinder")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class CameraConfigError(ValueError):
    """Raised when a Goal 3 camera configuration or result is unsafe."""


@dataclass(frozen=True)
class CameraTarget:
    name: str
    prim_path: str
    shape: str
    size_m: tuple[float, ...]
    color_rgb: tuple[float, float, float]
    lateral_index: int

    @property
    def height_m(self) -> float:
        return self.size_m[2] if self.shape == "cuboid" else self.size_m[1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "prim_path": self.prim_path,
            "shape": self.shape,
            "size_m": list(self.size_m),
            "color_rgb": list(self.color_rgb),
            "lateral_index": self.lateral_index,
        }


@dataclass(frozen=True)
class CameraPoseBindingConfig:
    mode: str
    parent_body: str
    orientation_convention: str
    position_tolerance_m: float
    orientation_tolerance_deg: float
    minimum_dynamic_translation_m: float
    minimum_dynamic_rotation_deg: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "parent_body": self.parent_body,
            "orientation_convention": self.orientation_convention,
            "position_tolerance_m": self.position_tolerance_m,
            "orientation_tolerance_deg": self.orientation_tolerance_deg,
            "minimum_dynamic_translation_m": self.minimum_dynamic_translation_m,
            "minimum_dynamic_rotation_deg": self.minimum_dynamic_rotation_deg,
        }


@dataclass(frozen=True)
class DofbotCameraConfig:
    schema_version: int
    name: str
    prim_path: str
    data_types: tuple[str, ...]
    width: int
    height: int
    update_period_s: float
    warmup_frames: int
    capture_frames: int
    pose_binding: CameraPoseBindingConfig
    placement: str
    forward_distance_m: float
    lateral_spacing_m: float
    targets: tuple[CameraTarget, ...]

    @property
    def nominal_frequency_hz(self) -> float:
        return 1.0 / self.update_period_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "camera": {
                "prim_path": self.prim_path,
                "data_types": list(self.data_types),
                "width": self.width,
                "height": self.height,
                "update_period_s": self.update_period_s,
                "nominal_frequency_hz": self.nominal_frequency_hz,
                "warmup_frames": self.warmup_frames,
                "capture_frames": self.capture_frames,
            },
            "pose_binding": self.pose_binding.to_dict(),
            "target_scene": {
                "placement": self.placement,
                "forward_distance_m": self.forward_distance_m,
                "lateral_spacing_m": self.lateral_spacing_m,
                "targets": [target.to_dict() for target in self.targets],
            },
        }


def _require_exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    actual = set(value)
    if actual != expected:
        raise CameraConfigError(
            f"{context} keys must match {sorted(expected)}; got {sorted(actual)}"
        )


def _require_number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CameraConfigError(f"{context} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise CameraConfigError(f"{context} must be a finite number")
    return result


def _parse_target(value: Any) -> CameraTarget:
    if not isinstance(value, dict):
        raise CameraConfigError("each target must be an object")
    _require_exact_keys(
        value,
        {"name", "prim_path", "shape", "size_m", "color_rgb", "lateral_index"},
        "target",
    )
    name = value["name"]
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise CameraConfigError("target name must be lowercase snake_case")
    prim_path = value["prim_path"]
    if not isinstance(prim_path, str) or not prim_path.startswith("/World/CameraTargets/"):
        raise CameraConfigError("target prim_path must be under /World/CameraTargets")
    shape = value["shape"]
    if shape not in SUPPORTED_TARGET_SHAPES:
        raise CameraConfigError(f"target shape must be one of {SUPPORTED_TARGET_SHAPES}")
    expected_size_length = 3 if shape == "cuboid" else 2
    raw_size = value["size_m"]
    if not isinstance(raw_size, list) or len(raw_size) != expected_size_length:
        raise CameraConfigError(
            f"{name} size_m must have {expected_size_length} values for {shape}"
        )
    size_m = tuple(_require_number(item, f"{name}.size_m") for item in raw_size)
    if any(item < 0.01 or item > 0.15 for item in size_m):
        raise CameraConfigError(f"{name}.size_m values must be in [0.01, 0.15]")
    raw_color = value["color_rgb"]
    if not isinstance(raw_color, list) or len(raw_color) != 3:
        raise CameraConfigError(f"{name}.color_rgb must contain three values")
    color_rgb = tuple(_require_number(item, f"{name}.color_rgb") for item in raw_color)
    if any(item < 0.0 or item > 1.0 for item in color_rgb):
        raise CameraConfigError(f"{name}.color_rgb values must be in [0, 1]")
    lateral_index = value["lateral_index"]
    if isinstance(lateral_index, bool) or not isinstance(lateral_index, int):
        raise CameraConfigError(f"{name}.lateral_index must be an integer")
    if lateral_index not in (-1, 0, 1):
        raise CameraConfigError(f"{name}.lateral_index must be -1, 0, or 1")
    return CameraTarget(
        name=name,
        prim_path=prim_path,
        shape=shape,
        size_m=size_m,
        color_rgb=color_rgb,  # type: ignore[arg-type]
        lateral_index=lateral_index,
    )


def parse_camera_config(value: Any) -> DofbotCameraConfig:
    if not isinstance(value, dict):
        raise CameraConfigError("camera config must be a JSON object")
    _require_exact_keys(
        value,
        {"schema_version", "name", "camera", "pose_binding", "target_scene"},
        "camera config",
    )
    if value["schema_version"] != CAMERA_CONFIG_SCHEMA_VERSION:
        raise CameraConfigError(
            f"schema_version must be {CAMERA_CONFIG_SCHEMA_VERSION}"
        )
    name = value["name"]
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise CameraConfigError("name must be lowercase snake_case")

    camera = value["camera"]
    if not isinstance(camera, dict):
        raise CameraConfigError("camera must be an object")
    _require_exact_keys(
        camera,
        {
            "prim_path",
            "data_types",
            "width",
            "height",
            "update_period_s",
            "warmup_frames",
            "capture_frames",
        },
        "camera",
    )
    if camera["prim_path"] != EXPECTED_CAMERA_PRIM_PATH:
        raise CameraConfigError(
            f"camera.prim_path must be {EXPECTED_CAMERA_PRIM_PATH}"
        )
    if camera["data_types"] != list(SUPPORTED_DATA_TYPES):
        raise CameraConfigError("Goal 3 permits only the rgb data type")
    for field, expected in (("width", 640), ("height", 480)):
        if camera[field] != expected or isinstance(camera[field], bool):
            raise CameraConfigError(f"camera.{field} must be {expected}")
    update_period_s = _require_number(
        camera["update_period_s"], "camera.update_period_s"
    )
    if not math.isclose(update_period_s, 0.1, abs_tol=1e-12):
        raise CameraConfigError(
            "Goal 3 baseline update_period_s must be 0.1 (10 Hz simulation time)"
        )
    warmup_frames = camera["warmup_frames"]
    capture_frames = camera["capture_frames"]
    if (
        isinstance(warmup_frames, bool)
        or not isinstance(warmup_frames, int)
        or warmup_frames < 2
        or warmup_frames > 30
    ):
        raise CameraConfigError("camera.warmup_frames must be an integer in [2, 30]")
    if (
        isinstance(capture_frames, bool)
        or not isinstance(capture_frames, int)
        or capture_frames < 3
        or capture_frames > 30
    ):
        raise CameraConfigError("camera.capture_frames must be an integer in [3, 30]")

    pose_binding = value["pose_binding"]
    if not isinstance(pose_binding, dict):
        raise CameraConfigError("pose_binding must be an object")
    _require_exact_keys(
        pose_binding,
        {
            "mode",
            "parent_body",
            "orientation_convention",
            "position_tolerance_m",
            "orientation_tolerance_deg",
            "minimum_dynamic_translation_m",
            "minimum_dynamic_rotation_deg",
        },
        "pose_binding",
    )
    if pose_binding["mode"] != EXPECTED_BINDING_MODE:
        raise CameraConfigError(
            f"pose_binding.mode must be {EXPECTED_BINDING_MODE}"
        )
    if pose_binding["parent_body"] != EXPECTED_PARENT_BODY:
        raise CameraConfigError(
            f"pose_binding.parent_body must be {EXPECTED_PARENT_BODY}"
        )
    if pose_binding["orientation_convention"] != EXPECTED_CAMERA_CONVENTION:
        raise CameraConfigError(
            "pose_binding.orientation_convention must be opengl"
        )
    position_tolerance_m = _require_number(
        pose_binding["position_tolerance_m"],
        "pose_binding.position_tolerance_m",
    )
    orientation_tolerance_deg = _require_number(
        pose_binding["orientation_tolerance_deg"],
        "pose_binding.orientation_tolerance_deg",
    )
    minimum_dynamic_translation_m = _require_number(
        pose_binding["minimum_dynamic_translation_m"],
        "pose_binding.minimum_dynamic_translation_m",
    )
    minimum_dynamic_rotation_deg = _require_number(
        pose_binding["minimum_dynamic_rotation_deg"],
        "pose_binding.minimum_dynamic_rotation_deg",
    )
    if not 1e-5 <= position_tolerance_m <= 0.005:
        raise CameraConfigError(
            "pose_binding.position_tolerance_m must be in [1e-5, 0.005]"
        )
    if not 0.01 <= orientation_tolerance_deg <= 2.0:
        raise CameraConfigError(
            "pose_binding.orientation_tolerance_deg must be in [0.01, 2.0]"
        )
    if not 0.001 <= minimum_dynamic_translation_m <= 0.05:
        raise CameraConfigError(
            "pose_binding.minimum_dynamic_translation_m must be in [0.001, 0.05]"
        )
    if not 0.1 <= minimum_dynamic_rotation_deg <= 10.0:
        raise CameraConfigError(
            "pose_binding.minimum_dynamic_rotation_deg must be in [0.1, 10.0]"
        )
    parsed_pose_binding = CameraPoseBindingConfig(
        mode=pose_binding["mode"],
        parent_body=pose_binding["parent_body"],
        orientation_convention=pose_binding["orientation_convention"],
        position_tolerance_m=position_tolerance_m,
        orientation_tolerance_deg=orientation_tolerance_deg,
        minimum_dynamic_translation_m=minimum_dynamic_translation_m,
        minimum_dynamic_rotation_deg=minimum_dynamic_rotation_deg,
    )

    target_scene = value["target_scene"]
    if not isinstance(target_scene, dict):
        raise CameraConfigError("target_scene must be an object")
    _require_exact_keys(
        target_scene,
        {
            "placement",
            "forward_distance_m",
            "lateral_spacing_m",
            "targets",
        },
        "target_scene",
    )
    if target_scene["placement"] != "camera_forward_optical_plane":
        raise CameraConfigError(
            "target_scene.placement must be camera_forward_optical_plane"
        )
    forward_distance_m = _require_number(
        target_scene["forward_distance_m"], "target_scene.forward_distance_m"
    )
    lateral_spacing_m = _require_number(
        target_scene["lateral_spacing_m"], "target_scene.lateral_spacing_m"
    )
    if not 0.15 <= forward_distance_m <= 0.60:
        raise CameraConfigError("forward_distance_m must be in [0.15, 0.60]")
    if not 0.03 <= lateral_spacing_m <= 0.12:
        raise CameraConfigError("lateral_spacing_m must be in [0.03, 0.12]")
    raw_targets = target_scene["targets"]
    if not isinstance(raw_targets, list) or len(raw_targets) != 3:
        raise CameraConfigError("target_scene.targets must contain exactly three targets")
    targets = tuple(_parse_target(item) for item in raw_targets)
    if len({target.name for target in targets}) != len(targets):
        raise CameraConfigError("target names must be unique")
    if len({target.prim_path for target in targets}) != len(targets):
        raise CameraConfigError("target prim paths must be unique")
    if {target.lateral_index for target in targets} != {-1, 0, 1}:
        raise CameraConfigError("targets must occupy lateral indices -1, 0, and 1")

    return DofbotCameraConfig(
        schema_version=value["schema_version"],
        name=name,
        prim_path=camera["prim_path"],
        data_types=tuple(camera["data_types"]),
        width=camera["width"],
        height=camera["height"],
        update_period_s=update_period_s,
        warmup_frames=warmup_frames,
        capture_frames=capture_frames,
        pose_binding=parsed_pose_binding,
        placement=target_scene["placement"],
        forward_distance_m=forward_distance_m,
        lateral_spacing_m=lateral_spacing_m,
        targets=targets,
    )


def load_camera_config(path: Path) -> tuple[DofbotCameraConfig, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CameraConfigError(f"{path} is not valid JSON: {error}") from error
    return parse_camera_config(value), hashlib.sha256(raw).hexdigest()


def evaluate_camera_observations(
    config: DofbotCameraConfig,
    *,
    camera_prim_is_usdgeom_camera: bool,
    sensor_initialized: bool,
    physics_dt_s: float,
    frame_samples: list[dict[str, Any]],
    target_projections: list[dict[str, Any]],
    saved_png_sha256: str | None,
    binding_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate the remote RGB result without silently weakening Goal 3."""

    expected_shape = [1, config.height, config.width, 3]
    frames = [sample.get("frame") for sample in frame_samples]
    sim_times = [sample.get("simulation_time_s") for sample in frame_samples]
    shapes_match = bool(frame_samples) and all(
        sample.get("shape") == expected_shape for sample in frame_samples
    )
    dtypes_match = bool(frame_samples) and all(
        sample.get("dtype") == "torch.uint8" for sample in frame_samples
    )
    frames_advance = len(frames) >= config.capture_frames and all(
        isinstance(previous, int)
        and isinstance(current, int)
        and current > previous
        for previous, current in zip(frames, frames[1:], strict=False)
    )
    cadence_tolerance_s = max(physics_dt_s * 1.5, config.update_period_s * 0.15)
    cadence_intervals_s: list[float] = []
    if len(sim_times) >= 2 and all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in sim_times
    ):
        cadence_intervals_s = [
            float(current) - float(previous)
            for previous, current in zip(sim_times, sim_times[1:], strict=False)
        ]
    cadence_matches = len(cadence_intervals_s) >= config.capture_frames - 1 and all(
        abs(interval - config.update_period_s) <= cadence_tolerance_s
        for interval in cadence_intervals_s
    )
    rgb_nonconstant = bool(frame_samples) and all(
        isinstance(sample.get("min"), (int, float))
        and isinstance(sample.get("max"), (int, float))
        and isinstance(sample.get("std"), (int, float))
        and float(sample["max"]) > float(sample["min"])
        and float(sample["std"]) > 1.0
        for sample in frame_samples
    )
    expected_target_paths = {target.prim_path for target in config.targets}
    projected_target_paths = {
        item.get("prim_path")
        for item in target_projections
        if item.get("center_in_frame") is True
    }
    targets_in_frame = projected_target_paths == expected_target_paths
    png_saved = isinstance(saved_png_sha256, str) and bool(
        SHA256_PATTERN.fullmatch(saved_png_sha256)
    )
    calibration_position_error_m = binding_metrics.get(
        "calibration_roundtrip_position_error_m"
    )
    calibration_orientation_error_deg = binding_metrics.get(
        "calibration_roundtrip_orientation_error_deg"
    )
    maximum_position_error_m = binding_metrics.get(
        "maximum_applied_position_error_m"
    )
    maximum_orientation_error_deg = binding_metrics.get(
        "maximum_applied_orientation_error_deg"
    )
    maximum_dynamic_translation_m = binding_metrics.get(
        "maximum_dynamic_translation_m"
    )
    maximum_dynamic_rotation_deg = binding_metrics.get(
        "maximum_dynamic_rotation_deg"
    )
    calibration_roundtrip_matches = (
        isinstance(calibration_position_error_m, (int, float))
        and not isinstance(calibration_position_error_m, bool)
        and isinstance(calibration_orientation_error_deg, (int, float))
        and not isinstance(calibration_orientation_error_deg, bool)
        and float(calibration_position_error_m)
        <= config.pose_binding.position_tolerance_m
        and float(calibration_orientation_error_deg)
        <= config.pose_binding.orientation_tolerance_deg
    )
    applied_pose_matches = (
        isinstance(maximum_position_error_m, (int, float))
        and not isinstance(maximum_position_error_m, bool)
        and isinstance(maximum_orientation_error_deg, (int, float))
        and not isinstance(maximum_orientation_error_deg, bool)
        and float(maximum_position_error_m)
        <= config.pose_binding.position_tolerance_m
        and float(maximum_orientation_error_deg)
        <= config.pose_binding.orientation_tolerance_deg
    )
    dynamic_pose_observed = (
        isinstance(maximum_dynamic_translation_m, (int, float))
        and not isinstance(maximum_dynamic_translation_m, bool)
        and isinstance(maximum_dynamic_rotation_deg, (int, float))
        and not isinstance(maximum_dynamic_rotation_deg, bool)
        and (
            float(maximum_dynamic_translation_m)
            >= config.pose_binding.minimum_dynamic_translation_m
            or float(maximum_dynamic_rotation_deg)
            >= config.pose_binding.minimum_dynamic_rotation_deg
        )
    )
    checks = {
        "camera_prim_is_usdgeom_camera": camera_prim_is_usdgeom_camera,
        "sensor_initialized": sensor_initialized,
        "rgb_only_scope": config.data_types == SUPPORTED_DATA_TYPES,
        "captured_expected_frame_count": len(frame_samples) >= config.capture_frames,
        "frames_advance": frames_advance,
        "rgb_shape_is_1x480x640x3": shapes_match,
        "rgb_dtype_is_uint8": dtypes_match,
        "rgb_is_nonconstant": rgb_nonconstant,
        "simulation_time_cadence_is_10_hz": cadence_matches,
        "all_target_centers_project_inside_frame": targets_in_frame,
        "png_saved_with_sha256": png_saved,
        "link4_camera_calibration_roundtrip": calibration_roundtrip_matches,
        "camera_world_pose_matches_binding": applied_pose_matches,
        "camera_pose_changes_with_link4": dynamic_pose_observed,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "expected_shape": expected_shape,
        "nominal_frequency_hz": config.nominal_frequency_hz,
        "cadence_intervals_s": cadence_intervals_s,
        "cadence_tolerance_s": cadence_tolerance_s,
        "pose_binding_tolerances": config.pose_binding.to_dict(),
    }
