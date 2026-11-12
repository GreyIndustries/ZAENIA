// Is the neural core actually on screen? Pure helpers so the decision is unit-testable (Claude, 2026-11-11).
// The core pauses its animation when nothing of it can be seen: detached, off-screen, zero-sized, or fully
// under an opaque surface (an app window, the category sheet). Translucent layers (orbit view, chat bubbles)
// never pause it.

/** Surfaces that hide whatever is beneath them (0.24.0 made windows and sheets opaque). */
export const OPAQUE_SURFACES = ".os-window, .navhub--workspace, .phone-more, [data-opaque-surface]";

export type CoreHit = "core" | "opaque" | "other" | "outside";

/** The centre and four inner points of a box (20% in from each edge), in viewport coordinates. */
export function samplePoints(box: { left: number; top: number; width: number; height: number }): [number, number][] {
  const xs = [0.2, 0.8], ys = [0.2, 0.8];
  const points: [number, number][] = [[box.left + box.width / 2, box.top + box.height / 2]];
  for (const fx of xs) for (const fy of ys) points.push([box.left + box.width * fx, box.top + box.height * fy]);
  return points;
}

/** Covered only when every sample point inside the viewport lands on an opaque surface. */
export function fullyCovered(hits: readonly CoreHit[]): boolean {
  const seen = hits.filter(hit => hit !== "outside");
  return seen.length > 0 && seen.every(hit => hit === "opaque");
}

/** Whether the core should animate. */
export function coreVisible(state: { connected: boolean; onScreen: boolean; width: number; height: number; hits: readonly CoreHit[] }): boolean {
  if (!state.connected || !state.onScreen || state.width < 2 || state.height < 2) return false;
  return !fullyCovered(state.hits);
}

/** On-screen size relative to the layout box (CSS transforms), clamped so zooming in never enlarges the buffer. */
export function renderScale(shownWidth: number, layoutWidth: number): number {
  if (!(layoutWidth > 0) || !(shownWidth > 0)) return 1;
  const scale = shownWidth / layoutWidth;
  return Math.round(Math.min(1, Math.max(0.25, scale)) * 100) / 100;
}
