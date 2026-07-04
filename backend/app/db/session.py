"""Async SQLAlchemy session management."""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.logging import logger


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base for ORM models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create tables if they do not exist yet, then sync any new columns.

    ``Base.metadata.create_all`` is a no-op for tables that already exist, so
    columns added to a model after the database was first created never appear
    on disk. This helper performs a lightweight, idempotent ``ALTER TABLE``
    pass for every column the model declares but the live schema lacks.
    """
    # Import models so that they are registered on Base.metadata
    from app.models import activity, alert, device  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _sync_schema(conn)
    logger.info("Database tables ensured.")


async def _sync_schema(conn: "AsyncConnection") -> None:
    """Add any columns missing from the live SQLite schema.

    Safe to run repeatedly: each ``ALTER TABLE`` is skipped if the column
    already exists. All new columns are created with SQLite's ``TEXT`` type —
    SQLAlchemy's JSON/Integer/Boolean/Float/DateTime adapters happily round-trip
    through text storage, which keeps the DDL portable and side-steps quirks
    with ``column.type.compile(dialect=...)`` for ``JSON`` types.

    Only additive migrations are performed; destructive changes (renames,
    drops, type narrowing) still require a manual migration.
    """
    from sqlalchemy import text

    type_default = {
        "json": "'[]'",
        "dict_json": "'{}'",
        "integer": "0",
        "boolean": "0",
        "float": "0.0",
        "datetime": "CURRENT_TIMESTAMP",
    }

    for table in Base.metadata.sorted_tables:
        table_name = table.name
        try:
            existing = {
                row[1]
                for row in (
                    await conn.execute(text(f'PRAGMA table_info("{table_name}")'))
                ).fetchall()
            }
        except Exception:  # noqa: BLE001 - table may not exist yet
            continue

        for column in table.columns:
            if column.name in existing:
                continue

            type_key = column.type.compile().__class__.__name__.lower()
            default_sql = type_default.get(type_key, "''")
            not_null = "" if column.nullable else " NOT NULL"
            ddl = (
                f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" '
                f"TEXT{not_null} DEFAULT {default_sql}"
            )
            try:
                await conn.execute(text(ddl))
                logger.info(f"Schema sync: added {table_name}.{column.name}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Schema sync: could not add {table_name}.{column.name}: {exc}"
                )