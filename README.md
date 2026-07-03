# Office Energy Monitoring System

> A production-quality real-time energy dashboard for small offices. Tracks
> every fan and light, simulates realistic usage, raises alerts when power
> spikes, and lets you query the building from Discord or the browser.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Flutter-Web-3.22-02569B?logo=flutter&logoColor=white)](https://flutter.dev)
[![Discord.py](https://img.shields.io/badge/discord.py-2.4-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](./docker-compose.yml)
[![License](https://img.shields.io/badge/license-MIT-22C55E)](./LICENSE)

---

## ✨ Features

- **Real-time dashboard** – Flutter Web with WebSocket updates, dark theme,
  live sparkline, room-level aggregation, activity feed and alerts panel.
- **REST API + WebSocket** – FastAPI 0.115 with async SQLAlchemy 2.0 and
  aiosqlite; full OpenAPI docs at `/docs`.
- **Simulation engine** – Office-hours-aware random toggling that runs in
  the background, raises alerts and broadcasts over WebSocket.
- **Discord bot** – `!status`, `!room`, `!usage`, `!alerts`, `!help` – all
  fetched live from the backend.
- **ESP32 ready** – Hardware documentation covers 3 rooms × 5 devices with
  relay wiring, ACS712 current sensing and an optocoupler-isolated 5 V rail.
- **Production packaging** – Dockerfile, docker-compose, static frontend
  build, nginx sample, Fly.io volume recipe.

---

## 📸 Screenshots

> Placeholder images – drop real PNGs into `docs/screenshots/` and they will
> be picked up automatically by the gallery below.

| Dashboard                                          | Room detail                                     |
|----------------------------------------------------|-------------------------------------------------|
| ![Overview](docs/screenshots/overview.png)         | ![Room](docs/screenshots/room.png)              |

---

## 🏗️ Architecture

```
   ESP32 hardware (3 rooms × 5 devices)
              │  JSON / Wi-Fi
              ▼
      ┌──────────────────┐
      │  FastAPI backend │ ◄─── SQLite (aiosqlite)
      │  REST + WebSocket│
      └──────────────────┘
        ▲            ▲
        │            │
   Flutter Web   Discord bot
   dashboard     (discord.py)
```

A full draw.io diagram is at `docs/architecture/diagram.drawio` (open in
[app.diagrams.net](https://app.diagrams.net)).

---

## 🚀 Quick start

### Option A – Docker (one command)

```bash
docker compose up --build
```

The dashboard is on <http://localhost:8080>, the API on
<http://localhost:8000/docs>.

### Option B – Native (development)

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# Discord bot
cd ../discord_bot
pip install -r requirements.txt
cp .env.example .env  # set DISCORD_BOT_TOKEN, BACKEND_URL
python -m app.bot

# Flutter web
cd ../frontend/web
flutter pub get
flutter run -d chrome \
  --dart-define=API_BASE_URL=http://localhost:8000 \
  --dart-define=WS_URL=ws://localhost:8000/ws
```

---

## 📦 Project layout

```
.
├── backend/                # FastAPI + SQLAlchemy + aiosqlite
│   ├── app/
│   │   ├── api/            # REST routers
│   │   ├── core/           # config + constants
│   │   ├── db/             # async session
│   │   ├── models/         # ORM
│   │   ├── schemas/        # Pydantic DTOs
│   │   ├── services/       # business logic + simulator
│   │   ├── websocket/      # realtime manager + routes
│   │   └── main.py
│   └── tests/
├── discord_bot/            # discord.py energy bot
├── frontend/web/           # Flutter Web dashboard
├── docs/
│   ├── api/                # REST + WebSocket reference
│   ├── architecture/       # draw.io diagram
│   └── hardware/           # ESP32 BOM, wiring, electrical notes
├── docker-compose.yml
├── Dockerfile              # backend
└── README.md
```

---

## 🧪 Testing

```bash
cd backend
pytest -v
```

The suite covers device CRUD, office-hour helpers, and end-to-end REST
round-trips with an in-memory SQLite.

---

## 📚 Documentation

* [`docs/api/README.md`](docs/api/README.md) – REST & WebSocket reference
* [`docs/hardware/README.md`](docs/hardware/README.md) – ESP32 BOM & wiring
* [`docs/architecture/diagram.drawio`](docs/architecture/diagram.drawio) –
  visual architecture
* [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) – native / docker / cloud

---

## 🤝 Contributing

1. Fork the repo.
2. Create a feature branch (`git checkout -b feature/awesome`).
3. Run the test suite (`cd backend && pytest -v`).
4. Open a PR.

---

## 📝 License

MIT – see [`LICENSE`](./LICENSE).