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

/** Local hand landmarks to deliberate UI manipulation. No identity or execution authority. */
export type MotionPoint = { x: number; y: number; z?: number };
export type HandDetection = { points: MotionPoint[]; handedness: string; score: number };
export type HandSettings = { hand: "auto" | "Left" | "Right"; sensitivity: number; range: { left: number; right: number; top: number; bottom: number } };
export type HandMotion = { kind: "begin" | "change" | "end"; target: string; x: number; y: number; dx: number; dy: number; scale: number; angle: number; twoHands: boolean; reason?: string };
export type HandFrame = { cursor: { x: number; y: number } | null; target: string | null; phase: "idle" | "hover" | "arming" | "grab" | "two-hand"; progress: number; motion: HandMotion | null; stop: boolean };

export const DEFAULT_HAND_SETTINGS: HandSettings = { hand: "auto", sensitivity: 1, range: { left: 0.12, right: 0.88, top: 0.12, bottom: 0.88 } };
const motionClamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
const motionDistance = (a: MotionPoint, b: MotionPoint) => Math.hypot(a.x - b.x, a.y - b.y);
const motionFinite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
export function normalizeHandSettings(value: unknown): HandSettings {
  const raw = value && typeof value === "object" ? value as Partial<HandSettings> : {};
  const range = raw.range && typeof raw.range === "object" ? raw.range : DEFAULT_HAND_SETTINGS.range;
  const read = (key: keyof HandSettings["range"]) => motionFinite(range[key]) ? motionClamp(range[key], 0, 1) : DEFAULT_HAND_SETTINGS.range[key];
  let left = read("left"), right = read("right"), top = read("top"), bottom = read("bottom");
  if (right - left < 0.25) { left = DEFAULT_HAND_SETTINGS.range.left; right = DEFAULT_HAND_SETTINGS.range.right; }
  if (bottom - top < 0.25) { top = DEFAULT_HAND_SETTINGS.range.top; bottom = DEFAULT_HAND_SETTINGS.range.bottom; }
  return { hand: raw.hand === "Left" || raw.hand === "Right" ? raw.hand : "auto", sensitivity: motionFinite(raw.sensitivity) ? motionClamp(raw.sensitivity, 0.4, 2) : 1, range: { left, right, top, bottom } };
}

type MotionSample = { input: HandDetection; center: MotionPoint; pinch: number; point: boolean; palm: boolean };
type MotionIdentity = { center: MotionPoint; handedness: string };
function sampleMotionHand(input: HandDetection): MotionSample | null {
  if (!input || !Array.isArray(input.points) || input.points.length !== 21 || !motionFinite(input.score) || input.score < 0.6 || input.score > 1 || !["Left", "Right"].includes(input.handedness)) return null;
  const p = input.points;
  if (p.some(q => !q || !motionFinite(q.x) || !motionFinite(q.y) || q.x < -0.2 || q.x > 1.2 || q.y < -0.2 || q.y > 1.2 || (q.z !== undefined && !motionFinite(q.z)))) return null;
  const scale = motionDistance(p[0], p[9]);
  if (scale < 0.025) return null;
  const extended = [8, 12, 16, 20].map(tip => motionDistance(p[tip], p[0]) > motionDistance(p[tip - 2], p[0]) * 1.15);
  const pinch = motionDistance(p[4], p[8]) / scale;
  return { input, center: { x: (p[0].x + p[9].x) / 2, y: (p[0].y + p[9].y) / 2 }, pinch,
    point: extended[0] && !extended[1] && !extended[2] && !extended[3] && pinch > 0.42,
    palm: extended.every(Boolean) && pinch > 0.42 };
}
const motionIdentity = (hand: MotionSample): MotionIdentity => ({ center: hand.center, handedness: hand.input.handedness });
/** Array order is never a tracking ID. Reject ties and large jumps rather than transfer control. */
function followMotionHand(previous: MotionIdentity, candidates: MotionSample[]): MotionSample | null {
  const nearest = candidates.filter(hand => hand.input.handedness === previous.handedness)
    .map(hand => ({ hand, d: motionDistance(previous.center, hand.center) })).filter(item => item.d <= 0.18).sort((a, b) => a.d - b.d);
  if (!nearest.length || (nearest[1] && nearest[1].d - nearest[0].d < 0.035)) return null;
  return nearest[0].hand;
}
const motionPinched = (hand: MotionSample, was: boolean) => hand.pinch < (was ? 0.42 : 0.28);
const motionAngleDifference = (next: number, before: number) => Math.atan2(Math.sin(next - before), Math.cos(next - before));

