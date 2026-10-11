"""The astrophysical ladder, loaded from client/data/ladder.json (shared with the browser)."""
import json
import math
from dataclasses import dataclass
from pathlib import Path

from . import config as C

LADDER_PATH = Path(__file__).resolve().parents[2] / "client" / "data" / "ladder.json"


@dataclass(frozen=True)
class Level:
    key: str
    name: str
    min_mass: float                  # game mass at which this level starts
    real_kg: tuple[float, float]     # real-mass range shown in the HUD


def _load() -> tuple[list[Level], float]:
    data = json.loads(LADDER_PATH.read_text())
    levels = [Level(d["key"], d["name"], float(d["min_mass"]), tuple(d["real_kg"])) for d in data["levels"]]
    return levels, float(data["top_mass"])


LEVELS, TOP_MASS = _load()


def level_index(mass: float) -> int:
    idx = 0
    for i, lvl in enumerate(LEVELS):
        if mass >= lvl.min_mass:
            idx = i
    return idx


def level_span(i: int) -> tuple[float, float]:
    """Game-mass range [start, end) of level i. Dust starts at START_MASS (nobody is smaller)
    and the last level ends at TOP_MASS."""
    start = C.START_MASS if i == 0 else LEVELS[i].min_mass
    end = LEVELS[i + 1].min_mass if i + 1 < len(LEVELS) else TOP_MASS
    return start, end


def real_mass_kg(mass: float) -> float:
    """Map game mass to a real mass in kg, log-linearly within the current level's real range."""
    i = level_index(mass)
    lo, hi = level_span(i)
    t = (math.log(max(mass, lo)) - math.log(lo)) / (math.log(hi) - math.log(lo))
    k_lo, k_hi = LEVELS[i].real_kg
    # past the top of the ladder keep extrapolating, so galaxies can keep "growing"
    return 10 ** (math.log10(k_lo) + max(0.0, t) * (math.log10(k_hi) - math.log10(k_lo)))
