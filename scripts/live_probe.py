"""Live verification: drives the same network calls the Flutter dashboard makes."""
import asyncio
import json
import urllib.request

import websockets


BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws"


def fetch(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as r:
        return json.loads(r.read())


def main() -> int:
    health = fetch("/health")
    rooms = fetch("/api/v1/rooms/")
    devices = fetch("/api/v1/devices/")
    alerts = fetch("/api/v1/alerts/")

    print(f"health: {health}")
    print(f"rooms ({len(rooms)}):")
    for r in rooms:
        print(f"  - {r['room']}: {r['active_devices']}/{r['total_devices']} active, {r['total_power']} W")
    print(f"devices: {len(devices)} total")
    on = [d for d in devices if d.get("status") == "on"]
    print(f"  on: {len(on)}, off: {len(devices) - len(on)}")
    print(f"alerts (open): {len(alerts)}")

    async def ws_probe() -> None:
        async with websockets.connect(WS, open_timeout=5) as ws:
            welcome = json.loads(await ws.recv())
            assert welcome["type"] == "welcome", welcome
            tick = json.loads(await ws.recv())
            assert tick["type"] == "simulation_tick", tick
            print(f"welcome: {welcome}")
            print(f"first tick: total_power={tick['data']['total_power']} W, changed={len(tick['data']['changed'])}")

    asyncio.run(ws_probe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())