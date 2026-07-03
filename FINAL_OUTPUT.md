# 📦 Final Output Report

## ✅ Completed Features

### Backend (FastAPI · Python 3.11)
- Async SQLAlchemy 2.0 + **aiosqlite** with persistent SQLite at
  `office_energy.db`.
- Configuration via **pydantic-settings** (`backend/app/core/config.py`),
  readable from `.env` (template provided as `.env.example`).
- Domain constants (`backend/app/core/constants.py`): three rooms,
  `fan`/`light` device types, 75 W/20 W nominal power, 15 seeded devices.
- Services: `DeviceService`, `ActivityService`, `AlertService`,
  `SimulationEngine`, `SimulationScheduler` (background `asyncio` loop),
  `office_hours` helper.
- REST API (prefix `/api/v1`):
  - `GET /devices/`, `GET /devices/{id}`, `PATCH /devices/{id}`
  - `GET /rooms/`
  - `GET /alerts/`
  - `GET /activities/`
  - `POST /simulation/tick`
  - `GET /simulation/overview`
- WebSocket `/ws` – broadcasts `simulation_update`, `device_update`,
  `alert` events with graceful ping/pong.
- Lifespan hooks seed the DB on first run, start/stop the scheduler and
  the WebSocket manager cleanly.
- Healthchecks: `GET /`, `GET /healthz`.
- Auto-generated **OpenAPI 3** at `/docs` and `/openapi.json`.

### Flutter Web Dashboard
- Single-page dashboard built with Material 3 + Inter font.
- Responsive layout (mobile/tablet/desktop breakpoints via `LayoutBuilder`).
- Reusable widgets in `lib/widgets/`:
  - `StatCard`, `RoomCard` (progress bar), `DeviceTile` (animated switch),
  - `LivePowerChart` (CustomPainter sparkline), `AlertList`,
  - `ActivityFeed`, `ConnectionIndicator` (pulsing live status).
- Services: `ApiService` (typed exception + fromJson), `RealtimeService`
  (`web_socket_channel` with auto-reconnect, ping/pong, exponential
  back-off, status stream).
- State management via a single `DashboardState extends ChangeNotifier`
  that owns the data and exposes a `toggleDevice()` action.

### Discord Bot (`discord_bot/`)
- `discord.py` 2.4 with custom `EnergyBot` class.
- Commands: **`!status`**, **`!room <name>`**, **`!usage`**, **`!alerts`**,
  **`!help`** – each pulls fresh data via `BackendClient` (httpx async).
- Built-in help text (`HELP_TEXT`).
- Dockerfile + integration into `docker-compose`.

### Hardware (`docs/hardware/README.md`)
- Bill of materials (ESP32, 5 relays/room, ACS712, optocouplers, 5 V PSU…).
- Pin map for 3 rooms × 5 devices + I²C LCD.
- Wiring table, electrical explanation, current-sensing math.
- **No `wokwi.json` is auto-generated** – explicitly forbidden and excluded
  from git.

### Architecture (`docs/architecture/diagram.drawio`)
- Layered draw.io XML covering hardware → backend → clients.
- Highlights REST, WebSocket, simulator, SQLite, Discord bot, Flutter UI.

### Documentation
- `README.md` – project overview, badges, screenshots, quick start,
  architecture, layout.
- `docs/api/README.md` – full REST + WebSocket reference with payloads.
- `docs/DEPLOYMENT.md` – native, Docker, cloud (Fly.io / Render /
  nginx), env vars, smoke tests, backup/restore.
- `LICENSE` (MIT).

### Tests
- `backend/tests/` with pytest:
  - `conftest.py` (in-memory SQLite fixture, FastAPI ASGI client).
  - `test_device_service.py` – CRUD + toggle + activity logging.
  - `test_office_hours.py` – boundary tests at 07:59, 08:00, 18:00.
  - `test_api.py` – REST round-trips.

### Docker / Production
- `Dockerfile` (backend, python:3.11-slim, healthcheck, persistent volume).
- `discord_bot/Dockerfile`.
- `frontend/web/Dockerfile` (multi-stage build → nginx:alpine).
- `docker-compose.yml` with `backend`, `discord`, `frontend` services,
  healthchecks, persistent volume for SQLite.
