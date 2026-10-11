import { Application, Container, Graphics, Sprite, Text } from 'https://cdn.jsdelivr.net/npm/pixi.js@8.21.0/dist/pixi.min.mjs';
import { LEVELS, foodColor } from './levels.js';

const GRID = 100;            // world units between grid lines
const BG = 0x0b1026;
const NAME_FONT = 36;

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

    this.grid = new Graphics();
    this.world = new Container();
    this.foodLayer = new Container();
    this.playerLayer = new Container();
    this.playerLayer.sortableChildren = true;
    this.bounds = new Graphics()
      .rect(0, 0, world[0], world[1])
      .stroke({ width: 6, color: 0xff6b8b, alpha: 0.6 });
    this.world.addChild(this.bounds, this.foodLayer, this.playerLayer);
    this.app.stage.addChild(this.grid, this.world);

    this.circleTex = this.app.renderer.generateTexture(
      new Graphics().circle(0, 0, 128).fill(0xffffff).circle(0, 0, 128).stroke({ width: 10, color: 0xb8b8b8 }),
    );
    this.dotTex = this.app.renderer.generateTexture(new Graphics().circle(0, 0, 16).fill(0xffffff));

    this.food = new Map();     // id -> Sprite (with .tx/.ty target position)
    this.movingFood = new Set();
    this.players = new Map();  // id -> { node, body, label, lvl, name }
    this.foodR = 4;
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
        s = new Sprite(this.dotTex);
        s.anchor.set(0.5);
        s.tint = foodColor(c);
        s.position.set(x, y);
        this.foodLayer.addChild(s);
        this.food.set(id, s);
      } else {
        this.movingFood.add(s);   // known pellet moved: glide there instead of jumping
      }
      s.width = s.height = r * 2;
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

  draw(view) {
    const { w, h } = this.size;
    const z = view.zoom;
    const cx = view.me.x, cy = view.me.y;
    this.world.scale.set(z);
    this.world.position.set(w / 2 - cx * z, h / 2 - cy * z);
    this.drawGrid(cx, cy, z, w, h);
    this.drawPlayers(view, z);
  }

  drawGrid(cx, cy, z, w, h) {
    const g = this.grid.clear();
    const step = GRID * z;
    const ox = (w / 2 - cx * z) % step;
    const oy = (h / 2 - cy * z) % step;
    for (let x = ox < 0 ? ox + step : ox; x < w; x += step) g.moveTo(x, 0).lineTo(x, h);
    for (let y = oy < 0 ? oy + step : oy; y < h; y += step) g.moveTo(0, y).lineTo(w, y);
    g.stroke({ width: 1, color: 0x9fb2ff, alpha: 0.13 });
  }

  drawPlayers(view, z) {
    const seen = new Set();
    for (const p of view.players) {
      seen.add(p.id);
      let e = this.players.get(p.id);
      if (!e) {
        const node = new Container();
        const body = new Sprite(this.circleTex);
        body.anchor.set(0.5);
        const label = new Text({
          text: '',
          style: { fontFamily: 'Trebuchet MS', fontSize: NAME_FONT, fontWeight: 'bold', fill: 0xffffff,
                   stroke: { color: 0x000000, width: 6 } },
        });
        label.anchor.set(0.5);
        node.addChild(body, label);
        this.playerLayer.addChild(node);
        e = { node, body, label, lvl: -1, name: null };
        this.players.set(p.id, e);
      }
      if (e.lvl !== p.lvl) { e.body.tint = LEVELS[p.lvl].color; e.lvl = p.lvl; }
      const name = p.bot ? `${p.name} [bot]` : p.name;
      if (e.name !== name) { e.label.text = name; e.name = name; }
      e.node.position.set(p.x, p.y);
      e.node.zIndex = p.r;
      e.body.width = e.body.height = p.r * 2;
      // keep names readable on screen regardless of zoom
      const screenPx = Math.min(30, Math.max(12, p.r * z * 0.45));
      e.label.scale.set(screenPx / z / NAME_FONT);
      e.body.alpha = p.id === view.me.id ? 1 : 0.92;
    }
    for (const [id, e] of this.players) {
      if (!seen.has(id)) { e.node.destroy({ children: true }); this.players.delete(id); }
    }
  }
}
