"""Tests for :class:`app.services.alert_watcher.AlertWatcher`.

We drive the watcher's ``_tick`` directly so we don't have to actually wait
on a polling timer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

import discord
import httpx
import pytest

from app.api_client import BackendClient
from app.config import get_settings
from app.services.alert_watcher import AlertWatcher


class _FakeChannel:
    def __init__(self) -> None:
        self.sent: List[discord.Embed] = []

    async def send(self, *, embed: discord.Embed) -> None:  # noqa: D401
        self.sent.append(embed)


class _FakeBot:
    def __init__(self, channel_id: int, channel: _FakeChannel) -> None:
        self._channel_id = channel_id
        self._channel = channel

    def get_channel(self, channel_id: int):
        return self._channel if channel_id == self._channel_id else None

    async def fetch_channel(self, channel_id: int):
        if channel_id == self._channel_id:
            return self._channel
        raise discord.DiscordException("missing")


def _make_watcher(
    handler: Callable[[httpx.Request], httpx.Response],
    channel_id: int,
    alert_poll_limit: int = 50,
    poll_interval_seconds: float = 1.0,
):
    settings = get_settings()
    settings.alert_poll_limit = alert_poll_limit
    settings.poll_interval_seconds = poll_interval_seconds
    backend = BackendClient(settings)
    backend._client = httpx.AsyncClient(
        base_url=settings.api_base,
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
    )
    backend._owns_client = True
    channel = _FakeChannel()
    bot = _FakeBot(channel_id, channel)
    watcher = AlertWatcher(
        client=backend,
        settings=settings,
        bot=bot,  # type: ignore[arg-type]
        channel_id=channel_id,
    )
    return watcher, backend, channel


def _alert_payload(alert_id: int, severity: str = "warning") -> Dict[str, Any]:
    return {
        "id": alert_id,
        "severity": severity,
        "message": f"Test alert {alert_id}",
        "room": "Drawing Room",
        "device_id": None,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        "acknowledged": False,
    }


@pytest.mark.asyncio
async def test_first_tick_backfills_seen_without_posting():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[_alert_payload(1), _alert_payload(2)]
        )

    watcher, backend, channel = _make_watcher(handler, channel_id=12345)
    try:
        await watcher._tick()
        assert channel.sent == []
        assert watcher._seen == {1, 2}
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_subsequent_tick_posts_only_new_alerts():
    payloads = [
        [_alert_payload(1)],
        [_alert_payload(1), _alert_payload(2)],
        [_alert_payload(1), _alert_payload(2), _alert_payload(3)],
    ]
    call = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        idx = min(call["n"], len(payloads) - 1)
        return httpx.Response(200, json=payloads[idx])

    watcher, backend, channel = _make_watcher(handler, channel_id=12345)
    try:
        await watcher._tick()  # backfill: alert 1
        call["n"] += 1
        await watcher._tick()  # new: alert 2
        call["n"] += 1
        await watcher._tick()  # new: alert 3
        assert len(channel.sent) == 2
        # Posted in arrival order
        assert "alert 2" in channel.sent[0].description
        assert "alert 3" in channel.sent[1].description
        assert watcher._seen == {1, 2, 3}
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_dedup_no_repost_on_second_seen_alert():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_alert_payload(1)])

    watcher, backend, channel = _make_watcher(handler, channel_id=12345)
    try:
        await watcher._tick()  # backfill
        await watcher._tick()  # alert 1 already seen — nothing posted
        assert channel.sent == []
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_start_no_op_when_channel_id_missing():
    settings = get_settings()
    settings.alert_channel_id = None
    backend = BackendClient(settings)
    backend._client = httpx.AsyncClient(
        base_url=settings.api_base,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])),
        timeout=httpx.Timeout(5.0),
    )
    backend._owns_client = True

    watcher = AlertWatcher(
        client=backend,
        settings=settings,
        bot=_FakeBot(0, _FakeChannel()),  # type: ignore[arg-type]
        channel_id=None,
    )
    await watcher.start()
    assert not watcher.is_running
    await backend.close()


@pytest.mark.asyncio
async def test_backend_connection_error_does_not_crash_watcher():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    watcher, backend, channel = _make_watcher(handler, channel_id=12345)
    try:
        # First tick swallows the error and does not populate _seen.
        await watcher._tick()
        assert channel.sent == []
        assert watcher._seen == set()
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_resolve_channel_falls_back_to_fetch():
    class _LazyBot:
        def __init__(self) -> None:
            self.channel = _FakeChannel()

        def get_channel(self, channel_id: int):
            return None  # force fetch path

        async def fetch_channel(self, channel_id: int):
            assert channel_id == 42
            return self.channel

    settings = get_settings()
    backend = BackendClient(settings)
    backend._client = httpx.AsyncClient(
        base_url=settings.api_base,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])),
        timeout=httpx.Timeout(5.0),
    )
    backend._owns_client = True

    bot = _LazyBot()
    watcher = AlertWatcher(
        client=backend,
        settings=settings,
        bot=bot,  # type: ignore[arg-type]
        channel_id=42,
    )
    try:
        resolved = await watcher._resolve_channel()
        assert resolved is bot.channel
    finally:
        await backend.close()