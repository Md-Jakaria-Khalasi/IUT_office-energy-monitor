"""``!usage`` command — recent activity and per-room power draw."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from ..api_client import (
    BackendConnectionError,
    BackendError,
)
from ..embed_builder import error_embed, usage_embed

if TYPE_CHECKING:
    from ..bot import EnergyBot

logger = logging.getLogger(__name__)


class UsageCog(commands.Cog):
    """Display recent activity and top rooms by power."""

    def __init__(self, bot: "EnergyBot") -> None:
        self.bot = bot

    @commands.command(name="usage", aliases=["activity", "recent"])
    async def usage_command(self, ctx: commands.Context) -> None:
        """Show recent device activity plus the top rooms by power draw."""
        try:
            activities = await self.bot.backend.list_activities(limit=20)
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
            logger.exception("Backend error in !usage")
            await ctx.send(embed=error_embed("❌ Backend error", f"{exc}"))
            return

        embed = usage_embed(activities, rooms)
        await ctx.send(embed=embed)


async def setup(bot: "EnergyBot") -> None:
    await bot.add_cog(UsageCog(bot))