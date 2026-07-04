"""``!alerts`` / ``!alert`` / ``!ack`` / ``!dismiss`` / ``!resolve`` commands.

Alert *notifications* (i.e. automatic posting of new alerts) are handled by
:class:`app.services.alert_watcher.AlertWatcher`, which is started in the
bot's ``setup_hook``. This cog only exposes user-invoked commands.
"""

from __future__ import annotations

import logging
import shlex
from typing import TYPE_CHECKING, List, Optional

import discord
from discord.ext import commands

from ..api_client import (
    BackendConnectionError,
    BackendError,
    BackendNotFound,
    BackendValidationError,
)
from ..embed_builder import (
    _alert_severity_color,
    _alert_status_glyph,
    alert_detail_embed,
    alerts_embed,
    error_embed,
)
from ..models import Alert

if TYPE_CHECKING:
    from ..bot import EnergyBot

logger = logging.getLogger(__name__)

VALID_SEVERITIES = {"info", "warning", "critical"}
VALID_STATUSES = {"active", "acknowledged", "dismissed", "resolved"}


def _parse_filters(args: List[str]) -> dict:
    """Parse ``!alerts severity=critical status=active room=Lab active=true``.

    Unknown ``key=value`` pairs are ignored. Bare tokens are ignored as well —
    we don't want users to accidentally type ``!alerts critical`` and silently
    drop the severity filter because we couldn't parse it.
    """
    parsed: dict = {}
    for token in args:
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if not key or not value:
            continue
        if key == "severity":
            if value not in VALID_SEVERITIES:
                raise ValueError(f"Unknown severity: {value!r}")
            parsed["severity"] = value
        elif key == "status":
            if value not in VALID_STATUSES:
                raise ValueError(f"Unknown status: {value!r}")
            parsed["status"] = value
        elif key == "room":
            parsed["room"] = value
        elif key == "type":
            parsed["alert_type"] = value
        elif key in ("device", "device_id"):
            try:
                parsed["device_id"] = int(value.lstrip("#"))
            except ValueError as exc:
                raise ValueError(f"Invalid device id: {value!r}") from exc
        elif key == "active":
            parsed["only_active"] = value.lower() in {"1", "true", "yes", "y"}
        elif key == "limit":
            try:
                parsed["limit"] = max(1, min(int(value), 100))
            except ValueError as exc:
                raise ValueError(f"Invalid limit: {value!r}")
    return parsed


class AlertsCog(commands.Cog):
    """Display and acknowledge active alerts."""

    def __init__(self, bot: "EnergyBot") -> None:
        self.bot = bot

    @commands.command(name="alerts", aliases=["warnings"])
    async def alerts_command(self, ctx: commands.Context, *, args: Optional[str] = None) -> None:
        """Show alerts with optional filters.

        Usage:
            ``!alerts``
            ``!alerts severity=critical``
            ``!alerts room=Lab status=active limit=20``
        """
        filters: dict = {}
        if args:
            try:
                filters = _parse_filters(shlex.split(args))
            except ValueError as exc:
                await ctx.send(
                    embed=error_embed("\u274C Invalid filter", str(exc))
                )
                return

        try:
            alerts = await self.bot.backend.list_alerts(
                limit=filters.pop("limit", 25), **filters
            )
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendValidationError as exc:
            await ctx.send(
                embed=error_embed(
                    "\u274C Invalid filter",
                    f"The backend rejected these filters: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !alerts")
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return

        embed = alerts_embed(alerts, limit=10)
        if filters:
            applied = ", ".join(f"{k}={v}" for k, v in sorted(filters.items()))
            embed.set_footer(text=f"Filters: {applied}")
        await ctx.send(embed=embed)

    @commands.command(name="alert", aliases=["alertinfo"])
    async def alert_command(self, ctx: commands.Context, alert_id: int) -> None:
        """Show full details for a single alert, including the timeline."""
        try:
            alert = await self.bot.backend.get_alert(alert_id)
        except BackendNotFound:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50E Alert not found",
                    f"No alert with id **{alert_id}** exists.",
                )
            )
            return
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !alert")
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return

        embed = alert_detail_embed(alert)
        await ctx.send(
            embed=embed,
            view=_AlertActionsView(alert_id=alert.id, bot=self.bot, requester=ctx.author),
        )

    @commands.command(name="ack", aliases=["acknowledge"])
    async def ack_command(self, ctx: commands.Context, alert_id: int) -> None:
        """Acknowledge an alert by its numeric ID (``!ack 3``)."""
        try:
            updated: Alert = await self.bot.backend.acknowledge_alert(
                alert_id, acknowledged_by=ctx.author.display_name
            )
        except BackendNotFound:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50E Alert not found",
                    f"No alert with id **{alert_id}** is currently open. "
                    "It may have already been acknowledged.",
                )
            )
            return
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !ack")
            await ctx.send(
                embed=error_embed(
                    "\u274C Backend error",
                    f"The backend refused the acknowledgement: {exc}",
                )
            )
            return

        color = _alert_severity_color(updated.severity)
        embed = discord.Embed(
            title=f"✅ Alert acknowledged ({updated.severity})",
            description=updated.message,
            color=color,
        )
        embed.add_field(name="ID", value=str(updated.id), inline=True)
        embed.add_field(
            name="Status",
            value=f"{_alert_status_glyph(updated.status)} {updated.status}",
            inline=True,
        )
        if updated.room:
            embed.add_field(name="Room", value=updated.room, inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="dismiss", aliases=["snooze", "mute"])
    async def dismiss_command(
        self,
        ctx: commands.Context,
        alert_id: int,
        duration: Optional[int] = None,
    ) -> None:
        """Dismiss an alert for N minutes (default 30)."""
        try:
            updated: Alert = await self.bot.backend.dismiss_alert(
                alert_id,
                duration_minutes=duration,
                dismissed_by=ctx.author.display_name,
            )
        except BackendNotFound:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50E Alert not found",
                    f"No alert with id **{alert_id}** is currently open.",
                )
            )
            return
        except BackendValidationError as exc:
            await ctx.send(
                embed=error_embed(
                    "\u274C Invalid duration",
                    f"The backend rejected the dismiss request: {exc}",
                )
            )
            return
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !dismiss")
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return

        embed = discord.Embed(
            title=f"🔕 Alert dismissed ({updated.severity})",
            description=updated.message,
            color=_alert_severity_color(updated.severity),
        )
        embed.add_field(name="ID", value=str(updated.id), inline=True)
        embed.add_field(
            name="Status",
            value=f"{_alert_status_glyph(updated.status)} {updated.status}",
            inline=True,
        )
        if updated.dismissed_until:
            embed.add_field(
                name="Quiet until",
                value=_short_dt(updated.dismissed_until),
                inline=True,
            )
        embed.set_footer(text=f"Dismissed by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="resolve")
    @commands.has_permissions(manage_messages=True)
    async def resolve_command(self, ctx: commands.Context, alert_id: int) -> None:
        """Mark an alert resolved. Requires the *Manage Messages* permission."""
        try:
            updated: Alert = await self.bot.backend.resolve_alert(alert_id)
        except BackendNotFound:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50E Alert not found",
                    f"No alert with id **{alert_id}** is currently open.",
                )
            )
            return
        except BackendConnectionError as exc:
            await ctx.send(
                embed=error_embed(
                    "\U0001F50C Backend unreachable",
                    f"Could not reach the FastAPI backend: {exc}",
                )
            )
            return
        except BackendError as exc:
            logger.exception("Backend error in !resolve")
            await ctx.send(embed=error_embed("\u274C Backend error", f"{exc}"))
            return

        embed = discord.Embed(
            title=f"✅ Alert resolved ({updated.severity})",
            description=updated.message,
            color=_alert_severity_color(updated.severity),
        )
        embed.add_field(name="ID", value=str(updated.id), inline=True)
        if updated.room:
            embed.add_field(name="Room", value=updated.room, inline=True)
        embed.set_footer(text=f"Resolved by {ctx.author.display_name}")
        await ctx.send(embed=embed)


