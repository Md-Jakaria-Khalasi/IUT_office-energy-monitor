"""Schemas for alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    """Schema for returning alerts."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    severity: str
    message: str
    room: Optional[str]
    device_id: Optional[int]
    created_at: datetime
    acknowledged: bool


class AlertCreate(BaseModel):
    """Schema for creating alerts."""

    severity: str = "info"
    message: str
    room: Optional[str] = None
    device_id: Optional[int] = None