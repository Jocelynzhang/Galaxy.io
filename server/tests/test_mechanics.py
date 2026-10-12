import math

import pytest

from server.game import config as C
from server.game.entities import Food
from server.game.levels import LEVELS, level_index
from server.game.npc import NpcManager
from server.game.world import World

DT = 1.0 / C.TICK_HZ


def empty_world() -> World:
    w = World(seed=1)
    for fid in list(w.food):
        w._remove_food(fid)
    return w


def freeze_food_spawning(monkeypatch):
    monkeypatch.setattr(C, "FOOD_SPAWN_PER_TICK", 0)


def total_mass(w: World) -> float:
    return sum(p.mass + p.boost_debt for p in w.players.values()) + sum(f.mass for f in w.food.values())


def test_boost_conserves_mass_and_ejects_food_behind(monkeypatch):
    freeze_food_spawning(monkeypatch)
    w = empty_world()
    p = w.add_player("a", mass=200)
    p.x = p.y = 2000
    w.set_input(p.id, angle=0.0, throttle=1.0, boost=True)    # heading +x
    before = total_mass(w)
    for _ in range(30):
        w.step(DT)
    assert p.mass < 200
    assert total_mass(w) == pytest.approx(before)
    assert w.food, "boosting should have emitted pellets"
    assert all(f.owner == p.id and f.x < p.x for f in w.food.values()), "pellets fly out the back"


def test_boost_is_faster():
    w = empty_world()
    a, b = w.add_player("a", mass=100), w.add_player("b", mass=100)
    a.x = b.x = 500
    a.y, b.y = 1000, 3000
    w.set_input(a.id, 0.0, 1.0, False)
    w.set_input(b.id, 0.0, 1.0, True)
    for _ in range(30):
        w.step(DT)
    assert (b.x - 500) > 1.6 * (a.x - 500)


def test_dust_cannot_boost(monkeypatch):
    freeze_food_spawning(monkeypatch)
    w = empty_world()
    p = w.add_player("dust")
    w.set_input(p.id, 0.0, 1.0, True)
    for _ in range(30):
        w.step(DT)
    assert p.mass == C.START_MASS and not w.food


def test_own_exhaust_is_not_edible_right_away_but_others_can_eat_it_soon():
    f = Food(id=1, x=0, y=0, color=0, owner=7, edible_tick=10, owner_edible_tick=40)
    assert not f.edible_by(7, 20) and f.edible_by(7, 40)
    assert not f.edible_by(3, 5) and f.edible_by(3, 10)
    assert Food(id=2, x=0, y=0, color=0).edible_by(7, 0)


def test_gravity_pulls_food_but_never_players(monkeypatch):
    freeze_food_spawning(monkeypatch)
    w = empty_world()
    big = w.add_player("star", mass=LEVELS[level_index(1000)].min_mass + 50)
    small = w.add_player("rock", mass=30)
    big.x = big.y = 2000
    start = 2000 + big.radius * 1.5
    small.x, small.y = start, 2000
    f = Food(id=999, x=2000, y=start, color=0)
    w._add_food(f)
    for _ in range(10):
        w.step(DT)
    assert f.y < start, "food should drift toward the big object"
    assert small.x == start, "players are not pulled"


def test_small_objects_have_no_gravity(monkeypatch):
    freeze_food_spawning(monkeypatch)
    w = empty_world()
    p = w.add_player("dust")
    f = Food(id=999, x=p.x + p.radius * 1.5, y=p.y, color=0)
    w._add_food(f)
    w.step(DT)
    assert f.x == p.x + p.radius * 1.5


def test_big_objects_decay_small_ones_do_not(monkeypatch):
    freeze_food_spawning(monkeypatch)
    w = empty_world()
    small = w.add_player("small", mass=100)
    big = w.add_player("big", mass=LEVELS[-1].min_mass * 1.5)
    for _ in range(30):
        w.step(DT)
    assert small.mass == 100
    assert big.mass < LEVELS[-1].min_mass * 1.5


def test_npcs_fill_world_when_empty():
    w = World(seed=3)
    NpcManager(w, seed=3)
    assert len(w.players) == C.TARGET_PLAYERS
    assert all(p.is_bot for p in w.players.values())


def test_humans_joining_do_not_remove_npcs_and_eaten_npcs_are_not_replaced_while_over_target():
    w = World(seed=4)
    npcs = NpcManager(w, seed=4)
    humans = [w.add_player(f"kid{i}") for i in range(3)]
    assert len(w.players) == C.TARGET_PLAYERS + 3          # nobody was kicked out
    bots = [p for p in w.players.values() if p.is_bot]
    for b in bots[:2]:                                     # two NPCs get eaten
        w.remove_player(b.id)
    for _ in range(int(C.NPC_RESPAWN_S * 3 / DT)):
        npcs.update(DT)
    assert len(w.players) == C.TARGET_PLAYERS + 1          # still above target: no respawn
    for b in [p for p in w.players.values() if p.is_bot][:3]:
        w.remove_player(b.id)                              # now below target
    for _ in range(int(C.NPC_RESPAWN_S * 3 / DT)):
        npcs.update(DT)
    assert len(w.players) == C.TARGET_PLAYERS              # refilled back to the target
    assert all(h.id in w.players for h in humans)


def test_npcs_never_spawn_when_humans_alone_fill_the_world():
    w = World(seed=5)
    npcs = NpcManager(w, seed=5)
    for p in list(w.players.values()):
        w.remove_player(p.id)
    for i in range(C.TARGET_PLAYERS):
        w.add_player(f"kid{i}")
    for _ in range(int(C.NPC_RESPAWN_S * 3 / DT)):
        npcs.update(DT)
    assert not any(p.is_bot for p in w.players.values())