# ----- interactive buttons ----------------------------------------------- #


def _short_dt(value) -> str:
    import datetime as _dt

    if value.tzinfo is None:
        value = value.replace(tzinfo=_dt.timezone.utc)
    return discord.utils.format_dt(value, style="R")


class _AlertActionsView(discord.ui.View):
    """Acknowledge / Dismiss / Show buttons shown on `!alert <id>` embeds."""

    def __init__(
        self,
        *,
        alert_id: int,
        bot: "EnergyBot",
        requester: discord.abc.User,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.alert_id = alert_id
        self.bot = bot
        self.requester = requester

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only the user who issued the command may press the buttons.
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "Only the requester can use these buttons.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Acknowledge", style=discord.ButtonStyle.success, emoji="✅")
    async def ack_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            updated = await self.bot.backend.acknowledge_alert(
                self.alert_id, acknowledged_by=interaction.user.display_name
            )
        except BackendError as exc:
            await interaction.followup.send(
                embed=error_embed("\u274C Failed", f"{exc}"), ephemeral=True
            )
            return
        await interaction.followup.send(
            f"✅ Alert **#{updated.id}** acknowledged.", ephemeral=True
        )

    @discord.ui.button(label="Dismiss 30m", style=discord.ButtonStyle.secondary, emoji="🔕")
    async def dismiss_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            updated = await self.bot.backend.dismiss_alert(
                self.alert_id,
                duration_minutes=30,
                dismissed_by=interaction.user.display_name,
            )
        except BackendError as exc:
            await interaction.followup.send(
                embed=error_embed("\u274C Failed", f"{exc}"), ephemeral=True
            )
            return
        await interaction.followup.send(
            f"🔕 Alert **#{updated.id}** dismissed for 30 minutes.", ephemeral=True
        )

    @discord.ui.button(label="Resolve", style=discord.ButtonStyle.danger, emoji="🛠️")
    async def resolve_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not interaction.user.guild_permissions or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You need the *Manage Messages* permission to resolve alerts.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self.bot.backend.resolve_alert(self.alert_id)
        except BackendError as exc:
            await interaction.followup.send(
                embed=error_embed("\u274C Failed", f"{exc}"), ephemeral=True
            )
            return
        await interaction.followup.send(
            f"🛠️ Alert **#{self.alert_id}** marked resolved.", ephemeral=True
        )


async def setup(bot: "EnergyBot") -> None:
    await bot.add_cog(AlertsCog(bot))