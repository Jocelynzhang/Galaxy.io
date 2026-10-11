"""Authoritative world state and simulation step. No networking in here."""
import itertools
import math
import random
from dataclasses import dataclass

from . import config as C
from .entities import Food, Player, radius_for
from .levels import level_index, real_mass_kg
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

    def move(self, f: Food, x: float, y: float) -> None:
        if self._key(f.x, f.y) != self._key(x, y):
            self.remove(f)
            f.x, f.y = x, y
            self.add(f)
        else:
            f.x, f.y = x, y

    def query_rect(self, x0: float, y0: float, x1: float, y1: float) -> list[int]:
        cx0, cy0 = self._key(x0, y0)
        cx1, cy1 = self._key(x1, y1)
        out: list[int] = []
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                bucket = self.cells.get((cx, cy))
                if bucket:
                    out.extend(bucket)
        return out


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
        self.natural_food = 0            # food count excluding boost ejecta
        self.flying: set[int] = set()    # food ids that still have velocity
        self.grid = FoodGrid()
        self.best_level: dict[int, int] = {}
        self._ids = itertools.count(1)
        self._food_ids = itertools.count(1)
        for _ in range(C.FOOD_TARGET):
            self._spawn_food()

    # ---------- players ----------
    def add_player(self, name: str, is_bot: bool = False, mass: float = C.START_MASS) -> Player:
        x, y = self._free_spot(radius_for(mass), mass)
        p = Player(id=next(self._ids), name=name, x=x, y=y, mass=mass, is_bot=is_bot,
                   shield_until=self.tick + round(C.SPAWN_SHIELD_S * C.TICK_HZ))
        self.players[p.id] = p
        self.best_level[p.id] = level_index(mass)
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

    def shielded(self, p: Player) -> bool:
        return self.tick < p.shield_until

    def _free_spot(self, r: float, mass: float) -> tuple[float, float]:
        """Random position far from anything that could eat a newcomer of `mass`. Tries a few
        candidates and keeps the safest one."""
        best, best_gap = (C.WORLD_W / 2, C.WORLD_H / 2), -math.inf
        for _ in range(40):
            x = self.rng.uniform(r, C.WORLD_W - r)
            y = self.rng.uniform(r, C.WORLD_H - r)
            gap = min((math.hypot(x - p.x, y - p.y) - p.radius - r - (C.SPAWN_SAFE_DIST if can_eat(p.mass, mass) else 50)
                       for p in self.players.values()), default=math.inf)
            if gap >= 0:
                return x, y
            if gap > best_gap:
                best, best_gap = (x, y), gap
        return best

    # ---------- food ----------
    def _add_food(self, f: Food) -> None:
        self.food[f.id] = f
        self.grid.add(f)
        if f.owner:
            self.flying.add(f.id)
        else:
            self.natural_food += 1

    def _spawn_food(self) -> None:
        self._add_food(Food(
            id=next(self._food_ids),
            x=self.rng.uniform(0, C.WORLD_W),
            y=self.rng.uniform(0, C.WORLD_H),
            color=self.rng.randrange(C.FOOD_COLORS),
            moved_tick=self.tick,
        ))

    def _remove_food(self, fid: int) -> None:
        f = self.food.pop(fid)
        self.grid.remove(f)
        self.flying.discard(fid)
        if not f.owner:
            self.natural_food -= 1

    def _eject(self, p: Player, mass: float) -> None:
        """Shoot a pellet of `mass` out of the back of `p`."""
        a = p.angle + math.pi + self.rng.uniform(-C.EJECTA_SPREAD, C.EJECTA_SPREAD)
        ca, sa = math.cos(a), math.sin(a)
        f = Food(id=next(self._food_ids), x=0, y=0, mass=mass,
                 color=C.EJECTA_COLOR_BASE + level_index(p.mass), moved_tick=self.tick, owner=p.id,
                 edible_tick=self.tick + round(C.EJECTA_ARM_S * C.TICK_HZ),
                 owner_edible_tick=self.tick + round(C.EJECTA_OWNER_ARM_S * C.TICK_HZ))
        dist = p.radius + f.radius + 2
        f.x = min(C.WORLD_W, max(0.0, p.x + ca * dist))
        f.y = min(C.WORLD_H, max(0.0, p.y + sa * dist))
        speed = C.EJECTA_SPEED * self.rng.uniform(0.8, 1.1)
        f.vx, f.vy = ca * speed, sa * speed
        self._add_food(f)

    # ---------- simulation ----------
    def step(self, dt: float) -> list[Death]:
        self.tick += 1
        for p in self.players.values():
            self._move(p, dt)
            self._decay(p, dt)
        self._move_food(dt)
        for p in self.players.values():
            self._eat_food(p)
        deaths = self._eat_players()
        for p in self.players.values():
            lvl = level_index(p.mass)
            if lvl > self.best_level[p.id]:
                self.best_level[p.id] = lvl
        missing = C.FOOD_TARGET - self.natural_food
        for _ in range(min(missing, C.FOOD_SPAWN_PER_TICK)):
            self._spawn_food()
        return deaths

    def _move(self, p: Player, dt: float) -> None:
        v = speed_for(p.mass) * p.throttle
        p.boosting = p.boost and p.throttle > 0.1 and p.mass >= C.BOOST_MIN_MASS
        if p.boosting:
            v *= C.BOOST_MULT
            loss = C.BOOST_LOSS_FRAC * p.mass * dt
            p.mass -= loss
            p.boost_debt += loss
            pellet = min(C.EJECTA_MASS_MAX, max(C.EJECTA_MASS_MIN, p.mass * C.EJECTA_MASS_FRAC))
            while p.boost_debt >= pellet:
                p.boost_debt -= pellet
                self._eject(p, pellet)
        tvx, tvy = math.cos(p.angle) * v, math.sin(p.angle) * v
        k = min(1.0, C.ACCEL * dt)
        p.vx += (tvx - p.vx) * k
        p.vy += (tvy - p.vy) * k
        r = p.radius
        p.x = min(C.WORLD_W - r, max(r, p.x + p.vx * dt))
        p.y = min(C.WORLD_H - r, max(r, p.y + p.vy * dt))

    def _decay(self, p: Player, dt: float) -> None:
        p.mass -= p.mass * C.DECAY[level_index(p.mass)] * dt

    def _move_food(self, dt: float) -> None:
        moves: dict[int, tuple[float, float]] = {}
        # flying ejecta coast and slow down
        drag = math.exp(-C.EJECTA_DRAG * dt)
        for fid in list(self.flying):
            f = self.food[fid]
            f.vx *= drag
            f.vy *= drag
            moves[fid] = (f.x + f.vx * dt, f.y + f.vy * dt)
            if f.vx * f.vx + f.vy * f.vy < 25:
                f.vx = f.vy = 0.0
                self.flying.discard(fid)
        # gravity: big objects pull food (never players) toward themselves
        for p in self.players.values():
            g = C.GRAVITY[level_index(p.mass)]
            if g <= 0:
                continue
            r = p.radius
            reach = r * C.GRAVITY_REACH
            for fid in self.grid.query_rect(p.x - reach, p.y - reach, p.x + reach, p.y + reach):
                f = self.food[fid]
                if f.owner == p.id and not f.edible_by(p.id, self.tick):
                    continue  # don't suck your own exhaust straight back in
                fx, fy = moves.get(fid, (f.x, f.y))
                dx, dy = p.x - fx, p.y - fy
                d = math.hypot(dx, dy)
                if d < 1e-6 or d > reach:
                    continue
                step = min(C.GRAVITY_MAX_SPEED, g * (r / d) ** 2) * dt
                step = min(step, d)
                moves[fid] = (fx + dx / d * step, fy + dy / d * step)
        for fid, (x, y) in moves.items():
            f = self.food[fid]
            x = min(C.WORLD_W, max(0.0, x))
            y = min(C.WORLD_H, max(0.0, y))
            if abs(x - f.x) > 0.01 or abs(y - f.y) > 0.01:
                self.grid.move(f, x, y)
                f.moved_tick = self.tick

    def _eat_food(self, p: Player) -> None:
        r = p.radius
        eaten = []
        for fid in self.grid.query_rect(p.x - r, p.y - r, p.x + r, p.y + r):
            f = self.food[fid]
            if math.hypot(f.x - p.x, f.y - p.y) < r and f.edible_by(p.id, self.tick):
                eaten.append(fid)
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
                if b is a or b.id in gone or not can_eat(a.mass, b.mass) or self.shielded(b):
                    continue
                if overlaps_to_eat(a.x, a.y, a.radius, b.x, b.y, b.radius):
                    a.mass += b.mass * C.EAT_EFFICIENCY
                    gone.add(b.id)
                    deaths.append(Death(b.id, a.name, b.mass, self.best_level[b.id]))
        for pid in gone:
            self.remove_player(pid)
        return deaths

    # ---------- snapshots ----------
    def leaderboard(self) -> list[Player]:
        return sorted(self.players.values(), key=lambda p: p.mass, reverse=True)

    def snapshot_for(self, pid: int, view_w: float, view_h: float, known_food: dict[int, int],
                     board: list[Player] | None = None) -> dict:
        """State visible to one player. `known_food` (food id -> tick last sent) is updated in place,
        so only new/moved food is sent and the client is told which ids to forget. When `board`
        (players sorted by mass) is given, the top of it and this player's rank are included."""
        me = self.players[pid]
        zoom = zoom_for(me.mass)
        hw = view_w / 2 / zoom + C.VIEW_MARGIN
        hh = view_h / 2 / zoom + C.VIEW_MARGIN
        x0, y0, x1, y1 = me.x - hw, me.y - hh, me.x + hw, me.y + hh

        players = [
            [p.id, round(p.x, 1), round(p.y, 1), round(p.radius, 1), level_index(p.mass), p.name,
             int(p.is_bot), int(p.boosting), int(self.shielded(p))]
            for p in self.players.values()
            if x0 - p.radius < p.x < x1 + p.radius and y0 - p.radius < p.y < y1 + p.radius
        ]

        visible = set(self.grid.query_rect(x0, y0, x1, y1))
        added = []
        for fid in visible:
            f = self.food[fid]
            if known_food.get(fid, -1) < f.moved_tick:
                added.append([fid, round(f.x), round(f.y), f.color, round(f.radius, 1)])
            known_food[fid] = self.tick
        removed = [fid for fid in known_food if fid not in visible]
        for fid in removed:
            del known_food[fid]

        snap = {
            "t": "s",
            "tk": self.tick,
            "me": {"id": pid, "x": round(me.x, 1), "y": round(me.y, 1), "m": round(me.mass, 1),
                   "lvl": level_index(me.mass), "b": int(me.boosting),
                   "rk": round(math.log10(real_mass_kg(me.mass)), 3)},
            "z": round(zoom, 4),
            "p": players,
            "f": added,
            "fr": removed,
        }
        if board is not None:
            snap["lb"] = [[p.id, p.name, round(p.mass), level_index(p.mass), int(p.is_bot)]
                          for p in board[:C.LEADERBOARD_SIZE]]
            snap["rank"] = next(i for i, p in enumerate(board, 1) if p.id == pid)
        return snap
