"""End-to-end tests for every command cog.

These instantiate each cog against a minimal ``EnergyBot``-shaped stub whose
``backend`` is a ``BackendClient`` backed by ``httpx.MockTransport``. We then
invoke the underlying coroutine directly (bypassing discord.py's invoke loop)
to capture the embed the cog would have sent.
"""

from __future__ import annotations

from typing import Callable, Dict, List

import discord
import httpx
import pytest

from app.api_client import BackendClient
from app.config import get_settings
from app.cogs import AlertsCog, HelpCog, RoomCog, StatusCog, UsageCog
from app.embed_builder import (
    EMBED_COLOR_CRITICAL,
    EMBED_COLOR_WARNING,
)


# ----------------------------------------------------------------- stub bot


class _StubBot:
    """Minimal stand-in exposing only what the cogs touch."""

    def __init__(self, backend: BackendClient, prefix: str = "!") -> None:
        self.backend = backend
        self.command_prefix = prefix
        self.user = None


class _StubContext:
    """Records every embed passed to ``send``."""

    def __init__(self, bot: _StubBot) -> None:
        self.bot = bot
        self.sent: List[discord.Embed] = []

    async def send(self, *, embed: discord.Embed) -> None:  # noqa: D401
        self.sent.append(embed)


def _make_bot(
    handler: Callable[[httpx.Request], httpx.Response],
    prefix: str = "!",
) -> tuple[_StubBot, BackendClient]:
    backend = BackendClient(get_settings())
    backend._client = httpx.AsyncClient(
        base_url=backend._settings.api_base,
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
    )
    backend._owns_client = True
    return _StubBot(backend, prefix=prefix), backend


# ----------------------------------------------------------------- !status


