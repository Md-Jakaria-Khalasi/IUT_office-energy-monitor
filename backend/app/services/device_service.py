"""Device-related business logic."""

from __future__ import annotations

from datetime import datetime, timezone
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
        """Toggle a single device to ``status``.

        Returns the device regardless of whether it was already in that state,
        so callers can decide to skip broadcasting on no-op transitions.
        """
        device, _ = await self.set_status_with_change(device_id, status)
        return device

    async def set_status_with_change(
        self, device_id: int, status: str
    ) -> tuple[Device, bool]:
        """Toggle a device and return ``(device, changed)``.

        ``changed`` is ``False`` when the device was already in ``status``.
        Callers should use this when they need to broadcast only real deltas.
        """
        device = await self.get_device(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        status = status.lower()
        if status not in {DeviceStatus.ON.value, DeviceStatus.OFF.value}:
            raise ValueError(f"Invalid status: {status}")

        changed = device.status != status
        device.status = status
        device.power_consumption = (
            POWER_RATINGS[DeviceType(device.type)] if status == DeviceStatus.ON.value else 0.0
        )
        device.last_changed = datetime.now(timezone.utc)
        await self.session.flush()

        if changed:
            await self._log_activity(
                device=device,
                action="turned_on" if status == DeviceStatus.ON.value else "turned_off",
                description=(
                    f"{device.name} in {device.room} was turned "
                    f"{'on' if status == DeviceStatus.ON.value else 'off'}"
                ),
            )
        logger.info(f"Device {device.id} status -> {status} (changed={changed})")
        return device, changed

    async def was_status_changed(self, device: Device, new_status: str) -> bool:
        """Return True iff ``device.status`` differs from ``new_status``."""
        return device.status != new_status.lower()

    async def set_room_status(self, room: str, status: str) -> List[Device]:
        """Flip every device in ``room`` to ``status``.

        Returns the list of devices whose status actually changed. Devices
        already in the target state are skipped silently (no activity row, no
        broadcast payload) so the WebSocket layer only ever fires for *real*
        deltas.
        """
        status = status.lower()
        if status not in {DeviceStatus.ON.value, DeviceStatus.OFF.value}:
            raise ValueError(f"Invalid status: {status}")

        stmt = select(Device).where(Device.room == room).order_by(Device.id)
        devices = list((await self.session.execute(stmt)).scalars().all())
        changed: List[Device] = []
        for device in devices:
            if device.status == status:
                continue
            device.status = status
            device.power_consumption = (
                POWER_RATINGS[DeviceType(device.type)] if status == DeviceStatus.ON.value else 0.0
            )
            device.last_changed = datetime.now(timezone.utc)
            await self._log_activity(
                device=device,
                action="turned_on" if status == DeviceStatus.ON.value else "turned_off",
                description=(
                    f"{device.name} in {device.room} was turned "
                    f"{'on' if status == DeviceStatus.ON.value else 'off'} (bulk)"
                ),
            )
            changed.append(device)
        await self.session.flush()
        logger.info(
            "Room %s bulk set to %s — %d/%d devices changed",
            room, status, len(changed), len(devices),
        )
        return changed

    def device_to_payload(self, device: Device) -> dict:
        """Return a JSON-safe payload for a device (used by broadcast layer)."""
        return {
            "id": device.id,
            "name": device.name,
            "room": device.room,
            "type": device.type,
            "status": device.status,
            "power_consumption": device.power_consumption,
            "last_changed": (
                device.last_changed.isoformat() if device.last_changed else None
            ),
        }

    async def room_summary(self, room: str) -> dict:
        """Return aggregated totals for a single room (devices + power)."""
        stmt = select(Device).where(Device.room == room)
        devices = list((await self.session.execute(stmt)).scalars().all())
        active = sum(1 for d in devices if d.status == DeviceStatus.ON.value)
        total_power = sum(d.power_consumption for d in devices)
        return {
            "room": room,
            "total_devices": len(devices),
            "active_devices": active,
            "total_power": total_power,
        }

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