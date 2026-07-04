"""``!help`` and ``!about`` commands."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from ..api_client import BackendConnectionError, BackendError
from ..embed_builder import EMBED_COLOR_INFO, help_embed

if TYPE_CHECKING:
    from ..bot import EnergyBot

logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    """Display the list of supported commands."""

    def __init__(self, bot: "EnergyBot") -> None:
        self.bot = bot

    @commands.command(name="help", aliases=["h", "commands"])
    async def help_command(self, ctx: commands.Context) -> None:
        """Show the bot's command reference. Room list is fetched live."""
        rooms: list[str] = []
        try:
            rooms = [room.room for room in await self.bot.backend.list_rooms()]
        except (BackendConnectionError, BackendError):
            # Help should always work — fall back to no room list rather than
            # sending a scary error embed for a help request.
            logger.debug("Could not fetch rooms for !help; falling back.")

        embed = help_embed(self.bot.command_prefix, rooms=rooms)
        try:
            await ctx.send(embed=embed)
        except discord.DiscordException as exc:
            logger.error("Failed to send help embed: %s", exc)

    @commands.command(name="about", aliases=["info"])
    async def about_command(self, ctx: commands.Context) -> None:
        """Short blurb about the bot and the project."""
        embed = discord.Embed(
            title="Office Energy Monitor",
            description=(
                "Discord companion bot for the Office Energy Monitor. "
                "Pulls live device and alert data from the FastAPI backend.\n\n"
                "Built for an online simulation-based hackathon; the "
                "backend is designed so that real ESP32 hardware can be "
                "dropped in without changing the bot."
            ),
            color=EMBED_COLOR_INFO,
        )
        embed.set_footer(text=f"prefix = {self.bot.command_prefix}")
        await ctx.send(embed=embed)


async def setup(bot: "EnergyBot") -> None:
    await bot.add_cog(HelpCog(bot))