# ESP32 Hardware – Bill of Materials, Wiring & Electrical Notes

This document describes the physical hardware used in the Office Energy Monitor
project. It complements the **simulator** that runs in software: every simulated
device is mirrored by real hardware that an ESP32 can report to the backend.

> **Important – Wokwi JSON rule**
>
> Per the project rules we **never** generate a `wokwi.json` automatically. Use
> the official Wokwi template or build the diagram manually in the Wokwi UI.
> The schema below is intentionally textual so it is safe to commit.

---

## 1. Overview

```
   ┌──────────┐      AC mains / DC         ┌────────────────┐
   │  Load    │ ◄───────── relay ──────────│   ESP32 Wroom  │
   │ (fan /   │                            │                │
   │  light)  │      optocoupler (5V↔3V3)  │   (Wi-Fi /     │
   └──────────┘                            │    MQTT)       │
                                           └──────┬─────────┘
                                                  │ Wi-Fi
                                              ┌───┴────────┐
                                              │   Router   │
                                              └─────┬──────┘
                                                    │
                                          ┌─────────┴────────┐
                                          │  Backend (REST + │
                                          │  WebSocket)      │
                                          └──────────────────┘
```

Each ESP32 module is responsible for **one room** (Drawing Room, Work Room 1,
Work Room 2) and reads up to 5 devices in that room.

---

## 2. Bill of Materials (per room)

| Qty | Component                              | Purpose                                     |
|----:|----------------------------------------|---------------------------------------------|
|  1  | ESP32-DevKitC V4 (ESP-WROOM-32)        | MCU, runs telemetry firmware                |
|  1  | 5 V / 2 A USB power supply (or 5V BEC)  | Powers ESP32 + relay board                  |
|  5  | 5 V SPST relay module (active LOW)      | Switches AC/DC loads                        |
|  1  | HLK-PM01 (or Hi-Link 5V module)        | Mains → 5 V DC isolation for whole board    |
|  1  | 16 × 2 LCD (I²C backpack)               | Local room view (optional)                  |
|  1  | 3.3 V ↔ 5 V level shifter (or optocou.) | ESP32 GPIO → relay board                    |
|  1  | ACS712-20A current sensor              | Measures aggregate current per room         |
|  5  | Resistors 220 Ω                        | Status-LED current limiting                 |
|  5  | LEDs (green = ON, red = OFF)           | Per-device visible status                   |
|  *  | Wago 221-413 splices, 22 AWG hookup    | Mains wiring                                |

> **Safety note** – Mains voltages are present. Use optocouplers **and**
> physical relays. Do not power the AC side without an earth connection.

---

## 3. ESP32 pin mapping (per room)

We use **5 devices** per room (2 fans + 3 lights, matching the simulation):

| Device # | Device Type | Logical Name         | ESP32 GPIO | ADC Channel | Notes                  |
|---------:|-------------|----------------------|-----------:|------------:|------------------------|
| 0        | Fan         | `FAN_1`              | GPIO 25    | –           | Relay + status LED     |
| 1        | Fan         | `FAN_2`              | GPIO 26    | –           | Relay + status LED     |
| 2        | Light       | `LIGHT_1`            | GPIO 27    | –           | Relay + status LED     |
| 3        | Light       | `LIGHT_2`            | GPIO 32    | –           | Relay + status LED     |
| 4        | Light       | `LIGHT_3`            | GPIO 33    | –           | Relay + status LED     |
| –        | Current     | `ACS712`             | GPIO 34    | ADC1_CH6    | Input-only, 0–5 V→0–3 V |
| –        | I²C SDA/SCL | LCD                  | GPIO 21/22 | –           | 4.7 kΩ pull-ups        |

GPIO 34 is **input-only**, which is fine for the ACS712 analogue output.

---

## 4. Wiring table

| Net              | From                  | To                  | Wire           |
|------------------|-----------------------|---------------------|----------------|
| `5V_RAIL`        | HLK-PM01 V+           | Relay VCC, LCD VCC  | 22 AWG red     |
| `3V3_RAIL`       | ESP32 3V3             | Level shifter HV    | 22 AWG red     |
| `GND`            | HLK-PM01 V− / ESP32 GND | All relay GND, LCD GND | 22 AWG black |
| `FAN1_CTRL`      | GPIO 25               | Level shifter IN1   | hookup         |
| `FAN1_RELAY`     | Level shifter OUT1    | Relay IN1           | hookup         |
| `FAN1_LINE`      | Relay COM             | L (mains black)     | 18 AWG mains   |
| `FAN1_LOAD`      | Relay NO              | Fan line            | 18 AWG mains   |
| …                | … (repeat for each)   | …                   | …              |
| `ACS712_OUT`     | ACS712 OUT pin        | GPIO 34             | hookup         |
| `I2C_SDA`        | GPIO 21               | LCD SDA             | 22 AWG yellow  |
| `I2C_SCL`        | GPIO 22               | LCD SCL             | 22 AWG blue    |

> Repeat the `*_CTRL` / `*_RELAY` / `*_LINE` / `*_LOAD` pattern for each of the
> five devices per room.

---

## 5. Electrical explanation

1. **Mains isolation** – A single HLK-PM01 isolated AC/DC module provides the
   entire 5 V rail; it is rated 3 kV isolation.
