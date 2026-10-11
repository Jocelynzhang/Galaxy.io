"""NPC population manager and simple steering brains.

Population rule (from the product owner): the world aims for TARGET_PLAYERS objects.
NPCs fill empty slots; when humans join, existing NPCs are NOT removed, but eaten NPCs are
only replaced while humans + NPCs < TARGET_PLAYERS.
"""
import math
import random
from dataclasses import dataclass, field

from . import config as C
from .entities import Player
from .levels import LEVELS
from .physics import can_eat
from .world import World

ASTRONOMERS = [
    "Hubble", "Leavitt", "Kepler", "Rubin", "Galileo", "Herschel", "Cannon", "Sagan",
    "Payne", "Copernicus", "Tycho", "Halley", "Burnell", "Chandra", "Messier", "Zwicky",
    "Hawking", "Ghez", "Huygens", "Lemaitre",
]


@dataclass
class Brain:
    hunter: bool
    rng: random.Random
    next_think: float = 0.0
    wander: float = field(default=0.0)
    chase_id: int | None = None
    chase_until: float = 0.0
    give_up_until: float = 0.0
    max_level: int = len(LEVELS) - 1
    slot: int = 0


class NpcManager:
    def __init__(self, world: World, seed: int | None = None):
        self.world = world
        self.rng = random.Random(seed)
        self.brains: dict[int, Brain] = {}
        self.time = 0.0
        self.spawn_at: float | None = None
        # fill the world immediately at startup
        while self._total() < C.TARGET_PLAYERS:
            self._spawn()

    def _humans(self) -> int:
        return sum(1 for p in self.world.players.values() if not p.is_bot)

    def _total(self) -> int:
        return len(self.world.players)

    def _spawn(self) -> None:
        used = {p.name for p in self.world.players.values() if p.is_bot}
        free = [n for n in ASTRONOMERS if n not in used] or ASTRONOMERS
        taken = {b.slot for b in self.brains.values()}
        slot = next((i for i in range(len(C.NPC_SLOTS)) if i not in taken), self.rng.randrange(len(C.NPC_SLOTS)))
        cap, hunter = C.NPC_SLOTS[slot]
        lo, hi = C.NPC_SPAWN_MASS
        hi = min(hi, LEVELS[min(cap + 1, len(LEVELS) - 1)].min_mass * 0.9)
        mass = math.exp(self.rng.uniform(math.log(lo), math.log(max(lo, hi))))
        p = self.world.add_player(self.rng.choice(free), is_bot=True, mass=mass)
        self.brains[p.id] = Brain(hunter=hunter, rng=random.Random(self.rng.random()),
                                  wander=self.rng.uniform(-math.pi, math.pi), max_level=cap, slot=slot)

    def update(self, dt: float) -> None:
        self.time += dt
        # forget brains of NPCs that were eaten
        for pid in [pid for pid in self.brains if pid not in self.world.players]:
            del self.brains[pid]
        if self._total() < C.TARGET_PLAYERS and self._humans() < C.TARGET_PLAYERS:
            if self.spawn_at is None:
                self.spawn_at = self.time + C.NPC_RESPAWN_S
            elif self.time >= self.spawn_at:
                self._spawn()
                self.spawn_at = None
        else:
            self.spawn_at = None
        for pid, brain in self.brains.items():
            me = self.world.players[pid]
            if me.level > brain.max_level:
                me.mass -= me.mass * C.NPC_OVERCAP_DECAY * dt
            if self.time >= brain.next_think:
                brain.next_think = self.time + brain.rng.uniform(*C.NPC_THINK_S)
                think(self.world, self.world.players[pid], brain, self.time)


def think(world: World, me: Player, brain: Brain, now: float) -> None:
    """Pick a heading: flee threats, chase prey, otherwise graze toward food."""
    rng = brain.rng
    r = me.radius
    sense = r * 4 + 450
    flee_x = flee_y = 0.0
    prey: Player | None = None
    prey_d = math.inf
    for o in world.players.values():
        if o is me:
            continue
        d = math.hypot(o.x - me.x, o.y - me.y)
        if d > sense:
            continue
        if can_eat(o.mass, me.mass):
            # closer and bigger threats push harder
            danger = max(0.0, 1.0 - (d - o.radius - r) / (sense * 0.6))
            if danger > 0:
                flee_x += (me.x - o.x) / max(d, 1) * danger
                flee_y += (me.y - o.y) / max(d, 1) * danger
        elif can_eat(me.mass, o.mass) and d < prey_d and not world.shielded(o):
            prey, prey_d = o, d

    boost = False
    if math.hypot(flee_x, flee_y) > 0.25:
        angle = math.atan2(flee_y, flee_x)
        boost = math.hypot(flee_x, flee_y) > 0.45 and rng.random() < 0.7
    elif prey is not None and _wants_chase(brain, prey, prey_d, r, now):
        angle = math.atan2(prey.y - me.y, prey.x - me.x)
        boost = prey_d < r * 3 + 150 and me.mass > prey.mass * 1.6 and rng.random() < (0.6 if brain.hunter else 0.25)
    else:
        brain.chase_id = None
        angle = _food_heading(world, me, sense)
        if angle is None:
            brain.wander += rng.uniform(-0.6, 0.6)
            angle = brain.wander
        # the odd playful dash shows players what boosting looks like
        boost = me.mass > C.BOOST_MIN_MASS * 3 and rng.random() < 0.03

    angle = _avoid_walls(me, angle, r)
    angle += rng.uniform(-0.25, 0.25)  # imperfect steering keeps NPCs beatable
    world.set_input(me.id, angle, 1.0, boost)


def _wants_chase(brain: Brain, prey: Player, d: float, r: float, now: float) -> bool:
    if now < brain.give_up_until:
        return False
    if brain.chase_id != prey.id:
        # hunters chase anything they sense; cautious NPCs only snack on very close prey
        if not brain.hunter and d > r * 2 + 80:
            return False
        brain.chase_id = prey.id
        brain.chase_until = now + (5.0 if brain.hunter else 2.0)
    if now > brain.chase_until:
        brain.chase_id = None
        brain.give_up_until = now + 3.0   # take a break so kids can escape
        return False
    return True


def _food_heading(world: World, me: Player, sense: float) -> float | None:
    sx = sy = 0.0
    reach = min(sense, 700)
    for fid in world.grid.query_rect(me.x - reach, me.y - reach, me.x + reach, me.y + reach):
        f = world.food[fid]
        dx, dy = f.x - me.x, f.y - me.y
        d2 = dx * dx + dy * dy
        if d2 < 1:
            continue
        w = f.mass / d2          # nearby and big pellets attract most
        sx += dx * w
        sy += dy * w
    if sx == 0 and sy == 0:
        return None
    return math.atan2(sy, sx)


def _avoid_walls(me: Player, angle: float, r: float) -> float:
    margin = r + 150
    vx, vy = math.cos(angle), math.sin(angle)
    if me.x < margin:
        vx += 1.5
    elif me.x > C.WORLD_W - margin:
        vx -= 1.5
    if me.y < margin:
        vy += 1.5
    elif me.y > C.WORLD_H - margin:
        vy -= 1.5
    return math.atan2(vy, vx)
