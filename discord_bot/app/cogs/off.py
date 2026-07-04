"""``!off`` — turn devices off via command or interactive buttons.

Supports three sub-commands:

* ``!off device <id|name>`` — turn a single device off.
* ``!off room <name>`` — turn every active device in a room off.
* ``!off all`` — turn every active device in the office off.

Each command response includes a confirmation view that re-lists what was
turned off, the new total power draw, and *Ignore 30 min* / *Ignore today*
buttons that dismiss any matching alerts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple

import discord
from discord.ext import commands

from ..api_client import (
    BackendConnectionError,
    BackendError,
)
from ..embed_builder import _alert_status_glyph, error_embed
from ..models import Device

if TYPE_CHECKING:
    from ..bot import EnergyBot

logger = logging.getLogger(__name__)


def _match_device(query: str, devices: List[Device]) -> Optional[Device]:
    """Match ``query`` against a device by id, name, or partial name."""
    q = query.strip().lower().lstrip("#")
    if q.isdigit():
        target = int(q)
        for device in devices:
            if device.id == target:
                return device
    for device in devices:
        if device.name.lower() == q:
            return device
    for device in devices:
        if q in device.name.lower():
            return device
    return None


def _match_room(query: str, devices: List[Device]) -> Optional[str]:
    q = query.strip().lower()
    rooms = {d.room for d in devices}
    if q in rooms:
        return q
    for room in rooms:
        if q in room.lower():
            return room
    return None


def _summary(devices: Iterable[Device]) -> Tuple[int, float]:
    on_devices = [d for d in devices if d.status == "on"]
    return len(on_devices), sum(d.power_consumption for d in on_devices)


class OffCog(commands.Cog):
    """Interactive commands to turn devices off."""

    def __init__(self, bot: "EnergyBot") -> None:
        self.bot = bot

    @commands.command(name="off", aliases=["shutdown", "kill"])
    async def off_command(
        self,
        ctx: commands.Context,
        scope: Optional[str] = None,
        *,
        target: Optional[str] = None,
    ) -> None:
        """Turn devices off.

        Usage:
            ``!off device 3``
            ``!off device Lab Light``
            ``!off room Drawing Room``
            ``!off all``
        """
        if scope is None:
            await ctx.send(
                embed=error_embed(
                    "\u274C Missing scope",
                    "Usage: `!off device <id|name>`, `!off room <name>`, or `!off all`.",
                )
            )
            return

        scope_norm = scope.lower()
        try:
            if scope_norm in ("device", "dev", "d"):
                if not target:
                    await ctx.send(
                        embed=error_embed(
                            "\u274C Missing target",
                            "Usage: `!off device <id|name>` (e.g. `!off device 3`).",
                        )
                    )
                    return
                await self._off_device(ctx, target)
            elif scope_norm in ("room", "r"):
                if not target:
                    await ctx.send(
                        embed=error_embed(
                            "\u274C Missing target",
                            "Usage: `!off room <name>` (e.g. `!off room Lab`).",
                        )
                    )
                    return
                await self._off_room(ctx, target)
            elif scope_norm in ("all", "everything", "office"):
                await self._off_all(ctx)
            else:
                # Allow `!off <name>` as shorthand for `!off device <name>`.
                await self._off_device(ctx, scope + (" " + target if target else ""))
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
        except BackendError as exc:
            logger.exception("Backend error in !off")
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))

    # ----- internal handlers --------------------------------------------- #

    async def _off_device(self, ctx: commands.Context, query: str) -> None:
        devices = await self.bot.backend.list_devices()
        match = _match_device(query, devices)
        if match is None:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50E Device not found",
                    f"Could not find a device matching **{query}**.",
                )
            )
            return
        if match.status == "off":
            await ctx.send(
                embed=_info_embed(
                    f"{match.name} is already off.",
                    f"No power was being drawn by `#{match.id}`.",
                )
            )
            return

        try:
            updated = await self.bot.backend.set_device_status(match.id, "off")
        except BackendError as exc:
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return

        embed = discord.Embed(
            title=f"\U0001F7E2 Turned off: {updated.name}",
            description=(
                f"Device `#{updated.id}` in **{updated.room}** is now **off**.\n"
                f"Freed **{match.power_consumption:.1f} W** of live power."
            ),
            color=0x2ECC71,
        )
        embed.add_field(name="Type", value=updated.type, inline=True)
        embed.add_field(name="Room", value=updated.room, inline=True)
        embed.add_field(
            name="Status",
            value=f"{updated.status.upper()}",
            inline=True,
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(
            embed=embed,
            view=_DeviceOffView(
                bot=self.bot,
                room=updated.room,
                device_id=updated.id,
                requester=ctx.author,
            ),
        )

    async def _off_room(self, ctx: commands.Context, query: str) -> None:
        devices = await self.bot.backend.list_devices()
        room = _match_room(query, devices)
        if room is None:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50E Room not found",
                    f"Could not find a room matching **{query}**.",
                )
            )
            return

        active = [d for d in devices if d.room == room and d.status == "on"]
        if not active:
            await ctx.send(
                embed=_info_embed(
                    f"Nothing is on in {room}.",
                    "Every device in this room is already off.",
                )
            )
            return

        freed = 0.0
        failed: List[str] = []
        for device in active:
            try:
                await self.bot.backend.set_device_status(device.id, "off")
                freed += device.power_consumption
            except BackendError as exc:
                logger.warning("Could not turn off device #%s: %s", device.id, exc)
                failed.append(f"#{device.id} {device.name}")

        embed = discord.Embed(
            title=f"\U0001F7E2 Turned off {len(active) - len(failed)} device(s) in {room}",
            description=(
                f"Freed approximately **{freed:.1f} W** of live power."
                + ("\n\nFailed: " + ", ".join(failed) if failed else "")
            ),
            color=0x2ECC71 if not failed else 0xF1C40F,
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(
            embed=embed,
            view=_RoomOffView(bot=self.bot, room=room, requester=ctx.author),
        )

    async def _off_all(self, ctx: commands.Context) -> None:
        devices = await self.bot.backend.list_devices()
        active = [d for d in devices if d.status == "on"]
        if not active:
            await ctx.send(
                embed=_info_embed("Nothing to turn off.", "Every device is already off.")
            )
            return

        rooms_touched = sorted({d.room for d in active})
        freed = 0.0
        failed: List[str] = []
        for device in active:
            try:
                await self.bot.backend.set_device_status(device.id, "off")
                freed += device.power_consumption
            except BackendError as exc:
                logger.warning("Could not turn off device #%s: %s", device.id, exc)
                failed.append(f"#{device.id} {device.name}")

        embed = discord.Embed(
            title=f"\U0001F7E2 Turned off {len(active) - len(failed)} device(s) across the office",
            description=(
                f"Rooms: {', '.join(rooms_touched)}\n"
                f"Freed approximately **{freed:.1f} W** of live power."
                + ("\n\nFailed: " + ", ".join(failed) if failed else "")
            ),
            color=0x2ECC71 if not failed else 0xF1C40F,
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(
            embed=embed,
            view=_OfficeOffView(bot=self.bot, requester=ctx.author),
        )


# ----- helpers ------------------------------------------------------------- #


def _info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=0x3498DB)


# ----- interactive views --------------------------------------------------- #


class _DismissAlertsButton(discord.ui.Button):
    """Base button that dismisses alerts and edits the parent message."""

    async def _dismiss(
        self,
        interaction: discord.Interaction,
        *,
        duration: Optional[int],
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            alerts = await self.view.bot.backend.list_alerts(  # type: ignore[attr-defined]
                only_active=True,
                room=getattr(self.view, "room", None),
                device_id=getattr(self.view, "device_id", None),
            )
        except BackendError as exc:
            await interaction.followup.send(
                embed=error_embed("\u274C Failed", f"{exc}"), ephemeral=True
            )
            return
        dismissed = 0
        for alert in alerts:
            try:
                await self.view.bot.backend.dismiss_alert(  # type: ignore[attr-defined]
                    alert.id,
                    duration_minutes=duration,
                    dismissed_by=interaction.user.display_name,
                )
                dismissed += 1
            except BackendError:
                continue
        await interaction.followup.send(
            f"🔕 Dismissed **{dismissed}** active alert(s).",
            ephemeral=True,
        )


class _Ignore30Button(_DismissAlertsButton):
    def __init__(self, bot: "EnergyBot") -> None:
        super().__init__(label="Ignore 30m", style=discord.ButtonStyle.secondary, emoji="🔕")
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._dismiss(interaction, duration=30)


class _IgnoreTodayButton(_DismissAlertsButton):
    def __init__(self, bot: "EnergyBot") -> None:
        super().__init__(label="Ignore today", style=discord.ButtonStyle.secondary, emoji="\U0001F4A4")  # 💤
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._dismiss(interaction, duration=1440)


class _TurnOffRoomButton(discord.ui.Button):
    """Confirm turning off the whole room."""

    def __init__(self, bot: "EnergyBot", room: str) -> None:
        super().__init__(
            label=f"Turn off {room}",
            style=discord.ButtonStyle.danger,
            emoji="\U0001F7E2",  # 🟢
        )
        self.bot = bot
        self.room_name = room

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            devices = await self.bot.backend.list_devices(room=self.room_name)
            active = [d for d in devices if d.status == "on"]
            freed = 0.0
            for d in active:
                try:
                    await self.bot.backend.set_device_status(d.id, "off")
                    freed += d.power_consumption
                except BackendError:
                    continue
        except BackendError as exc:
            await interaction.followup.send(
                embed=error_embed("\u274C Failed", f"{exc}")
            )
            return
        await interaction.followup.send(
            f"Turned off **{len(active)}** device(s) in **{self.room_name}** "
            f"(~{freed:.1f} W freed)."
        )


class _TurnOffDeviceButton(discord.ui.Button):
    """Confirm turning off a single device by id."""

    def __init__(self, bot: "EnergyBot", device_id: int) -> None:
        super().__init__(label="Turn off device", style=discord.ButtonStyle.danger, emoji="⏻")
        self.bot = bot
        self.device_id = device_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            await self.bot.backend.set_device_status(self.device_id, "off")
        except BackendError as exc:
            await interaction.followup.send(
                embed=error_embed("\u274C Failed", f"{exc}")
            )
            return
        await interaction.followup.send(
            f"Device **#{self.device_id}** turned off."
        )


class _AcknowledgeButton(discord.ui.Button):
    def __init__(self, bot: "EnergyBot") -> None:
        super().__init__(label="Acknowledge alerts", style=discord.ButtonStyle.success, emoji="✅")
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            alerts = await self.bot.backend.list_alerts(
                only_active=True,
                room=getattr(self.view, "room", None),
                device_id=getattr(self.view, "device_id", None),
            )
            acked = 0
            for alert in alerts:
                try:
                    await self.bot.backend.acknowledge_alert(
                        alert.id, acknowledged_by=interaction.user.display_name
                    )
                    acked += 1
                except BackendError:
                    continue
        except BackendError as exc:
            await interaction.followup.send(
                embed=error_embed("\u274C Failed", f"{exc}"), ephemeral=True
            )
            return
        await interaction.followup.send(
            f"✅ Acknowledged **{acked}** active alert(s).", ephemeral=True
        )


class _ViewDashboardButton(discord.ui.Button):
    def __init__(self, bot: "EnergyBot") -> None:
        super().__init__(label="Dashboard", style=discord.ButtonStyle.primary, emoji="\U0001F39B️")  # 🎛️
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        from .summary import _build_dashboard  # local import to avoid cycle

        try:
            embed = await _build_dashboard(self.bot)
        except BackendError as exc:
            await interaction.followup.send(
                embed=error_embed("\u274C Failed", f"{exc}"), ephemeral=True
            )
            return
        await interaction.followup.send(embed=embed, ephemeral=True)


class _DeviceOffView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "EnergyBot",
        room: str,
        device_id: int,
        requester: discord.abc.User,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.room = room
        self.device_id = device_id
        self.requester = requester
        self.add_item(_AcknowledgeButton(bot))
        self.add_item(_Ignore30Button(bot))
        self.add_item(_IgnoreTodayButton(bot))
        self.add_item(_TurnOffRoomButton(bot, room))
        self.add_item(_ViewDashboardButton(bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "Only the requester can use these buttons.", ephemeral=True
            )
            return False
        return True


class _RoomOffView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "EnergyBot",
        room: str,
        requester: discord.abc.User,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.room = room
        self.requester = requester
        self.add_item(_AcknowledgeButton(bot))
        self.add_item(_Ignore30Button(bot))
        self.add_item(_IgnoreTodayButton(bot))
        self.add_item(_ViewDashboardButton(bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "Only the requester can use these buttons.", ephemeral=True
            )
            return False
        return True


class _OfficeOffView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "EnergyBot",
        requester: discord.abc.User,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.requester = requester
        self.add_item(_AcknowledgeButton(bot))
        self.add_item(_Ignore30Button(bot))
        self.add_item(_IgnoreTodayButton(bot))
        self.add_item(_ViewDashboardButton(bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "Only the requester can use these buttons.", ephemeral=True
            )
            return False
        return True


async def setup(bot: "EnergyBot") -> None:
    await bot.add_cog(OffCog(bot))