"""Read-only command cog for overviews, devices, power, and the dashboard.

Commands:

* ``!summary`` — top-of-house status card (one-shot).
* ``!devices [room]`` — list all devices, optionally filtered by room.
* ``!power`` — current power consumption ranked by room.
* ``!dashboard`` — full dashboard embed (used by the View button).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

import discord
from discord.ext import commands

from ..api_client import BackendConnectionError, BackendError
from ..embed_builder import (
    EMBED_COLOR_INFO,
    EMBED_COLOR_WARNING,
    dashboard_embed,
    error_embed,
    room_not_found_embed,
)
from ..models import Device

if TYPE_CHECKING:
    from ..bot import EnergyBot

logger = logging.getLogger(__name__)


class SummaryCog(commands.Cog):
    """Read-only summary commands."""

    def __init__(self, bot: "EnergyBot") -> None:
        self.bot = bot

    @commands.command(name="summary", aliases=["overview", "now"])
    async def summary(self, ctx: commands.Context) -> None:
        try:
            overview = await self.bot.backend.get_overview()
            embed = dashboard_embed(overview)
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !summary")
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return
        await ctx.send(embed=embed)

    @commands.command(name="dashboard", aliases=["board", "panel"])
    async def dashboard(self, ctx: commands.Context) -> None:
        try:
            embed = await _build_dashboard(self.bot)
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !dashboard")
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return
        await ctx.send(embed=embed)

    @commands.command(name="devices", aliases=["devs", "list"])
    async def devices(self, ctx: commands.Context, *, room: Optional[str] = None) -> None:
        try:
            devices = await self.bot.backend.list_devices(room=room)
            overview = await self.bot.backend.get_overview()
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return
        await ctx.send(embed=_devices_embed(devices, overview.total_devices, room))

    @commands.command(name="power", aliases=["watts", "load"])
    async def power(self, ctx: commands.Context) -> None:
        try:
            overview = await self.bot.backend.get_overview()
            devices = await self.bot.backend.list_devices()
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return
        await ctx.send(embed=_power_embed(devices, overview))


# ----- helpers ------------------------------------------------------------- #


def _group_by_room(devices: List[Device]) -> dict[str, tuple[int, float]]:
    by_room: dict[str, list[Device]] = {}
    for d in devices:
        by_room.setdefault(d.room, []).append(d)
    return {
        room: (
            sum(1 for d in dev_list if d.status == "on"),
            sum(d.power_consumption for d in dev_list if d.status == "on"),
        )
        for room, dev_list in by_room.items()
    }


async def _build_dashboard(bot: "EnergyBot") -> discord.Embed:
    overview = await bot.backend.get_overview()
    return dashboard_embed(overview)


def _devices_embed(
    devices: List[Device], total: int, room: Optional[str]
) -> discord.Embed:
    if room and not devices:
        return room_not_found_embed(room)
    title = f"\U0001F4CB Devices in {room}" if room else "\U0001F4CB All devices"
    if not devices:
        return discord.Embed(
            title=title,
            description="No devices reported.",
            color=EMBED_COLOR_INFO,
        )
    on_count = sum(1 for d in devices if d.status == "on")
    embed = discord.Embed(
        title=title,
        description=(
            f"**{on_count}** of **{len(devices)}** devices on · "
            f"office total **{total}** devices"
        ),
        color=EMBED_COLOR_INFO,
    )
    by_room = _group_by_room(devices)
    for room_name, (on, watts) in sorted(by_room.items(), key=lambda x: -x[1][1]):
        embed.add_field(
            name=f"{room_name}",
            value=f"{on} on · {watts:.1f} W",
            inline=True,
        )
    embed.set_footer(text=f"showing {len(devices)} device(s)")
    return embed


def _power_embed(devices: List[Device], overview) -> discord.Embed:
    by_room = _group_by_room(devices)
    rows = sorted(by_room.items(), key=lambda x: -x[1][1])
    if not rows:
        return discord.Embed(
            title="\u26A1 Power by room",
            description="No devices reported.",
            color=EMBED_COLOR_INFO,
        )
    embed = discord.Embed(
        title="\u26A1 Power by room",
        description=(
            f"Office total: **{overview.total_power_w:.1f} W** "
            f"· **{overview.total_devices_on}** device(s) on"
        ),
        color=EMBED_COLOR_WARNING if overview.total_power_w > 1500 else EMBED_COLOR_INFO,
    )
    for room_name, (on, watts) in rows:
        bar_len = max(1, int(round(watts / 50.0)))
        bar = "▮" * bar_len
        embed.add_field(
            name=f"{room_name}",
            value=f"{bar} **{watts:.1f} W** ({on} on)",
            inline=False,
        )
    embed.set_footer(text="Bars are 50 W per ▮")
    return embed


async def setup(bot: "EnergyBot") -> None:
    await bot.add_cog(SummaryCog(bot))