/**
 * The Security tab's eleven live readings, folded into the four groups the 3D security model shows (kept free of the
 * screen so it can be tested). A group is as strong as its weakest measured reading.
 */
export type Level = "strong" | "fair" | "weak" | "unknown";
export type AreaLite = { id: string; title: string; level: Level };
export type GroupId = "identity" | "access" | "secrets" | "watch";
export type SecurityGroup = { id: GroupId; name: string; blurb: string; level: Level; areas: AreaLite[] };
export type Signals = { failedSignins?: number; denied?: number; voiceRejected?: number; unlockFailed?: number };

const LAYOUT: { id: GroupId; name: string; blurb: string; ids: string[] }[] = [
  { id: "identity", name: "Identity", blurb: "Who you are: the passkey, your voice and your paired devices", ids: ["signin", "voice", "clients"] },
  { id: "access", name: "Access", blurb: "Who can reach ZAE: the network and the server mode", ids: ["network", "mode"] },
  { id: "secrets", name: "Secrets", blurb: "Stored keys, and what is kept out of GitHub", ids: ["secrets", "git"] },
  { id: "watch", name: "Watch", blurb: "The audit trail, signs of attack, security tests and software flaws", ids: ["audit", "signals", "tests", "packages"] },
];
const ORDER: Record<Level, number> = { weak: 0, fair: 1, strong: 2, unknown: 3 };
export const LEVEL_WORD: Record<Level, string> = { strong: "strong", fair: "fair", weak: "weak", unknown: "not measured" };

/** The weakest measured level; "unknown" only when nothing was measured. */
export function worst(levels: Level[]): Level {
  const measured = levels.filter(level => level !== "unknown");
  return measured.length ? measured.reduce((a, b) => ORDER[a] <= ORDER[b] ? a : b) : "unknown";
}

/** Always four groups, in a fixed order. A reading with an id we don't know joins "Watch" so nothing is lost. */
export function groupAreas(areas: AreaLite[]): SecurityGroup[] {
  const known = new Set(LAYOUT.flatMap(group => group.ids));
  return LAYOUT.map(group => {
    const mine = areas.filter(area => group.ids.includes(area.id) || (group.id === "watch" && !known.has(area.id)));
    return { id: group.id, name: group.name, blurb: group.blurb, level: worst(mine.map(area => area.level)), areas: mine };
  });
}

/** Failed or blocked attempts in the last 24 hours, all kinds together. */
export function alertCount(signals: Signals | undefined): number {
  if (!signals) return 0;
  return [signals.failedSignins, signals.denied, signals.voiceRejected, signals.unlockFailed].reduce<number>((sum, n) => sum + (Number.isFinite(n) ? Math.max(0, n as number) : 0), 0);
}

/** How fast the audit-trail ring runs, 0 to 1: calm when nothing was blocked, quicker as more attempts pile up. */
export const trailSpeed = (alerts: number) => Math.max(0.2, Math.min(1, 0.2 + alerts / 25));
