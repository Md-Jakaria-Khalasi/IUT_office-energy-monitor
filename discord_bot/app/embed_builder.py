"""Shared helpers that turn backend models into Discord embeds.

Keeping every visual decision in one module means commands stay focused on
data fetching and orchestration; the formatting rules live here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence

import discord

from .models import (
    Activity,
    Alert,
    AlertSummary,
    Device,
    OverviewStats,
    RoomSummary,
)

# ----------------------------------------------------------------- constants   #
EMBED_COLOR_OK = 0x2ECC71        # green
EMBED_COLOR_INFO = 0x3498DB       # blue
EMBED_COLOR_WARNING = 0xF1C40F    # yellow
EMBED_COLOR_CRITICAL = 0xE74C3C   # red
EMBED_COLOR_MUTED = 0x95A5A6      # grey

SEVERITY_COLORS = {
    "info": EMBED_COLOR_INFO,
    "warning": EMBED_COLOR_WARNING,
    "critical": EMBED_COLOR_CRITICAL,
}

SEVERITY_GLYPH = {
    "info": "\u2139\ufe0f",        # ℹ️
    "warning": "\u26a0\ufe0f",     # ⚠️
    "critical": "\U0001F6A8",      # 🚨
}

STATUS_GLYPH = {
    "active": "\U0001F534",        # 🔴
    "acknowledged": "\U0001F7E1",  # 🟡
    "dismissed": "\U0001F7E2",     # 🟢
    "resolved": "\u2705",          # ✅
}

ALERT_TYPE_LABELS = {
    "after_hours_device": "After-hours device",
    "room_continuous": "Room running continuously",
    "critical_power": "Critical power draw",
    "office_consumption": "High office consumption",
}


# ----------------------------------------------------------------- helpers     #
def _format_timestamp(value: datetime) -> str:
    """Render a datetime as a Discord timestamp string."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return discord.utils.format_dt(value, style="f")


def _short_timestamp(value: Optional[datetime]) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return discord.utils.format_dt(value, style="R")


def _truncate(text: str, limit: int = 1024) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _alert_severity_color(severity: str) -> int:
    """Return the embed color matching the given alert severity."""
    return SEVERITY_COLORS.get(severity, EMBED_COLOR_INFO)


def _alert_status_glyph(status: str) -> str:
    return STATUS_GLYPH.get(status, "•")


def _alert_type_label(alert_type: str) -> str:
    return ALERT_TYPE_LABELS.get(alert_type, alert_type.replace("_", " ").title())


def _format_kwh(value: float) -> str:
    """Render a kWh value with adaptive precision."""
    if value >= 10:
        return f"{value:.1f} kWh"
    if value >= 1:
        return f"{value:.2f} kWh"
    return f"{value:.3f} kWh"


def _format_usd(value: float) -> str:
    """Render a USD value with adaptive precision."""
    if value >= 100:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:.2f}"
    return f"${value:.2f}"


def _known_room_names(rooms: Iterable[str]) -> str:
    """Render a list of room names the way ``help_embed`` expects them."""
    names = [name for name in rooms if name]
    if not names:
        return "_No rooms yet._"
    return ", ".join(names)


