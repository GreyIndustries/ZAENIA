/**
 * Hand gestures for actions (Grey's list, 2026-10-31). Hand landmarks in, one action out. Pure logic: no camera or
 * DOM. Most actions also have a voice command; the camera can't tell whose hand it is, so nothing sensitive is here.
 *
 *  swipe left / right (open hand) → previous / next tab     swipe up → Home        swipe down → minimise tab
 *  hold 1–5 fingers ~1 s → category 1 Plan, 2 Health, 3 Know, 4 Create, 5 Build     rock sign → System
 *  Explicit shortcut mode only. Open palm always means Stop; pinch is reserved for manipulation.
 *  fist held → Calm view     peace sign (V, fingers spread) → mic on/off
 *  thumbs up → confirm the card ZAE is showing     thumbs down → dismiss it
 */
export type Point = { x: number; y: number; z?: number };
export type HandShape = "one" | "two" | "peace" | "three" | "four" | "five" | "rock" | "fist" | "thumbsUp" | "thumbsDown" | "pinch" | "other";
export type GestureAction =
  | { kind: "previous" } | { kind: "next" } | { kind: "home" } | { kind: "minimize" } | { kind: "close" }
  | { kind: "category"; index: number } | { kind: "system" } | { kind: "stop" } | { kind: "calm" } | { kind: "mic" }
  | { kind: "confirm" } | { kind: "dismiss" };
export type GestureFrame = { shape: HandShape | null; holding: { label: string; progress: number } | null; action: GestureAction | null };

const dist = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);

/** Which hand shape this is (single frame). */
export function shapeOf(points: readonly Point[]): HandShape | null {
  if (points.length !== 21 || points.some(p => !Number.isFinite(p.x) || !Number.isFinite(p.y))) return null;
  const scale = dist(points[0], points[9]);
  if (!(scale > 0.02)) return null;
  const up = [8, 12, 16, 20].map(tip => dist(points[tip], points[0]) > dist(points[tip - 2], points[0]) * 1.18);
  const [index, middle, ring, pinky] = up;
  // Thumb out: its tip is well away from the index knuckle and the palm.
  const thumbOut = dist(points[4], points[5]) / scale > 0.75 && dist(points[4], points[9]) / scale > 0.8;
  // A pinch keeps the index finger out from the palm; in a fist the thumb also rests on a curled index finger.
  if (dist(points[4], points[8]) / scale < 0.25 && !middle && dist(points[8], points[0]) > dist(points[5], points[0]) * 1.05) return "pinch";
  if (!index && !middle && !ring && !pinky) {
    // Thumbs up / down: the thumb stands straight out of the fist, mostly vertical. In a plain fist it lies
    // across the fingers, mostly sideways.
    const dx = (points[4].x - points[2].x) / scale, dy = (points[4].y - points[2].y) / scale;
    if (Math.abs(dy) > 0.6 && Math.abs(dy) > 2 * Math.abs(dx) && dist(points[4], points[0]) > dist(points[3], points[0]) * (dy < 0 ? 1 : 0.9)) {
      return dy < 0 ? "thumbsUp" : "thumbsDown";
    }
    return "fist";
  }
  if (index && pinky && !middle && !ring) return "rock";
  if (index && middle && ring && pinky) return thumbOut ? "five" : "four";
  if (index && middle && ring && !pinky) return "three";
  if (index && middle && !ring && !pinky) return dist(points[8], points[12]) / scale > 0.55 ? "peace" : "two";
  if (index && !middle && !ring && !pinky) return "one";
  return "other";
}

