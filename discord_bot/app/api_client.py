"""HTTP client for the FastAPI backend."""

from __future__ import annotations

from typing import Any, Dict, List

import httpx

from app.config import get_settings


class BackendClient:
    """Thin async wrapper around the backend REST API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> Any:
        response = await self._client.get(path)
        response.raise_for_status()
        return response.json()

    async def overview(self) -> Dict[str, Any]:
        return await self._get("/api/v1/rooms/overview")

    async def rooms(self) -> List[Dict[str, Any]]:
        return await self._get("/api/v1/rooms")

    async def devices(self, room: str | None = None) -> List[Dict[str, Any]]:
        path = "/api/v1/devices"
        if room:
            path += f"?room={room}"
        return await self._get(path)

    async def alerts(self) -> List[Dict[str, Any]]:
        return await self._get("/api/v1/alerts")

    async def health(self) -> Dict[str, Any]:
        return await self._get("/health")