def _format_age(alert: Alert) -> str:
    """Render how long ago an alert was raised."""
    now = datetime.now(timezone.utc)
    created = alert.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    seconds = max(0, int((now - created).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"


# ----------------------------------------------------------------- overview    #
def overview_embed(stats: OverviewStats) -> discord.Embed:
    """Build the embed returned by ``!status``."""
    embed = discord.Embed(
        title="\U0001F4CA Office Energy Monitor",   # 📊
        color=EMBED_COLOR_INFO,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="Total devices",
        value=f"`{stats.total_devices}`",
        inline=True,
    )
    embed.add_field(
        name="Active devices",
        value=f"`{stats.active_devices}`",
        inline=True,
    )
    embed.add_field(
        name="Live power draw",
        value=f"`{stats.total_power:.1f} W`",
        inline=True,
    )
    embed.add_field(
        name="Active alerts",
        value=f"`{stats.active_alerts}`",
        inline=True,
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    if stats.rooms:
        lines = [
            f"**{room.room}** — {room.active_devices}/{room.total_devices} on · "
            f"{room.total_power:.1f} W"
            for room in stats.rooms
        ]
        embed.add_field(
            name="Per-room summary",
            value=_truncate("\n".join(lines), 1024),
            inline=False,
        )

    embed.set_footer(text="Data fetched live from the backend.")
    return embed


# ----------------------------------------------------------------- rooms       #
def room_embed(
    room: RoomSummary, devices: Iterable[Device]
) -> discord.Embed:
    """Build the embed returned by ``!room <name>``."""
    devices_list = list(devices)
    embed = discord.Embed(
        title=f"\U0001F3E0 {room.room}",   # 🏠
        color=EMBED_COLOR_OK if room.active_devices > 0 else EMBED_COLOR_MUTED,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="Active / total",
        value=f"`{room.active_devices}` / `{room.total_devices}`",
        inline=True,
    )
    embed.add_field(
        name="Live power",
        value=f"`{room.total_power:.1f} W`",
        inline=True,
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    if not devices_list:
        embed.description = "_No devices reported for this room._"
        embed.set_footer(text="Data fetched live from the backend.")
        return embed

    lines: List[str] = []
    for device in devices_list:
        glyph = "\U0001F7E2" if device.status == "on" else "\u26AB"   # 🟢 / ⚫
        lines.append(
            f"{glyph} **{device.name}** (`#{device.id}` · {device.type}) — "
            f"{device.power_consumption:.1f} W · {device.status.upper()}"
        )
    embed.add_field(
        name="Devices",
        value=_truncate("\n".join(lines), 1024),
        inline=False,
    )
    embed.set_footer(text="Data fetched live from the backend.")
    return embed


def room_not_found_embed(query: str, known_rooms: Iterable[str]) -> discord.Embed:
    embed = discord.Embed(
        title="❓ Unknown room",
        description=f"Could not find a room matching **{query}**.",
        color=EMBED_COLOR_WARNING,
    )
    embed.add_field(
        name="Available rooms",
        value="\n".join(f"• {name}" for name in known_rooms) or "_(none)_",
        inline=False,
    )
    return embed


# ----------------------------------------------------------------- usage       #
def usage_embed(activities: List[Activity], rooms: List[RoomSummary]) -> discord.Embed:
    """Build the embed returned by ``!usage``."""
    embed = discord.Embed(
        title="⚡ Recent power usage",
        color=EMBED_COLOR_INFO,
        timestamp=datetime.now(timezone.utc),
    )

    if rooms:
        top = sorted(rooms, key=lambda r: r.total_power, reverse=True)[:3]
        lines = [
            f"**{room.room}** — {room.total_power:.1f} W "
            f"({room.active_devices}/{room.total_devices} active)"
            for room in top
        ]
        embed.add_field(
            name="Top rooms by current draw",
            value="\n".join(lines),
            inline=False,
        )

    if not activities:
        embed.description = "_No activity recorded yet._"
        embed.set_footer(text="Data fetched live from the backend.")
        return embed

    lines = [
        f"`{_short_timestamp(act.created_at)}` "
        f"**{act.device_name}** ({act.room}) — {act.description}"
        for act in activities[:10]
    ]
    embed.add_field(
        name="Latest activity",
        value=_truncate("\n".join(lines), 1024),
        inline=False,
    )
    embed.set_footer(text=f"Showing {min(len(activities), 10)} of {len(activities)} entries.")
    return embed


# ----------------------------------------------------------------- alerts      #
def _alert_location(alert: Alert) -> str:
    """Render a one-line location string for an alert."""
    if alert.involved_rooms:
        rooms = ", ".join(alert.involved_rooms[:3])
        if len(alert.involved_rooms) > 3:
            rooms += f" (+{len(alert.involved_rooms) - 3})"
        if alert.room and alert.room not in alert.involved_rooms:
            rooms = f"{alert.room} · {rooms}"
        return rooms or alert.room or "office"
    if alert.room:
        return alert.room
    if alert.device_id is not None:
        return f"device #{alert.device_id}"
    return "office"


def _alert_waste_line(alert: Alert) -> Optional[str]:
    """Render a one-line summary of waste/cost, or None if both zero."""
    kwh = float(alert.energy_waste_kwh or 0.0)
    usd = float(alert.estimated_cost_usd or 0.0)
    if kwh <= 0 and usd <= 0:
        return None
    parts = []
    if kwh > 0:
        parts.append(_format_kwh(kwh))
    if usd > 0:
        parts.append(_format_usd(usd))
    return " · ".join(parts)


def alerts_embed(
    alerts: List[Alert],
    *,
    limit: int = 10,
    title: str = "\U0001F514 Active alerts",   # 🔔
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        color=EMBED_COLOR_WARNING,
        timestamp=datetime.now(timezone.utc),
    )
    if not alerts:
        embed.description = "✅ No active alerts."
        embed.color = EMBED_COLOR_OK
        embed.set_footer(text="Data fetched live from the backend.")
        return embed

    lines = []
    for alert in alerts[:limit]:
        glyph = SEVERITY_GLYPH.get(alert.severity, "•")
        status = _alert_status_glyph(alert.status)
        location = _alert_location(alert)
        waste = _alert_waste_line(alert)
        meta = f"{status} `{alert.status}` · {location} · {_short_timestamp(alert.created_at)}"
        if waste:
            meta = f"{meta} · {waste}"
        lines.append(
            f"{glyph} `{alert.id}` **{alert.severity.upper()}** — {alert.message}\n"
            f"   _{meta}_"
        )
    embed.description = _truncate("\n".join(lines), 4096)
    footer = f"Showing {min(len(alerts), limit)} of {len(alerts)} alerts."
    embed.set_footer(text=footer)
    return embed


def alert_notification_embed(alert: Alert) -> discord.Embed:
    """Embed posted by the watcher for a freshly seen / escalated alert."""
    color = SEVERITY_COLORS.get(alert.severity, EMBED_COLOR_INFO)
    glyph = SEVERITY_GLYPH.get(alert.severity, "\U0001F514")
    title_suffix = ""
    if alert.escalated_at and alert.escalated_at >= (
        alert.created_at.replace(tzinfo=alert.created_at.tzinfo or timezone.utc)
    ):
        title_suffix = " (escalated)"
    embed = discord.Embed(
        title=f"{glyph} New {alert.severity} alert{title_suffix}",
        description=alert.message,
        color=color,
        timestamp=alert.created_at,
    )
    embed.add_field(name="Type", value=_alert_type_label(alert.alert_type), inline=True)
    embed.add_field(name="Status", value=f"{_alert_status_glyph(alert.status)} {alert.status}", inline=True)
    embed.add_field(name="Location", value=_alert_location(alert), inline=True)

    if alert.peak_power_w:
        embed.add_field(name="Peak power", value=f"`{alert.peak_power_w:.0f} W`", inline=True)
    waste = _alert_waste_line(alert)
    if waste:
        embed.add_field(name="Impact", value=waste, inline=True)
    embed.add_field(
        name="Triggered",
        value=_format_timestamp(alert.created_at),
        inline=True,
    )
    embed.set_footer(text=f"Alert ID #{alert.id} · use !alert {alert.id} for details")
    return embed


def alert_detail_embed(alert: Alert) -> discord.Embed:
    """Embed returned by ``!alert <id>`` with full lifecycle info."""
    color = SEVERITY_COLORS.get(alert.severity, EMBED_COLOR_INFO)
    glyph = SEVERITY_GLYPH.get(alert.severity, "\U0001F514")
    embed = discord.Embed(
        title=f"{glyph} Alert #{alert.id} — {_alert_type_label(alert.alert_type)}",
        description=alert.message,
        color=color,
        timestamp=alert.last_evaluated_at or alert.created_at,
    )
    embed.add_field(name="Severity", value=alert.severity.upper(), inline=True)
    embed.add_field(
        name="Status",
        value=f"{_alert_status_glyph(alert.status)} {alert.status}",
        inline=True,
    )
    embed.add_field(name="Age", value=_format_age(alert), inline=True)

    embed.add_field(name="Location", value=_alert_location(alert), inline=True)
    if alert.peak_power_w:
        embed.add_field(name="Peak power", value=f"`{alert.peak_power_w:.0f} W`", inline=True)
    waste = _alert_waste_line(alert)
    if waste:
        embed.add_field(name="Energy / cost", value=waste, inline=True)

    if alert.acknowledged:
        embed.add_field(
            name="Acknowledged",
            value=f"by **{alert.acknowledged_by or 'unknown'}** · {_short_timestamp(alert.acknowledged_at)}",
            inline=True,
        )
    if alert.dismissed:
        embed.add_field(
            name="Dismissed",
            value=(
                f"by **{alert.dismissed_by or 'unknown'}** until "
                f"{_short_timestamp(alert.dismissed_until)}"
            ),
            inline=True,
        )

    embed.add_field(
        name="Timeline",
        value=_format_severity_history(alert.severity_history),
        inline=False,
    )

    embed.set_footer(text=f"Alert ID #{alert.id}")
    return embed


def _format_severity_history(history: Sequence) -> str:
    """Render the severity history timeline."""
    if not history:
        return "_No escalation steps recorded._"
    lines: List[str] = []
    for entry in history:
        severity = entry.severity if hasattr(entry, "severity") else entry.get("severity", "?")
        at = entry.at if hasattr(entry, "at") else entry.get("at")
        reason = entry.reason if hasattr(entry, "reason") else entry.get("reason")
        glyph = SEVERITY_GLYPH.get(severity, "•")
        line = f"{glyph} **{severity.upper()}** — {_short_timestamp(at)}"
        if reason:
            line += f" · {reason}"
        lines.append(line)
    return _truncate("\n".join(lines), 1024)


# ----------------------------------------------------------------- summary     #
def alert_summary_embed(summary: AlertSummary) -> discord.Embed:
    """Embed for ``!summary``."""
    color = EMBED_COLOR_CRITICAL if summary.critical else (
        EMBED_COLOR_WARNING if summary.warning else EMBED_COLOR_OK
    )
    embed = discord.Embed(
        title="\U0001F4CA Alert summary",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Total active", value=f"`{summary.total_active}`", inline=True)
    embed.add_field(name="Critical", value=f"`{summary.critical}`", inline=True)
    embed.add_field(name="Warning", value=f"`{summary.warning}`", inline=True)
    embed.add_field(name="Info", value=f"`{summary.info}`", inline=True)
    embed.add_field(name="Acknowledged", value=f"`{summary.acknowledged}`", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(
        name="Waste today",
        value=_format_kwh(summary.estimated_waste_kwh_today),
        inline=True,
    )
    embed.add_field(
        name="Cost today",
        value=_format_usd(summary.estimated_cost_usd_today),
        inline=True,
    )
    return embed


def dashboard_embed(
    stats: OverviewStats,
    summary: Optional[AlertSummary] = None,
) -> discord.Embed:
    """Compact text dashboard returned by ``!dashboard``."""
    embed = discord.Embed(
        title="\U0001F39B️ Energy dashboard",   # 🎛️
        color=EMBED_COLOR_INFO,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Devices", value=f"`{stats.active_devices}/{stats.total_devices}`", inline=True)
    embed.add_field(name="Power", value=f"`{stats.total_power:.1f} W`", inline=True)
    embed.add_field(name="Active alerts", value=f"`{stats.active_alerts}`", inline=True)

    if stats.rooms:
        lines = [
            f"**{room.room}** — {room.active_devices}/{room.total_devices} on · {room.total_power:.1f} W"
            for room in stats.rooms[:8]
        ]
        embed.add_field(
            name="Rooms",
            value=_truncate("\n".join(lines), 1024),
            inline=False,
        )

    if summary is not None:
        embed.add_field(
            name="Today",
            value=(
                f"{summary.critical} critical · {summary.warning} warning · "
                f"{summary.acknowledged} acknowledged\n"
                f"Waste: {_format_kwh(summary.estimated_waste_kwh_today)} · "
                f"Cost: {_format_usd(summary.estimated_cost_usd_today)}"
            ),
            inline=False,
        )

    embed.set_footer(text="Run !alerts for the full list.")
    return embed


# ----------------------------------------------------------------- error / help
def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=EMBED_COLOR_CRITICAL)


def help_embed(
    prefix: str, rooms: Optional[Iterable[str]] = None
) -> discord.Embed:
    """Build the ``!help`` embed. ``rooms`` lists the actual configured rooms so
    the help text never goes stale if the backend adds or renames a room."""
    embed = discord.Embed(
        title="\U0001F4D8 Office Energy Monitor — Commands",   # 📘
        color=EMBED_COLOR_INFO,
        timestamp=datetime.now(timezone.utc),
    )
    room_label = _known_room_names(rooms or [])
    embed.description = (
        "All commands pull data live from the Office Energy backend. "
        f"Prefix: `{prefix}`"
    )
    sections = [
        (
            "📊 Overview",
            [
                ("status", "Quick office overview (devices, power, active alerts)."),
                ("room <name>", f"Room-specific stats. Available rooms: {room_label}."),
                ("usage", "Recent activity feed and top rooms by current power draw."),
                ("summary", "Alert counts by severity plus waste/cost today."),
                ("dashboard", "Compact single-screen energy + alert dashboard."),
                ("devices", "List every device with current status and power."),
                ("power", "Current power draw per room with totals."),
                ("help", "Show this message."),
            ],
        ),
        (
            "🔔 Alerts",
            [
                ("alerts [filters]", "List alerts. Filters: `severity`, `status`, `room`, `type`, `active`."),
                ("alert <id>", "Show full details for a single alert including timeline."),
                ("ack <id>", "Acknowledge an alert by its numeric ID."),
                ("dismiss <id> [minutes]", "Snooze an alert for N minutes (default 30)."),
                ("resolve <id>", "Mark an alert resolved (admin only)."),
            ],
        ),
        (
            "⚡ Actions",
            [
                ("off device <id|name>", "Turn a single device off."),
                ("off room <name>", "Turn every device in a room off."),
                ("off all", "Turn every active device off."),
            ],
        ),
    ]
    for section_title, commands in sections:
        body = "\n".join(
            f"`{prefix}{name}` — {desc}" for name, desc in commands
        )
        embed.add_field(name=section_title, value=_truncate(body, 1024), inline=False)
    embed.set_footer(text="Use !alerts to inspect active alerts in detail.")
    return embed


__all__ = [
    "ALERT_TYPE_LABELS",
    "EMBED_COLOR_CRITICAL",
    "EMBED_COLOR_INFO",
    "EMBED_COLOR_MUTED",
    "EMBED_COLOR_OK",
    "EMBED_COLOR_WARNING",
    "SEVERITY_COLORS",
    "SEVERITY_GLYPH",
    "STATUS_GLYPH",
    "_alert_severity_color",
    "_alert_status_glyph",
    "_alert_type_label",
    "alert_detail_embed",
    "alert_notification_embed",
    "alert_summary_embed",
    "alerts_embed",
    "dashboard_embed",
    "error_embed",
    "help_embed",
    "overview_embed",
    "room_embed",
    "room_not_found_embed",
    "usage_embed",
]