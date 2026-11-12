/**
 * "SE Stack" (Grey's pick for the security model, 2026-11-04): ZAE's defenses as a hologram tower. Four slabs are the four
 * groups of defenses, coloured by how strong each is right now (teal strong, amber fair, red weak, grey not measured);
 * the glowing plate on top is the security gate with the score; signals climb the pillars, faster as failed or blocked
 * attempts add up.
 */
import { AMBER, CREAM, SLATE, TAU, cross, fontSize, glow, label, lerp, mix, rgba, type DrawFn, type RGB, type Scene, type Tip } from "./engine";
import { LEVEL_COLOR, type Strength } from "./levels";

export type StackLayer = { name: string; sub: string; level: Strength; tip: Tip };
export type StackFeed = {
  /** Four layers, bottom first. Read every frame. */
  layers: () => StackLayer[];
  gate: () => { name: string; word: string; score: number; level: Strength; tip: Tip };
  /** How fast signals climb (0 to 1) and whether anything needs a look. */
  trail: () => { speed: number; alert: boolean };
};

type Face = { pts: { x: number; y: number }[]; z: number; c: RGB; a: number; edge: RGB; ea: number };
type BoxOptions = { c: RGB; aTop: number; aSide: number; ea: number };

// A box from (cx, y) up by h with a w by d footprint. Only faces turned toward the viewer are returned; the caller paints far to near.
function boxFaces(cam: Parameters<DrawFn>[1], cx: number, y: number, cz: number, w: number, h: number, d: number, o: BoxOptions): Face[] {
  const x0 = cx - w / 2, x1 = cx + w / 2, y0 = y, y1 = y + h, z0 = cz - d / 2, z1 = cz + d / 2, P = cam.p;
  const v = [P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1), P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)];
  const defs: [number[], string][] = [[[4, 7, 6, 5], "top"], [[3, 2, 6, 7], "front"], [[2, 1, 5, 6], "right"], [[1, 0, 4, 5], "back"], [[0, 3, 7, 4], "left"], [[0, 1, 2, 3], "bottom"]];
  const out: Face[] = [];
  for (const [idx, kind] of defs) {
    const a = v[idx[0]], b = v[idx[1]], c = v[idx[2]];
    const n = cross([b.X - a.X, b.Y - a.Y, b.Z - a.Z], [c.X - a.X, c.Y - a.Y, c.Z - a.Z]);
    if (n[2] <= 0) continue;
    const pts = idx.map(i => v[i]), z = pts.reduce((s, q) => s + q.z, 0) / 4;
    const alpha = kind === "top" ? o.aTop : kind === "front" || kind === "right" ? o.aSide * 1.25 : kind === "bottom" ? o.aSide * 0.5 : o.aSide * 0.7;
    out.push({ pts, z, c: o.c, a: Math.min(1, alpha), edge: o.c, ea: o.ea });
  }
  return out;
}

function paint(ctx: CanvasRenderingContext2D, faces: Face[]) {
  faces.sort((a, b) => a.z - b.z);
  for (const f of faces) {
    ctx.beginPath(); f.pts.forEach((q, i) => { if (i) ctx.lineTo(q.x, q.y); else ctx.moveTo(q.x, q.y); }); ctx.closePath();
    ctx.fillStyle = rgba(f.c, f.a); ctx.fill(); ctx.strokeStyle = rgba(f.edge, f.ea); ctx.lineWidth = 1; ctx.stroke();
  }
}

