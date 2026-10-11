"""The astrophysical ladder. Game-mass thresholds are drafts; they get tuned in M2."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    key: str
    name: str
    min_mass: float   # game mass at which this level starts


LEVELS = [
    Level("dust", "Dust", 0),
    Level("asteroid", "Asteroid", 25),
    Level("dwarf_planet", "Dwarf planet", 60),
    Level("terrestrial", "Terrestrial planet", 130),
    Level("gas_giant", "Gas giant", 260),
    Level("brown_dwarf", "Brown dwarf", 500),
    Level("main_sequence", "Main-sequence star", 900),
    Level("giant", "Giant star", 1600),
    Level("neutron_star", "Neutron star", 2600),
    Level("black_hole", "Black hole", 3800),
    Level("quasar", "Quasar", 5500),
    Level("galaxy", "Galaxy", 8000),
]


def level_index(mass: float) -> int:
    idx = 0
    for i, lvl in enumerate(LEVELS):
        if mass >= lvl.min_mass:
            idx = i
    return idx
