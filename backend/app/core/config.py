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

    # Advanced alert engine tuning (PART 1)
    cost_per_kwh_usd: float = Field(default=0.15, ge=0)
    after_hours_grace_minutes: int = Field(default=5, ge=0)
    room_continuous_threshold_minutes: int = Field(default=120, ge=1)
    critical_power_threshold_w: int = Field(default=1500, ge=0)
    critical_power_dwell_seconds: int = Field(default=30, ge=1)
    office_consumption_threshold_kwh: float = Field(default=5.0, ge=0)
    alert_warning_after_minutes: int = Field(default=30, ge=1)
    alert_critical_after_minutes: int = Field(default=60, ge=1)
    alert_max_after_minutes: int = Field(default=120, ge=1)
    reminder_interval_minutes: int = Field(default=30, ge=1)
    default_dismiss_duration_minutes: int = Field(default=30, ge=1)

    # Logging
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()