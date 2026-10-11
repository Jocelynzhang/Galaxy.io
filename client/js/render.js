import { Application, Container, Graphics, Sprite, Text } from 'https://cdn.jsdelivr.net/npm/pixi.js@8.21.0/dist/pixi.min.mjs';
import { LensBackground } from './background.js';
import { Effects } from './effects.js';
import { LEVELS, foodColor, levelSpan } from './levels.js';
import { sprites } from './objects/art.js';
import { createBody } from './objects/bodies.js';

const BG = 0x0b1026;
const NAME_FONT = 36;
// Einstein radius as a fraction of the object's radius, per level. Deliberately exaggerated
// (real planets bend light imperceptibly) but ordered by how compact and heavy each object is:
// subtle for planets, strong for neutron stars, dramatic rings around black holes and quasars.
const LENS_K = [0, 0, 0.16, 0.22, 0.3, 0.34, 0.42, 0.4, 0.75, 1.2, 1.3, 0.95];

export class Renderer {
  async init(el, world) {
    this.worldSize = world;
    this.app = new Application();
    await this.app.init({
      resizeTo: window,
      background: BG,
      antialias: true,
      autoDensity: true,
      resolution: window.devicePixelRatio || 1,
    });
    el.appendChild(this.app.canvas);

    this.background = new LensBackground();
    this.world = new Container();
    this.foodLayer = new Container();
    this.fxBelow = new Container();
    this.playerLayer = new Container();
    this.playerLayer.sortableChildren = true;
    this.fxAbove = new Container();
    this.labelLayer = new Container();
    this.bounds = new Graphics()
      .rect(0, 0, world[0], world[1])
      .stroke({ width: 6, color: 0xff6b8b, alpha: 0.6 });
    this.world.addChild(this.bounds, this.foodLayer, this.fxBelow, this.playerLayer, this.fxAbove, this.labelLayer);
    this.app.stage.addChild(this.background.view, this.world);

    this.effects = new Effects(this.fxBelow, this.fxAbove);
    this.food = new Map();     // id -> Sprite (with .tx/.ty target position)
    this.movingFood = new Set();
    this.players = new Map();  // id -> entry
    this.foodR = 4;
    this.time = 0;
  }

  get size() {
    return { w: this.app.screen.width, h: this.app.screen.height };
  }

  applyFood({ add, remove }) {
    for (const id of remove) {
      const s = this.food.get(id);
      if (s) { s.destroy(); this.food.delete(id); this.movingFood.delete(s); }
    }
    for (const [id, x, y, c, r] of add) {
      let s = this.food.get(id);
      if (!s) {
        s = new Sprite(sprites.softDot());
        s.anchor.set(0.5);
        s.tint = foodColor(c);
        s.position.set(x, y);
        this.foodLayer.addChild(s);
        this.food.set(id, s);
      } else {
        this.movingFood.add(s);   // known pellet moved: glide there instead of jumping
      }
      s.width = s.height = r * 2.6;   // soft dot: a little larger than the hit radius
      s.tx = x;
      s.ty = y;
    }
  }

  // Smoothly move pellets (boost exhaust, food pulled by gravity) toward their latest position.
  updateFood(dt) {
    const k = Math.min(1, dt * 14);
    for (const s of this.movingFood) {
      s.x += (s.tx - s.x) * k;
      s.y += (s.ty - s.y) * k;
      if (Math.abs(s.tx - s.x) < 0.3 && Math.abs(s.ty - s.y) < 0.3) {
        s.position.set(s.tx, s.ty);
        this.movingFood.delete(s);
      }
    }
  }

  draw(view, dt) {
    this.time += dt;
    const { w, h } = this.size;
    const z = view.zoom;
    const cx = view.me.x, cy = view.me.y;
    this.world.scale.set(z);
    this.world.position.set(w / 2 - cx * z, h / 2 - cy * z);
    const lenses = this.drawPlayers(view, z, dt);
    this.background.update(w, h, cx, cy, z, this.time,
      lenses.map((l) => ({ x: (l.x - cx) * z + w / 2, y: (l.y - cy) * z + h / 2, e: l.e * z })));
    this.effects.update(dt);
  }

