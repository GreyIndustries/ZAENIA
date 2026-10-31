import { nodeWakeLevel, wakeLevel } from "../../core/coreWake";

/**
 * ZÆNIA neural field.
 * A dense, glowing neural sphere with star-shaped neurons through its volume,
 * six module nerves, and two particle streams that drift from its sides to
 * the stage edges. Everything is drawn on ONE canvas with one light model so the
 * branches belong to the core. Fully procedural: no images.
 */

const TAU = Math.PI * 2;
const clamp = (v: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
const smooth = (v: number) => v * v * (3 - 2 * v);

export type BranchKey = "security" | "calendar" | "status" | "files" | "tasks" | "system";
export type BranchTone = "amber" | "blue";
export type BranchDef = {
  key: BranchKey; name: string; description: string;
  side: -1 | 1; tone: BranchTone;
  /** Orb position in core radii, relative to the nucleus. */
  ox: number; oy: number;
  /** Middle orbs sit level with the nucleus; their distance adapts to width. */
  mid: boolean;
};

/** Order matters: it is also the wake order during the seven-second startup. */
export const BRANCHES: readonly BranchDef[] = [
  { key: "security", name: "Security", description: "Protection and privacy", side: -1, tone: "amber", ox: -1.24, oy: -0.95, mid: false },
  { key: "calendar", name: "Calendar", description: "Schedule and time", side: 1, tone: "blue", ox: 1.24, oy: -0.95, mid: false },
  { key: "status", name: "Status", description: "Readiness and health", side: -1, tone: "blue", ox: -1.62, oy: -0.02, mid: true },
  { key: "files", name: "Files", description: "Knowledge and data", side: 1, tone: "amber", ox: 1.62, oy: -0.02, mid: true },
  { key: "tasks", name: "Tasks", description: "Planning and execution", side: -1, tone: "amber", ox: -1.24, oy: 0.74, mid: false },
  { key: "system", name: "System", description: "Core and configuration", side: 1, tone: "blue", ox: 1.24, oy: 0.74, mid: false },
];

export type OrbPlacement = { key: BranchKey; x: number; y: number; labelAbove: boolean };
export type FieldLayout = {
  width: number; height: number; cx: number; cy: number;
  r: number; orbR: number; compact: boolean; orbs: OrbPlacement[];
};

/**
 * Phone ring: the six orbs sit evenly around the core (top pair, side pair,
 * bottom pair) so labels never collide on a narrow screen.
 */
const COMPACT_RING: Record<BranchKey, [number, number]> = {
  security: [-0.7, -1.2], calendar: [0.7, -1.2],
  status: [-1.36, 0], files: [1.36, 0],
  tasks: [-0.7, 1.2], system: [0.7, 1.2],
};

/** Places the core and its six orbs so the outer label plates always fit. */
export function computeLayout(width: number, height: number, ringed = false): FieldLayout {
  const compact = width < 760;
  if (ringed) {
    // Grey, 2026-10-31: the core by itself, its nerves wrapped around it like Saturn's rings (outer ring 2.15 r).
    const cx = width / 2, cy = height * (compact ? 0.5 : 0.45);
    const r = Math.max(48, Math.min((width / 2 - 12) / RING_OUTER, height * (compact ? 0.38 : 0.31), cy - 14, 280));
    return { width, height, cx, cy, r, orbR: 0, compact, orbs: [] };
  }
  if (compact) {
    const orbR = clamp(width * 0.06, 20, 26);
    const cx = width / 2, cy = height / 2;
    // Side labels sit under their orbs; top labels sit above theirs.
    const byWidth = (width / 2 - Math.max(orbR, 42) - 4) / 1.36;
    const byHeight = (height / 2 - orbR - 26) / 1.2;
    const r = Math.max(48, Math.min(byWidth, byHeight, 230));
    const orbs = BRANCHES.map(b => {
      const [ox, oy] = COMPACT_RING[b.key];
      return { key: b.key, x: cx + ox * r, y: cy + oy * r, labelAbove: oy < 0 };
    });
    return { width, height, cx, cy, r, orbR, compact, orbs };
  }
  const orbR = clamp(width * 0.031, 26, 36);
  const mid = 1.62;
  const room = orbR + 192;
  const cx = width / 2;
  const cy = height * 0.47;
  // A little smaller than before, leaving room for readouts under the orbs.
  const r = Math.max(56, Math.min((width / 2 - room) / mid, height * 0.33, cy - 14, 290));
  const orbs = BRANCHES.map(b => ({
    key: b.key,
    x: cx + (b.mid ? Math.sign(b.ox) * mid : b.ox) * r,
    y: cy + b.oy * r,
    labelAbove: false,
  }));
  return { width, height, cx, cy, r, orbR, compact, orbs };
}

/** What ZÆNIA is doing right now; the core reacts the way a live assistant does. */
export type VoicePhase = "idle" | "listening" | "thinking" | "speaking";
export type FieldState = { progress: number; motion: boolean; processing: boolean; phase?: VoicePhase; ringed?: boolean; look?: string };

/**
 * Black-hole variants (Grey's pictures, 2026-10-31): the middle of the core is a void with no light, ringed by a bright
 * photon ring and the core's own nerves swirling around it as the lensed disk; the accretion disk crosses in front.
 * Previews only until Grey picks one. roll = disk tilt on screen, squash = how open the disk looks.
 */
type VoidLook = { roll: number; squash: number; hot: string; mid: string; cool: string; ring: string; hole: number;
  /** Where the disk runs, in core radii (default 1.04 to DISK_OUTER). "void-photo" keeps it inside the core. */
  diskIn?: number; diskOut?: number; contained?: boolean;
  /** No neural core at all: only the black hole (Grey, 2026-10-31: "clear core ... exact copy of the picture"). */
  clear?: boolean };
const VOID_LOOKS: Record<string, VoidLook> = {
  "void-ember": { roll: -0.5, squash: 0.38, hot: "255,224,160", mid: "255,150,60", cool: "214,84,28", ring: "255,200,120", hole: 0.74 },
  "void-white": { roll: -1.02, squash: 0.15, hot: "255,250,244", mid: "255,214,184", cool: "196,128,92", ring: "255,244,232", hole: 0.7 },
  // Grey's photo (2026-10-31): compact, nothing past the core's own circle. A black void, a bright gold rim, the
  // lensed ring hugging it, and a tilted dusty disk rising from lower left to upper right.
  // Grey's photo, as is: a black hole only. Void, thin bright rim, a thick gold lensed ring brightest at the upper
  // left, and a wide dusty disk rising from lower left to upper right and crossing in front of the void.
  "void-exact": { roll: -0.6, squash: 0.3, hot: "255,222,150", mid: "232,128,48", cool: "120,60,28", ring: "255,206,120", hole: 0.5,
    diskIn: 0.78, diskOut: 1.95, clear: true },
  "void-photo": { roll: -0.62, squash: 0.3, hot: "255,226,160", mid: "236,140,58", cool: "150,72,30", ring: "255,214,140", hole: 0.46,
    diskIn: 0.5, diskOut: 1.0, contained: true },
  "void-flat": { roll: -0.06, squash: 0.09, hot: "255,240,244", mid: "255,186,170", cool: "170,150,255", ring: "255,236,240", hole: 0.76 },
};

/* ------------------------------------------------------------------ */
/* Saturn rings: the nerves wrapped around the core                    */
/* ------------------------------------------------------------------ */

export const RING_OUTER = 2.15;
const DISK_OUTER = 2.5;   // the black-hole disk reaches a little wider (Grey: "wider rings")
const RING_SQUASH = 0.27;   // how open the rings look (0 = edge on)
const RING_ROLL = -0.33;    // tilt of the ring plane on screen
const RING_POINTS = 120;
type RingStrand = { radius: number; wobble: number; phase: number; freq: number; blue: boolean; alpha: number; width: number; order: number };
type RingSignal = { strand: number; angle: number; speed: number; blue: boolean };

function buildRings(): { strands: RingStrand[]; signals: RingSignal[]; dense: RingStrand[]; three: RingStrand[] } {
  const rnd = seeded(4242);
  const strands: RingStrand[] = [];
  // Three bands with Saturn-like gaps between them: inner (faint), main (bright), outer (thin).
  const bands: [number, number, number, number][] = [[1.28, 1.42, 7, 0.32], [1.5, 1.86, 16, 0.72], [1.94, RING_OUTER, 6, 0.42]];
  for (const [from, to, count, strength] of bands) {
    for (let i = 0; i < count; i++) {
      const u = (i + rnd() * 0.8) / count;
      strands.push({ radius: from + (to - from) * u, wobble: 0.004 + rnd() * 0.012, phase: rnd() * TAU, freq: 2 + Math.floor(rnd() * 5),
        blue: rnd() < 0.18, alpha: strength * (0.45 + rnd() * 0.55), width: 0.6 + rnd() * (strength > 0.6 ? 1.3 : 0.6), order: rnd() });
    }
  }
  const signals: RingSignal[] = [];
  for (let i = 0; i < 26; i++) {
    signals.push({ strand: Math.floor(rnd() * strands.length), angle: rnd() * TAU, speed: (0.12 + rnd() * 0.22) * (rnd() < 0.85 ? 1 : -1), blue: rnd() < 0.2 });
  }
  // The black-hole disk: one wide, dense, streaky band with no gaps (Grey's pictures).
  const dense: RingStrand[] = [];
  for (let i = 0; i < 90; i++) {
    const u = i / 89;
    dense.push({ radius: 1.04 + u * (DISK_OUTER - 1.04) + (rnd() - 0.5) * 0.01, wobble: 0.003 + rnd() * 0.02, phase: rnd() * TAU,
      freq: 2 + Math.floor(rnd() * 7), blue: false, alpha: (0.35 + rnd() * 0.65) * (1 - u * 0.55), width: 0.5 + rnd() * 2.2 * (1 - u * 0.5), order: rnd() * 0.6 });
  }
  // "jarvis": exactly three crisp planet rings.
  const three: RingStrand[] = [[1.34, 2.4, 0.95], [1.68, 1.7, 0.8], [2.02, 1.2, 0.65]].map(([radius, width, alpha], i) =>
    ({ radius, wobble: 0.002, phase: i * 2.1, freq: 3, blue: false, alpha, width, order: i * 0.15 }));
  return { strands, signals, dense, three };
}

export type NeuralField = {
  setLayout(layout: FieldLayout): void;
  setState(state: FieldState): void;
  destroy(): void;
};

/* ------------------------------------------------------------------ */
/* Colour and depth tables used for batched strokes                    */
/* ------------------------------------------------------------------ */

const AMBER = 0, HOT = 1, BLUE = 2;
const RGB = ["255,128,32", "255,182,88", "128,160,255"];
const DEPTH_ALPHA = [0.05, 0.1, 0.22, 0.46, 0.78];
const DEPTH_WIDTH = [0.4, 0.5, 0.65, 0.85, 1.05];
const VIS_ALPHA = [0.3, 0.65, 1];
const BUCKETS = 45;
const bucketOf = (color: number, depth: number, vis: number) =>
  color * 15 + Math.min(4, Math.floor(clamp(depth) * 5)) * 3 + (vis < 0.34 ? 0 : vis < 0.67 ? 1 : 2);

/* ------------------------------------------------------------------ */
/* Sphere anatomy (unit sphere, deterministic)                         */
/* ------------------------------------------------------------------ */

type Edge = {
  a: number; b: number; mx: number; my: number; mz: number; k: number; color: number; order: number;
  sx: number; sy: number; ex: number; ey: number; qx: number; qy: number; depth: number; vis: number;
};
type Hub = { x: number; y: number; z: number; major: boolean; blue: boolean; order: number };
type Dendrite = { hub: number; pts: Float32Array; color: number };
type Fibre = { tx: number; ty: number; tz: number; px: number; py: number; pz: number; twist: number; blue: boolean; order: number };
type Pulse = { edge: number; t: number; speed: number };
type Mote = { x: number; y: number; vx: number; vy: number; age: number; life: number; size: number; blue: boolean };

const DENDRITE_POINTS = 7;

function seeded(start: number) {
  let s = start;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

function buildSphere() {
  const rnd = seeded(11);
  const n = 820;
  const x0 = new Float32Array(n), y0 = new Float32Array(n), z0 = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const y = 1 - (i + 0.5) / n * 2 + (rnd() - 0.5) * 0.03;
    const ring = Math.sqrt(Math.max(0, 1 - y * y));
    const th = i * 2.399963 + (rnd() - 0.5) * 0.5;
    const x = Math.cos(th) * ring, z = Math.sin(th) * ring;
    const len = Math.hypot(x, y, z) || 1, jitter = 0.972 + rnd() * 0.026;
    x0[i] = x / len * jitter; y0[i] = y / len * jitter; z0[i] = z / len * jitter;
  }
  // The network lights up outward from this point during startup.
  const seed = [0.3, 0.2, 0.93];
  const sl = Math.hypot(seed[0], seed[1], seed[2]);
  seed[0] /= sl; seed[1] /= sl; seed[2] /= sl;
  const reveal = (x: number, y: number, z: number) => {
    const l = Math.hypot(x, y, z) || 1;
    return (1 - (x * seed[0] + y * seed[1] + z * seed[2]) / l) / 2;
  };
  const pickColor = () => { const c = rnd(); return c < 0.3 ? BLUE : c < 0.45 ? HOT : AMBER; };

  const edges: Edge[] = [];
  const seen = new Set<number>();
  const addEdge = (a: number, b: number, k: number) => {
    const key = a < b ? a * n + b : b * n + a;
    if (seen.has(key)) return;
    seen.add(key);
    let mx = x0[a] + x0[b], my = y0[a] + y0[b], mz = z0[a] + z0[b];
    const l = Math.hypot(mx, my, mz) || 1; mx /= l; my /= l; mz /= l;
    edges.push({
      a, b, mx, my, mz, k, color: pickColor(), order: clamp(reveal(mx, my, mz) * 0.72 + rnd() * 0.28),
      sx: 0, sy: 0, ex: 0, ey: 0, qx: 0, qy: 0, depth: 0, vis: 0,
    });
  };
  const dist = new Float64Array(n);
  const idx: number[] = new Array(n);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const dx = x0[i] - x0[j], dy = y0[i] - y0[j], dz = z0[i] - z0[j];
      dist[j] = j === i ? Infinity : dx * dx + dy * dy + dz * dz;
      idx[j] = j;
    }
    idx.sort((p, q) => dist[p] - dist[q]);
    for (let q = 0; q < 3; q++) addEdge(i, idx[q], 1.0 + rnd() * 0.035);
  }
  // Long chords arc through the volume, so the ball reads as filled, not hollow.
  for (let c = 0; c < 190; c++) {
    const a = Math.floor(rnd() * n);
    for (let t = 0; t < 40; t++) {
      const j = Math.floor(rnd() * n);
      const dot = x0[a] * x0[j] + y0[a] * y0[j] + z0[a] * z0[j];
      if (dot > -0.2 && dot < 0.8) { addEdge(a, j, 0.5 + rnd() * 0.4); break; }
    }
  }

  // Star-shaped neurons: bright cell bodies with curling dendrites, spread
  // through the whole volume like the reference.
  const hubs: Hub[] = [];
  const dendrites: Dendrite[] = [];
  for (let i = 0; i < 58; i++) {
    const u = rnd() * 2 - 1, th = rnd() * TAU, ring = Math.sqrt(1 - u * u);
    const rh = i < 22 ? 0.86 + rnd() * 0.1 : 0.35 + rnd() * 0.5;
    const hx = Math.cos(th) * ring * rh, hy = u * rh, hz = Math.sin(th) * ring * rh;
    const major = i % 4 === 0, blue = rnd() < 0.16;
    hubs.push({ x: hx, y: hy, z: hz, major, blue, order: clamp(reveal(hx, hy, hz) * 0.7 + rnd() * 0.3) });
    const count = major ? 22 : 10 + Math.floor(rnd() * 6);
    for (let d = 0; d < count; d++) {
      let dx = rnd() - 0.5, dy = rnd() - 0.5, dz = rnd() - 0.5;
      if (rh > 0.84) {
        // Surface neurons spread mostly along the shell.
        const nx = hx / rh, ny = hy / rh, nz = hz / rh, dot = dx * nx + dy * ny + dz * nz;
        dx -= nx * dot * 0.85; dy -= ny * dot * 0.85; dz -= nz * dot * 0.85;
      }
      let dl = Math.hypot(dx, dy, dz) || 1; dx /= dl; dy /= dl; dz /= dl;
      const length = (major ? 0.3 : 0.16) + rnd() * 0.2, step = length / (DENDRITE_POINTS - 1);
      const pts = new Float32Array(DENDRITE_POINTS * 3);
      let px = hx, py = hy, pz = hz;
      for (let k = 0; k < DENDRITE_POINTS; k++) {
        pts[k * 3] = px; pts[k * 3 + 1] = py; pts[k * 3 + 2] = pz;
        dx += (rnd() - 0.5) * 0.45; dy += (rnd() - 0.5) * 0.45; dz += (rnd() - 0.5) * 0.45;
        dl = Math.hypot(dx, dy, dz) || 1; dx /= dl; dy /= dl; dz /= dl;
        px += dx * step; py += dy * step; pz += dz * step;
        const pr = Math.hypot(px, py, pz);
        if (pr > 0.985) { px *= 0.985 / pr; py *= 0.985 / pr; pz *= 0.985 / pr; }
      }
      dendrites.push({ hub: i, pts, color: blue ? BLUE : rnd() < 0.4 ? HOT : AMBER });
    }
  }

  const fibres: Fibre[] = [];
  for (let i = 0; i < 64; i++) {
    const t = Math.floor(rnd() * n);
    const tx = x0[t], ty = y0[t], tz = z0[t];
    const rx = rnd() - 0.5, ry = rnd() - 0.5, rz = rnd() - 0.5;
    let px = ty * rz - tz * ry, py = tz * rx - tx * rz, pz = tx * ry - ty * rx;
    const pl = Math.hypot(px, py, pz) || 1; px /= pl; py /= pl; pz /= pl;
    fibres.push({ tx, ty, tz, px, py, pz, twist: 0.14 + rnd() * 0.2, blue: rnd() < 0.25, order: clamp(reveal(tx, ty, tz) * 0.5 + rnd() * 0.5) });
  }
  const pulses: Pulse[] = Array.from({ length: 60 }, () => ({ edge: Math.floor(rnd() * edges.length), t: rnd(), speed: 0.0005 + rnd() * 0.0009 }));
  return {
    n, x0, y0, z0, xs: new Float32Array(n), ys: new Float32Array(n), zs: new Float32Array(n),
    edges, hubs, dendrites, fibres, pulses,
    hubDepth: new Float32Array(hubs.length), hubVis: new Float32Array(hubs.length),
    hubSX: new Float32Array(hubs.length), hubSY: new Float32Array(hubs.length),
    dProj: new Float32Array(dendrites.length * DENDRITE_POINTS * 2),
  };
}

