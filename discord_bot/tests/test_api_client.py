"""Unit tests for :class:`app.api_client.BackendClient`.

Uses ``httpx.MockTransport`` to avoid any real network I/O.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict

import httpx
import pytest

from app.api_client import (
    BackendClient,
    BackendConnectionError,
    BackendHTTPError,
    BackendNotFound,
    BackendValidationError,
)
from app.config import get_settings


def _build_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> BackendClient:
    """Return a started :class:`BackendClient` that uses ``handler`` for every call."""
    client = BackendClient(get_settings())
    client._client = httpx.AsyncClient(
        base_url=client._settings.api_base,
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
    )
    client._owns_client = True
    return client


@pytest.mark.asyncio
async def test_get_overview_returns_parsed_model(overview_payload: Dict[str, Any]):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/rooms/overview")
        return httpx.Response(200, json=overview_payload)

    client = _build_client(handler)
    try:
        stats = await client.get_overview()
        assert stats.total_devices == 15
        assert stats.active_devices == 7
        assert stats.total_power == 312.5
        assert len(stats.rooms) == 3
        assert stats.rooms[0].room == "Drawing Room"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_list_devices_filters_by_room(devices_payload):
    captured: Dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=devices_payload)

    client = _build_client(handler)
    try:
        devices = await client.list_devices(room="Drawing Room")
        assert captured["params"]["room"] == "Drawing Room"
        assert len(devices) == 2
        assert devices[0].id == 1
        assert devices[0].status == "on"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_list_devices_no_room_omits_query():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "room" not in request.url.params
        return httpx.Response(200, json=[])

    client = _build_client(handler)
    try:
        devices = await client.list_devices()
        assert devices == []
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_set_device_status_sends_patch_with_payload(devices_payload):
    captured: Dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content or b"null")
        return httpx.Response(
            200, json={**devices_payload[0], "status": "off"}
        )

    client = _build_client(handler)
    try:
        device = await client.set_device_status(1, "off")
        assert captured["method"] == "PATCH"
        assert captured["url"].endswith("/devices/1")
        assert captured["body"] == {"status": "off"}
        assert device.status == "off"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_set_device_status_rejects_invalid_value():
    client = _build_client(lambda req: httpx.Response(200, json={}))
    try:
        with pytest.raises(ValueError):
            await client.set_device_status(1, "bogus")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_list_alerts_honors_limit(alerts_payload):
    captured: Dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=alerts_payload)

    client = _build_client(handler)
    try:
        alerts = await client.list_alerts(limit=7)
        assert captured["params"]["limit"] == "7"
        assert len(alerts) == 2
        assert alerts[0].severity == "warning"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_list_activities_supports_room(activities_payload):
    captured: Dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=activities_payload)

    client = _build_client(handler)
    try:
        acts = await client.list_activities(limit=5, room="Drawing Room")
        assert captured["params"]["limit"] == "5"
        assert captured["params"]["room"] == "Drawing Room"
        assert acts[0].device_name == "Light 1"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_404_raises_backend_not_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")

    client = _build_client(handler)
    try:
        with pytest.raises(BackendNotFound) as exc_info:
            await client.get_device(999)
        assert exc_info.value.status_code == 404
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_4xx_raises_backend_validation_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "bad"})

    client = _build_client(handler)
    try:
        with pytest.raises(BackendValidationError) as exc_info:
            await client.list_devices()
        assert exc_info.value.status_code == 422
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_5xx_raises_backend_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = _build_client(handler)
    try:
        with pytest.raises(BackendHTTPError) as exc_info:
            await client.list_devices()
        assert exc_info.value.status_code == 500
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_connection_error_is_wrapped():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = _build_client(handler)
    try:
        with pytest.raises(BackendConnectionError):
            await client.list_devices()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_invalid_json_raises_backend_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    client = _build_client(handler)
    try:
        from app.api_client import BackendError

        with pytest.raises(BackendError):
            await client.list_devices()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_healthcheck_hits_backend_root_not_api_prefix():
    """``/healthz`` lives at the backend root, not under ``/api/v1``.

    The probe client must therefore be anchored at ``settings.backend_url``;
    routing it through ``api_base`` (``http://host:port/api/v1``) would 404.
    """
    captured: Dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": "ok"})

    client = BackendClient(get_settings())
    # Inject the mock onto the *probe* client by patching httpx.AsyncClient
    # creation just for this test.
    original_async_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    httpx.AsyncClient = factory  # type: ignore[assignment]
    try:
        ok = await client.healthcheck()
    finally:
        httpx.AsyncClient = original_async_client  # type: ignore[assignment]

    assert ok is True
    assert captured["url"].endswith("/healthz")
    # The probe must NOT have been routed through the API prefix.
    assert "/api/v1/healthz" not in captured["url"]


@pytest.mark.asyncio
async def test_healthcheck_returns_false_when_all_paths_fail():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")

    client = BackendClient(get_settings())
    original_async_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    httpx.AsyncClient = factory  # type: ignore[assignment]
    try:
        ok = await client.healthcheck()
    finally:
        httpx.AsyncClient = original_async_client  # type: ignore[assignment]
    assert ok is False


@pytest.mark.asyncio
async def test_context_manager_lifecycle():
    started = {"called": False}
    closed = {"called": False}

    async def handler(request: httpx.Request) -> httpx.Response:
        started["called"] = True
        return httpx.Response(200, json=[])

    client = BackendClient(get_settings())
    client._client = httpx.AsyncClient(
        base_url=client._settings.api_base,
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
    )
    client._owns_client = True

    original_close = client.close

    async def tracking_close() -> None:
        closed["called"] = True
        await original_close()

    client.close = tracking_close  # type: ignore[method-assign]

    async with client as c:
        rooms = await c.list_rooms()
        assert rooms == []
    assert started["called"]
    assert closed["called"]