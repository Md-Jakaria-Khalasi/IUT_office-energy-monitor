"""Device service unit tests."""

from __future__ import annotations

import pytest

from app.services.device_service import DeviceService


@pytest.mark.asyncio
async def test_seed_creates_default_devices(session):
    service = DeviceService(session)
    devices = await service.seed_default_devices()
    assert len(devices) == 15  # 3 rooms * (2 fans + 3 lights)


@pytest.mark.asyncio
async def test_set_status_updates_power(session):
    service = DeviceService(session)
    devices = await service.seed_default_devices()
    fan = next(d for d in devices if d.type == "fan")

    updated = await service.set_status(fan.id, "on")
    await session.commit()

    assert updated.status == "on"
    assert updated.power_consumption == 75


@pytest.mark.asyncio
async def test_set_status_invalid(session):
    service = DeviceService(session)
    devices = await service.seed_default_devices()
    fan = devices[0]
    with pytest.raises(ValueError):
        await service.set_status(fan.id, "invalid")