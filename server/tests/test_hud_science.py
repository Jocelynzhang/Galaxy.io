import json
import math

import pytest

from server.game import config as C
from server.game.levels import LADDER_PATH, LEVELS, TOP_MASS, level_index, level_span, real_mass_kg
from server.game.names import clean_name, is_inappropriate
from server.game.world import World

SUN = 1.989e30
EARTH = 5.97e24
JUPITER = 1.898e27


def test_ladder_file_is_complete_for_the_client():
    data = json.loads(LADDER_PATH.read_text())
    keys = [d["key"] for d in data["levels"]]
    assert keys == ["dust", "asteroid", "dwarf_planet", "terrestrial", "gas_giant", "brown_dwarf",
                    "main_sequence", "giant", "neutron_star", "black_hole", "quasar", "galaxy"]
    for d in data["levels"]:
        assert d["name"] and d["facts"] and d["color"].startswith("#")
        lo, hi = d["real_kg"]
        assert 0 < lo < hi
    assert TOP_MASS > LEVELS[-1].min_mass


@pytest.mark.parametrize("i", range(12))
def test_real_mass_rises_within_each_level(i):
    lo, hi = level_span(i)
    masses = [lo + (hi - lo) * f for f in (0.0, 0.25, 0.5, 0.75, 0.999)]
    kgs = [real_mass_kg(m) for m in masses]
    assert kgs == sorted(kgs)
    assert kgs[0] == pytest.approx(LEVELS[i].real_kg[0], rel=1e-6)
    assert kgs[-1] == pytest.approx(LEVELS[i].real_kg[1], rel=0.05)


def test_real_mass_landmarks_are_scientifically_sensible():
    assert real_mass_kg(C.START_MASS) == pytest.approx(1e-15)     # you start as a real speck of dust
    assert 1e23 <= real_mass_kg(LEVELS[3].min_mass + 1) < 1e25     # terrestrial: Mars..Earth-ish
    assert 13 * JUPITER * 0.9 < real_mass_kg(LEVELS[5].min_mass) < 80 * JUPITER   # brown dwarf
    assert real_mass_kg(LEVELS[6].min_mass) == pytest.approx(0.08 * SUN, rel=0.01)  # smallest star
    assert 1.3 * SUN < real_mass_kg(LEVELS[8].min_mass + 1) < 2.4 * SUN            # neutron star
    assert real_mass_kg(LEVELS[11].min_mass) >= 1e10 * SUN                          # galaxy


def test_supernova_makes_you_lighter_in_real_mass():
    """Honest science: the neutron star left after a supernova is lighter than the giant before it."""
    giant_top = real_mass_kg(LEVELS[8].min_mass - 1)
    neutron = real_mass_kg(LEVELS[8].min_mass)
    assert neutron < giant_top


def test_galaxies_keep_growing_past_the_top():
    assert real_mass_kg(TOP_MASS * 2) > real_mass_kg(TOP_MASS)


def test_snapshot_reports_real_mass_and_leaderboard():
    w = World(seed=1)
    a, b, c = (w.add_player(n) for n in "abc")
    a.mass, b.mass, c.mass = 50, 500, 5
    for p in (a, b, c):
        p.level = level_index(p.mass)
    board = w.leaderboard()
    snap = w.snapshot_for(a.id, 1280, 720, {}, board)
    assert snap["rank"] == 2
    assert [row[1] for row in snap["lb"]] == ["b", "a", "c"]
    assert snap["lb"][0][3] == level_index(500)
    assert snap["me"]["rk"] == pytest.approx(math.log10(real_mass_kg(50)), abs=1e-3)
    assert "lb" not in w.snapshot_for(a.id, 1280, 720, {})


def test_leaderboard_is_capped():
    w = World(seed=1)
    players = [w.add_player(f"p{i}") for i in range(C.LEADERBOARD_SIZE + 5)]
    snap = w.snapshot_for(players[-1].id, 1280, 720, {}, w.leaderboard())
    assert len(snap["lb"]) == C.LEADERBOARD_SIZE
    assert 1 <= snap["rank"] <= len(players)


@pytest.mark.parametrize("name", ["fuck", "FUCKER", "f.u.c.k", "sh1t head", "a s s", "Big Dick", "b1tch",
                                  "ＦＵＣＫ"])
def test_bad_names_are_replaced(name):
    assert is_inappropriate(name)
    assert clean_name(name) == C.DEFAULT_NAME


@pytest.mark.parametrize("name", ["Glass", "Class 3B", "Peacock", "Grape", "Dickens", "Hancock", "Scunthorpe",
                                  "Analysis", "Cassie", "Skill", "Titan", "Swanky", "星尘"])
def test_innocent_names_pass(name):
    assert not is_inappropriate(name)
    assert clean_name(name) == name
