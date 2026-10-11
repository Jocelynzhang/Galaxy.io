import { Renderer } from './render.js';
import { State } from './state.js';
import { LEVELS } from './levels.js';

const $ = (id) => document.getElementById(id);
const joinEl = $('join'), deadEl = $('dead'), hudEl = $('hud');
const form = $('join-form'), nameEl = $('name'), statusEl = $('join-status');

const state = new State();
let renderer = null;
let ws = null;
let playing = false;
let playerName = '';

// ---------- networking ----------
function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/ws`;
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function viewSize() {
  return { vw: window.innerWidth, vh: window.innerHeight };
}

function connect() {
  return new Promise((resolve, reject) => {
    ws = new WebSocket(wsUrl());
    ws.onopen = () => resolve();
    ws.onerror = () => reject(new Error('Could not reach the server'));
    ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
    ws.onclose = () => {
      ws = null;
      playing = false;
      hudEl.hidden = true;
      deadEl.hidden = true;
      joinEl.hidden = false;
      statusEl.textContent = 'Disconnected from the server. Press Confirm to rejoin.';
      if (renderer) { renderer.app.destroy(true, { children: true }); renderer = null; }
      $('join-form').querySelector('button').disabled = false;
    };
  });
}

async function onMessage(msg) {
  switch (msg.t) {
    case 'welcome':
      if (!renderer) {
        renderer = new Renderer();
        await renderer.init($('stage'), msg.world);
        renderer.foodR = msg.foodR;
      }
      state.clearMotion();
      playing = true;
      joinEl.hidden = true;
      deadEl.hidden = true;
      hudEl.hidden = false;
      break;
    case 's':
      state.push(msg);
      break;
    case 'dead':
      playing = false;
      hudEl.hidden = true;
      $('dead-msg').textContent =
        `${msg.by} swallowed you at ${Math.round(msg.mass)} mass. ` +
        `Best level reached: ${LEVELS[msg.best].name}.`;
      deadEl.hidden = false;
      break;
  }
}

// ---------- join flow ----------
form.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  playerName = nameEl.value.trim();
  const button = form.querySelector('button');
  button.disabled = true;
  statusEl.textContent = '';
  try {
    if (!ws) {
      statusEl.textContent = 'Connecting…';
      await connect();
      // a fresh connection starts with no food known on either side
      state.foodQueue = [];
    }
    send({ t: 'join', name: playerName, ...viewSize() });
    statusEl.textContent = '';
  } catch (err) {
    statusEl.textContent = err.message;
    button.disabled = false;
  }
});

// ?name=Foo pre-fills the name and joins straight away (handy for testing)
const preset = new URLSearchParams(location.search).get('name');
if (preset) {
  nameEl.value = preset;
  form.requestSubmit();
}

$('again').addEventListener('click', () => {
  send({ t: 'join', name: playerName, ...viewSize() });
});

// ---------- input ----------
const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2, boost: false };
window.addEventListener('mousemove', (e) => { mouse.x = e.clientX; mouse.y = e.clientY; });
window.addEventListener('mousedown', (e) => { if (e.button === 0) { mouse.boost = true; sendInput(); } });
window.addEventListener('mouseup', (e) => { if (e.button === 0) { mouse.boost = false; sendInput(); } });
window.addEventListener('blur', () => { mouse.boost = false; });
window.addEventListener('resize', () => send({ t: 'view', ...viewSize() }));

function sendInput() {
  if (!playing) return;
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
  if (!renderer) return;
  const t = state.renderTime();
  for (const upd of state.dueFood(t)) renderer.applyFood(upd);
  renderer.updateFood(dt);
  if (!playing) return;
  const view = state.sample(t);
  if (!view) return;
  renderer.draw(view);
  $('hud-mass').textContent = `${LEVELS[view.me.lvl].name} · mass ${Math.round(view.me.m)}`;
}
requestAnimationFrame(frame);
