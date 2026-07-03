"""Discord bot configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    discord_token: str = Field(default="")
    api_base_url: str = Field(default="http://localhost:8000")
    command_prefix: str = Field(default="!")


@lru_cache
def get_settings() -> Settings:
    return Settings()