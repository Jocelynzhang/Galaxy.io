"""Play Universe IO in headless Chrome via the DevTools protocol: steer toward food, boost, screenshot.

usage: python playtest.py <out_dir> [seconds] [base_url]
"""
import asyncio
import base64
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1280, 720
PORT = 9333
BASE = sys.argv[3].rstrip("/") if len(sys.argv) > 3 else "http://127.0.0.1:8000"


class Cdp:
    def __init__(self, ws):
        self.ws, self.n, self.pending, self.console = ws, 0, {}, []

    async def pump(self):
        async for raw in self.ws:
            m = json.loads(raw)
            if "id" in m and m["id"] in self.pending:
                self.pending.pop(m["id"]).set_result(m)
            elif m.get("method") == "Runtime.consoleAPICalled":
                self.console.append(" ".join(str(a.get("value", a.get("description"))) for a in m["params"]["args"]))
            elif m.get("method") == "Runtime.exceptionThrown":
                self.console.append("EXCEPTION " + json.dumps(m["params"]["exceptionDetails"])[:400])

    async def call(self, method, **params):
        self.n += 1
        fut = asyncio.get_running_loop().create_future()
        self.pending[self.n] = fut
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        res = await fut
        if "error" in res:
            raise RuntimeError(res["error"])
        return res.get("result", {})

    async def js(self, expr):
        r = await self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    async def mouse(self, kind, x, y, button="none"):
        await self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button=button,
                        buttons=1 if button == "left" and kind != "mouseReleased" else 0, clickCount=1)

    async def shot(self, path):
        r = await self.call("Page.captureScreenshot", format="png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))


async def main(out, seconds):
    prof = tempfile.mkdtemp(prefix="gio-")
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={prof}",
                             "--use-angle=swiftshader", "--enable-unsafe-swiftshader", f"--window-size={W},{H}",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
                if pages:
                    break
            except OSError:
                pass
            time.sleep(0.2)
        page = next(p for p in pages if p["type"] == "page")
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
            cdp = Cdp(ws)
            pump = asyncio.create_task(cdp.pump())
            await cdp.call("Runtime.enable")
            await cdp.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
            await cdp.call("Page.navigate", url=BASE + "/")
            await asyncio.sleep(2)
            await cdp.shot(f"{out}/01-join.png")
            # type a name and press Confirm like a kid would
            await cdp.js("document.getElementById('name').value = 'Claude'")
            await cdp.js("document.querySelector('#join-form button').click()")
            await asyncio.sleep(2.5)
            await cdp.shot(f"{out}/02-spawn.png")

            t0 = time.time()
            shots = 3
            boosting = False
            while time.time() - t0 < seconds:
                # steer: aim at a slowly rotating heading, boost in short bursts every ~8 s
                t = time.time() - t0
                a = t * 0.35
                x, y = W / 2 + math.cos(a) * 300, H / 2 + math.sin(a) * 220
                await cdp.mouse("mouseMoved", x, y, "left" if boosting else "none")
                want_boost = (t % 8) < 1.5 and t > 5
                if want_boost != boosting:
                    await cdp.mouse("mousePressed" if want_boost else "mouseReleased", x, y, "left")
                    boosting = want_boost
                    if want_boost:
                        await asyncio.sleep(0.6)
                        await cdp.shot(f"{out}/{shots:02d}-boost.png")
                        shots += 1
                dead = await cdp.js("!document.getElementById('dead').hidden")
                if dead:
                    await cdp.shot(f"{out}/{shots:02d}-dead.png")
                    shots += 1
                    print("died at", round(t), "s:", await cdp.js("document.getElementById('dead-msg').textContent"))
                    await cdp.js("document.getElementById('again').click()")
                await asyncio.sleep(0.1)
            await cdp.shot(f"{out}/{shots:02d}-end.png")
            hud = await cdp.js("""JSON.stringify({lvl: document.getElementById('lvl-cur').textContent,
                real: document.getElementById('real-mass').textContent,
                fill: document.getElementById('prog-fill').style.width,
                me: document.getElementById('lb-me').textContent,
                toast: document.getElementById('toast').hidden ? '' : document.querySelector('.toast-title').textContent})""")
            print("HUD:", hud)
            print("console:", cdp.console[-10:])
            pump.cancel()
    finally:
        proc.terminate()


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    asyncio.run(main(out, float(sys.argv[2]) if len(sys.argv) > 2 else 40))
