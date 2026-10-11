"""All tunable game numbers live here. World units are arbitrary 'pixels at zoom 1'."""

# --- timing ---
TICK_HZ = 30
SNAPSHOT_EVERY = 2           # send a snapshot every N ticks (30 Hz / 2 = 15 Hz)

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

# --- camera ---
# on-screen radius = SCREEN_R0 * (r / r_start) ** ZOOM_EXP ; zoom = screen radius / world radius
SCREEN_R0 = 24.0
ZOOM_EXP = 0.6
VIEW_MARGIN = 150            # extra world units sent around the visible area

# --- input / names ---
NAME_MAX_LEN = 16
DEFAULT_NAME = "Stardust"
MAX_VIEW_PX = 4096           # clamp client-reported viewport size
