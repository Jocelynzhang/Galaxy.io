// One animated look per ladder level. Every body is built at radius 1; the renderer scales
// `body.view` to the object's radius. `extent` is how far the art reaches beyond radius 1
// (rings, jets), used to fit HUD icons.
import { Container, Graphics, Sprite } from 'https://cdn.jsdelivr.net/npm/pixi.js@8.21.0/dist/pixi.min.mjs';
import { rng, sprites, surfaces } from './art.js';
import { makeSphere } from './sphere.js';

function sprite(texture, size, { tint = 0xffffff, alpha = 1, add = false, anchor = [0.5, 0.5] } = {}) {
  const s = new Sprite(texture);
  s.anchor.set(anchor[0], anchor[1]);
  s.width = size;
  s.height = size * (texture.height / texture.width);
  s.tint = tint;
  s.alpha = alpha;
  if (add) s.blendMode = 'add';
  return s;
}

function lerpColor(stops, t) {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < stops.length; i++) {
    const [t1, c1] = stops[i];
    const [t0, c0] = stops[i - 1];
    if (t <= t1) {
      const k = (t - t0) / (t1 - t0);
      return c0.map((v, j) => v + (c1[j] - v) * k);
    }
  }
  return stops[stops.length - 1][1];
}

const rgbHex = ([r, g, b]) => (Math.round(r * 255) << 16) | (Math.round(g * 255) << 8) | Math.round(b * 255);

// Real stars: small ones are red, the Sun is yellow-white, heavy ones are blue.
const STAR_COLORS = [[0, [1.0, 0.5, 0.32]], [0.35, [1.0, 0.82, 0.5]], [0.6, [1.0, 0.96, 0.86]], [1, [0.7, 0.82, 1.0]]];

class Body {
  constructor() {
    this.view = new Container();
    this.extent = 1;
    this.t = 0;
  }

  // o = { frac: progress through the level 0..1, boosting, px: radius in screen pixels }
  update(dt, o) {
    this.t += dt;
  }

  destroy() {
    this.view.destroy({ children: true });
  }
}

class Dust extends Body {
  constructor(seed) {
    super();
    const r = rng(seed);
    this.view.addChild(sprite(sprites.glow(), 2.6, { tint: 0xd8c6a8, alpha: 0.35 }));
    this.grains = [];
    const tints = [0xffffff, 0xe8d8c0, 0xc8b8a0, 0xf0e0d0];
    // a swirling cloud: a few bigger grains and lots of tiny glinting specks
    for (let i = 0; i < 40; i++) {
      const big = i < 12;
      const g = big
        ? sprite(sprites.grain(i % 4), 0.14 + r() * 0.2, { tint: tints[i % 4] })
        : sprite(sprites.softDot(), 0.05 + r() * 0.08, { tint: 0xfff4e0, alpha: 0.5 + r() * 0.5 });
      g.orbit = { a: (big ? 0.05 : 0.15) + r() * 0.7, phase: r() * Math.PI * 2, speed: (0.3 + r() * 0.9) * (r() < 0.7 ? 1 : -1), wob: r() * 3 };
      this.grains.push(g);
      this.view.addChild(g);
    }
  }

  update(dt, o) {
    super.update(dt, o);
    for (const g of this.grains) {
      const { a, phase, speed, wob } = g.orbit;
      const ang = phase + this.t * speed;
      const rad = a * (0.85 + 0.15 * Math.sin(this.t * 1.3 + wob));
      g.position.set(Math.cos(ang) * rad, Math.sin(ang) * rad);
      g.rotation += dt * speed * 2;
    }
  }
}

class Asteroid extends Body {
  constructor(seed) {
    super();
    const t = sprites.asteroid(seed % 3);
    this.rock = sprite(t, 2.15);
    // light comes from a fixed direction while the rock spins; clip the shading to the rock
    this.shapeMask = sprite(t, 2.15);
    const shade = sprite(sprites.rockShade(), 2.15);
    shade.mask = this.shapeMask;
    this.spin = (0.25 + (seed % 5) * 0.06) * (seed % 2 ? 1 : -1);
    this.view.addChild(this.rock, this.shapeMask, shade);
  }

  update(dt, o) {
    super.update(dt, o);
    this.rock.rotation += dt * this.spin;
    this.shapeMask.rotation = this.rock.rotation;
  }
}

class Globe extends Body {
  // layers: [{ texture, opts, speed, scale }]
  constructor(layers, { glow = null, spin = 0.3 } = {}) {
    super();
    if (glow) this.view.addChild(sprite(sprites.glow(), glow.size, { tint: glow.tint, alpha: glow.alpha, add: glow.add }));
    this.glowSprite = glow ? this.view.children[0] : null;
    if (this.glowSprite) this.glowSprite.baseScale = this.glowSprite.scale.x;
    this.spheres = layers.map(({ texture, opts, speed = 1, scale = 1 }) => {
      const m = makeSphere(texture, opts);
      m.scale.set(scale);
      m.speed = speed * spin;
      this.view.addChild(m);
      return m;
    });
  }

