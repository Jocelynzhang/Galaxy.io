"""Headless smoke test: N bots join, steer, and we measure snapshot rate and bandwidth."""
import asyncio
import json
import math
import sys
import time

import websockets

URL = "ws://127.0.0.1:8000/ws"


async def bot(i, secs, stats):
    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps({"t": "join", "name": f"bot{i}", "vw": 1280, "vh": 720}))
        t0 = time.time()
        n = nbytes = 0
        first = None
        last = None
        while time.time() - t0 < secs:
            await ws.send(json.dumps({"t": "in", "a": i, "th": 1, "b": 0}))
            try:
                raw = await asyncio.wait_for(ws.recv(), 0.2)
            except asyncio.TimeoutError:
                continue
            msg = json.loads(raw)
            if msg["t"] == "s":
                n += 1
                nbytes += len(raw)
                first = first or msg
                last = msg
            elif msg["t"] == "dead":
                stats.setdefault("deaths", []).append((f"bot{i}", msg))
                await ws.send(json.dumps({"t": "join", "name": f"bot{i}", "vw": 1280, "vh": 720}))
        stats[i] = dict(snaps_per_s=n / secs, kb_per_s=nbytes / secs / 1024,
                        first_food=len(first["f"]) if first else 0,
                        moved=round(math.hypot(last["me"]["x"] - first["me"]["x"], last["me"]["y"] - first["me"]["y"])) if first else 0,
                        mass=last["me"]["m"] if last else None)


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 4
    stats = {}
    await asyncio.gather(*(bot(i, secs, stats) for i in range(n)))
    for k, v in stats.items():
        print(k, v)


asyncio.run(main())
