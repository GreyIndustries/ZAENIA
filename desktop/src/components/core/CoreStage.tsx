import { useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { computeLayout } from "./neuralField";

// One neural core for the whole app (Claude, 2026-11-11). The core renders once into a host element that
// moves between slots (Home centre, the chat mic on other pages, phone Home, Calm view) instead of remounting,
// so its animation never resets. The highest-priority mounted slot holds it; with no slot mounted it is
// detached and pauses itself. A move between two visible places glides (C5: 0.55 s into or out of the mic).

type Slot = { el: HTMLElement; priority: number; order: number };
type Sphere = { x: number; y: number; r: number; k: number; cx: number; cy: number };
const slots: Slot[] = [];
let host: HTMLDivElement | null = null;
let order = 0;
let last: Sphere | null = null;
const MOVE = "transform .55s cubic-bezier(.2,.8,.2,1)";

function coreHost() {
  if (!host) { host = document.createElement("div"); host.className = "core-host"; }
  return host;
}

/** Where the core's sphere is on screen (its rings are drawn around it). */
function sphere(el: Element | null): Sphere | null {
  if (!(el instanceof HTMLElement) || !el.isConnected) return null;
  const w = el.offsetWidth, h = el.offsetHeight;
  if (w < 2 || h < 2) return null;
  const box = el.getBoundingClientRect();
  const k = box.width / w;
  const at = computeLayout(w, h, true);
  return { x: box.left + at.cx * k, y: box.top + at.cy * k, r: at.r * k, k, cx: at.cx, cy: at.cy };
}

function stillMotion() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  const motion = document.querySelector<HTMLElement>(".zaenia-app")?.dataset.motion;
  return motion !== "off" && motion !== "reduced";
}

/** Glide the core from where it was to where it now is (FLIP), without touching its canvas. */
function glide(core: HTMLElement, from: Sphere | null, to: Sphere | null) {
  if (!from || !to || !stillMotion()) return;
  if (Math.abs(from.x - to.x) < 2 && Math.abs(from.y - to.y) < 2 && Math.abs(from.r - to.r) < 2) return;
  core.style.transition = "none";
  core.style.transformOrigin = `${to.cx}px ${to.cy}px`;
  core.style.transform = `translate(${(from.x - to.x) / to.k}px, ${(from.y - to.y) / to.k}px) scale(${from.r / to.r})`;
  void core.offsetWidth;
  core.style.transition = MOVE;
  core.style.transform = "";
  const done = (event: TransitionEvent) => {
    if (event.target !== core) return;
    core.style.transition = ""; core.style.transformOrigin = "";
    core.removeEventListener("transitionend", done);
  };
  core.addEventListener("transitionend", done);
}

function place() {
  const el = coreHost();
  const core = el.firstElementChild as HTMLElement | null;
  const top = slots.reduce<Slot | null>((best, slot) => !best || slot.priority > best.priority || (slot.priority === best.priority && slot.order > best.order) ? slot : best, null);
  const target = top?.el ?? null;
  if (el.parentNode === target && target) return;
  const from = sphere(core) ?? last;
  if (target) target.appendChild(el); else el.remove();
  if (core && target) {
    const to = sphere(core);
    glide(core, from, to);
    if (to) last = to;
  }
  window.dispatchEvent(new CustomEvent("zae:core-moved"));
}

/** Keep the last on-screen spot fresh (called on layout events) so a glide starts where the core really was. */
export function rememberCore(core: Element) {
  const at = sphere(core);
  if (at && !(core as HTMLElement).style.transform) last = at;
}

/** Where the core shows. Calm view outranks the mic, which outranks the dashboard. */
export function CoreSlot({ priority = 0 }: { priority?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const slot = { el: ref.current!, priority, order: ++order };
    slots.push(slot);
    place();
    return () => { slots.splice(slots.indexOf(slot), 1); place(); };
  }, [priority]);
  return <div ref={ref} className="core-slot"/>;
}

/** Renders the single core instance into the moving host. */
export function CorePortal({ children }: { children: ReactNode }) {
  return createPortal(children, coreHost());
}