/* ------------------------------------------------------------------ */
/* Screen-space geometry (rebuilt on resize)                           */
/* ------------------------------------------------------------------ */

const STRAND_SAMPLES = 72;
const FAN_SAMPLES = 48;
type Strand = { pts: Float32Array; blue: boolean; width: number; alpha: number; speed: number; offset: number };
type BranchGeo = { tone: BranchTone; strands: Strand[]; roots: Float32Array[]; exitX: number; exitY: number; sockX: number; sockY: number };
type FanParticle = { path: number; t: number; speed: number; spread: number; size: number; blue: boolean; spark: boolean };
type Fan = { paths: Float32Array[]; particles: FanParticle[] };

function catmull(points: [number, number][], samples: number) {
  const out = new Float32Array(samples * 2);
  const segs = points.length - 1;
  for (let i = 0; i < samples; i++) {
    const t = i / (samples - 1) * segs;
    const s = Math.min(segs - 1, Math.floor(t)), u = t - s, u2 = u * u, u3 = u2 * u;
    const p0 = points[Math.max(0, s - 1)], p1 = points[s], p2 = points[s + 1], p3 = points[Math.min(segs, s + 2)];
    for (let c = 0; c < 2; c++) {
      out[i * 2 + c] = 0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * u + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * u2 + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * u3);
    }
  }
  return out;
}

