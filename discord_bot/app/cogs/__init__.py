"""Discord cogs package.

Each cog is a self-contained group of slash-free, prefix-based commands.
Cogs depend on ``Bot.backend`` (a :class:`BackendClient`) for data and never
construct responses from hardcoded data.
"""

from __future__ import annotations

from .alerts import AlertsCog
from .help import HelpCog
from .room import RoomCog
from .status import StatusCog
from .usage import UsageCog

__all__ = [
    "AlertsCog",
    "HelpCog",
    "RoomCog",
    "StatusCog",
    "UsageCog",
]