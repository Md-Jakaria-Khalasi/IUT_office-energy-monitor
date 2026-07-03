"""WebSocket connection manager."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Set

from fastapi import WebSocket

from app.core.logging import logger


class WebSocketManager:
    """Tracks active websocket clients and broadcasts events to them."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket connected ({len(self.active_connections)} active)")
        await self._send(websocket, {"type": "welcome", "timestamp": datetime.utcnow().isoformat()})

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected ({len(self.active_connections)} active)")

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Broadcast a JSON payload to every active connection."""
        if not self.active_connections:
            return
        data = json.dumps(payload, default=str)
        stale: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(data)
            except Exception:
                stale.append(connection)
        for connection in stale:
            await self.disconnect(connection)

    async def broadcast_simulation(self, stats: Dict[str, Any]) -> None:
        await self.broadcast(
            {
                "type": "simulation_tick",
                "data": stats,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    async def broadcast_device_update(self, device_payload: Dict[str, Any]) -> None:
        await self.broadcast(
            {
                "type": "device_update",
                "data": device_payload,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    async def _send(self, websocket: WebSocket, payload: Dict[str, Any]) -> None:
        try:
            await websocket.send_text(json.dumps(payload, default=str))
        except Exception:
            await self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


ws_manager = WebSocketManager()