/**
 * Taught hand poses (Grey, 2026-11-05): hold any hand pose to teach it, name it, and choose what it does. A pose is kept as
 * 21 hand points moved to the wrist and scaled by palm size, so it matches at any distance. Saved on this PC only; camera
 * images are never kept. Pure logic: no camera, no DOM.
 */
export type PosePoint = { x: number; y: number };
export type PoseAction = { kind: "close" | "minimize" | "previous" | "next" | "home" | "calm" | "mic" } | { kind: "command"; text: string };
export type TaughtPose = { id: string; name: string; template: number[]; action: PoseAction };

export const POSE_ACTIONS: { id: Exclude<PoseAction["kind"], "command">; name: string }[] = [
  { id: "close", name: "Close window" }, { id: "minimize", name: "Minimize window" }, { id: "previous", name: "Previous tab" },
  { id: "next", name: "Next tab" }, { id: "home", name: "Home" }, { id: "calm", name: "Calm view" }, { id: "mic", name: "Mic on or off" },
];
export const POSES_KEY = "zaenia.handPoses";
export const POSES_EVENT = "zae:hand-poses";
export const MAX_POSES = 10, MAX_NAME = 30, MAX_COMMAND = 160;
/** Mean distance (in palm sizes) under which a hand counts as that pose, and how much closer than the runner-up it must be. */
export const MATCH_LIMIT = 0.12, MATCH_MARGIN = 0.03;

const kinds = new Set<string>(POSE_ACTIONS.map(action => action.id));
export const cleanLabel = (value: unknown, max: number): string =>
  typeof value === "string" ? value.replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, max) : "";

/** The 42 numbers that describe a hand pose, or null when the points are unusable. */
export function template(points: readonly PosePoint[] | null | undefined): number[] | null {
  if (!points || points.length !== 21 || points.some(p => !p || !Number.isFinite(p.x) || !Number.isFinite(p.y))) return null;
  const scale = Math.hypot(points[9].x - points[0].x, points[9].y - points[0].y);
  if (!(scale > 0.02)) return null;
  const out: number[] = [];
  for (const p of points) out.push(Math.round((p.x - points[0].x) / scale * 1000) / 1000, Math.round((p.y - points[0].y) / scale * 1000) / 1000);
  return out;
}

/** Mean distance between two templates, in palm sizes. */
export function distance(a: readonly number[], b: readonly number[]): number {
  if (a.length !== 42 || b.length !== 42) return Infinity;
  let sum = 0;
  for (let i = 0; i < 42; i += 2) sum += Math.hypot(a[i] - b[i], a[i + 1] - b[i + 1]);
  return sum / 21;
}

/** Averages several frames of a held pose; null if there are too few or the hand moved around too much to be one pose. */
export function buildPose(frames: readonly (number[] | null)[]): number[] | null {
  const good = frames.filter((f): f is number[] => !!f && f.length === 42);
  if (good.length < 8) return null;
  const mean = good[0].map((_, i) => good.reduce((sum, f) => sum + f[i], 0) / good.length);
  if (good.some(f => distance(f, mean) > 0.1)) return null;
  return mean.map(v => Math.round(v * 1000) / 1000);
}

/** Makes a matcher for a list of taught poses. The best pose must be close enough and clearly closer than the next one. */
export function makeMatcher(poses: readonly TaughtPose[]): (points: readonly PosePoint[]) => TaughtPose | null {
  return points => {
    if (!poses.length) return null;
    const now = template(points);
    if (!now) return null;
    const ranked = poses.map(pose => ({ pose, d: distance(now, pose.template) })).sort((a, b) => a.d - b.d);
    if (ranked[0].d > MATCH_LIMIT) return null;
    if (ranked[1] && ranked[1].d - ranked[0].d < MATCH_MARGIN) return null;
    return ranked[0].pose;
  };
}

/** A saved list made safe: valid templates, a known action, no empty names, no repeated ids, at most MAX_POSES. */
export function normalizePoses(raw: unknown): TaughtPose[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>(), out: TaughtPose[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object" || out.length >= MAX_POSES) continue;
    const { id, name, template: t, action } = item as { id?: unknown; name?: unknown; template?: unknown; action?: unknown };
    const label = cleanLabel(name, MAX_NAME);
    const tmpl = Array.isArray(t) && t.length === 42 && t.every(v => typeof v === "number" && Number.isFinite(v) && Math.abs(v) < 10) ? (t as number[]) : null;
    const safe = normalizeAction(action);
    if (typeof id !== "string" || !id || seen.has(id) || !label || !tmpl || !safe) continue;
    seen.add(id); out.push({ id, name: label, template: tmpl, action: safe });
  }
  return out;
}

/** One action from saved data, or null if it isn't a known action. */
export function normalizeAction(action: unknown): PoseAction | null {
  const kind = action && typeof action === "object" ? (action as { kind?: unknown }).kind : undefined;
  if (typeof kind === "string" && kinds.has(kind)) return { kind: kind as Exclude<PoseAction["kind"], "command"> };
  if (kind === "command") { const text = cleanLabel((action as { text?: unknown }).text, MAX_COMMAND); if (text) return { kind: "command", text }; }
  return null;
}

/** Microphone finger snap: off unless the owner turns it on; one snap and a double snap each get an action. */
export type SnapSettings = { on: boolean; single: PoseAction | null; double: PoseAction | null };
export const SNAP_KEY = "zaenia.handSnap", SNAP_EVENT = "zae:hand-snap";
export function normalizeSnap(raw: unknown): SnapSettings {
  const r = raw && typeof raw === "object" ? raw as { on?: unknown; single?: unknown; double?: unknown } : {};
  const single = normalizeAction(r.single), double = normalizeAction(r.double);
  return { on: r.on === true && !!(single || double), single, double };
}
export function readSnap(): SnapSettings { try { return normalizeSnap(JSON.parse(localStorage.getItem(SNAP_KEY) ?? "null")); } catch { return normalizeSnap(null); } }
export function saveSnap(settings: SnapSettings) {
  try { localStorage.setItem(SNAP_KEY, JSON.stringify(normalizeSnap(settings))); } catch { /* optional preference */ }
  window.dispatchEvent(new Event(SNAP_EVENT));
}

export function readPoses(): TaughtPose[] {
  try { return normalizePoses(JSON.parse(localStorage.getItem(POSES_KEY) ?? "null")); } catch { return []; }
}
export function savePoses(list: TaughtPose[]) {
  try { localStorage.setItem(POSES_KEY, JSON.stringify(normalizePoses(list))); } catch { /* optional preference */ }
  window.dispatchEvent(new Event(POSES_EVENT));
}
