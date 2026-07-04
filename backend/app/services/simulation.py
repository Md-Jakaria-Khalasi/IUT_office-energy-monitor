"""Device simulation engine.

Ticks the device state machine, persists activity rows, evaluates alerts and
broadcasts every state change to live websocket subscribers.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import (
    CRITICAL_POWER_DWELL_SECONDS,
    CRITICAL_POWER_THRESHOLD_W,
    POWER_RATINGS,
    DeviceStatus,
    DeviceType,
)
from app.core.logging import logger
from app.models.activity import Activity
from app.models.device import Device
from app.services.alert_service import AlertService
from app.services.device_service import DeviceService
from app.services.office_hours import is_office_hours
from app.websocket.manager import ws_manager


class SimulationEngine:
    """Periodically updates device states with realistic behaviour."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.device_service = DeviceService(session)
        self.alert_service = AlertService(session)
        # State carried across ticks so we can measure dwell on high power.
        self._first_critical_power_seen_at: Optional[datetime] = None

    # ------------------------------------------------------------------ entry
    async def tick(self) -> Dict:
        """Run one simulation step and return aggregate stats."""
        devices = await self.device_service.list_devices()
        if not devices:
            self._reset_critical_power_dwell()
            stats = {
                "changed": [],
                "total_power": 0.0,
                "active": 0,
                "alerts_created": 0,
                "alerts_resolved": 0,
            }
            await ws_manager.broadcast_simulation(stats)
            return stats

        office_hours = is_office_hours()

        # Toggle some devices with realistic probability.
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
                device.last_changed = datetime.now(timezone.utc)
                self.session.add(
                    Activity(
                        device_id=device.id,
                        device_name=device.name,
                        room=device.room,
                        action=(
                            "turned_on"
                            if new_status == DeviceStatus.ON.value
                            else "turned_off"
                        ),
                        description=(
                            f"{device.name} in {device.room} simulated "
                            f"{'on' if new_status == DeviceStatus.ON.value else 'off'}"
                        ),
                    )
                )
                changed.append(device.id)

        await self.session.flush()

        total_power = sum(d.power_consumption for d in devices)
        active = sum(1 for d in devices if d.status == DeviceStatus.ON.value)
        office_consumption_kwh = await self._office_consumption_today(devices)

        # Evaluate alerts via the new engine.
        first_seen = self._update_critical_power_dwell(total_power)
        evaluation = await self.alert_service.evaluate_simulation_tick(
            devices=devices,
            total_power=total_power,
            office_hours=office_hours,
            office_consumption_kwh=office_consumption_kwh,
            first_critical_power_seen_at=first_seen,
        )

        await self.session.flush()

        # Build broadcast payloads BEFORE committing so we never leak state
        # to websocket clients if the commit fails.
        device_payloads: List[Dict] = [
            {
                "id": device.id,
                "name": device.name,
                "room": device.room,
                "type": device.type,
                "status": device.status,
                "power_consumption": device.power_consumption,
                "last_changed": (
                    device.last_changed.isoformat()
                    if device.last_changed
                    else None
                ),
            }
            for device in devices
            if device.id in changed
        ]
        alert_created_payloads = [_alert_to_payload(a) for a in evaluation.alerts_created]
        alert_updated_payloads = [_alert_to_payload(a) for a in evaluation.alerts_updated]
        alert_resolved_payloads = [_alert_to_payload(a) for a in evaluation.alerts_resolved]

        stats = {
            "changed": changed,
            "total_power": total_power,
            "active": active,
            "alerts_created": len(evaluation.alerts_created),
            "alerts_updated": len(evaluation.alerts_updated),
            "alerts_resolved": len(evaluation.alerts_resolved),
            "office_consumption_kwh": round(office_consumption_kwh, 4),
            "office_hours": office_hours,
            "first_critical_power_seen_at": (
                first_seen.isoformat() if first_seen else None
            ),
        }

        # Commit first — only fan the state out to clients once persistence is
        # durable. This keeps "no duplicates, no stale rows" guarantees intact.
        await self.session.commit()

        for payload in device_payloads:
            await ws_manager.broadcast_device_update(payload)
        for payload in alert_created_payloads:
            await ws_manager.broadcast_alert_created(payload)
        for payload in alert_updated_payloads:
            await ws_manager.broadcast_alert_updated(payload)
        for payload in alert_resolved_payloads:
            await ws_manager.broadcast_alert_resolved(payload)
        await ws_manager.broadcast_simulation(stats)
        logger.debug(
            "Simulation tick: %d changes, total_power=%.1fW, active=%d, "
            "alerts c=%d u=%d r=%d",
            len(changed), total_power, active,
            stats["alerts_created"], stats["alerts_updated"], stats["alerts_resolved"],
        )
        return stats

    # ----------------------------------------------------------- alert helpers
    def _update_critical_power_dwell(
        self, total_power: float,
    ) -> Optional[datetime]:
        """Track when the office first crossed the critical-power threshold.

        Returns the timestamp at which the current high-power streak started,
        or ``None`` when the office is currently below the threshold.
        """
        threshold = float(
            get_settings().critical_power_threshold_w
            or CRITICAL_POWER_THRESHOLD_W
        )
        if total_power >= threshold:
            if self._first_critical_power_seen_at is None:
                self._first_critical_power_seen_at = datetime.now(timezone.utc)
        else:
            self._first_critical_power_seen_at = None
        return self._first_critical_power_seen_at

    def _reset_critical_power_dwell(self) -> None:
        self._first_critical_power_seen_at = None

    async def _office_consumption_today(
        self, devices: List[Device],
    ) -> float:
        """Estimate kWh consumed since midnight.

        Strategy: sum ``power_consumption * dt`` using the device's
        ``last_changed`` time and current ``power_consumption``. The estimate is
        coarse but sufficient for the OFFICE_CONSUMPTION alert threshold.
        """
        now = datetime.now(timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        total_kwh = 0.0
        for d in devices:
            if d.power_consumption <= 0:
                continue
            start = d.last_changed or midnight
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if start < midnight:
                start = midnight
            dt_hours = max(0.0, (now - start).total_seconds() / 3600.0)
            total_kwh += (d.power_consumption * dt_hours) / 1000.0
        return round(total_kwh, 4)

    # ------------------------------------------------------------------ helpers
    def _probability(self, device: Device, office_hours: bool) -> float:
        """Probability a given device toggles this tick."""
        base = 0.05 if office_hours else 0.02
        if device.type == DeviceType.LIGHT.value:
            return base * (1.5 if office_hours else 0.5)
        return base


def _alert_to_payload(alert) -> Dict:
    """Convert an ORM ``Alert`` instance into a JSON-serializable dict."""
    from app.schemas.alert import AlertRead

    payload = AlertRead.model_validate(alert).model_dump(mode="json")
    history = []
    for entry in payload.get("severity_history") or []:
        if isinstance(entry, dict):
            history.append(
                {
                    k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in entry.items()
                }
            )
    payload["severity_history"] = history
    return payload