"""Manual simulation trigger endpoint (useful for demos/tests)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.services.simulation import SimulationEngine


router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/tick")
async def tick(session: AsyncSession = Depends(db_session)) -> dict:
    engine = SimulationEngine(session)
    stats = await engine.tick()
    await session.commit()
    return stats