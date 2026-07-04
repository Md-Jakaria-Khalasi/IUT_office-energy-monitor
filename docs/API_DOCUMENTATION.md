# API Documentation

The backend exposes two surfaces:

| Surface     | Base path  | Description                              |
|-------------|------------|------------------------------------------|
| REST        | `/api/v1`  | JSON HTTP API consumed by the bot & web  |
| WebSocket   | `/ws`      | Realtime push of device updates & alerts |

OpenAPI / Swagger is available at:

* Swagger UI  — `GET /docs`
* OpenAPI 3.0 — `GET /openapi.json`

The detailed endpoint catalogue (every verb, path, query parameter, payload
shape, error model, CORS posture, and the WebSocket frame contract) lives in
[`api/endpoints.md`](api/endpoints.md). For a shorter, navigator-friendly
overview read the section index below.

---

## 1. Endpoint index

| Section | Surface | Contents                                                              |
|---------|---------|-----------------------------------------------------------------------|
| 0       | HTTP    | Service endpoints (`/`, `/healthz`, `/health`, `/ready`)              |
| 1       | HTTP    | Devices — list, get, update                                           |
| 2       | HTTP    | Rooms — aggregate stats per room                                      |
| 3       | HTTP    | Alerts — list, acknowledge                                            |
| 4       | HTTP    | Activities — recent device activity events                            |
| 5       | HTTP    | Simulation — manual tick, aggregate overview                          |
| 6       | WS      | WebSocket message protocol (`/ws`)                                    |
| 7       | HTTP    | Error model (`application/problem+json`)                              |
| 8       | HTTP    | CORS posture                                                          |

→ **[Full endpoint reference](api/endpoints.md)**

---

## 2. Authentication & access control

The backend ships **without** an auth layer by design — the deployment
guide ([`DEPLOYMENT.md`](PROJECT_DOCUMENTATION.md#5-deployment) covers
deployment) recommends LAN-only deployment or a reverse-proxy IP
allow-list. The dashboard does not send credentials; every request is
implicitly trusted.

---

## 3. Live demo runbook

```bash
# 1. Start the backend
cd backend
uvicorn app.main:app --reload --port 8000

# 2. Smoke test the API
curl http://localhost:8000/                       # {"ok": true, "service": "office-energy"}
curl http://localhost:8000/api/v1/devices/        # JSON list of 15 seeded devices
curl http://localhost:8000/api/v1/rooms/          # per-room aggregates

# 3. Tail a WebSocket session
wscat -c ws://localhost:8000/ws
# {"type": "welcome", "timestamp": "..."}
# {"type": "simulation_tick", "data": {...}, "timestamp": "..."}
```

For a one-shot end-to-end smoke test (REST + WebSocket + Discord bot)
use `scripts/live_probe.py` from the repo root.

---

## 4. Related documents

* [`ARCHITECTURE.md`](ARCHITECTURE.md) — system architecture, data flow,
  simulation engine, WebSocket protocol.
* [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md) — overview,
  deployment recipes, environment variables, ESP32 hardware reference.
* [`diagrams/architecture.drawio`](diagrams/architecture.drawio) — editable
  draw.io architecture diagram.