def test_npcs_respect_their_level_cap():
    w = World(seed=6)
    npcs = NpcManager(w, seed=6)
    pid, brain = next(iter(npcs.brains.items()))
    me = w.players[pid]
    me.mass = LEVELS[brain.max_level + 1].min_mass * 1.2 if brain.max_level + 1 < len(LEVELS) else me.mass
    me.level = level_index(me.mass)
    start = me.mass
    for _ in range(60):
        npcs.update(DT)
    assert me.mass < start or brain.max_level + 1 >= len(LEVELS)


def test_npc_ai_flees_bigger_and_chases_smaller():
    from server.game.npc import Brain, think
    import random
    w = empty_world()
    me = w.add_player("npc", is_bot=True, mass=100)
    threat = w.add_player("big", mass=1000)
    me.x, me.y = 2000, 2000
    threat.x, threat.y = 2000 + me.radius + threat.radius + 20, 2000   # right next to us, on the right
    think(w, me, Brain(hunter=False, rng=random.Random(0)), 0.0)
    assert math.cos(me.angle) < 0, "should run left, away from the threat"

    w.remove_player(threat.id)
    prey = w.add_player("small", mass=20)
    prey.x, prey.y = 2000, 2000 + me.radius + 40                       # just below us
    prey.shield_until = 0
    think(w, me, Brain(hunter=True, rng=random.Random(0)), 0.0)
    assert math.sin(me.angle) > 0, "should head down toward the prey"


def test_cornered_npc_slides_along_the_wall_and_boosts():
    from server.game.npc import Brain, think
    import random
    w = empty_world()
    me = w.add_player("npc", is_bot=True, mass=100)
    threat = w.add_player("big", mass=200)
    me.x, me.y = me.radius + 30, 2000                                    # back against the left wall
    threat.x, threat.y = me.x + me.radius + threat.radius + 60, 2000      # closing in from the right
    boosts = 0
    for seed in range(10):
        think(w, me, Brain(hunter=False, rng=random.Random(seed)), 0.0)
        assert math.cos(me.angle) < 0.5, "must not run back toward the threat"
        assert abs(math.sin(me.angle)) > 0.7, "should escape up or down along the wall"
        boosts += me.boost
    assert boosts >= 7          # boosting is a dice roll per decision (NPC_FLEE_BOOST)


def test_simulation_smoke():
    from server.sim import run
    res = run(minutes=0.5, pilots=1, seed=0)
    assert res["players_end"] >= C.TARGET_PLAYERS
    assert res["tick_ms_p99"] < 1000 / C.TICK_HZ


def test_npcs_ignore_shielded_newcomers():
    from server.game.npc import Brain, think
    import random
    w = empty_world()
    me = w.add_player("npc", is_bot=True, mass=100)
    me.x, me.y = 2000, 2000
    kid = w.add_player("kid")
    kid.x, kid.y = 2000, 2000 + me.radius + 40
    for seed in range(5):
        think(w, me, Brain(hunter=True, rng=random.Random(seed)), 0.0)
        assert not (math.sin(me.angle) > 0.9), "should not beeline at a shielded kid"


def test_level_hysteresis_up_immediately_down_only_after_margin():
    from server.game.levels import settle_level
    t = LEVELS[4].min_mass                     # gas giant threshold
    assert settle_level(3, t) == 4             # level up right at the threshold
    assert settle_level(4, t * 0.99) == 4      # a little below: stay
    assert settle_level(4, t * (1 - C.LEVEL_DOWN_MARGIN) * 0.999) == 3
    assert settle_level(0, LEVELS[7].min_mass) == 7   # big meals can jump several levels
    assert settle_level(9, 10) == 0


def test_boosting_at_a_threshold_does_not_flicker(monkeypatch):
    freeze_food_spawning(monkeypatch)
    w = empty_world()
    p = w.add_player("a", mass=LEVELS[5].min_mass + 2)
    p.x = p.y = 2000
    w.set_input(p.id, 0.0, 1.0, True)
    levels = []
    for _ in range(C.TICK_HZ * 2):            # 2 s of boosting, eating its own pellets is blocked
        w.step(DT)
        levels.append(p.level)
    changes = sum(1 for a, b in zip(levels, levels[1:]) if a != b)
    assert changes <= 1 and levels[-1] == 5


def test_hunter_goes_into_the_corner_after_hiding_prey():
    # wall avoidance used to turn the hunter away, and both froze there for good
    from server.game.npc import Brain, think
    import random
    w = empty_world()
    prey = w.add_player("small", is_bot=True, mass=25)
    prey.x, prey.y = C.WORLD_W - prey.radius, prey.radius
    prey.shield_until = 0
    me = w.add_player("npc", is_bot=True, mass=34)
    me.x, me.y = prey.x - 150, prey.y + 160
    for seed in range(5):
        think(w, me, Brain(hunter=True, rng=random.Random(seed)), 0.0)
        assert math.cos(me.angle) > 0.3 and math.sin(me.angle) < -0.3, "should head up-right into the corner"


def test_npc_reset_refills_the_world():
    w = World(seed=2)
    npcs = NpcManager(w, seed=2)
    w.reset()
    npcs.reset()
    assert len(w.players) == C.TARGET_PLAYERS == len(npcs.brains)
    assert set(npcs.brains) == set(w.players)
