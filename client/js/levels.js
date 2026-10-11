// The ladder is loaded from data/ladder.json, the same file the server reads.
export const LEVELS = [];
export let TOP_MASS = Infinity;
let startMass = 0;

// Everyone spawns at the server's start mass, so dust progress is measured from there.
export function setStartMass(m) {
  startMass = m;
}

export async function loadLadder() {
  const data = await (await fetch(new URL('../data/ladder.json', import.meta.url))).json();
  TOP_MASS = data.top_mass;
  for (const l of data.levels) {
    LEVELS.push({ ...l, css: l.color, color: parseInt(l.color.slice(1), 16) });
  }
}

// Game-mass range [start, end) of level i.
export function levelSpan(i) {
  const start = i === 0 ? startMass : LEVELS[i].min_mass;
  return [start, i + 1 < LEVELS.length ? LEVELS[i + 1].min_mass : TOP_MASS];
}

export const FOOD_PALETTE = [0x70b7db, 0x9e89d6, 0xb2c76f, 0xf2a7c3, 0xffd98a, 0x8fe3c8];

// Food color codes >= EJECTA_COLOR_BASE are boost exhaust, tinted by the booster's level.
const EJECTA_COLOR_BASE = 100;
export function foodColor(c) {
  if (c >= EJECTA_COLOR_BASE) return LEVELS[Math.min(c - EJECTA_COLOR_BASE, LEVELS.length - 1)].color;
  return FOOD_PALETTE[c % FOOD_PALETTE.length];
}
