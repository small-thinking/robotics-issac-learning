"""Compile Goal 4 reaching preparation without Isaac, GPU, or hardware."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .dofbot_motion_config import compile_motion_config
    from .dofbot_reaching import (
        load_reaching_config,
        next_state_controller_angles,
    )
except ImportError:
    from dofbot_motion_config import compile_motion_config
    from dofbot_reaching import (
        load_reaching_config,
        next_state_controller_angles,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed local preview of fixed-tabletop DOFBOT reaching."
    )
    parser.add_argument(
        "--reaching-config",
        type=Path,
        default=Path("configs/dofbot/reaching/goal4_fixed_tabletop.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/dofbot-reaching-preview.json"),
    )
    return parser.parse_args()


def build_preview(*, reaching_config_path: Path) -> dict[str, Any]:
    config, source_sha256 = load_reaching_config(reaching_config_path)
    scripted_samples = compile_motion_config(config.scripted_baseline)
    scripted_writes = [write for sample in scripted_samples for write in sample.api_writes()]
    synthetic_jacobian = (
        (0.10, 0.00, 0.00, 0.00),
        (0.00, 0.10, 0.00, 0.00),
        (0.00, 0.00, 0.10, 0.05),
    )
    synthetic_error = (0.03, -0.02, -0.01)
    synthetic_next_angles = next_state_controller_angles(
        current_angles_deg=(90.0, 90.0, 90.0, 90.0),
        translation_jacobian=synthetic_jacobian,
        position_error_m=synthetic_error,
        controller=config.state_controller,
    )
    checks = {
        "table_collision_enabled": config.table.collision_enabled,
        "target_cube_static": config.target_cube.static,
        "target_cube_collision_enabled": config.target_cube.collision_enabled,
        "target_cube_rests_on_table": abs(config.target_cube.bottom_z_m - config.table.top_z_m)
        <= 1e-6,
        "approach_waypoint_is_above_cube": (
            config.approach_target_world_m[2] > config.target_cube.top_z_m
        ),
        "scripted_starts_neutral": (scripted_samples[0].angles_deg == (90, 90, 90, 90)),
        "scripted_ends_neutral": (scripted_samples[-1].angles_deg == (90, 90, 90, 90)),
        "scripted_calls_only_at_pose_boundaries": (
            len(scripted_writes) == len(config.scripted_baseline.steps) * 4
        ),
        "synthetic_state_step_within_safe_envelope": all(
            config.state_controller.safe_angle_min_deg
            <= angle
            <= config.state_controller.safe_angle_max_deg
            for angle in synthetic_next_angles
        ),
        "real_hardware_not_commanded": True,
        "gpu_not_started": True,
    }
    return {
        "schema_version": 1,
        "experiment": "dofbot_goal4_reaching_local_preparation",
        "source": {
            "path": str(reaching_config_path),
            "sha256": source_sha256,
        },
        "config": config.to_dict(),
        "compiled": {
            "approach_target_world_m": list(config.approach_target_world_m),
            "scripted_sample_count": len(scripted_samples),
            "scripted_official_api_call_count": len(scripted_writes),
            "scripted_api_writes": [write.to_dict() for write in scripted_writes],
            "synthetic_state_controller_probe": {
                "current_angles_deg": [90, 90, 90, 90],
                "position_error_m": list(synthetic_error),
                "next_angles_deg": list(synthetic_next_angles),
            },
        },
        "acceptance": {
            "checks": checks,
            "software_preparation_passed": all(checks.values()),
            "simulator_machine_passed": False,
            "visual_passed": False,
            "physical_hardware_passed": False,
        },
        "scope": {
            "gpu_started": False,
            "isaac_started": False,
            "real_hardware_commanded": False,
            "arm_lib_imported": False,
            "camera_used_as_controller_input": False,
            "gripper_commanded": False,
            "target_cube_moved": False,
            "policy_or_checkpoint_loaded": False,
        },
    }


def main() -> None:
    args = _parse_args()
    result = build_preview(reaching_config_path=args.reaching_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "[INFO] "
        f"config={result['config']['name']} "
        f"scripted_api_calls="
        f"{result['compiled']['scripted_official_api_call_count']} "
        f"output={args.output}",
        flush=True,
    )
    if not result["acceptance"]["software_preparation_passed"]:
        raise SystemExit("DOFBOT reaching local preparation failed")


if __name__ == "__main__":
    main()
