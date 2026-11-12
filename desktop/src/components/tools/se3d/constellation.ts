/**
 * "Neural Constellation" (Grey's pick, 2026-11-04): the SE as a 3D network. Each brain is a cluster of cells, the
 * conductor is the hub in the middle, and signals cascade from cell to cell and flash where they land. A busy brain
 * fires faster; a brain that isn't loaded dims and goes quiet.
 */
import { AMBER, BLUE, CREAM, TEAL, VIOLET, clamp, fontSize, glow, label, lerp, mix, rgba, seeded, type DrawFn, type Hit, type RGB, type Scene, type Tip } from "./engine";

import type { BrainId } from "../seActivity";
export const BRAIN_IDS: BrainId[] = ["talk", "seek", "study", "keep"];
export const BRAIN_COLOR: Record<BrainId, RGB> = { talk: AMBER, seek: BLUE, study: VIOLET, keep: TEAL };
/** How hard a brain is working: 0 asleep, about .4 loaded and resting, 1 working now. A brain that isn't installed is dark. */
/** The built-in parts around the four models (no model of their own): where they sit and how they are coloured. */
export const PARTS = [
  { id: "reasoning", name: "Reasoning", role: "checks answers against evidence", at: [-92, -92, -92], colour: [255, 112, 150] as RGB },
  { id: "memory", name: "Memory", role: "what ZAE remembers about you", at: [-92, 92, 92], colour: [214, 222, 255] as RGB },
  { id: "index", name: "Search & topics", role: "finds related past context", at: [92, -92, 92], colour: [160, 230, 92] as RGB },
  { id: "senses", name: "Ears & voice", role: "hearing in, Talk's voice out", at: [92, 92, -92], colour: [255, 214, 102] as RGB },
] as const;
export type PartReading = { level: number; words: string };
export type BrainSignal = { level: number; installed: boolean };
export type BrainText = { name: string; model: string; job: string; state: string };
export type ConstellationFeed = {
  /** Read every frame, in the order talk, seek, study, keep. */
  signals: () => BrainSignal[];
  text: (id: BrainId) => BrainText;
  tip: (id: BrainId) => Tip;
  hubTip: () => Tip;
  /** The four built-in parts, in the order of PARTS. */
  parts?: () => PartReading[];
  partTip?: (index: number) => Tip;
};

type Cell = { x: number; y: number; z: number; g: number; fl: number };
type Pulse = { e: number; u: number; fwd: boolean; sp: number; hops: number; g: number };

