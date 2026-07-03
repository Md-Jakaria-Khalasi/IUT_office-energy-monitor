"""Logging configuration using loguru."""

import sys

from loguru import logger

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure the global logger."""
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stdout,
        level="DEBUG" if settings.debug else "INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
        enqueue=True,
    )


__all__ = ["logger", "configure_logging"]