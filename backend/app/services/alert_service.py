"""Alert engine and persistence.

This module owns the alert lifecycle:

* four distinct alert types (after-hours device, room continuous, critical
  power draw, office-wide consumption),
* severity escalation based on age (INFO -> WARNING -> CRITICAL),
* acknowledgement and dismissal semantics,
* energy waste and cost estimation,
* aggregate summary helpers used by the dashboard and Discord bot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import (
    ALERT_CRITICAL_AFTER_MINUTES,
    ALERT_MAX_AFTER_MINUTES,
    ALERT_WARNING_AFTER_MINUTES,
    AFTER_HOURS_DEVICE_GRACE_MINUTES,
    CRITICAL_POWER_DWELL_SECONDS,
    CRITICAL_POWER_THRESHOLD_W,
    DEFAULT_COST_PER_KWH_USD,
    OFFICE_CONSUMPTION_THRESHOLD_KWH,
    REMINDER_INTERVAL_MINUTES,
    ROOM_CONTINUOUS_THRESHOLD_MINUTES,
    AlertSeverity,
    AlertStatus,
    AlertType,
    DeviceStatus,
)
from app.core.logging import logger
from app.models.alert import Alert
from app.models.device import Device


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class AlertEvaluation:
    """Outcome of evaluating a single simulation tick."""

    alerts_created: List[Alert] = field(default_factory=list)
    alerts_updated: List[Alert] = field(default_factory=list)
    alerts_resolved: List[Alert] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(ts: datetime | None) -> datetime | None:
    """Coerce a possibly-naive datetime into a UTC-aware one.

    SQLite strips timezone information on storage, so any ``DateTime`` column
    read back from the live DB comes out naive even when the model default
    writes tz-aware values. Comparing naive to aware raises
    ``TypeError: can't compare offset-naive and offset-aware datetimes``,
    so every DB-read timestamp must be normalised before arithmetic.
    """
    if ts is None:
        return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def _minutes_since(ts: datetime) -> float:
    return max(0.0, (_now() - _as_utc(ts)).total_seconds() / 60.0)


def _severity_for_age(age_minutes: float) -> str:
    """Pick severity from alert age (in minutes)."""
    if age_minutes >= ALERT_CRITICAL_AFTER_MINUTES:
        return AlertSeverity.CRITICAL.value
    if age_minutes >= ALERT_WARNING_AFTER_MINUTES:
        return AlertSeverity.WARNING.value
    return AlertSeverity.INFO.value


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AlertService:
    """Manages alerts: creation, escalation, dismissal, listing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    # ------------------------------------------------------------------ create
    async def create_alert(
        self,
        message: str,
        severity: str = AlertSeverity.INFO.value,
        room: Optional[str] = None,
        device_id: Optional[int] = None,
        alert_type: str = AlertType.AFTER_HOURS_DEVICE.value,
        involved_device_ids: Optional[Sequence[int]] = None,
        involved_rooms: Optional[Sequence[str]] = None,
        energy_waste_kwh: float = 0.0,
        estimated_cost_usd: Optional[float] = None,
        peak_power_w: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
        dedupe_seconds: int = 60,
    ) -> Optional[Alert]:
        """Create an alert unless an identical one was created recently."""
        cutoff = _now() - timedelta(seconds=dedupe_seconds)
        stmt = (
            select(Alert)
            .where(Alert.alert_type == alert_type)
            .where(Alert.room == room)
            .where(Alert.device_id == device_id)
            .where(Alert.status.in_([
                AlertStatus.ACTIVE.value,
                AlertStatus.ACKNOWLEDGED.value,
                AlertStatus.DISMISSED.value,
            ]))
            .where(Alert.created_at >= cutoff)
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing:
            return None

        ids = list(
            involved_device_ids
            or ([] if device_id is None else [device_id])
        )
        rooms = list(involved_rooms or ([] if room is None else [room]))

        cost_per_kwh = float(
            (extra or {}).get("cost_per_kwh_usd", DEFAULT_COST_PER_KWH_USD)
        )
        if estimated_cost_usd is None:
            estimated_cost_usd = energy_waste_kwh * cost_per_kwh

        alert = Alert(
            severity=severity,
            alert_type=alert_type,
            status=AlertStatus.ACTIVE.value,
            message=message,
            room=room,
            device_id=device_id,
            involved_device_ids=ids,
            involved_rooms=rooms,
            device_count=len(ids),
            room_count=len(rooms),
            peak_power_w=peak_power_w,
            energy_waste_kwh=round(energy_waste_kwh, 4),
            estimated_cost_usd=round(estimated_cost_usd, 4),
            severity_history=[{
                "severity": severity,
                "at": _now().isoformat(),
                "reason": "created",
            }],
            extra=extra or {},
            created_at=_now(),
            last_evaluated_at=_now(),
        )
        self.session.add(alert)
        await self.session.flush()
        logger.info(
            "alert.created id=%s type=%s severity=%s room=%s",
            alert.id, alert_type, severity, room,
        )
        return alert

    # ------------------------------------------------------------------ update
    async def update_last_evaluated(self, alert: Alert) -> None:
        alert.last_evaluated_at = _now()
        await self.session.flush()

    async def escalate(
        self,
        alert: Alert,
        new_severity: str,
        reason: str = "age",
    ) -> Alert:
        if new_severity not in {s.value for s in AlertSeverity}:
            return alert
        if new_severity == alert.severity:
            return alert
        old = alert.severity
        alert.severity = new_severity
        alert.escalated_at = _now()
        if alert.status == AlertStatus.DISMISSED.value:
            # never re-activate a dismissed alert just because of age
            pass
        else:
            alert.status = AlertStatus.ACTIVE.value
        history = list(alert.severity_history or [])
        history.append({
            "severity": new_severity,
            "at": _now().isoformat(),
            "reason": reason,
            "previous": old,
        })
        alert.severity_history = history
        await self.session.flush()
        logger.info(
            "alert.escalated id=%s %s -> %s (%s)",
            alert.id, old, new_severity, reason,
        )
        return alert

    async def acknowledge(
        self,
        alert_id: int,
        acknowledged_by: Optional[str] = None,
    ) -> Optional[Alert]:
        alert = await self.session.get(Alert, alert_id)
        if not alert:
            return None
        if alert.status == AlertStatus.RESOLVED.value:
            return alert
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = _now()
        alert.status = AlertStatus.ACKNOWLEDGED.value
        await self.session.flush()
        return alert

    async def dismiss(
        self,
        alert_id: int,
        duration_minutes: Optional[int] = None,
        dismissed_by: Optional[str] = None,
    ) -> Optional[Alert]:
        alert = await self.session.get(Alert, alert_id)
        if not alert:
            return None
        minutes = (
            duration_minutes
            or self.settings.default_dismiss_duration_minutes
        )
        alert.dismissed = True
        alert.dismissed_until = _now() + timedelta(minutes=minutes)
        alert.dismissed_by = dismissed_by
        alert.status = AlertStatus.DISMISSED.value
        await self.session.flush()
        return alert

    async def resolve(self, alert: Alert) -> Alert:
        if alert.status == AlertStatus.RESOLVED.value:
            return alert
        alert.status = AlertStatus.RESOLVED.value
        alert.resolved_at = _now()
        alert.dismissed = False
        alert.dismissed_until = None
        await self.session.flush()
        return alert

    # ------------------------------------------------------------------- read
    async def list_alerts(
        self,
        limit: int = 50,
        only_active: bool = True,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        alert_type: Optional[str] = None,
        room: Optional[str] = None,
        device_id: Optional[int] = None,
    ) -> List[Alert]:
        stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        if only_active:
            stmt = stmt.where(
                Alert.status.in_([
                    AlertStatus.ACTIVE.value,
                    AlertStatus.ACKNOWLEDGED.value,
                    AlertStatus.DISMISSED.value,
                ])
            )
        if severity:
            stmt = stmt.where(Alert.severity == severity)
        if status:
            stmt = stmt.where(Alert.status == status)
        if alert_type:
            stmt = stmt.where(Alert.alert_type == alert_type)
        if room:
            stmt = stmt.where(
                (Alert.room == room) | (Alert.involved_rooms.contains([room]))
            )
        if device_id is not None:
            stmt = stmt.where(
                (Alert.device_id == device_id)
                | (Alert.involved_device_ids.contains([device_id]))
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_alert(self, alert_id: int) -> Optional[Alert]:
        return await self.session.get(Alert, alert_id)

    async def active_count(self) -> int:
        stmt = select(func.count(Alert.id)).where(
            Alert.status.in_([
                AlertStatus.ACTIVE.value,
                AlertStatus.ACKNOWLEDGED.value,
                AlertStatus.DISMISSED.value,
            ])
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def summary(self) -> Dict[str, Any]:
        alerts = await self.list_alerts(limit=500, only_active=True)
        critical = sum(
            1 for a in alerts if a.severity == AlertSeverity.CRITICAL.value
        )
        warning = sum(
            1 for a in alerts if a.severity == AlertSeverity.WARNING.value
        )
        info = sum(
            1 for a in alerts if a.severity == AlertSeverity.INFO.value
        )
        acknowledged = sum(1 for a in alerts if a.acknowledged)
        waste = round(sum(a.energy_waste_kwh for a in alerts), 4)
        cost = round(sum(a.estimated_cost_usd for a in alerts), 4)
        return {
            "total_active": len(alerts),
            "critical": critical,
            "warning": warning,
            "info": info,
            "acknowledged": acknowledged,
            "estimated_waste_kwh_today": waste,
            "estimated_cost_usd_today": cost,
        }

    async def due_for_reminder(
        self, now: Optional[datetime] = None
    ) -> List[Alert]:
        """Return active alerts that have not been reminded within the window."""
        now = now or _now()
        stmt = select(Alert).where(
            Alert.status.in_([
                AlertStatus.ACTIVE.value,
                AlertStatus.ACKNOWLEDGED.value,
            ])
        )
        rows = list((await self.session.execute(stmt)).scalars())
        interval = timedelta(minutes=REMINDER_INTERVAL_MINUTES)
        out: List[Alert] = []
        for a in rows:
            last = a.last_evaluated_at or a.created_at
            if (now - last) >= interval and a.severity in {
                AlertSeverity.WARNING.value,
                AlertSeverity.CRITICAL.value,
            }:
                out.append(a)
        return out

    # ----------------------------------------------------------- main evaluate
    async def evaluate_simulation_tick(
        self,
        devices: Sequence[Device],
        total_power: float,
        office_hours: bool,
        office_consumption_kwh: float,
        first_critical_power_seen_at: Optional[datetime] = None,
    ) -> AlertEvaluation:
        """Run every alert rule for the current tick.

        ``first_critical_power_seen_at`` is the timestamp at which the office
        first crossed :data:`CRITICAL_POWER_THRESHOLD_W` on the current streak;
        if more than :data:`CRITICAL_POWER_DWELL_SECONDS` have passed since
        then, the CRITICAL_POWER alert is raised.
        """
        outcome = AlertEvaluation()
        await self._auto_resolve(devices, office_hours, outcome)

        await self._check_after_hours(devices, office_hours, outcome)
        await self._check_room_continuous(devices, outcome)
        await self._check_critical_power(
            total_power,
            first_critical_power_seen_at,
            outcome,
        )
        await self._check_office_consumption(
            office_consumption_kwh, outcome,
        )

        # Always escalate age-based
        await self._escalate_by_age(outcome)
        return outcome

    # --------------------------------------------------------- internal rules
    async def _auto_resolve(
        self,
        devices: Sequence[Device],
        office_hours: bool,
        outcome: AlertEvaluation,
    ) -> None:
        """Mark active alerts as RESOLVED when the underlying condition clears."""
        on_devices = [d for d in devices if d.status == DeviceStatus.ON.value]
        on_ids = {d.id for d in on_devices}

        stmt = select(Alert).where(
            Alert.status.in_([
                AlertStatus.ACTIVE.value,
                AlertStatus.ACKNOWLEDGED.value,
                AlertStatus.DISMISSED.value,
            ])
        )
        active = list((await self.session.execute(stmt)).scalars())

        for alert in active:
            should_resolve = False
            if alert.alert_type == AlertType.AFTER_HOURS_DEVICE.value:
                if office_hours or alert.device_id not in on_ids:
                    should_resolve = True
            elif alert.alert_type == AlertType.ROOM_CONTINUOUS.value:
                if not any(
                    did in on_ids for did in (alert.involved_device_ids or [])
                ):
                    should_resolve = True
            elif alert.alert_type == AlertType.CRITICAL_POWER.value:
                if not office_hours and not on_devices:
                    should_resolve = True
            # OFFICE_CONSUMPTION is reset at midnight by the daily job, so we
            # never auto-resolve it here.
            if should_resolve:
                await self.resolve(alert)
                outcome.alerts_resolved.append(alert)

    async def _check_after_hours(
        self,
        devices: Sequence[Device],
        office_hours: bool,
        outcome: AlertEvaluation,
    ) -> None:
        if office_hours or not self.settings.alert_off_hours_active:
            return
        cutoff = _now() - timedelta(minutes=AFTER_HOURS_DEVICE_GRACE_MINUTES)
        for d in devices:
            if d.status != DeviceStatus.ON.value:
                continue
            last_changed = _as_utc(d.last_changed)
            if last_changed is None or last_changed > cutoff:
                continue
            existing = await self._existing_active(
                AlertType.AFTER_HOURS_DEVICE.value,
                room=d.room,
                device_id=d.id,
            )
            if existing:
                continue
            minutes_on = max(
                0,
                int((_now() - last_changed).total_seconds() // 60),
            )
            hours = max(0.0, (_now() - last_changed).total_seconds() / 3600.0)
            waste = (d.power_consumption or 0.0) * hours / 1000.0
            message = (
                f"🔌 {d.name} in {d.room} has been ON after office hours "
                f"for {minutes_on} min"
            )
            alert = await self.create_alert(
                message=message,
                severity=AlertSeverity.INFO.value,
                room=d.room,
                device_id=d.id,
                alert_type=AlertType.AFTER_HOURS_DEVICE.value,
                involved_device_ids=[d.id],
                involved_rooms=[d.room],
                energy_waste_kwh=waste,
                peak_power_w=d.power_consumption,
            )
            if alert:
                outcome.alerts_created.append(alert)

    async def _check_room_continuous(
        self,
        devices: Sequence[Device],
        outcome: AlertEvaluation,
    ) -> None:
        threshold = timedelta(minutes=ROOM_CONTINUOUS_THRESHOLD_MINUTES)
        by_room: Dict[str, List[Device]] = {}
        for d in devices:
            if d.status != DeviceStatus.ON.value or d.last_changed is None:
                continue
            last_changed = _as_utc(d.last_changed)
            if last_changed is None or (_now() - last_changed) < threshold:
                continue
            by_room.setdefault(d.room, []).append(d)

        for room, dev_list in by_room.items():
            ids = [d.id for d in dev_list]
            existing = await self._existing_active(
                AlertType.ROOM_CONTINUOUS.value,
                room=room,
                device_id=None,
            )
            if existing:
                continue
            total_power = sum(d.power_consumption or 0.0 for d in dev_list)
            oldest = min(_as_utc(d.last_changed) for d in dev_list)
            hours = (_now() - oldest).total_seconds() / 3600.0
            waste = total_power * hours / 1000.0
            names = ", ".join(sorted({d.name for d in dev_list}))
            message = (
                f"⏱️ {room} devices have been ON continuously for "
                f">{ROOM_CONTINUOUS_THRESHOLD_MINUTES} min ({names})"
            )
            alert = await self.create_alert(
                message=message,
                severity=AlertSeverity.WARNING.value,
                room=room,
                alert_type=AlertType.ROOM_CONTINUOUS.value,
                involved_device_ids=ids,
                involved_rooms=[room],
                energy_waste_kwh=waste,
                peak_power_w=total_power,
            )
            if alert:
                outcome.alerts_created.append(alert)

    async def _check_critical_power(
        self,
        total_power: float,
        first_seen_at: Optional[datetime],
        outcome: AlertEvaluation,
    ) -> None:
        threshold = float(
            self.settings.critical_power_threshold_w or CRITICAL_POWER_THRESHOLD_W
        )
        if total_power < threshold or first_seen_at is None:
            return
        if (_now() - first_seen_at).total_seconds() < CRITICAL_POWER_DWELL_SECONDS:
            return

        existing = await self._existing_active(
            AlertType.CRITICAL_POWER.value, room=None, device_id=None,
        )
        if existing:
            return
        hours = max(
            0.0,
            (_now() - first_seen_at).total_seconds() / 3600.0,
        )
        waste = (total_power * hours) / 1000.0
        message = (
            f"⚡ Office drawing {total_power:.0f}W — exceeds {threshold:.0f}W "
            f"sustained for {CRITICAL_POWER_DWELL_SECONDS}s"
        )
        alert = await self.create_alert(
            message=message,
            severity=AlertSeverity.CRITICAL.value,
            alert_type=AlertType.CRITICAL_POWER.value,
            energy_waste_kwh=waste,
            peak_power_w=total_power,
        )
        if alert:
            outcome.alerts_created.append(alert)

    async def _check_office_consumption(
        self,
        consumption_kwh: float,
        outcome: AlertEvaluation,
    ) -> None:
        threshold = float(
            self.settings.office_consumption_threshold_kwh
            or OFFICE_CONSUMPTION_THRESHOLD_KWH
        )
        if consumption_kwh < threshold:
            return
        existing = await self._existing_active(
            AlertType.OFFICE_CONSUMPTION.value, room=None, device_id=None,
        )
        if existing:
            return
        cost = consumption_kwh * float(
            self.settings.cost_per_kwh_usd or DEFAULT_COST_PER_KWH_USD
        )
        message = (
            f"📊 Office has consumed {consumption_kwh:.2f} kWh today "
            f"(threshold {threshold:.1f} kWh, ~${cost:.2f})"
        )
        alert = await self.create_alert(
            message=message,
            severity=AlertSeverity.WARNING.value,
            alert_type=AlertType.OFFICE_CONSUMPTION.value,
            energy_waste_kwh=consumption_kwh,
            estimated_cost_usd=cost,
        )
        if alert:
            outcome.alerts_created.append(alert)

    async def _escalate_by_age(self, outcome: AlertEvaluation) -> None:
        stmt = select(Alert).where(
            Alert.status.in_([
                AlertStatus.ACTIVE.value,
                AlertStatus.DISMISSED.value,
            ])
        )
        rows = list((await self.session.execute(stmt)).scalars())
        for alert in rows:
            age = _minutes_since(alert.created_at)
            if age >= ALERT_MAX_AFTER_MINUTES and alert.alert_type != AlertType.OFFICE_CONSUMPTION.value:
                await self.resolve(alert)
                outcome.alerts_resolved.append(alert)
                continue
            target = _severity_for_age(age)
            if target != alert.severity:
                await self.escalate(alert, target, reason=f"age={int(age)}m")
                outcome.alerts_updated.append(alert)
            alert.last_evaluated_at = _now()
            await self.session.flush()

    async def _existing_active(
        self,
        alert_type: str,
        room: Optional[str],
        device_id: Optional[int],
    ) -> Optional[Alert]:
        stmt = select(Alert).where(
            Alert.alert_type == alert_type,
            Alert.status.in_([
                AlertStatus.ACTIVE.value,
                AlertStatus.ACKNOWLEDGED.value,
                AlertStatus.DISMISSED.value,
            ]),
        )
        if room is not None:
            stmt = stmt.where(Alert.room == room)
        if device_id is not None:
            stmt = stmt.where(Alert.device_id == device_id)
        return (await self.session.execute(stmt)).scalars().first()

    # --------------------------------------------------------- energy helpers
    def compute_waste_for_devices(
        self,
        devices: Iterable[Device],
        since: Optional[datetime] = None,
    ) -> float:
        """Estimate kWh consumed by ``devices`` since ``since`` (default: 1h)."""
        if since is None:
            since = _now() - timedelta(hours=1)
        hours = max(0.0, (_now() - since).total_seconds() / 3600.0)
        watts = sum(
            d.power_consumption or 0.0
            for d in devices
            if d.status == DeviceStatus.ON.value
        )
        return watts * hours / 1000.0