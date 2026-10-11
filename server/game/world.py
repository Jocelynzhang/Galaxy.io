"""Authoritative world state and simulation step. No networking in here."""
import itertools
import math
import random
from dataclasses import dataclass

from . import config as C
from .entities import Food, Player, radius_for
from .levels import level_index
from .physics import can_eat, overlaps_to_eat, speed_for, zoom_for


class FoodGrid:
    """Uniform spatial hash of food ids, so eating and view queries only scan nearby cells."""

    def __init__(self, cell: float = C.GRID_CELL):
        self.cell = cell
        self.cells: dict[tuple[int, int], set[int]] = {}

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return int(x // self.cell), int(y // self.cell)

    def add(self, f: Food) -> None:
        self.cells.setdefault(self._key(f.x, f.y), set()).add(f.id)

    def remove(self, f: Food) -> None:
        key = self._key(f.x, f.y)
        bucket = self.cells.get(key)
        if bucket is not None:
            bucket.discard(f.id)
            if not bucket:
                del self.cells[key]

    def query_rect(self, x0: float, y0: float, x1: float, y1: float):
        cx0, cy0 = self._key(x0, y0)
        cx1, cy1 = self._key(x1, y1)
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                bucket = self.cells.get((cx, cy))
                if bucket:
                    yield from bucket


@dataclass
class Death:
    victim_id: int
    killer_name: str
    mass: float          # victim's mass when eaten
    best_level: int


class World:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.tick = 0
        self.players: dict[int, Player] = {}
        self.food: dict[int, Food] = {}
        self.grid = FoodGrid()
        self.best_level: dict[int, int] = {}
        self._ids = itertools.count(1)
        self._food_ids = itertools.count(1)
        for _ in range(C.FOOD_TARGET):
            self._spawn_food()

    # ---------- players ----------
    def add_player(self, name: str, is_bot: bool = False) -> Player:
        x, y = self._free_spot(radius_for(C.START_MASS))
        p = Player(id=next(self._ids), name=name, x=x, y=y, is_bot=is_bot)
        self.players[p.id] = p
        self.best_level[p.id] = 0
        return p

    def remove_player(self, pid: int) -> None:
        self.players.pop(pid, None)
        self.best_level.pop(pid, None)

    def set_input(self, pid: int, angle: float, throttle: float, boost: bool) -> None:
        p = self.players.get(pid)
        if p is None:
            return
        p.angle = angle
        p.throttle = min(1.0, max(0.0, throttle))
        p.boost = boost

    def _free_spot(self, r: float) -> tuple[float, float]:
        """Random position not inside any player (gives up after a few tries)."""
        for _ in range(30):
            x = self.rng.uniform(r, C.WORLD_W - r)
            y = self.rng.uniform(r, C.WORLD_H - r)
            if all(math.hypot(x - p.x, y - p.y) > p.radius + r + 50 for p in self.players.values()):
                return x, y
        return x, y

    # ---------- food ----------
    def _spawn_food(self) -> None:
        f = Food(
            id=next(self._food_ids),
            x=self.rng.uniform(0, C.WORLD_W),
            y=self.rng.uniform(0, C.WORLD_H),
            color=self.rng.randrange(C.FOOD_COLORS),
            moved_tick=self.tick,
        )
        self.food[f.id] = f
        self.grid.add(f)

    def _remove_food(self, fid: int) -> None:
        f = self.food.pop(fid)
        self.grid.remove(f)

    # ---------- simulation ----------
    def step(self, dt: float) -> list[Death]:
        self.tick += 1
        for p in self.players.values():
            self._move(p, dt)
        for p in self.players.values():
            self._eat_food(p)
        deaths = self._eat_players()
        for p in self.players.values():
            lvl = level_index(p.mass)
            if lvl > self.best_level[p.id]:
                self.best_level[p.id] = lvl
        missing = C.FOOD_TARGET - len(self.food)
        for _ in range(min(missing, C.FOOD_SPAWN_PER_TICK)):
            self._spawn_food()
        return deaths

    def _move(self, p: Player, dt: float) -> None:
        v = speed_for(p.mass) * p.throttle
        tvx, tvy = math.cos(p.angle) * v, math.sin(p.angle) * v
        k = min(1.0, C.ACCEL * dt)
        p.vx += (tvx - p.vx) * k
        p.vy += (tvy - p.vy) * k
        r = p.radius
        p.x = min(C.WORLD_W - r, max(r, p.x + p.vx * dt))
        p.y = min(C.WORLD_H - r, max(r, p.y + p.vy * dt))

    def _eat_food(self, p: Player) -> None:
        r = p.radius
        eaten = [
            fid for fid in self.grid.query_rect(p.x - r, p.y - r, p.x + r, p.y + r)
            if math.hypot(self.food[fid].x - p.x, self.food[fid].y - p.y) < r
        ]
        for fid in eaten:
            p.mass += self.food[fid].mass
            self._remove_food(fid)

    def _eat_players(self) -> list[Death]:
        deaths: list[Death] = []
        # biggest first, so a big player eats before possibly being eaten itself
        order = sorted(self.players.values(), key=lambda q: q.mass, reverse=True)
        gone: set[int] = set()
        for a in order:
            if a.id in gone:
                continue
            for b in order:
                if b is a or b.id in gone or not can_eat(a.mass, b.mass):
                    continue
                if overlaps_to_eat(a.x, a.y, a.radius, b.x, b.y, b.radius):
                    a.mass += b.mass * C.EAT_EFFICIENCY
                    gone.add(b.id)
                    deaths.append(Death(b.id, a.name, b.mass, self.best_level[b.id]))
        for pid in gone:
            self.remove_player(pid)
        return deaths

    # ---------- snapshots ----------
    def snapshot_for(self, pid: int, view_w: float, view_h: float, known_food: dict[int, int]) -> dict:
        """State visible to one player. `known_food` (food id -> tick last sent) is updated in place,
        so only new/moved food is sent and the client is told which ids to forget."""
        me = self.players[pid]
        zoom = zoom_for(me.mass)
        hw = view_w / 2 / zoom + C.VIEW_MARGIN
        hh = view_h / 2 / zoom + C.VIEW_MARGIN
        x0, y0, x1, y1 = me.x - hw, me.y - hh, me.x + hw, me.y + hh

        players = [
            [p.id, round(p.x, 1), round(p.y, 1), round(p.radius, 1), level_index(p.mass), p.name, int(p.is_bot)]
            for p in self.players.values()
            if x0 - p.radius < p.x < x1 + p.radius and y0 - p.radius < p.y < y1 + p.radius
        ]

        visible = set(self.grid.query_rect(x0, y0, x1, y1))
        added = []
        for fid in visible:
            f = self.food[fid]
            if known_food.get(fid, -1) < f.moved_tick:
                added.append([fid, round(f.x), round(f.y), f.color])
            known_food[fid] = self.tick
        removed = [fid for fid in known_food if fid not in visible]
        for fid in removed:
            del known_food[fid]

        return {
            "t": "s",
            "tk": self.tick,
            "me": {"id": pid, "x": round(me.x, 1), "y": round(me.y, 1), "m": round(me.mass, 1),
                   "lvl": level_index(me.mass)},
            "z": round(zoom, 4),
            "p": players,
            "f": added,
            "fr": removed,
        }
