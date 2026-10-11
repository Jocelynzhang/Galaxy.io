# Galaxy.io: project memory

## Vision
A browser IO game that teaches kids about the objects in the universe. You start as a speck of
**dust**, eat food and smaller players, and climb the astrophysical ladder until you are the most
massive object in the universe:

dust → asteroid → dwarf planet → terrestrial planet → gas giant → brown dwarf → main-sequence star
→ giant star → neutron star → black hole → quasar → galaxy

Scientific accuracy matters (real-mass readouts, fact cards, honest notes where the game simplifies).
When accuracy and readable gameplay conflict, gameplay wins and a fact card tells the truth.

## Roles
- **Product owner (user):** features, ideas, feel. Expect changing requirements.
- **Engineering lead (Claude):** architecture, implementation, tests, tuning, deploy. Record every new
  feature request or decision in this file (Backlog / Decisions log).

## Architecture
- **Server (Python 3.11, authoritative):** FastAPI + uvicorn, one asyncio game loop at 30 Hz, spatial
  hash grid, ~20 Hz per-client snapshots culled to the player's view. All rules live here: movement,
  eating, boost, food gravity, mass decay, levels, NPCs.
- **Client (browser, render only):** `client/index.html` + ES modules + PixiJS v8 from a CDN (no
  build step). Sends `{angle, throttle, boost}`; interpolates snapshots about 100 ms behind.
- **Transport:** WebSocket `/ws`, JSON messages. Never use pickle on the network.
- `legacy/` = the original 2022 pygame LAN version, for reference only (run it from inside `legacy/`).

```
server/main.py            FastAPI: static files + WS /ws
server/game/              world.py, entities.py, levels.py, physics.py, npc.py
server/tests/             pytest on pure game logic
client/                   index.html, js/ (net, render, camera, lensing, hud, objects/<level>.js)
```

## Feature backlog (from the product owner)
1. Server + HTML model: users just open the URL, type a name and play.
2. First scene: name input + Confirm → game.
3. Mouse steering. Hold left-click to boost at the cost of mass; the mass is ejected backward as
   animated particles that become food for smaller players. Bigger objects move slower.
4. Light line-grid background with gravitational lensing that distorts it based on mass.
5. HUD: leaderboard top-left. Top-right: progress bar with the current level and the next level's
   icon/animation, plus progress to the next level.
6. Loop animations for every level including dust; boost particles animated too.
7. ~10 players in the world. With no humans, NPCs fill it. When humans join, don't remove NPCs; just
   stop respawning eaten NPCs until the total is back to ~10.

## Decisions log
**2026-10-11** (initial Q&A)
| Topic | Decision |
|---|---|
| Engine | Python authoritative server + JS/PixiJS v8 render-only client |
| Art | Procedural / code-drawn animations; tone cute + semi-real |
| Devices | Desktop (mouse) first; touch later |
| World | Large scrolling map; camera follows and zooms out as you grow |
| Gravity | Big objects pull **food and ejected particles only**, not players |
| Death | Respawn as dust; "swallowed by X" screen with best level; Play Again |
| Endgame | Galaxy is the top rank; keep growing; mass decay for big objects |
| Ladder | 12 levels (neutron star added); "dwarf star" = brown dwarf |
| Black hole | Small dark core + big accretion disk + strong lensing; fact card on real size |
| Science extras | Supernova animation (giant → neutron star), level-up fact cards, real-mass readout |
| Language | English only |
| NPCs | Astronomer names + small bot tag; mostly cautious, 1–2 hunters; beatable |
| Login | Name only; no accounts, no chat; basic name profanity filter |
| Hosting | Decide at M5; ship a Dockerfile (Fly.io / Render / VPS) |
| Pacing | Skilled dust → galaxy ≈ 10–15 min; early levels fast |
| Lensing | Exaggerated and grows by level; Einstein rings for black hole and above |
| Boost | Hold left mouse; ~2× speed; mass streams out as edible particles; dust can't boost |
| Workflow | Branch + PR per milestone, each with a local playable demo |

