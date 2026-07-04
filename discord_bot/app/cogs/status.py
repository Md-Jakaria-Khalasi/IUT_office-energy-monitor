"""``!status`` command — quick office overview."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from ..api_client import (
    BackendConnectionError,
    BackendError,
)
from ..embed_builder import error_embed, overview_embed

if TYPE_CHECKING:
    from ..bot import EnergyBot

logger = logging.getLogger(__name__)


class StatusCog(commands.Cog):
    """Report the overall office state."""

    def __init__(self, bot: "EnergyBot") -> None:
        self.bot = bot

    @commands.command(name="status", aliases=["overview", "office"])
    async def status_command(self, ctx: commands.Context) -> None:
        """Reply with a live overview embed from the backend."""
        try:
            stats = await self.bot.backend.get_overview()
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "🔌 Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !status")
            await ctx.send(
                embed=error_embed(
                    "❌ Backend error",
                    f"The backend returned an error: {exc}",
                )
            )
            return

        embed = overview_embed(stats)
        await ctx.send(embed=embed)


async def setup(bot: "EnergyBot") -> None:
    await bot.add_cog(StatusCog(bot))