/**
 * A small 3D stage for the SE pictures (Grey, 2026-11-04): the perspective is worked out by hand and drawn on a plain
 * 2D canvas, so nothing new is installed. Drag to turn it, hover for details, and it rests while it is off screen
 * or the window is hidden. Scenes (constellation.ts, tetra.ts) only describe what to draw each frame.
 */
export type RGB = readonly [number, number, number];
/** A point after projection: x/y on the canvas, z for depth sorting, s for size, X/Y/Z after the turn. */
export type P3 = { x: number; y: number; z: number; s: number; X: number; Y: number; Z: number };
/** What hovering a part shows. The key changes whenever the text does, so the page only redraws it when needed. */
export type Tip = { key: string; title: string; color: string; sub?: string; lines: string[]; note?: string };
export type Hit = { x: number; y: number; r: number; tip: Tip };
export type Cam = {
  yaw: number; pitch: number; vYaw: number; vPitch: number;
  w: number; h: number; dpr: number; sc: number; cx: number; cy: number; px: number; py: number; f: number;
  font: string;
  p: (x: number, y: number, z: number) => P3;
};
/** Called once per frame. `dt` is 0 when the person asked for reduced motion, so a scene must still draw a still picture. */
export type DrawFn = (ctx: CanvasRenderingContext2D, cam: Cam, time: number, dt: number, hits: Hit[]) => void;
export type StageOptions = { yaw?: number; pitch?: number; auto?: number; sway?: number; fitW?: number; fitH?: number; cx?: number; cy?: number };
export type Scene = { draw: DrawFn; options: StageOptions };
export type TipHandler = (hit: Hit | null, bounds: { w: number; h: number }) => void;

