"""WebSocket connection manager."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

from app.core.logging import logger


class WebSocketManager:
    """Tracks active websocket clients and broadcasts events to them."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ basic
    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket connected ({len(self.active_connections)} active)")
        await self._send(
            websocket,
            {"type": "welcome", "timestamp": datetime.now(timezone.utc).isoformat()},
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected ({len(self.active_connections)} active)")

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Broadcast a JSON payload to every active connection.

        Uses :func:`asyncio.gather` so a slow / broken client never blocks the
        rest of the fan-out — each connection's send is its own task and a
        failure simply drops that connection. ``return_exceptions=True`` keeps
        a single bad socket from surfacing as an exception to the caller.
        """
        if not self.active_connections:
            return
        data = json.dumps(payload, default=str)

        async def _safe_send(connection: WebSocket) -> Optional[WebSocket]:
            try:
                await connection.send_text(data)
                return None
            except Exception:
                return connection

        results = await asyncio.gather(
            *[_safe_send(c) for c in list(self.active_connections)],
            return_exceptions=True,
        )
        stale: list[WebSocket] = []
        for result in results:
            if isinstance(result, WebSocket):
                stale.append(result)
            elif isinstance(result, Exception):
                # If gather itself raised (shouldn't with return_exceptions),
                # drop nothing — the inner _safe_send already handled errors.
                continue
        for connection in stale:
            await self.disconnect(connection)

    async def broadcast_async(self, payload: Dict[str, Any]) -> None:
        """Fire-and-forget broadcast scheduled on the running loop.

        Use this from request handlers so the WebSocket fan-out never blocks
        the response lifecycle. If no loop is running, falls back to a regular
        awaited broadcast.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            await self.broadcast(payload)
            return
        loop.create_task(self.broadcast(payload))

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)

    async def _send(self, websocket: WebSocket, payload: Dict[str, Any]) -> None:
        try:
            await websocket.send_text(json.dumps(payload, default=str))
        except Exception:
            await self.disconnect(websocket)

    # --------------------------------------------------------------- framed events
    def _frame(self, event_type: str, data: Any) -> Dict[str, Any]:
        return {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def broadcast_simulation(self, stats: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("simulation_tick", stats))

    async def broadcast_device_update(self, device_payload: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("device_update", device_payload))

    async def broadcast_room_power(self, room_payload: Dict[str, Any]) -> None:
        """Broadcast per-room aggregate power update.

        Payload shape::

            {
                "room": "Drawing Room",
                "total_devices": 5,
                "active_devices": 2,
                "total_power": 150.0,
            }
        """
        await self.broadcast(self._frame("room_power", room_payload))

    # --------------------------------------------------------------- alert events
    async def broadcast_alert_created(self, alert_payload: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("alert_created", alert_payload))

    async def broadcast_alert_updated(self, alert_payload: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("alert_updated", alert_payload))

    async def broadcast_alert_escalated(
        self, alert_payload: Dict[str, Any], previous_severity: Optional[str] = None
    ) -> None:
        await self.broadcast(
            self._frame(
                "alert_escalated",
                {"alert": alert_payload, "previous_severity": previous_severity},
            )
        )

    async def broadcast_alert_resolved(self, alert_payload: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("alert_resolved", alert_payload))

    async def broadcast_alert_acknowledged(self, alert_payload: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("alert_acknowledged", alert_payload))

    async def broadcast_alert_dismissed(self, alert_payload: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("alert_dismissed", alert_payload))

    async def broadcast_reminder(self, alert_payload: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("alert_reminder", alert_payload))

    async def broadcast_summary(self, summary_payload: Dict[str, Any]) -> None:
        await self.broadcast(self._frame("alert_summary", summary_payload))


ws_manager = WebSocketManager()