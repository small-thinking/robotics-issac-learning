"""Shared DOFBOT joint-command API and Yahboom ``Arm_Lib`` bridge.

The public command uses named joint positions in radians plus a duration in
milliseconds. Simulator and hardware backends implement the same protocol.
The documented Yahboom mapping is intentionally marked unverified until the
user's physical arm is calibrated; the real ``Arm_Lib`` backend fails closed
when given an unverified calibration.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

CONTROLLED_JOINT_NAMES = ("joint1", "joint2", "joint3", "joint4")
MAX_COMMAND_DURATION_MS = 30_000


class DofbotControlError(ValueError):
    """Raised when a shared DOFBOT command or backend result is unsafe."""


@dataclass(frozen=True)
class JointPositionCommand:
    """One complete arm-joint target in the shared simulator/hardware schema."""

    positions_rad: tuple[float, ...]
    duration_ms: int

    @classmethod
    def from_mapping(
        cls,
        positions_rad: Mapping[str, float],
        *,
        duration_ms: int,
    ) -> JointPositionCommand:
        if set(positions_rad) != set(CONTROLLED_JOINT_NAMES):
            raise DofbotControlError(
                "joint command must contain exactly "
                f"{', '.join(CONTROLLED_JOINT_NAMES)}"
            )
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
            raise DofbotControlError("duration_ms must be an integer")
        if duration_ms <= 0 or duration_ms > MAX_COMMAND_DURATION_MS:
            raise DofbotControlError(
                f"duration_ms must be in [1, {MAX_COMMAND_DURATION_MS}]"
            )

        ordered_positions: list[float] = []
        for name in CONTROLLED_JOINT_NAMES:
            raw_value = positions_rad[name]
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise DofbotControlError(f"position for {name} must be numeric")
            value = float(raw_value)
            if not math.isfinite(value):
                raise DofbotControlError(f"position for {name} must be finite")
            ordered_positions.append(value)

        return cls(
            positions_rad=tuple(ordered_positions),
            duration_ms=duration_ms,
        )

    def as_mapping(self) -> dict[str, float]:
        return dict(zip(CONTROLLED_JOINT_NAMES, self.positions_rad, strict=True))


class JointPositionBackend(Protocol):
    """Backend contract shared by Isaac and future physical DOFBOT control."""

    def command_joint_positions(self, command: JointPositionCommand) -> None:
        """Send a validated named-joint command."""

    def read_joint_positions(self) -> dict[str, float]:
        """Return the four controlled joint positions in radians."""


class DofbotArm:
    """Backend-neutral arm facade used by motion plans and later policies."""

    def __init__(self, backend: JointPositionBackend) -> None:
        self._backend = backend

    def move_joints(
        self,
        positions_rad: Mapping[str, float],
        *,
        duration_ms: int,
    ) -> JointPositionCommand:
        command = JointPositionCommand.from_mapping(
            positions_rad,
            duration_ms=duration_ms,
        )
        self._backend.command_joint_positions(command)
        return command

    def read_joint_positions(self) -> dict[str, float]:
        positions = self._backend.read_joint_positions()
        if set(positions) != set(CONTROLLED_JOINT_NAMES):
            raise DofbotControlError("backend returned the wrong joint set")
        for name, value in positions.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DofbotControlError(f"backend position for {name} must be numeric")
            if not math.isfinite(float(value)):
                raise DofbotControlError(f"backend position for {name} must be finite")
        return {name: float(positions[name]) for name in CONTROLLED_JOINT_NAMES}


@dataclass(frozen=True)
class YahboomJointCalibration:
    """Mapping from one simulated joint to one documented Yahboom servo."""

    joint_name: str
    servo_id: int
    center_deg: float
    direction: int
    minimum_deg: float
    maximum_deg: float


@dataclass(frozen=True)
class YahboomCalibration:
    """Complete mapping plus whether it was checked on the user's real arm."""

    joints: tuple[YahboomJointCalibration, ...]
    hardware_verified: bool
    provenance: str