@pytest.mark.asyncio
async def test_status_returns_overview_embed(overview_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rooms/overview"):
            return httpx.Response(200, json=overview_payload)
        return httpx.Response(404, text="")

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = StatusCog(bot)

    try:
        await cog.status_command.callback(cog, ctx)  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        assert embed.title.startswith("📊")
        # The overview embed should reflect live data: 15 devices, 7 active.
        names = [f.name for f in embed.fields]
        assert "Total devices" in names
        assert "Active devices" in names
        assert "Live power draw" in names
        # Find the total devices value
        total_field = next(f for f in embed.fields if f.name == "Total devices")
        assert "15" in total_field.value
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_status_reports_backend_unreachable():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = StatusCog(bot)

    try:
        await cog.status_command.callback(cog, ctx)  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        assert "Backend unreachable" in embed.title
        assert embed.color.value == EMBED_COLOR_CRITICAL
    finally:
        await backend.close()


# ----------------------------------------------------------------- !room


@pytest.mark.asyncio
async def test_room_returns_room_embed(rooms_payload, devices_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rooms"):
            return httpx.Response(200, json=rooms_payload)
        if request.url.path.endswith("/devices"):
            assert dict(request.url.params).get("room") == "Drawing Room"
            return httpx.Response(200, json=devices_payload)
        return httpx.Response(404, text="")

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = RoomCog(bot)

    try:
        await cog.room_command.callback(cog, ctx, name="Drawing Room")  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        assert embed.title == "🏠 Drawing Room"
        names = [f.name for f in embed.fields]
        assert "Active / total" in names
        assert "Devices" in names
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_room_fuzzy_match_substring(rooms_payload, devices_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rooms"):
            return httpx.Response(200, json=rooms_payload)
        if request.url.path.endswith("/devices"):
            return httpx.Response(200, json=[])
        return httpx.Response(404, text="")

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = RoomCog(bot)

    try:
        await cog.room_command.callback(cog, ctx, name="drawing")  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        assert ctx.sent[0].title == "🏠 Drawing Room"
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_room_missing_name_sends_error_embed(rooms_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=rooms_payload)

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = RoomCog(bot)

    try:
        await cog.room_command.callback(cog, ctx, name=None)  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        assert "Missing room name" in embed.title
        assert embed.color.value == EMBED_COLOR_CRITICAL
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_room_unknown_name_lists_available(rooms_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rooms"):
            return httpx.Response(200, json=rooms_payload)
        return httpx.Response(404, text="")

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = RoomCog(bot)

    try:
        await cog.room_command.callback(cog, ctx, name="Garage")  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        assert "Unknown room" in embed.title
        assert embed.color.value == EMBED_COLOR_WARNING
        field_text = "\n".join(f.value for f in embed.fields)
        assert "Drawing Room" in field_text
    finally:
        await backend.close()


# ----------------------------------------------------------------- !usage


@pytest.mark.asyncio
async def test_usage_returns_combined_embed(rooms_payload, activities_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/activities"):
            return httpx.Response(200, json=activities_payload)
        if request.url.path.endswith("/rooms"):
            return httpx.Response(200, json=rooms_payload)
        return httpx.Response(404, text="")

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = UsageCog(bot)

    try:
        await cog.usage_command.callback(cog, ctx)  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        names = [f.name for f in embed.fields]
        assert "Top rooms by current draw" in names
        assert "Latest activity" in names
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_usage_handles_empty_data():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = UsageCog(bot)

    try:
        await cog.usage_command.callback(cog, ctx)  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        # With no rooms + no activities, "Top rooms" field is absent.
        names = [f.name for f in embed.fields]
        assert "Top rooms by current draw" not in names
    finally:
        await backend.close()


# ----------------------------------------------------------------- !alerts


@pytest.mark.asyncio
async def test_alerts_lists_active_alerts(alerts_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/alerts"):
            return httpx.Response(200, json=alerts_payload)
        return httpx.Response(404, text="")

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = AlertsCog(bot)

    try:
        await cog.alerts_command.callback(cog, ctx)  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        assert embed.title.startswith("🔔")
        assert "WARNING" in (embed.description or "")
        assert "CRITICAL" in (embed.description or "")
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_alerts_empty_says_no_active_alerts():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = AlertsCog(bot)

    try:
        await cog.alerts_command.callback(cog, ctx)  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        assert "No active alerts" in (embed.description or "")
    finally:
        await backend.close()


# ----------------------------------------------------------------- !help


@pytest.mark.asyncio
async def test_help_lists_every_command():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    bot, backend = _make_bot(handler)
    ctx = _StubContext(bot)
    cog = HelpCog(bot)

    try:
        await cog.help_command.callback(cog, ctx)  # type: ignore[arg-type]
        assert len(ctx.sent) == 1
        embed = ctx.sent[0]
        # The help embed groups commands into sections (📊 Overview, 🔔 Alerts,
        # ⚡ Actions). Section names are the field names; each section's body
        # lists the available commands. We assert the commands are listed by
        # joining every field value together. The !help command itself isn't
        # listed inside its own embed — instead the title advertises it as
        # "Commands" — so we check the title and the description prefix hint
        # in addition to the listed commands.
        assert "Commands" in (embed.title or "")
        names = [f.name for f in embed.fields]
        assert any(name.startswith("📊") for name in names), names
        assert any(name.startswith("🔔") for name in names), names
        assert any(name.startswith("⚡") for name in names), names
        bodies = "\n".join(f.value for f in embed.fields)
        for command in ("!status", "!room <name>", "!usage", "!alerts", "!help"):
            assert command in bodies, f"missing {command!r} in help embed"
    finally:
        await backend.close()


# ----------------------------------------------------------------- default help suppression


def test_energybot_suppresses_default_help_command():
    """EnergyBot must call ``remove_command("help")`` so the built-in
    discord.py ``!help`` doesn't shadow our custom HelpCog."""
    from app.bot import EnergyBot

    # Inspect the source-level intent without actually connecting to Discord.
    # We do this by constructing the bot and reading its internal command map.
    import inspect

    src = inspect.getsource(EnergyBot.__init__)
    assert "remove_command(\"help\")" in src, (
        "EnergyBot.__init__ must call self.remove_command(\"help\") to "
        "avoid colliding with the custom HelpCog."
    )