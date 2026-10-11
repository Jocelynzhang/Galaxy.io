"""Evaluate a JS expression in the game page via headless Chrome: python jseval.py '<expr>'"""
import asyncio, json, subprocess, sys, tempfile, time, urllib.request
import websockets
from playtest import CHROME, Cdp
PORT = 9334
async def main(expr):
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
                             f"--user-data-dir={tempfile.mkdtemp()}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                pages = [p for p in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list")) if p["type"] == "page"]
                if pages: break
            except OSError: pass
            time.sleep(0.2)
        async with websockets.connect(pages[0]["webSocketDebuggerUrl"]) as ws:
            cdp = Cdp(ws); pump = asyncio.create_task(cdp.pump())
            await cdp.call("Runtime.enable")
            await cdp.call("Page.navigate", url="http://127.0.0.1:8000/")
            await asyncio.sleep(1.5)
            print(await cdp.js(expr))
            pump.cancel()
    finally:
        proc.terminate()
asyncio.run(main(sys.argv[1]))
