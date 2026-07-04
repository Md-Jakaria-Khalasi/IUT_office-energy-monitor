"""Asynchronous HTTP client for the FastAPI backend.

Every method returns parsed Pydantic models and raises typed exceptions that
the bot's cogs can catch and translate into user-friendly Discord messages.
The client is fully async and supports use as an asynchronous context manager.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

import httpx

from .config import Settings, get_settings
from .models import (
    Activity,
    Alert,
    AlertSummary,
    Device,
    DeviceUpdate,
    OverviewStats,
    RoomSummary,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class BackendError(Exception):
    """Base class for all backend communication errors."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendConnectionError(BackendError):
    """Raised when the backend is unreachable or times out."""


class BackendHTTPError(BackendError):
    """Raised when the backend returns a non-2xx status code."""

    def __init__(self, message: str, status_code: int, body: str = "") -> None:
        super().__init__(message, status_code=status_code)
        self.body = body


class BackendNotFound(BackendHTTPError):
    """Raised when the backend returns 404."""


class BackendValidationError(BackendHTTPError):
    """Raised when the backend returns 4xx other than 404."""


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class BackendClient:
    """Thin wrapper around ``httpx.AsyncClient`` with typed responses."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._client: Optional[httpx.AsyncClient] = None
        self._owns_client = False

    # ----- lifecycle --------------------------------------------------------- #

    async def start(self) -> None:
        if self._client is not None:
            return
        self._client = httpx.AsyncClient(
            base_url=self._settings.api_base,
            timeout=httpx.Timeout(self._settings.request_timeout_seconds),
            headers={"User-Agent": "office-energy-bot/1.0"},
        )
        self._owns_client = True
        logger.info("BackendClient started -> %s", self._settings.api_base)

    async def healthcheck(self) -> bool:
        """Ping the backend's ``/healthz`` (and ``/`` as fallback). Returns
        True if the backend reports itself healthy, False otherwise. Never
        raises — the caller decides what to do with an unhealthy backend.

        The health endpoint is exposed at the backend *root* (no ``/api/v1``
        prefix), so the probe uses a dedicated client anchored at
        ``settings.backend_url`` instead of the API base used for data calls.
        This prevents a 404 when ``BACKEND_API_PREFIX`` is set to ``/api/v1``.
        """
        candidates = ("/healthz", "/")
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.backend_url,
                timeout=httpx.Timeout(self._settings.request_timeout_seconds),
                headers={"User-Agent": "office-energy-bot/1.0"},
            ) as probe:
                for path in candidates:
                    try:
                        response = await probe.get(path)
                    except httpx.HTTPError:
                        continue
                    if response.status_code == 200:
                        logger.info(
                            "Backend healthcheck OK on %s%s",
                            self._settings.backend_url,
                            path,
                        )
                        return True
        except httpx.HTTPError as exc:
            logger.warning("Backend healthcheck transport error: %s", exc)
            return False
        logger.warning(
            "Backend healthcheck failed for all candidates: %s",
            ", ".join(candidates),
        )
        return False

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None
            logger.info("BackendClient closed")

    async def __aenter__(self) -> "BackendClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    # ----- internals --------------------------------------------------------- #

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("BackendClient used before start(); call start() first.")
        return self._client

    async def _get_json(self, path: str, *, params: Optional[dict] = None) -> object:
        try:
            response = await self.client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise BackendConnectionError(
                f"Could not reach backend at {self._settings.api_base}{path}: {exc}"
            ) from exc
        return self._handle(response, path)

    async def _post_json(self, path: str, payload: Optional[dict] = None) -> object:
        try:
            if payload is None:
                response = await self.client.post(path)
            else:
                response = await self.client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise BackendConnectionError(
                f"Could not reach backend at {self._settings.api_base}{path}: {exc}"
            ) from exc
        return self._handle(response, path)

    async def _patch_json(self, path: str, payload: dict) -> object:
        try:
            response = await self.client.patch(path, json=payload)
        except httpx.HTTPError as exc:
            raise BackendConnectionError(
                f"Could not reach backend at {self._settings.api_base}{path}: {exc}"
            ) from exc
        return self._handle(response, path)

    def _handle(self, response: httpx.Response, path: str) -> object:
        if response.status_code == 404:
            raise BackendNotFound(
                f"Resource not found: {path}",
                status_code=404,
                body=response.text,
            )
        if response.status_code >= 400:
            if 400 <= response.status_code < 500:
                raise BackendValidationError(
                    f"Backend rejected request {path}: {response.text}",
                    status_code=response.status_code,
                    body=response.text,
                )
            raise BackendHTTPError(
                f"Backend error on {path}: {response.status_code} {response.text}",
                status_code=response.status_code,
                body=response.text,
            )
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise BackendError(
                f"Backend returned invalid JSON for {path}: {exc}",
            ) from exc

    # ----- endpoints --------------------------------------------------------- #

    async def get_overview(self) -> OverviewStats:
        data = await self._get_json("/rooms/overview")
        return OverviewStats.model_validate(data)

    async def list_rooms(self) -> List[RoomSummary]:
        data = await self._get_json("/rooms")
        return [RoomSummary.model_validate(item) for item in (data or [])]

    async def list_devices(self, room: Optional[str] = None) -> List[Device]:
        params = {"room": room} if room else None
        data = await self._get_json("/devices", params=params)
        return [Device.model_validate(item) for item in (data or [])]

    async def get_device(self, device_id: int) -> Device:
        data = await self._get_json(f"/devices/{device_id}")
        return Device.model_validate(data)

    async def set_device_status(self, device_id: int, status: str) -> Device:
        if status not in {"on", "off"}:
            raise ValueError("status must be 'on' or 'off'")
        payload = DeviceUpdate(status=status).model_dump()
        data = await self._patch_json(f"/devices/{device_id}", payload)
        return Device.model_validate(data)

    async def list_alerts(
        self,
        limit: int = 50,
        *,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        alert_type: Optional[str] = None,
        room: Optional[str] = None,
        device_id: Optional[int] = None,
        only_active: Optional[bool] = None,
    ) -> List[Alert]:
        params: dict[str, Any] = {"limit": limit}
        if severity:
            params["severity"] = severity
        if status:
            params["status"] = status
        if alert_type:
            params["alert_type"] = alert_type
        if room:
            params["room"] = room
        if device_id is not None:
            params["device_id"] = device_id
        if only_active is not None:
            params["only_active"] = str(bool(only_active)).lower()
        data = await self._get_json("/alerts", params=params)
        return [Alert.model_validate(item) for item in (data or [])]

    async def get_alert(self, alert_id: int) -> Alert:
        data = await self._get_json(f"/alerts/{alert_id}")
        return Alert.model_validate(data)

    async def get_alert_summary(self) -> AlertSummary:
        data = await self._get_json("/alerts/summary")
        return AlertSummary.model_validate(data)

    async def get_due_reminders(self) -> List[Alert]:
        data = await self._get_json("/alerts/due-reminders")
        return [Alert.model_validate(item) for item in (data or [])]

    async def acknowledge_alert(
        self, alert_id: int, *, acknowledged_by: Optional[str] = None
    ) -> Alert:
        payload = {"acknowledged_by": acknowledged_by} if acknowledged_by else None
        data = await self._post_json(f"/alerts/{alert_id}/acknowledge", payload)
        return Alert.model_validate(data)

    async def dismiss_alert(
        self,
        alert_id: int,
        *,
        duration_minutes: Optional[int] = None,
        dismissed_by: Optional[str] = None,
    ) -> Alert:
        payload: dict[str, Any] = {}
        if duration_minutes is not None:
            payload["duration_minutes"] = int(duration_minutes)
        if dismissed_by:
            payload["dismissed_by"] = dismissed_by
        data = await self._post_json(f"/alerts/{alert_id}/dismiss", payload or None)
        return Alert.model_validate(data)

    async def resolve_alert(self, alert_id: int) -> Alert:
        data = await self._post_json(f"/alerts/{alert_id}/resolve")
        return Alert.model_validate(data)

    async def list_activities(
        self, limit: int = 20, room: Optional[str] = None
    ) -> List[Activity]:
        params: dict = {"limit": limit}
        if room:
            params["room"] = room
        data = await self._get_json("/activities", params=params)
        return [Activity.model_validate(item) for item in (data or [])]


__all__ = [
    "BackendClient",
    "BackendConnectionError",
    "BackendError",
    "BackendHTTPError",
    "BackendNotFound",
    "BackendValidationError",
]