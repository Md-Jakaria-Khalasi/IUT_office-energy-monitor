# Deployment Guide

This project ships **three** independently runnable components:

| Component         | Tech                | Default port |
|-------------------|---------------------|-------------:|
| Backend API       | FastAPI / uvicorn   | 8000         |
| Discord bot       | discord.py          | –            |
| Web dashboard     | Flutter Web (static)| 8080         |

You can run them natively on your workstation, with Docker Compose, or
deploy the static dashboard to any static host.

---

## 1. Native (development)

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Discord bot (separate shell)
cd discord_bot
pip install -r requirements.txt
copy .env.example .env  # set DISCORD_BOT_TOKEN, BACKEND_URL
python -m app.bot

# Flutter web
cd frontend\web
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=WS_URL=ws://localhost:8000/ws
```

---

## 2. Docker Compose (recommended)

```bash
docker compose up --build
```

Services:

- `backend`   – uvicorn on `:8000`
- `discord`   – python bot, depends on backend
- `frontend`  – nginx serving the Flutter web build on `:8080`

The SQLite volume is mounted to `./backend/data` so the database persists
across restarts.

To stop and remove containers:

```bash
docker compose down
```

To rebuild after a code change:

```bash
docker compose up --build --force-recreate
```

---

## 3. Production build (Flutter web)

```bash
cd frontend/web
flutter build web --release \
  --dart-define=API_BASE_URL=https://api.example.com \
  --dart-define=WS_URL=wss://api.example.com/ws
```

The compiled bundle lands in `build/web/`. Drop it into any static host
(nginx, S3 + CloudFront, GitHub Pages, etc.). Point your reverse proxy at
`https://api.example.com` for the FastAPI backend.

### Sample nginx server block

```nginx
server {
  listen 80;
  server_name office.example.com;

  root /var/www/office-energy/build/web;
  index index.html;

  location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
  }

  location /ws {
    proxy_pass http://127.0.0.1:8000/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

---

## 4. Cloud

* **Render / Fly.io / Railway** – push the backend as a Docker image.
* **Fly.io** works especially well because we need a persistent volume for
  SQLite. Use:

  ```toml
  # fly.toml
  [[mounts]]
    source = "office_data"
    destination = "/app/data"
  ```

* **Discord bot** – same pattern; keep its token in a secret.

---

## 5. Configuration

| Variable                          | Default            | Description                       |
|-----------------------------------|--------------------|-----------------------------------|
| `DATABASE_URL`                    | `sqlite+aiosqlite:///office_energy.db` | Async SQLAlchemy DSN |
| `OFFICE_START_HOUR`               | `8`                | Office start (24h)                |
| `OFFICE_END_HOUR`                 | `18`               | Office end (24h)                  |
| `ALERT_WATT_THRESHOLD`            | `1500`             | Threshold for sustained alerts    |
| `SIMULATION_INTERVAL_SECONDS`     | `5`                | Tick cadence                      |
| `BACKEND_URL`                     | `http://localhost:8000` | Used by the Discord bot       |
| `DISCORD_BOT_TOKEN`               | –                  | Discord bot token                 |
| `API_BASE_URL` (Flutter)          | `http://localhost:8000` | Injected at build time        |
| `WS_URL` (Flutter)                | `ws://localhost:8000/ws` | Injected at build time       |

---

## 6. Health checks

* `GET /` returns `{"ok": true, "service": "office-energy"}`
* `GET /healthz` returns `200 OK` once the DB is seeded.

A simple smoke test:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/api/v1/simulation/overview
```

---

## 7. Backup & restore

```bash
# Snapshot
cp backend/office_energy.db backup-$(date +%F).db

# Restore
cp backup-2025-01-01.db backend/office_energy.db
docker compose restart backend
```