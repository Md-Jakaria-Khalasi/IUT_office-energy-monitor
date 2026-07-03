"""Discord bot implementation."""

from __future__ import annotations

import discord
from discord.ext import commands

from app.api_client import BackendClient
from app.config import get_settings


HELP_TEXT = """
**Office Energy Monitor — Bot Commands**

`!status` — Quick office overview
`!room [name]` — Room-specific stats (Drawing Room, Work Room 1, Work Room 2)
`!usage` — Detailed power usage by room
`!alerts` — Latest active alerts
`!help` — Show this message

All data is fetched live from the backend API.
"""


intents = discord.Intents.default()
intents.message_content = True


class EnergyBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix=get_settings().command_prefix, intents=intents)
        self.backend = BackendClient()

    async def setup_hook(self) -> None:
        await self.add_cog(EnergyCog(self))

    async def close(self) -> None:
        await self.backend.close()
        await super().close()


class EnergyCog(commands.Cog):
    def __init__(self, bot: EnergyBot) -> None:
        self.bot = bot

    @commands.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        data = await self.bot.backend.overview()
        embed = discord.Embed(
            title="🏢 Office Energy Overview",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Active Devices",
            value=f"{data['active_devices']} / {data['total_devices']}",
            inline=True,
        )
        embed.add_field(
            name="Total Power",
            value=f"{data['total_power']:.0f} W",
            inline=True,
        )
        embed.add_field(
            name="Active Alerts",
            value=str(data["active_alerts"]),
            inline=True,
        )
        await ctx.send(embed=embed)

    @commands.command(name="room")
    async def room(self, ctx: commands.Context, *, name: str | None = None) -> None:
        rooms = await self.bot.backend.rooms()
        target = name or "Drawing Room"
        room_data = next((r for r in rooms if r["room"].lower() == target.lower()), None)
        if not room_data:
            await ctx.send(f"❌ Room `{target}` not found. Try: Drawing Room, Work Room 1, Work Room 2")
            return

        devices = await self.bot.backend.devices(room=room_data["room"])
        embed = discord.Embed(title=f"🚪 {room_data['room']}", color=discord.Color.blue())
        embed.add_field(name="Total Devices", value=str(room_data["total_devices"]), inline=True)
        embed.add_field(name="Active", value=str(room_data["active_devices"]), inline=True)
        embed.add_field(name="Power", value=f"{room_data['total_power']:.0f} W", inline=True)
        body = "\n".join(
            f"{'🟢' if d['status'] == 'on' else '⚪'} {d['name']} ({d['type']}): {d['power_consumption']:.0f} W"
            for d in devices
        )
        embed.add_field(name="Devices", value=body or "No devices", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="usage")
    async def usage(self, ctx: commands.Context) -> None:
        rooms = await self.bot.backend.rooms()
        embed = discord.Embed(title="⚡ Power Usage by Room", color=discord.Color.orange())
        for room in rooms:
            embed.add_field(
                name=room["room"],
                value=(
                    f"Active: {room['active_devices']}/{room['total_devices']}\n"
                    f"Power: {room['total_power']:.0f} W"
                ),
                inline=False,
            )
        total = sum(r["total_power"] for r in rooms)
        embed.set_footer(text=f"Total power draw: {total:.0f} W")
        await ctx.send(embed=embed)

    @commands.command(name="alerts")
    async def alerts(self, ctx: commands.Context) -> None:
        alerts = await self.bot.backend.alerts()
        if not alerts:
            await ctx.send("✅ No active alerts")
            return
        embed = discord.Embed(title="🚨 Active Alerts", color=discord.Color.red())
        for a in alerts[:10]:
            embed.add_field(
                name=f"[{a['severity'].upper()}] {a['created_at']}",
                value=a["message"],
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context) -> None:
        await ctx.send(HELP_TEXT)


def run() -> None:
    settings = get_settings()
    if not settings.discord_token:
        raise RuntimeError(
            "DISCORD_TOKEN environment variable is required to start the bot."
        )
    bot = EnergyBot()
    bot.run(settings.discord_token)


if __name__ == "__main__":
    run()