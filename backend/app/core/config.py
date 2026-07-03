"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Centralised application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Office Energy Monitoring System"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False)
    environment: str = Field(default="development")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    reload: bool = Field(default=False)

    # Database
    database_url: str = Field(default=f"sqlite+aiosqlite:///{BASE_DIR / 'office_energy.db'}")

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000", "*"]
    )

    # Simulation
    simulation_interval_seconds: int = Field(default=5)
    simulation_enabled: bool = Field(default=True)

    # Office Hours (24h format)
    office_start_hour: int = Field(default=8)
    office_end_hour: int = Field(default=18)
    office_timezone: str = Field(default="UTC")

    # Alerts
    alert_watt_threshold: int = Field(default=1500)
    alert_off_hours_active: bool = Field(default=True)

    # Discord Bot
    discord_bot_token: str = Field(default="")
    discord_api_base_url: str = Field(default="http://localhost:8000")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()