DOCUMENTED_YAHBOOM_CALIBRATION = YahboomCalibration(
    joints=tuple(
        YahboomJointCalibration(
            joint_name=name,
            servo_id=index,
            center_deg=90.0,
            direction=1,
            minimum_deg=0.0,
            maximum_deg=180.0,
        )
        for index, name in enumerate(CONTROLLED_JOINT_NAMES, start=1)
    ),
    hardware_verified=False,
    provenance=(
        "Yahboom documents servo IDs 1-4 as joint1-joint4 and 90 degrees as "
        "the upright neutral pose; direction and per-device offsets still "
        "require physical calibration"
    ),
)


def _validated_yahboom_mappings(
    calibration: YahboomCalibration,
) -> dict[str, YahboomJointCalibration]:
    if not isinstance(calibration.hardware_verified, bool):
        raise DofbotControlError("hardware_verified must be a boolean")
    mappings = {joint.joint_name: joint for joint in calibration.joints}
    if set(mappings) != set(CONTROLLED_JOINT_NAMES):
        raise DofbotControlError("Yahboom calibration does not cover the controlled joints")
    if len(mappings) != len(calibration.joints):
        raise DofbotControlError("Yahboom calibration contains duplicate joint names")

    servo_ids: list[int] = []
    for expected_servo_id, joint_name in enumerate(CONTROLLED_JOINT_NAMES, start=1):
        mapping = mappings[joint_name]
        if isinstance(mapping.servo_id, bool) or not isinstance(mapping.servo_id, int):
            raise DofbotControlError(f"servo ID for {joint_name} must be an integer")
        if mapping.servo_id != expected_servo_id:
            raise DofbotControlError(
                f"{joint_name} must map to documented servo ID {expected_servo_id}"
            )
        if isinstance(mapping.direction, bool) or mapping.direction not in {-1, 1}:
            raise DofbotControlError(f"direction for {joint_name} must be -1 or 1")

        numeric_fields = {
            "center_deg": mapping.center_deg,
            "minimum_deg": mapping.minimum_deg,
            "maximum_deg": mapping.maximum_deg,
        }
        converted: dict[str, float] = {}
        for label, raw_value in numeric_fields.items():
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise DofbotControlError(f"{label} for {joint_name} must be numeric")
            value = float(raw_value)
            if not math.isfinite(value):
                raise DofbotControlError(f"{label} for {joint_name} must be finite")
            converted[label] = value
        if not (
            0.0
            <= converted["minimum_deg"]
            <= converted["center_deg"]
            <= converted["maximum_deg"]
            <= 180.0
        ):
            raise DofbotControlError(
                f"angle calibration for {joint_name} must stay within documented 0-180 degrees"
            )
        if converted["minimum_deg"] == converted["maximum_deg"]:
            raise DofbotControlError(f"angle range for {joint_name} must be nonzero")
        servo_ids.append(mapping.servo_id)

    if len(servo_ids) != len(set(servo_ids)):
        raise DofbotControlError("Yahboom calibration contains duplicate servo IDs")
    return mappings


@dataclass(frozen=True)
class YahboomServoWrite:
    """One exact official ``Arm_serial_servo_write`` call."""

    servo_id: int
    angle_deg: int
    duration_ms: int
    method: str = "Arm_serial_servo_write"

    def to_dict(self) -> dict[str, int | str]:
        return {
            "method": self.method,
            "servo_id": self.servo_id,
            "angle_deg": self.angle_deg,
            "duration_ms": self.duration_ms,
        }


def encode_yahboom_servo_writes(
    command: JointPositionCommand,
    *,
    calibration: YahboomCalibration = DOCUMENTED_YAHBOOM_CALIBRATION,
) -> tuple[YahboomServoWrite, ...]:
    """Translate named radians into official Yahboom single-servo calls."""

    mappings = _validated_yahboom_mappings(calibration)

    writes: list[YahboomServoWrite] = []
    for joint_name, position_rad in command.as_mapping().items():
        mapping = mappings[joint_name]
        angle_deg_float = (
            mapping.center_deg + mapping.direction * math.degrees(position_rad)
        )
        if (
            angle_deg_float < mapping.minimum_deg - 1.0e-9
            or angle_deg_float > mapping.maximum_deg + 1.0e-9
        ):
            raise DofbotControlError(
                f"mapped angle for {joint_name} is outside servo {mapping.servo_id} range"
            )
        angle_deg = int(round(angle_deg_float))
        if angle_deg < mapping.minimum_deg or angle_deg > mapping.maximum_deg:
            raise DofbotControlError(
                f"rounded angle for {joint_name} is outside servo {mapping.servo_id} range"
            )
        writes.append(
            YahboomServoWrite(
                servo_id=mapping.servo_id,
                angle_deg=angle_deg,
                duration_ms=command.duration_ms,
            )
        )
    return tuple(writes)