export class HandMotionController {
  readonly settings: HandSettings;
  private lastAt: number | null = null;
  private primary: MotionIdentity | null = null;
  private secondary: MotionIdentity | null = null;
  private cursor: MotionPoint | null = null;
  private secondaryCursor: MotionPoint | null = null;
  private previousCursor: MotionPoint | null = null;
  private hoverTarget: string | null = null;
  private hoverSince = 0;
  private readyTarget: string | null = null;
  private pinchSince: number | null = null;
  private needsOpen = true;
  private primaryPinch = false;
  private secondaryPinch = false;
  private grabbed: string | null = null;
  private pair: { span: number; angle: number } | null = null;
  private palmSince: number | null = null;
  private palmFired = false;

  constructor(settings: unknown = DEFAULT_HAND_SETTINGS) { this.settings = normalizeHandSettings(settings); }
  reset(): void {
    this.lastAt = null; this.primary = this.secondary = null; this.cursor = this.secondaryCursor = this.previousCursor = null;
    this.hoverTarget = this.readyTarget = this.grabbed = null; this.hoverSince = 0; this.pinchSince = null;
    this.needsOpen = true; this.primaryPinch = this.secondaryPinch = false; this.pair = null; this.palmSince = null; this.palmFired = false;
  }
  private frame(phase: HandFrame["phase"] = "idle", target: string | null = null, motion: HandMotion | null = null, progress = 0, stop = false): HandFrame {
    return { cursor: this.cursor ? { x: this.cursor.x, y: this.cursor.y } : null, target, phase, progress, motion, stop };
  }
  private map(point: MotionPoint): MotionPoint {
    const { range, sensitivity } = this.settings;
    return { x: motionClamp(((1 - point.x - range.left) / (range.right - range.left) - 0.5) * sensitivity + 0.5, 0, 1),
      y: motionClamp(((point.y - range.top) / (range.bottom - range.top) - 0.5) * sensitivity + 0.5, 0, 1) };
  }
  private smooth(before: MotionPoint | null, next: MotionPoint, dt: number): MotionPoint {
    const alpha = before ? 1 - Math.exp(-dt / 65) : 1;
    return { x: before ? before.x + (next.x - before.x) * alpha : next.x, y: before ? before.y + (next.y - before.y) * alpha : next.y };
  }
  private motion(kind: HandMotion["kind"], target: string, dx = 0, dy = 0, scale = 1, angle = 0, twoHands = false, reason?: string): HandMotion {
    return { kind, target, x: this.cursor?.x ?? 0.5, y: this.cursor?.y ?? 0.5, dx, dy, scale, angle, twoHands, ...(reason ? { reason } : {}) };
  }
  private end(reason: string): HandMotion | null {
    const result = this.grabbed ? this.motion("end", this.grabbed, 0, 0, 1, 0, !!this.pair, reason) : null;
    this.grabbed = this.readyTarget = this.hoverTarget = null; this.pinchSince = null; this.needsOpen = true;
    this.previousCursor = this.secondaryCursor = null; this.secondary = null; this.pair = null; this.secondaryPinch = false;
    return result;
  }

