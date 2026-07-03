"""Alert engine and persistence."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AlertSeverity
from app.models.alert import Alert


class AlertService:
    """Manages alerts: creation, de-duplication, listing, acknowledgement."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_alert(
        self,
        message: str,
        severity: str = AlertSeverity.INFO.value,
        room: Optional[str] = None,
        device_id: Optional[int] = None,
        dedupe_seconds: int = 60,
    ) -> Optional[Alert]:
        """Create an alert unless an identical one was created recently."""
        cutoff = datetime.utcnow() - timedelta(seconds=dedupe_seconds)
        stmt = (
            select(Alert)
            .where(Alert.message == message)
            .where(Alert.created_at >= cutoff)
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing:
            return None

        alert = Alert(
            severity=severity,
            message=message,
            room=room,
            device_id=device_id,
            created_at=datetime.utcnow(),
        )
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def list_alerts(
        self, limit: int = 50, only_active: bool = True
    ) -> List[Alert]:
        stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        if only_active:
            stmt = stmt.where(Alert.acknowledged.is_(False))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def active_count(self) -> int:
        stmt = select(Alert).where(Alert.acknowledged.is_(False))
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))

    async def acknowledge(self, alert_id: int) -> Optional[Alert]:
        alert = await self.session.get(Alert, alert_id)
        if not alert:
            return None
        alert.acknowledged = True
        await self.session.flush()
        return alert