  update(dt, o) {
    super.update(dt, o);
    const aa = Math.min(0.2, 1.5 / Math.max(1, o.px ?? 50));   // ~1.5 px soft edge
    for (const m of this.spheres) {
      m.sphere.uRot += dt * m.speed;
      m.sphere.uAA = aa;
    }
  }
}

class RingedGiant extends Globe {
  constructor() {
    const rings = new Container();
    super([{ texture: surfaces.saturn(), opts: { atmo: [1, 0.95, 0.8, 0.35], tilt: 0.35 } }], { spin: 0.35 });
    this.extent = 2.15;
    const back = sprite(sprites.rings('back'), 4.3);
    const front = sprite(sprites.rings('front'), 4.3);
    // back half of the rings behind the planet, front half in front
    rings.addChild(back);
    this.view.addChildAt(rings, 0);
    const frontC = new Container();
    frontC.addChild(front);
    this.view.addChild(frontC);
    rings.rotation = frontC.rotation = -0.32;
  }
}

class Star extends Globe {
  constructor() {
    super([{ texture: surfaces.starSurface(), opts: { emissive: 1, atmo: [1, 1, 0.85, 0.9], tilt: 0.1 } }],
      { glow: { size: 4.2, tint: 0xffe08a, alpha: 0.6, add: true }, spin: 0.08 });
    this.inner = sprite(sprites.glow(), 2.5, { tint: 0xffffff, alpha: 0.75, add: true });
    this.view.addChildAt(this.inner, 1);
    this.extent = 1.6;
  }

  update(dt, o) {
    super.update(dt, o);
    const c = lerpColor(STAR_COLORS, o.frac ?? 0.4);
    this.spheres[0].sphere.uTint.set(c);
    this.glowSprite.tint = rgbHex(c);
    this.inner.tint = rgbHex(c.map((v) => 0.5 + 0.5 * v));
    this.glowSprite.scale.set(this.glowSprite.baseScale * (1 + 0.05 * Math.sin(this.t * 2.2)));
  }
}

class Giant extends Globe {
  constructor() {
    super([{ texture: surfaces.giantSurface(), opts: { emissive: 1, tint: [1.0, 0.7, 0.45], atmo: [1, 0.6, 0.35, 1.0], tilt: 0.1 } }],
      { glow: { size: 4.2, tint: 0xff7a45, alpha: 0.8, add: true }, spin: 0.05 });
    this.view.addChildAt(sprite(sprites.glow(), 2.7, { tint: 0xffc090, alpha: 0.85, add: true }), 1);
    this.extent = 1.7;
  }

  update(dt, o) {
    super.update(dt, o);
    // giants gently pulsate
    this.spheres[0].scale.set(1 + 0.03 * Math.sin(this.t * 1.1));
  }
}

class NeutronStar extends Body {
  constructor() {
    super();
    this.extent = 1.6;
    this.beams = new Container();
    for (const rot of [0, Math.PI]) {
      const b = sprite(sprites.beam(), 0.5, { tint: 0xbfe6ff, alpha: 0.9, add: true, anchor: [0.5, 1] });
      b.height = 1.6;
      b.rotation = rot;
      this.beams.addChild(b);
    }
    this.halo = sprite(sprites.glow(), 2.2, { tint: 0x9fd8ff, alpha: 0.6, add: true });
    this.core = sprite(sprites.softDot(), 0.62, { tint: 0xffffff, add: true });
    this.view.addChild(this.halo, this.beams, this.core);
  }

  update(dt, o) {
    super.update(dt, o);
    this.beams.rotation += dt * 4.0;                       // pulsar: a spinning lighthouse
    const flash = 0.75 + 0.25 * Math.max(0, Math.cos(this.beams.rotation * 2));
    this.halo.alpha = 0.45 + 0.25 * flash;
  }
}

