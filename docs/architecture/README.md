# Architecture

> Companion to [`diagram.drawio`](./diagram.drawio). Open the file in
> [app.diagrams.net](https://app.diagrams.net) for the full visual.

The Office Energy Monitoring System is a small, self-contained stack with
three independently deployable pieces: a **FastAPI** backend (source of
truth), a **Flutter Web** dashboard (operator UI), and a **Discord bot**
(read-only alerting surface). Optional **ESP32** modules feed the same
backend in place of the built-in simulator without changing any other
contract.

---

## 1. High-level view

```
                 ┌──────────────────────────┐
                 │   Office Admin Browser   │
                 └──────────────┬───────────┘
                                │ HTTPS  (REST + WebSocket)
                                ▼
   ┌───────────────────────────────────────────────────────┐
   │                FastAPI backend (uvicorn)              │
   │                                                       │
   │   /api/v1/*  ── routers ── services ── SQLAlchemy 2.0 │
   │   /ws        ── WebSocketManager                     │
   │   /docs      ── OpenAPI                              │
   │                                                       │
   │   ┌────────────────────────┐                          │
   │   │ Simulation scheduler   │  ticks every N seconds   │
   │   │  ├ office-hours gate   │                          │
   │   │  ├ random device toggle│                          │
   │   │  └ alert evaluator     │                          │
   │   └────────────────────────┘                          │
   └──────────────┬─────────────────────┬──────────────────┘
                  │                     │
                  ▼                     ▼
           ┌────────────┐        ┌──────────────────┐
           │  SQLite    │        │   Discord bot    │
           │ (aiosqlite)│        │   (discord.py)   │
           └────────────┘        └──────────────────┘
                                          ▲
                                          │  !status · !room · !usage · !alerts
                                          │
                                  ┌──────────────────┐
                                  │   Discord user   │
                                  └──────────────────┘
```

A editable draw.io diagram lives at
[`docs/architecture/diagram.drawio`](./diagram.drawio). It groups the
system into four horizontal bands: **ESP32 hardware**, **FastAPI
backend**, **Flutter dashboard**, and **Discord bot**, with two human
actors (browser admin, Discord user) on the right.

---

## 2. Component responsibilities

### 2.1 Backend — `backend/app/`

| Layer        | Module(s)                                     | Responsibility                                                   |
|--------------|-----------------------------------------------|------------------------------------------------------------------|
| Entrypoint   | `main.py`                                     | Creates the `FastAPI` app, registers CORS, lifespan, routers.    |
| Config       | `core/config.py`, `core/constants.py`         | Pydantic settings from `.env`, enums for rooms / device types.   |
| DB           | `db/session.py`                               | Async engine + session factory + table creation.                |
| Models       | `models/{device,activity,alert}.py`           | SQLAlchemy 2.0 declarative tables.                              |
| Schemas      | `schemas/*.py`                                | Pydantic DTOs for request/response.                             |
| Services     | `services/{device_service,activity_service,alert_service,simulation,scheduler,office_hours}.py` | Business logic. No FastAPI imports.       |
| API routers  | `api/{devices,rooms,alerts,activities,simulation}.py` | Thin HTTP wrappers around services.                       |
| WebSocket    | `websocket/{manager,routes}.py`               | Connection registry, broadcast helpers, `/ws` endpoint.         |
| Tests        | `tests/`                                      | `pytest` with in-memory SQLite.                                 |

The backend is the single owner of device state, activity history, and
alert history. Every other component is a client of it.

### 2.2 Frontend — `frontend/lib/` and `frontend/web/lib/`

| Layer        | File(s)                                                              | Responsibility                                                |
|--------------|----------------------------------------------------------------------|---------------------------------------------------------------|
| Theme        | `theme/app_theme.dart`                                               | Material 3 dark palette (`AppColors`, `AppTheme.dark()`).     |
| Models       | `models/device.dart`                                                 | Mirror of backend `DeviceRead` schema.                        |
| HTTP client  | `services/api_service.dart`                                          | `package:http` wrapper for REST endpoints.                    |
| Realtime     | `services/realtime_service.dart`                                     | `WebSocketChannel` with broadcast streams + reconnect timer.  |
| State        | `services/dashboard_state.dart`                                      | `ChangeNotifier` merging REST snapshot + WS deltas.           |
| Screen       | `screens/dashboard_screen.dart`                                      | Top-level layout: stat cards, room grid, alerts, activity.    |
| Widgets      | `widgets/{stat_card,room_card,device_tile,live_power_chart,alert_list,activity_feed,connection_indicator}.dart` | Reusable building blocks. |

Two copies of the `lib/` tree exist (`frontend/lib/` and the canonical
`frontend/web/lib/`) because the Flutter web build runs from the `web/`
folder. Both are kept identical — see the `frontend/README.md` for the
rationale.

### 2.3 Discord bot — `discord_bot/app/`

| Layer        | File(s)                                            | Responsibility                                                  |
|--------------|----------------------------------------------------|-----------------------------------------------------------------|
| Entry        | `bot.py`                                           | Builds the discord.py client and loads cogs.                    |
| Config       | `config.py`                                        | Pydantic settings loaded from `discord_bot/.env`.               |
| HTTP client  | `api_client.py`                                    | Thin async wrapper over `httpx` calling the FastAPI backend.    |
| Embeds       | `embed_builder.py`                                 | Renders Discord embeds for status / room / usage / alerts.      |
| Commands     | `cogs/{status,room,usage,alerts,help}.py`          | `!status`, `!room`, `!usage`, `!alerts`, `!help` cogs.          |
| Watcher      | `services/alert_watcher.py`                        | Background task polling `/alerts` and posting new entries.     |
| Models       | `models.py`                                        | Pydantic mirrors of backend responses.                          |

The bot is **read-only** with respect to device control; it only
acknowledges alerts and posts notifications.

### 2.4 ESP32 hardware (future)

Per-room ESP32 modules will replace the simulator by posting JSON
telemetry to a backend ingestion endpoint. Today the path is described
in [`docs/hardware/README.md`](../hardware/README.md); no firmware is
checked in yet.

---

## 3. Data flow

### 3.1 Browser → Backend (REST + WebSocket)

```
Browser
   │  GET /api/v1/devices, /rooms/overview, /alerts?limit=N, /activities
   ▼
FastAPI router → service → SQLAlchemy → SQLite
   ▲                                          │
   │                                          ▼
   │                            Activity / Alert / Device rows persisted
   │
   │  WebSocket frames pushed by WebSocketManager.broadcast_*()
   ▼
RealtimeService → DashboardState → setState → widget rebuild
```

`DashboardState` keeps the latest REST snapshot in memory and overlays
WebSocket deltas as they arrive, so the UI is correct within one tick
even after a reconnect.

### 3.2 Discord bot → Backend (REST only)

```
Discord user  ──!status──▶  discord.py cog
                                 │
                                 ▼
                       BackendClient (httpx)
                                 │  GET /api/v1/rooms/overview
                                 ▼
                       FastAPI router ─▶ service ─▶ response
                                 ▲
                                 │
                       embed_builder.py
                                 │
                                 ▼
                       Discord channel message
```

The bot never writes back to devices. The only mutation it makes is
`POST /api/v1/alerts/{id}/ack` when a moderator types the equivalent
of `!ack` (implemented as a slash command / context menu).

### 3.3 ESP32 → Backend (planned)

```
ESP32 sensor reads
   │  JSON: { device_id, status, power_consumption, timestamp }
   ▼
POST /api/v1/devices/{id}/telemetry   (future endpoint)
   │                                   │
   ▼                                   ▼
DeviceService.update_from_telemetry()  ActivityService.log()
   │                                   │
   └──────────► WebSocketManager.broadcast_device_update()
```

The WebSocket message contract is identical regardless of the source,
so the dashboard never needs to know whether a state change came from
the simulator or real hardware.

---

## 4. Simulation engine

The simulator lives in `backend/app/services/simulation.py` and is
driven by `backend/app/services/scheduler.py`.

### 4.1 Tick loop

1. On application startup (`main.py:lifespan`), `SimulationScheduler.start()`
   schedules an `asyncio` task that runs every
   `SIMULATION_INTERVAL_SECONDS` seconds (default **5**).
2. Each iteration calls `SimulationEngine.tick()` inside a fresh
   `AsyncSessionLocal()` context, then broadcasts the resulting stats
   over `/ws` via `ws_manager.broadcast_simulation()`.
3. If `SIMULATION_ENABLED=false`, the scheduler exits early and logs a
   warning — useful for production once real ESP32s are deployed.

### 4.2 What a tick does

For every device in the database:

1. Compute `p = _probability(device, is_office_hours())`:
   - `base = 0.05` during office hours, `0.02` outside.
   - Lights get `base * 1.5` during office hours, `base * 0.5` outside.
2. If `random.random() < p`, flip the device's status.
3. Update `power_consumption` to the device-type nominal (fan=75 W,
   light=20 W) when ON, `0.0` when OFF.
4. Append an `Activity` row tagged with the actor `simulator`.

After all devices are processed:

1. Sum `total_power` across active devices.
2. If `total_power > ALERT_WATT_THRESHOLD` (default **1500 W**),
   `AlertService.create_alert()` writes a `warning` alert (de-duplicated
   for 60 s).
3. If `is_office_hours()` is false and `ALERT_OFF_HOURS_ACTIVE=true`,
   each device still ON produces an `info` alert of the form
   `"<name> in <room> is still ON after office hours"`.
4. The scheduler broadcasts `{type: "simulation_tick", data: {changed,
   total_power, active}}` to every connected WebSocket client.

### 4.3 Office hours gate

`app/services/office_hours.py` returns `True` only when **both**:

- `now.weekday() < 5` (Mon–Fri), and
- `OFFICE_START_HOUR ≤ now.hour < OFFICE_END_HOUR` (default 08:00–18:00,
  24 h, in `OFFICE_TIMEZONE`).

The gate is used by the simulator to dampen activity outside hours and
by `AlertService` to surface after-hours usage. There is **no** write
gate on `PATCH /api/v1/devices/{id}`; humans can still override via the
dashboard or future ESP32 control path.

### 4.4 Manual trigger

`POST /api/v1/simulation/tick` runs a single tick immediately and
returns the resulting stats. The Flutter dashboard exposes this as a
"refresh" button via `ApiService`.

---

## 5. WebSocket message protocol

The backend exposes a single endpoint: `ws://<host>/ws`. All messages
are JSON with a `type` discriminator and an ISO-8601 `timestamp`.

| Event type         | Direction | Payload                                                                                       | Emitted when                              |
|--------------------|-----------|-----------------------------------------------------------------------------------------------|-------------------------------------------|
| `welcome`          | S → C     | `{ "type": "welcome", "timestamp": "…" }`                                                    | On connect (after `accept()`).            |
| `pong`             | S → C     | `{ "type": "pong" }`                                                                          | Server reply to client `ping` text frame. |
| `device_update`    | S → C     | `{ "type": "device_update", "data": <DeviceRead>, "timestamp": "…" }`                        | After `PATCH /devices/{id}` or telemetry. |
| `simulation_tick`  | S → C     | `{ "type": "simulation_tick", "data": { "changed": [id…], "total_power": W, "active": N }, "timestamp": "…" }` | Every scheduler tick. |
| `alert`            | S → C     | `{ "type": "alert", "data": <AlertRead>, "timestamp": "…" }`                                 | When `AlertService.create_alert` succeeds. (Note: currently alerts are persisted and the bot polls for them; the `alert` frame is reserved for a future direct-push path.) |

Clients may send a plain-text `ping` frame to verify the connection;
the server responds with `{"type": "pong"}`. The Flutter
`RealtimeService` reconnects on any error with a 3-second timer (see
`_scheduleReconnect()`).

---

## 6. Database

| Setting          | Value                                                       |
|------------------|-------------------------------------------------------------|
| Driver           | SQLite via `aiosqlite` (`sqlite+aiosqlite:///…`)            |
| ORM              | SQLAlchemy 2.0 async (`async_sessionmaker`, `DeclarativeBase`) |
| Schema location  | `backend/app/db/session.py` (`init_db()` on app startup)    |
| Tables           | `devices`, `activities`, `alerts`                           |
| Migrations       | `Base.metadata.create_all()` — no Alembic yet               |
| Production swap  | Change `DATABASE_URL` to `postgresql+asyncpg://…` and adjust `connect_args` in `db/session.py`. |

Three tables back the entire feature set:

- `devices` — `id`, `name`, `room`, `type`, `status`, `power_consumption`,
  `last_changed`.
- `activities` — append-only log written by both simulator and human
  actions (`device_id`, `device_name`, `room`, `action`, `description`,
  `created_at`).
- `alerts` — `severity`, `message`, `room`, `device_id`, `created_at`,
  `acknowledged`.

All timestamps are stored in UTC.

---

## 7. Configuration

Settings come from environment variables (see
[`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) and
[`backend/.env.example`](../../backend/.env.example)). The most
relevant knobs for the simulator:

| Env var                       | Default | Purpose                                                       |
|-------------------------------|--------:|---------------------------------------------------------------|
| `SIMULATION_ENABLED`          | `true`  | If `false`, the scheduler never starts.                       |
| `SIMULATION_INTERVAL_SECONDS` | `5`     | Seconds between ticks.                                        |
| `OFFICE_START_HOUR`           | `8`     | 24-h, inclusive.                                              |
| `OFFICE_END_HOUR`             | `18`    | 24-h, exclusive.                                              |
| `OFFICE_TIMEZONE`             | `UTC`   | Used only for display.                                        |
| `ALERT_WATT_THRESHOLD`        | `1500`  | Aggregate wattage above which a warning alert fires.          |
| `ALERT_OFF_HOURS_ACTIVE`      | `true`  | Emit per-device info alerts for after-hours ON devices.       |
| `CORS_ORIGINS`                | local   | Comma-separated allow-list for browser dashboards.            |

---

## 8. Future: swapping the simulator for real ESP32s

The simulator is intentionally narrow: it produces
`(device_id, status, power_consumption)` triples, persists them, and
broadcasts them on `/ws`. Real hardware needs exactly the same
contract.

Planned migration:

1. **Ingest endpoint.** Add `POST /api/v1/devices/{id}/telemetry`
   accepting the JSON shape documented in
   [`docs/hardware/README.md` § 7](../hardware/README.md).
2. **Replace the scheduler loop.** Either disable the simulator
   (`SIMULATION_ENABLED=false`) or change the loop body to *consume*
   telemetry rather than *generate* it. Either way, the persistence
   path (`ActivityService`, `AlertService`) is unchanged.
3. **Prefer reported wattage.** When a telemetry frame arrives, store
   its `power_consumption` on the `Device` row instead of the nominal.
   Aggregations in `DeviceService.total_power()` and the room
   summaries will pick this up automatically.
4. **Keep the WebSocket contract.** No changes to `/ws`; the dashboard
   and Discord bot continue to work without redeployment.

In other words, the simulator is a **substitutable implementation
detail** behind the same REST + WebSocket surface that the rest of the
system already speaks.

---

## 9. Related documents

* [`docs/api/README.md`](../api/README.md) — REST + WebSocket reference.
* [`docs/hardware/README.md`](../hardware/README.md) — ESP32 BOM,
  wiring, and the simulator ↔ hardware mapping.
* [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) — native, Docker, and cloud
  deployment recipes.
* [`docs/architecture/diagram.drawio`](./diagram.drawio) — editable
  draw.io diagram of everything above.