// Procedural art: every texture in the game is painted here with Canvas 2D, once, and cached.
// Surface maps are equirectangular (2:1) so the sphere shader can wrap them around a globe.
import { CanvasSource, Texture } from 'https://cdn.jsdelivr.net/npm/pixi.js@8.21.0/dist/pixi.min.mjs';

const cache = new Map();

// Small seeded PRNG so every texture looks the same on every visit.
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

function toTexture(c, repeat) {
  const source = new CanvasSource({ resource: c, addressMode: repeat ? 'repeat' : 'clamp-to-edge' });
  return new Texture({ source });
}

export function tex(key, paint, { w = 256, h = w, repeat = false } = {}) {
  if (!cache.has(key)) {
    const c = canvas(w, h);
    paint(c.getContext('2d'), w, h);
    cache.set(key, toTexture(c, repeat));
  }
  return cache.get(key);
}

// ---------- helpers ----------
function blob(ctx, x, y, r, color, alpha = 1) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, color);
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.globalAlpha = alpha;
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

// Draw on an equirectangular map, wrapping horizontally so the seam is invisible.
function wrapped(w, fn) {
  fn(0);
  fn(-w);
  fn(w);
}

// Value-noise "clouds": sum of random soft blobs; returns nothing, paints with the given colors.
function speckle(ctx, w, h, rand, n, colors, rMin, rMax, alpha = 0.5, latBand = [0, 1]) {
  for (let i = 0; i < n; i++) {
    const x = rand() * w;
    const y = (latBand[0] + rand() * (latBand[1] - latBand[0])) * h;
    const r = rMin + rand() * (rMax - rMin);
    const col = colors[Math.floor(rand() * colors.length)];
    wrapped(w, (dx) => blob(ctx, x + dx, y, r, col, alpha));
  }
}

function bands(ctx, w, h, rand, palette, count, wobble) {
  const bh = h / count;
  for (let i = 0; i < count; i++) {
    ctx.fillStyle = palette[i % palette.length];
    ctx.beginPath();
    ctx.moveTo(0, i * bh);
    for (let x = 0; x <= w; x += 8) {
      ctx.lineTo(x, i * bh + Math.sin((x / w) * Math.PI * 2 * (2 + i % 3) + i) * wobble);
    }
    ctx.lineTo(w, (i + 1) * bh + wobble);
    ctx.lineTo(0, (i + 1) * bh + wobble);
    ctx.fill();
  }
}

