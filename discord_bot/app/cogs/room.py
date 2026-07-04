"""``!room <name>`` command — per-room stats + device list."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable, List, Optional

import discord
from discord.ext import commands

from ..api_client import (
    BackendConnectionError,
    BackendError,
)
from ..embed_builder import error_embed, room_embed, room_not_found_embed
from ..models import Device, RoomSummary

if TYPE_CHECKING:
    from ..bot import EnergyBot

logger = logging.getLogger(__name__)


class RoomCog(commands.Cog):
    """Report the state of a single room."""

    def __init__(self, bot: "EnergyBot") -> None:
        self.bot = bot

    @commands.command(name="room", aliases=["roomstats"])
    async def room_command(self, ctx: commands.Context, *, name: Optional[str] = None) -> None:
        """Show detailed stats for the named room."""
        if not name:
            await ctx.send(
                embed=error_embed(
                    "❓ Missing room name",
                    "Usage: `!room <name>` (e.g. `!room Drawing Room`).",
                )
            )
            return

        try:
            rooms = await self.bot.backend.list_rooms()
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "🔌 Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !room (rooms)")
            await ctx.send(
                embed=error_embed("❌ Backend error", f"{exc}")
            )
            return

        match = _match_room(name, rooms)
        if match is None:
            await ctx.send(embed=room_not_found_embed(name, [r.room for r in rooms]))
            return

        try:
            devices = await self.bot.backend.list_devices(room=match.room)
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "🔌 Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !room (devices)")
            await ctx.send(embed=error_embed("❌ Backend error", f"{exc}"))
            return

        embed = room_embed(match, devices)
        await ctx.send(embed=embed)


def _match_room(query: str, rooms: Iterable[RoomSummary]) -> Optional[RoomSummary]:
    """Resolve ``query`` to a room.

    Matching is case-insensitive and supports partial substring matches so
    users can type ``!room drawing`` instead of the full ``Drawing Room``.
    """
    q = query.strip().lower()
    rooms_list: List[RoomSummary] = list(rooms)
    for room in rooms_list:
        if room.room.lower() == q:
            return room
    for room in rooms_list:
        if q in room.room.lower():
            return room
    return None


async def setup(bot: "EnergyBot") -> None:
    await bot.add_cog(RoomCog(bot))