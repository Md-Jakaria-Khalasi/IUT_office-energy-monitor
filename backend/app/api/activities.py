"""Activity REST endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.schemas.activity import ActivityRead
from app.services.activity_service import ActivityService


router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("", response_model=List[ActivityRead])
async def recent_activities(
    limit: int = Query(default=20, ge=1, le=200),
    room: str | None = Query(default=None),
    session: AsyncSession = Depends(db_session),
) -> List[ActivityRead]:
    service = ActivityService(session)
    if room:
        activities = await service.for_room(room=room, limit=limit)
    else:
        activities = await service.recent(limit=limit)
    return [ActivityRead.model_validate(a) for a in activities]