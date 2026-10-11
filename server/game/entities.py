from dataclasses import dataclass

from . import config as C


def radius_for(mass: float) -> float:
    return C.RADIUS_K * mass ** 0.5


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
