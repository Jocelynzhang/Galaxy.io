// Client-side display info for the ladder; indices match server/game/levels.py.
export const LEVELS = [
  { key: 'dust', name: 'Dust', color: 0xc9b79c },
  { key: 'asteroid', name: 'Asteroid', color: 0x9e8f80 },
  { key: 'dwarf_planet', name: 'Dwarf planet', color: 0xd9c2a7 },
  { key: 'terrestrial', name: 'Terrestrial planet', color: 0x4f9de0 },
  { key: 'gas_giant', name: 'Gas giant', color: 0xe0a96d },
  { key: 'brown_dwarf', name: 'Brown dwarf', color: 0xb0507a },
  { key: 'main_sequence', name: 'Main-sequence star', color: 0xffd34d },
  { key: 'giant', name: 'Giant star', color: 0xff7a45 },
  { key: 'neutron_star', name: 'Neutron star', color: 0xbfe6ff },
  { key: 'black_hole', name: 'Black hole', color: 0x5b3f8c },
  { key: 'quasar', name: 'Quasar', color: 0x9f7bff },
  { key: 'galaxy', name: 'Galaxy', color: 0xd6b8ff },
];

export const FOOD_PALETTE = [0x70b7db, 0x9e89d6, 0xb2c76f, 0xf2a7c3, 0xffd98a, 0x8fe3c8];

// Food color codes >= EJECTA_COLOR_BASE are boost exhaust, tinted by the booster's level.
const EJECTA_COLOR_BASE = 100;
export function foodColor(c) {
  if (c >= EJECTA_COLOR_BASE) return LEVELS[Math.min(c - EJECTA_COLOR_BASE, LEVELS.length - 1)].color;
  return FOOD_PALETTE[c % FOOD_PALETTE.length];
}
