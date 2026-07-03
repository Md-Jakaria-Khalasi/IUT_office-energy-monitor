"""FastAPI integration tests using httpx.AsyncClient."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.asyncio
async def test_root():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            response = await client.get("/")
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "online"


@pytest.mark.asyncio
async def test_list_devices_after_seed():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            response = await client.get("/api/v1/devices")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 15