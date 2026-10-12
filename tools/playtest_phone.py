"""Phone play-test in WebKit (Safari's engine) with an iPhone profile: drives the joystick and BOOST
with touch pointer events (two fingers at once), checks the inputs sent and that the player moves.

usage: python tools/playtest_phone.py <out_dir> [base_url] ["iPhone 15" | "iPhone 15 landscape" | ...]
needs: pip install playwright && python -m playwright install webkit
"""
import os
import sys
from playwright.sync_api import sync_playwright
OUT = sys.argv[1]
BASE = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:8000"
DEVICE = sys.argv[3] if len(sys.argv) > 3 else "iPhone 15"
os.makedirs(OUT, exist_ok=True)
HOOK = """
(() => {
  const S = WebSocket.prototype.send;
  WebSocket.prototype.send = function (d) { try { const m = JSON.parse(d); if (m.t === 'in') window.__in = m; } catch (e) {} return S.call(this, d); };
  const O = window.WebSocket;
  window.WebSocket = function (...a) { const ws = new O(...a); ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.t === 's') window.__me = m.me; }); return ws; };
  window.WebSocket.prototype = O.prototype; window.WebSocket.OPEN = O.OPEN;
})();"""
PTR = """([sel, type, id, x, y]) => { const el = sel === 'doc' ? document.elementFromPoint(x, y) : document.querySelector(sel);
  el.dispatchEvent(new PointerEvent(type, {pointerType: 'touch', pointerId: id, isPrimary: id === 1, clientX: x, clientY: y, bubbles: true, cancelable: true, button: 0})); return el.className; }"""
with sync_playwright() as p:
    b = p.webkit.launch()
    ctx = b.new_context(**p.devices[DEVICE])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.add_init_script(HOOK)
    page.goto(BASE + "/")
    page.wait_for_timeout(3000)
    W, H = page.evaluate("[innerWidth, innerHeight]")
    print(f"{DEVICE}: {W}x{H}")
    page.screenshot(path=f"{OUT}/01-join.png")
    print("touch mode:", page.evaluate("document.body.classList.contains('touch')"),
          "| touch hint shown:", page.evaluate("getComputedStyle(document.querySelector('.touch-hint')).display !== 'none'"))
    page.fill("#name", "Phone")
    page.click("#join-form button")
    page.wait_for_timeout(3500)
    print("controls shown:", page.evaluate("getComputedStyle(document.querySelector('.boost-btn')).display !== 'none'"))
    page.screenshot(path=f"{OUT}/02-playing.png")
    ptr = lambda sel, t, i, x, y: page.evaluate(PTR, [sel, t, i, x, y])
    sx, sy = W * 0.25, H * 0.75
    start = page.evaluate("window.__me")
    print("finger lands on:", ptr("doc", "pointerdown", 1, sx, sy))
    for k in range(1, 6):
        ptr(".stick-zone", "pointermove", 1, sx + 15 * k, sy); page.wait_for_timeout(40)
    page.wait_for_timeout(1500)
    mid, inp = page.evaluate("window.__me"), page.evaluate("window.__in")
    print(f"stick right:  a={inp['a']} th={inp['th']} b={inp['b']}  moved dx={mid['x'] - start['x']:+.0f} dy={mid['y'] - start['y']:+.0f}")
    page.screenshot(path=f"{OUT}/03-stick.png")
    for k in range(1, 6):
        ptr(".stick-zone", "pointermove", 1, sx + 75, sy - 15 * k); page.wait_for_timeout(30)
    box = page.locator(".boost-btn").bounding_box()
    bx, by = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    print("2nd finger lands on:", ptr("doc", "pointerdown", 2, bx, by))
    page.wait_for_timeout(1000)
    inp, m2 = page.evaluate("window.__in"), page.evaluate("window.__me")
    cls = page.evaluate("document.querySelector('.boost-btn').className")
    print(f"stick up-right + BOOST: a={inp['a']} th={inp['th']} b={inp['b']}  moved dx={m2['x'] - mid['x']:+.0f} dy={m2['y'] - mid['y']:+.0f}  mass {m2['m']}  button: {cls}")
    page.screenshot(path=f"{OUT}/04-boost.png")
    ptr(".boost-btn", "pointerup", 2, bx, by); ptr(".stick-zone", "pointerup", 1, sx + 75, sy - 75)
    page.wait_for_timeout(400)
    inp = page.evaluate("window.__in"); print(f"both released: th={inp['th']} b={inp['b']}")
    ptr("doc", "pointerdown", 3, W * 0.7, H * 0.3); ptr("doc", "pointerup", 3, W * 0.7, H * 0.3)
    page.mouse.click(W * 0.7, H * 0.3)       # Safari also fires a fake mouse click for a tap
    page.wait_for_timeout(300)
    inp = page.evaluate("window.__in"); print(f"tap on empty screen (+ fake mouse click): b={inp['b']} th={inp['th']}")
    print("page errors:", errors[:5])
    b.close()
