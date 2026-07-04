"""EnergyBot — the Discord entry point.

Responsibilities of this module:

* Load every cog under :mod:`app.cogs` automatically.
* Start/stop the :class:`~app.services.alert_watcher.AlertWatcher`.
* Manage the lifetime of the shared :class:`~app.api_client.BackendClient`.
* Provide ``run()`` for ``python -m app.bot`` (used by ``Dockerfile``).
* Provide light-weight natural-language routing for plain-English messages
  like ``turn off the lab`` or ``show me the dashboard``.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import pkgutil
import re
from typing import Awaitable, List, Optional

import discord
from discord.ext import commands

from .api_client import BackendClient
from .config import get_settings
from .services.alert_watcher import AlertWatcher

logger = logging.getLogger(__name__)


def _configure_logging(level_name: str) -> None:
    level = logging.getLevelName(level_name.upper())
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


class EnergyBot(commands.Bot):
    """Top-level bot instance."""

    def __init__(self) -> None:
        self._settings = get_settings()
        _configure_logging(self._settings.log_level)

        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=self._settings.command_prefix,
            intents=intents,
            description="Office Energy Monitor — Discord companion bot.",
        )

        # Suppress discord.py's built-in ``!help`` so our custom HelpCog is the
        # only command responding to that name.
        self.remove_command("help")

        self.backend = BackendClient(self._settings)
        self.alert_watcher = AlertWatcher(
            client=self.backend,
            settings=self._settings,
            bot=self,
            channel_id=self._settings.alert_channel_id,
        )

    # ----------------------------------------------------------------- lifecycle
    async def setup_hook(self) -> None:  # noqa: D401 - discord.py hook
        """Connect to the backend, verify it is reachable, then load cogs."""
        await self.backend.start()
        await self._wait_for_backend(max_attempts=10, delay=1.0)
        await self._load_cogs()
        await self.alert_watcher.start()
        logger.info(
            "EnergyBot ready (prefix=%s, backend=%s, alert_channel=%s)",
            self.command_prefix,
            self._settings.api_base,
            self._settings.alert_channel_id,
        )

    async def _wait_for_backend(self, *, max_attempts: int, delay: float) -> None:
        """Ping ``/healthz`` repeatedly until the backend reports healthy."""
        for attempt in range(1, max_attempts + 1):
            try:
                if await self.backend.healthcheck():
                    return
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Backend healthcheck attempt %d/%d raised: %s",
                    attempt,
                    max_attempts,
                    exc,
                )
            if attempt < max_attempts:
                await asyncio.sleep(delay)
        logger.warning(
            "Backend not reachable after %d attempts; continuing anyway.",
            max_attempts,
        )

    async def close(self) -> None:
        """Cleanly shut down backend and watcher."""
        try:
            await self.alert_watcher.stop()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error stopping alert watcher: %s", exc)
        try:
            await self.backend.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error closing backend client: %s", exc)
        await super().close()

    # ----------------------------------------------------------------- events
    async def on_ready(self) -> None:
        if self.user is None:
            return
        logger.info("Logged in as %s (id=%s)", self.user, self.user.id)
        logger.info(
            "Connected to %d guild(s); command_prefix=%r",
            len(self.guilds),
            self.command_prefix,
        )

    async def on_message(self, message: discord.Message) -> None:
        """Route natural-language requests before command processing."""
        if message.author.bot:
            return
        if not self.is_ready():
            return
        routed = await self._maybe_route_natural_language(message)
        # Always let the command processor run so explicit ``!foo`` still works.
        await self.process_commands(message)

    async def _maybe_route_natural_language(
        self, message: discord.Message
    ) -> bool:
        """If the message looks like plain English, route it to the right cog."""
        content = (message.content or "").strip()
        if not content:
            return False
        if content.startswith(self.command_prefix):
            return False  # explicit command
        if content.startswith("/"):
            return False  # slash command handled elsewhere
        if message.mention_everyone or content.startswith("@"):
            return False
        lowered = content.lower()
        handler = _classify_natural_language(lowered)
        if handler is None:
            return False
        invoker, route = handler
        ctx = await self.get_context(message)
        if ctx is None:
            return False
        await invoker(self, ctx, route)
        return True

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Translate common errors into user-friendly messages."""
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=discord.Embed(
                    title="🔒 Permission denied",
                    description=str(error),
                    color=0xE74C3C,
                )
            )
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                embed=discord.Embed(
                    title="❓ Missing argument",
                    description=str(error),
                    color=0xE74C3C,
                )
            )
            return
        if isinstance(error, commands.CommandInvokeError):
            logger.exception(
                "Command %s raised", ctx.command, exc_info=error.original
            )
            await ctx.send(
                embed=discord.Embed(
                    title="⌛ Unexpected error",
                    description=(
                        "Something went wrong while running this command. "
                        "Check the bot logs for details."
                    ),
                    color=0xE74C3C,
                )
            )
            return
        logger.warning("Unhandled command error: %r", error)

    # ----------------------------------------------------------------- helpers
    async def _load_cogs(self) -> None:
        """Auto-discover and load every module under ``app.cogs``."""
        import app.cogs as cogs_pkg

        loaded: List[str] = []
        for module_info in pkgutil.iter_modules(cogs_pkg.__path__):
            if module_info.name.startswith("_"):
                continue
            module = importlib.import_module(f"app.cogs.{module_info.name}")
            setup = getattr(module, "setup", None)
            if setup is None:
                logger.warning("Cog %s has no setup() — skipping.", module_info.name)
                continue
            try:
                await setup(self)
                loaded.append(module_info.name)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Failed to load cog %s: %s", module_info.name, exc)
        logger.info("Loaded cogs: %s", ", ".join(loaded) or "<none>")


