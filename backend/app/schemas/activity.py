"""Schemas for activity logs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityRead(BaseModel):
    """Schema for returning activity entries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    device_name: str
    room: str
    action: str
    description: str
    created_at: datetime