2. **Logical isolation** – Each relay coil is driven through an optocoupler
   (`PC817`-equivalents on most blue relay boards). The opto's LED side is
   driven from the ESP32 with a 470 Ω resistor; the phototransistor side
   switches 5 V to the relay coil.
3. **Status feedback** – The relay's NO contact feeds an LED + resistor to
   indicate that the high-voltage contact is actually closed (defensive
   programming against a stuck relay).
4. **Current sensing** – The ACS712 outputs a centred 2.5 V (no current) with
   ±185 mV/A. We bias and read it on ADC1_CH6 once per second. The firmware
   applies the calibration constant `0.026 V → 5 V` (1/220 V of measured mains
   current) to report a wattage figure.
5. **Bounded accuracy** – A fan is assumed to be `75 W`, a light `20 W`. Sensor
   data is rounded to whole watts and clipped at `0–5000 W` to avoid spurious
   noise turning into alerts.
6. **Network** – Each ESP32 joins the office Wi-Fi via WPA2-PSK. On boot it
   emits a single MQTT message per device (`office/<room>/<device>`) and
   subscribes to the backend's `SetDeviceStatus` event topic. When offline,
   the local firmware continues to switch the relays so users can still turn
   fans/lights on manually.

---

## 6. Calibration & power mapping

```text
FAN   →  75 W  (always-on load)
LIGHT →  20 W  (always-on load)

office_hours = 08:00 .. 18:00 (local server time)
alert_threshold_w = 1500      # settable via env
simulator_tick    = 5 seconds # settable via env
```

The simulator mirrors these constants exactly. When real ESP32 modules are
online the backend prefers their reported wattage; otherwise it uses the
device's stored nominal wattage.

---

## 7. Where to find firmware

The firmware lives in `firmware/esp32/` (placeholder – drop your Arduino /
ESP-IDF sketch here). It must publish a JSON payload of the form:

```json
{
  "device_id": 0,
  "status": "ON",
  "power_consumption": 75,
  "timestamp": "2025-01-01T10:00:00Z"
}
```

> Do **not** commit a generated `wokwi.json`. If you need a Wokwi diagram, open
> Wokwi manually and re-create the wiring described above.

---

## 8. Simulation engine vs real hardware

The backend has **two interchangeable telemetry sources**, and you can run
either one, both, or switch between them without changing the dashboard.

### 8.1 What the simulator does

A background task in `backend/app/services/scheduler.py` (started from
`app/main.py` at FastAPI startup) ticks every `SIMULATION_INTERVAL_SECONDS`
(default `5`). Each tick:

1. Reads every device from SQLite.
2. For each device, decides an action based on the device's
   `toggle_probability_office_hours` (or `_off_hours`) seed:
   - **ON → OFF** when below threshold for >10 ticks.
   - **OFF → ON** with a small probability per tick during office hours,
     zero probability outside them.
3. Updates `device.status`, `power_consumption`, `last_changed`.
4. Logs an `Activity` row.
5. Aggregates totals per room and the whole office.
6. If the rolling average power over the last few ticks exceeds
   `ALERT_WATT_THRESHOLD` (default `1500` W), inserts an `Alert` row and
   broadcasts an `alert` event on `/ws`.
7. Broadcasts a `simulation_tick` and `device_update` envelope on `/ws`.

The gate is `OFFICE_START_HOUR` / `OFFICE_END_HOUR` (default `08`–`18`,
Mon–Fri) in `backend/app/core/constants.py`. Outside office hours the
simulator still ticks but only flips devices OFF, never ON.

### 8.2 What the firmware does

Each ESP32 in `firmware/esp32/` (placeholder) runs the same shape of
loop **locally**:

1. Reads relay status (GPIO) for the 5 devices in its room.
2. Reads `ACS712` on ADC1_CH6 once per second, applies the `0.026 V → 5 V`
   calibration, rounds to whole watts, clips to `0–5000 W`.
3. Publishes the JSON payload documented in section 7 to
   `office/<room>/<device>` (MQTT) **or** POSTs the same body to
   `PATCH /api/v1/devices/{device_id}` on the FastAPI backend.

The wire shape is identical; the backend cannot tell the difference
between a simulator tick and a real firmware report — both end up as
the same Pydantic-shaped device update row.

### 8.3 How to switch between them

| Mode                         | Set in `backend/.env`                                       | Effect on dashboard                                   |
|------------------------------|------------------------------------------------------------|-------------------------------------------------------|
| **Simulator only** (default) | `SIMULATION_ENABLED=true`, no MQTT broker required         | Devices toggle every 5 s, watts drift ±20% of nominal. |
| **Firmware only**            | `SIMULATION_ENABLED=false`, set `MQTT_URL`, `MQTT_TOPIC`    | Backend ingests only ESP32 reports; no auto-toggling. |
| **Hybrid (sim + firmware)**  | `SIMULATION_ENABLED=true`, ESP32 also reporting             | Firmware reports win when fresh; simulator keeps the rest of the room alive. |

There is no `wokwi.json` committed. To prototype firmware without
hardware, open Wokwi manually, paste the pin map from section 3, and
point the firmware's MQTT / HTTP target at your local backend.
