"""Background scheduler that ticks the simulation engine."""

from __future__ import annotations

import asyncio
from typing import Optional

from app.core.config import get_settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.services.simulation import SimulationEngine
from app.websocket.manager import ws_manager


class SimulationScheduler:
    """Runs the simulation engine on a fixed interval."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not self.settings.simulation_enabled:
            logger.warning("Simulation disabled; scheduler not started.")
            return
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="simulation-scheduler")
        logger.info(
            f"Simulation scheduler started "
            f"(interval={self.settings.simulation_interval_seconds}s)"
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            await self._task
            self._task = None

    async def _run(self) -> None:
        interval = self.settings.simulation_interval_seconds
        while not self._stopping.is_set():
            try:
                await self._tick_once()
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception(f"Simulation tick failed: {exc}")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _tick_once(self) -> None:
        async with AsyncSessionLocal() as session:
            engine = SimulationEngine(session)
            stats = await engine.tick()
        # Broadcast update to all subscribers
        await ws_manager.broadcast_simulation(stats)