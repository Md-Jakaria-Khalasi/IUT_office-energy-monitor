# API Documentation

The backend exposes two surfaces:

| Surface     | Base path      | Description                                |
|-------------|----------------|--------------------------------------------|
| REST        | `/api/v1`      | JSON HTTP API consumed by the bot & web    |
| WebSocket   | `/ws`          | Realtime push of device updates & alerts   |

OpenAPI / Swagger is available at:

- Swagger UI  ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ `GET /docs`
- OpenAPI 3.0 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ `GET /openapi.json`

---

## 0. Service endpoints (unversioned)

These endpoints live at the root and are **not** under `/api/v1`. They
exist for liveness probes, load balancers, and smoke tests.

### `GET /`

Returns a tiny JSON banner.

**Response 200**

```json
{ "ok": true, "service": "office-energy" }
```

### `GET /healthz`

Liveness probe. Returns **200 OK** as soon as the FastAPI process is
up ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â does **not** verify the database.

### `GET /health`

Same as `/healthz` but also confirms the database is reachable.
Returns **503** if the SQLite file cannot be opened.

### `GET /ready`

Readiness probe. Returns **200** once the simulator has seeded the
default rooms and devices; returns **503** during the first few hundred
milliseconds of startup.

---

## 1. Devices

### `GET /api/v1/devices/`

List every device.

**Response 200**

```json
[
  {
    "id": 1,
    "name": "Drawing Room Fan 1",
    "room": "Drawing Room",
    "type": "fan",
    "status": "ON",
    "power_consumption": 75,
    "last_changed": "2025-01-01T10:00:00Z"
  }
]
```

### `GET /api/v1/devices/{device_id}`

Fetch a single device. Returns **404** when not found.

### `PATCH /api/v1/devices/{device_id}`

Update a device.

```json
{ "status": "OFF" }
```

**Response 200** returns the updated device. A side effect: a new
`Activity` row is logged and the change is broadcast on `/ws`.

---

## 2. Rooms

### `GET /api/v1/rooms/`

Aggregate stats per room.

```json
[
  {
    "room": "Drawing Room",
    "active_devices": 3,
    "total_devices": 5,
    "total_power": 190
  }
]
```

---

## 3. Alerts

### `GET /api/v1/alerts/`

Returns the last alerts, newest first.

**Query parameters**

| Name     | Type    | Default | Description                                     |
|----------|---------|--------:|-------------------------------------------------|
| `limit`  | integer | `50`    | Maximum number of alerts to return.             |
| `acked`  | boolean | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â       | When `true`, return acknowledged alerts; default `false`. |

```json
[
  {
    "id": 1,
    "device_id": 4,
    "message": "Sustained power above 1500 W",
    "severity": "warning",
    "created_at": "2025-01-01T10:00:00Z"
  }
]
```

### `POST /api/v1/alerts/{alert_id}/ack`

Mark an alert as acknowledged. Idempotent Ã¢â‚¬â€ calling twice is a no-op the second time.

**Response 200**

```json
{ "id": 1, "acknowledged": true, "acknowledged_at": "2025-01-01T10:05:00Z" }
```

Returns **404** when the alert id is unknown. The endpoint is **reserved for future use** Ã¢â‚¬â€ the bundled Discord bot's `!ack` command currently only prints to the console and does not call this endpoint yet; see `discord_bot/app/cogs/alerts.py`.

---

## 4. Activities

### `GET /api/v1/activities/`

Recent device activity events.


**Query parameters**

| Name     | Type    | Default | Description                                                  |
|----------|---------|--------:|--------------------------------------------------------------|
| `limit`  | integer | `50`    | Maximum number of activity rows to return.                   |
| `room`   | string  | â€”       | Filter to a single room name (e.g. `Drawing Room`).          |

```json
[
  {
    "id": 12,
    "device_id": 3,
    "device_name": "Work Room 1 Light 1",
    "action": "OFF",
    "actor": "user:discord:123456789",
    "timestamp": "2025-01-01T10:00:00Z"
  }
]
```

---

## 5. Simulation

### `POST /api/v1/simulation/tick`

Force a single simulation tick. Useful for tests and the frontend "refresh"
button.

**Response 200**

```json
{ "ok": true, "ticked_at": "2025-01-01T10:00:00Z" }
```

### `GET /api/v1/simulation/overview`

Convenience aggregate. Returns:

```json
{
  "total_devices": 15,
  "active_devices": 7,
  "total_power": 410,
  "active_alerts": 1,
  "rooms": [
    { "room": "Drawing Room", "active_devices": 3, "total_devices": 5, "total_power": 150 }
  ]
}
```

---

## 6. WebSocket

`ws://localhost:8000/ws`

Server ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ client messages:

```jsonc
// simulation tick
{ "type": "simulation_update", "data": { "total_power": 410, "timestamp": "..." } }

// device state change
{ "type": "device_update", "data": { "device_id": 5, "status": "ON" } }

// alert created
{ "type": "alert", "data": { "device_id": 5, "message": "...", "severity": "warning" } }
```

The server pings every 25 s; clients must reply with a pong within 30 s or
they will be dropped. The Flutter `RealtimeService` handles this automatically
with exponential reconnect back-off.

---

## 7. Error model

Every non-2xx response is `application/problem+json`:

```json
{
  "detail": "Device 99 not found"
}
```

`400` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ validation error. `404` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ resource missing. `500` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ unhandled.

---

## 8. CORS

Cross-Origin Resource Sharing is enabled. Allowed origins are
controlled by the backend env var `CORS_ALLOW_ORIGINS` (default `*`).
All standard methods are permitted (`GET`, `POST`, `PATCH`, `OPTIONS`)
and the headers `Content-Type` and `Authorization`. No credentials
are sent by the Flutter client because the dashboard authenticates
by network position (LAN-only deployment) or by a reverse-proxy IP
allow-list — see [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md).

