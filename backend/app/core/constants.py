"""Domain constants for the Office Energy Monitoring System."""

from enum import Enum


class RoomName(str, Enum):
    """Three rooms that exist in the office."""

    DRAWING_ROOM = "Drawing Room"
    WORK_ROOM_1 = "Work Room 1"
    WORK_ROOM_2 = "Work Room 2"


class DeviceType(str, Enum):
    """Device categories tracked by the system."""

    FAN = "fan"
    LIGHT = "light"


class DeviceStatus(str, Enum):
    """Operational status of a device."""

    ON = "on"
    OFF = "off"


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# Power ratings (watts) for device types
POWER_RATINGS = {
    DeviceType.FAN: 75,
    DeviceType.LIGHT: 20,
}

# Devices per room layout
DEVICES_PER_ROOM = {
    RoomName.DRAWING_ROOM: {"fan": 2, "light": 3},
    RoomName.WORK_ROOM_1: {"fan": 2, "light": 3},
    RoomName.WORK_ROOM_2: {"fan": 2, "light": 3},
}