function buildBranch(def: BranchDef, place: OrbPlacement, L: FieldLayout, index: number): BranchGeo {
  const rnd = seeded(101 + index * 977);
  const { cx, cy, r, orbR } = L;
  const dx = place.x - cx, dy = place.y - cy, dist = Math.hypot(dx, dy) || 1;
  const ux = dx / dist, uy = dy / dist, px = -uy, py = ux;
  const angle = Math.atan2(dy, dx);
  const exitX = cx + ux * r * 0.985, exitY = cy + uy * r * 0.985;
  const sockX = place.x - ux * orbR * 0.9, sockY = place.y - uy * orbR * 0.9;
  const span = Math.hypot(sockX - exitX, sockY - exitY);
  const bend = (index % 2 ? 1 : -1) * span * 0.16;
  const at = (rad: number, ang: number): [number, number] => [cx + Math.cos(ang) * rad, cy + Math.sin(ang) * rad];

  // Five fibres gather inside the sphere, leave through one root on the
  // surface, then reach the module orb.
  const count = 5, strands: Strand[] = [];
  for (let j = 0; j < count; j++) {
    const k = (j - (count - 1) / 2) / ((count - 1) / 2);
    const blue = def.tone === "blue" ? j !== 1 : j === 1;
    const ctrl: [number, number][] = [
      at(r * (0.25 + 0.08 * (j % 3)), angle + k * 1.0),
      at(r * 0.6, angle + k * 0.35),
      at(r * 0.985, angle + k * 0.05),
      [exitX + ux * span * 0.45 + px * (bend + k * orbR * 0.25), exitY + uy * span * 0.45 + py * (bend + k * orbR * 0.25)],
      [sockX + px * k * orbR * 0.4, sockY + py * k * orbR * 0.4],
    ];
    const base = catmull(ctrl, STRAND_SAMPLES);
    const pts = new Float32Array(base.length);
    const amp = (1.8 + rnd() * 3) * clamp(r / 170, 0.6, 1.6);
    const freq = 1.2 + rnd() * 1.7, phase = rnd() * TAU;
    for (let i = 0; i < STRAND_SAMPLES; i++) {
      const t = i / (STRAND_SAMPLES - 1);
      const i0 = Math.max(0, i - 1), i1 = Math.min(STRAND_SAMPLES - 1, i + 1);
      let tx = base[i1 * 2] - base[i0 * 2], ty = base[i1 * 2 + 1] - base[i0 * 2 + 1];
      const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
      const outside = smooth(clamp((t - 0.42) / 0.16));
      const pinch = 1 - 0.8 * Math.exp(-(((t - 0.5) / 0.05) ** 2));
      const env = Math.pow(Math.sin(Math.PI * t), 0.8) * (0.3 + 0.7 * outside) * pinch;
      const off = amp * env * Math.sin(t * TAU * freq + phase);
      pts[i * 2] = base[i * 2] - ty * off;
      pts[i * 2 + 1] = base[i * 2 + 1] + tx * off;
    }
    strands.push({ pts, blue, width: j === 2 ? 1.6 : 0.7 + rnd() * 0.7, alpha: 0.62 + rnd() * 0.33, speed: 0.14 + rnd() * 0.12, offset: rnd() });
  }
  const roots: Float32Array[] = [];
  for (let j = 0; j < 6; j++) {
    const d = (j % 2 ? 1 : -1) * (0.09 + 0.06 * j);
    const rr = r * (0.88 + rnd() * 0.09);
    const q = at(r * 1.0, angle + d * 0.55), e = at(rr, angle + d);
    roots.push(Float32Array.of(exitX, exitY, q[0], q[1], e[0], e[1]));
  }
  return { tone: def.tone, strands, roots, exitX, exitY, sockX, sockY };
}

/**
 * Particle streams that leave the sphere's sides and drift to the stage edges.
 * The paths are invisible guides; only the particles are drawn, which keeps
 * the stage light and matches the dotted streams in the reference.
 */
