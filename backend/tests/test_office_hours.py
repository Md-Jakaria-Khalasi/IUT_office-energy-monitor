"""Office-hours detection tests."""

from __future__ import annotations

from datetime import datetime

from app.services.office_hours import is_office_hours


def test_inside_office_hours():
    ts = datetime(2026, 7, 3, 10, 0, 0)  # Friday 10:00
    assert is_office_hours(ts) is True


def test_outside_office_hours():
    ts = datetime(2026, 7, 3, 6, 0, 0)  # Friday 06:00
    assert is_office_hours(ts) is False


def test_weekend():
    ts = datetime(2026, 7, 4, 10, 0, 0)  # Saturday 10:00
    assert is_office_hours(ts) is False