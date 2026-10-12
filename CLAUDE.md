# Universe IO: project memory

Renamed from Galaxy.io on 2026-10-11 (repo, conda env and `GALAXY_*` env vars keep the old name).

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

**2026-10-11** (M3)
- The ladder (names, thresholds, real-mass ranges, colours, facts) lives in `client/data/ladder.json`,
  read by both server and client. Edit facts there.
- Real-mass readout: the server maps game mass to real kg (log-linear within each level) and sends
  log10(kg); the client formats it ("≈ 1.1 Earths · like Earth"). The neutron star is *lighter*
  than the giant before it on purpose (the supernova blows most of the mass away); the fact card says so.
- Kid safety: spawn far from anything that can eat you, 3 s spawn shield (bubble ring), and NPCs
  ignore shielded players. Found by play-testing: I was eaten 7 s after spawning.
- Name filter in `server/game/names.py` (substring list + whole-word list + allowlist for
  Scunthorpe-style false positives). Bad names become "Stardust".

**2026-10-11** (M4)
- Level hysteresis (product owner request): level up at the threshold, level down only after
  falling `LEVEL_DOWN_MARGIN` (8%) below it, so boosting near a threshold doesn't flicker.
  The server owns each player's `level`; everything (decay, gravity, HUD, visuals) uses it.
- Visuals are all procedural: Canvas-2D painted textures (`client/js/objects/art.js`), a sphere
  shader for planets/stars (`sphere.js`), sprites for the rest (`bodies.js`). Variants per player id:
  Earth/Mars/Venus, Jupiter/Saturn/Neptune, Pluto/Ceres. Star colour follows mass (red→blue).
- Background: one full-screen shader draws a starfield + grid bent by the point-lens equation
  (`background.js`); Einstein radius per level in `LENS_K` (render.js). Shaders avoid `fwidth`
  so they compile on WebGL1 too (headless Chrome fell back to WebGL1).
- Effects: boost exhaust, level-up sparkle, supernova (giant→neutron), collapse (neutron→black hole).
- The menu spectates the leader live (attract mode); `?watch=1` hides the menu (classroom screen).
- Dev gallery of every object: http://localhost:8000/dev/gallery.html (`?boost=1`, `?fx=supernova`).

**2026-10-11** (M5)
- Hosting: the product owner's **Mac Studio** at **galaxyio.fun** (now universe-io.fun, see below) via **Cloudflare Tunnel** (no port
  forwarding, home IP hidden, automatic HTTPS). The server runs as a launchd LaunchAgent
  (`deploy/install_mac_service.sh`), `cloudflared service install` for the tunnel. Docker dropped
  (not needed on a single Mac). Full steps: `deploy/DEPLOY.md`.
- Safeguards: per-IP (8) and total (300) connection caps, 40-human cap (extra visitors spectate),
  message token bucket + flood disconnect, join cooldown, Origin check (`GALAXY_ALLOWED_ORIGINS`),
  crash-safe game loop, `/healthz`. Real IP from `CF-Connecting-IP` when the peer is localhost.
- Verified on the laptop with a quick tunnel (`cloudflared tunnel --url http://127.0.0.1:8000`):
  played through the public HTTPS URL in Chrome.

**2026-10-11** (rename + go-live)
- Product name is now **Universe IO**; domain **universe-io.fun** (replaces galaxyio.fun). Launchd label
  `fun.universe-io.server`, logs `~/Library/Logs/universe-io/`, tunnel name `universe-io`.
- Claude runs the production server on this Mac. The service runs from a separate checkout at
  `~/universe-io` (deploy with `git pull` there): macOS privacy protection (TCC) blocks launchd from
  reading `~/Documents`, where the dev checkout lives.
- conda: use `--override-channels -c conda-forge` (the Anaconda default channels need a ToS acceptance).
- Live 2026-10-11: tunnel `universe-io` (id 9269cdbe…), CNAMEs for apex + www. `cloudflared service install`
  wrote a plist without `tunnel run`; fixed by hand (steps in DEPLOY.md). Verified wss join through
  the public URL and a 403 for a foreign Origin.

