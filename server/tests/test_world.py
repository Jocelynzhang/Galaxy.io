import math

import pytest

from server.game import config as C
from server.game.levels import LEVELS, level_index
from server.game.physics import can_eat, speed_for, zoom_for
from server.game.world import World
from server.game.names import clean_name

DT = 1.0 / C.TICK_HZ


def empty_world() -> World:
    w = World(seed=1)
    for fid in list(w.food):
        w._remove_food(fid)
    return w


def test_bigger_is_slower_but_never_stuck():
    assert speed_for(10) > speed_for(100) > speed_for(1000)
    assert speed_for(1e9) == C.SPEED_MIN


def test_camera_zooms_out_as_you_grow():
    assert zoom_for(10) > zoom_for(100) > zoom_for(10000)


def test_eat_ratio():
    assert can_eat(125, 100)
    assert not can_eat(120, 100)


def test_player_moves_toward_input_angle_and_stays_in_world():
    w = empty_world()
    p = w.add_player("a")
    p.x, p.y = 100, 100
    w.set_input(p.id, angle=math.pi, throttle=1.0, boost=False)   # head left, into the wall
    for _ in range(60):
        w.step(DT)
    assert p.x == pytest.approx(p.radius)
    assert p.y == pytest.approx(100, abs=1e-6)


def test_throttle_is_clamped():
    w = empty_world()
    p = w.add_player("a")
    w.set_input(p.id, 0.0, 50.0, False)
    assert p.throttle == 1.0


def test_eating_food_adds_mass_and_removes_it():
    w = empty_world()
    p = w.add_player("a")
    w.food.clear()
    w.grid.cells.clear()
    from server.game.entities import Food
    f = Food(id=999, x=p.x + 1, y=p.y, color=0)
    w.food[f.id] = f
    w.grid.add(f)
    before = p.mass
    w._eat_food(p)
    assert p.mass == before + C.FOOD_MASS
    assert 999 not in w.food


def test_food_is_replenished():
    w = empty_world()
    for _ in range(5):
        w.step(DT)
    assert len(w.food) == 5 * C.FOOD_SPAWN_PER_TICK


def test_big_player_eats_small_one():
    w = empty_world()
    big, small = w.add_player("big"), w.add_player("small")
    big.mass, small.mass = 100, 20
    small.shield_until = 0          # spawn protection over
    big.x = big.y = small.x = small.y = 1000
    small.x += 5
    deaths = w._eat_players()
    assert [d.victim_id for d in deaths] == [small.id]
    assert deaths[0].killer_name == "big"
    assert big.mass == pytest.approx(100 + 20 * C.EAT_EFFICIENCY)
    assert small.id not in w.players


def test_similar_sizes_bounce_off_instead_of_eating():
    w = empty_world()
    a, b = w.add_player("a"), w.add_player("b")
    a.mass, b.mass = 100, 90
    a.x = a.y = b.x = b.y = 1000
    assert w._eat_players() == []
    assert len(w.players) == 2


def test_level_ladder_is_ordered_and_complete():
    assert [lvl.key for lvl in LEVELS][0] == "dust" and LEVELS[-1].key == "galaxy"
    assert len(LEVELS) == 12
    mins = [lvl.min_mass for lvl in LEVELS]
    assert mins == sorted(mins)
    assert level_index(C.START_MASS) == 0
    assert level_index(1e9) == len(LEVELS) - 1


def test_snapshot_sends_food_once_then_only_removals():
    w = World(seed=2)
    p = w.add_player("a")
    known: dict[int, int] = {}
    s1 = w.snapshot_for(p.id, 1280, 720, known)
    assert s1["f"], "first snapshot should contain nearby food"
    w.tick += 1
    s2 = w.snapshot_for(p.id, 1280, 720, known)
    assert s2["f"] == [] and s2["fr"] == []
    gone = s1["f"][0][0]
    w._remove_food(gone)
    s3 = w.snapshot_for(p.id, 1280, 720, known)
    assert s3["fr"] == [gone]


def test_snapshot_only_includes_players_in_view():
    w = empty_world()
    a, b = w.add_player("a"), w.add_player("b")
    a.x, a.y, b.x, b.y = 500, 500, 4000, 4000
    ids = [row[0] for row in w.snapshot_for(a.id, 1280, 720, {})["p"]]
    assert ids == [a.id]


@pytest.mark.parametrize("raw,expected", [
    ("  Tq  ", "Tq"),
    ("a\x00b\nc", "abc"),
    ("x" * 40, "x" * C.NAME_MAX_LEN),
    ("", C.DEFAULT_NAME),
    (None, C.DEFAULT_NAME),
    ("星尘 dust", "星尘 dust"),
])
def test_clean_name(raw, expected):
    assert clean_name(raw) == expected


def test_new_players_are_shielded_then_edible():
    w = empty_world()
    big = w.add_player("big", mass=500)
    kid = w.add_player("kid")
    kid.x, kid.y = big.x, big.y
    assert w._eat_players() == [], "spawn shield protects newcomers"
    w.tick = kid.shield_until
    assert [d.victim_id for d in w._eat_players()] == [kid.id]


def test_newcomers_spawn_away_from_threats():
    w = empty_world()
    for _ in range(4):
        w.add_player("big", mass=800)
    for _ in range(20):
        kid = w.add_player("kid")
        threats = [p for p in w.players.values() if p.mass >= C.EAT_RATIO * kid.mass]
        gap = min(math.hypot(kid.x - p.x, kid.y - p.y) - p.radius for p in threats)
        assert gap > C.SPAWN_SAFE_DIST * 0.9
        w.remove_player(kid.id)


def test_spectator_snapshot_is_marked_and_follows_given_player():
    w = World(seed=1)
    leader = w.add_player("big", mass=900)
    snap = w.snapshot_for(leader.id, 1280, 720, {}, spectating=True)
    assert snap["spec"] == 1 and snap["me"]["id"] == leader.id
    assert "spec" not in w.snapshot_for(leader.id, 1280, 720, {})
