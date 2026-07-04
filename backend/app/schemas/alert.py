"""Schemas for alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import AlertSeverity, AlertStatus, AlertType


class AlertRead(BaseModel):
    """Schema for returning alerts."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    severity: str
    alert_type: str
    status: str
    message: str

    room: Optional[str] = None
    device_id: Optional[int] = None
    involved_device_ids: List[int] = Field(default_factory=list)
    involved_rooms: List[str] = Field(default_factory=list)
    device_count: int = 0
    room_count: int = 0
    peak_power_w: Optional[float] = None

    created_at: datetime
    last_evaluated_at: datetime
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

    dismissed: bool
    dismissed_until: Optional[datetime] = None
    dismissed_by: Optional[str] = None

    energy_waste_kwh: float = 0.0
    estimated_cost_usd: float = 0.0

    severity_history: List[Dict[str, Any]] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)


class AlertCreate(BaseModel):
    """Schema for creating alerts manually."""

    severity: str = AlertSeverity.INFO.value
    alert_type: str = AlertType.AFTER_HOURS_DEVICE.value
    message: str
    room: Optional[str] = None
    device_id: Optional[int] = None


class AlertAcknowledge(BaseModel):
    """Schema for acknowledging an alert."""

    acknowledged_by: Optional[str] = Field(default=None, max_length=120)


class AlertDismiss(BaseModel):
    """Schema for dismissing / snoozing an alert."""

    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    dismissed_by: Optional[str] = Field(default=None, max_length=120)


class AlertSummary(BaseModel):
    """Aggregate counts used by the dashboard."""

    total_active: int
    critical: int
    warning: int
    info: int
    acknowledged: int
    estimated_waste_kwh_today: float
    estimated_cost_usd_today: float


class AlertFilters(BaseModel):
    """Filters supported by GET /alerts."""

    severity: Optional[str] = None
    status: Optional[str] = None
    alert_type: Optional[str] = None
    room: Optional[str] = None
    device_id: Optional[int] = None
    only_active: bool = True
    limit: int = Field(default=50, ge=1, le=500)