from dataclasses import dataclass

from . import config as C


def radius_for(mass: float) -> float:
    return C.RADIUS_K * mass ** 0.5


def food_radius_for(mass: float) -> float:
    return C.FOOD_RADIUS * (mass / C.FOOD_MASS) ** 0.5


@dataclass
class Player:
    id: int
    name: str
    x: float
    y: float
    mass: float = C.START_MASS
    is_bot: bool = False
    vx: float = 0.0
    vy: float = 0.0
    # latest input: heading in radians, throttle 0..1, boost held
    angle: float = 0.0
    throttle: float = 0.0
    boost: bool = False
    boosting: bool = False       # actually boosting this tick (input held and allowed)
    boost_debt: float = 0.0      # shed mass not yet emitted as a pellet

    @property
    def radius(self) -> float:
        return radius_for(self.mass)


@dataclass
class Food:
    id: int
    x: float
    y: float
    color: int
    mass: float = C.FOOD_MASS
    # tick on which the position last changed; lets snapshots send only changes
    moved_tick: int = 0
    # ejected pellets fly and belong to their booster for a moment
    vx: float = 0.0
    vy: float = 0.0
    owner: int = 0               # 0 = natural food
    edible_tick: int = 0         # anyone else may eat it from this tick
    owner_edible_tick: int = 0   # the owner may eat it from this tick

    @property
    def radius(self) -> float:
        return food_radius_for(self.mass)

    def edible_by(self, pid: int, tick: int) -> bool:
        if not self.owner:
            return True
        return tick >= (self.owner_edible_tick if pid == self.owner else self.edible_tick)