const HOLDS: Partial<Record<HandShape, { ms: number; label: string }>> = {
  one: { ms: 900, label: "1 · Plan" }, two: { ms: 900, label: "2 · Health" }, three: { ms: 900, label: "3 · Know" },
  four: { ms: 900, label: "4 · Create" }, rock: { ms: 800, label: "System" },
  fist: { ms: 900, label: "Calm view" }, peace: { ms: 700, label: "Mic on/off" },
  thumbsUp: { ms: 600, label: "Confirm" }, thumbsDown: { ms: 600, label: "Dismiss" },
};
const ACTION_OF: Partial<Record<HandShape, GestureAction>> = {
  one: { kind: "category", index: 0 }, two: { kind: "category", index: 1 }, three: { kind: "category", index: 2 },
  four: { kind: "category", index: 3 }, rock: { kind: "system" }, fist: { kind: "calm" },
  peace: { kind: "mic" }, thumbsUp: { kind: "confirm" }, thumbsDown: { kind: "dismiss" },
};

export class GestureActions {
  private shape: HandShape | null = null;
  private since = 0;
  private fired = false;
  private lastAction = -Infinity;
  private track: { x: number; y: number; at: number }[] = [];
  static COOLDOWN = 1200; static SWIPE = 0.2; static SWIPE_MS = 450; static STOP_MS = 450;

  reset() { this.shape = null; this.fired = false; this.track = []; }

  update(points: readonly Point[] | null, at: number, _speaking = false): GestureFrame {
    const shape = points ? shapeOf(points) : null;
    if (!points || !shape) { this.reset(); return { shape: null, holding: null, action: null }; }
    const cool = at - this.lastAction >= GestureActions.COOLDOWN;
    if (shape !== this.shape) { this.shape = shape; this.since = at; this.fired = false; }
    if (shape === "five") {
      if (this.fired || !cool) return { shape, holding: null, action: null };
      const progress = Math.min(1, (at - this.since) / GestureActions.STOP_MS);
      if (progress >= 1) { this.fired = true; this.lastAction = at; return { shape, holding: null, action: { kind: "stop" } }; }
      return { shape, holding: { label: "Stop talking", progress }, action: null };
    }
    // Swipes: an open hand (4 or 5 fingers) moving fast. The palm centre is steadier than a fingertip.
    const palm = { x: 1 - (points[0].x + points[9].x) / 2, y: (points[0].y + points[9].y) / 2 };
    if (shape === "four") {
      this.track.push({ ...palm, at });
      this.track = this.track.filter(p => at - p.at <= GestureActions.SWIPE_MS);
      const first = this.track[0];
      const dx = palm.x - first.x, dy = palm.y - first.y;
      if (cool && (Math.abs(dx) > GestureActions.SWIPE || Math.abs(dy) > GestureActions.SWIPE)) {
        this.track = []; this.lastAction = at; this.fired = true;
        const action: GestureAction = Math.abs(dx) >= Math.abs(dy) ? { kind: dx > 0 ? "next" : "previous" } : { kind: dy < 0 ? "home" : "minimize" };
        return { shape, holding: null, action };
      }
      // A moving hand is a swipe in progress, not a hold.
      if (this.track.length > 1 && Math.hypot(dx, dy) > 0.05) { this.since = at; return { shape, holding: null, action: null }; }
    } else this.track = [];
    if (this.fired || !cool) return { shape, holding: null, action: null };
    const hold = HOLDS[shape];
    if (!hold) return { shape, holding: null, action: null };
    const progress = Math.min(1, (at - this.since) / hold.ms);
    if (progress >= 1) { this.fired = true; this.lastAction = at; return { shape, holding: null, action: ACTION_OF[shape] ?? null }; }
    return { shape, holding: progress > 0.15 ? { label: hold.label, progress } : null, action: null };
  }
}

/** Bones to draw in the camera preview: pairs of landmark indexes. */
export const BONES: readonly [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];

export const ACTION_LABEL: Record<GestureAction["kind"], string> = {
  previous: "Previous tab", next: "Next tab", home: "Home", minimize: "Minimise tab", close: "Close tab", category: "Category",
  system: "System", stop: "Stopped", calm: "Calm view", mic: "Mic", confirm: "Confirmed", dismiss: "Dismissed",
};
