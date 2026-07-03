"""Schemas for devices."""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class DeviceBase(BaseModel):
    """Common device fields."""

    name: str = Field(..., min_length=1, max_length=100)
    room: str = Field(..., min_length=1, max_length=50)
    type: str = Field(..., pattern="^(fan|light)$")


class DeviceCreate(DeviceBase):
    """Schema used when creating a new device."""

    initial_status: str = Field(default="off", pattern="^(on|off)$")


class DeviceUpdate(BaseModel):
    """Schema used when updating a device status."""

    status: str = Field(..., pattern="^(on|off)$")


class DeviceRead(DeviceBase):
    """Schema used for returning device information."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    power_consumption: float
    last_changed: datetime


class RoomSummary(BaseModel):
    """Aggregated stats for a single room."""

    room: str
    total_devices: int
    active_devices: int
    total_power: float


class OverviewStats(BaseModel):
    """Aggregated stats across the whole office."""

    total_devices: int
    active_devices: int
    total_power: float
    rooms: List[RoomSummary]
    active_alerts: int