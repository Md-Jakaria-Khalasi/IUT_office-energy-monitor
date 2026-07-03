"""Device REST endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.schemas.device import DeviceRead, DeviceUpdate
from app.services.device_service import DeviceService
from app.websocket.manager import ws_manager


router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=List[DeviceRead])
async def list_devices(
    room: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(db_session),
) -> List[DeviceRead]:
    service = DeviceService(session)
    devices = await service.list_devices(room=room)
    return [DeviceRead.model_validate(d) for d in devices]


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(
    device_id: int, session: AsyncSession = Depends(db_session)
) -> DeviceRead:
    service = DeviceService(session)
    device = await service.get_device(device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return DeviceRead.model_validate(device)


@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: int,
    payload: DeviceUpdate,
    session: AsyncSession = Depends(db_session),
) -> DeviceRead:
    service = DeviceService(session)
    try:
        device = await service.set_status(device_id, payload.status)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    data = DeviceRead.model_validate(device)
    await ws_manager.broadcast_device_update(data.model_dump())
    return data