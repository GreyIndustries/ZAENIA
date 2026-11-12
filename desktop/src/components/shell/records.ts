import { api, LIVE_API } from "../../core/bridge";
import type { Mini } from "./Bento";

/**
 * Records shown as mini tiles inside a screen's tile (preview 05: Notebook → "Food Plan · Note"), and as the
 * screen's own children. Read-only listings through the existing authenticated routes; cached for a minute.
 * Opening one goes to its screen and asks that screen to open the record ("zae:open-record").
 */
type Source = { url: string; type: string; pick: (reply: unknown) => { id: string; title: string }[] };
const SOURCES: Record<string, Source> = {
  "notes/panes": { url: "/api/platform/notes?q=&archived=false&offset=0", type: "Note", pick: reply => ((reply as { notes?: { id: string; title: string }[] }).notes ?? []) },
  "notes/editor": { url: "/api/platform/notes?q=&archived=false&offset=0", type: "Note", pick: reply => ((reply as { notes?: { id: string; title: string }[] }).notes ?? []) },
  "tasks/fitness/food/cookbook": { url: "/api/platform/personal/recipes?day=&archived=false&offset=0", type: "Recipe", pick: reply => ((reply as { items?: { id: string; title: string }[] }).items ?? []) },
  "tasks/fitness/training/plans": { url: "/api/platform/personal/plans?day=&archived=false&offset=0", type: "Plan", pick: reply => ((reply as { items?: { id: string; title: string }[] }).items ?? []) },
  "workbench/projects": { url: "/api/platform/personal/workbench?day=&archived=false&offset=0", type: "Project", pick: reply => ((reply as { items?: { id: string; title: string }[] }).items ?? []) },
};
const cache = new Map<string, { at: number; rows: { id: string; title: string }[] }>();
const loading = new Set<string>();

export function recordMinis(app: string, path: string[]): Mini[] {
  const key = [app, ...path].join("/"); const source = SOURCES[key];
  if (!source) return [];
  const hit = cache.get(key);
  if (LIVE_API && (!hit || Date.now() - hit.at > 60_000) && !loading.has(key)) {
    loading.add(key);
    void api<unknown>("GET", source.url).then(reply => { cache.set(key, { at: Date.now(), rows: source.pick(reply).filter(row => row?.id).slice(0, 12) }); window.dispatchEvent(new Event("zae:record-minis")); },
      () => cache.set(key, { at: Date.now(), rows: hit?.rows ?? [] })).finally(() => loading.delete(key));
  }
  return (hit?.rows ?? []).map(row => ({ key: `r-${row.id}`, name: row.title?.trim() || "Untitled", label: source.type,
    onOpen: () => { window.dispatchEvent(new CustomEvent("zae:open-route", { detail: { app, path, label: row.title } }));
      window.setTimeout(() => window.dispatchEvent(new CustomEvent("zae:open-record", { detail: { screen: key, id: row.id } })), 500); } }));
}
/** Tests and previews: put rows in the cache without the server. */
export function seedRecordMinis(key: string, rows: { id: string; title: string }[]) { cache.set(key, { at: Date.now() + 3_600_000, rows }); window.dispatchEvent(new Event("zae:record-minis")); }