function buildFan(side: -1 | 1, L: FieldLayout): Fan {
  const rnd = seeded(side < 0 ? 4441 : 8803);
  const { cx, cy, r, width: W, height: H } = L;
  const x0 = cx + side * r * 0.92, x1 = side < 0 ? -12 : W + 12;
  const paths: Float32Array[] = [];
  const count = 16;
  for (let j = 0; j < count; j++) {
    const f = j / (count - 1);
    const y0 = cy + (f - 0.5) * r * 0.3;
    const yEnd = cy + (f - 0.54) * H * 0.62 + (rnd() - 0.5) * H * 0.04;
    const freq = 0.8 + rnd() * 1.4, ph = rnd() * TAU, amp = (6 + rnd() * 18) * clamp(r / 170, 0.6, 1.4);
    const pts = new Float32Array(FAN_SAMPLES * 2);
    for (let i = 0; i < FAN_SAMPLES; i++) {
      const t = i / (FAN_SAMPLES - 1);
      pts[i * 2] = x0 + (x1 - x0) * t;
      pts[i * 2 + 1] = y0 + (yEnd - y0) * smooth(Math.min(1, t * 1.15)) + Math.sin(t * TAU * freq + ph) * amp * Math.min(1, t * 2.2);
    }
    paths.push(pts);
  }
  const particles: FanParticle[] = Array.from({ length: 360 }, () => ({
    path: Math.floor(rnd() * count),
    t: rnd(),
    speed: 0.05 + rnd() * 0.09,
    spread: (rnd() - 0.5) * 12 * clamp(r / 170, 0.6, 1.4),
    size: 4 + Math.pow(rnd(), 2) * 7,
    blue: rnd() < 0.55,
    spark: rnd() < 0.08,
  }));
  return { paths, particles };
}

/* ------------------------------------------------------------------ */
/* Renderer                                                            */
/* ------------------------------------------------------------------ */

function sprite(r: number, g: number, b: number) {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const x = c.getContext("2d");
  if (x) {
    const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, `rgba(${r},${g},${b},1)`);
    gr.addColorStop(0.25, `rgba(${r},${g},${b},.5)`);
    gr.addColorStop(1, `rgba(${r},${g},${b},0)`);
    x.fillStyle = gr;
    x.fillRect(0, 0, 64, 64);
  }
  return c;
}

