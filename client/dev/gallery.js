// Dev page: every body (with variants) animated over the lensed background.
import { Application, Container, Text } from 'https://cdn.jsdelivr.net/npm/pixi.js@8.21.0/dist/pixi.min.mjs';
import { LensBackground } from '../js/background.js';
import { Effects } from '../js/effects.js';
import { LEVELS, loadLadder } from '../js/levels.js';
import { createBody } from '../js/objects/bodies.js';

await loadLadder();
const params = new URLSearchParams(location.search);
const app = new Application();
await app.init({ resizeTo: window, background: 0x0b1026, antialias: true, autoDensity: true, resolution: window.devicePixelRatio || 1 });
document.body.appendChild(app.canvas);

const LENS_K = [0, 0, 0.16, 0.22, 0.3, 0.34, 0.42, 0.4, 0.75, 1.2, 1.3, 0.95];
// level index + variant seed for each tile
const tiles = [[0, 0], [1, 0], [1, 1], [2, 0], [2, 1], [3, 0], [3, 1], [3, 2], [4, 0], [4, 1], [4, 2],
               [5, 0], [6, 0], [6, 1], [7, 0], [8, 0], [9, 0], [10, 0], [11, 0]];
const bg = new LensBackground();
const world = new Container();
const below = new Container(), above = new Container();
app.stage.addChild(bg.view, below, world, above);
const fx = new Effects(below, above);

const cols = 7;
const items = tiles.map(([lvl, seed], i) => {
  const body = createBody(LEVELS[lvl].key, seed);
  const label = new Text({ text: LEVELS[lvl].name, style: { fontFamily: 'Trebuchet MS', fontSize: 14, fill: 0xffffff } });
  label.anchor.set(0.5, 0);
  world.addChild(body.view, label);
  return { body, label, lvl, seed, i, frac: lvl === 6 ? [0.05, 0.95][seed] : 0.5 };
});

let t = 0;
app.ticker.add((tk) => {
  const dt = tk.deltaMS / 1000;
  t += dt;
  const w = app.screen.width, h = app.screen.height;
  const cw = w / cols, rows = Math.ceil(items.length / cols), ch = h / rows;
  const lenses = [];
  for (const it of items) {
    const x = cw * (it.i % cols + 0.5), y = ch * (Math.floor(it.i / cols) + 0.45);
    const r = Math.min(cw, ch) * 0.26;
    it.body.view.position.set(x, y);
    it.body.view.scale.set(r / Math.max(1, it.body.extent * 0.75));
    it.body.update(dt, { frac: it.frac, px: it.body.view.scale.x });
    it.label.position.set(x, y + Math.min(cw, ch) * 0.38);
    if (params.get('boost')) fx.boost(x, y, r, 1, 0, it.lvl, dt);
    if (LENS_K[it.lvl]) lenses.push({ x, y, e: LENS_K[it.lvl] * r });
    if (params.get('fx') && Math.floor(t * 0.5) !== Math.floor((t - dt) * 0.5) && it.lvl === 8) {
      const kind = params.get('fx');
      kind === 'supernova' ? fx.supernova(x, y, r) : kind === 'collapse' ? fx.collapse(x, y, r) : fx.levelUp(x, y, r, 0xffffff);
    }
  }
  bg.update(w, h, w / 2, h / 2, 1, t, lenses);
  fx.update(dt);
});