  drawPlayers(view, z, dt) {
    const seen = new Set();
    const lenses = [];
    for (const p of view.players) {
      seen.add(p.id);
      let e = this.players.get(p.id);
      if (!e) {
        e = this.addEntry(p);
      } else if (e.lvl !== p.lvl) {
        this.changeLevel(e, p);
      }
      const name = p.bot ? `${p.name} [bot]` : p.name;
      if (e.name !== name) { e.label.text = name; e.name = name; }

      // heading from motion, for the exhaust direction
      const vx = (p.x - e.x) / Math.max(dt, 1e-3), vy = (p.y - e.y) / Math.max(dt, 1e-3);
      const sp = Math.hypot(vx, vy);
      if (sp > 1) { e.dx = vx / sp; e.dy = vy / sp; }
      e.x = p.x; e.y = p.y;

      e.node.position.set(p.x, p.y);
      e.node.zIndex = p.r;
      e.body.view.scale.set(p.r);
      const [lo, hi] = levelSpan(p.lvl);
      e.body.update(dt, { frac: ((p.r / 4) ** 2 - lo) / (hi - lo), boosting: p.boost, px: p.r * z });
      if (p.boost) this.effects.boost(p.x, p.y, p.r, e.dx, e.dy, p.lvl, dt);

      e.shield.visible = !!p.shield;
      if (p.shield) e.shield.scale.set(p.r * (1.2 + 0.04 * Math.sin(this.time * 8)));

      // keep names readable on screen regardless of zoom
      const screenPx = Math.min(30, Math.max(12, p.r * z * 0.4));
      e.label.scale.set(screenPx / z / NAME_FONT);
      e.label.position.set(p.x, p.y + p.r * 1.05 + 4 / z);
      e.label.alpha = p.id === view.me.id ? 1 : 0.85;

      const k = LENS_K[p.lvl] ?? 0;
      if (k > 0) lenses.push({ x: p.x, y: p.y, e: k * p.r });
    }
    for (const [id, e] of this.players) {
      if (!seen.has(id)) {
        e.body.destroy();
        e.node.destroy({ children: true });
        e.label.destroy();
        this.players.delete(id);
      }
    }
    return lenses;
  }

  addEntry(p) {
    const node = new Container();
    const shield = new Graphics().circle(0, 0, 1).stroke({ width: 0.05, color: 0x9fe8ff, alpha: 0.9 });
    const label = new Text({
      text: '',
      style: { fontFamily: 'Trebuchet MS', fontSize: NAME_FONT, fontWeight: 'bold', fill: 0xffffff,
               stroke: { color: 0x000000, width: 6 } },
    });
    label.anchor.set(0.5, 0);
    const body = createBody(LEVELS[p.lvl].key, p.id);
    node.addChild(body.view, shield);
    this.playerLayer.addChild(node);
    this.labelLayer.addChild(label);
    const e = { node, body, shield, label, lvl: p.lvl, name: null, x: p.x, y: p.y, dx: 1, dy: 0 };
    this.players.set(p.id, e);
    return e;
  }

  changeLevel(e, p) {
    const prev = e.lvl;
    e.body.destroy();
    e.body = createBody(LEVELS[p.lvl].key, p.id);
    e.node.addChildAt(e.body.view, 0);
    e.lvl = p.lvl;
    if (p.lvl > prev) {
      if (prev <= 7 && p.lvl === 8) this.effects.supernova(p.x, p.y, p.r);
      else if (prev === 8 && p.lvl === 9) this.effects.collapse(p.x, p.y, p.r);
      else this.effects.levelUp(p.x, p.y, p.r, LEVELS[p.lvl].color);
    }
  }
}
