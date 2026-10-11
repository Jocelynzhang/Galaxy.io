"""Headless pacing simulation: `python -m server.sim [minutes] [pilots] [seed]`.

Runs the real World + NPCs faster than real time. "Pilots" stand in for skilled human players:
they start as dust, use a hunter brain, and respawn as dust when eaten. Prints how long pilots
took to first reach each level, plus tick cost, to tune the ladder toward a 10-15 min run.
"""
import random
import statistics
import sys
import time

from .game import config as C
from .game.levels import LEVELS
from .game.npc import Brain, NpcManager, think
from .game.world import World


def run(minutes: float = 15, pilots: int = 1, seed: int = 0) -> dict:
    world = World(seed=seed)
    npcs = NpcManager(world, seed=seed)
    rng = random.Random(seed)
    dt = 1 / C.TICK_HZ
    t = 0.0
    lives: list[dict] = []          # one entry per pilot life: level -> seconds since spawn
    pilot: dict[int, tuple[Brain, dict, float]] = {}

    def spawn_pilot():
        p = world.add_player(f"pilot{len(lives)}")       # counted as a human
        life = {0: 0.0}
        lives.append(life)
        pilot[p.id] = (Brain(hunter=True, rng=random.Random(rng.random())), life, t)

    for _ in range(pilots):
        spawn_pilot()

    tick_ms = []
    mix: list[str] = []          # level histogram of all objects, once per minute
    peak = {"mass": 0.0, "level": 0}
    while t < minutes * 60:
        for pid, (brain, life, born) in list(pilot.items()):
            if pid not in world.players:
                del pilot[pid]
                spawn_pilot()
                continue
            if t >= brain.next_think:
                brain.next_think = t + 0.15
                think(world, world.players[pid], brain, t)
        t0 = time.perf_counter()
        npcs.update(dt)
        world.step(dt)
        tick_ms.append((time.perf_counter() - t0) * 1000)
        t += dt
        if world.tick % (60 * C.TICK_HZ) == 0:
            lv = sorted(p.level for p in world.players.values())
            mix.append(f"min {round(t / 60):2d}: " + " ".join(str(x) for x in lv))
        for pid, (brain, life, born) in pilot.items():
            p = world.players.get(pid)
            if p is None:
                continue
            lvl = p.level
            if lvl not in life:
                for k in range(lvl + 1):
                    life.setdefault(k, t - born)
            if p.mass > peak["mass"]:
                peak = {"mass": round(p.mass), "level": lvl}

    tick_ms.sort()
    return {
        "lives": lives,
        "mix": mix,
        "peak": peak,
        "tick_ms_p50": round(statistics.median(tick_ms), 2),
        "tick_ms_p99": round(tick_ms[int(len(tick_ms) * 0.99)], 2),
        "players_end": len(world.players),
        "masses_end": sorted((round(p.mass), p.name) for p in world.players.values()),
    }


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 15
    pilots = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    res = run(minutes, pilots, seed)
    print(f"tick ms p50={res['tick_ms_p50']} p99={res['tick_ms_p99']} "
          f"players={res['players_end']} peak={res['peak']} ({LEVELS[res['peak']['level']].name})")
    print("end masses:", res["masses_end"])
    print("level mix over time (one digit per object, 0=dust .. 11=galaxy):")
    for line in res["mix"]:
        print("  " + line)
    best = max(res["lives"], key=len)
    print(f"{len(res['lives'])} pilot lives; best life reached:")
    for lvl, secs in sorted(best.items()):
        print(f"  {LEVELS[lvl].name:20s} at {secs / 60:5.1f} min")


if __name__ == "__main__":
    main()