class BlackHole extends Body {
  constructor(hot) {
    super();
    this.extent = hot ? 2.7 : 1.35;
    const tilt = 0.34;
    const glow = sprite(sprites.glow(), hot ? 3.2 : 2.6, { tint: hot ? 0x9f7bff : 0x7a4cff, alpha: hot ? 0.55 : 0.3, add: true });
    this.view.addChild(glow);
    if (hot) {
      this.jets = [0, Math.PI].map((rot) => {
        const j = sprite(sprites.beam(), 0.55, { tint: 0xc8deff, alpha: 1, add: true, anchor: [0.5, 1] });
        j.height = 3.0;
        j.rotation = rot + 0.18;
        this.view.addChild(j);
        return j;
      });
    }
    const diskTex = sprites.accretionDisk(hot);
    const back = new Container();
    back.scale.y = tilt;
    this.diskBack = sprite(diskTex, 2.7);
    back.addChild(this.diskBack);
    const core = new Graphics().circle(0, 0, 0.32).fill(0x000000);
    const photonRing = sprite(sprites.ring(), 0.9, { tint: hot ? 0xe0eaff : 0xffd9a0, alpha: 0.95, add: true });
    const front = new Container();
    front.scale.y = tilt;
    this.diskFront = sprite(diskTex, 2.7);
    const mask = new Graphics().rect(-1.5, 0.05, 3, 1.5).fill(0xffffff);
    front.addChild(this.diskFront, mask);
    this.diskFront.mask = mask;
    this.view.addChild(back, core, photonRing, front);
    if (hot) this.view.addChild(this.coreGlow = sprite(sprites.glow(), 1.1, { tint: 0xffffff, alpha: 0.9, add: true }));
    this.spin = hot ? 1.3 : 0.8;
  }

  update(dt, o) {
    super.update(dt, o);
    this.diskBack.rotation += dt * this.spin;
    this.diskFront.rotation = this.diskBack.rotation;
    if (this.jets) {
      const f = 0.8 + 0.2 * Math.sin(this.t * 17) * Math.sin(this.t * 7.3);
      for (const j of this.jets) j.alpha = 0.75 * f + 0.25;
      this.coreGlow.alpha = 0.75 + 0.2 * f;
    }
  }
}

class Galaxy extends Body {
  constructor(seed) {
    super();
    this.extent = 1.25;
    this.view.addChild(sprite(sprites.glow(), 2.6, { tint: 0x8f7bff, alpha: 0.3, add: true }));
    this.disk = new Container();
    this.disk.scale.y = 0.8;          // seen slightly from the side
    this.arms = sprite(sprites.spiral(0), 2.4, { add: true });
    this.bright = sprite(sprites.spiral(1), 2.4, { add: true, alpha: 0.9 });
    this.disk.addChild(this.arms, this.bright);
    this.disk.rotation = (seed % 7) * 0.4;
    this.view.addChild(this.disk);
  }

  update(dt, o) {
    super.update(dt, o);
    this.arms.rotation -= dt * 0.12;
    this.bright.rotation -= dt * 0.15;
  }
}

const pick = (seed, list) => list[Math.abs(seed) % list.length];

export function createBody(key, seed = 0) {
  switch (key) {
    case 'dust': return new Dust(seed);
    case 'asteroid': return new Asteroid(seed);
    case 'dwarf_planet': return new Globe([{ texture: pick(seed, [surfaces.pluto, surfaces.ceres])(), opts: { atmo: [0.7, 0.8, 1, 0.12] } }], { spin: 0.3 });
    case 'terrestrial': {
      const kind = pick(seed, ['earth', 'mars', 'venus']);
      if (kind === 'earth') {
        return new Globe([
          { texture: surfaces.earth(), opts: { atmo: [0.45, 0.7, 1, 0.9] } },
          { texture: surfaces.earthClouds(), opts: { atmo: [0, 0, 0, 0] }, speed: 1.3, scale: 1.015 },
        ], { glow: { size: 2.5, tint: 0x6aa8ff, alpha: 0.3 }, spin: 0.35 });
      }
      if (kind === 'mars') return new Globe([{ texture: surfaces.mars(), opts: { atmo: [1, 0.6, 0.4, 0.3] } }], { spin: 0.35 });
      return new Globe([{ texture: surfaces.venus(), opts: { atmo: [1, 0.9, 0.6, 0.7] } }], { spin: 0.15 });
    }
    case 'gas_giant': {
      const kind = pick(seed, ['jupiter', 'saturn', 'neptune']);
      if (kind === 'saturn') return new RingedGiant();
      if (kind === 'jupiter') return new Globe([{ texture: surfaces.jupiter(), opts: { atmo: [1, 0.9, 0.75, 0.35], tilt: 0.12 } }], { spin: 0.45 });
      return new Globe([{ texture: surfaces.neptune(), opts: { atmo: [0.5, 0.7, 1, 0.8], tilt: 0.2 } }], { glow: { size: 2.4, tint: 0x5a85ea, alpha: 0.25 }, spin: 0.4 });
    }
    case 'brown_dwarf':
      return new Globe([{ texture: surfaces.brownDwarf(), opts: { emissive: 1, atmo: [0.9, 0.3, 0.6, 0.6], tint: [0.85, 0.75, 0.8], tilt: 0.15 } }],
        { glow: { size: 2.8, tint: 0xb0507a, alpha: 0.35, add: true }, spin: 0.4 });
    case 'main_sequence': return new Star();
    case 'giant': return new Giant();
    case 'neutron_star': return new NeutronStar();
    case 'black_hole': return new BlackHole(false);
    case 'quasar': return new BlackHole(true);
    case 'galaxy': return new Galaxy(seed);
    default: return new Dust(seed);
  }
}
