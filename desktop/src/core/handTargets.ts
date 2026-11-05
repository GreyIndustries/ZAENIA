import type { HandFrame } from "./handGestures";
import type { GestureAction } from "./gestureActions";

export type VisualHandMotion = NonNullable<HandFrame["motion"]>;
export const HAND_MODEL_EVENT = "zae:model-hand-motion";
export const HAND_ACTIVITY_EVENT = "zae:hand-activity";
const ACTIONS = ["previous", "next", "home", "minimize", "close"] as const;
type HandTarget = { key: string; name: string; element: HTMLElement; kind: "model" | "window" | "action"; id: string };
let nextModel = 0;

/** Only explicit presentation surfaces participate. Never synthesize a click on arbitrary app content. */
export function handTargetAt(x: number, y: number): HandTarget | null {
  const hit = document.elementFromPoint(x, y);
  if (!(hit instanceof HTMLElement) || hit.closest("[data-hand-blocked],.calm,.faceid-approve,.near-code")) return null;
  const action = hit.closest<HTMLElement>("[data-hand-action]");
  if (action && !action.matches(":disabled") && ACTIONS.includes(action.dataset.handAction as typeof ACTIONS[number])) {
    const id = action.dataset.handAction!;
    return { key: `action:${id}`, name: action.textContent?.trim() || id, element: action, kind: "action", id };
  }
  const model = hit.closest<HTMLElement>("[data-hand-model]");
  if (model && model.querySelector(".se-fusion__canvas")) {
    model.dataset.handModel ||= `se-${++nextModel}`;
    return { key: `model:${model.dataset.handModel}`, name: "SE model", element: model, kind: "model", id: model.dataset.handModel };
  }
  if (hit.closest("button,input,textarea,select,[contenteditable=true],.os-window__controls")) return null;
  const bar = hit.closest<HTMLElement>(".os-window__bar");
  const win = bar?.closest<HTMLElement>(".os-window[data-window-id]");
  if (!win?.dataset.windowId) return null;
  return { key: `window:${win.dataset.windowId}`, name: win.getAttribute("aria-label") || "Window", element: win, kind: "window", id: win.dataset.windowId };
}

/** Holds one visible target until release. Camera data can change presentation only. */
export class HandTargetSession {
  private hovered: HandTarget | null = null;
  private grabbed: HandTarget | null = null;
  constructor(private windowMotion: (id: string, motion: VisualHandMotion) => boolean, private action: (action: GestureAction) => void) {}
  get name() { return (this.grabbed ?? this.hovered)?.name ?? null; }
  resolve = (cursor: { x: number; y: number }): string | null => {
    if (this.grabbed) return this.grabbed.key;
    const target = handTargetAt(cursor.x * window.innerWidth, cursor.y * window.innerHeight);
    if (target?.key !== this.hovered?.key) {
      this.hovered?.element.classList.remove("hand-target");
      this.hovered = target;
      target?.element.classList.add("hand-target");
    }
    return target?.key ?? null;
  };
  consume(frame: HandFrame): boolean {
    if ((!frame.cursor || frame.phase === "idle") && !this.grabbed) this.clear();
    const motion = frame.motion;
    if (!motion) return true;
    if (motion.kind === "begin") {
      const target = this.hovered;
      if (!target || target.key !== motion.target || !this.visible(target)) return false;
      if (target.kind === "action") {
        this.action({ kind: target.id } as GestureAction);
        return true;
      }
      if (target.kind === "window" && !this.windowMotion(target.id, motion)) return false;
      this.grabbed = target;
      target.element.classList.add("hand-grabbed");
      if (target.kind === "model") target.element.dispatchEvent(new CustomEvent(HAND_MODEL_EVENT, { detail: motion }));
    } else {
      const target = this.grabbed;
      if (!target || target.key !== motion.target) return false;
      if (!this.visible(target)) { this.clear(); return false; }
      if (target.kind === "window") {
        if (!this.windowMotion(target.id, motion)) { this.clear(); return false; }
      } else target.element.dispatchEvent(new CustomEvent(HAND_MODEL_EVENT, { detail: motion }));
      if (motion.kind === "end") this.clear(false);
    }
    return true;
  }
  private visible(target: HandTarget): boolean {
    const box = target.element.getBoundingClientRect();
    return target.element.isConnected && box.width > 0 && box.height > 0 && getComputedStyle(target.element).visibility !== "hidden";
  }
  clear(notify = true): void {
    const target = this.grabbed;
    if (notify && target) {
      const end: VisualHandMotion = { kind: "end", target: target.key, x: 0, y: 0, dx: 0, dy: 0, scale: 1, angle: 0, twoHands: false, reason: "cancelled" };
      if (target.kind === "window") this.windowMotion(target.id, end);
      else target.element.dispatchEvent(new CustomEvent(HAND_MODEL_EVENT, { detail: end }));
    }
    this.hovered?.element.classList.remove("hand-target");
    target?.element.classList.remove("hand-target", "hand-grabbed");
    this.hovered = null; this.grabbed = null;
  }
}