export function constellationScene(feed: ConstellationFeed): Scene {
  const rnd = seeded(31);
  const gauss = () => { let s = 0; for (let i = 0; i < 4; i++) s += rnd(); return (s - 2) * 1.7; };
  const centers = ([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]] as const).map(v => v.map(c => c * 80) as [number, number, number]);
  const sizes = [44, 56, 66, 30];
  const nodes: Cell[] = [];
  centers.forEach((c, g) => { for (let i = 0; i < sizes[g]; i++) nodes.push({ x: c[0] + gauss() * 30, y: c[1] + gauss() * 30, z: c[2] + gauss() * 30, g, fl: 0 }); });
  for (let i = 0; i < 32; i++) nodes.push({ x: gauss() * 22, y: gauss() * 22, z: gauss() * 22, g: 4, fl: 0 });   // the conductor's hub
  PARTS.forEach((part, k) => { for (let i = 0; i < 18; i++) nodes.push({ x: part.at[0] + gauss() * 17, y: part.at[1] + gauss() * 17, z: part.at[2] + gauss() * 17, g: 5 + k, fl: 0 }); });

  const edges: { a: number; b: number }[] = [];
  const seen = new Set<string>();
  const adj: number[][] = nodes.map(() => []);
  const link = (i: number, j: number) => {
    const k = i < j ? `${i}-${j}` : `${j}-${i}`;
    if (seen.has(k)) return;
    seen.add(k); edges.push({ a: i, b: j }); adj[i].push(edges.length - 1); adj[j].push(edges.length - 1);
  };
  const d2 = (a: { x: number; y: number; z: number }, b: { x: number; y: number; z: number }) => (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2;
  nodes.forEach((a, i) => {
    nodes.map((b, j) => [j, d2(a, b)] as const).filter(([j]) => j !== i).sort((p, q) => p[1] - q[1]).slice(0, 3).forEach(([j]) => link(i, j));
  });
  const hub = nodes.map((_, i) => i).filter(i => nodes[i].g === 4);
  const origin = { x: 0, y: 0, z: 0 };
  for (let g = 0; g < 9; g++) {
    nodes.map((_, i) => i).filter(i => nodes[i].g === g).sort((p, q) => d2(nodes[p], origin) - d2(nodes[q], origin)).slice(0, 5).forEach(i => {
      const j = hub.reduce((best, h) => d2(nodes[i], nodes[h]) < d2(nodes[i], nodes[best]) ? h : best, hub[0]);
      link(i, j);
    });
  }
  const byGroup = [0, 1, 2, 3, 4, 5, 6, 7, 8].map(g => edges.map((_, i) => i).filter(i => nodes[edges[i].a].g === g || nodes[edges[i].b].g === g));

  const pulses: Pulse[] = [];
  const acc = [0, 0, 0, 0, 0, 0, 0, 0, 0];
  const act = [0, 0, 0, 0];
  let started = false;
  const colour = (g: number): RGB => g < 4 ? BRAIN_COLOR[BRAIN_IDS[g]] : g === 4 ? CREAM : PARTS[g - 5].colour;

  const draw: DrawFn = (ctx, cam, _time, dt, hits: Hit[]) => {
    const thin = Math.max(0.7, cam.sc);
    const signals = feed.signals();
    for (let i = 0; i < 4; i++) {
      const target = signals[i]?.installed ? clamp(signals[i].level, 0, 1) : 0;
      act[i] = !started || dt === 0 ? target : act[i] + (target - act[i]) * (1 - Math.exp(-dt * 3));
    }
    started = true;
    const parts = feed.parts?.() ?? [];
    const partLevel = (g: number) => clamp(parts[g - 5]?.level ?? 0.3, 0, 1);
    const present = (g: number) => g > 3 || !!signals[g]?.installed;
    const rate = (g: number) => g > 4 ? 0.6 + 5 * partLevel(g) : g > 3 ? 1 + 6 * (act[0] + act[1] + act[2] + act[3]) / 4 : present(g) ? 0.9 + 10 * act[g] : 0;
    const level = (g: number) => g > 4 ? 0.5 + 0.5 * partLevel(g) : g > 3 ? 0.7 + 0.3 * Math.max(...act) : present(g) ? 0.55 + 0.45 * act[g] : 0.22;

    for (let g = 0; g < 9; g++) {
      acc[g] += dt * rate(g);
      while (acc[g] >= 1 && pulses.length < 160) {
        acc[g] -= 1;
        const pool = byGroup[g];
        pulses.push({ e: pool[Math.floor(rnd() * pool.length)], u: 0, fwd: rnd() < 0.5, sp: 0.8 + rnd() * 0.8, hops: 0, g });
      }
      if (acc[g] > 3) acc[g] = 0;
    }
    for (let k = pulses.length - 1; k >= 0; k--) {
      const p = pulses[k];
      p.u += dt * p.sp;
      if (p.u >= 1) {
        const e = edges[p.e], end = p.fwd ? e.b : e.a;
        nodes[end].fl = 1;
        if (p.hops < 6 && rnd() < 0.68) {
          const options = adj[end].filter(x => x !== p.e);
          if (options.length) { const ne = options[Math.floor(rnd() * options.length)]; p.e = ne; p.fwd = edges[ne].a === end; p.u = 0; p.hops++; continue; }
        }
        pulses.splice(k, 1);
      }
    }

    const Q = nodes.map(n => cam.p(n.x, n.y, n.z));
    ctx.save(); ctx.globalCompositeOperation = "lighter"; ctx.lineCap = "round";
    for (const e of edges) {
      const a = Q[e.a], b = Q[e.b], zn = clamp(((a.z + b.z) / 2 + 150) / 300, 0, 1), gA = nodes[e.a].g;
      ctx.strokeStyle = rgba(colour(gA), (0.08 + 0.22 * zn) * (0.5 + 0.5 * level(gA)));
      ctx.lineWidth = (0.7 + 0.8 * zn) * thin;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    nodes.forEach((n, i) => {
      const q = Q[i], zn = clamp((q.z + 120) / 240, 0, 1);
      n.fl = Math.max(0, n.fl - dt * 1.7);
      glow(ctx, q.x, q.y, (3 + n.fl * 10) * q.s, colour(n.g), ((0.45 + 0.45 * zn) + 0.6 * n.fl) * level(n.g));
    });
    for (const p of pulses) {
      const e = edges[p.e], a = Q[p.fwd ? e.a : e.b], b = Q[p.fwd ? e.b : e.a];
      const x = lerp(a.x, b.x, p.u), y = lerp(a.y, b.y, p.u);
      glow(ctx, x, y, 6 * thin, CREAM, 0.9);
      glow(ctx, lerp(a.x, b.x, Math.max(0, p.u - 0.12)), lerp(a.y, b.y, Math.max(0, p.u - 0.12)), 4 * thin, colour(nodes[e.a].g), 0.6);
    }
    ctx.restore();

    const narrow = cam.w < 430;
    centers.forEach((c, g) => {
      const id = BRAIN_IDS[g], text = feed.text(id), q = cam.p(c[0] * 1.42, c[1] * 1.42 + 14, c[2] * 1.42), colourOf = BRAIN_COLOR[id];
      const alpha = present(g) ? 1 : 0.5;
      label(ctx, cam, text.name, q.x, q.y, { size: fontSize(cam, 13), color: rgba(colourOf, 1), alpha });
      label(ctx, cam, text.model, q.x, q.y + 13 * thin, { size: fontSize(cam, 10), color: "#8fa7c2", weight: 500, alpha });
      if (!narrow) label(ctx, cam, text.state, q.x, q.y + 25 * thin, { size: fontSize(cam, 10), color: rgba(mix(colourOf, CREAM, 0.35), 1), weight: 500, alpha: 0.55 + 0.45 * act[g] });
      const m = cam.p(c[0], c[1], c[2]);
      hits.push({ x: m.x, y: m.y, r: 44 * m.s, tip: feed.tip(id) });
    });
    PARTS.forEach((part, k) => {
      const q = cam.p(part.at[0] * 1.18, part.at[1] * 1.18 + 12, part.at[2] * 1.18), m = cam.p(part.at[0], part.at[1], part.at[2]);
      label(ctx, cam, part.name, q.x, q.y, { size: fontSize(cam, 11.5), color: rgba(part.colour, 1) });
      if (!narrow) label(ctx, cam, part.role, q.x, q.y + 12 * thin, { size: fontSize(cam, 9.5), color: "#8fa7c2", weight: 500 });
      if (feed.partTip) hits.push({ x: m.x, y: m.y, r: 34 * m.s, tip: feed.partTip(k) });
    });
    const h0 = cam.p(0, 0, 0);
    label(ctx, cam, "Conductor", h0.x, h0.y - 24 * thin, { size: fontSize(cam, 11), color: "#fff2cf" });
    hits.push({ x: h0.x, y: h0.y, r: 22 * h0.s, tip: feed.hubTip() });
  };
  return { draw, options: { yaw: 0.4, pitch: 0.3, auto: 0.11, sway: 0.1, fitW: 540, fitH: 470 } };
}
