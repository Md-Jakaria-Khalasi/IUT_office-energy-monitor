"""Per-room aggregated stats endpoints."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.core.constants import RoomName
from app.models.device import Device
from app.schemas.device import OverviewStats, RoomSummary
from app.services.alert_service import AlertService
from app.services.device_service import DeviceService
from app.websocket.manager import ws_manager
from sqlalchemy import select


router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=List[RoomSummary])
async def list_room_summaries(session: AsyncSession = Depends(db_session)) -> List[RoomSummary]:
    service = DeviceService(session)
    devices = await service.list_devices()
    summary: list[RoomSummary] = []
    for room in RoomName:
        room_devices = [d for d in devices if d.room == room.value]
        summary.append(
            RoomSummary(
                room=room.value,
                total_devices=len(room_devices),
                active_devices=sum(1 for d in room_devices if d.status == "on"),
                total_power=sum(d.power_consumption for d in room_devices),
            )
        )
    return summary


@router.get("/overview", response_model=OverviewStats)
async def office_overview(session: AsyncSession = Depends(db_session)) -> OverviewStats:
    device_service = DeviceService(session)
    alert_service = AlertService(session)

    devices: list[Device] = await device_service.list_devices()
    rooms: list[RoomSummary] = []
    for room in RoomName:
        room_devices = [d for d in devices if d.room == room.value]
        rooms.append(
            RoomSummary(
                room=room.value,
                total_devices=len(room_devices),
                active_devices=sum(1 for d in room_devices if d.status == "on"),
                total_power=sum(d.power_consumption for d in room_devices),
            )
        )
    return OverviewStats(
        total_devices=len(devices),
        active_devices=sum(1 for d in devices if d.status == "on"),
        total_power=sum(d.power_consumption for d in devices),
        rooms=rooms,
        active_alerts=await alert_service.active_count(),
    )


def _resolve_room(room: str) -> RoomName:
    """Map a path parameter into a known ``RoomName`` enum."""
    try:
        return RoomName(room)
    except ValueError as exc:
        valid = ", ".join(r.value for r in RoomName)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Unknown room '{room}'. Valid rooms: {valid}",
        ) from exc


@router.post("/{room}/all-on", response_model=Dict[str, Any])
async def all_on(room: str, session: AsyncSession = Depends(db_session)) -> Dict[str, Any]:
    """Turn every device in a room on. Idempotent and delta-only."""
    target = _resolve_room(room)
    service = DeviceService(session)
    changed = await service.set_room_status(target.value, "on")
    await session.commit()
    payloads = [service.device_to_payload(d) for d in changed]
    summary = await service.room_summary(target.value)
    for payload in payloads:
        await ws_manager.broadcast_device_update(payload)
    await ws_manager.broadcast_room_power(summary)
    return {"room": target.value, "changed": len(payloads), "devices": payloads, "summary": summary}


@router.post("/{room}/all-off", response_model=Dict[str, Any])
async def all_off(room: str, session: AsyncSession = Depends(db_session)) -> Dict[str, Any]:
    """Turn every device in a room off. Idempotent and delta-only."""
    target = _resolve_room(room)
    service = DeviceService(session)
    changed = await service.set_room_status(target.value, "off")
    await session.commit()
    payloads = [service.device_to_payload(d) for d in changed]
    summary = await service.room_summary(target.value)
    for payload in payloads:
        await ws_manager.broadcast_device_update(payload)
    await ws_manager.broadcast_room_power(summary)
    return {"room": target.value, "changed": len(payloads), "devices": payloads, "summary": summary}