class YahboomArmDeviceProtocol(Protocol):
    """The official ``Arm_Lib.Arm_Device`` methods used by this bridge."""

    def Arm_serial_servo_write(self, servo_id: int, angle: int, time: int) -> Any:
        """Control one servo using Yahboom's documented API."""

    def Arm_serial_servo_write6(
        self,
        s1: int,
        s2: int,
        s3: int,
        s4: int,
        s5: int,
        s6: int,
        time: int,
    ) -> Any:
        """Control all six servos using Yahboom's documented API."""

    def Arm_serial_servo_read(self, servo_id: int) -> Any:
        """Read one servo angle using Yahboom's documented API."""


class YahboomDryRunBackend:
    """Record official API calls without importing ``Arm_Lib`` or touching hardware."""

    def __init__(
        self,
        *,
        calibration: YahboomCalibration = DOCUMENTED_YAHBOOM_CALIBRATION,
    ) -> None:
        self.calibration = calibration
        self.writes: list[YahboomServoWrite] = []

    def command_joint_positions(self, command: JointPositionCommand) -> None:
        self.writes.extend(
            encode_yahboom_servo_writes(
                command,
                calibration=self.calibration,
            )
        )

    def read_joint_positions(self) -> dict[str, float]:
        raise DofbotControlError("dry-run backend has no physical servo readings")


class YahboomArmLibBackend:
    """Physical backend that delegates to the official ``Arm_Lib`` methods."""

    def __init__(
        self,
        device: YahboomArmDeviceProtocol,
        *,
        calibration: YahboomCalibration,
    ) -> None:
        self._device = device
        self.calibration = calibration

    @classmethod
    def from_system(
        cls,
        *,
        calibration: YahboomCalibration,
    ) -> YahboomArmLibBackend:
        """Load the factory-installed ``Arm_Lib`` only on the robot computer."""

        try:
            module = importlib.import_module("Arm_Lib")
        except ModuleNotFoundError as error:
            raise DofbotControlError(
                "Arm_Lib is unavailable; run this backend only in the Yahboom "
                "Jetson/Raspberry Pi environment"
            ) from error
        arm_device = getattr(module, "Arm_Device", None)
        if arm_device is None:
            raise DofbotControlError("Arm_Lib does not expose Arm_Device")
        return cls(arm_device(), calibration=calibration)

    def _require_verified_calibration(self) -> None:
        if not self.calibration.hardware_verified:
            raise DofbotControlError(
                "real hardware command refused: Yahboom calibration is not verified"
            )

    def command_joint_positions(self, command: JointPositionCommand) -> None:
        self._require_verified_calibration()
        for write in encode_yahboom_servo_writes(
            command,
            calibration=self.calibration,
        ):
            self._device.Arm_serial_servo_write(
                write.servo_id,
                write.angle_deg,
                write.duration_ms,
            )

    def read_joint_positions(self) -> dict[str, float]:
        self._require_verified_calibration()
        mappings = _validated_yahboom_mappings(self.calibration)
        positions: dict[str, float] = {}
        for joint_name in CONTROLLED_JOINT_NAMES:
            mapping = mappings[joint_name]
            raw_angle = self._device.Arm_serial_servo_read(mapping.servo_id)
            if isinstance(raw_angle, bool) or not isinstance(raw_angle, (int, float)):
                raise DofbotControlError(
                    f"servo {mapping.servo_id} returned a nonnumeric angle"
                )
            angle_deg = float(raw_angle)
            if not math.isfinite(angle_deg) or angle_deg == -1.0:
                raise DofbotControlError(
                    f"servo {mapping.servo_id} position read failed"
                )
            if angle_deg < mapping.minimum_deg or angle_deg > mapping.maximum_deg:
                raise DofbotControlError(
                    f"servo {mapping.servo_id} returned an out-of-range angle"
                )
            position_deg = (angle_deg - mapping.center_deg) / mapping.direction
            positions[mapping.joint_name] = math.radians(position_deg)
        return positions
