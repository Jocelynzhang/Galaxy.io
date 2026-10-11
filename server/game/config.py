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
SPAWN_SAFE_DIST = 700        # try to spawn at least this far from anything that could eat you
SPAWN_SHIELD_S = 3.0         # newly spawned objects can't be eaten for this long
RADIUS_K = 4.0               # radius = RADIUS_K * sqrt(mass)

# speed = SPEED_V0 * mass^-SPEED_EXP, never below SPEED_MIN (world units / second)
SPEED_V0 = 230.0
SPEED_EXP = 0.25
SPEED_MIN = 40.0
ACCEL = 8.0                  # how quickly velocity approaches the target (1/s)

# eating: A eats B if m_A >= EAT_RATIO * m_B and dist < r_A - EAT_OVERLAP * r_B
EAT_RATIO = 1.25
EAT_OVERLAP = 0.4
EAT_EFFICIENCY = 0.9         # fraction of the victim's mass the eater gains

# --- boost (hold left mouse) ---
BOOST_MULT = 2.0             # speed multiplier while boosting
BOOST_MIN_MASS = 25.0        # asteroid threshold: dust can't boost
BOOST_LOSS_FRAC = 0.03       # fraction of mass shed per second while boosting
EJECTA_MASS_FRAC = 0.003     # each pellet's mass as a fraction of the booster's mass...
EJECTA_MASS_MIN = 1.0        # ...clamped to this range
EJECTA_MASS_MAX = 25.0
EJECTA_SPEED = 420.0         # launch speed backward (world units / s)
EJECTA_SPREAD = 0.26         # half-angle of the exhaust cone (radians, ~15 degrees)
EJECTA_DRAG = 4.0            # velocity decay rate (1/s)
EJECTA_ARM_S = 0.25          # others may eat a pellet after this many seconds
EJECTA_OWNER_ARM_S = 1.2     # the booster itself may re-eat it after this many seconds
EJECTA_COLOR_BASE = 100      # food color = base + booster's level, so the client can tint it

# --- gravity on food (never on players) ---
# food within GRAVITY_REACH * r drifts inward at GRAVITY[level] * (r / d)^2 units / s
GRAVITY = [0, 0, 30, 40, 55, 60, 80, 90, 110, 160, 200, 140]
GRAVITY_REACH = 2.2
GRAVITY_MAX_SPEED = 300.0

# --- mass decay for big objects (stars shine away mass!) ---
# fraction of mass lost per second, by level index
DECAY = [0, 0, 0, 0, 0, 0, 0.0004, 0.0006, 0.0008, 0.001, 0.0013, 0.0016]

# --- NPCs ---
TARGET_PLAYERS = 10          # humans + NPCs the world aims for
NPC_RESPAWN_S = 3.0          # delay before a missing NPC slot is refilled
NPC_SPAWN_MASS = (10.0, 300.0)  # log-uniform spawn mass range, so there is prey and danger
NPC_THINK_S = (0.2, 0.4)     # reaction delay range
# NPC "slots": each slot has a fixed ambition (max level) and personality. Above its cap an NPC
# sheds mass fast, so the world keeps a stable mix of small, medium and big objects and the very
# top of the leaderboard is left for humans. Slots are filled in this order (first = most kept).
NPC_SLOTS = [  # (max level, hunter)
    (6, False), (3, False), (5, True), (8, False), (4, False),
    (7, False), (2, False), (9, True), (5, False), (6, False),
]
NPC_OVERCAP_DECAY = 0.02     # extra fraction of mass lost per second above the cap

# --- camera ---
# on-screen radius = SCREEN_R0 * (r / r_start) ** ZOOM_EXP ; zoom = screen radius / world radius
SCREEN_R0 = 24.0
ZOOM_EXP = 0.6
VIEW_MARGIN = 150            # extra world units sent around the visible area

# --- input / names ---
NAME_MAX_LEN = 16
DEFAULT_NAME = "Stardust"
MAX_VIEW_PX = 4096           # clamp client-reported viewport size
