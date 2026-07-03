"""Pytest fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SIMULATION_ENABLED", "false")


@pytest_asyncio.fixture
async def session():
    """Yield a fresh in-memory database session for each test."""
    from app.db.session import AsyncSessionLocal, Base, engine, init_db  # noqa: WPS433
    from app.models import activity, alert, device  # noqa: F401,WPS433

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session