function craters(ctx, w, h, rand, n, rMax, dark, light) {
  for (let i = 0; i < n; i++) {
    const x = rand() * w, y = h * (0.12 + rand() * 0.76), r = 2 + rand() * rMax;
    wrapped(w, (dx) => {
      ctx.fillStyle = dark;
      ctx.beginPath();
      ctx.ellipse(x + dx, y, r, r * 0.9, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = light;
      ctx.lineWidth = Math.max(1, r * 0.25);
      ctx.beginPath();
      ctx.arc(x + dx + r * 0.15, y - r * 0.15, r, Math.PI * 1.1, Math.PI * 1.9);
      ctx.stroke();
    });
  }
}

function polarCaps(ctx, w, h, color, size = 0.09) {
  const g1 = ctx.createLinearGradient(0, 0, 0, h * size * 1.6);
  g1.addColorStop(0, color);
  g1.addColorStop(0.6, color);
  g1.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g1;
  ctx.fillRect(0, 0, w, h * size * 1.6);
  const g2 = ctx.createLinearGradient(0, h, 0, h - h * size * 1.6);
  g2.addColorStop(0, color);
  g2.addColorStop(0.6, color);
  g2.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g2;
  ctx.fillRect(0, h - h * size * 1.6, w, h * size * 1.6);
}

const MAP = { w: 512, h: 256, repeat: true };

// ---------- surface maps (for the sphere shader) ----------
export const surfaces = {
  pluto: () => tex('pluto', (ctx, w, h) => {
    const r = rng(11);
    ctx.fillStyle = '#c9a98a';
    ctx.fillRect(0, 0, w, h);
    speckle(ctx, w, h, r, 120, ['#8a5a3c', '#a77b58', '#e2c9a8'], 8, 40, 0.45);
    // Tombaugh Regio: the famous bright "heart"
    ctx.fillStyle = '#f6ece0';
    ctx.beginPath();
    const cx = w * 0.5, cy = h * 0.52, s = h * 0.2;
    ctx.moveTo(cx, cy + s);
    ctx.bezierCurveTo(cx - s * 1.6, cy, cx - s * 0.9, cy - s * 1.1, cx, cy - s * 0.35);
    ctx.bezierCurveTo(cx + s * 0.9, cy - s * 1.1, cx + s * 1.6, cy, cx, cy + s);
    ctx.fill();
    craters(ctx, w, h, r, 25, 6, 'rgba(90,60,40,0.35)', 'rgba(255,240,220,0.3)');
  }, MAP),

  ceres: () => tex('ceres', (ctx, w, h) => {
    const r = rng(12);
    ctx.fillStyle = '#7d7a76';
    ctx.fillRect(0, 0, w, h);
    speckle(ctx, w, h, r, 90, ['#5e5b58', '#9a9691'], 6, 30, 0.5);
    craters(ctx, w, h, r, 70, 9, 'rgba(50,48,46,0.55)', 'rgba(200,198,190,0.35)');
    // Occator crater's bright salt spots
    wrapped(w, (dx) => blob(ctx, w * 0.3 + dx, h * 0.45, 7, '#ffffff', 0.95));
  }, MAP),

  earth: () => tex('earth', (ctx, w, h) => {
    const r = rng(21);
    ctx.fillStyle = '#1f5fae';
    ctx.fillRect(0, 0, w, h);
    speckle(ctx, w, h, r, 40, ['#2a74c9', '#164a8c'], 20, 60, 0.4);
    // continents: clusters of overlapping blobs
    for (let c = 0; c < 7; c++) {
      const cx = r() * w, cy = h * (0.25 + r() * 0.5);
      for (let i = 0; i < 26; i++) {
        const x = cx + (r() - 0.5) * 90, y = cy + (r() - 0.5) * 60, rad = 8 + r() * 18;
        const col = r() < 0.7 ? '#3f9a3c' : (r() < 0.5 ? '#b49a5a' : '#2f7a33');
        wrapped(w, (dx) => {
          ctx.fillStyle = col;
          ctx.beginPath();
          ctx.arc(x + dx, y, rad, 0, Math.PI * 2);
          ctx.fill();
        });
      }
    }
    polarCaps(ctx, w, h, '#f4f8ff', 0.08);
  }, MAP),

  earthClouds: () => tex('earthClouds', (ctx, w, h) => {
    const r = rng(22);
    ctx.clearRect(0, 0, w, h);
    speckle(ctx, w, h, r, 140, ['rgba(255,255,255,0.9)'], 6, 26, 0.55, [0.1, 0.9]);
  }, MAP),

  mars: () => tex('mars', (ctx, w, h) => {
    const r = rng(23);
    ctx.fillStyle = '#c1502a';
    ctx.fillRect(0, 0, w, h);
    speckle(ctx, w, h, r, 110, ['#8f3418', '#d9703f', '#7a2e17'], 10, 45, 0.45);
    // Valles Marineris
    ctx.strokeStyle = 'rgba(90,30,15,0.7)';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(w * 0.3, h * 0.55);
    ctx.bezierCurveTo(w * 0.38, h * 0.5, w * 0.45, h * 0.58, w * 0.52, h * 0.53);
    ctx.stroke();
    craters(ctx, w, h, r, 30, 6, 'rgba(110,40,20,0.4)', 'rgba(240,160,120,0.3)');
    polarCaps(ctx, w, h, '#fff4ee', 0.06);
  }, MAP),

  venus: () => tex('venus', (ctx, w, h) => {
    const r = rng(24);
    ctx.fillStyle = '#e3c27f';
    ctx.fillRect(0, 0, w, h);
    bands(ctx, w, h, r, ['rgba(240,214,150,0.6)', 'rgba(205,165,95,0.5)'], 9, 10);
    speckle(ctx, w, h, r, 120, ['#f3dca6', '#c79d5c'], 10, 40, 0.35);
  }, MAP),

  jupiter: () => tex('jupiter', (ctx, w, h) => {
    const r = rng(31);
    bands(ctx, w, h, r, ['#e9dcc0', '#c99b6b', '#f1e6cf', '#a8714b', '#dcc29a', '#b9855a'], 14, 4);
    speckle(ctx, w, h, r, 160, ['rgba(255,255,255,0.5)', 'rgba(120,70,40,0.5)'], 4, 14, 0.35);
    // Great Red Spot
    wrapped(w, (dx) => {
      ctx.fillStyle = '#c0573c';
      ctx.beginPath();
      ctx.ellipse(w * 0.62 + dx, h * 0.64, 26, 14, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#e8b392';
      ctx.lineWidth = 3;
      ctx.stroke();
    });
  }, MAP),

  saturn: () => tex('saturn', (ctx, w, h) => {
    const r = rng(32);
    bands(ctx, w, h, r, ['#ead9a8', '#d8bf84', '#f1e4be', '#c9ac70'], 12, 2);
    speckle(ctx, w, h, r, 60, ['rgba(255,250,230,0.4)'], 6, 20, 0.3);
  }, MAP),

  neptune: () => tex('neptune', (ctx, w, h) => {
    const r = rng(33);
    bands(ctx, w, h, r, ['#3f63d1', '#4b74e0', '#3556b8', '#5a85ea'], 10, 3);
    speckle(ctx, w, h, r, 40, ['rgba(255,255,255,0.7)'], 3, 9, 0.5, [0.25, 0.75]);
    wrapped(w, (dx) => {   // Great Dark Spot
      ctx.fillStyle = '#1f347e';
      ctx.beginPath();
      ctx.ellipse(w * 0.4 + dx, h * 0.62, 20, 11, 0, 0, Math.PI * 2);
      ctx.fill();
    });
  }, MAP),

  brownDwarf: () => tex('brownDwarf', (ctx, w, h) => {
    const r = rng(41);
    bands(ctx, w, h, r, ['#7a2b4f', '#5a1d3a', '#953a62', '#682544'], 11, 5);
    speckle(ctx, w, h, r, 180, ['rgba(200,90,140,0.5)', 'rgba(40,10,25,0.5)'], 4, 16, 0.4);
  }, MAP),

  // greyscale granulation, tinted per star by the shader
  starSurface: () => tex('starSurface', (ctx, w, h) => {
    const r = rng(51);
    ctx.fillStyle = '#ececec';
    ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 2600; i++) {   // fine granulation: subtle bright/dark convection cells
      const x = r() * w, y = r() * h, rad = 2 + r() * 4;
      wrapped(w, (dx) => blob(ctx, x + dx, y, rad, r() < 0.5 ? '#ffffff' : '#c4c4c4', 0.3));
    }
    speckle(ctx, w, h, r, 4, ['#8a8a8a'], 2.5, 4.5, 0.6, [0.35, 0.65]);   // a few small sunspots
  }, MAP),

  giantSurface: () => tex('giantSurface', (ctx, w, h) => {
    const r = rng(52);
    ctx.fillStyle = '#e6e6e6';
    ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 110; i++) {   // giant stars have a few huge convection cells
      const x = r() * w, y = r() * h, rad = 16 + r() * 36;
      wrapped(w, (dx) => blob(ctx, x + dx, y, rad, r() < 0.5 ? '#ffffff' : '#b0b0b0', 0.35));
    }
  }, MAP),
};