# --------------------------------------------------------------------- natural language


# Patterns are intentionally conservative — we only auto-route when we are
# reasonably sure. Anything ambiguous stays in the help channel.
_OFF_PATTERNS = [
    re.compile(r"\bturn\s+(?:off|down)\b"),
    re.compile(r"\bshut\s+(?:down|off)\b"),
    re.compile(r"\bkill\s+(?:the\s+)?(?:lights?|power)\b"),
    re.compile(r"\bpower\s+down\b"),
]
_ALERTS_PATTERNS = [
    re.compile(r"\bwhat\s+alerts?\b"),
    re.compile(r"\bopen\s+(?:the\s+)?alerts?\b"),
    re.compile(r"\bactive\s+alerts?\b"),
    re.compile(r"\bany\s+alerts?\b"),
    re.compile(r"\balert\s+(?:list|status)\b"),
]
_USAGE_PATTERNS = [
    re.compile(r"\bhow\s+much\s+energy\b"),
    re.compile(r"\benergy\s+(?:today|so\s+far|used)\b"),
    re.compile(r"\bwhat.s\s+(?:the\s+)?usage\b"),
    re.compile(r"\bpower\s+(?:now|currently|today)\b"),
    re.compile(r"\busage\s+(?:today|report)\b"),
]
_DASHBOARD_PATTERNS = [
    re.compile(r"\bshow\s+(?:me\s+)?(?:the\s+)?dashboard\b"),
    re.compile(r"\bopen\s+(?:the\s+)?dashboard\b"),
    re.compile(r"\bdashboard\b"),
]
_HELP_PATTERNS = [
    re.compile(r"^\s*help\s*$"),
    re.compile(r"\bwhat\s+can\s+you\s+do\b"),
    re.compile(r"\bhow\s+do\s+i\b"),
]


