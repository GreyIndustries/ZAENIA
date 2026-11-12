import { useCallback, useEffect, useState } from "react";
import { api, errorText } from "../../core/bridge";

type ProfileRecord = { id: string; key: string; value: string; kind: string; scope: string; status: string; sensitivity: string; confidence: number; updatedAt: string; evidence: number };
type Evidence = { type: string; at: string; quote: string; source: string };
type Explained = ProfileRecord & { note: string; createdAt: string; evidence: Evidence[] };
type HistoryRow = { id: string; value: string; status: string; updatedAt: string };
const STATUS_WORD: Record<string, string> = { active: "current", superseded: "earlier", historical: "earlier", conflicted: "conflicting", candidate: "to confirm" };

const VIEWS = [
  { id: "active", label: "Known" },
  { id: "candidate", label: "To confirm" },
] as const;

function label(key: string): string {
  return key.replace(/\.p[0-9a-f]{12,16}$/, "").replace(/[._]/g, " ");
}

function evidenceLabel(type: string): string {
  return ({ user_statement: "You said", user_correction: "You corrected", import_user_report: "From your profile import",
    import_pattern: "Pattern in your profile import", assistant_hypothesis: "ZAE's guess from your words", behavior_observation: "Observed pattern" } as Record<string, string>)[type] ?? type;
}

/** Long-term profile (memory ledger): see what ZAE knows, why, confirm guesses, forget anything. */
export function ProfileReview() {
  const [view, setView] = useState<"active" | "candidate">("active");
  const [query, setQuery] = useState("");
  const [records, setRecords] = useState<ProfileRecord[] | null>(null);
  const [available, setAvailable] = useState(true);
  const [open, setOpen] = useState<Explained | null>(null);
  const [history, setHistory] = useState<{ id: string; rows: HistoryRow[] } | null>(null);
  const [forgetAsked, setForgetAsked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const reply = await api<{ available: boolean; records: ProfileRecord[] }>("GET", `/api/assistant/profile?status=${view}&limit=200&q=${encodeURIComponent(query.trim())}`);
      setRecords(reply.records); setAvailable(reply.available);
    } catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  }, [view, query]);
  useEffect(() => { void load(); }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (work: () => Promise<unknown>, done: string) => {
    setBusy(true); setMessage(null);
    try { await work(); setMessage(done); setOpen(null); setForgetAsked(null); await load(); }
    catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  };

  return <section className="assistant-panel__section" aria-labelledby="assistant-profile-heading" aria-busy={busy}>
    <header className="assistant-panel__heading"><h2 id="assistant-profile-heading">What ZAE knows about you</h2><span>{records?.length ?? "—"} {view === "active" ? "known" : "to confirm"}</span></header>
    <p className="assistant-panel__note">Your long-term profile. Each item keeps the evidence it came from. "To confirm" holds ZAE's guesses, which she doesn't use until you confirm them. Forgetting an item removes it and stops her learning it again. Stored only on this PC.</p>
    {!available && <p className="assistant-panel__empty">No profile database on this PC yet.</p>}
    <div className="assistant-panel__actions">
      {VIEWS.map(item => <button key={item.id} type="button" aria-pressed={view === item.id} className={view === item.id ? "choice choice--active" : "choice"} onClick={() => setView(item.id)} disabled={busy}>{item.label}</button>)}
    </div>
    <form className="assistant-panel__form" onSubmit={event => { event.preventDefault(); void load(); }}>
      <label>Search your profile<input value={query} onChange={event => setQuery(event.target.value)} maxLength={200} placeholder="e.g. voice, GPU, Minecraft"/></label>
      <button type="submit" disabled={busy}>Search</button>
    </form>
    {message && <p className="assistant-panel__note" role="status">{message}</p>}
    {records?.length === 0 && available && <p className="assistant-panel__empty">{view === "active" ? "Nothing matches." : "No guesses waiting for you."}</p>}
    <ul className="assistant-panel__list">
      {records?.map(record => <li className="assistant-panel__item" key={record.id}>
        <div className="assistant-panel__item-head"><strong>{label(record.key)}: {record.value}</strong>
          <span className="assistant-panel__badge">{record.kind}{record.sensitivity === "sensitive" ? " · private" : ""}</span></div>
        <small className="assistant-panel__meta">{record.scope !== "global" ? `${record.scope.replace("project:", "project ")} · ` : ""}{record.evidence} evidence · updated {new Date(record.updatedAt).toLocaleDateString()}</small>
        {open?.id === record.id && <div className="assistant-panel__note">
          <strong>Why ZAE remembers this</strong>
          <ul>{open.evidence.map((item, index) => <li key={index}>{evidenceLabel(item.type)} ({new Date(item.at).toLocaleDateString()}){item.quote ? `: “${item.quote}”` : ""}</li>)}</ul>
          {open.note && <small>{open.note}</small>}
        </div>}
        {record.status === "conflicted" && <small className="assistant-panel__meta">You've said two different things here. Open History and keep the right one.</small>}
        {history?.id === record.id && <div className="assistant-panel__note">
          <strong>History</strong>
          <ul>{history.rows.map(row => <li key={row.id}>{row.value} <small>({STATUS_WORD[row.status] ?? row.status}, {new Date(row.updatedAt).toLocaleDateString()})</small>
            {["superseded", "historical", "conflicted"].includes(row.status) && <button type="button" disabled={busy} onClick={() => void act(
              () => api("POST", `/api/assistant/profile/${encodeURIComponent(row.id)}/restore`), row.status === "conflicted" ? "Kept that one." : "Restored the earlier value.")}>
              {row.status === "conflicted" ? "Keep this" : "Restore"}</button>}</li>)}</ul>
        </div>}
        <div className="assistant-panel__actions">
          <button type="button" disabled={busy} onClick={() => history?.id === record.id ? setHistory(null)
            : void api<{ history: HistoryRow[] }>("GET", `/api/assistant/profile/${encodeURIComponent(record.id)}/history`).then(r => setHistory({ id: record.id, rows: r.history }), error => setMessage(errorText(error)))}>
            {history?.id === record.id ? "Hide history" : "History"}</button>
          <button type="button" disabled={busy} onClick={() => open?.id === record.id ? setOpen(null)
            : void api<Explained>("GET", `/api/assistant/profile/${encodeURIComponent(record.id)}`).then(setOpen, error => setMessage(errorText(error)))}>
            {open?.id === record.id ? "Hide why" : "Why?"}</button>
          {record.status === "candidate" && <button type="button" disabled={busy} onClick={() => void act(
            () => api("POST", `/api/assistant/profile/${encodeURIComponent(record.id)}/confirm`, { kind: record.kind === "inference" ? "preference" : null }),
            "Confirmed. ZAE will use it from now on.")}>Confirm</button>}
          <button type="button" disabled={busy} className={forgetAsked === record.id ? "choice--danger" : undefined}
            onClick={() => forgetAsked === record.id
              ? void act(() => api("DELETE", `/api/assistant/profile/${encodeURIComponent(record.id)}`), "Forgotten. ZAE won't learn it again unless you tell her.")
              : setForgetAsked(record.id)}>{forgetAsked === record.id ? "Tap again to forget" : "Forget"}</button>
        </div>
      </li>)}
    </ul>
  </section>;
}
