"""Device simulation engine."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Dict, List

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
from app.services.alert_service import AlertService
from app.services.device_service import DeviceService
from app.services.office_hours import is_office_hours


class SimulationEngine:
    """Periodically updates device states with realistic behaviour."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.device_service = DeviceService(session)
        self.alert_service = AlertService(session)

    async def tick(self) -> Dict:
        """Run one simulation step and return aggregate stats."""
        devices = await self.device_service.list_devices()
        if not devices:
            return {"changed": [], "total_power": 0.0, "active": 0}

        office_hours = is_office_hours()
        changed: List[int] = []
        for device in devices:
            if random.random() < self._probability(device, office_hours):
                new_status = (
                    DeviceStatus.OFF.value
                    if device.status == DeviceStatus.ON.value
                    else DeviceStatus.ON.value
                )
                device.status = new_status
                device.power_consumption = (
                    POWER_RATINGS[DeviceType(device.type)]
                    if new_status == DeviceStatus.ON.value
                    else 0.0
                )
                device.last_changed = datetime.utcnow()
                self.session.add(
                    Activity(
                        device_id=device.id,
                        device_name=device.name,
                        room=device.room,
                        action="turned_on" if new_status == DeviceStatus.ON.value else "turned_off",
                        description=(
                            f"{device.name} in {device.room} simulated "
                            f"{'on' if new_status == DeviceStatus.ON.value else 'off'}"
                        ),
                    )
                )
                changed.append(device.id)

        await self.session.commit()

        total_power = sum(d.power_consumption for d in devices)
        active = sum(1 for d in devices if d.status == DeviceStatus.ON.value)

        await self._evaluate_alerts(total_power=total_power, office_hours=office_hours)
        await self.session.commit()

        logger.debug(
            f"Simulation tick: {len(changed)} changes, "
            f"total_power={total_power:.1f}W, active={active}"
        )
        return {"changed": changed, "total_power": total_power, "active": active}

    def _probability(self, device: Device, office_hours: bool) -> float:
        """Probability a given device toggles this tick."""
        # Lower probability during off-hours to mimic quiet office
        base = 0.05 if office_hours else 0.02
        if device.type == DeviceType.LIGHT.value:
            return base * (1.5 if office_hours else 0.5)
        return base

    async def _evaluate_alerts(self, total_power: float, office_hours: bool) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        if total_power > settings.alert_watt_threshold:
            await self.alert_service.create_alert(
                message=f"High power usage detected: {total_power:.0f}W "
                f"(threshold {settings.alert_watt_threshold}W)",
                severity="warning",
            )
        if (not office_hours) and settings.alert_off_hours_active:
            from sqlalchemy import select
            stmt = select(Device).where(Device.status == DeviceStatus.ON.value)
            on_devices = list((await self.session.execute(stmt)).scalars())
            if on_devices:
                for d in on_devices:
                    await self.alert_service.create_alert(
                        message=f"{d.name} in {d.room} is still ON after office hours",
                        severity="info",
                        room=d.room,
                        device_id=d.id,
                    )