def _classify_natural_language(
    text: str,
) -> Optional[
    tuple[
        "EnergyBot._NLHandler",
        str,
    ]
]:
    """Return ``(handler, captured_target)`` if the text looks like a request.

    ``captured_target`` is whatever comes after the trigger verb (e.g. the
    room/device name after "turn off"), or ``""`` if not relevant.
    """
    for pattern in _OFF_PATTERNS:
        if pattern.search(text):
            target = _strip_target(text, pattern, verbs=("off", "down", "shutdown", "kill", "down"))
            return _handle_off, target
    for pattern in _ALERTS_PATTERNS:
        if pattern.search(text):
            return _handle_alerts, ""
    for pattern in _USAGE_PATTERNS:
        if pattern.search(text):
            return _handle_usage, ""
    for pattern in _DASHBOARD_PATTERNS:
        if pattern.search(text):
            return _handle_dashboard, ""
    for pattern in _HELP_PATTERNS:
        if pattern.search(text):
            return _handle_help, ""
    return None


def _strip_target(text: str, pattern: re.Pattern, *, verbs: tuple[str, ...]) -> str:
    """Return the trailing tail of ``text`` after the matched verb."""
    match = pattern.search(text)
    if not match:
        return ""
    tail = text[match.end():].strip(" .,!?")
    for prefix in ("the ", "a ", "an "):
        if tail.startswith(prefix):
            tail = tail[len(prefix):]
    for verb in verbs:
        prefix = verb + " "
        if tail.startswith(prefix):
            tail = tail[len(prefix):]
            break
    return tail.strip()


# type alias for natural-language handlers
EnergyBot._NLHandler = "callable[[EnergyBot, commands.Context, str], Awaitable[None]]"


async def _handle_off(
    bot: "EnergyBot", ctx: commands.Context, target: str
) -> None:
    """Route to ``!off`` with the captured target."""
    cog = bot.get_cog("OffCog")
    if cog is None:
        return
    if not target:
        # Fall back to `!off all` so the user isn't left hanging.
        await cog.off_command(ctx, "all")
        return
    if target.lower() in {"all", "everything", "office"}:
        await cog.off_command(ctx, "all")
        return
    # Heuristic: if the target matches a known room, route to room; else device.
    try:
        devices = await bot.backend.list_devices()
    except Exception:
        devices = []
    rooms = {d.room.lower() for d in devices}
    target_l = target.lower()
    if target_l in rooms or any(target_l in r for r in rooms):
        await cog.off_command(ctx, "room", target=target)
    else:
        await cog.off_command(ctx, "device", target=target)


async def _handle_alerts(
    bot: "EnergyBot", ctx: commands.Context, target: str
) -> None:
    cog = bot.get_cog("AlertsCog")
    if cog is None:
        return
    await cog.alerts.callback(cog, ctx)  # type: ignore[attr-defined]


async def _handle_usage(
    bot: "EnergyBot", ctx: commands.Context, target: str
) -> None:
    cog = bot.get_cog("UsageCog")
    if cog is None:
        return
    if hasattr(cog, "usage"):
        await cog.usage.callback(cog, ctx)  # type: ignore[attr-defined]


async def _handle_dashboard(
    bot: "EnergyBot", ctx: commands.Context, target: str
) -> None:
    cog = bot.get_cog("SummaryCog")
    if cog is None:
        return
    await cog.dashboard.callback(cog, ctx)  # type: ignore[attr-defined]


async def _handle_help(
    bot: "EnergyBot", ctx: commands.Context, target: str
) -> None:
    cog = bot.get_cog("HelpCog")
    if cog is None:
        return
    if hasattr(cog, "help"):
        await cog.help.callback(cog, ctx)  # type: ignore[attr-defined]


def run() -> None:
    """Entry point used by ``python -m app.bot`` and the Dockerfile."""
    settings = get_settings()
    bot = EnergyBot()
    try:
        bot.run(settings.discord_token, log_handler=None)
    except discord.LoginFailure as exc:
        raise RuntimeError(
            "Discord login failed. Verify DISCORD_TOKEN is correct and the "
            "bot has been invited to the guild."
        ) from exc


if __name__ == "__main__":  # pragma: no cover
    run()