// DOM heads-up display: leaderboard (top-left), level progress (top-right), fact toasts.
// Player names come from other people: always use textContent, never innerHTML.
import { LEVELS, levelSpan } from './levels.js';
import { formatRealMass } from './realmass.js';

const $ = (id) => document.getElementById(id);
const TOAST_MS = 7000;

export class Hud {
  constructor() {
    this.root = $('hud');
    this.lbList = $('lb-list');
    this.lbMe = $('lb-me');
    this.iconCur = $('icon-cur');
    this.iconNext = $('icon-next');
    this.fill = $('prog-fill');
    this.lvlCur = $('lvl-cur');
    this.lvlNext = $('lvl-next');
    this.realMass = $('real-mass');
    this.toast = $('toast');
    this.toastTimer = null;
    this.level = -1;
    this.factIndex = new Map();   // level -> next fact to show, so repeats cycle
  }

  show(on) {
    this.root.hidden = !on;
    if (!on) this.hideToast();
  }

  // Called when a new life starts.
  reset() {
    this.level = -1;
  }

  update(me) {
    const lvl = me.lvl;
    if (lvl !== this.level) {
      if (this.level === -1) {
        this.showToast(`You're a speck of ${LEVELS[0].name.toLowerCase()}!`,
          `${LEVELS[0].facts[0]} Steer with your mouse, hold click to boost.`);
      } else if (lvl > this.level) {
        this.showToast(`You're now ${article(LEVELS[lvl].name)}!`, this.nextFact(lvl));
      }
      this.level = lvl;
      setIcon(this.iconCur, lvl);
      this.lvlCur.textContent = LEVELS[lvl].name;
      const top = lvl === LEVELS.length - 1;
      this.iconNext.hidden = top;
      if (!top) setIcon(this.iconNext, lvl + 1);
      this.lvlNext.textContent = top ? 'Top of the universe!' : `Next: ${LEVELS[lvl + 1].name}`;
    }
    const [lo, hi] = levelSpan(lvl);
    const frac = Math.max(0, Math.min(1, (me.m - lo) / (hi - lo)));
    this.fill.style.width = `${(frac * 100).toFixed(1)}%`;
    this.realMass.textContent = formatRealMass(me.rk);
  }

  leaderboard(rows, rank, myId) {
    const items = rows.map(([id, name, mass, lvl, bot], i) => {
      const li = document.createElement('li');
      if (id === myId) li.className = 'me';
      const dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.background = LEVELS[lvl].css;
      const nm = document.createElement('span');
      nm.className = 'nm';
      nm.textContent = `${i + 1}. ${name}`;
      li.append(dot, nm);
      if (bot) {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.textContent = 'bot';
        li.append(tag);
      }
      li.title = `${LEVELS[lvl].name} · mass ${mass}`;
      return li;
    });
    this.lbList.replaceChildren(...items);
    const inTop = rows.some(([id]) => id === myId);
    this.lbMe.hidden = inTop;
    this.lbMe.textContent = inTop ? '' : `You: #${rank}`;
  }

  nextFact(lvl) {
    const facts = LEVELS[lvl].facts;
    const i = this.factIndex.get(lvl) ?? 0;
    this.factIndex.set(lvl, i + 1);
    return facts[i % facts.length];
  }

  showToast(title, body) {
    this.toast.querySelector('.toast-title').textContent = title;
    this.toast.querySelector('.toast-body').textContent = body;
    this.toast.hidden = false;
    this.toast.classList.remove('pop');
    void this.toast.offsetWidth;  // restart the CSS animation
    this.toast.classList.add('pop');
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => this.hideToast(), TOAST_MS);
  }

  hideToast() {
    this.toast.hidden = true;
    clearTimeout(this.toastTimer);
  }
}

export function setIcon(el, lvl) {
  el.dataset.level = LEVELS[lvl].key;
  el.style.setProperty('--c', LEVELS[lvl].css);
  el.title = LEVELS[lvl].name;
}

export function randomFact(maxLevel) {
  const lvl = Math.floor(Math.random() * (Math.min(maxLevel + 2, LEVELS.length)));
  const facts = LEVELS[lvl].facts;
  return facts[Math.floor(Math.random() * facts.length)];
}

function article(name) {
  return /^[aeiou]/i.test(name) ? `an ${name}` : `a ${name}`;
}