- `.dockerignore` and `.gitignore` (including the `wokwi.json` exclusion).

---

## 🟡 Pending / Out of Scope

| Area                              | Why                                                             |
|-----------------------------------|-----------------------------------------------------------------|
| Real ESP32 firmware source code   | Documentation describes the firmware contract; actual Arduino / ESP-IDF sketch is left to users because prompt forbids generating `wokwi.json`. |
| Mongoose / InfluxDB migration     | We pin SQLite for portability; no migration path delivered.      |
| Authentication (OAuth/JWT)        | Single-tenant office deployment – no auth in MVP.               |
| E2E Flutter WebDriver tests       | Spec only required backend tests.                               |
| Multi-tenancy                     | Future feature.                                                 |

---

## 🗂️ Folder Structure

```
office-energy-monitor/
├── LICENSE
├── README.md
├── FINAL_OUTPUT.md
├── .gitignore
├── .dockerignore
├── docker-compose.yml
├── Dockerfile                       # backend
├── backend/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   ├── app/
│   │   ├── main.py                  # FastAPI factory + lifespan
│   │   ├── core/
│   │   │   ├── config.py            # Settings (pydantic-settings)
│   │   │   ├── constants.py         # rooms, device types, ratings
│   │   │   └── logger.py
│   │   ├── db/
│   │   │   └── session.py           # async engine + session
│   │   ├── models/
│   │   │   ├── device.py
│   │   │   ├── alert.py
│   │   │   └── activity.py
│   │   ├── schemas/
│   │   │   ├── device.py
│   │   │   ├── alert.py
│   │   │   ├── activity.py
│   │   │   └── overview.py
│   │   ├── services/
│   │   │   ├── device_service.py
│   │   │   ├── activity_service.py
│   │   │   ├── alert_service.py
│   │   │   ├── office_hours.py
│   │   │   ├── simulation.py
│   │   │   └── scheduler.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── routers/
│   │   │       ├── devices.py
│   │   │       ├── rooms.py
│   │   │       ├── alerts.py
│   │   │       ├── activities.py
│   │   │       └── simulation.py
│   │   └── websocket/
│   │       ├── manager.py
│   │       └── routes.py
│   └── tests/
│       ├── conftest.py
│       ├── test_device_service.py
│       ├── test_office_hours.py
│       └── test_api.py
├── discord_bot/
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   └── app/
│       ├── bot.py                   # EnergyBot + !status etc.
│       ├── api_client.py            # BackendClient (httpx)
│       └── config.py
└── frontend/web/
    ├── pubspec.yaml
    ├── analysis_options.yaml
    ├── Dockerfile
    ├── nginx.conf
    └── lib/
        ├── main.dart
        ├── theme/
        │   └── app_theme.dart       # Material 3 dark + AppColors
        ├── models/
        │   └── device.dart          # Device, RoomSummary, OverviewStats, Alert, Activity
        ├── services/
        │   ├── api_service.dart
        │   ├── realtime_service.dart
        │   └── dashboard_state.dart # ChangeNotifier
        ├── widgets/
        │   ├── stat_card.dart
        │   ├── room_card.dart
        │   ├── device_tile.dart
        │   ├── connection_indicator.dart
        │   ├── alert_list.dart
        │   ├── activity_feed.dart
        │   └── live_power_chart.dart
        └── screens/
            └── dashboard_screen.dart # top-level screen
└── docs/
    ├── api/README.md
    ├── architecture/diagram.drawio
    ├── hardware/README.md
    └── DEPLOYMENT.md
```

---

## 🧭 Architecture Summary

```
ESP32 hardware  ─┐
                 │ JSON / Wi-Fi
                 ▼
          FastAPI backend
          ├── REST  (/api/v1)
          ├── WS    (/ws)
          ├── SimEngine + scheduler (office-hours aware)
          └── SQLite (aiosqlite)
                 ▲            ▲
                 │            │
          Flutter Web     Discord bot
          (ChangeNotifier (`!status`,`!room`,
            + WS bridge)    `!usage`,`!alerts`)
```

