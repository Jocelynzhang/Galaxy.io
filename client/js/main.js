import { Renderer } from './render.js';
import { State } from './state.js';
import { LEVELS, loadLadder, setStartMass } from './levels.js';
import { Hud, randomFact } from './hud.js';
import { initTouch, setBoostReady, setTouchVisible, touch } from './touch.js';

await loadLadder();

const $ = (id) => document.getElementById(id);
const joinEl = $('join'), deadEl = $('dead');
const form = $('join-form'), nameEl = $('name'), statusEl = $('join-status');
const joinButton = form.querySelector('button');

const state = new State();
const hud = new Hud();
let renderer = null;
let ws = null;
let playing = false;
let playerName = '';

// ---------- networking ----------
// The page connects straight away and spectates the leader, so the live universe is visible
// behind the name screen; "join" turns the same connection into a player.
function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/ws`;
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

// Small screens zoom out so a phone sees about as much of the universe as a desktop
// (otherwise phone players get eaten by things they can't see). 1 on screens >= 720 px.
function viewScale() {
  return Math.min(1, Math.min(window.innerWidth, window.innerHeight) / 720);
}

function viewSize() {
  const k = viewScale();
  return { vw: Math.round(window.innerWidth / k), vh: Math.round(window.innerHeight / k) };
}

function connect() {
  return new Promise((resolve, reject) => {
    ws = new WebSocket(wsUrl());
    ws.onopen = () => {
      send({ t: 'view', ...viewSize() });
      send({ t: 'spectate' });
      resolve();
    };
    ws.onerror = () => reject(new Error('Could not reach the server'));
    ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
    ws.onclose = () => {
      ws = null;
      playing = false;
      hud.show(false);
      setTouchVisible(false);
      deadEl.hidden = true;
      joinEl.hidden = false;
      statusEl.textContent = 'Disconnected from the server. Press Confirm to rejoin.';
      if (renderer) { renderer.app.destroy(true, { children: true }); renderer = null; }
      state.foodQueue = [];
      state.clearMotion();
      joinButton.disabled = false;
    };
  });
}

async function onMessage(msg) {
  switch (msg.t) {
    case 'hello':
      setStartMass(msg.startMass);
      if (!renderer) {
        renderer = new Renderer();
        await renderer.init($('stage'), msg.world);
        renderer.foodR = msg.foodR;
        renderer.ready = true;
      }
      break;
    case 'welcome':
      state.clearMotion();
      hud.reset();
      playing = true;
      joinEl.hidden = true;
      deadEl.hidden = true;
      joinButton.disabled = false;
      hud.show(true);
      setTouchVisible(true);
      break;
    case 's':
      state.push(msg);
      if (msg.lb && playing) hud.leaderboard(msg.lb, msg.rank, msg.me.id);
      break;
    case 'full':
      joinEl.hidden = false;
      joinButton.disabled = false;
      statusEl.textContent = 'The universe is full right now! Watching for a moment, then try again.';
      break;
    case 'dead':
      playing = false;
      hud.show(false);
      setTouchVisible(false);
      state.clearMotion();   // the camera switches to the leader
      $('dead-msg').textContent =
        `${msg.by} swallowed you at ${Math.round(msg.mass)} mass. ` +
        `Best level reached: ${LEVELS[msg.best].name}.`;
      $('dead-fact').textContent = randomFact(msg.best);
      deadEl.hidden = false;
      break;
  }
}

// ---------- join flow ----------
form.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  playerName = nameEl.value.trim();
  joinButton.disabled = true;
  statusEl.textContent = '';
  try {
    if (!ws) {
      statusEl.textContent = 'Connecting…';
      await connect();
    }
    send({ t: 'join', name: playerName, ...viewSize() });
    statusEl.textContent = '';
  } catch (err) {
    statusEl.textContent = err.message;
    joinButton.disabled = false;
  }
});

$('again').addEventListener('click', () => {
  send({ t: 'join', name: playerName, ...viewSize() });
});

// ---------- input ----------
// Mouse via pointer events filtered to real mice: Safari turns screen taps into fake mouse
// clicks, which would otherwise fire a boost on every tap.
const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2, boost: false };
let lastInput = 'mouse';
const isMouse = (e) => e.pointerType === 'mouse';
window.addEventListener('pointermove', (e) => { if (isMouse(e)) { mouse.x = e.clientX; mouse.y = e.clientY; lastInput = 'mouse'; } });
window.addEventListener('pointerdown', (e) => { if (isMouse(e) && e.button === 0) { mouse.boost = true; lastInput = 'mouse'; sendInput(); } });
window.addEventListener('pointerup', (e) => { if (isMouse(e) && e.button === 0) { mouse.boost = false; sendInput(); } });
window.addEventListener('blur', () => { mouse.boost = false; });
window.addEventListener('resize', () => send({ t: 'view', ...viewSize() }));
initTouch(() => { lastInput = 'touch'; sendInput(); });

function sendInput() {
  if (!playing) return;
  if (lastInput === 'touch') {
    send({ t: 'in', a: +touch.angle.toFixed(3), th: +touch.throttle.toFixed(2), b: touch.boost ? 1 : 0 });
    return;
  }
  const dx = mouse.x - window.innerWidth / 2;
  const dy = mouse.y - window.innerHeight / 2;
  const dist = Math.hypot(dx, dy);
  // full speed once the mouse is ~1/5 of the screen away from you; stop when it is on top of you
  const full = Math.min(window.innerWidth, window.innerHeight) * 0.2;
  const th = dist < 6 ? 0 : Math.min(1, dist / full);
  send({ t: 'in', a: +Math.atan2(dy, dx).toFixed(3), th: +th.toFixed(2), b: mouse.boost ? 1 : 0 });
}
setInterval(sendInput, 50);

// ---------- render loop ----------
let lastFrame = performance.now();
function frame() {
  requestAnimationFrame(frame);
  const nowMs = performance.now();
  const dt = Math.min(0.1, (nowMs - lastFrame) / 1000);
  lastFrame = nowMs;
  if (!renderer?.ready) return;
  const t = state.renderTime();
  for (const upd of state.dueFood(t)) renderer.applyFood(upd);
  renderer.updateFood(dt);
  const view = state.sample(t);
  if (!view) return;
  view.zoom *= viewScale();
  renderer.draw(view, dt);
  if (playing && !view.spectating) {
    hud.update(view.me);
    setBoostReady(view.me.m >= 25);   // server: BOOST_MIN_MASS
  }
}
requestAnimationFrame(frame);

// ?name=Foo pre-fills the name and joins straight away (handy for testing)
// ?watch=1 hides the menu and just follows the leader (screenshots, a classroom screen)
const params = new URLSearchParams(location.search);
const preset = params.get('name');
if (params.has('watch')) joinEl.hidden = true;

// connect immediately so the menu shows the live game behind it
connect()
  .then(() => {
    if (preset) {
      nameEl.value = preset;
      form.requestSubmit();
    }
  })
  .catch((err) => { statusEl.textContent = err.message; });
