export type WindowRect = { x: number; y: number; w: number; h: number };
export type ResizeEdge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
export const MIN_WINDOW_WIDTH = .26, MIN_WINDOW_HEIGHT = .3;
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
const finite = (value: number, fallback: number) => Number.isFinite(value) ? value : fallback;

/** Keeps every window and its title bar reachable after moving or resizing. */
export function boundedWindow(rect: WindowRect): WindowRect {
  const w = clamp(finite(rect.w, .6), MIN_WINDOW_WIDTH, 1), h = clamp(finite(rect.h, .72), MIN_WINDOW_HEIGHT, 1);
  return { x: clamp(finite(rect.x, 0), 0, 1 - w), y: clamp(finite(rect.y, 0), 0, 1 - h), w, h };
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

/** Pointer/keyboard attention survives clicking the chat or microphone controls. */
export function attendedWindow(windows: { id: string; minimized: boolean }[], attended: string | null, active: string | null): string | null {
  const visible = (id: string | null) => id !== null && windows.some(win => win.id === id && !win.minimized);
  return visible(attended) ? attended : visible(active) ? active : null;
}
