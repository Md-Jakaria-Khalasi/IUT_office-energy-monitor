"""Detect whether the current time falls within office hours."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.config import get_settings


def get_office_hours_window() -> Tuple[int, int]:
    """Return (start_hour, end_hour) for the office day."""
    settings = get_settings()
    return settings.office_start_hour, settings.office_end_hour


def is_office_hours(now: Optional[datetime] = None) -> bool:
    """Return True if `now` (defaults to utcnow) is inside office hours."""
    now = now or datetime.now(timezone.utc)
    start, end = get_office_hours_window()
    # weekday() == 0 means Monday; Saturday/Sunday are non-working days
    if now.weekday() >= 5:
        return False
    return start <= now.hour < end