export function createNeuralField(canvas: HTMLCanvasElement): NeuralField | null {
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const S = buildSphere();
  const SA = sprite(255, 165, 55), SB = sprite(120, 165, 255), SW = sprite(255, 238, 196);
  const RINGS = buildRings();
  // Dust for the "void-exact" disk: many faint specks, denser and brighter close to the hole.
  const DUST = (() => {
    const rnd = seeded(9090);
    return Array.from({ length: 1100 }, () => ({ u: Math.pow(rnd(), 1.6), a: rnd() * TAU, lift: (rnd() - 0.5) * 2, size: 1.5 + rnd() * 5,
      alpha: 0.3 + rnd() * 0.7, hot: rnd() < 0.35, speed: 0.04 + rnd() * 0.06 }));
  })();
  const bloom = document.createElement("canvas");
  const bctx = bloom.getContext("2d");
  const canBlur = !!bctx && "filter" in bctx;
  const edgeBuckets: number[][] = Array.from({ length: BUCKETS }, () => []);
  const dendBuckets: number[][] = Array.from({ length: BUCKETS }, () => []);
  const motes: Mote[] = [];
  const moteRnd = seeded(77);

  let L: FieldLayout | null = null;
  let geo: BranchGeo[] = [];
  let fans: Fan[] = [];
  let state: FieldState = { progress: 0, motion: true, processing: false };
  let dpr = 1, raf = 0, last = performance.now(), dirty = true, drawnProgress = -1;
  let spin = 0.6, time = 0;
  // Eased 0..1 weights per voice phase, so the core blends between behaviours.
  let lis = 0, thk = 0, spk = 0;
  const TILT = 0.28;

  const spr = (s: HTMLCanvasElement, x: number, y: number, size: number, a: number) => {
    ctx.globalAlpha = a;
    ctx.drawImage(s, x - size / 2, y - size / 2, size, size);
  };
  const tracePolyline = (pts: Float32Array, from: number, upto: number) => {
    ctx.moveTo(pts[from * 2], pts[from * 2 + 1]);
    for (let i = from + 1; i <= upto; i++) ctx.lineTo(pts[i * 2], pts[i * 2 + 1]);
  };
  const pointAt = (pts: Float32Array, samples: number, t: number): [number, number] => {
    const f = clamp(t) * (samples - 1), i = Math.min(samples - 2, Math.floor(f)), u = f - i;
    return [pts[i * 2] + (pts[i * 2 + 2] - pts[i * 2]) * u, pts[i * 2 + 1] + (pts[i * 2 + 3] - pts[i * 2 + 1]) * u];
  };
  const spawnMote = (m?: Mote): Mote => {
    const a = moteRnd() * TAU, rr = 0.92 + moteRnd() * 0.16;
    const out = 0.02 + moteRnd() * 0.05;
    const next = m ?? { x: 0, y: 0, vx: 0, vy: 0, age: 0, life: 0, size: 0, blue: false };
    next.x = Math.cos(a) * rr; next.y = Math.sin(a) * rr;
    next.vx = Math.cos(a) * out; next.vy = Math.sin(a) * out + 0.035;
    next.age = moteRnd() * 2; next.life = 2.5 + moteRnd() * 3;
    next.size = 2.5 + moteRnd() * 4; next.blue = moteRnd() < 0.2;
    return next;
  };
  for (let i = 0; i < 90; i++) motes.push(spawnMote());

  const draw = () => {
    if (!L) return;
    const { width: W, height: H, cx, cy, r } = L;
    const sc = clamp(r / 190, 0.55, 1.4);
    const pe = smooth(clamp(state.progress / 100));
    const nucleusWake = wakeLevel(state.progress, 0, 14);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    ctx.clearRect(0, 0, W, H);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    // Saturn rings. The far half is drawn first so the sphere hides what passes behind it.
    const ringReveal = state.ringed ? smooth(clamp((pe - 0.35) / 0.65)) : 0;
    const vl = state.ringed && state.look ? VOID_LOOKS[state.look] : undefined;
    // "jarvis" (Grey, 2026-10-31): the JARVIS hologram crossed with a planet: a golden sphere of broken circuit
    // shells around a bright nucleus, and three rings.
    const jv = state.ringed && state.look === "jarvis";
    const roll = vl ? vl.roll : RING_ROLL, squash = vl ? vl.squash : RING_SQUASH;
    const cR = Math.cos(roll), sR = Math.sin(roll);
    // Dense black-hole strands are laid out between 1.04 and DISK_OUTER; a look can squeeze them into its own range.
    const diskRadius = (s: RingStrand) => vl && vl.diskOut !== undefined && RINGS.dense.includes(s)
      ? (vl.diskIn ?? 1.04) + (s.radius - 1.04) / (DISK_OUTER - 1.04) * (vl.diskOut - (vl.diskIn ?? 1.04)) : s.radius;
    const ringPoint = (s: RingStrand, a: number): [number, number] => {
      const rad = diskRadius(s) * (1 + s.wobble * Math.sin(a * s.freq + s.phase + time * 0.4)) * r;
      const x = Math.cos(a) * rad, y = Math.sin(a) * rad * squash;
      return [cx + x * cR - y * sR, cy + x * sR + y * cR];
    };
    const drawRings = (front: boolean) => {
      if (ringReveal <= 0) return;
      const start = front ? 0 : Math.PI;
      const rate = (state.processing ? 1.8 : 1) + thk * 0.8 + spk * 0.5;
      const glow = 1 + lis * 0.25 + spk * 0.35;
      ctx.globalCompositeOperation = "lighter";
      if (vl) {
        // A soft luminous body under the strands, brightest near the hole.
        const steps = 48, a0 = start;
        ctx.beginPath();
        for (let k = 0; k <= steps; k++) { const a = a0 + Math.PI * (k / steps), rad = (vl.diskOut ?? DISK_OUTER) * r, x = Math.cos(a) * rad, y = Math.sin(a) * rad * squash; const px = cx + x * cR - y * sR, py = cy + x * sR + y * cR; if (k === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py); }
        for (let k = steps; k >= 0; k--) { const a = a0 + Math.PI * (k / steps), rad = (vl.diskIn ?? 1.02) * r, x = Math.cos(a) * rad, y = Math.sin(a) * rad * squash; ctx.lineTo(cx + x * cR - y * sR, cy + x * sR + y * cR); }
        ctx.closePath();
        const body = ctx.createRadialGradient(cx, cy, (vl.diskIn ?? 1) * r, cx, cy, (vl.diskOut ?? DISK_OUTER) * r);
        body.addColorStop(0, `rgba(${vl.hot},${(front ? 0.42 : 0.24) * (vl.clear ? 0.35 : 1) * glow * ringReveal})`);
        body.addColorStop(0.45, `rgba(${vl.mid},${(front ? 0.22 : 0.12) * (vl.clear ? 0.35 : 1) * glow * ringReveal})`);
        body.addColorStop(1, `rgba(${vl.cool},0)`);
        ctx.fillStyle = body; ctx.fill();
      }
      if (vl?.clear) {
        const inner = vl.diskIn ?? 1.04, outer = vl.diskOut ?? DISK_OUTER;
        for (const d of DUST) {
          const a = ((d.a + time * d.speed * Math.pow(1 / (inner + d.u * (outer - inner)), 1.5)) % TAU + TAU) % TAU;
          if ((a < Math.PI) !== front) continue;
          const rad = (inner + d.u * (outer - inner)) * r;
          const x = Math.cos(a) * rad, y = Math.sin(a) * rad * squash + d.lift * r * 0.07 * (1 - d.u * 0.4);
          spr(d.hot ? SW : SA, cx + x * cR - y * sR, cy + x * sR + y * cR, d.size * 1.3 * sc, d.alpha * (1 - d.u * 0.7) * ringReveal * (front ? 1 : 0.7));
        }
        ctx.globalAlpha = 1;
      }
      for (const s of vl ? RINGS.dense : jv ? RINGS.three : RINGS.strands) {
        const shown = smooth(clamp((ringReveal - s.order * 0.5) * 2));
        if (shown <= 0) continue;
        const span = Math.PI * shown;
        const col = vl ? (s.radius < 1.4 ? vl.hot : s.radius < 1.9 ? vl.mid : vl.cool) : jv ? (s.radius < 1.5 ? "255,214,120" : "255,176,64") : s.blue ? RGB[BLUE] : RGB[AMBER];
        const depth = front ? 1 : 0.55;
        ctx.beginPath();
        const steps = Math.round(RING_POINTS / 2);
        for (let k = 0; k <= steps; k++) {
          const a = start + span * (k / steps);
          const [x, y] = ringPoint(s, a);
          if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.globalAlpha = 1;
        ctx.strokeStyle = `rgba(${col},${s.alpha * 0.16 * depth * glow * (vl?.clear ? 0.4 : 1)})`;
        ctx.lineWidth = s.width * 3.2 * sc;
        ctx.stroke();
        ctx.strokeStyle = `rgba(${col},${Math.min(1, s.alpha * depth * glow * (vl?.clear ? (front ? 0.3 : 0.45) : 1))})`;
        ctx.lineWidth = s.width * sc;
        ctx.stroke();
      }
      // Signals running around the rings.
      for (const g of RINGS.signals) {
        const s = jv ? RINGS.three[g.strand % 3] : RINGS.strands[g.strand];
        const a = ((g.angle + time * g.speed * rate + spin * 0.6) % TAU + TAU) % TAU;
        const isFront = a < Math.PI;
        if (isFront !== front) continue;
        const [x, y] = ringPoint(s, a);
        spr(g.blue ? SB : SW, x, y, (front ? 13 : 9) * sc, (front ? 0.95 : 0.5) * ringReveal);
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    };
    drawRings(false);
    // JARVIS-style hologram: concentric shells of broken golden arcs with circuit ticks, turning at different speeds
    // and tilts, around a bright swirling nucleus.
    const drawHologram = () => {
      const reveal = smooth(clamp((pe - 0.2) / 0.8));
      if (reveal <= 0) return;
      const glow = (1 + lis * 0.3 + spk * 0.4 + thk * 0.2) * reveal;
      const rate = (state.processing ? 1.8 : 1) + thk * 0.8;
      ctx.globalCompositeOperation = "lighter";
      for (let shell = 0; shell < 8; shell++) {
        const rad = r * (0.26 + shell * 0.1);
        const tilt = 0.55 + 0.45 * Math.cos(time * 0.12 * (shell % 2 ? 1 : -1) + shell * 0.9);   // 3D-ish turn
        const turn = time * (0.08 + (shell % 3) * 0.05) * (shell % 2 ? 1 : -1) * rate + shell * 1.3;
        const segments = 5 + (shell * 3) % 6;
        for (let k = 0; k < segments; k++) {
          const seed = shell * 31 + k * 7;
          const start = turn + (k / segments) * TAU;
          const len = (TAU / segments) * (0.35 + ((seed * 13) % 10) / 18);
          const a = (0.35 + ((seed * 7) % 10) / 22) * glow * (1 - shell * 0.05);
          ctx.strokeStyle = `rgba(255,${180 + (seed % 5) * 10},${70 + (seed % 3) * 25},${a})`;
          ctx.lineWidth = (shell % 3 === 0 ? 2.2 : 1.2) * sc;
          ctx.beginPath(); ctx.ellipse(cx, cy, rad, rad * tilt, shell * 0.35, start, start + len); ctx.stroke();
          // Circuit ticks and little blocks along the arc.
          const ticks = Math.max(2, Math.round(len * 6));
          for (let j = 0; j <= ticks; j += 1 + (seed + j) % 2) {
            const u = start + len * (j / ticks);
            const ex = Math.cos(u) * rad, ey = Math.sin(u) * rad * tilt;
            const c0 = Math.cos(shell * 0.35), s0 = Math.sin(shell * 0.35);
            const px = cx + ex * c0 - ey * s0, py = cy + ex * s0 + ey * c0;
            const out = (3 + (j * seed) % 7) * sc * ((seed + j) % 3 === 0 ? 1.8 : 1);
            const nx = (px - cx) / rad, ny = (py - cy) / rad;
            ctx.lineWidth = 1 * sc;
            ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px + nx * out, py + ny * out); ctx.stroke();
            if ((seed + j) % 5 === 0) { ctx.globalAlpha = a; ctx.fillStyle = "rgba(255,210,120,0.9)"; ctx.fillRect(px - 2 * sc, py - 2 * sc, 4 * sc, 3 * sc); ctx.globalAlpha = 1; }
          }
        }
      }
      // Nucleus: a bright core and a swirl around it.
      const swirl = time * 0.6 * rate;
      ctx.strokeStyle = `rgba(255,226,150,${0.8 * glow})`;
      ctx.lineWidth = 2 * sc;
      ctx.beginPath();
      for (let k = 0; k <= 80; k++) { const u = k / 80, ang = swirl + u * TAU * 1.6, rr = r * (0.05 + u * 0.22); const x = cx + Math.cos(ang) * rr, y = cy + Math.sin(ang) * rr * 0.8; if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
      ctx.stroke();
      ctx.strokeStyle = `rgba(255,240,200,${0.9 * glow})`;
      ctx.lineWidth = 1.6 * sc;
      ctx.beginPath(); ctx.arc(cx, cy, r * 0.07, 0, TAU); ctx.stroke();
      spr(SW, cx, cy, r * 0.45, 0.55 * glow);
      ctx.globalCompositeOperation = "source-over";
    };

    // The neural sphere itself (skipped when the look is a black hole only).
    if (!vl?.clear) {
    // Dark, warm body blocks the backdrop so the network reads as a solid ball.
    const body = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    body.addColorStop(0, `rgba(36,12,4,${0.94 * pe})`);
    body.addColorStop(0.85, `rgba(14,5,3,${0.92 * pe})`);
    body.addColorStop(1, `rgba(10,4,3,${0.88 * pe})`);
    ctx.fillStyle = body;
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, TAU); ctx.fill();

    ctx.globalCompositeOperation = "lighter";
    // Outer halo.
    const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * (vl?.contained ? 1.0 : 1.55));
    halo.addColorStop(0, "rgba(255,140,40,0)");
    halo.addColorStop(0.6, "rgba(255,140,40,0)");
    halo.addColorStop(0.64, `rgba(255,140,40,${0.26 * pe})`);
    halo.addColorStop(1, "rgba(255,120,30,0)");
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(cx, cy, r * (vl?.contained ? 1.0 : 1.55), 0, TAU); ctx.fill();
    // Inner luminous haze: the whole ball glows, brightest toward the centre.
    const haze = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    haze.addColorStop(0, `rgba(255,160,70,${0.14 * pe})`);
    haze.addColorStop(0.4, `rgba(230,100,28,${0.04 * pe})`);
    haze.addColorStop(0.9, `rgba(210,80,20,${0.05 * pe})`);
    haze.addColorStop(1, "rgba(210,85,22,0)");
    ctx.fillStyle = haze;
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, TAU); ctx.fill();

    // Rotate the anatomy.
    const cA = Math.cos(spin), sA = Math.sin(spin), cT = Math.cos(TILT), sT = Math.sin(TILT);
    let rx = 0, ry = 0, rz = 0;
    const rot = (x: number, y: number, z: number) => {
      const x1 = x * cA + z * sA, z1 = -x * sA + z * cA;
      rx = x1; ry = y * cT - z1 * sT; rz = y * sT + z1 * cT;
    };
    for (let i = 0; i < S.n; i++) { rot(S.x0[i], S.y0[i], S.z0[i]); S.xs[i] = rx; S.ys[i] = ry; S.zs[i] = rz; }

    // Inner fibres from the nucleus.
    for (const f of S.fibres) {
      const v = clamp((pe * 1.3 - f.order * 0.9) * 6);
      if (v <= 0) continue;
      rot(f.tx, f.ty, f.tz);
      const tx = rx, ty = ry, tz = rz;
      rot(f.tx * 0.5 + f.px * f.twist * 1.4, f.ty * 0.5 + f.py * f.twist * 1.4, f.tz * 0.5 + f.pz * f.twist * 1.4);
      const a = (0.1 + 0.35 * (tz + 1) / 2) * v;
      ctx.strokeStyle = f.blue ? `rgba(128,165,255,${a * 0.8})` : `rgba(255,170,60,${a})`;
      ctx.lineWidth = 0.8 * sc;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.quadraticCurveTo(cx + rx * r, cy + ry * r, cx + tx * r, cy + ty * r); ctx.stroke();
    }

    // Surface and volume nerves, batched by colour, depth and reveal.
    for (const list of edgeBuckets) list.length = 0;
    for (let i = 0; i < S.edges.length; i++) {
      const e = S.edges[i];
      e.vis = clamp((pe * 1.3 - e.order * 0.9) * 6);
      rot(e.mx * e.k, e.my * e.k, e.mz * e.k);
      e.sx = cx + S.xs[e.a] * r; e.sy = cy + S.ys[e.a] * r;
      e.ex = cx + S.xs[e.b] * r; e.ey = cy + S.ys[e.b] * r;
      e.qx = cx + rx * r; e.qy = cy + ry * r;
      e.depth = ((S.zs[e.a] + S.zs[e.b]) / 2 + 1) / 2;
      if (e.vis < 0.05) continue;
      edgeBuckets[bucketOf(e.color, e.depth, e.vis)].push(i);
    }
    for (let b = 0; b < BUCKETS; b++) {
      const list = edgeBuckets[b];
      if (!list.length) continue;
      const color = Math.floor(b / 15), level = Math.floor((b % 15) / 3), a = DEPTH_ALPHA[level] * VIS_ALPHA[b % 3];
      ctx.beginPath();
      for (const i of list) { const e = S.edges[i]; ctx.moveTo(e.sx, e.sy); ctx.quadraticCurveTo(e.qx, e.qy, e.ex, e.ey); }
      if (level >= 3) {
        ctx.strokeStyle = `rgba(${RGB[color]},${a * 0.16})`;
        ctx.lineWidth = DEPTH_WIDTH[level] * 3.2 * sc;
        ctx.stroke();
      }
      ctx.strokeStyle = `rgba(${RGB[color]},${a})`;
      ctx.lineWidth = DEPTH_WIDTH[level] * sc;
      ctx.stroke();
    }

    // Star neurons: dendrites batched, then bright cell bodies.
    for (let h = 0; h < S.hubs.length; h++) {
      const hub = S.hubs[h];
      rot(hub.x, hub.y, hub.z);
      S.hubSX[h] = cx + rx * r; S.hubSY[h] = cy + ry * r;
      S.hubDepth[h] = clamp((rz + 1) / 2);
      S.hubVis[h] = clamp((pe * 1.3 - hub.order * 0.9) * 6);
    }
    for (const list of dendBuckets) list.length = 0;
    for (let d = 0; d < S.dendrites.length; d++) {
      const den = S.dendrites[d], vis = S.hubVis[den.hub];
      if (vis < 0.05) continue;
      const base = d * DENDRITE_POINTS * 2;
      for (let k = 0; k < DENDRITE_POINTS; k++) {
        rot(den.pts[k * 3], den.pts[k * 3 + 1], den.pts[k * 3 + 2]);
        S.dProj[base + k * 2] = cx + rx * r; S.dProj[base + k * 2 + 1] = cy + ry * r;
      }
      dendBuckets[bucketOf(den.color, S.hubDepth[den.hub], vis)].push(d);
    }
    for (let b = 0; b < BUCKETS; b++) {
      const list = dendBuckets[b];
      if (!list.length) continue;
      const color = Math.floor(b / 15), level = Math.floor((b % 15) / 3), a = Math.min(1, DEPTH_ALPHA[level] * 1.35) * VIS_ALPHA[b % 3];
      // Whole dendrite.
      ctx.beginPath();
      for (const d of list) {
        const base = d * DENDRITE_POINTS * 2;
        ctx.moveTo(S.dProj[base], S.dProj[base + 1]);
        for (let k = 1; k < DENDRITE_POINTS; k++) ctx.lineTo(S.dProj[base + k * 2], S.dProj[base + k * 2 + 1]);
      }
      ctx.strokeStyle = `rgba(${RGB[color]},${a * 0.9})`;
      ctx.lineWidth = DEPTH_WIDTH[level] * 0.9 * sc;
      ctx.stroke();
      // Thicker, hotter base near the cell body.
      ctx.beginPath();
      for (const d of list) {
        const base = d * DENDRITE_POINTS * 2;
        ctx.moveTo(S.dProj[base], S.dProj[base + 1]);
        for (let k = 1; k < 3; k++) ctx.lineTo(S.dProj[base + k * 2], S.dProj[base + k * 2 + 1]);
      }
      if (level >= 2) {
        ctx.strokeStyle = `rgba(${RGB[color]},${a * 0.22})`;
        ctx.lineWidth = DEPTH_WIDTH[level] * 4.5 * sc;
        ctx.stroke();
      }
      ctx.strokeStyle = `rgba(${RGB[color === BLUE ? BLUE : HOT]},${a * 0.85})`;
      ctx.lineWidth = DEPTH_WIDTH[level] * 1.7 * sc;
      ctx.stroke();
    }
    for (let h = 0; h < S.hubs.length; h++) {
      const v = S.hubVis[h];
      if (v <= 0) continue;
      const hub = S.hubs[h], d = S.hubDepth[h], big = hub.major ? 1.5 : 1;
      spr(hub.blue ? SB : SA, S.hubSX[h], S.hubSY[h], 34 * sc * big * (0.45 + 0.75 * d), (0.14 + 0.56 * d) * v);
      spr(SW, S.hubSX[h], S.hubSY[h], 15 * sc * big * (0.45 + d), (0.15 + 0.85 * d) * v);
      if (hub.major && d > 0.5) spr(SW, S.hubSX[h], S.hubSY[h], 7 * sc * big, d * v);
    }

    // Small neurons on the shell.
    for (let i = 0; i < S.n; i++) {
      const d = (S.zs[i] + 1) / 2;
      if (d < 0.3) continue;
      const v = clamp((pe * 1.3 - (i / S.n) * 0.5 - 0.1) * 5);
      if (v <= 0) continue;
      spr(i % 6 === 0 ? SB : SA, cx + S.xs[i] * r, cy + S.ys[i] * r, (3 + 4 * d) * sc, 0.5 * d * v);
    }
    // Discrete signals on the web.
    for (const p of S.pulses) {
      const e = S.edges[p.edge];
      if (e.vis < 0.9 || e.depth < 0.4) continue;
      const u = 1 - p.t;
      spr(SW, u * u * e.sx + 2 * u * p.t * e.qx + p.t * p.t * e.ex, u * u * e.sy + 2 * u * p.t * e.qy + p.t * p.t * e.ey, 10 * sc * (0.5 + e.depth), 0.9 * Math.sin(Math.PI * p.t));
    }
    // Nucleus: a steady hot centre that swells with her voice while she speaks.
    const voice = 0.5 + 0.5 * (Math.sin(time * 11.3) * 0.55 + Math.sin(time * 17.1 + 1.3) * 0.3 + Math.sin(time * 4.7) * 0.15);
    const nr = r * (0.04 + 0.1 * nucleusWake) * (1 + 0.32 * spk * voice + 0.14 * lis);
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, nr * 3.2);
    g.addColorStop(0, `rgba(255,246,220,${0.95 * nucleusWake})`);
    g.addColorStop(0.2, `rgba(255,190,100,${0.5 * nucleusWake})`);
    g.addColorStop(1, "rgba(255,130,40,0)");
    ctx.globalAlpha = 1;
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(cx, cy, nr * 3.2, 0, TAU); ctx.fill();

    // Crisp glowing rim.
    const rim = ctx.createRadialGradient(cx, cy, r * 0.8, cx, cy, r * 1.04);
    rim.addColorStop(0, "rgba(255,160,60,0)");
    rim.addColorStop(0.78, `rgba(255,165,70,${0.34 * pe})`);
    rim.addColorStop(1, "rgba(255,160,60,0)");
    ctx.fillStyle = rim;
    ctx.beginPath(); ctx.arc(cx, cy, r * 1.04, 0, TAU); ctx.fill();
    ctx.strokeStyle = `rgba(255,208,140,${0.4 * pe})`;
    ctx.lineWidth = 1.3 * sc;
    ctx.beginPath(); ctx.arc(cx, cy, r * 0.992, 0, TAU); ctx.stroke();

    // Voice behaviour: listening draws light inward, thinking runs arcs around
    // the rim, speaking sends ripples outward in time with the voice.
    if (lis > 0.01) {
      for (let k = 0; k < 3; k++) {
        const t = (time * 0.55 + k / 3) % 1;
        ctx.strokeStyle = `rgba(${RGB[BLUE]},${0.62 * lis * Math.sin(Math.PI * t) * pe})`;
        ctx.lineWidth = (1.6 - t) * 1.4 * sc;
        ctx.beginPath(); ctx.arc(cx, cy, r * (1.48 - 0.42 * t), 0, TAU); ctx.stroke();
      }
    }
    if (thk > 0.01) {
      const a1 = time * 2.4, a2 = -time * 1.7;
      ctx.lineWidth = 2.2 * sc;
      ctx.strokeStyle = `rgba(${RGB[HOT]},${0.7 * thk * pe})`;
      for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.arc(cx, cy, r * 1.1, a1 + k * TAU / 3, a1 + k * TAU / 3 + 0.75); ctx.stroke(); }
      ctx.lineWidth = 1.2 * sc;
      ctx.strokeStyle = `rgba(${RGB[BLUE]},${0.55 * thk * pe})`;
      for (let k = 0; k < 2; k++) { ctx.beginPath(); ctx.arc(cx, cy, r * 1.17, a2 + k * Math.PI, a2 + k * Math.PI + 1.1); ctx.stroke(); }
    }
    if (spk > 0.01) {
      for (let k = 0; k < 3; k++) {
        const t = (time * 0.8 + k / 3) % 1;
        ctx.strokeStyle = `rgba(${RGB[HOT]},${0.5 * spk * (1 - t) * (0.45 + 0.55 * voice) * pe})`;
        ctx.lineWidth = (2.2 - 1.4 * t) * sc;
        ctx.beginPath(); ctx.arc(cx, cy, r * (1.0 + 0.55 * t), 0, TAU); ctx.stroke();
      }
    }

    // Dust and sparks drifting off the surface.
    for (const m of motes) {
      const life = m.age / m.life;
      if (life <= 0 || life >= 1) continue;
      spr(m.blue ? SB : SA, cx + m.x * r, cy + m.y * r, m.size * sc, 0.75 * Math.sin(Math.PI * life) * pe);
    }

    // Side particle streams drift from the sphere toward the stage edges.
    const fanReach = state.ringed ? 0 : smooth(clamp((pe - 0.55) / 0.45));
    if (fanReach > 0) {
      for (const fan of fans) {
        for (const p of fan.particles) {
          const t = (p.t + time * p.speed) % 1;
          if (t > fanReach) continue;
          const [x, y] = pointAt(fan.paths[p.path], FAN_SAMPLES, t);
          const fade = Math.pow(1 - t, 0.55) * Math.min(1, t * 12);
          const size = p.size * sc * (1.2 - 0.4 * t) * (p.spark ? 1.7 : 1);
          const sprite = p.spark ? SW : t < 0.18 ? SA : p.blue ? SB : SA;
          spr(sprite, x, y + p.spread * (0.25 + t), size, fade);
        }
      }
    }

    }
    // Module nerves grow out of the core as each module wakes (not with the rings).
    if (jv) drawHologram();
    if (state.ringed && !vl) drawRings(true);
    if (!state.ringed) geo.forEach((b, bi) => {
      const wake = nodeWakeLevel(state.progress, bi);
      if (wake <= 0) return;
      const upto = Math.max(1, Math.round(wake * (STRAND_SAMPLES - 1)));
      const rootGlow = smooth(clamp((wake - 0.4) / 0.25));
      ctx.globalAlpha = 1;
      if (rootGlow > 0) {
        for (let j = 0; j < b.roots.length; j++) {
          const q = b.roots[j];
          ctx.strokeStyle = `rgba(${j % 3 === 1 ? RGB[BLUE] : RGB[AMBER]},${0.55 * rootGlow})`;
          ctx.lineWidth = (j < 2 ? 1.2 : 0.7) * sc;
          ctx.beginPath(); ctx.moveTo(q[0], q[1]); ctx.quadraticCurveTo(q[2], q[3], q[4], q[5]); ctx.stroke();
        }
      }
      const surface = Math.round((STRAND_SAMPLES - 1) * 0.5);
      for (const s of b.strands) {
        const col = s.blue ? RGB[BLUE] : RGB[AMBER];
        ctx.beginPath(); tracePolyline(s.pts, 0, Math.min(upto, surface));
        ctx.strokeStyle = `rgba(${col},${s.alpha * 0.35})`;
        ctx.lineWidth = s.width * 0.8 * sc;
        ctx.stroke();
        if (upto <= surface) continue;
        ctx.beginPath(); tracePolyline(s.pts, surface - 2, upto);
        ctx.strokeStyle = `rgba(${col},${s.alpha * 0.14})`;
        ctx.lineWidth = s.width * 3.4 * sc;
        ctx.stroke();
        ctx.strokeStyle = `rgba(${col},${s.alpha})`;
        ctx.lineWidth = s.width * sc;
        ctx.stroke();
        if (s.width > 1.4) {
          ctx.strokeStyle = s.blue ? "rgba(214,236,255,.7)" : "rgba(255,232,196,.75)";
          ctx.lineWidth = 0.55 * sc;
          ctx.stroke();
        }
      }
      if (rootGlow > 0) {
        spr(SA, b.exitX, b.exitY, 30 * sc, 0.7 * rootGlow);
        spr(SW, b.exitX, b.exitY, 11 * sc, 0.95 * rootGlow);
      }
      if (wake > 0.96) spr(b.tone === "blue" ? SB : SA, b.sockX, b.sockY, 28 * sc, 0.7);
      const rate = (state.processing ? 1.8 : 1) + thk * 0.6 + spk * 0.4;
      for (const s of b.strands) {
        const t = (time * s.speed * rate + s.offset) % 1;
        if (t > wake) continue;
        const [x, y] = pointAt(s.pts, STRAND_SAMPLES, t);
        spr(s.blue ? SB : SW, x, y, 12 * sc, 0.95 * Math.sin(Math.PI * Math.min(1, t * 1.05)) + 0.05);
      }
    });
    ctx.globalAlpha = 1;

    // Shared bloom makes the sphere and its branches read as one light source.
    if (canBlur && bctx) {
      bctx.setTransform(1, 0, 0, 1, 0, 0);
      bctx.clearRect(0, 0, bloom.width, bloom.height);
      bctx.filter = "blur(8px)";
      bctx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, bloom.width, bloom.height);
      bctx.filter = "none";
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = 0.36;
      ctx.drawImage(bloom, 0, 0, canvas.width, canvas.height);
      ctx.globalAlpha = 1;
    }
    if (vl && ringReveal > 0) {
      // The void: nothing comes out of the middle. Then the photon ring, the swirling lensed ring of nerves, and the
      // near side of the disk crossing in front.
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.globalCompositeOperation = "source-over";
      const hr = r * vl.hole;
      const edge = ctx.createRadialGradient(cx, cy, hr * 0.96, cx, cy, r * 1.02);
      edge.addColorStop(0, "rgba(0,0,0,1)");
      edge.addColorStop(vl.contained ? 0.8 : 0.35, `rgba(0,0,0,${vl.contained ? 0.9 : 0.55})`);
      edge.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = edge;
      if (!vl.clear) { ctx.beginPath(); ctx.arc(cx, cy, r * 1.02, 0, TAU); ctx.fill(); }
      ctx.fillStyle = "#000";
      ctx.beginPath(); ctx.arc(cx, cy, hr, 0, TAU); ctx.fill();
      ctx.globalCompositeOperation = "lighter";
      const glow = (1 + lis * 0.25 + spk * 0.35) * ringReveal;
      if (vl.clear) {
        // The lensed ring: a thick band of light wrapped round the void, brightest at the upper left like the photo.
        for (let i = 0; i < 34; i++) {
          const rad = hr * (1.01 + i * 0.016 + 0.004 * Math.sin(time * 0.8 + i * 1.7));
          const cone = ctx.createConicGradient(-Math.PI * 0.95 + Math.sin(time * 0.2) * 0.1, cx, cy);
          const a = Math.min(1, Math.max(0, 1.35 - i * 0.03) * glow);
          cone.addColorStop(0, `rgba(${vl.hot},${a})`);
          cone.addColorStop(0.18, `rgba(${vl.mid},${a * 0.75})`);
          cone.addColorStop(0.45, `rgba(${vl.mid},${a * 0.28})`);
          cone.addColorStop(0.7, `rgba(${vl.cool},${a * 0.18})`);
          cone.addColorStop(0.88, `rgba(${vl.mid},${a * 0.6})`);
          cone.addColorStop(1, `rgba(${vl.hot},${a})`);
          ctx.strokeStyle = cone;
          ctx.lineWidth = (i < 4 ? 2.4 : 1.4) * sc;
          ctx.beginPath(); ctx.ellipse(cx, cy, rad * 1.03, rad, roll * 0.25, 0, TAU); ctx.stroke();
        }
      }
      for (let i = 0; i < (vl.clear ? 0 : 18); i++) {
        const rad = hr * (1.02 + i * 0.03 + 0.006 * Math.sin(time * 0.7 + i));
        const start = (i * 0.83 + time * (0.35 - i * 0.008)) % TAU;
        const len = TAU * (0.45 + ((i * 53) % 10) / 22);
        const a = Math.max(0, vl.contained ? 1 - i * 0.045 : 0.5 - i * 0.026) * glow;
        ctx.strokeStyle = `rgba(${i < 6 ? vl.hot : i < 16 ? vl.mid : vl.cool},${a})`;
        ctx.lineWidth = (i < 3 ? (vl.contained ? 2.6 : 1.8) : vl.contained ? 1.4 : 1) * sc;
        ctx.beginPath(); ctx.ellipse(cx, cy, rad * 1.02, rad, roll * 0.2, start, start + len); ctx.stroke();
      }
      const halo = ctx.createRadialGradient(cx, cy, hr, cx, cy, hr * 2.3);
      halo.addColorStop(0, `rgba(${vl.ring},${0.14 * glow})`);
      halo.addColorStop(0.3, `rgba(${vl.mid},${0.05 * glow})`);
      halo.addColorStop(1, `rgba(${vl.ring},0)`);
      ctx.fillStyle = halo;
      ctx.beginPath(); ctx.arc(cx, cy, hr * 2.3, 0, TAU); ctx.arc(cx, cy, hr, 0, TAU, true); ctx.fill();
      ctx.strokeStyle = `rgba(${vl.ring},${0.95 * glow})`;
      ctx.lineWidth = 1.8 * sc;
      ctx.beginPath(); ctx.arc(cx, cy, hr * 1.005, 0, TAU); ctx.stroke();
      ctx.globalCompositeOperation = "source-over";
      drawRings(true);
    }
    ctx.globalCompositeOperation = "source-over";
  };

  // Frames are requested only while something moves. A still core (motion
  // off, or the app in the background) draws once and then costs nothing;
  // setState, setLayout or the window becoming visible wakes the loop again.
  const schedule = () => { if (!raf) raf = requestAnimationFrame(loop); };
  const loop = (now: number) => {
    raf = 0;
    if (!L || document.hidden) { last = now; return; }
    const elapsed = now - last;
    const progressChanged = drawnProgress !== state.progress;
    if (!state.motion && !progressChanged && !dirty) return;
    // ~33 fps while you're using the app or she's busy; ~11 fps in the
    // background (window not focused and she's not thinking or speaking).
    const background = !document.hasFocus() && state.phase !== "thinking" && state.phase !== "speaking" && !state.processing;
    if (state.motion && elapsed < (background ? 90 : 30)) { schedule(); return; }
    last = now;
    const dt = Math.min(64, elapsed);
    if (state.motion) {
      const pe = smooth(clamp(state.progress / 100));
      const rate = (state.processing ? 1.8 : 1) + thk * 0.6 + spk * 0.4;
      spin += dt * (0.00012 + (1 - pe) * 0.0006 + thk * 0.00025);
      const ease = Math.min(1, dt / 260);
      lis += ((state.phase === "listening" ? 1 : 0) - lis) * ease;
      thk += ((state.phase === "thinking" ? 1 : 0) - thk) * ease;
      spk += ((state.phase === "speaking" ? 1 : 0) - spk) * ease;
      time += dt / 1000;
      for (const p of S.pulses) {
        p.t += dt * p.speed * rate;
        if (p.t > 1) { p.t = 0; p.edge = Math.floor(Math.random() * S.edges.length); }
      }
      for (const m of motes) {
        m.age += dt / 1000;
        m.x += m.vx * dt / 1000; m.y += m.vy * dt / 1000;
        if (m.age > m.life) spawnMote(m);
      }
    }
    draw();
    drawnProgress = state.progress;
    dirty = false;
    if (state.motion) schedule();
  };
  const onVisibility = () => { if (!document.hidden) { dirty = true; schedule(); } };
  document.addEventListener("visibilitychange", onVisibility);
  schedule();

  return {
    setLayout(next) {
      L = next;
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.max(1, Math.round(next.width * dpr));
      canvas.height = Math.max(1, Math.round(next.height * dpr));
      bloom.width = Math.max(1, Math.round(next.width * 0.5));
      bloom.height = Math.max(1, Math.round(next.height * 0.5));
      geo = next.orbs.length ? BRANCHES.map((b, i) => buildBranch(b, next.orbs[i], next, i)) : [];
      fans = next.compact ? [] : [buildFan(-1, next), buildFan(1, next)];
      dirty = true;
      schedule();
    },
    setState(next) {
      state = next;
      // Without motion the phase still shows, just without easing.
      if (!next.motion) { lis = next.phase === "listening" ? 1 : 0; thk = next.phase === "thinking" ? 1 : 0; spk = next.phase === "speaking" ? 1 : 0; }
      dirty = true;
      schedule();
    },
    destroy() {
      cancelAnimationFrame(raf);
      raf = 0;
      document.removeEventListener("visibilitychange", onVisibility);
    },
  };
}
