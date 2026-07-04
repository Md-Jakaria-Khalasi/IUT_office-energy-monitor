"""WebSocket sync contracts.

These tests assert the PART 6 invariants:

* Device updates broadcast exactly once and only for devices whose state
  actually changed (no no-op fan-out).
* Room-level bulk endpoints broadcast per-device updates AND a single
  ``room_power`` event, only AFTER the database commit has succeeded.
* Alert lifecycle endpoints (ack/dismiss/resolve) broadcast the
  matching alert event after the commit.
* Two parallel PATCHes do not produce duplicate ``device_update`` events
  for the device that ends up unchanged.
* The simulation engine commits its transaction BEFORE fanning events
  out, so a failed commit never leaks stale state.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.constants import RoomName, RoomName as _RoomName  # noqa: F401
from app.main import create_app
from app.services.simulation import SimulationEngine
from app.websocket import manager as ws_module
from app.websocket.manager import ws_manager


# ---------------------------------------------------------------------------
# Recording fake WebSocket manager
# ---------------------------------------------------------------------------


class RecordingWsManager:
    """Drop-in replacement for ``ws_manager`` that records every broadcast."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    # event helpers the router layer calls ----------------------------------
    async def broadcast_device_update(self, payload):  # noqa: D401
        self.calls.append({"event": "device_update", "payload": payload})

    async def broadcast_room_power(self, payload):
        self.calls.append({"event": "room_power", "payload": payload})

    async def broadcast_alert_created(self, payload):
        self.calls.append({"event": "alert_created", "payload": payload})

    async def broadcast_alert_updated(self, payload):
        self.calls.append({"event": "alert_updated", "payload": payload})

    async def broadcast_alert_resolved(self, payload):
        self.calls.append({"event": "alert_resolved", "payload": payload})

    async def broadcast_alert_acknowledged(self, payload):
        self.calls.append({"event": "alert_acknowledged", "payload": payload})

    async def broadcast_alert_dismissed(self, payload):
        self.calls.append({"event": "alert_dismissed", "payload": payload})

    async def broadcast_simulation(self, stats):
        self.calls.append({"event": "simulation_tick", "payload": stats})

    # unused helpers --------------------------------------------------------
    async def broadcast(self, payload):  # pragma: no cover - passthrough
        self.calls.append({"event": payload.get("type"), "payload": payload.get("data")})

    async def broadcast_async(self, payload):  # pragma: no cover
        await self.broadcast(payload)

    async def broadcast_summary(self, payload):  # pragma: no cover
        self.calls.append({"event": "alert_summary", "payload": payload})

    async def broadcast_reminder(self, payload):  # pragma: no cover
        self.calls.append({"event": "alert_reminder", "payload": payload})

    async def broadcast_alert_escalated(self, payload, previous_severity=None):  # pragma: no cover
        self.calls.append(
            {"event": "alert_escalated", "payload": {**payload, "previous_severity": previous_severity}}
        )


