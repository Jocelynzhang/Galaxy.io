"""All tunable game numbers live here. World units are arbitrary 'pixels at zoom 1'."""

# --- timing ---
TICK_HZ = 30
SNAPSHOT_EVERY = 2           # send a snapshot every N ticks (30 Hz / 2 = 15 Hz)
LEADERBOARD_EVERY = 30       # include the leaderboard every N ticks (must be a multiple of SNAPSHOT_EVERY)
LEADERBOARD_SIZE = 10

# --- world ---
WORLD_W = 4500
WORLD_H = 4500
GRID_CELL = 200              # spatial hash cell size

# --- food ---
FOOD_TARGET = 4500           # food pellets kept in the world
FOOD_SPAWN_PER_TICK = 20     # max pellets respawned per tick
FOOD_MASS = 1.0
FOOD_RADIUS = 4.0
FOOD_COLORS = 6              # number of palette entries the client knows about

# --- players ---
START_MASS = 10.0
# level hysteresis: you level up at a threshold, but only drop back once your mass is this
# fraction below it, so boosting near a threshold doesn't flicker between two levels
LEVEL_DOWN_MARGIN = 0.08
SPAWN_SAFE_DIST = 700        # try to spawn at least this far from anything that could eat you
SPAWN_SHIELD_S = 3.0         # newly spawned objects can't be eaten for this long
RADIUS_K = 4.0               # radius = RADIUS_K * sqrt(mass)

# speed = SPEED_V0 * mass^-SPEED_EXP, never below SPEED_MIN (world units / second)
SPEED_V0 = 300.0             # 2026-10-11: +30% (was 230) for a faster pace
SPEED_EXP = 0.25
SPEED_MIN = 52.0
ACCEL = 10.0                 # how quickly velocity approaches the target (1/s)

# eating: A eats B if m_A >= EAT_RATIO * m_B and dist < r_A - EAT_OVERLAP * r_B
# (EAT_OVERLAP 0 = swallowed as soon as B's centre crosses A's edge, i.e. half of B is inside A).
# Was 1.25 / 0.4: same-level objects overlapped by more than half and nothing happened.
EAT_RATIO = 1.15
EAT_OVERLAP = 0.0
EAT_EFFICIENCY = 0.9         # fraction of the victim's mass the eater gains

# --- boost (hold left mouse) ---
BOOST_MULT = 2.0             # speed multiplier while boosting
BOOST_MIN_MASS = 25.0        # asteroid threshold: dust can't boost
BOOST_LOSS_FRAC = 0.03       # fraction of mass shed per second while boosting
EJECTA_MASS_FRAC = 0.003     # each pellet's mass as a fraction of the booster's mass...
EJECTA_MASS_MIN = 1.0        # ...clamped to this range
EJECTA_MASS_MAX = 25.0
EJECTA_SPEED = 540.0         # launch speed backward (world units / s)
EJECTA_SPREAD = 0.26         # half-angle of the exhaust cone (radians, ~15 degrees)
EJECTA_DRAG = 4.0            # velocity decay rate (1/s)
EJECTA_ARM_S = 0.25          # others may eat a pellet after this many seconds
EJECTA_OWNER_ARM_S = 1.2     # the booster itself may re-eat it after this many seconds
EJECTA_COLOR_BASE = 100      # food color = base + booster's level, so the client can tint it

# --- gravity on food (never on players) ---
# food within GRAVITY_REACH * r drifts inward at GRAVITY[level] * (r / d)^2 units / s
# 2026-10-11: halved and shorter reach (was [.., 30, 40, 55, 60, 80, 90, 110, 160, 200, 140], 2.2):
# gravity was quadrupling food income at star level, so big objects grew without hunting
GRAVITY = [0, 0, 15, 20, 28, 30, 40, 45, 55, 80, 100, 70]
GRAVITY_REACH = 1.6
GRAVITY_MAX_SPEED = 300.0

# --- mass decay for big objects (stars shine away mass!) ---
# fraction of mass lost per second, by level index
DECAY = [0, 0, 0, 0, 0, 0, 0.0004, 0.0006, 0.0008, 0.001, 0.0013, 0.0016]

