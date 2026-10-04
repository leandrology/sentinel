"""Modernized copy of reference_generator.py. Run: python scripts/run_simulator.py."""

import asyncio
import datetime
import json
import os
import random
import uuid

import websockets

TYPES = [
    "motion_detected", "perimeter_breach", "door_forced", "glass_break",
    "smoke_detected", "fire_alarm", "object_detected", "loitering",
    "camera_offline", "panic_button",
]
CAMERA = {"motion_detected", "object_detected", "loitering", "glass_break"}


def _get_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def get_delay_range() -> tuple[float, float]:
    """Incident interval in seconds. Defaults to 30s~40s random."""
    min_d = _get_float_env("SIMULATOR_MIN_DELAY_S", 30.0)
    max_d = _get_float_env("SIMULATOR_MAX_DELAY_S", 40.0)
    if min_d > max_d:
        min_d, max_d = max_d, min_d
    return max(0.0, min_d), max(0.0, max_d)


def make_event() -> dict:
    t = random.choice(TYPES)
    return {
        "event_id": "evt_" + uuid.uuid4().hex[:10],
        "site_id": f"site-{random.randint(100, 106)}",
        "zone": random.choice(
            ["north-perimeter", "lobby", "loading-dock", "roof", "server-room"]
        ),
        "type": t,
        "source": "camera" if t in CAMERA else "sensor",
        "confidence": round(random.uniform(0.35, 0.99), 2),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "snapshot_url": None,
        "metadata": {"object": random.choice(["person", "vehicle", "animal"])}
        if t == "object_detected"
        else {},
    }


async def handler(ws: websockets.ServerConnection) -> None:
    while True:
        await ws.send(json.dumps(make_event()))
        min_d, max_d = get_delay_range()
        await asyncio.sleep(random.uniform(min_d, max_d))


async def main() -> None:
    host = os.getenv("SIMULATOR_HOST", "0.0.0.0")
    port = int(os.getenv("SIMULATOR_PORT", "8765"))
    min_d, max_d = get_delay_range()
    async with websockets.serve(handler, host, port):
        print(f"Event stream live on ws://{host}:{port} (event every {min_d:g}~{max_d:g}s)")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