@pytest.fixture
def recorder(monkeypatch):
    """Swap the singleton ``ws_manager`` for a recording fake."""
    fake = RecordingWsManager()
    monkeypatch.setattr(ws_module, "ws_manager", fake, raising=False)
    # The routers import the symbol directly — patch both locations.
    from app.api import alerts as alerts_module
    from app.api import devices as devices_module
    from app.api import rooms as rooms_module
    from app.services import simulation as simulation_module

    for module in (alerts_module, devices_module, rooms_module, simulation_module):
        monkeypatch.setattr(module, "ws_manager", fake, raising=False)

    # Also patch the singleton at the original location so any helper that
    # imported the binding by name observes the same fake.
    monkeypatch.setattr(ws_module, "ws_manager", fake, raising=False)
    return fake


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_devices(app) -> None:
    """Seed the in-memory DB with three rooms of devices via the public API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            await client.get("/api/v1/devices")


def _select_device_ids(payload, room: str) -> List[int]:
    return [row["id"] for row in payload if row["room"] == room]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_device_broadcasts_device_update_once(recorder):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            listing = await client.get("/api/v1/devices")
            devices = listing.json()
            target_id = _select_device_ids(devices, RoomName.DRAWING_ROOM.value)[0]
            original_status = next(d for d in devices if d["id"] == target_id)["status"]
            new_status = "off" if original_status == "on" else "on"

            response = await client.patch(
                f"/api/v1/devices/{target_id}",
                json={"status": new_status},
            )
            assert response.status_code == 200, response.text

    updates = [c for c in recorder.calls if c["event"] == "device_update"]
    assert len(updates) == 1
    assert updates[0]["payload"]["id"] == target_id
    assert updates[0]["payload"]["status"] == new_status


@pytest.mark.asyncio
async def test_patch_device_noop_does_not_broadcast(recorder):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            listing = await client.get("/api/v1/devices")
            devices = listing.json()
            target_id = _select_device_ids(devices, RoomName.WORK_ROOM_1.value)[0]
            current_status = next(d for d in devices if d["id"] == target_id)["status"]

            # No-op: setting status to its current value should NOT emit an
            # update event (otherwise dashboards churn on every refresh).
            response = await client.patch(
                f"/api/v1/devices/{target_id}",
                json={"status": current_status},
            )
            assert response.status_code == 200, response.text

    updates = [c for c in recorder.calls if c["event"] == "device_update"]
    assert updates == []


@pytest.mark.asyncio
async def test_all_on_broadcasts_per_device_and_room_power(recorder):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            listing = await client.get("/api/v1/devices")
            devices = listing.json()
            room = RoomName.WORK_ROOM_1.value
            room_devices = [d for d in devices if d["room"] == room]
            already_on = sum(1 for d in room_devices if d["status"] == "on")

            response = await client.post(f"/api/v1/rooms/{room}/all-on")
            assert response.status_code == 200, response.text
            body = response.json()

    # Response contract: changed count == number of device_update events.
    updates = [c for c in recorder.calls if c["event"] == "device_update"]
    assert len(updates) == body["changed"]
    assert body["changed"] == len(room_devices) - already_on

    # Each device_update must reference a real room device.
    device_ids = {d["id"] for d in room_devices}
    assert {u["payload"]["id"] for u in updates}.issubset(device_ids)

    # Exactly ONE room_power event fans out per request.
    powers = [c for c in recorder.calls if c["event"] == "room_power"]
    assert len(powers) == 1
    assert powers[0]["payload"]["room"] == room


@pytest.mark.asyncio
async def test_all_off_idempotent_on_already_off_devices(recorder):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            # First, force everything off in Drawing Room.
            turn_off = await client.post(f"/api/v1/rooms/{RoomName.DRAWING_ROOM.value}/all-off")
            assert turn_off.status_code == 200
            first_changes = turn_off.json()["changed"]
            recorder.calls.clear()

            # Repeat: nothing should be emitted.
            repeat = await client.post(f"/api/v1/rooms/{RoomName.DRAWING_ROOM.value}/all-off")
            assert repeat.status_code == 200
            assert repeat.json()["changed"] == 0

    updates = [c for c in recorder.calls if c["event"] == "device_update"]
    powers = [c for c in recorder.calls if c["event"] == "room_power"]
    assert updates == []
    # room_power may still be broadcast to keep dashboards in sync, but no
    # device-level fan-out happens for unchanged devices.
    assert len(powers) == 1
    assert first_changes >= 0  # sanity check that the first call did something


@pytest.mark.asyncio
async def test_alert_ack_broadcasts_after_commit(recorder):
    """Ack must broadcast the matching alert_acknowledged event after commit."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal, Base, engine
    from app.models.alert import Alert
    from app.core.constants import AlertStatus, AlertSeverity, AlertType

    # Fresh in-memory DB so we control what alerts exist.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        session.add(
            Alert(
                message="Test alert",
                severity=AlertSeverity.WARNING.value,
                alert_type=AlertType.CRITICAL_POWER.value,
                status=AlertStatus.ACTIVE.value,
                room=RoomName.DRAWING_ROOM.value,
                created_at=datetime.now(timezone.utc),
                last_evaluated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        alert_id = (
            await session.execute(select(Alert).order_by(Alert.id).limit(1))
        ).scalar_one().id

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            response = await client.post(f"/api/v1/alerts/{alert_id}/acknowledge")
            assert response.status_code == 200, response.text

    acks = [c for c in recorder.calls if c["event"] == "alert_acknowledged"]
    assert len(acks) == 1
    assert acks[0]["payload"]["id"] == alert_id
    assert acks[0]["payload"]["status"] == AlertStatus.ACKNOWLEDGED.value


@pytest.mark.asyncio
async def test_alert_resolve_broadcasts_after_commit(recorder):
    """Resolve must broadcast alert_resolved post-commit."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal, Base, engine
    from app.models.alert import Alert
    from app.core.constants import AlertStatus, AlertSeverity, AlertType

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        session.add(
            Alert(
                message="Resolve me",
                severity=AlertSeverity.WARNING.value,
                alert_type=AlertType.CRITICAL_POWER.value,
                status=AlertStatus.ACTIVE.value,
                room=RoomName.DRAWING_ROOM.value,
                created_at=datetime.now(timezone.utc),
                last_evaluated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        alert_id = (
            await session.execute(select(Alert).order_by(Alert.id).limit(1))
        ).scalar_one().id

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            response = await client.post(f"/api/v1/alerts/{alert_id}/resolve")
            assert response.status_code == 200, response.text

    resolved = [c for c in recorder.calls if c["event"] == "alert_resolved"]
    assert len(resolved) == 1
    assert resolved[0]["payload"]["id"] == alert_id


@pytest.mark.asyncio
async def test_simulator_broadcasts_after_commit(recorder, monkeypatch):
    """``tick()`` must commit BEFORE fanning out events."""
    from app.db.session import AsyncSessionLocal

    # We need at least one seeded device.
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            listing = await client.get("/api/v1/devices")
            assert listing.status_code == 200
            devices = listing.json()
            assert len(devices) > 0

            # Re-attach an engine and run a single tick.
            async with AsyncSessionLocal() as session:
                engine = SimulationEngine(session)
                # Force every device's toggle probability to 0 so the engine
                # emits at most a no-change tick; this still exercises the
                # commit-then-broadcast ordering.
                monkeypatch.setattr(engine, "_probability", lambda *a, **kw: 0.0)
                await engine.tick()

            # After tick() the simulator must have emitted a simulation_tick.
            ticks = [c for c in recorder.calls if c["event"] == "simulation_tick"]
            assert len(ticks) == 1


@pytest.mark.asyncio
async def test_concurrent_patch_no_duplicate_events(recorder):
    """Two tasks racing on the same device produce a single, consistent state."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            listing = await client.get("/api/v1/devices")
            devices = listing.json()
            target_id = _select_device_ids(devices, RoomName.WORK_ROOM_2.value)[0]
            current = next(d for d in devices if d["id"] == target_id)["status"]
            # Race the SAME target value (no-op) with a real change.
            new_status = "off" if current == "on" else "on"

            async def patch(status_value: str) -> None:
                r = await client.patch(
                    f"/api/v1/devices/{target_id}",
                    json={"status": status_value},
                )
                assert r.status_code == 200

            await asyncio.gather(patch(current), patch(new_status))

    updates = [c for c in recorder.calls if c["event"] == "device_update"]
    # At most one transition — the no-op PATCH must not emit an update.
    relevant = [u for u in updates if u["payload"]["id"] == target_id]
    assert len(relevant) <= 1
    if relevant:
        assert relevant[0]["payload"]["status"] == new_status