Detailed visualisation: open `docs/architecture/diagram.drawio` in
[app.diagrams.net](https://app.diagrams.net).

---

## 🔌 API Summary

| Method | Path                              | Description                              |
|-------:|-----------------------------------|------------------------------------------|
| GET    | `/api/v1/devices/`                | List devices                             |
| GET    | `/api/v1/devices/{id}`            | Single device                            |
| PATCH  | `/api/v1/devices/{id}`            | Update status (`ON`/`OFF`)               |
| GET    | `/api/v1/rooms/`                  | Per-room aggregates                      |
| GET    | `/api/v1/alerts/`                 | Recent alerts                            |
| GET    | `/api/v1/activities/`             | Recent activity events                   |
| POST   | `/api/v1/simulation/tick`         | Force a simulator tick                   |
| GET    | `/api/v1/simulation/overview`     | Aggregate office stats                   |
| WS     | `/ws`                             | Live `simulation_update`/`device_update`/`alert` events |
| GET    | `/docs`                           | Swagger UI                               |
| GET    | `/healthz`                        | Healthcheck                              |

---

## 💾 Database Summary

| Table       | Purpose                                                 |
|-------------|---------------------------------------------------------|
| `devices`   | Per-room, per-type device records, status + power        |
| `alerts`    | Severity + message + timestamp                          |
| `activities`| Per-device state-change log with optional `actor`       |

Migration path is via the auto-seeding `seed_default_devices()` invocation
on startup – no Alembic needed for the demo since SQLite is in-tree.

---

## 🧪 Testing Summary

```
backend/tests/
├── conftest.py              # in-memory DB fixture + ASGI transport
├── test_device_service.py   # CRUD + power calc + activity log
├── test_office_hours.py     # boundary tests
└── test_api.py              # REST round-trips
```

Run with:

```bash
cd backend
pytest -v
```

Coverage focuses on business logic; UI is verified manually.

---

## 📚 Documentation Summary

* `README.md` – entrypoint, features, quick start, layout, links.
* `docs/api/README.md` – REST + WS reference with payloads.
* `docs/hardware/README.md` – BOM, pin map, wiring, electrical notes,
  firmware contract.  **No `wokwi.json` is generated.**
* `docs/architecture/diagram.drawio` – XML architecture file.
* `docs/DEPLOYMENT.md` – native, docker, cloud (Fly.io / Render / nginx).

---

## ⚠️ Remaining Risks

1. **SQLite write contention** – fine for a single office but not for many
   concurrent ESP32 nodes. Swap-in path: set `DATABASE_URL` to Postgres.
2. **No auth** – anyone on the LAN can flip switches. Add JWT or mTLS
   before exposing publicly.
3. **WebSocket scalability** – in-process pub/sub only. Move to Redis
   pub/sub once you exceed ~5 instances.
4. **Wokwi diagram** – left to the user (we comply with the rule: never
   auto-generate `wokwi.json`).
5. **Flutter web binary size** – mitigated by `--release` builds; can be
   further optimised with `--web-renderer html` or tree-shaking.

---

## 🚀 Suggested Future Improvements

* Add OAuth2/OIDC login for both dashboard and Discord bot.
* Replace the simulator with MQTT ingestion of real ESP32 telemetry;
  use the same WebSocket broadcast.
* Promote `Activity`/`Alert` to a time-series store (TimescaleDB /
  InfluxDB) and add Grafana dashboards.
* Per-user notification preferences via the bot (DM on alert).
* Internationalisation (English / Bangla / Spanish) using Flutter
  `flutter_localizations` + ARB files.
* Flutter unit + widget tests for state classes and widgets.
* CI: GitHub Actions matrix running pytest, `flutter analyze`,
  `flutter test`, `docker compose config`.
* Multi-tenant namespace via path prefix (`/t/{tenant}/api/v1`).
* Add Playwright e2e against the static build.
* Generate a real `wokwi.json` only from a deliberately authored
  template committed by humans.
