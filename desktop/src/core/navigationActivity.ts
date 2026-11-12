/** Device-local app visits only: never record documents, prompts, meal data or credentials. */
export type AppVisit = { id: string; at: number };
export const VISITS_KEY = "zaenia.navigation.recentApps.v1"; // gitleaks:allow -- localStorage identifier, not a credential
const IDS = new Set(["tasks", "fitness", "notes", "research", "news", "assistant", "music", "workbench", "codedoctor", "files", "arena", "system", "status", "security"]);
export function normalizeVisits(value: unknown, now = Date.now()): AppVisit[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.filter((item): item is AppVisit => !!item && typeof item === "object" && IDS.has(item.id)
    && Number.isFinite(item.at) && item.at > 0 && item.at <= now)
    .sort((a, b) => b.at - a.at).filter(item => {
      if (seen.has(item.id)) return false;
      seen.add(item.id); return true;
    }).slice(0, 10).map(({ id, at }) => ({ id, at }));
}
export function readAppVisits(): AppVisit[] {
  try { return normalizeVisits(JSON.parse(localStorage.getItem(VISITS_KEY) ?? "[]")); } catch { return []; }
}
export function recordAppVisit(id: string) {
  if (!IDS.has(id)) return;
  try { localStorage.setItem(VISITS_KEY, JSON.stringify(normalizeVisits([{ id, at: Date.now() }, ...readAppVisits()]))); } catch { /* optional on shared/private browsers */ }
  window.dispatchEvent(new Event("zae:app-visits"));
}
export function clearAppVisits() {
  try { localStorage.removeItem(VISITS_KEY); } catch { /* optional */ }
  window.dispatchEvent(new Event("zae:app-visits"));
}
