/**
 * Per-screen navigation history (Claude, 2026-11-11).
 *
 * Every desktop pane (ZAE window) and the single phone screen own their own
 * back/forward stacks. A step is either a sub-page change inside one page
 * navigator ("research: desk -> library") or, on the phone only, an app change.
 * Pure data: React wiring lives in components/shell/PaneNav.tsx.
 * Nothing here grants navigation or action permissions; it only replays page
 * choices the owner already made on screen.
 */
export type NavStep =
  | { kind: "page"; navigator: string; from: string; to: string }
  | { kind: "app"; from: string; to: string };
export type PaneHistory = { back: NavStep[]; forward: NavStep[] };

export const HISTORY_LIMIT = 60;
const STORAGE_KEY = "zaenia.paneNav.v1";
const ID = /^[a-z0-9][a-z0-9:_ -]{0,63}$/i;

export const emptyHistory = (): PaneHistory => ({ back: [], forward: [] });

function validStep(step: unknown): step is NavStep {
  if (!step || typeof step !== "object") return false;
  const item = step as Record<string, unknown>;
  const ok = (value: unknown) => typeof value === "string" && ID.test(value);
  if (item.kind === "app") return ok(item.from) && ok(item.to) && item.from !== item.to;
  return item.kind === "page" && ok(item.navigator) && ok(item.from) && ok(item.to) && item.from !== item.to;
}

/** Record a new step: it clears Forward, ignores no-op changes and stays bounded. */
export function pushStep(history: PaneHistory, step: NavStep): PaneHistory {
  if (!validStep(step)) return history;
  return { back: [...history.back, step].slice(-HISTORY_LIMIT), forward: [] };
}

/** Take the newest Back step; the caller replays `step.from`. */
export function takeBack(history: PaneHistory): { history: PaneHistory; step: NavStep } | null {
  const step = history.back[history.back.length - 1];
  if (!step) return null;
  return { step, history: { back: history.back.slice(0, -1), forward: [...history.forward, step].slice(-HISTORY_LIMIT) } };
}

/** Take the newest Forward step; the caller replays `step.to`. */
export function takeForward(history: PaneHistory): { history: PaneHistory; step: NavStep } | null {
  const step = history.forward[history.forward.length - 1];
  if (!step) return null;
  return { step, history: { back: [...history.back, step].slice(-HISTORY_LIMIT), forward: history.forward.slice(0, -1) } };
}

/** Drop a step that can no longer be replayed (its page navigator is gone). */
export function dropBack(history: PaneHistory): PaneHistory { return { back: history.back.slice(0, -1), forward: history.forward }; }

/** "LIFE › Fitness & Health › Food" — the app name, then each ancestor page. */
export function breadcrumb(app: string, chain: { label: string }[]): string[] {
  const parts = [app, ...chain.map(item => item.label)].map(part => part.trim()).filter(Boolean);
  return parts.filter((part, index) => index === 0 || part !== parts[index - 1]);
}

/** Session-scoped persistence: a reload keeps each pane's Back/Forward. */
export function readHistories(get: (key: string) => string | null): Record<string, PaneHistory> {
  try {
    const saved = JSON.parse(get(STORAGE_KEY) ?? "{}") as Record<string, PaneHistory>;
    const result: Record<string, PaneHistory> = {};
    for (const [pane, value] of Object.entries(saved ?? {}).slice(0, 20)) {
      if (!ID.test(pane) || !value || !Array.isArray(value.back) || !Array.isArray(value.forward)) continue;
      result[pane] = { back: value.back.filter(validStep).slice(-HISTORY_LIMIT), forward: value.forward.filter(validStep).slice(-HISTORY_LIMIT) };
    }
    return result;
  } catch { return {}; }
}
export function writeHistories(histories: Record<string, PaneHistory>, set: (key: string, value: string) => void) {
  try { set(STORAGE_KEY, JSON.stringify(histories)); } catch { /* optional */ }
}

/** Bounded scroll memory per location key. */
export function rememberScroll(memory: Map<string, number>, key: string, top: number, limit = 200) {
  if (!key || !Number.isFinite(top)) return;
  memory.delete(key); memory.set(key, Math.max(0, Math.round(top)));
  while (memory.size > limit) memory.delete(memory.keys().next().value!);
}
