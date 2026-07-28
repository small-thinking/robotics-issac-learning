"""Compile and inspect a DOFBOT ActionChunk config without Isaac or hardware."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .dofbot_motion_config import (
        NEUTRAL_ANGLES_DEG,
        SAFE_MAX_ANGLE_DEG,
        SAFE_MIN_ANGLE_DEG,
        compile_motion_config,
        load_motion_config,
    )
except ImportError:
    from dofbot_motion_config import (
        NEUTRAL_ANGLES_DEG,
        SAFE_MAX_ANGLE_DEG,
        SAFE_MIN_ANGLE_DEG,
        compile_motion_config,
        load_motion_config,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed local preview of a DOFBOT motion config."
    )
    parser.add_argument(
        "--motion-config",
        type=Path,
        default=Path("configs/dofbot/motions/safe_api_wave.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/dofbot-motion-config-preview.json"),
    )
    return parser.parse_args()


def build_preview(
    *,
    motion_config_path: Path,
) -> dict[str, Any]:
    config, source_sha256 = load_motion_config(motion_config_path)
    samples = compile_motion_config(config)
    writes = [
        write
        for sample in samples
        for write in sample.api_writes()
    ]
    per_servo_ranges = {
        str(servo_id): {
            "minimum_angle_deg": min(
                write.angle_deg for write in writes if write.servo_id == servo_id
            ),
            "maximum_angle_deg": max(
                write.angle_deg for write in writes if write.servo_id == servo_id
            ),
        }
        for servo_id in range(1, 5)
    }
    maximum_compiled_delta_deg = max(
        max(
            abs(current - previous)
            for current, previous in zip(
                sample.angles_deg,
                samples[index - 1].angles_deg
                if index
                else NEUTRAL_ANGLES_DEG,
                strict=True,
            )
        )
        for index, sample in enumerate(samples)
    )
    checks = {
        "starts_neutral": samples[0].angles_deg == NEUTRAL_ANGLES_DEG,
        "ends_neutral": samples[-1].angles_deg == NEUTRAL_ANGLES_DEG,
        "angles_within_safe_profile": all(
            SAFE_MIN_ANGLE_DEG <= write.angle_deg <= SAFE_MAX_ANGLE_DEG
            for write in writes
        ),
        "one_write_per_servo_per_sample": len(writes) == len(samples) * 4,
        "compiled_duration_matches_config": (
            samples[-1].elapsed_ms == config.total_duration_ms
        ),
        "compiled_delta_no_more_than_one_degree": maximum_compiled_delta_deg <= 1,
        "real_hardware_not_commanded": True,
        "gpu_not_started": True,
    }
    return {
        "schema_version": 1,
        "experiment": "dofbot_motion_config_local_dry_run",
        "source": {
            "path": str(motion_config_path),
            "sha256": source_sha256,
        },
        "config": config.to_dict(),
        "compiled": {
            "control_hz": config.control_hz,
            "total_duration_ms": config.total_duration_ms,
            "sample_count": len(samples),
            "official_api_call_count": len(writes),
            "maximum_sample_delta_deg": maximum_compiled_delta_deg,
            "per_servo_ranges": per_servo_ranges,
            "first_calls": [write.to_dict() for write in writes[:8]],
            "last_calls": [write.to_dict() for write in writes[-8:]],
            "samples": [sample.to_dict() for sample in samples],
        },
        "acceptance": {
            "checks": checks,
            "software_compile_passed": all(checks.values()),
            "simulator_machine_passed": False,
            "visual_passed": False,
            "physical_hardware_passed": False,
        },
        "scope": {
            "real_hardware_commanded": False,
            "arm_lib_imported": False,
            "gpu_started": False,
            "camera_tensor_captured": False,
            "policy_or_checkpoint_loaded": False,
        },
    }


def main() -> None:
    args = _parse_args()
    result = build_preview(motion_config_path=args.motion_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "[INFO] "
        f"config={result['config']['name']} "
        f"samples={result['compiled']['sample_count']} "
        f"api_calls={result['compiled']['official_api_call_count']} "
        f"output={args.output}",
        flush=True,
    )
    if not result["acceptance"]["software_compile_passed"]:
        raise SystemExit("DOFBOT motion config dry-run acceptance failed")


if __name__ == "__main__":
    main()
