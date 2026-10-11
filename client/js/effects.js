// Client-only eye candy in world coordinates: boost exhaust, level-up sparkles, supernova.
// Purely visual; the server's ejected pellets are the real (edible) exhaust.
import { Container, Sprite } from 'https://cdn.jsdelivr.net/npm/pixi.js@8.21.0/dist/pixi.min.mjs';
import { sprites } from './objects/art.js';

const MAX_PARTICLES = 700;

// exhaust colours per level: rock chips -> gas -> plasma
const EXHAUST = [
  [0xc9b79c, 0x8c7a62], [0x9e8f80, 0x6f655c], [0xd9c2a7, 0xa58b70], [0x9fd0ff, 0xffffff],
  [0xf0c89a, 0xffe7c4], [0xd16a9a, 0xff9fd0], [0xffd34d, 0xfff1b0], [0xff8a50, 0xffd0a0],
  [0xbfe6ff, 0xffffff], [0xb48cff, 0xffd9a0], [0xc0d8ff, 0xffffff], [0xd6b8ff, 0xffffff],
];

export class Effects {
  constructor(below, above) {
    this.below = below;     // under the objects (exhaust)
    this.above = above;     // over the objects (explosions)
    this.live = [];
    this.pool = [];
    this.rings = [];
  }

  _particle(layer) {
    let s = this.pool.pop();
    if (!s) {
      s = new Sprite(sprites.softDot());
      s.anchor.set(0.5);
    }
    layer.addChild(s);
    return s;
  }

  spawn(layer, x, y, vx, vy, life, size, tint, { add = false, grow = 0, alpha = 1 } = {}) {
    if (this.live.length >= MAX_PARTICLES) return;
    const s = this._particle(layer);
    s.position.set(x, y);
    s.tint = tint;
    s.blendMode = add ? 'add' : 'normal';
    s.alpha = alpha;
    s.width = s.height = size;
    this.live.push({ s, vx, vy, life, age: 0, size, grow, alpha });
  }

  // Exhaust streaming out the back of a boosting object. dir = unit heading.
  boost(x, y, r, dirX, dirY, level, dt) {
    const [c1, c2] = EXHAUST[level] ?? EXHAUST[0];
    const n = Math.min(6, Math.ceil(dt * 70));
    const hot = level >= 6;
    for (let i = 0; i < n; i++) {
      const spread = (Math.random() - 0.5) * 0.9;
      const px = -dirY, py = dirX;
      const bx = x - dirX * r * 0.85 + px * spread * r * 0.7;
      const by = y - dirY * r * 0.85 + py * spread * r * 0.7;
      const speed = r * (1.2 + Math.random() * 1.2);
      this.spawn(this.below, bx, by,
        -dirX * speed + px * spread * speed * 0.4, -dirY * speed + py * spread * speed * 0.4,
        0.35 + Math.random() * 0.35, r * (0.12 + Math.random() * 0.14), Math.random() < 0.5 ? c1 : c2,
        { add: hot, grow: hot ? 1.2 : -0.6, alpha: 0.9 });
    }
  }

  // An expanding glowing ring.
  ring(x, y, r0, r1, duration, tint, layer = this.above, alpha = 0.9) {
    const s = new Sprite(sprites.ring());
    s.anchor.set(0.5);
    s.position.set(x, y);
    s.tint = tint;
    s.blendMode = 'add';
    layer.addChild(s);
    this.rings.push({ s, r0, r1, duration, age: 0, alpha });
  }

  levelUp(x, y, r, tint) {
    this.ring(x, y, r * 0.9, r * 2.2, 0.7, tint);
    for (let i = 0; i < 24; i++) {
      const a = (i / 24) * Math.PI * 2;
      const v = r * (1.5 + Math.random());
      this.spawn(this.above, x + Math.cos(a) * r, y + Math.sin(a) * r, Math.cos(a) * v, Math.sin(a) * v,
        0.6, r * 0.12, 0xffffff, { add: true, grow: -0.8 });
    }
  }

  // Giant star -> neutron star: blinding flash, expanding shell, flying debris.
  supernova(x, y, r) {
    this.ring(x, y, r * 0.5, r * 3.5, 0.6, 0xffffff, this.above, 1);
    this.ring(x, y, r, r * 7, 1.6, 0xffa860);
    this.ring(x, y, r, r * 5, 2.2, 0xff5aa0, this.above, 0.6);
    for (let i = 0; i < 140; i++) {
      const a = Math.random() * Math.PI * 2;
      const v = r * (1 + Math.random() * 4);
      const tint = [0xffffff, 0xffd27a, 0xff8a50, 0xff5aa0][i % 4];
      this.spawn(this.above, x, y, Math.cos(a) * v, Math.sin(a) * v, 1 + Math.random() * 1.2, r * (0.08 + Math.random() * 0.18), tint, { add: true, grow: 0.5 });
    }
  }

  // Neutron star -> black hole: light falling inward.
  collapse(x, y, r) {
    this.ring(x, y, r * 3, r * 0.3, 0.9, 0xb48cff);
    this.ring(x, y, r * 2, r * 0.2, 0.7, 0xffffff, this.above, 0.6);
  }

  update(dt) {
    for (let i = this.live.length - 1; i >= 0; i--) {
      const p = this.live[i];
      p.age += dt;
      if (p.age >= p.life) {
        p.s.removeFromParent();
        this.pool.push(p.s);
        this.live[i] = this.live[this.live.length - 1];
        this.live.pop();
        continue;
      }
      const k = p.age / p.life;
      p.s.x += p.vx * dt;
      p.s.y += p.vy * dt;
      p.vx *= 1 - 1.5 * dt;
      p.vy *= 1 - 1.5 * dt;
      p.s.width = p.s.height = Math.max(0.01, p.size * (1 + p.grow * k));
      p.s.alpha = p.alpha * (1 - k);
    }
    for (let i = this.rings.length - 1; i >= 0; i--) {
      const g = this.rings[i];
      g.age += dt;
      const k = g.age / g.duration;
      if (k >= 1) {
        g.s.destroy();
        this.rings.splice(i, 1);
        continue;
      }
      const ease = 1 - (1 - k) * (1 - k);
      const rad = g.r0 + (g.r1 - g.r0) * ease;
      g.s.width = g.s.height = rad * 2;
      g.s.alpha = g.alpha * (1 - k);
    }
  }
}