export const TAU = Math.PI * 2;
export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
/** A colour string; an alpha that is not a number draws as clear instead of breaking the whole picture. */
export const rgba = (c: RGB, a: number) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${Number.isFinite(a) ? clamp(a, 0, 1) : 0})`;
export const mix = (a: RGB, b: RGB, t: number): RGB => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
/** A small repeatable random source, so a scene is built the same way every time. */
export function seeded(seed: number) { let s = seed; return () => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; }; }
export const cross = (a: readonly number[], b: readonly number[]): [number, number, number] => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

export const AMBER: RGB = [255, 179, 71];
export const BLUE: RGB = [90, 162, 255];
export const VIOLET: RGB = [180, 124, 255];
export const TEAL: RGB = [79, 227, 180];
export const CREAM: RGB = [255, 242, 207];
export const RED: RGB = [255, 122, 89];
export const SLATE: RGB = [143, 167, 194];
export const css = (c: RGB) => `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})`;

// ---- drawing helpers

export function glow(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, c: RGB, a: number) {
  if (!(r > 0) || !(a > 0) || !Number.isFinite(x) || !Number.isFinite(y)) return;
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, rgba(c, a)); g.addColorStop(0.4, rgba(c, a * 0.35)); g.addColorStop(1, rgba(c, 0));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
}

/** A glowing ball with a highlight, like a small lit sphere. */
export function orb(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, c: RGB, a: number, halo = 3.2) {
  if (!(r > 0) || !Number.isFinite(x) || !Number.isFinite(y)) return;
  ctx.save(); ctx.globalCompositeOperation = "lighter"; glow(ctx, x, y, r * (halo + a * 2.4), c, 0.22 + 0.45 * a); ctx.restore();
  const g = ctx.createRadialGradient(x - r * 0.38, y - r * 0.42, r * 0.05, x, y, r * 1.05);
  g.addColorStop(0, "rgba(255,255,255,.96)"); g.addColorStop(0.3, rgba(c, 1)); g.addColorStop(1, rgba([c[0] * 0.28, c[1] * 0.28, c[2] * 0.28], 1));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
  ctx.strokeStyle = rgba(c, 0.8); ctx.lineWidth = 1; ctx.stroke();
}

export type LabelOptions = { size?: number; weight?: number; align?: CanvasTextAlign; alpha?: number; color?: string; italic?: boolean };
export function label(ctx: CanvasRenderingContext2D, cam: Cam, text: string, x: number, y: number, o: LabelOptions = {}) {
  ctx.font = `${o.italic ? "italic " : ""}${o.weight ?? 600} ${o.size ?? 12}px ${cam.font}`;
  ctx.textAlign = o.align ?? "center"; ctx.textBaseline = "middle";
  ctx.shadowColor = "rgba(0,0,0,.95)"; ctx.shadowBlur = 6; ctx.globalAlpha = o.alpha ?? 1; ctx.fillStyle = o.color ?? "#e4edf8";
  ctx.fillText(text, x, y); ctx.shadowBlur = 0; ctx.globalAlpha = 1;
}
/** A label size that grows a little on big stages and never gets unreadable on a phone. */
export const fontSize = (cam: Cam, n: number) => Math.max(10, Math.round(n * Math.max(0.9, Math.min(1.25, cam.sc))));

/** Faint rings and spokes on the floor of the picture, to give the eye a ground to stand on. */
export function floorGrid(ctx: CanvasRenderingContext2D, cam: Cam, y: number, R: number, c: RGB) {
  ctx.save(); ctx.globalCompositeOperation = "lighter"; ctx.lineWidth = 1;
  for (const r of [R * 0.34, R * 0.66, R]) {
    ctx.beginPath();
    for (let k = 0; k <= 72; k++) { const a = k / 72 * TAU, q = cam.p(Math.cos(a) * r, y, Math.sin(a) * r); if (k) ctx.lineTo(q.x, q.y); else ctx.moveTo(q.x, q.y); }
    ctx.strokeStyle = rgba(c, 0.11); ctx.stroke();
  }
  for (let k = 0; k < 18; k++) {
    const a = k / 18 * TAU, q1 = cam.p(Math.cos(a) * R * 0.34, y, Math.sin(a) * R * 0.34), q2 = cam.p(Math.cos(a) * R, y, Math.sin(a) * R);
    ctx.beginPath(); ctx.moveTo(q1.x, q1.y); ctx.lineTo(q2.x, q2.y); ctx.strokeStyle = rgba(c, 0.055); ctx.stroke();
  }
  ctx.restore();
}

// ---- the stage: camera, drag to turn, hover details, rest while off screen

/**
 * Starts drawing a scene on the canvas and returns the function that stops it.
 * `onTip` hears about the part under the pointer (or null) after each frame.
 */
export function mountStage(canvas: HTMLCanvasElement, draw: DrawFn, onTip: TipHandler, o: StageOptions = {}): () => void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => undefined;
  const reduced = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hits: Hit[] = [];
  const cam: Cam = {
    yaw: o.yaw ?? 0.5, pitch: o.pitch ?? 0.3, vYaw: 0, vPitch: 0, w: 0, h: 0, dpr: 1, sc: 1, cx: 0, cy: 0, px: 0.5, py: 0.5, f: 950,
    font: "system-ui, sans-serif",
    p(x, y, z) {
      const c1 = Math.cos(cam.vYaw), s1 = Math.sin(cam.vYaw), X = x * c1 + z * s1, Z0 = -x * s1 + z * c1;
      const c2 = Math.cos(cam.vPitch), s2 = Math.sin(cam.vPitch), Y = y * c2 - Z0 * s2, Z = y * s2 + Z0 * c2;
      const s = cam.f / (cam.f - Z);
      return { x: cam.cx + X * s * cam.sc, y: cam.cy - Y * s * cam.sc, z: Z, s: s * cam.sc, X, Y, Z };
    },
  };
  let drag: { x: number; y: number; yaw: number; pitch: number } | null = null;
  let mouse: { x: number; y: number } | null = null;
  let visible = true, alive = true, raf = 0, last = performance.now(), time = 0, cost = 0;

  const resize = () => {
    const r = canvas.getBoundingClientRect();
    cam.dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.max(1, Math.round(r.width * cam.dpr)); canvas.height = Math.max(1, Math.round(r.height * cam.dpr));
    cam.w = r.width; cam.h = r.height; cam.cx = cam.w * (o.cx ?? 0.5); cam.cy = cam.h * (o.cy ?? 0.5);
    cam.sc = Math.max(0.2, Math.min(cam.w / (o.fitW ?? 540), cam.h / (o.fitH ?? 430)));
    cam.font = getComputedStyle(canvas).fontFamily || cam.font;
    if (reduced) frame(performance.now(), true);
  };
  const resizer = new ResizeObserver(resize);
  const viewer = new IntersectionObserver(entries => { visible = entries[entries.length - 1]?.isIntersecting ?? true; });

  const down = (e: PointerEvent) => { try { canvas.setPointerCapture(e.pointerId); } catch { /* optional */ } drag = { x: e.clientX, y: e.clientY, yaw: cam.yaw, pitch: cam.pitch }; };
  const move = (e: PointerEvent) => {
    const r = canvas.getBoundingClientRect();
    mouse = { x: e.clientX - r.left, y: e.clientY - r.top }; cam.px = mouse.x / Math.max(1, r.width); cam.py = mouse.y / Math.max(1, r.height);
    if (drag) { cam.yaw = drag.yaw + (e.clientX - drag.x) * 0.01; cam.pitch = clamp(drag.pitch + (e.clientY - drag.y) * 0.008, -0.25, 1.3); }
    if (reduced) frame(performance.now(), true);
  };
  const stop = () => { drag = null; };
  const leave = () => { mouse = null; cam.px = 0.5; cam.py = 0.5; };

  function pick() {
    if (!mouse) { onTip(null, { w: cam.w, h: cam.h }); return; }
    let best: Hit | null = null, bestDistance = 1e9;
    for (const h of hits) {
      const d = Math.hypot(h.x - mouse.x, h.y - mouse.y);
      if (d < Math.max(h.r, 16) && d < bestDistance) { best = h; bestDistance = d; }
    }
    onTip(best, { w: cam.w, h: cam.h });
  }

  function frame(now: number, force = false) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (!force && (!visible || document.hidden)) return;
    const stepped = reduced ? 0 : dt;
    time += stepped;
    if (!drag && !reduced) cam.yaw += (o.auto ?? 0.1) * dt;
    cam.vYaw = cam.yaw + (o.sway ? o.sway * Math.sin(time * 0.33) : 0) + (drag ? 0 : (cam.px - 0.5) * 0.3);
    cam.vPitch = clamp(cam.pitch + (drag ? 0 : (cam.py - 0.5) * 0.12), -0.3, 1.4);
    ctx!.setTransform(cam.dpr, 0, 0, cam.dpr, 0, 0); ctx!.clearRect(0, 0, cam.w, cam.h); hits.length = 0;
    const began = performance.now();
    try { draw(ctx!, cam, time, stepped, hits); }
    catch (failure) { alive = false; console.error("SE picture stopped:", failure); return; }
    cost = cost * 0.9 + (performance.now() - began) * 0.1;
    pick();
  }
  const loop = (now: number) => {
    if (!alive) return;
    raf = requestAnimationFrame(loop);
    if (reduced) { last = now; return; }
    // about 70 pictures a second at most, so a fast screen doesn't burn power; half that when a picture is slow to draw (a phone)
    if (now - last < (cost > 11 ? 32 : 14)) return;
    frame(now);
  };

  canvas.addEventListener("pointerdown", down); canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerup", stop); canvas.addEventListener("pointercancel", stop); canvas.addEventListener("pointerleave", leave);
  resizer.observe(canvas); viewer.observe(canvas);
  resize();
  raf = requestAnimationFrame(loop);
  // With reduced motion the picture stays still, but it is drawn again every second so it still follows the live state
  const refresh = reduced ? window.setInterval(() => { if (alive && visible && !document.hidden) frame(performance.now(), true); }, 1000) : 0;
  return () => {
    alive = false; cancelAnimationFrame(raf); window.clearInterval(refresh); resizer.disconnect(); viewer.disconnect();
    canvas.removeEventListener("pointerdown", down); canvas.removeEventListener("pointermove", move);
    canvas.removeEventListener("pointerup", stop); canvas.removeEventListener("pointercancel", stop); canvas.removeEventListener("pointerleave", leave);
    onTip(null, { w: cam.w, h: cam.h });
  };
}
