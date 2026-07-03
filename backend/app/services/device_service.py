"""Device-related business logic."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    DEVICES_PER_ROOM,
    POWER_RATINGS,
    DeviceStatus,
    DeviceType,
    RoomName,
)
from app.core.logging import logger
from app.models.activity import Activity
from app.models.device import Device


class DeviceService:
    """Handles device CRUD, aggregation, and state changes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------- queries --------
    async def list_devices(self, room: Optional[str] = None) -> List[Device]:
        stmt = select(Device).order_by(Device.room, Device.id)
        if room:
            stmt = stmt.where(Device.room == room)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_device(self, device_id: int) -> Optional[Device]:
        return await self.session.get(Device, device_id)

    async def total_power(self) -> float:
        devices = await self.list_devices()
        return sum(d.power_consumption for d in devices)

    async def active_count(self) -> int:
        devices = await self.list_devices()
        return sum(1 for d in devices if d.status == DeviceStatus.ON.value)

    # -------- mutations --------
    async def set_status(self, device_id: int, status: str) -> Device:
        device = await self.get_device(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        status = status.lower()
        if status not in {DeviceStatus.ON.value, DeviceStatus.OFF.value}:
            raise ValueError(f"Invalid status: {status}")

        device.status = status
        device.power_consumption = (
            POWER_RATINGS[DeviceType(device.type)] if status == DeviceStatus.ON.value else 0.0
        )
        device.last_changed = datetime.utcnow()
        await self.session.flush()

        await self._log_activity(
            device=device,
            action="turned_on" if status == DeviceStatus.ON.value else "turned_off",
            description=(
                f"{device.name} in {device.room} was turned "
                f"{'on' if status == DeviceStatus.ON.value else 'off'}"
            ),
        )
        logger.info(f"Device {device.id} status -> {status}")
        return device

    async def _log_activity(self, device: Device, action: str, description: str) -> None:
        entry = Activity(
            device_id=device.id,
            device_name=device.name,
            room=device.room,
            action=action,
            description=description,
        )
        self.session.add(entry)
        await self.session.flush()

    # -------- seeding --------
    async def seed_default_devices(self) -> List[Device]:
        """Seed the three rooms with 2 fans and 3 lights each if empty."""
        existing = await self.list_devices()
        if existing:
            return existing

        seeded: List[Device] = []
        for room in RoomName:
            layout = DEVICES_PER_ROOM[room]
            for n in range(1, layout["fan"] + 1):
                seeded.append(
                    Device(
                        name=f"Fan {n}",
                        room=room.value,
                        type=DeviceType.FAN.value,
                        status=DeviceStatus.OFF.value,
                        power_consumption=0.0,
                    )
                )
            for n in range(1, layout["light"] + 1):
                seeded.append(
                    Device(
                        name=f"Light {n}",
                        room=room.value,
                        type=DeviceType.LIGHT.value,
                        status=DeviceStatus.OFF.value,
                        power_consumption=0.0,
                    )
                )
        self.session.add_all(seeded)
        await self.session.commit()
        logger.info(f"Seeded {len(seeded)} default devices.")
        return seeded