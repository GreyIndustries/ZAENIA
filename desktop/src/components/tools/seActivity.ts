/**
 * What the SE picture shows for each brain, worked out from the /api/brains rows (kept free of the screen so it can be
 * tested). A brain is "loaded" while Ollama holds its model in memory. It counts as "working" for a few seconds after
 * Ollama pushes that model's keep-alive time later, which Ollama does every time the model answers something.
 */
export type BrainRow = { id: string; installed: boolean; loaded: unknown };
export type Seen = Record<string, { until: string; usedAt: number }>;
export type BrainId = "talk" | "seek" | "study" | "keep";
export type BrainState = "working" | "loaded" | "ready" | "missing";
export type BrainReading = { level: number; installed: boolean; state: BrainState; words: string };

/** How long a brain keeps counting as working after its last answer. */
export const HOT_MS = 12_000;

const untilOf = (loaded: unknown): string => {
  if (loaded && typeof loaded === "object") { const until = (loaded as { until?: unknown }).until; if (typeof until === "string") return until; }
  return "";
};

/** Remembers when each loaded model last answered, by watching its keep-alive time move. */
export function trackUse(seen: Seen, rows: BrainRow[], now: number): Seen {
  const next: Seen = {};
  for (const row of rows) {
    if (!row.loaded) continue;
    const until = untilOf(row.loaded), before = seen[row.id];
    if (!before) { next[row.id] = { until, usedAt: 0 }; continue; }   // first sight: loaded, but we can't know when it last answered
    const a = Date.parse(until), b = Date.parse(before.until);
    const moved = until !== before.until && (Number.isNaN(a) || Number.isNaN(b) || a > b);
    next[row.id] = { until, usedAt: moved ? now : before.usedAt };
  }
  return next;
}

export function readBrain(id: BrainId, row: BrainRow | undefined, seen: Seen, now: number): BrainReading {
  if (!row || !row.installed) return { level: 0, installed: false, state: "missing", words: "not installed" };
  if (!row.loaded) return { level: 0, installed: true, state: "ready", words: "ready, loads when needed" };
  const hot = now - (seen[id]?.usedAt ?? 0) < HOT_MS && (seen[id]?.usedAt ?? 0) > 0;
  if (hot) return { level: 1, installed: true, state: "working", words: id === "talk" ? "speaking now" : "working now" };
  return { level: id === "talk" ? 0.4 : 0.55, installed: true, state: "loaded", words: id === "talk" ? "loaded, resting" : "loaded in memory" };
}
