"""Background alert watcher.

Polls the backend ``GET /alerts`` endpoint on a fixed interval and posts an
embed for every newly observed alert to the configured channel. Also handles
**escalation** (warning / critical re-posts) and **30-minute reminders** by
consulting the dedicated ``/alerts/due-reminders`` endpoint.

State (deduped IDs, last-reminder timestamps) is persisted to a JSON file
on disk so that bot restarts do not re-announce the same alerts that were
seen before shutdown.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Set

import discord

from ..api_client import BackendClient, BackendConnectionError, BackendError
from ..config import Settings
from ..embed_builder import alert_notification_embed, error_embed
from ..models import Alert

logger = logging.getLogger(__name__)


def _default_state_path() -> Path:
    """Resolve the default path for the persistence file.

    Honors ``ALERT_WATCHER_STATE_PATH`` so Docker can mount a volume; falls
    back to ``./.alert_watcher_state.json`` for local development.
    """
    override = os.getenv("ALERT_WATCHER_STATE_PATH")
    if override:
        return Path(override)
    return Path.cwd() / ".alert_watcher_state.json"


class AlertWatcher:
    """Periodically forwards new + escalated alerts to a Discord channel."""

    def __init__(
        self,
        client: BackendClient,
        *,
        settings: Settings,
        bot: discord.Client,
        channel_id: Optional[int],
        state_path: Optional[Path] = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._bot = bot
        self._channel_id = channel_id
        self._task: Optional[asyncio.Task] = None
        self._reminder_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._seen: Set[int] = set()
        # alert_id -> severity last announced (for escalation reposts)
        self._last_severity: Dict[int, str] = {}
        # alert_id -> monotonic timestamp of last reminder
        self._last_reminded: Dict[int, float] = {}
        self._state_path = state_path or _default_state_path()

    # ----------------------------------------------------------------- persist
    def _load_seen(self) -> Set[int]:
        if not self._state_path.exists():
            return set()
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Could not read alert state file %s: %s", self._state_path, exc
            )
            return set()
        ids = {int(x) for x in data.get("seen_ids", []) if str(x).isdigit()}
        # Cap memory on disk: only keep the most recent 500 IDs.
        if len(ids) > 500:
            ids = set(sorted(ids, reverse=True)[:500])
        logger.info("Loaded %d seen alert IDs from %s", len(ids), self._state_path)
        return ids

    def _save_seen(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(
                    {
                        "seen_ids": sorted(self._seen),
                        "last_severity": {
                            str(k): v for k, v in self._last_severity.items()
                        },
                        "last_reminded_at": {
                            str(k): v for k, v in self._last_reminded.items()
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            os.replace(tmp, self._state_path)
        except OSError as exc:
            logger.warning(
                "Could not persist alert state to %s: %s", self._state_path, exc
            )

    # ----------------------------------------------------------------- public
    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def reminder_running(self) -> bool:
        return self._reminder_task is not None and not self._reminder_task.done()

    async def start(self) -> None:
        """Start the polling + reminder tasks. No-op if disabled."""
        if not self._channel_id:
            logger.warning(
                "AlertWatcher disabled: ALERT_CHANNEL_ID is not configured."
            )
            return
        if not self.is_running:
            self._seen = self._load_seen()
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run(), name="alert-watcher")
            logger.info(
                "AlertWatcher started (channel=%s, interval=%.1fs, seen=%d)",
                self._channel_id,
                self._settings.poll_interval_seconds,
                len(self._seen),
            )
        if not self.reminder_running:
            self._reminder_task = asyncio.create_task(
                self._run_reminders(), name="alert-reminders"
            )
            logger.info("AlertWatcher reminder loop started")

    async def stop(self) -> None:
        """Signal all tasks to stop and wait for them to finish."""
        self._stop_event.set()
        for task in (self._task, self._reminder_task):
            if not task:
                continue
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._task = None
        self._reminder_task = None
        self._save_seen()
        logger.info(
            "AlertWatcher stopped (persisted %d seen IDs)",
            len(self._seen),
        )

    # ----------------------------------------------------------------- internals
    async def _run(self) -> None:
        interval = self._settings.poll_interval_seconds
        while not self._stop_event.is_set():
            try:
                await self._tick()
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("AlertWatcher tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        try:
            alerts = await self._client.list_alerts(
                limit=self._settings.alert_poll_limit
            )
        except BackendConnectionError as exc:
            logger.warning("AlertWatcher could not reach backend: %s", exc)
            return
        except BackendError as exc:
            logger.warning("AlertWatcher backend error: %s", exc)
            return

        # Backfill seen IDs on the first poll so we only notify about new ones.
        if not self._seen:
            self._seen = {alert.id for alert in alerts}

        new_alerts = [a for a in alerts if a.id not in self._seen]
        # An escalation also requires a post even if the alert was previously seen.
        if not new_alerts:
            for alert in alerts:
                prev = self._last_severity.get(alert.id)
                if prev is not None and prev != alert.severity:
                    new_alerts.append(alert)
                    break
        if not new_alerts:
            return

        channel = await self._resolve_channel()
        if channel is None:
            logger.warning(
                "AlertWatcher cannot post: channel %s is unavailable.",
                self._channel_id,
            )
            return

        posted_anything = False
        for alert in new_alerts:
            # ---- new alerts --------------------------------------------------
            if alert.id not in self._seen:
                try:
                    embed = alert_notification_embed(alert)
                    await channel.send(embed=embed)
                except discord.DiscordException as exc:
                    logger.error(
                        "Failed to post alert #%s: %s", alert.id, exc
                    )
                    continue
                self._seen.add(alert.id)
                self._last_severity[alert.id] = alert.severity
                posted_anything = True
                continue

            # ---- escalations -------------------------------------------------
            prev_severity = self._last_severity.get(alert.id)
            if prev_severity != alert.severity:
                try:
                    embed = alert_notification_embed(alert)
                    await channel.send(embed=embed)
                except discord.DiscordException as exc:
                    logger.error(
                        "Failed to post escalation for #%s: %s", alert.id, exc
                    )
                self._last_severity[alert.id] = alert.severity
                posted_anything = True

        if posted_anything:
            self._save_seen()

    async def _run_reminders(self) -> None:
        """Re-post active alerts whose last reminder was >= 30 min ago."""
        # Use a slightly shorter loop so we catch the boundary promptly.
        interval = max(60.0, self._settings.poll_interval_seconds)
        loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            try:
                await self._reminder_tick(loop)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Reminder tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _reminder_tick(self, loop: asyncio.AbstractEventLoop) -> None:
        try:
            due = await self._client.get_due_reminders()
        except BackendConnectionError as exc:
            logger.warning("Reminder poll failed: backend unreachable: %s", exc)
            return
        except BackendError as exc:
            logger.warning("Reminder poll failed: %s", exc)
            return
        if not due:
            return

        channel = await self._resolve_channel()
        if channel is None:
            logger.warning(
                "Reminder tick skipped: channel %s unavailable.", self._channel_id
            )
            return

        now = loop.time()
        for alert in due:
            last = self._last_reminded.get(alert.id)
            if last is not None and (now - last) < 30 * 60:
                continue
            try:
                embed = alert_notification_embed(alert)
                await channel.send(embed=embed)
            except discord.DiscordException as exc:
                logger.error(
                    "Failed to post reminder for #%s: %s", alert.id, exc
                )
                continue
            self._last_reminded[alert.id] = now
        self._save_seen()

    async def _resolve_channel(self) -> Optional[discord.abc.Messageable]:
        channel = (
            self._bot.get_channel(self._channel_id) if self._channel_id else None
        )
        if channel is None and self._channel_id:
            try:
                channel = await self._bot.fetch_channel(self._channel_id)
            except (discord.DiscordException, ValueError) as exc:
                logger.error("AlertWatcher could not fetch channel: %s", exc)
                channel = None
        return channel


__all__ = ["AlertWatcher"]