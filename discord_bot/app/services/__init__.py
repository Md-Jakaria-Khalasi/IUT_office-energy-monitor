"""Long-running background services (e.g. the alert watcher)."""

from __future__ import annotations

from .alert_watcher import AlertWatcher

__all__ = ["AlertWatcher"]