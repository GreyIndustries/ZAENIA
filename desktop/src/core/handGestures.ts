/** Landmarks only: no camera, image storage, identity or face inference here. */
export type Point = { x: number; y: number; z?: number };
export type HandPose = { kind: "point" | "pinch" | "spread" | "palm" | "fist"; x: number; y: number; span: number };
export type GestureCommand = { kind: "point" | "move" | "resize" | "release" | "stop" | "next" | "previous" | "minimize"; x?: number; y?: number; span?: number };
const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);
export function classifyHand(points: readonly Point[]): HandPose | null {
  if (points.length !== 21 || points.some(point => !Number.isFinite(point.x) || !Number.isFinite(point.y))) return null;
  const scale = distance(points[0], points[9]);
  if (scale < .025) return null;
  const extended = [8, 12, 16, 20].map(tip => distance(points[tip], points[0]) > distance(points[tip - 2], points[0]) * 1.2);
  const span = distance(points[4], points[8]) / scale;
  const kind = span < .28 ? "pinch" : extended.every(Boolean) ? "palm" : extended[0] && extended[1] && !extended[2] && !extended[3] ? "spread" : extended[0] && !extended[1] && !extended[2] && !extended[3] ? "point" : "fist";
  return { kind, x: Math.min(1, Math.max(0, 1 - points[8].x)), y: Math.min(1, Math.max(0, points[8].y)), span: kind === "spread" ? distance(points[8], points[12]) / scale : span };
}
export class GestureInterpreter {
  private previous: HandPose["kind"] | null = null;
  private began = 0;
  private lastAction = -Infinity;
  private anchor: { x: number; y: number; at: number } | null = null;
  private palmTriggered = false;
  reset() { this.previous = null; this.began = 0; this.anchor = null; this.palmTriggered = false; }
  update(hand: HandPose | null, now: number): GestureCommand[] {
    if (!hand) { const release = this.previous === "pinch" || this.previous === "spread"; this.reset(); return release ? [{ kind: "release" }] : []; }
    const commands: GestureCommand[] = [];
    if (hand.kind !== this.previous) {
      if (this.previous === "pinch" || this.previous === "spread") commands.push({ kind: "release" });
      this.previous = hand.kind; this.began = now; this.anchor = { x: hand.x, y: hand.y, at: now };
      this.palmTriggered = false;
    }
    if (hand.kind === "pinch") commands.push({ kind: "move", x: hand.x, y: hand.y });
    else if (hand.kind === "spread") commands.push({ kind: "resize", x: hand.x, y: hand.y, span: hand.span });
    else if (hand.kind === "palm" && !this.palmTriggered && now - this.began >= 450 && now - this.lastAction > 1800) { commands.push({ kind: "stop" }); this.lastAction = now; this.palmTriggered = true; }
    else if (hand.kind === "point" && now - this.began >= 250) commands.push({ kind: "point", x: hand.x, y: hand.y });
    else if (hand.kind === "fist" && this.anchor && now - this.anchor.at < 650 && now - this.lastAction > 1200) {
      const dx = hand.x - this.anchor.x, dy = hand.y - this.anchor.y;
      if (Math.abs(dx) > .2 || dy > .22) { commands.push({ kind: dy > .22 && dy > Math.abs(dx) ? "minimize" : dx > 0 ? "next" : "previous" }); this.lastAction = now; this.anchor = null; }
    }
    return commands;
  }
}
