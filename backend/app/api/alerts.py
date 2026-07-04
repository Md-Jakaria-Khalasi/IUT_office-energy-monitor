"""Alert REST endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.schemas.alert import (
    AlertAcknowledge,
    AlertDismiss,
    AlertRead,
    AlertSummary,
)
from app.services.alert_service import AlertService
from app.websocket.manager import ws_manager


router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize(alert) -> Dict[str, Any]:
    """Serialize an Alert to a JSON-safe dict.

    Pydantic's ``from_attributes`` converts datetime and JSON columns for us,
    but we still want to coerce ``severity_history`` so each entry is a plain
    ``dict`` even if the column was returned as a list of tuples.
    """
    payload = AlertRead.model_validate(alert).model_dump(mode="json")
    history: List[Any] = []
    for entry in payload.get("severity_history") or []:
        if not isinstance(entry, dict):
            continue
        history.append({k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in entry.items()})
    payload["severity_history"] = history
    return payload


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[AlertRead])
async def list_alerts(
    severity: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    alert_type: Optional[str] = Query(default=None),
    room: Optional[str] = Query(default=None),
    device_id: Optional[int] = Query(default=None),
    only_active: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(db_session),
) -> List[AlertRead]:
    service = AlertService(session)
    alerts = await service.list_alerts(
        limit=limit,
        only_active=only_active,
        severity=severity,
        status=status_filter,
        alert_type=alert_type,
        room=room,
        device_id=device_id,
    )
    return [AlertRead.model_validate(a) for a in alerts]


@router.get("/summary", response_model=AlertSummary)
async def alerts_summary(
    session: AsyncSession = Depends(db_session),
) -> AlertSummary:
    service = AlertService(session)
    data = await service.summary()
    return AlertSummary(**data)


@router.get("/due-reminders", response_model=List[AlertRead])
async def due_reminders(
    session: AsyncSession = Depends(db_session),
) -> List[AlertRead]:
    """Return active alerts whose last reminder is older than the interval."""
    service = AlertService(session)
    rows = await service.due_for_reminder()
    return [AlertRead.model_validate(a) for a in rows]


@router.get("/{alert_id}", response_model=AlertRead)
async def get_alert(
    alert_id: int,
    session: AsyncSession = Depends(db_session),
) -> AlertRead:
    service = AlertService(session)
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    return AlertRead.model_validate(alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertRead)
async def acknowledge_alert(
    alert_id: int,
    payload: AlertAcknowledge | None = None,
    session: AsyncSession = Depends(db_session),
) -> AlertRead:
    service = AlertService(session)
    ack_by = payload.acknowledged_by if payload else None
    alert = await service.acknowledge(alert_id, acknowledged_by=ack_by)
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    await session.commit()
    await ws_manager.broadcast_alert_acknowledged(_serialize(alert))
    return AlertRead.model_validate(alert)


# Backwards-compatible alias used by the existing Discord cog.
@router.post("/{alert_id}/ack", response_model=AlertRead)
async def ack_alias(
    alert_id: int,
    session: AsyncSession = Depends(db_session),
) -> AlertRead:
    service = AlertService(session)
    alert = await service.acknowledge(alert_id)
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    await session.commit()
    await ws_manager.broadcast_alert_acknowledged(_serialize(alert))
    return AlertRead.model_validate(alert)


@router.post("/{alert_id}/dismiss", response_model=AlertRead)
async def dismiss_alert(
    alert_id: int,
    payload: AlertDismiss | None = None,
    session: AsyncSession = Depends(db_session),
) -> AlertRead:
    service = AlertService(session)
    if payload is None:
        payload = AlertDismiss()
    alert = await service.dismiss(
        alert_id,
        duration_minutes=payload.duration_minutes,
        dismissed_by=payload.dismissed_by,
    )
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    await session.commit()
    await ws_manager.broadcast_alert_dismissed(_serialize(alert))
    return AlertRead.model_validate(alert)


@router.post("/{alert_id}/resolve", response_model=AlertRead)
async def resolve_alert(
    alert_id: int,
    session: AsyncSession = Depends(db_session),
) -> AlertRead:
    service = AlertService(session)
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    await service.resolve(alert)
    await session.commit()
    await ws_manager.broadcast_alert_resolved(_serialize(alert))
    return AlertRead.model_validate(alert)