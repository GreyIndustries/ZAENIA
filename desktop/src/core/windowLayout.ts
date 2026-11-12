export type WindowRect = { x: number; y: number; w: number; h: number };
export type ResizeEdge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
export const MIN_WINDOW_WIDTH = .26, MIN_WINDOW_HEIGHT = .3;
export type SnapCount = 2 | 3 | 4;
export const isMaximized = (rect: WindowRect) => rect.w >= .95 && rect.h >= .94;
/** Windows-style two panes, large-left/stacked-right, or four quadrants. */
export function snapRectangles(count: SnapCount): WindowRect[] {
  const half = .494, next = .506;
  if (count === 2) return [{ x: 0, y: 0, w: half, h: 1 }, { x: next, y: 0, w: half, h: 1 }];
  if (count === 3) return [{ x: 0, y: 0, w: half, h: 1 }, { x: next, y: 0, w: half, h: half }, { x: next, y: next, w: half, h: half }];
  return [{ x: 0, y: 0, w: half, h: half }, { x: next, y: 0, w: half, h: half }, { x: 0, y: next, w: half, h: half }, { x: next, y: next, w: half, h: half }];
}
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
const finite = (value: number, fallback: number) => Number.isFinite(value) ? value : fallback;

/** Keeps every window and its title bar reachable after moving or resizing. */
export function boundedWindow(rect: WindowRect): WindowRect {
  const w = clamp(finite(rect.w, .6), MIN_WINDOW_WIDTH, 1), h = clamp(finite(rect.h, .72), MIN_WINDOW_HEIGHT, 1);
  return { x: clamp(finite(rect.x, 0), 0, 1 - w), y: clamp(finite(rect.y, 0), 0, 1 - h), w, h };
}

/** Incremental hand movement uses viewport coordinates; window geometry stays in stage fractions. */
export function handWindowRect(rect: WindowRect, motion: { dx: number; dy: number; scale: number }, viewport: { width: number; height: number }, stage: { width: number; height: number }): WindowRect {
  const r = boundedWindow(rect);
  if (![motion.dx, motion.dy, motion.scale, viewport.width, viewport.height, stage.width, stage.height].every(Number.isFinite) || stage.width <= 0 || stage.height <= 0) return r;
  const scale = clamp(motion.scale, .8, 1.25);
  const w = clamp(r.w * scale, MIN_WINDOW_WIDTH, 1), h = clamp(r.h * scale, MIN_WINDOW_HEIGHT, 1);
  return boundedWindow({ x: r.x + clamp(motion.dx, -.15, .15) * viewport.width / stage.width + (r.w - w) / 2,
    y: r.y + clamp(motion.dy, -.15, .15) * viewport.height / stage.height + (r.h - h) / 2, w, h });
}

/** Resizing a leading edge preserves the opposite edge. Deltas are stage fractions. */
export function resizeWindow(rect: WindowRect, edge: ResizeEdge, dx: number, dy: number): WindowRect {
  const r = boundedWindow(rect);
  let { x, y, w, h } = r;
  if (edge.includes("w")) { x = clamp(r.x + dx, 0, r.x + r.w - MIN_WINDOW_WIDTH); w = r.x + r.w - x; }
  if (edge.includes("e")) w = clamp(r.w + dx, MIN_WINDOW_WIDTH, 1 - r.x);
  if (edge.includes("n")) { y = clamp(r.y + dy, 0, r.y + r.h - MIN_WINDOW_HEIGHT); h = r.y + r.h - y; }
  if (edge.includes("s")) h = clamp(r.h + dy, MIN_WINDOW_HEIGHT, 1 - r.y);
  return boundedWindow({ x, y, w, h });
}

type Placed = WindowRect & { id: string; z: number; minimized: boolean };
/**
 * Which apps fill a 2/3/4 layout, in slot order (Claude, 2026-11-11). Explicitly named apps first,
 * then the pane the picker was used from, then visible panes in their current slot order (top-to-bottom,
 * left-to-right, so re-arranging does not shuffle them), then minimized windows (newest first), then
 * recently used apps and finally the known app order. Earlier versions used visible windows only, so a
 * second arrangement (which had minimized the rest) or a single open window silently did nothing.
 */
export function snapOrder(count: SnapCount, windows: Placed[], options: { ids?: string[]; anchor?: string | null; recent?: string[]; known: readonly string[] }): string[] | null {
  const { known } = options;
  const visible = windows.filter(win => !win.minimized).sort((a, b) => Math.abs(a.y - b.y) > .05 ? a.y - b.y : a.x - b.x || b.z - a.z);
  const hidden = windows.filter(win => win.minimized).sort((a, b) => b.z - a.z);
  const order = options.ids?.length ? [...options.ids] : [options.anchor ?? "", ...visible.map(win => win.id), ...hidden.map(win => win.id), ...(options.recent ?? []), ...known];
  const chosen = [...new Set(order.filter(id => known.includes(id)))].slice(0, count);
  return chosen.length === count ? chosen : null;
}

