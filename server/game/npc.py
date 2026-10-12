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
from .physics import can_eat, speed_for
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
        self.reset()

    def reset(self) -> None:
        """Fill the world with fresh NPCs (at startup and after World.reset)."""
        self.brains.clear()
        self.spawn_at = None
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
    sense = r * C.NPC_SENSE[0] + C.NPC_SENSE[1]
    flee_x = flee_y = 0.0
    alarm = 0.0                      # how urgent the worst threat is (0 = none, 1 = touching)
    threats: list[Player] = []
    prey: Player | None = None
    prey_d = math.inf
    for o in world.players.values():
        if o is me:
            continue
        d = math.hypot(o.x - me.x, o.y - me.y)
        if d > sense:
            continue
        if can_eat(o.mass, me.mass):
            threats.append(o)
            # danger grows as the gap closes; fast (or boosting) threats count from further away
            gap = d - o.radius
            reach = max(sense * 0.6, _top_speed(o) * C.NPC_FLEE_WARN_S)
            danger = max(0.0, 1.0 - gap / reach)
            if danger > 0:
                flee_x += (me.x - o.x) / max(d, 1) * danger
                flee_y += (me.y - o.y) / max(d, 1) * danger
                alarm = max(alarm, danger)
        elif can_eat(me.mass, o.mass) and d < prey_d and not world.shielded(o):
            prey, prey_d = o, d

    boost = False
    noise = C.NPC_AIM_NOISE[1]
    if alarm > C.NPC_FLEE_ALARM:
        angle, worst_gap, closest = _flee_heading(me, threats)
        noise = C.NPC_AIM_NOISE[0]
        # boost once the nearest threat could reach us within NPC_FLEE_BOOST_S
        boost = worst_gap < _top_speed(closest) * C.NPC_FLEE_BOOST_S and rng.random() < C.NPC_FLEE_BOOST
        brain.next_think = now + rng.uniform(*C.NPC_FLEE_THINK_S)   # stay alert while in danger
        world.set_input(me.id, angle + rng.uniform(-noise, noise), 1.0, boost)
        return
    if prey is not None and _wants_chase(brain, prey, prey_d, r, now):
        # no wall avoidance while chasing: it kept hunters from ever reaching prey that hid in a
        # corner, and the two froze there in a standoff
        angle = _intercept(me, prey, prey_d)
        noise = C.NPC_AIM_NOISE[0]
        boost = (prey_d < r * 4 + 250 and me.mass > prey.mass * C.NPC_BOOST_RATIO
                 and rng.random() < C.NPC_CHASE_BOOST[0 if brain.hunter else 1])
    else:
        brain.chase_id = None
        angle = _food_heading(world, me, sense)
        if angle is None:
            brain.wander += rng.uniform(-0.6, 0.6)
            angle = brain.wander
        if flee_x or flee_y:
            # a threat is around but not close yet: graze away from it rather than toward it
            angle = math.atan2(math.sin(angle) + flee_y * 4, math.cos(angle) + flee_x * 4)
        # the odd playful dash shows players what boosting looks like
        boost = me.mass > C.BOOST_MIN_MASS * 3 and rng.random() < 0.03
        angle = _avoid_walls(me, angle, r)

    angle += rng.uniform(-noise, noise)  # imperfect steering keeps NPCs beatable
    world.set_input(me.id, angle, 1.0, boost)


def _top_speed(o: Player) -> float:
    return speed_for(o.mass) * (C.BOOST_MULT if o.mass >= C.BOOST_MIN_MASS else 1.0)


def _flee_heading(me: Player, threats: list[Player]) -> tuple[float, float, Player]:
    """Try NPC_FLEE_DIRS headings; keep the one that leaves the biggest gap to the nearest threat
    after NPC_FLEE_LOOKAHEAD s, assuming every threat chases us at its top speed. Walls are handled
    by clamping our predicted position, so heading into a wall or corner scores badly.
    Returns (heading, current gap to the nearest threat, that threat)."""
    t = C.NPC_FLEE_LOOKAHEAD
    step = _top_speed(me) * t        # we boost when it gets tight, so plan with boost speed
    r = me.radius
    closest = min(threats, key=lambda o: math.hypot(o.x - me.x, o.y - me.y) - o.radius)
    now_gap = math.hypot(closest.x - me.x, closest.y - me.y) - closest.radius
    best_a, best_score = 0.0, -math.inf
    for k in range(C.NPC_FLEE_DIRS):
        a = 2 * math.pi * k / C.NPC_FLEE_DIRS
        px = min(C.WORLD_W - r, max(r, me.x + math.cos(a) * step))
        py = min(C.WORLD_H - r, max(r, me.y + math.sin(a) * step))
        score = math.inf
        for o in threats:
            # not capped at 0: "caught later" must still beat "caught sooner", or every heading
            # ties and the wall-room term sends us back toward the chaser
            d = math.hypot(px - o.x, py - o.y)
            score = min(score, d - _top_speed(o) * t - o.radius)
        # keep a little room from walls so the next escape still has options
        wall = min(px, py, C.WORLD_W - px, C.WORLD_H - py) - r
        score -= max(0.0, C.NPC_FLEE_WALL_ROOM - wall) * 0.5
        if score > best_score:
            best_a, best_score = a, score
    return best_a, now_gap, closest


def _wants_chase(brain: Brain, prey: Player, d: float, r: float, now: float) -> bool:
    if now < brain.give_up_until:
        return False
    if brain.chase_id != prey.id:
        # hunters chase anything they sense; cautious NPCs only snack on very close prey
        if not brain.hunter and d > r * C.NPC_SNACK_DIST[0] + C.NPC_SNACK_DIST[1]:
            return False
        brain.chase_id = prey.id
        brain.chase_until = now + C.NPC_CHASE_S[0 if brain.hunter else 1]
    if now > brain.chase_until:
        brain.chase_id = None
        brain.give_up_until = now + C.NPC_GIVE_UP_S   # take a break so kids can escape
        return False
    return True


def _intercept(me: Player, prey: Player, d: float) -> float:
    """Heading toward where the prey will be when we get there (capped look-ahead)."""
    t = min(C.NPC_LEAD_S, d / max(1.0, speed_for(me.mass)))
    return math.atan2(prey.y + prey.vy * t - me.y, prey.x + prey.vx * t - me.x)


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
    margin = r + C.NPC_WALL_MARGIN
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
