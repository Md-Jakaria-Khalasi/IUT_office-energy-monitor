"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import activities, alerts, devices, rooms, simulation
from app.core.config import get_settings
from app.core.logging import configure_logging, logger
from app.db.session import AsyncSessionLocal, init_db
from app.services.device_service import DeviceService
from app.services.scheduler import SimulationScheduler
from app.websocket import routes as websocket_routes


scheduler = SimulationScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    await init_db()
    async with AsyncSessionLocal() as session:
        await DeviceService(session).seed_default_devices()

    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["health"])
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "online",
            "docs": "/docs",
        }

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(rooms.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.include_router(activities.router, prefix="/api/v1")
    app.include_router(simulation.router, prefix="/api/v1")
    app.include_router(websocket_routes.router)

    return app


app = create_app()