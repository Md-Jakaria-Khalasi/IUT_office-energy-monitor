"""Activity log queries."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity


class ActivityService:
    """Provides read-only access to activity history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recent(self, limit: int = 20) -> List[Activity]:
        stmt = (
            select(Activity)
            .order_by(Activity.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def for_room(self, room: str, limit: int = 20) -> List[Activity]:
        stmt = (
            select(Activity)
            .where(Activity.room == room)
            .order_by(Activity.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())