# --- NPCs ---
TARGET_PLAYERS = 10          # humans + NPCs the world aims for
NPC_RESPAWN_S = 3.0          # delay before a missing NPC slot is refilled
NPC_SPAWN_MASS = (10.0, 300.0)  # log-uniform spawn mass range, so there is prey and danger
NPC_THINK_S = (0.12, 0.25)    # reaction delay range
# NPC "slots": each slot has a fixed ambition (max level) and personality. Above its cap an NPC
# sheds mass fast, so the world keeps a stable mix of small, medium and big objects and the very
# top of the leaderboard is left for humans. Slots are filled in this order (first = most kept).
NPC_SLOTS = [  # (max level, hunter)
    (6, False), (3, False), (5, True), (8, True), (4, False),
    (7, False), (2, True), (9, True), (5, False), (6, False),
]
NPC_OVERCAP_DECAY = 0.02     # extra fraction of mass lost per second above the cap
# NPC brains (2026-10-11: made more aggressive; old values in brackets)
NPC_SENSE = (5.0, 600.0)     # sensing range = k * radius + c   [4, 450]
NPC_CHASE_S = (6.0, 3.0)     # how long a hunter / cautious NPC chases one target   [5, 2]
NPC_GIVE_UP_S = 2.0          # rest after a chase times out, so players can escape   [3]
NPC_SNACK_DIST = (3.0, 200.0)  # cautious NPCs start chases within k * radius + c   [2, 80]
NPC_CHASE_BOOST = (0.8, 0.4)   # chance per think to boost at close prey, hunter / cautious   [0.6, 0.25]
NPC_BOOST_RATIO = 1.35       # only boost-chase prey this much lighter (boosting costs mass)   [1.6]
NPC_FLEE_BOOST = 0.95        # chance per think to boost away from a close threat   [0.7]
# running away (2026-10-11 round 2): score NPC_FLEE_DIRS headings by the gap they leave to the
# nearest threat after NPC_FLEE_LOOKAHEAD s, so NPCs slide along walls instead of getting cornered
NPC_FLEE_ALARM = 0.2         # danger level that switches an NPC into escape mode   [0.25]
NPC_FLEE_WARN_S = 2.0        # a threat counts as dangerous within this many seconds of its top speed
NPC_FLEE_BOOST_S = 1.2       # boost when the nearest threat could reach us within this many seconds
NPC_FLEE_THINK_S = (0.05, 0.1)  # faster reactions while escaping
NPC_FLEE_DIRS = 24
NPC_FLEE_LOOKAHEAD = 1.0
NPC_FLEE_WALL_ROOM = 250.0   # prefer escape routes that keep this much room from the walls
NPC_LEAD_S = 0.8             # aim at where the prey will be, up to this many seconds ahead   [0]
NPC_AIM_NOISE = (0.1, 0.25)    # steering error (radians) while chasing / otherwise   [0.25, 0.25]

# --- camera ---
# on-screen radius = SCREEN_R0 * (r / r_start) ** ZOOM_EXP ; zoom = screen radius / world radius
SCREEN_R0 = 24.0
ZOOM_EXP = 0.6
VIEW_MARGIN = 150            # extra world units sent around the visible area

# --- public-server limits ---
MAX_CONNECTIONS = 300          # total open WebSockets
MAX_CONNECTIONS_PER_IP = 8     # a family/classroom behind one IP still fits
MAX_HUMANS = 40                # beyond this, visitors can watch but not join
MSG_RATE = 40.0                # messages per second per connection (client sends ~20)
MSG_BURST = 80.0
MSG_ABUSE_DROPS = 400          # rate-limited messages before the connection is closed
JOIN_COOLDOWN_S = 1.0          # minimum time between joins on one connection

# --- input / names ---
NAME_MAX_LEN = 16
DEFAULT_NAME = "Stardust"
MAX_VIEW_PX = 4096           # clamp client-reported viewport size
