// Buffers server snapshots and renders slightly in the past so motion is smooth
// even though snapshots only arrive ~15 times per second.
const INTERP_DELAY = 0.12; // seconds behind the newest server time
const KEEP = 1.0;          // seconds of history to keep

const now = () => performance.now() / 1000;
const lerp = (a, b, t) => a + (b - a) * t;

export class State {
  constructor() {
    this.offset = null;    // estimate of (server clock - local clock)
    this.foodQueue = [];   // food changes waiting until render time reaches them
    this.clearMotion();
  }

  // Called on respawn: forget old positions. Food changes are kept, because the server
  // tracks what this connection already knows about food across deaths.
  clearMotion() {
    this.snaps = [];
    this.latest = null;
  }

  push(snap) {
    const sample = snap.ts - now();
    this.offset = this.offset === null ? sample : this.offset + (sample - this.offset) * 0.1;
    snap.players = new Map(snap.p.map(([id, x, y, r, lvl, name, bot, boost, shield]) =>
      [id, { id, x, y, r, lvl, name, bot, boost, shield }]));
    this.snaps.push(snap);
    this.latest = snap;
    if (snap.f.length || snap.fr.length) this.foodQueue.push({ ts: snap.ts, add: snap.f, remove: snap.fr });
    while (this.snaps.length > 2 && this.snaps[0].ts < snap.ts - KEEP) this.snaps.shift();
  }

  renderTime() {
    return now() + (this.offset ?? 0) - INTERP_DELAY;
  }

  // Pops food updates whose time has come; returns them in order.
  dueFood(t) {
    const due = [];
    while (this.foodQueue.length && this.foodQueue[0].ts <= t) due.push(this.foodQueue.shift());
    return due;
  }

  // Interpolated view of the world at time t, or null before the first snapshot.
  sample(t) {
    const s = this.snaps;
    if (!s.length) return null;
    let a = s[0], b = s[0];
    if (t >= s[s.length - 1].ts) {
      a = b = s[s.length - 1];
    } else {
      for (let i = s.length - 1; i > 0; i--) {
        if (s[i - 1].ts <= t) { a = s[i - 1]; b = s[i]; break; }
      }
    }
    const k = b.ts > a.ts ? Math.min(1, Math.max(0, (t - a.ts) / (b.ts - a.ts))) : 1;
    const players = [];
    for (const pb of b.players.values()) {
      const pa = a.players.get(pb.id);
      players.push(pa ? { ...pb, x: lerp(pa.x, pb.x, k), y: lerp(pa.y, pb.y, k), r: lerp(pa.r, pb.r, k) } : pb);
    }
    return {
      spectating: !!b.spec,
      me: { ...b.me, x: lerp(a.me.x, b.me.x, k), y: lerp(a.me.y, b.me.y, k) },
      zoom: lerp(a.z, b.z, k),
      players,
    };
  }
}