// ---------- sprite textures ----------
export const sprites = {
  glow: () => tex('glow', (ctx, w) => blob(ctx, w / 2, w / 2, w / 2, '#ffffff'), { w: 128 }),

  softDot: () => tex('softDot', (ctx, w) => {
    const g = ctx.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.5, 'rgba(255,255,255,0.8)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, w);
  }, { w: 32 }),

  ring: () => tex('ring', (ctx, w) => {
    const g = ctx.createRadialGradient(w / 2, w / 2, w * 0.38, w / 2, w / 2, w / 2);
    g.addColorStop(0, 'rgba(255,255,255,0)');
    g.addColorStop(0.55, 'rgba(255,255,255,1)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, w);
  }, { w: 256 }),

  grain: (seed) => tex(`grain${seed}`, (ctx, w) => {
    const r = rng(100 + seed);
    ctx.translate(w / 2, w / 2);
    ctx.beginPath();
    const n = 9;
    for (let i = 0; i <= n; i++) {
      const a = (i / n) * Math.PI * 2, rad = w * (0.3 + r() * 0.15);
      i ? ctx.lineTo(Math.cos(a) * rad, Math.sin(a) * rad) : ctx.moveTo(Math.cos(a) * rad, Math.sin(a) * rad);
    }
    const g = ctx.createRadialGradient(-w * 0.1, -w * 0.1, 0, 0, 0, w * 0.45);
    g.addColorStop(0, '#fff3dd');
    g.addColorStop(1, '#8c7a62');
    ctx.fillStyle = g;
    ctx.fill();
  }, { w: 32 }),

  asteroid: (seed) => tex(`asteroid${seed}`, (ctx, w) => {
    const r = rng(200 + seed);
    ctx.translate(w / 2, w / 2);
    const pts = [];
    const n = 22;
    let rad = w * 0.4;
    for (let i = 0; i < n; i++) {
      rad = Math.min(w * 0.48, Math.max(w * 0.3, rad + (r() - 0.5) * w * 0.07));
      const a = (i / n) * Math.PI * 2;
      pts.push([Math.cos(a) * rad, Math.sin(a) * rad * (0.82 + seed * 0.04)]);
    }
    ctx.beginPath();
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
    ctx.fillStyle = ['#8d8174', '#7b7068', '#9a8a77'][seed % 3];
    ctx.fill();
    ctx.save();
    ctx.clip();
    for (let i = 0; i < 14; i++) {
      const x = (r() - 0.5) * w * 0.6, y = (r() - 0.5) * w * 0.6, cr = w * (0.02 + r() * 0.07);
      ctx.fillStyle = 'rgba(55,48,42,0.55)';
      ctx.beginPath();
      ctx.arc(x, y, cr, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(230,220,200,0.35)';
      ctx.lineWidth = cr * 0.3;
      ctx.beginPath();
      ctx.arc(x + cr * 0.2, y + cr * 0.2, cr, Math.PI * 0.1, Math.PI * 0.9);
      ctx.stroke();
    }
    ctx.restore();
  }, { w: 256 }),

  // shading that stays fixed while the rock spins under it, for a 3D look
  rockShade: () => tex('rockShade', (ctx, w) => {
    const g = ctx.createRadialGradient(w * 0.35, w * 0.32, w * 0.05, w * 0.5, w * 0.5, w * 0.55);
    g.addColorStop(0, 'rgba(255,250,240,0.35)');
    g.addColorStop(0.55, 'rgba(0,0,0,0)');
    g.addColorStop(1, 'rgba(0,0,0,0.65)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, w);
  }, { w: 256 }),

  // Saturn-style rings, split into the half behind the planet and the half in front
  rings: (half) => tex(`rings-${half}`, (ctx, w, h) => {
    ctx.translate(w / 2, h / 2);
    ctx.save();
    ctx.beginPath();
    if (half === 'back') ctx.rect(-w / 2, -h / 2, w, h / 2);
    else ctx.rect(-w / 2, 0, w, h / 2);
    ctx.clip();
    const bandsR = [[0.62, 'rgba(210,190,150,0.55)'], [0.7, 'rgba(235,220,180,0.9)'], [0.78, 'rgba(200,180,140,0.75)'],
      [0.83, 'rgba(0,0,0,0)'], [0.87, 'rgba(225,210,170,0.7)'], [0.95, 'rgba(190,170,130,0.5)']];
    for (let i = bandsR.length - 1; i >= 0; i--) {
      const [rr, col] = bandsR[i];
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.ellipse(0, 0, (w / 2) * rr, (h / 2) * rr, 0, 0, Math.PI * 2);
      ctx.ellipse(0, 0, (w / 2) * (rr - 0.07), (h / 2) * (rr - 0.07), 0, 0, Math.PI * 2, true);
      ctx.fill('evenodd');
    }
    ctx.restore();
  }, { w: 512, h: 160 }),

  accretionDisk: (hot) => tex(`disk${hot ? 'hot' : ''}`, (ctx, w) => {
    const r = rng(hot ? 61 : 60);
    const c = w / 2;
    const g = ctx.createRadialGradient(c, c, w * 0.12, c, c, c);
    const stops = hot
      ? [[0, 'rgba(255,255,255,1)'], [0.25, 'rgba(190,220,255,0.95)'], [0.55, 'rgba(140,110,255,0.6)'], [1, 'rgba(60,20,120,0)']]
      : [[0, 'rgba(255,250,230,1)'], [0.25, 'rgba(255,200,110,0.95)'], [0.6, 'rgba(230,100,40,0.55)'], [1, 'rgba(120,30,10,0)']];
    stops.forEach(([o, col]) => g.addColorStop(o, col));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(c, c, c, 0, Math.PI * 2);
    ctx.fill();
    // spiral streaks so the rotation is visible
    ctx.globalCompositeOperation = 'destination-out';
    for (let i = 0; i < 70; i++) {
      const a0 = r() * Math.PI * 2, rad = w * (0.15 + r() * 0.33);
      ctx.strokeStyle = `rgba(0,0,0,${0.15 + r() * 0.35})`;
      ctx.lineWidth = 1 + r() * 4;
      ctx.beginPath();
      ctx.arc(c, c, rad, a0, a0 + 0.6 + r() * 1.2);
      ctx.stroke();
    }
    ctx.globalCompositeOperation = 'source-over';
    // hollow centre (the black hole sits there)
    ctx.globalCompositeOperation = 'destination-out';
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.arc(c, c, w * 0.13, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
  }, { w: 512 }),

  beam: () => tex('beam', (ctx, w, h) => {
    // a cone from the bottom-centre upward (pulsar beams, quasar jets)
    const g = ctx.createLinearGradient(0, h, 0, 0);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.5, 'rgba(255,255,255,0.45)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(w / 2, h);
    ctx.lineTo(0, 0);
    ctx.lineTo(w, 0);
    ctx.closePath();
    ctx.fill();
    // soften the edges
    const s = ctx.createLinearGradient(0, 0, w, 0);
    s.addColorStop(0, 'rgba(0,0,0,1)');
    s.addColorStop(0.4, 'rgba(0,0,0,0)');
    s.addColorStop(0.6, 'rgba(0,0,0,0)');
    s.addColorStop(1, 'rgba(0,0,0,1)');
    ctx.globalCompositeOperation = 'destination-out';
    ctx.fillStyle = s;
    ctx.fillRect(0, 0, w, h);
  }, { w: 64, h: 256 }),

  spiral: (layer) => tex(`spiral${layer}`, (ctx, w) => {
    const r = rng(70 + layer);
    const c = w / 2;
    if (layer === 0) {
      blob(ctx, c, c, w * 0.5, 'rgba(120,110,200,0.35)');
    }
    const arms = 2;
    const n = layer === 0 ? 2600 : 900;
    for (let i = 0; i < n; i++) {
      const arm = i % arms;
      const t = Math.pow(r(), 0.8);                       // distance along the arm
      const theta = t * 3.4 * Math.PI + arm * Math.PI;    // log-spiral-ish winding
      const rad = c * (0.08 + 0.88 * t);
      const spread = (r() - 0.5) * c * (0.06 + 0.22 * t);
      const x = c + Math.cos(theta) * rad + Math.cos(theta + Math.PI / 2) * spread;
      const y = c + Math.sin(theta) * rad + Math.sin(theta + Math.PI / 2) * spread;
      const colors = layer === 0 ? ['#cfe0ff', '#ffffff', '#9fb8ff', '#ffd9f0'] : ['#ffffff', '#ffb3e6', '#b3d1ff'];
      const size = layer === 0 ? 0.6 + r() * 1.3 : 1 + r() * 2.2;
      ctx.globalAlpha = 0.35 + r() * 0.65;
      ctx.fillStyle = colors[Math.floor(r() * colors.length)];
      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    if (layer === 0) {   // glowing bulge
      blob(ctx, c, c, w * 0.17, 'rgba(255,236,190,1)');
      blob(ctx, c, c, w * 0.08, 'rgba(255,255,240,1)');
    }
  }, { w: 512 }),
};
