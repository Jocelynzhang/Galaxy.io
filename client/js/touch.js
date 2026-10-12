// Touch controls for phones and tablets: a floating joystick on the left half of the screen and a
// hold-to-boost button on the right. Shown on touch devices (and after the first touch anywhere).
// main.js reads `touch` when sending input; the mouse path is used otherwise.

export const touch = { used: false, angle: 0, throttle: 0, boost: false };

const STICK_R = 60;          // px the knob can travel from the base centre = full speed

let root, base, knob, boostBtn;
let stickId = null, boostId = null;
let originX = 0, originY = 0;

function el(cls, parent) {
  const d = document.createElement('div');
  d.className = cls;
  parent.appendChild(d);
  return d;
}

function restBase() {
  // resting spot, bottom-left, so players can see where the stick is before they touch
  base.classList.remove('active');
  base.style.left = '';
  base.style.top = '';
  knob.style.transform = '';
}

function moveKnob(x, y) {
  let dx = x - originX, dy = y - originY;
  const d = Math.hypot(dx, dy);
  if (d > STICK_R) { dx *= STICK_R / d; dy *= STICK_R / d; }
  knob.style.transform = `translate(${dx}px, ${dy}px)`;
  touch.throttle = d < 6 ? 0 : Math.min(1, d / STICK_R);
  if (d >= 6) touch.angle = Math.atan2(dy, dx);
}

function show() {
  if (touch.used) return;
  touch.used = true;
  document.body.classList.add('touch');
}

export function initTouch(onChange) {
  root = el('touch-ui', document.body);
  const zone = el('stick-zone', root);
  base = el('stick-base', zone);
  knob = el('stick-knob', base);
  boostBtn = el('boost-btn', root);
  boostBtn.innerHTML = '<span>BOOST</span>';

  zone.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse' || stickId !== null) return;
    show();
    stickId = e.pointerId;
    try { zone.setPointerCapture(e.pointerId); } catch { /* pointer already gone */ }
    // the stick appears under the thumb, wherever it lands in the left half
    originX = e.clientX;
    originY = e.clientY;
    base.classList.add('active');
    base.style.left = `${originX}px`;
    base.style.top = `${originY}px`;
    moveKnob(e.clientX, e.clientY);
    onChange();
  });
  zone.addEventListener('pointermove', (e) => {
    if (e.pointerId !== stickId) return;
    moveKnob(e.clientX, e.clientY);
  });
  const endStick = (e) => {
    if (e.pointerId !== stickId) return;
    stickId = null;
    touch.throttle = 0;      // let go = stop (heading is kept)
    restBase();
    onChange();
  };
  zone.addEventListener('pointerup', endStick);
  zone.addEventListener('pointercancel', endStick);

  boostBtn.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse') return;
    show();
    boostId = e.pointerId;
    try { boostBtn.setPointerCapture(e.pointerId); } catch { /* pointer already gone */ }
    touch.boost = true;
    boostBtn.classList.add('on');
    onChange();
  });
  const endBoost = (e) => {
    if (e.pointerId !== boostId) return;
    boostId = null;
    touch.boost = false;
    boostBtn.classList.remove('on');
    onChange();
  };
  boostBtn.addEventListener('pointerup', endBoost);
  boostBtn.addEventListener('pointercancel', endBoost);

  // touch devices get the controls straight away; anything else after its first touch
  if (matchMedia('(pointer: coarse)').matches || navigator.maxTouchPoints > 0) show();
  window.addEventListener('touchstart', show, { once: true, passive: true });
  // iOS Safari still pinch-zooms despite the viewport tag; the game needs every gesture
  document.addEventListener('gesturestart', (e) => e.preventDefault());
  window.addEventListener('blur', () => { touch.boost = false; touch.throttle = 0; });
}

// Dust is too light to boost (server: BOOST_MIN_MASS = 25); grey the button out until then.
export function setBoostReady(ready) {
  boostBtn?.classList.toggle('disabled', !ready);
}

export function setTouchVisible(visible) {
  root?.classList.toggle('playing', visible);
}
