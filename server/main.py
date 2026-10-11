"""FastAPI app: serves the browser client and runs the authoritative game loop over WebSockets.

Protocol (JSON text frames):
  client -> server
    {"t": "join", "name": str, "vw": px, "vh": px}
    {"t": "in", "a": radians, "th": 0..1, "b": 0|1}
    {"t": "view", "vw": px, "vh": px}
    {"t": "spectate"}   watch the leader without playing (menus, death screen)
  server -> client
    {"t": "hello", "world": [w, h], "foodR": float, "startMass": float}   on connect
    {"t": "welcome", "id": int, "world": [w, h], "foodR": float, "tickHz": int, "startMass": float}
    {"t": "s", ...}  snapshot, see World.snapshot_for (includes "lb" leaderboard about once a second)
    {"t": "dead", "by": name, "mass": float, "best": level index}
    {"t": "full"}   too many players right now; the connection keeps spectating

Public-hosting safeguards: per-IP and total connection caps, a human-player cap, a per-connection
message rate limit, a join cooldown, an Origin check, and a game loop that survives exceptions.
Env: GALAXY_ALLOWED_ORIGINS="https://galaxyio.fun,https://www.galaxyio.fun" (default: same host).
"""
import asyncio
import json
import logging
import math
import os
import time
import traceback
from urllib.parse import urlparse
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from .game import config as C
from .game.names import clean_name
from .game.npc import NpcManager
from .game.world import World

CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"
log = logging.getLogger("galaxyio")
ALLOWED_ORIGINS = {o.strip().rstrip("/") for o in os.environ.get("GALAXY_ALLOWED_ORIGINS", "").split(",") if o.strip()}
TRUSTED_PROXIES = {"127.0.0.1", "::1"}   # cloudflared / a reverse proxy on the same machine