  update(hands: HandDetection[], at: number, targetAt: (cursor: { x: number; y: number }) => string | null): HandFrame {
    if (!motionFinite(at) || at < 0 || (this.lastAt !== null && at <= this.lastAt)) {
      const ended = this.end("stale frame"); this.primary = null; this.primaryPinch = false; this.cursor = null;
      this.palmSince = null; this.palmFired = false;
      return this.frame("idle", null, ended);
    }
    const dt = this.lastAt === null ? 40 : at - this.lastAt;
    this.lastAt = at;
    if (dt > 350 && this.primary) {
      const ended = this.end("tracking gap"); this.primary = null; this.cursor = null; this.primaryPinch = false;
      this.palmSince = null; this.palmFired = false; return this.frame("idle", null, ended);
    }
    const candidates = Array.isArray(hands) ? hands.map(sampleMotionHand).filter((hand): hand is MotionSample => hand !== null) : [];
    const hand = this.primary ? followMotionHand(this.primary, candidates) : candidates
      .filter(item => this.settings.hand === "auto" || item.input.handedness === this.settings.hand)
      .sort((a, b) => b.input.score - a.input.score)[0] ?? null;
    if (!hand) {
      const ended = this.end("hand lost"); this.primary = null; this.cursor = null; this.primaryPinch = false;
      this.palmSince = null; this.palmFired = false; return this.frame("idle", null, ended);
    }
    this.primary = motionIdentity(hand);
    this.cursor = this.smooth(this.cursor, this.map(hand.input.points[8]), dt);
    this.primaryPinch = motionPinched(hand, this.primaryPinch);

    let stop = false;
    if (hand.palm) {
      if (this.palmSince === null) this.palmSince = at;
      if (!this.palmFired && at - this.palmSince >= 450) { stop = true; this.palmFired = true; }
    } else { this.palmSince = null; this.palmFired = false; }

    if (this.grabbed) {
      if (!this.primaryPinch) return this.frame("idle", null, this.end("released"), 0, stop);
      const others = candidates.filter(item => item !== hand);
      const other = this.secondary ? followMotionHand(this.secondary, others) : others.sort((a, b) => b.input.score - a.input.score)[0] ?? null;
      if (other) {
        this.secondary = motionIdentity(other);
        this.secondaryPinch = motionPinched(other, this.secondaryPinch);
        this.secondaryCursor = this.smooth(this.secondaryCursor, this.map(other.input.points[8]), dt);
      } else { this.secondary = null; this.secondaryPinch = false; this.secondaryCursor = null; }
      const span = this.secondaryCursor ? motionDistance(this.cursor, this.secondaryCursor) : 0;
      const usePair = this.secondaryPinch && span >= 0.08;
      const angle = this.secondaryCursor ? Math.atan2(this.secondaryCursor.y - this.cursor.y, this.secondaryCursor.x - this.cursor.x) : 0;
      const rebasing = usePair !== !!this.pair;
      const center = usePair && this.secondaryCursor ? { x: (this.cursor.x + this.secondaryCursor.x) / 2, y: (this.cursor.y + this.secondaryCursor.y) / 2 } : this.cursor;
      const dx = rebasing ? 0 : motionClamp(center.x - (this.previousCursor?.x ?? center.x), -0.055, 0.055);
      const dy = rebasing ? 0 : motionClamp(center.y - (this.previousCursor?.y ?? center.y), -0.055, 0.055);
      const scale = usePair && this.pair ? motionClamp(span / this.pair.span, 0.8, 1.25) : 1;
      const twist = usePair && this.pair ? motionClamp(motionAngleDifference(angle, this.pair.angle), -0.18, 0.18) : 0;
      this.pair = usePair ? { span, angle } : null; this.previousCursor = { ...center };
      return this.frame(usePair ? "two-hand" : "grab", this.grabbed, this.motion("change", this.grabbed, dx, dy, scale, twist, usePair), 1, stop);
    }

    let target: string | null = null;
    try { const found = targetAt({ x: this.cursor.x, y: this.cursor.y }); target = typeof found === "string" && found.length > 0 ? found : null; } catch { /* no target is safer than a guessed one */ }
    if (hand.point && !this.primaryPinch) {
      this.needsOpen = false; this.pinchSince = null;
      if (target !== this.hoverTarget) { this.hoverTarget = target; this.hoverSince = at; this.readyTarget = null; }
      if (target && at - this.hoverSince >= 180) this.readyTarget = target;
      return this.frame(target ? "hover" : "idle", target, null, target ? motionClamp((at - this.hoverSince) / 180, 0, 1) : 0, stop);
    }
    if (this.primaryPinch && !this.needsOpen && target && target === this.readyTarget) {
      if (this.pinchSince === null) this.pinchSince = at;
      const progress = motionClamp((at - this.pinchSince) / 180, 0, 1);
      if (progress >= 1) {
        this.grabbed = target; this.previousCursor = { ...this.cursor }; this.pair = null;
        return this.frame("grab", target, this.motion("begin", target), 1, stop);
      }
      return this.frame("arming", target, null, progress, stop);
    }
    this.readyTarget = this.hoverTarget = null; this.pinchSince = null;
    if (this.primaryPinch) this.needsOpen = true;
    return this.frame("idle", null, null, 0, stop);
  }
}
