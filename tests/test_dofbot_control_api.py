from __future__ import annotations

import json
import math
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from tools.dofbot_control_api import (
    CONTROLLED_JOINT_NAMES,
    DOCUMENTED_YAHBOOM_CALIBRATION,
    DofbotArm,
    DofbotControlError,
    JointPositionCommand,
    YahboomArmLibBackend,
    YahboomDryRunBackend,
    YahboomJointCalibration,
    YahboomServoApiAdapter,
    encode_yahboom_servo_writes,
)
from tools.preview_dofbot_yahboom_api import build_preview

PROJECT_DIR = Path(__file__).resolve().parents[1]
ASSET_CONTRACT_PATH = PROJECT_DIR / "artifacts/dofbot/asset_contract.json"


def _positions(**overrides: float) -> dict[str, float]:
    positions = dict.fromkeys(CONTROLLED_JOINT_NAMES, 0.0)
    positions.update(overrides)
    return positions


class _FakeArmDevice:
    def __init__(self, reads: dict[int, Any] | None = None) -> None:
        self.writes: list[tuple[int, int, int]] = []
        self.reads = reads or {}

    def Arm_serial_servo_write(self, servo_id: int, angle: int, time: int) -> None:
        self.writes.append((servo_id, angle, time))

    def Arm_serial_servo_write6(
        self,
        s1: int,
        s2: int,
        s3: int,
        s4: int,
        s5: int,
        s6: int,
        time: int,
    ) -> None:
        raise AssertionError("six-servo API must not be called")

    def Arm_serial_servo_read(self, servo_id: int) -> Any:
        return self.reads[servo_id]


class _MemoryBackend:
    def __init__(self, positions: dict[str, float] | None = None) -> None:
        self.positions = positions or _positions()
        self.commands: list[JointPositionCommand] = []

    def command_joint_positions(self, command: JointPositionCommand) -> None:
        self.commands.append(command)
        self.positions = command.as_mapping()

    def read_joint_positions(self) -> dict[str, float]:
        return dict(self.positions)


class DofbotControlApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.asset_contract = json.loads(ASSET_CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_documented_neutral_maps_joint1_through_joint4_to_90_degrees(self) -> None:
        command = JointPositionCommand.from_mapping(_positions(), duration_ms=500)
        writes = encode_yahboom_servo_writes(command)
        self.assertEqual(
            [(write.servo_id, write.angle_deg, write.duration_ms) for write in writes],
            [(1, 90, 500), (2, 90, 500), (3, 90, 500), (4, 90, 500)],
        )

    def test_radians_map_to_documented_degree_endpoints(self) -> None:
        positive = JointPositionCommand.from_mapping(
            _positions(joint1=math.pi / 2),
            duration_ms=100,
        )
        negative = JointPositionCommand.from_mapping(
            _positions(joint1=-math.pi / 2),
            duration_ms=100,
        )
        self.assertEqual(encode_yahboom_servo_writes(positive)[0].angle_deg, 180)
        self.assertEqual(encode_yahboom_servo_writes(negative)[0].angle_deg, 0)

    def test_goal_two_amplitude_maps_to_85_through_95_degrees(self) -> None:
        positive = JointPositionCommand.from_mapping(
            _positions(joint2=math.radians(5)),
            duration_ms=100,
        )
        negative = JointPositionCommand.from_mapping(
            _positions(joint2=math.radians(-5)),
            duration_ms=100,
        )
        self.assertEqual(encode_yahboom_servo_writes(positive)[1].angle_deg, 95)
        self.assertEqual(encode_yahboom_servo_writes(negative)[1].angle_deg, 85)

    def test_command_rejects_missing_extra_or_nonfinite_joint_values(self) -> None:
        with self.assertRaisesRegex(DofbotControlError, "exactly"):
            JointPositionCommand.from_mapping({"joint1": 0.0}, duration_ms=100)
        with self.assertRaisesRegex(DofbotControlError, "exactly"):
            JointPositionCommand.from_mapping(
                {**_positions(), "joint5": 0.0},
                duration_ms=100,
            )
        with self.assertRaisesRegex(DofbotControlError, "finite"):
            JointPositionCommand.from_mapping(
                _positions(joint1=math.nan),
                duration_ms=100,
            )

    def test_command_rejects_invalid_duration(self) -> None:
        for invalid in (True, 0, -1, 30_001, 1.5):
            with self.subTest(invalid=invalid):
                with self.assertRaises(DofbotControlError):
                    JointPositionCommand.from_mapping(
                        _positions(),
                        duration_ms=invalid,  # type: ignore[arg-type]
                    )

    def test_mapping_rejects_angle_outside_documented_range(self) -> None:
        command = JointPositionCommand.from_mapping(
            _positions(joint4=math.radians(91)),
            duration_ms=100,
        )
        with self.assertRaisesRegex(DofbotControlError, "outside servo 4 range"):
            encode_yahboom_servo_writes(command)

    def test_mapping_rejects_invalid_calibration_before_encoding(self) -> None:
        invalid_joint = YahboomJointCalibration(
            joint_name="joint1",
            servo_id=2,
            center_deg=math.nan,
            direction=0,
            minimum_deg=0,
            maximum_deg=180,
        )
        invalid = replace(
            DOCUMENTED_YAHBOOM_CALIBRATION,
            joints=(invalid_joint, *DOCUMENTED_YAHBOOM_CALIBRATION.joints[1:]),
        )
        command = JointPositionCommand.from_mapping(_positions(), duration_ms=100)
        with self.assertRaisesRegex(DofbotControlError, "documented servo ID 1"):
            encode_yahboom_servo_writes(command, calibration=invalid)

    def test_dry_run_records_exact_official_single_servo_calls(self) -> None:
        backend = YahboomDryRunBackend()
        arm = DofbotArm(backend)
        arm.move_joints(_positions(joint3=math.radians(5)), duration_ms=250)
        self.assertEqual(
            [write.to_dict() for write in backend.writes],
            [
                {
                    "method": "Arm_serial_servo_write",
                    "servo_id": 1,
                    "angle_deg": 90,
                    "duration_ms": 250,
                },
                {
                    "method": "Arm_serial_servo_write",
                    "servo_id": 2,
                    "angle_deg": 90,
                    "duration_ms": 250,
                },
                {
                    "method": "Arm_serial_servo_write",
                    "servo_id": 3,
                    "angle_deg": 95,
                    "duration_ms": 250,
                },
                {
                    "method": "Arm_serial_servo_write",
                    "servo_id": 4,
                    "angle_deg": 90,
                    "duration_ms": 250,
                },
            ],
        )

    def test_official_api_shape_controls_simulator_style_backend(self) -> None:
        backend = _MemoryBackend()
        api = YahboomServoApiAdapter(DofbotArm(backend))
        api.Arm_serial_servo_write(2, 95, 250)
        self.assertEqual(len(backend.commands), 1)
        self.assertEqual(backend.commands[0].duration_ms, 250)
        self.assertAlmostEqual(
            backend.commands[0].as_mapping()["joint2"],
            math.radians(5),
        )
        for name in ("joint1", "joint3", "joint4"):
            self.assertEqual(backend.commands[0].as_mapping()[name], 0.0)

    def test_official_read_shape_converts_backend_radians_to_degrees(self) -> None:
        backend = _MemoryBackend(_positions(joint3=math.radians(-5)))
        api = YahboomServoApiAdapter(DofbotArm(backend))
        self.assertEqual(api.Arm_serial_servo_read(3), 85)

    def test_official_api_adapter_rejects_unvalidated_servos_and_batch_call(self) -> None:
        api = YahboomServoApiAdapter(DofbotArm(_MemoryBackend()))
        with self.assertRaisesRegex(DofbotControlError, "IDs 1 through 4"):
            api.Arm_serial_servo_write(5, 90, 100)
        with self.assertRaisesRegex(DofbotControlError, "disabled"):
            api.Arm_serial_servo_write6(90, 90, 90, 90, 90, 90, 100)

    def test_real_backend_refuses_unverified_calibration_without_writes(self) -> None:
        device = _FakeArmDevice()
        backend = YahboomArmLibBackend(
            device,
            calibration=DOCUMENTED_YAHBOOM_CALIBRATION,
        )
        arm = DofbotArm(backend)
        with self.assertRaisesRegex(DofbotControlError, "not verified"):
            arm.move_joints(_positions(), duration_ms=100)
        self.assertEqual(device.writes, [])

    def test_verified_backend_calls_official_method_for_four_servos(self) -> None:
        device = _FakeArmDevice()
        verified = replace(DOCUMENTED_YAHBOOM_CALIBRATION, hardware_verified=True)
        arm = DofbotArm(YahboomArmLibBackend(device, calibration=verified))
        arm.move_joints(_positions(joint1=math.radians(5)), duration_ms=400)
        self.assertEqual(
            device.writes,
            [(1, 95, 400), (2, 90, 400), (3, 90, 400), (4, 90, 400)],
        )

    def test_verified_backend_reads_degrees_back_as_named_radians(self) -> None:
        device = _FakeArmDevice({1: 90, 2: 95, 3: 85, 4: 100})
        verified = replace(DOCUMENTED_YAHBOOM_CALIBRATION, hardware_verified=True)
        positions = DofbotArm(
            YahboomArmLibBackend(device, calibration=verified)
        ).read_joint_positions()
        expected_deg = {"joint1": 0, "joint2": 5, "joint3": -5, "joint4": 10}
        for name, degrees in expected_deg.items():
            self.assertAlmostEqual(positions[name], math.radians(degrees))

    def test_failed_hardware_read_is_rejected(self) -> None:
        device = _FakeArmDevice({1: 90, 2: -1, 3: 90, 4: 90})
        verified = replace(DOCUMENTED_YAHBOOM_CALIBRATION, hardware_verified=True)
        arm = DofbotArm(YahboomArmLibBackend(device, calibration=verified))
        with self.assertRaisesRegex(DofbotControlError, "position read failed"):
            arm.read_joint_positions()

    def test_real_backend_refuses_unverified_calibration_before_reading(self) -> None:
        device = _FakeArmDevice({1: 90, 2: 90, 3: 90, 4: 90})
        arm = DofbotArm(
            YahboomArmLibBackend(
                device,
                calibration=DOCUMENTED_YAHBOOM_CALIBRATION,
            )
        )
        with self.assertRaisesRegex(DofbotControlError, "not verified"):
            arm.read_joint_positions()

    def test_full_goal_two_dry_run_passes_without_gpu_or_hardware(self) -> None:
        preview = build_preview(asset_contract=self.asset_contract, sample_hz=10.0)
        acceptance = preview["acceptance"]
        scope = preview["scope"]
        trajectory = preview["trajectory"]
        self.assertTrue(acceptance["software_bridge_passed"])
        self.assertFalse(acceptance["physical_hardware_passed"])
        self.assertFalse(scope["real_hardware_commanded"])
        self.assertFalse(scope["arm_lib_imported"])
        self.assertFalse(scope["gpu_started"])
        self.assertEqual(
            trajectory["official_api_call_count"],
            trajectory["sample_count"] * len(CONTROLLED_JOINT_NAMES),
        )
        for angle_range in trajectory["per_servo_ranges"].values():
            self.assertEqual(angle_range["minimum_angle_deg"], 85)
            self.assertEqual(angle_range["maximum_angle_deg"], 95)

    def test_preview_rejects_nonpositive_or_nonfinite_sample_rate(self) -> None:
        for invalid in (0.0, -1.0, math.inf, math.nan):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "positive and finite"):
                    build_preview(asset_contract=self.asset_contract, sample_hz=invalid)


if __name__ == "__main__":
    unittest.main()
