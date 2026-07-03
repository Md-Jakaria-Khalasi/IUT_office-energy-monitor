# API Documentation

The backend exposes two surfaces:

| Surface     | Base path      | Description                                |
|-------------|----------------|--------------------------------------------|
| REST        | `/api/v1`      | JSON HTTP API consumed by the bot & web    |
| WebSocket   | `/ws`          | Realtime push of device updates & alerts   |

OpenAPI / Swagger is available at:

- Swagger UI  – `GET /docs`
- OpenAPI 3.0 – `GET /openapi.json`

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

Returns the last **N** alerts (default 50).

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

---

## 4. Activities

### `GET /api/v1/activities/`

Recent device activity events.

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

Server → client messages:

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

`400` – validation error. `404` – resource missing. `500` – unhandled.