def _finite(v, default=0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


class Session:
    """One browser connection. Snapshots are built only when the previous one has been sent,
    so the per-client food delta (known_food) never skips a message."""

    def __init__(self, ws: WebSocket, ip: str = "?"):
        self.ws = ws
        self.ip = ip
        self.tokens = C.MSG_BURST          # token bucket for the message rate limit
        self.last_refill = time.monotonic()
        self.dropped = 0
        self.last_join = -1e9
        self.player_id: int | None = None
        self.spectating = False
        self.vw, self.vh = 1280.0, 720.0
        self.known_food: dict[int, int] = {}
        self._important: deque[str] = deque()
        self._snapshot: str | None = None
        self._wake = asyncio.Event()

    @property
    def ready_for_snapshot(self) -> bool:
        return (self.player_id is not None or self.spectating) and self._snapshot is None

    def send(self, msg: dict) -> None:
        self._important.append(json.dumps(msg, separators=(",", ":")))
        self._wake.set()

    def send_snapshot(self, msg: dict) -> None:
        self._snapshot = json.dumps(msg, separators=(",", ":"))
        self._wake.set()

    def allow_message(self) -> bool:
        now = time.monotonic()
        self.tokens = min(C.MSG_BURST, self.tokens + (now - self.last_refill) * C.MSG_RATE)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        self.dropped += 1
        return False

    def set_view(self, msg: dict) -> None:
        self.vw = min(C.MAX_VIEW_PX, max(100.0, _finite(msg.get("vw"), self.vw)))
        self.vh = min(C.MAX_VIEW_PX, max(100.0, _finite(msg.get("vh"), self.vh)))

    async def writer(self) -> None:
        try:
            while True:
                await self._wake.wait()
                self._wake.clear()
                while self._important:
                    await self.ws.send_text(self._important.popleft())
                if self._snapshot is not None:
                    await self.ws.send_text(self._snapshot)
                    self._snapshot = None
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass  # connection gone; the reader side cleans up


class Game:
    def __init__(self):
        self.world = World()
        self.npcs = NpcManager(self.world)
        self.sessions: set[Session] = set()
        self.by_player: dict[int, Session] = {}
        self.tick_ms = 0.0               # smoothed cost of one simulation tick
        self.errors = 0

    def humans(self) -> int:
        return len(self.by_player)

    def join(self, s: Session, msg: dict) -> None:
        if s.player_id is not None:
            return
        now = time.monotonic()
        if now - s.last_join < C.JOIN_COOLDOWN_S:
            return
        s.last_join = now
        if self.humans() >= C.MAX_HUMANS:
            s.spectating = True
            s.send({"t": "full"})
            return
        s.set_view(msg)
        p = self.world.add_player(clean_name(msg.get("name")))
        s.player_id = p.id
        s.spectating = False
        self.by_player[p.id] = s
        s.send({"t": "welcome", "id": p.id, "world": [C.WORLD_W, C.WORLD_H],
                "foodR": C.FOOD_RADIUS, "tickHz": C.TICK_HZ, "startMass": C.START_MASS})

    def leave(self, s: Session) -> None:
        self.sessions.discard(s)
        if s.player_id is not None:
            self.by_player.pop(s.player_id, None)
            self.world.remove_player(s.player_id)
            s.player_id = None

    def handle(self, s: Session, msg: dict) -> None:
        kind = msg.get("t")
        if kind == "in" and s.player_id is not None:
            self.world.set_input(s.player_id, _finite(msg.get("a")), _finite(msg.get("th")), bool(msg.get("b")))
        elif kind == "join":
            self.join(s, msg)
        elif kind == "view":
            s.set_view(msg)
        elif kind == "spectate" and s.player_id is None:
            s.spectating = True

    async def run(self) -> None:
        dt = 1.0 / C.TICK_HZ
        next_t = time.perf_counter()
        while True:
            t0 = time.perf_counter()
            try:
                self.tick(dt)
            except Exception:  # never let one bad tick freeze the universe
                self.errors += 1
                log.error("game tick failed:\n%s", traceback.format_exc())
            self.tick_ms += ((time.perf_counter() - t0) * 1000 - self.tick_ms) * 0.05
            next_t += dt
            delay = next_t - time.perf_counter()
            if delay < -0.25:          # fell far behind (e.g. laptop slept): resync instead of bursting
                next_t = time.perf_counter()
                delay = 0
            await asyncio.sleep(max(0.0, delay))

    def tick(self, dt: float) -> None:
        self.npcs.update(dt)
        for d in self.world.step(dt):
            s = self.by_player.pop(d.victim_id, None)
            if s is not None:
                s.player_id = None
                s.spectating = True
                s.send({"t": "dead", "by": d.killer_name, "mass": round(d.mass, 1), "best": d.best_level})
        if self.world.tick % C.SNAPSHOT_EVERY == 0:
            # the leaderboard rides along about once a second
            lb_tick = self.world.tick % C.LEADERBOARD_EVERY == 0
            ranked = self.world.leaderboard()
            for s in self.sessions:
                if not s.ready_for_snapshot:
                    continue
                if s.player_id is not None:
                    snap = self.world.snapshot_for(s.player_id, s.vw, s.vh, s.known_food,
                                                   ranked if lb_tick else None)
                elif ranked:   # spectators watch the current leader
                    snap = self.world.snapshot_for(ranked[0].id, s.vw, s.vh, s.known_food,
                                                   ranked if lb_tick else None, spectating=True)
                else:
                    continue
                snap["ts"] = round(time.perf_counter(), 4)
                s.send_snapshot(snap)


game = Game()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(game.run())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/healthz")
async def healthz():
    return {"ok": True, "tick": game.world.tick, "tick_ms": round(game.tick_ms, 2), "errors": game.errors,
            "connections": len(game.sessions), "humans": game.humans(), "objects": len(game.world.players)}


def client_ip(ws: WebSocket) -> str:
    host = ws.client.host if ws.client else "?"
    if host in TRUSTED_PROXIES:   # behind cloudflared the real visitor IP is in a header
        return ws.headers.get("cf-connecting-ip") or ws.headers.get("x-forwarded-for", host).split(",")[0].strip()
    return host


def origin_allowed(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    if origin is None:            # non-browser clients (tests, load tools) send no Origin
        return True
    origin = origin.rstrip("/")
    if ALLOWED_ORIGINS:
        return origin in ALLOWED_ORIGINS
    return urlparse(origin).netloc == ws.headers.get("host")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    ip = client_ip(ws)
    if not origin_allowed(ws):
        log.warning("rejected websocket from origin %s", ws.headers.get("origin"))
        await ws.close(code=1008)
        return
    if len(game.sessions) >= C.MAX_CONNECTIONS or sum(1 for x in game.sessions if x.ip == ip) >= C.MAX_CONNECTIONS_PER_IP:
        await ws.close(code=1013)  # try again later
        return
    await ws.accept()
    s = Session(ws, ip)
    game.sessions.add(s)
    writer = asyncio.create_task(s.writer())
    s.send({"t": "hello", "world": [C.WORLD_W, C.WORLD_H], "foodR": C.FOOD_RADIUS, "startMass": C.START_MASS})
    try:
        while True:
            raw = await ws.receive_text()
            if not s.allow_message():
                if s.dropped > C.MSG_ABUSE_DROPS:
                    log.warning("closing flooding connection from %s", ip)
                    await ws.close(code=1008)
                    break
                continue
            if len(raw) > 512:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if isinstance(msg, dict):
                game.handle(s, msg)
    except (WebSocketDisconnect, KeyError):  # KeyError: client sent a binary frame
        pass
    finally:
        writer.cancel()
        game.leave(s)


app.mount("/", StaticFiles(directory=CLIENT_DIR, html=True), name="client")
