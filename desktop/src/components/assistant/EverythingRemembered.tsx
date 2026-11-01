import { useEffect, useMemo, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";

type Item = { store: "told" | "profile" | "noticed"; label: string; id: string; about: string; value: string; status: string;
  updatedAt: string | null; source: string; evidence: string | null };
type View = { items: Item[]; counts: Record<string, number>; note: string };

/**
 * Everything ZAE remembers about Grey, from all three memory stores, each with where it came from (Phase 3).
 * Changing or forgetting stays in the Profile and Memory screens; this is the one place to see it all.
 */
export function EverythingRemembered() {
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | Item["store"]>("all");
  const [query, setQuery] = useState("");
  useEffect(() => { if (LIVE_API) void api<View>("GET", "/api/assistant/memory/all").then(setView, f => setError(errorText(f))); }, []);
  const shown = useMemo(() => (view?.items ?? []).filter(item => (filter === "all" || item.store === filter)
    && (!query.trim() || `${item.about} ${item.value} ${item.evidence ?? ""}`.toLowerCase().includes(query.trim().toLowerCase()))), [view, filter, query]);
  if (!LIVE_API) return <p className="assistant-panel__note">This list needs the ZAE server.</p>;
  return <section className="assistant-panel" aria-label="Everything ZAE remembers">
    <p className="assistant-panel__note">Everything ZAE remembers about you, in one place, and where each item came from. It's reference only: nothing here can approve an action or change a permission. Say "off the record" to keep something out of memory.</p>
    <div className="assistant-panel__views">
      {([["all", "All"], ["told", `You told me (${view?.counts.told ?? 0})`], ["profile", `Profile (${view?.counts.profile ?? 0})`], ["noticed", `Noticed (${view?.counts.noticed ?? 0})`]] as const)
        .map(([id, text]) => <button key={id} type="button" aria-pressed={filter === id} className={filter === id ? "choice choice--active" : "choice"} onClick={() => setFilter(id)}>{text}</button>)}
    </div>
    <label className="assistant-panel__form">Search<input value={query} onChange={event => setQuery(event.target.value)} maxLength={200} placeholder="e.g. training, coffee, voice"/></label>
    {error && <p role="alert">{error}</p>}
    {view && shown.length === 0 && <p className="assistant-panel__empty">Nothing here.</p>}
    <ul className="assistant-panel__list">
      {shown.map(item => <li className="assistant-panel__item" key={`${item.store}-${item.id}`}>
        <div className="assistant-panel__item-head"><strong>{item.about.replace(/[._]/g, " ")}: {item.value}</strong>
          <span className="assistant-panel__badge">{item.label} · {item.status}</span></div>
        <small className="assistant-panel__meta">{item.source}{item.updatedAt ? ` · ${new Date(item.updatedAt).toLocaleDateString()}` : ""}</small>
        {item.evidence && <small className="assistant-panel__meta">From your words: “{item.evidence}”</small>}
      </li>)}
    </ul>
  </section>;
}