/**
 * Resize one tiled pane and move the edges of the panes that shared that edge, so a layout stays
 * gap-free (Claude, 2026-11-11). Neighbour minimum sizes limit the move. Non-adjacent panes are untouched.
 */
export function resizeTiled<T extends WindowRect & { id: string }>(panes: T[], id: string, next: WindowRect): T[] {
  const old = panes.find(pane => pane.id === id);
  if (!old) return panes;
  const near = (a: number, b: number) => Math.abs(a - b) < .03;
  const overlaps = (a0: number, a1: number, b0: number, b1: number) => Math.min(a1, b1) - Math.max(a0, b0) > .02;
  let target = boundedWindow(next);
  const others = panes.filter(pane => pane.id !== id);
  // Clamp the moved edges so every neighbour keeps its minimum size.
  for (const pane of others) {
    const vertical = overlaps(old.y, old.y + old.h, pane.y, pane.y + pane.h), horizontal = overlaps(old.x, old.x + old.w, pane.x, pane.x + pane.w);
    if (vertical && near(pane.x, old.x + old.w)) { const limit = pane.x + pane.w - MIN_WINDOW_WIDTH; if (target.x + target.w > limit) target = { ...target, w: limit - target.x }; }
    if (vertical && near(pane.x + pane.w, old.x)) { const limit = pane.x + MIN_WINDOW_WIDTH; if (target.x < limit) target = { ...target, w: target.x + target.w - limit, x: limit }; }
    if (horizontal && near(pane.y, old.y + old.h)) { const limit = pane.y + pane.h - MIN_WINDOW_HEIGHT; if (target.y + target.h > limit) target = { ...target, h: limit - target.y }; }
    if (horizontal && near(pane.y + pane.h, old.y)) { const limit = pane.y + MIN_WINDOW_HEIGHT; if (target.y < limit) target = { ...target, h: target.y + target.h - limit, y: limit }; }
  }
  const gapX = .012, gapY = .012;
  return panes.map(pane => {
    if (pane.id === id) return { ...pane, ...target };
    const vertical = overlaps(old.y, old.y + old.h, pane.y, pane.y + pane.h), horizontal = overlaps(old.x, old.x + old.w, pane.x, pane.x + pane.w);
    let { x, y, w, h } = pane;
    if (vertical && near(pane.x, old.x + old.w)) { const right = x + w; x = target.x + target.w + gapX; w = right - x; }
    if (vertical && near(pane.x + pane.w, old.x)) { w = target.x - gapX - x; }
    if (horizontal && near(pane.y, old.y + old.h)) { const bottom = y + h; y = target.y + target.h + gapY; h = bottom - y; }
    if (horizontal && near(pane.y + pane.h, old.y)) { h = target.y - gapY - y; }
    return { ...pane, ...boundedWindow({ x, y, w, h }) };
  });
}

/** Panes in reading order (top-to-bottom, left-to-right) for "next pane" / "left pane". */
export function paneInDirection(panes: (WindowRect & { id: string })[], from: string | null, direction: "next" | "previous" | "left" | "right" | "up" | "down"): string | null {
  if (!panes.length) return null;
  const order = [...panes].sort((a, b) => Math.abs(a.y - b.y) > .05 ? a.y - b.y : a.x - b.x);
  const current = order.find(pane => pane.id === from) ?? order[0];
  if (direction === "next" || direction === "previous") {
    const index = order.indexOf(current);
    return order[(index + (direction === "next" ? 1 : -1) + order.length) % order.length].id;
  }
  const cx = current.x + current.w / 2, cy = current.y + current.h / 2;
  const candidates = order.filter(pane => pane !== current).map(pane => ({ pane, dx: pane.x + pane.w / 2 - cx, dy: pane.y + pane.h / 2 - cy }))
    .filter(({ dx, dy }) => direction === "left" ? dx < -.05 : direction === "right" ? dx > .05 : direction === "up" ? dy < -.05 : dy > .05)
    .sort((a, b) => Math.hypot(a.dx, a.dy) - Math.hypot(b.dx, b.dy));
  return candidates[0]?.pane.id ?? null;
}

/** Pointer/keyboard attention survives clicking the chat or microphone controls. */
export function attendedWindow(windows: { id: string; minimized: boolean }[], attended: string | null, active: string | null): string | null {
  const visible = (id: string | null) => id !== null && windows.some(win => win.id === id && !win.minimized);
  return visible(attended) ? attended : visible(active) ? active : null;
}
