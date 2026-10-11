"""Pure game-rule functions (no world state), easy to unit test."""
import math

from . import config as C
from .entities import radius_for


def speed_for(mass: float) -> float:
    return max(C.SPEED_MIN, C.SPEED_V0 * mass ** -C.SPEED_EXP)


def zoom_for(mass: float) -> float:
    r = radius_for(mass)
    r0 = radius_for(C.START_MASS)
    return C.SCREEN_R0 * (r / r0) ** C.ZOOM_EXP / r


def can_eat(m_a: float, m_b: float) -> bool:
    return m_a >= C.EAT_RATIO * m_b


def overlaps_to_eat(ax, ay, ar, bx, by, br) -> bool:
    return math.hypot(ax - bx, ay - by) < ar - C.EAT_OVERLAP * br
