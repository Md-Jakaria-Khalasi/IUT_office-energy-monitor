"""Alert REST endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.schemas.alert import AlertRead
from app.services.alert_service import AlertService


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertRead])
async def list_alerts(
    limit: int = 50, session: AsyncSession = Depends(db_session)
) -> List[AlertRead]:
    service = AlertService(session)
    alerts = await service.list_alerts(limit=limit)
    return [AlertRead.model_validate(a) for a in alerts]


@router.post("/{alert_id}/ack", response_model=AlertRead)
async def acknowledge(alert_id: int, session: AsyncSession = Depends(db_session)) -> AlertRead:
    service = AlertService(session)
    alert = await service.acknowledge(alert_id)
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    await session.commit()
    return AlertRead.model_validate(alert)