**2026-10-11** (M2 tuning, from `python -m server.sim`)
- Game-mass thresholds: dust 0, asteroid 25, dwarf planet 60, terrestrial 130, gas giant 260,
  brown dwarf 500, main-sequence 900, giant 1600, neutron star 2600, black hole 3800, quasar 5500,
  galaxy 8000. Top levels are close together because late growth comes from eating big NPCs.
- Mass decay per level (`DECAY` table): only main-sequence and up; galaxy 0.16 %/s.
- NPCs use fixed "slots" (`NPC_SLOTS`), each with a max level and personality. Above its cap an
  NPC sheds mass quickly. This keeps a stable mix of sizes, so kids joining late are not surrounded
  by galaxies, and leaves the top of the leaderboard to humans. 2 of 10 slots are hunters.
- Sim result: skilled pilot reaches galaxy in ~10–15 min in 3 of 4 seeds; tick ≈ 0.6 ms.
- Workflow: Claude opens a PR per milestone and merges it when tests pass; the product owner
  play-tests on master and sends feedback.

## Science ladder (real-mass ranges shown in the HUD, log-mapped within each level)
| # | Level | Real mass | Fact-card examples |
|---|---|---|---|
| 0 | Dust | 10⁻¹⁵ – 10³ kg | interplanetary dust → boulder |
| 1 | Asteroid | 10³ – 10²⁰ kg | Bennu, Vesta |
| 2 | Dwarf planet | 10²⁰ – 10²³ kg | Ceres, Pluto |
| 3 | Terrestrial planet | 10²³ – 10²⁵ kg | Mars, Earth |
| 4 | Gas giant | 10²⁵ – 2.5×10²⁸ kg | Neptune, Saturn, Jupiter |
| 5 | Brown dwarf | 13 – 80 M_Jup | "failed star" |
| 6 | Main-sequence star | 0.08 – 20 M☉ | red dwarf → Sun → blue star |
| 7 | Giant star | ~1 – 20 M☉, huge radius | Betelgeuse |
| 8 | Neutron star | 1.4 – 2.3 M☉, city-sized | pulsar |
| 9 | Black hole | 5 – 10⁹ M☉ | Cygnus X-1 → Sgr A* |
| 10 | Quasar | 10⁸ – 10¹⁰ M☉, actively feeding | 3C 273 |
| 11 | Galaxy | 10⁹ – 10¹² M☉ | Milky Way |

## Milestones
- [x] **M0 Bootstrap:** CLAUDE.md, legacy/ move, requirements, .gitignore
- [x] **M1 Skeleton:** FastAPI + WS, name screen, mouse steering, food, eating, big world + camera
- [x] **M2 Mechanics:** speed curve, boost + ejecta, food gravity, decay, ladder, death screen, NPCs
- [ ] **M3 HUD + science:** leaderboard, progress bar, real-mass readout, fact cards, name filter
- [ ] **M4 Visuals:** lensing grid shader, boost particles, 12 animations, supernova
- [ ] **M5 Deploy:** Dockerfile, host, HTTPS/wss, rate limits, internet play-test
- Later: touch controls, sound, optional accounts or high scores, multiple rooms

## Commands
- Environment: `conda activate galaxyio` (Python 3.11), then `pip install -r requirements-dev.txt`
- Run server: `uvicorn server.main:app --reload --reload-dir server --port 8000`
  (`--reload-dir server` matters: watching the whole repo hung the reloader on branch switches), then open http://localhost:8000
- Tests: `pytest server/tests`
- Pacing sim: `python -m server.sim [minutes] [pilots] [seed]` (time to each level, size mix, tick cost)
- Auto-join for testing: http://localhost:8000/?name=TQ
- Headless screenshot (no browser extension needed):
  `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --user-data-dir=<tmp> --window-size=1280,720 --virtual-time-budget=6000 --screenshot=out.png "http://127.0.0.1:8000/?name=TQ"`
  (Chrome may not exit after the shot; wrap it in `perl -e 'alarm 45; exec @ARGV'` and kill the profile's process.)
- Legacy game: `cd legacy && python server.py` and `python game.py` (needs pygame)

## Engineering conventions
- Game rules are pure functions or classes in `server/game/` with no network code, so they are unit-testable.
- All tunable numbers live in one place (`server/game/config.py`), not scattered through the code.
- Client never decides outcomes; it only sends input and draws.