export function stackScene(feed: StackFeed): Scene {
  const W = 190, H = 15, STEP = 58, Y0 = -120;
  let phase = 0;
  const draw: DrawFn = (ctx, cam, t, dt, hits) => {
    const thin = Math.max(0.7, cam.sc), layers = feed.layers(), gate = feed.gate(), trail = feed.trail();
    if (layers.length < 4) return;
    phase += dt * (0.18 + 0.5 * trail.speed);
    const colour = layers.map(l => LEVEL_COLOR[l.level]);
    const flick = layers.map((l, i) => l.level === "weak" ? 0.65 + 0.35 * Math.sin(t * 5 + i * 1.3) : 1);
    const gateColour = mix(CREAM, LEVEL_COLOR[gate.level], 0.3), gateY = Y0 + 4 * STEP;

    const faces: Face[] = [];
    layers.slice(0, 4).forEach((_l, i) => faces.push(...boxFaces(cam, 0, Y0 + i * STEP, 0, W, H, W, { c: colour[i], aTop: 0.3 * flick[i], aSide: 0.24 * flick[i], ea: 0.85 })));
    faces.push(...boxFaces(cam, 0, gateY, 0, W * 0.78, 6, W * 0.78, { c: gateColour, aTop: 0.55, aSide: 0.4, ea: 1 }));
    paint(ctx, faces);

    ctx.save(); ctx.globalCompositeOperation = "lighter"; ctx.lineCap = "round";
    // four pillars with signals climbing
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      const x = sx * (W / 2 - 9), z = sz * (W / 2 - 9), a = cam.p(x, Y0, z), b = cam.p(x, gateY, z);
      ctx.strokeStyle = rgba(AMBER, 0.3); ctx.lineWidth = 1.6 * thin; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      for (let k = 0; k < 3; k++) { const u = (phase + k / 3 + (sx + sz) * 0.11 + 1) % 1; glow(ctx, lerp(a.x, b.x, u), lerp(a.y, b.y, u), 6 * thin, trail.alert ? [255, 170, 140] : AMBER, 0.35 + 0.4 * trail.speed); }
    }
    // the gate's ring and glow
    const gc = cam.p(0, gateY + 6, 0);
    for (const r of [26, 40]) {
      ctx.beginPath(); for (let k = 0; k <= 48; k++) { const a = k / 48 * TAU, q = cam.p(Math.cos(a) * r, gateY + 40, Math.sin(a) * r); if (k) ctx.lineTo(q.x, q.y); else ctx.moveTo(q.x, q.y); }
      ctx.strokeStyle = rgba(gateColour, 0.45 + 0.3 * Math.sin(t * 2 + r)); ctx.lineWidth = 1.3 * thin; ctx.stroke();
    }
    glow(ctx, gc.x, gc.y - 10 * thin, 30 * thin, gateColour, 0.3 + 0.4 * (gate.score / 100));
    ctx.restore();
    const gl = cam.p(0, gateY + 40, 0);
    label(ctx, cam, gate.name, gl.x, gl.y - 20 * thin, { size: fontSize(cam, 12), color: "#fff2cf" });
    label(ctx, cam, gate.word, gl.x, gl.y - 6 * thin, { size: fontSize(cam, 11), color: rgba(gateColour, 1), weight: 500 });
    const gm = cam.p(0, gateY + 3, 0);
    hits.push({ x: gm.x, y: gm.y, r: 50 * thin, tip: gate.tip });

    // names on the right, joined to their slabs by a dotted line
    const lx = cam.w * 0.68;
    layers.slice(0, 4).forEach((l, i) => {
      const q = cam.p(W / 2, Y0 + i * STEP + H / 2, 0), c = colour[i] ?? SLATE;
      ctx.strokeStyle = rgba(c, 0.5); ctx.lineWidth = 1; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(lx, q.y); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = rgba(c, 0.95); ctx.beginPath(); ctx.arc(lx, q.y, 2.8, 0, TAU); ctx.fill();
      label(ctx, cam, l.name, lx + 10, q.y - 7 * thin, { size: fontSize(cam, 13), align: "left", color: rgba(mix(c, [255, 255, 255], 0.35), 1) });
      label(ctx, cam, l.sub, lx + 10, q.y + 8 * thin, { size: fontSize(cam, 10.5), align: "left", color: "#8fa7c2", weight: 500 });
      hits.push({ x: q.x - 40 * thin, y: q.y, r: 50 * thin, tip: l.tip });
    });
  };
  return { draw, options: { yaw: 0.62, pitch: 0.5, auto: 0.07, sway: 0.22, cx: 0.31, cy: 0.52, fitW: 420, fitH: 400 } };
}
