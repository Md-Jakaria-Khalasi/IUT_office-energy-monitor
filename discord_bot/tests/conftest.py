"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest

# Make `app` importable when tests run from the discord_bot directory.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --- env shims so settings can be constructed without a real token ---------
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("BACKEND_URL", "http://testserver")
os.environ.setdefault("ALERT_CHANNEL_ID", "")
os.environ.setdefault("POLL_INTERVAL_SECONDS", "30")


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Reset the lru_cache on get_settings between tests."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---- sample data ----------------------------------------------------------


@pytest.fixture
def overview_payload() -> dict:
    return {
        "total_devices": 15,
        "active_devices": 7,
        "total_power": 312.5,
        "rooms": [
            {
                "room": "Drawing Room",
                "total_devices": 5,
                "active_devices": 3,
                "total_power": 145.0,
            },
            {
                "room": "Work Room 1",
                "total_devices": 5,
                "active_devices": 2,
                "total_power": 90.0,
            },
            {
                "room": "Work Room 2",
                "total_devices": 5,
                "active_devices": 2,
                "total_power": 77.5,
            },
        ],
        "active_alerts": 2,
    }


@pytest.fixture
def rooms_payload() -> list:
    return [
        {"room": "Drawing Room", "total_devices": 5, "active_devices": 3, "total_power": 145.0},
        {"room": "Work Room 1", "total_devices": 5, "active_devices": 2, "total_power": 90.0},
        {"room": "Work Room 2", "total_devices": 5, "active_devices": 2, "total_power": 77.5},
    ]


@pytest.fixture
def devices_payload() -> list:
    return [
        {
            "id": 1,
            "name": "Light 1",
            "room": "Drawing Room",
            "type": "light",
            "status": "on",
            "power_consumption": 20.0,
            "last_changed": "2024-01-01T00:00:00+00:00",
        },
        {
            "id": 2,
            "name": "Fan 1",
            "room": "Drawing Room",
            "type": "fan",
            "status": "off",
            "power_consumption": 0.0,
            "last_changed": "2024-01-01T00:00:00+00:00",
        },
    ]


@pytest.fixture
def alerts_payload() -> list:
    return [
        {
            "id": 1,
            "severity": "warning",
            "message": "Drawing Room is using more than 100W",
            "room": "Drawing Room",
            "device_id": None,
            "created_at": "2024-01-01T00:00:00+00:00",
            "acknowledged": False,
        },
        {
            "id": 2,
            "severity": "critical",
            "message": "Fan 2 failed health check",
            "room": "Work Room 2",
            "device_id": 12,
            "created_at": "2024-01-01T00:05:00+00:00",
            "acknowledged": False,
        },
    ]


@pytest.fixture
def activities_payload() -> list:
    return [
        {
            "id": 1,
            "device_id": 1,
            "device_name": "Light 1",
            "room": "Drawing Room",
            "action": "turned_on",
            "description": "Turned on by simulated motion.",
            "created_at": "2024-01-01T00:00:00+00:00",
        },
        {
            "id": 2,
            "device_id": 2,
            "device_name": "Fan 1",
            "room": "Drawing Room",
            "action": "turned_off",
            "description": "Auto-off after 30 minutes idle.",
            "created_at": "2024-01-01T00:10:00+00:00",
        },
    ]
