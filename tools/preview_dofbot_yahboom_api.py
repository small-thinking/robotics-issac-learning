"""Dry-run the Goal 2 trajectory through Yahboom's documented servo API."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

try:
    from .dofbot_control_api import (
        CONTROLLED_JOINT_NAMES,
        DOCUMENTED_YAHBOOM_CALIBRATION,
        DofbotArm,
        YahboomDryRunBackend,
    )
    from .dofbot_motion_plan import build_motion_plan, iter_plan_samples
except ImportError:
    from dofbot_control_api import (
        CONTROLLED_JOINT_NAMES,
        DOCUMENTED_YAHBOOM_CALIBRATION,
        DofbotArm,
        YahboomDryRunBackend,
    )
    from dofbot_motion_plan import build_motion_plan, iter_plan_samples


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Encode the safe DOFBOT motion plan as Yahboom API calls without hardware."
    )
    parser.add_argument(
        "--asset-contract",
        type=Path,
        default=Path("artifacts/dofbot/asset_contract.json"),
    )
    parser.add_argument("--sample-hz", type=float, default=10.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def build_preview(
    *,
    asset_contract: dict[str, Any],
    sample_hz: float,
) -> dict[str, object]:
    if not math.isfinite(sample_hz) or sample_hz <= 0.0:
        raise ValueError("sample_hz must be positive and finite")
    plan = build_motion_plan(asset_contract)
    backend = YahboomDryRunBackend()
    arm = DofbotArm(backend)
    duration_ms = round(1000.0 / sample_hz)
    samples = iter_plan_samples(plan, sample_hz=sample_hz)

    for sample in samples:
        arm.move_joints(
            sample.target_positions_rad,
            duration_ms=duration_ms,
        )

    writes = backend.writes
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
    checks = {
        "uses_documented_single_servo_method": all(
            write.method == "Arm_serial_servo_write" for write in writes
        ),
        "servo_ids_match_joint_order": set(write.servo_id for write in writes)
        == {1, 2, 3, 4},
        "all_angles_within_documented_range": all(
            0 <= write.angle_deg <= 180 for write in writes
        ),
        "positive_nonzero_duration": all(write.duration_ms > 0 for write in writes),
        "one_write_per_joint_per_sample": len(writes)
        == len(samples) * len(CONTROLLED_JOINT_NAMES),
        "real_hardware_not_commanded": True,
        "hardware_calibration_remains_unverified": (
            not DOCUMENTED_YAHBOOM_CALIBRATION.hardware_verified
        ),
    }
    return {
        "schema_version": 1,
        "experiment": "dofbot_yahboom_api_dry_run",
        "official_api": {
            "single_servo_method": "Arm_serial_servo_write(id, angle, time)",
            "read_method": "Arm_serial_servo_read(id)",
            "six_servo_method_reserved": (
                "Arm_serial_servo_write6(S1, S2, S3, S4, S5, S6, time)"
            ),
            "six_servo_method_used": False,
            "reason": "servo5 wrist and servo6 gripper are not calibrated",
        },
        "mapping": {
            "formula": "servo_angle_deg = 90 + degrees(sim_joint_rad)",
            "joint_to_servo_id": {
                name: index for index, name in enumerate(CONTROLLED_JOINT_NAMES, start=1)
            },
            "hardware_verified": DOCUMENTED_YAHBOOM_CALIBRATION.hardware_verified,
            "provenance": DOCUMENTED_YAHBOOM_CALIBRATION.provenance,
        },
        "trajectory": {
            "sample_hz": sample_hz,
            "sample_count": len(samples),
            "duration_ms_per_write": duration_ms,
            "official_api_call_count": len(writes),
            "per_servo_ranges": per_servo_ranges,
            "first_calls": [write.to_dict() for write in writes[:8]],
            "last_calls": [write.to_dict() for write in writes[-8:]],
        },
        "acceptance": {
            "checks": checks,
            "software_bridge_passed": all(checks.values()),
            "physical_hardware_passed": False,
        },
        "scope": {
            "real_hardware_commanded": False,
            "arm_lib_imported": False,
            "gpu_started": False,
        },
    }


def main() -> None:
    args = _parse_args()
    asset_contract = json.loads(args.asset_contract.read_text(encoding="utf-8"))
    result = build_preview(
        asset_contract=asset_contract,
        sample_hz=args.sample_hz,
    )
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not result["acceptance"]["software_bridge_passed"]:
        raise SystemExit("Yahboom API dry-run acceptance failed")


if __name__ == "__main__":
    main()