**2026-10-11** (play-test feedback: swallow bug, pace, bot difficulty)
- "Can't swallow a same-level neighbour": no code bug; the rules were too strict. Measured with a
  probe: overlaps where nothing happened were mostly "not deep enough" (old rule: B's centre 40% of
  r_B inside A's edge) plus same-level pairs under the 25% mass margin (only 12% wider, look identical).
  Now `EAT_RATIO` 1.15 and `EAT_OVERLAP` 0 (swallowed once B's centre crosses A's edge). Regression tests.
- Pace +30%: `SPEED_V0` 230→300, `SPEED_MIN` 40→52, `ACCEL` 8→10, `EJECTA_SPEED` 420→540.
- Bots more aggressive: 4 of 10 slots are hunters (was 2), wider sensing, longer chases, shorter
  rest, boost-chasing, intercept aiming (lead the target), tighter aim while chasing, faster reactions.
  All in `config.py` under "NPC brains" with the old values in brackets. Kid safety unchanged (spawn
  shield, safe spawn spot, NPCs ignore shielded players).
- Sim (4 seeds, 15 min): bots-only world 10 eats per 10 min (was 2). The sim pilot dies 3–6 times
  per run (was 1–2) and its best life reaches giant star (in ~3 min on one seed, was 7.7 min) but
  no longer black hole / galaxy within 15 min. A first, harsher setting (5 hunters) killed it every
  1–2 min and was pulled back. `python -m server.sim` now prints each pilot death and its killer.

**2026-10-11** (feedback round 2: bots flee better, weaker gravity, phone controls)
- Escape AI: an NPC in danger scores 24 headings by the gap left to the nearest threat after 1 s
  (threats assumed to chase at top speed, own position clamped to the world, so corners score badly),
  notices fast/boosting threats earlier, grazes away from nearby threats, reacts every 0.05–0.1 s and
  boosts when a threat could reach it within 1.2 s. Bug found while tuning: capping the score at 0
  made every heading tie and sent cornered NPCs back toward the chaser. Benchmark (smart human-like
  chaser, 540 trials): caught 31 % → 11 %. Remaining catches are big NPCs pinned to a wall: above
  ~1100 mass everything moves at `SPEED_MIN`, so cornering stays a real tactic.
- Food gravity halved and reach 2.2 → 1.6 r: it was quadrupling food income at star level
  (52 vs 13 %/min with gravity off); now ~32 %/min. Growth at the top should come from hunting.
- Sim after both: pilot 1–2 deaths per 15 min, best life main-sequence/giant star; bots-only world
  4 eats per 10 min. Pacing is now slow at the top for a bot-skill pilot; watch play-test feedback.
- Touch controls (`client/js/touch.js`): floating joystick on the left half (appears under the thumb,
  let go = stop), hold-to-boost button on the right (greyed out until 25 mass), multi-touch via
  pointer events. Mouse input now uses pointer events filtered to `pointerType === 'mouse'`, because
  Safari turns taps into fake mouse clicks. Small screens zoom out (`viewScale`, 1 at >= 720 px) so a
  phone sees about the area a desktop does; compact HUD and touch wording on small screens.
  Tested in WebKit with iPhone portrait + landscape profiles (`tools/playtest_phone.py`).

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
- [x] **M3 HUD + science:** leaderboard, progress bar, real-mass readout, fact cards, name filter
- [x] **M4 Visuals:** lensing grid shader, boost particles, 12 animations, supernova
- [x] **M5 Deploy:** Mac + Cloudflare Tunnel, safeguards, launchd service, internet play-test
- [x] Touch controls (phone joystick + boost button)
- Later: sound, optional accounts or high scores, multiple rooms

## Commands
- Environment: `conda activate galaxyio` (Python 3.11), then `pip install -r requirements-dev.txt`
- Run server: `uvicorn server.main:app --reload --reload-dir server --port 8000`
  (`--reload-dir server` matters: watching the whole repo hung the reloader on branch switches), then open http://localhost:8000
- Tests: `pytest server/tests`
- Pacing sim: `python -m server.sim [minutes] [pilots] [seed]` (time to each level, size mix, tick cost)
- Auto-join for testing: http://localhost:8000/?name=TQ
- Play-test in real Chrome via DevTools (types a name, steers, boosts, screenshots, reads the HUD):
  `python tools/playtest.py <out_dir> [seconds]` (server must be running on :8000)
- Evaluate client JS in the page (no Node needed): `python tools/jseval.py "import('/js/realmass.js').then(m => m.formatRealMass(24.8))"`
- Phone play-test (WebKit, iPhone profile; `pip install playwright && python -m playwright install webkit`):
  `python tools/playtest_phone.py <out_dir> [base_url] ["iPhone 15 landscape"]`
- WebSocket load test: `python tools/loadtest.py [bots] [seconds]` (snapshot rate + KB/s per client)
- Object gallery: http://localhost:8000/dev/gallery.html · spectator view: http://localhost:8000/?watch=1
- Headless screenshot (no browser extension needed):
  `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --user-data-dir=<tmp> --window-size=1280,720 --virtual-time-budget=6000 --screenshot=out.png "http://127.0.0.1:8000/?name=TQ"`
  (Chrome may not exit after the shot; wrap it in `perl -e 'alarm 45; exec @ARGV'` and kill the profile's process.)
- Host / update production (one command, idempotent): `deploy/start_hosting.sh`
- Production by hand: `GALAXY_PYTHON=$(which python) scripts/run_prod.sh` (+ `cloudflared tunnel --url http://127.0.0.1:8000` for a temporary public URL); hosting guide `deploy/DEPLOY.md`
- Legacy game: `cd legacy && python server.py` and `python game.py` (needs pygame)

## Engineering conventions
- Game rules are pure functions or classes in `server/game/` with no network code, so they are unit-testable.
- All tunable numbers live in one place (`server/game/config.py`), not scattered through the code.
- Client never decides outcomes; it only sends input and draws.
