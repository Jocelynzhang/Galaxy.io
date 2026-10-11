// Turns a real mass (sent by the server as log10 of kilograms) into kid-friendly text,
// e.g. "≈ 2.1 Earths · like Earth" or "≈ 4.3 million Suns · like Sagittarius A*".
const SUN = 1.989e30;
const JUPITER = 1.898e27;
const EARTH = 5.97e24;

// Real objects to compare against (kg). Shown when you're within about 2x of one.
const LANDMARKS = [
  [1e-15, 'a speck of space dust'],
  [1e-6, 'a grain of sand'],
  [1, 'a bag of sugar'],
  [1.5e3, 'a car'],
  [6e3, 'an elephant'],
  [1.5e5, 'a blue whale'],
  [3.3e8, 'the Empire State Building'],
  [6e9, 'the Great Pyramid'],
  [7.3e10, 'asteroid Bennu'],
  [2.2e14, "Halley's Comet"],
  [2.6e20, 'asteroid Vesta'],
  [9.4e20, 'Ceres'],
  [1.3e22, 'Pluto'],
  [7.35e22, 'the Moon'],
  [6.4e23, 'Mars'],
  [5.97e24, 'Earth'],
  [1.02e26, 'Neptune'],
  [5.68e26, 'Saturn'],
  [1.898e27, 'Jupiter'],
  [1.989e30, 'the Sun'],
  [3.6e31, 'Betelgeuse'],
  [4.3e6 * SUN, 'Sagittarius A*'],
  [6.5e9 * SUN, 'M87*'],
  [1.5e12 * SUN, 'the Milky Way'],
];

const BIG = [[1e12, 'trillion'], [1e9, 'billion'], [1e6, 'million'], [1e3, 'thousand']];

function nice(x) {
  for (const [v, word] of BIG) {
    if (x >= v) return `${trim(x / v)} ${word}`;
  }
  return trim(x);
}

function trim(x) {
  if (x >= 100) return String(Math.round(x));
  if (x >= 10) return x.toFixed(1).replace(/\.0$/, '');
  return String(+x.toPrecision(2));   // 0.10 -> "0.1", 2.0 -> "2"
}

const SUP = { '-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' };
function sci(x, unit) {
  const e = Math.floor(Math.log10(x));
  const m = x / 10 ** e;
  const exp = String(e).split('').map((c) => SUP[c]).join('');
  return `${trim(m)} × 10${exp} ${unit}`;
}

function amount(x, one, many) {
  const s = nice(x);
  return `${s} ${s === '1' ? one : many}`;
}

export function formatRealMass(log10kg) {
  const kg = 10 ** log10kg;
  let text;
  if (kg >= 0.08 * SUN) text = amount(kg / SUN, 'Sun', 'Suns');
  else if (kg >= 0.05 * JUPITER) text = amount(kg / JUPITER, 'Jupiter', 'Jupiters');
  else if (kg >= 0.01 * EARTH) text = amount(kg / EARTH, 'Earth', 'Earths');
  else if (kg >= 1e15) text = sci(kg, 'kg');           // beyond a trillion tonnes words stop helping
  else if (kg >= 1e3) text = `${nice(kg / 1e3)} tonnes`;
  else if (kg >= 1) text = `${trim(kg)} kg`;
  else if (kg >= 1e-3) text = `${trim(kg * 1e3)} g`;
  else text = sci(kg * 1e3, 'g');

  let best = null;
  for (const [mass, name] of LANDMARKS) {
    const d = Math.abs(Math.log10(mass) - log10kg);
    if (d < 0.3 && (!best || d < best.d)) best = { d, name };
  }
  return best ? `≈ ${text} · like ${best.name}` : `≈ ${text}`;
}
