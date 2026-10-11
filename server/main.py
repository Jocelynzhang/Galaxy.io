"""FastAPI app: serves the browser client and runs the authoritative game loop over WebSockets.

Protocol (JSON text frames):
  client -> server
    {"t": "join", "name": str, "vw": px, "vh": px}
    {"t": "in", "a": radians, "th": 0..1, "b": 0|1}
    {"t": "view", "vw": px, "vh": px}
  server -> client
    {"t": "welcome", "id": int, "world": [w, h], "foodR": float, "tickHz": int}
    {"t": "s", ...}  snapshot, see World.snapshot_for
    {"t": "dead", "by": name, "mass": float, "best": level index}
"""
import asyncio
import json
import math
import time
import unicodedata
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from .game import config as C
from .game.world import World

CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"


def clean_name(raw) -> str:
    if not isinstance(raw, str):
        return C.DEFAULT_NAME
    # drop control/format characters, collapse whitespace
    text = "".join(ch for ch in raw if unicodedata.category(ch)[0] != "C")
    text = " ".join(text.split())[: C.NAME_MAX_LEN]
    return text or C.DEFAULT_NAME


def _finite(v, default=0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


class Session:
    """One browser connection. Snapshots are built only when the previous one has been sent,
    so the per-client food delta (known_food) never skips a message."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.player_id: int | None = None
        self.vw, self.vh = 1280.0, 720.0
        self.known_food: dict[int, int] = {}
        self._important: deque[str] = deque()
        self._snapshot: str | None = None
        self._wake = asyncio.Event()

    @property
    def ready_for_snapshot(self) -> bool:
        return self.player_id is not None and self._snapshot is None

    def send(self, msg: dict) -> None:
        self._important.append(json.dumps(msg, separators=(",", ":")))
        self._wake.set()

    def send_snapshot(self, msg: dict) -> None:
        self._snapshot = json.dumps(msg, separators=(",", ":"))
        self._wake.set()

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
        self.sessions: set[Session] = set()
        self.by_player: dict[int, Session] = {}

    def join(self, s: Session, msg: dict) -> None:
        if s.player_id is not None:
            return
        s.set_view(msg)
        p = self.world.add_player(clean_name(msg.get("name")))
        s.player_id = p.id
        self.by_player[p.id] = s
        s.send({"t": "welcome", "id": p.id, "world": [C.WORLD_W, C.WORLD_H],
                "foodR": C.FOOD_RADIUS, "tickHz": C.TICK_HZ})

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

    async def run(self) -> None:
        dt = 1.0 / C.TICK_HZ
        next_t = time.perf_counter()
        while True:
            for d in self.world.step(dt):
                s = self.by_player.pop(d.victim_id, None)
                if s is not None:
                    s.player_id = None
                    s.send({"t": "dead", "by": d.killer_name, "mass": round(d.mass, 1), "best": d.best_level})
            if self.world.tick % C.SNAPSHOT_EVERY == 0:
                for s in self.sessions:
                    if s.ready_for_snapshot:
                        snap = self.world.snapshot_for(s.player_id, s.vw, s.vh, s.known_food)
                        snap["ts"] = round(time.perf_counter(), 4)
                        s.send_snapshot(snap)
            next_t += dt
            delay = next_t - time.perf_counter()
            if delay < -0.25:          # fell far behind (e.g. laptop slept): resync instead of bursting
                next_t = time.perf_counter()
                delay = 0
            await asyncio.sleep(max(0.0, delay))


game = Game()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(game.run())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    s = Session(ws)
    game.sessions.add(s)
    writer = asyncio.create_task(s.writer())
    try:
        while True:
            raw = await ws.receive_text()
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
