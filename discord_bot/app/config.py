"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from the discord_bot/.env file if it exists.
# We resolve the path relative to this module so it works in dev, in Docker,
# and from any working directory.
_DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_DOTENV_PATH, override=False)


class Settings(BaseSettings):
    """Settings loaded from environment variables.

    All values can be set via .env file or shell environment.
    See ``.env.example`` for the full list of supported keys.
    """

    model_config = SettingsConfigDict(
        env_file=str(_DOTENV_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Discord ---------------------------------------------------------------
    discord_token: str = Field(
        ...,
        description="Bot token issued by the Discord developer portal.",
    )
    command_prefix: str = Field(
        default="!",
        min_length=1,
        max_length=3,
        description="Prefix used for all bot commands.",
    )

    # --- Backend integration ---------------------------------------------------
    backend_url: str = Field(
        default="http://localhost:8000",
        description="Base URL of the FastAPI backend.",
    )
    backend_api_prefix: str = Field(
        default="/api/v1",
        description="API prefix used by the backend (do not include trailing slash).",
    )
    request_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60,
        description="HTTP timeout for backend requests.",
    )

    # --- Alert watcher ---------------------------------------------------------
    alert_channel_id: Optional[int] = Field(
        default=None,
        description=(
            "Discord channel ID where new alerts are posted. "
            "If unset, automatic notifications are disabled."
        ),
    )
    @field_validator("alert_channel_id", mode="before")
    @classmethod
    def _empty_alert_channel_to_none(cls, value):
        """Treat ``ALERT_CHANNEL_ID=""`` in .env the same as unset."""
        if value is None or value == "":
            return None
        return value

    poll_interval_seconds: float = Field(
        default=30.0,
        gt=0,
        le=600,
        description="How often to poll /alerts for new entries.",
    )
    alert_poll_limit: int = Field(
        default=50,
        gt=0,
        le=500,
        description="Maximum number of alerts fetched per poll cycle.",
    )

    # --- Logging ---------------------------------------------------------------
    log_level: str = Field(
        default="INFO",
        description="Python logging level (DEBUG/INFO/WARNING/ERROR).",
    )

    # ------------------------------------------------------------------ helpers
    @field_validator("backend_url", "backend_api_prefix")
    @classmethod
    def _strip_slashes(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def api_base(self) -> str:
        """Return the full base URL for API calls (no trailing slash)."""
        return f"{self.backend_url}{self.backend_api_prefix}"

    @property
    def log_level_int(self) -> int:
        return logging.getLevelName(self.log_level)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build a cached :class:`Settings` instance.

    Raises a clear ``RuntimeError`` if the required ``DISCORD_TOKEN`` is missing
    so the bot fails fast on startup rather than crashing deep in discord.py.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - depends on env state
        # Re-raise with friendlier message if the only issue is missing token.
        token = os.getenv("DISCORD_TOKEN") or os.getenv("discord_token")
        if not token:
            raise RuntimeError(
                "DISCORD_TOKEN is not set. Copy .env.example to .env and add "
                "your bot token, or export DISCORD_TOKEN in the environment."
            ) from exc
        raise


__all__ = ["Settings", "get_settings"]