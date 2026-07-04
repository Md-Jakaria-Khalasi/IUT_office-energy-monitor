"""Pydantic models mirroring the FastAPI backend schemas.

These models are the single source of truth inside the bot. Every command
decodes the backend response through one of these models so downstream code
never has to handle raw ``dict`` shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Device
# --------------------------------------------------------------------------- #


class Device(BaseModel):
    """A single controllable device (fan or light) in an office room."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    room: str
    type: Literal["fan", "light"]
    status: Literal["on", "off"]
    power_consumption: float = Field(ge=0, description="Current draw in watts.")
    last_changed: datetime


class DeviceUpdate(BaseModel):
    """Payload used when toggling a device via PATCH /devices/{id}."""

    status: Literal["on", "off"]


# --------------------------------------------------------------------------- #
# Rooms / Overview
# --------------------------------------------------------------------------- #


class RoomSummary(BaseModel):
    """Aggregated stats for a single room."""

    model_config = ConfigDict(extra="ignore")

    room: str
    total_devices: int
    active_devices: int
    total_power: float


class OverviewStats(BaseModel):
    """Aggregated stats across the whole office."""

    model_config = ConfigDict(extra="ignore")

    total_devices: int
    active_devices: int
    total_power: float
    rooms: List[RoomSummary]
    active_alerts: int


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #


class SeverityHistoryEntry(BaseModel):
    """One step in an alert's severity escalation timeline."""

    model_config = ConfigDict(extra="ignore")

    severity: str
    at: datetime
    reason: Optional[str] = None


class Alert(BaseModel):
    """A single alert produced by the backend alert engine.

    Mirrors ``backend.app.schemas.alert.AlertRead`` — every field the backend
    returns should be present here so command code can stay strongly typed.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    severity: Literal["info", "warning", "critical"]
    alert_type: str = "after_hours_device"
    status: str = "active"
    message: str

    room: Optional[str] = None
    device_id: Optional[int] = None
    involved_device_ids: List[int] = Field(default_factory=list)
    involved_rooms: List[str] = Field(default_factory=list)
    device_count: int = 0
    room_count: int = 0
    peak_power_w: Optional[float] = None

    created_at: datetime
    last_evaluated_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

    dismissed: bool = False
    dismissed_until: Optional[datetime] = None
    dismissed_by: Optional[str] = None

    energy_waste_kwh: float = 0.0
    estimated_cost_usd: float = 0.0

    severity_history: List[SeverityHistoryEntry] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)


class AlertSummary(BaseModel):
    """Aggregate counts returned by ``GET /alerts/summary``."""

    model_config = ConfigDict(extra="ignore")

    total_active: int
    critical: int
    warning: int
    info: int
    acknowledged: int
    estimated_waste_kwh_today: float = 0.0
    estimated_cost_usd_today: float = 0.0


# --------------------------------------------------------------------------- #
# Activity
# --------------------------------------------------------------------------- #


class Activity(BaseModel):
    """A single activity log entry."""

    model_config = ConfigDict(extra="ignore")

    id: int
    device_id: int
    device_name: str
    room: str
    action: str
    description: str
    created_at: datetime


__all__ = [
    "Activity",
    "Alert",
    "AlertSummary",
    "Device",
    "DeviceUpdate",
    "OverviewStats",
    "RoomSummary",
    "SeverityHistoryEntry",
]