import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { Locked, securitySession, setSecuritySession } from "../security/SecurityPanel";
import "./MainViews.css";
import "./SecondViews.css";

/**
 * Grey's 2nd and 3rd picks from the preview canvas (2026-10-30), batch 1: Notes "Three-pane" (B) and "Notes map" (C),
 * Arena "Leaderboard" (B), Security "Activity" (B) and "Security plan" (C). Real data only; the Security views stay
 * behind the same passkey / phrase unlock as the Details tab.
 */
const needServer = (what: string) => <p className="mv-muted">{what} needs the ZÆNIA server: open it in the desktop app or the phone app.</p>;
const ago = (iso?: string) => {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 60) return `${Math.max(1, minutes)} min`;
  if (minutes < 1440) return `${Math.round(minutes / 60)} h`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

// ---------------------------------------------------------------- Notes B: three panes
const NOTES = "/api/platform/notes";
type NoteSummary = { id: string; revision: number; title: string; excerpt: string; tags?: string[]; pinned: boolean; archived: boolean; reference: boolean; updatedAt: string };
type NoteFull = NoteSummary & { body: string };
type Folder = { id: string; name: string; test: (note: NoteSummary) => boolean };

function useNotes() {
  const [notes, setNotes] = useState<NoteSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    if (LIVE_API) api<{ notes: NoteSummary[] }>("GET", `${NOTES}?q=&archived=false&offset=0`).then(r => setNotes(r.notes), f => setError(errorText(f)));
  }, []);
  useEffect(load, [load]);
  return { notes, error, load };
}

export function NotesThreePane() {
  const { notes, error, load } = useNotes();
  const [folder, setFolder] = useState("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<NoteFull | null>(null);
  const [draft, setDraft] = useState<{ title: string; body: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [fail, setFail] = useState<string | null>(null);
  const week = Date.now() - 7 * 86400000;
  const folders: Folder[] = useMemo(() => {
    const tags = [...new Set((notes ?? []).flatMap(n => n.tags ?? []))].slice(0, 8);
    return [
      { id: "all", name: "All notes", test: () => true },
      { id: "pinned", name: "Pinned", test: n => n.pinned },
      { id: "recent", name: "This week", test: n => new Date(n.updatedAt).getTime() > week },
      { id: "zae", name: "ZAE can read", test: n => n.reference },
      ...tags.map(tag => ({ id: `#${tag}`, name: `#${tag}`, test: (n: NoteSummary) => (n.tags ?? []).includes(tag) })),
    ];
  }, [notes]); // eslint-disable-line react-hooks/exhaustive-deps
  const current = folders.find(f => f.id === folder) ?? folders[0];
  const shown = (notes ?? []).filter(current.test).filter(n => !query.trim() || `${n.title} ${n.excerpt}`.toLowerCase().includes(query.trim().toLowerCase()));
  const pick = async (id: string) => {
    setFail(null); setNote(null);
    try { const full = await api<NoteFull>("GET", `${NOTES}/${id}`); setOpen(full); setDraft({ title: full.title, body: full.body }); }
    catch (f) { setFail(errorText(f)); }
  };
  useEffect(() => { if (!open && shown[0]) void pick(shown[0].id); }, [notes]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = Boolean(open && draft && (draft.title !== open.title || draft.body !== open.body));
  const save = async (changes: Partial<NoteFull> = {}) => {
    if (!open || !draft) return;
    setBusy(true); setFail(null);
    try {
      const value = { ...open, ...draft, ...changes };
      const saved = await api<NoteFull>("PUT", `${NOTES}/${open.id}`, { title: value.title, body: value.body, pinned: value.pinned, archived: value.archived, reference: value.reference, revision: open.revision });
      setOpen(saved); setDraft({ title: saved.title, body: saved.body }); setNote("Saved."); load();
    } catch (f) { setFail(errorText(f)); } finally { setBusy(false); }
  };
  if (!LIVE_API) return needServer("Notes");
  return <div className="sv-three zx-card">
    <nav className="sv-three__folders" aria-label="Note folders">
      <span className="mv-kicker">Notes</span>
      {folders.map(f => <button key={f.id} type="button" aria-pressed={f.id === folder} onClick={() => setFolder(f.id)}>
        <span>{f.name}</span><b>{(notes ?? []).filter(f.test).length}</b></button>)}
    </nav>
    <section className="sv-three__list">
      <input className="zx-inset" aria-label="Search notes" placeholder="Search notes" value={query} onChange={e => setQuery(e.target.value)}/>
      {error && <p className="mv-error">{error}</p>}
      {notes && !shown.length && <p className="mv-muted">No notes here.</p>}
      {shown.map(n => <button key={n.id} type="button" className="sv-three__item" aria-pressed={open?.id === n.id} onClick={() => void pick(n.id)}>
        <span className="mv-row"><b>{n.title || "Untitled"}</b><small>{ago(n.updatedAt)}</small></span>
        <span className="sv-clip">{n.excerpt}</span>
      </button>)}
    </section>
    <main className="sv-three__page">
      {!open ? <p className="mv-muted">Pick a note.</p> : draft && <>
        <div className="mv-row sv-three__meta">
          <span className="mv-muted">Edited {ago(open.updatedAt)} ago{(open.tags ?? []).length ? ` · ${(open.tags ?? []).map(t => `#${t}`).join(" ")}` : ""}</span>
          <span className="sv-actions">
            <button type="button" aria-pressed={open.pinned} disabled={busy} onClick={() => void save({ pinned: !open.pinned })}>{open.pinned ? "Pinned" : "Pin"}</button>
            <button type="button" aria-pressed={open.reference} disabled={busy} onClick={() => void save({ reference: !open.reference })}>ZAE can read: {open.reference ? "on" : "off"}</button>
          </span>
        </div>
        <input className="sv-three__title" aria-label="Title" value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })}/>
        <textarea className="sv-three__body" aria-label="Note" value={draft.body} onChange={e => setDraft({ ...draft, body: e.target.value })}/>
        <div className="mv-row">
          <span className="mv-muted">{fail ? <span className="mv-error">{fail}</span> : note ?? (dirty ? "Unsaved changes" : "")}</span>
          <button type="button" className="mv-primary" disabled={!dirty || busy} onClick={() => void save()}>Save</button>
        </div>
      </>}
    </main>
  </div>;
}

// ---------------------------------------------------------------- Notes C: how notes connect
const STOP = new Set("the a an and or of to in on for with is it this that be are was at by from as my your our we i you me so not but if then".split(" "));
const words = (text: string) => new Set(text.toLowerCase().match(/[a-z][a-z0-9]{3,}/g)?.filter(w => !STOP.has(w)) ?? []);

export function NotesMap() {
  const { notes, error } = useNotes();
  const [picked, setPicked] = useState<string | null>(null);
  const graph = useMemo(() => {
    const list = (notes ?? []).slice(0, 18);
    const bags = list.map(n => ({ note: n, tags: new Set(n.tags ?? []), words: words(`${n.title} ${n.excerpt}`) }));
    const links: { a: number; b: number; why: string; strength: number }[] = [];
    for (let i = 0; i < bags.length; i++) for (let j = i + 1; j < bags.length; j++) {
      const tags = [...bags[i].tags].filter(t => bags[j].tags.has(t));
      const shared = [...bags[i].words].filter(w => bags[j].words.has(w));
      if (tags.length) links.push({ a: i, b: j, why: `Same #${tags[0]} tag`, strength: 3 + tags.length });
      else if (shared.length >= 2) links.push({ a: i, b: j, why: `Both mention “${shared[0]}”`, strength: shared.length });
    }
    const degree = bags.map((_, i) => links.filter(l => l.a === i || l.b === i).length);
    const hub = degree.indexOf(Math.max(0, ...degree));
    const others = bags.map((_, i) => i).filter(i => i !== hub);
    const place = bags.map((_, i) => {
      if (i === hub) return { x: 50, y: 50 };
      const k = others.indexOf(i), ring = k < 8 ? 0 : 1, count = ring ? others.length - 8 : Math.min(8, others.length);
      const angle = ((ring ? k - 8 : k) / Math.max(1, count)) * Math.PI * 2 - Math.PI / 2 + ring * 0.4;
      const r = ring ? 44 : 28;
      return { x: 50 + Math.cos(angle) * r, y: 50 + Math.sin(angle) * r * 0.82 };
    });
    // A pair that shares words but has no tag in common: worth linking with a tag.
    const hint = links.filter(l => !l.why.startsWith("Same")).sort((x, y) => y.strength - x.strength)[0];
    return { bags, links, degree, hub, place, hint };
  }, [notes]);
  if (!LIVE_API) return needServer("The notes map");
  const sel = picked ? graph.bags.findIndex(b => b.note.id === picked) : graph.hub;
  const selected = graph.bags[sel];
  const linked = graph.links.filter(l => l.a === sel || l.b === sel).map(l => ({ note: graph.bags[l.a === sel ? l.b : l.a].note, why: l.why }));
  return <div className="sv-map">
    <main className="sv-map__canvas zx-card">
      <div className="sv-map__head"><span className="mv-kicker">How your notes connect</span><h2 className="zx-title">Notes map</h2>
        <span className="mv-muted">Lines join notes that share a tag or the same words. Your 18 most recent notes.</span></div>
      {error && <p className="mv-error">{error}</p>}
      {notes && graph.bags.length < 2 && <p className="mv-muted sv-map__empty">Write a few notes and the map fills in.</p>}
      <svg className="sv-map__lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {graph.links.map((l, i) => <line key={i} x1={graph.place[l.a].x} y1={graph.place[l.a].y} x2={graph.place[l.b].x} y2={graph.place[l.b].y}
          className={l.a === sel || l.b === sel ? "on" : ""} vectorEffect="non-scaling-stroke"/>)}
      </svg>
      {graph.bags.map((b, i) => <button key={b.note.id} type="button" className={`sv-map__node ${i === graph.hub ? "sv-map__node--hub" : graph.degree[i] ? "" : "sv-map__node--lone"}`}
        aria-pressed={i === sel} style={{ left: `${graph.place[i].x}%`, top: `${graph.place[i].y}%` }} onClick={() => setPicked(b.note.id)}>{b.note.title || "Untitled"}</button>)}
    </main>
    <aside className="sv-map__side zx-card">
      <span className="mv-muted">SELECTED</span>
      {selected ? <><h3 className="zx-title">{selected.note.title || "Untitled"}</h3>
        <span className="mv-muted">{linked.length} linked note{linked.length === 1 ? "" : "s"} · edited {ago(selected.note.updatedAt)} ago</span>
        {linked.map(l => <button key={l.note.id} type="button" className="zx-inset sv-map__link" onClick={() => setPicked(l.note.id)}><b>{l.note.title || "Untitled"}</b><span className="mv-muted">{l.why}</span></button>)}
        {!linked.length && <p className="mv-muted">Nothing links here yet. Add a tag it shares with another note.</p>}
      </> : <p className="mv-muted">No notes yet.</p>}
      {graph.hint && <div className="zx-inset sv-map__hint"><b>ZAE noticed</b>
        <span>“{graph.bags[graph.hint.a].note.title}” and “{graph.bags[graph.hint.b].note.title}” {graph.hint.why.replace("Both mention", "both mention")} but share no tag. A shared tag would link them.</span></div>}
    </aside>
  </div>;
}

// ---------------------------------------------------------------- Arena B: leaderboard
type BoardRow = { model: string; rounds: number; wins: number; winRate: number; avgSeconds: number | null };
type ModelInfo = { name: string; size: number; parameters: string };
export function ArenaLeaderboard() {
  const [data, setData] = useState<{ board: BoardRow[]; models: ModelInfo[]; brain: { model: string; override: string | null }; rounds: unknown[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(() => { if (LIVE_API) api<typeof data>("GET", "/api/arena").then(setData, f => setError(errorText(f))); }, []);
  useEffect(load, [load]);
  if (!LIVE_API) return needServer("The leaderboard");
  const brain = data?.brain.override || data?.brain.model;
  const size = (name: string) => { const m = data?.models.find(x => x.name === name); return m ? `${(m.size / 1e9).toFixed(1)} GB` : "—"; };
  const rows = (data?.board ?? []).filter(r => !/embed/i.test(r.model));
  const total = rows.reduce((sum, r) => sum + r.rounds, 0);
  const choose = async (model: string) => {
    setBusy(model); setError(null);
    try { await api("POST", "/api/arena/brain", { model }, { desktop: true }); load(); }
    catch (f) { setError(errorText(f)); } finally { setBusy(null); }
  };
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">Your votes · {Math.round(total / 2)} rounds</span><h2 className="zx-title">Leaderboard</h2></div>
      <span className="zx-inset sv-pill">ZAE's brain now: <b>{brain ?? "…"}</b></span></div>
    {error && <p className="mv-error">{error}</p>}
    <div className="sv-split">
      <section className="zx-card sv-table" role="table" aria-label="Models ranked by your votes">
        <div className="sv-table__row sv-table__head" role="row"><span>#</span><span>Model</span><span>Win rate</span><span>Wins</span><span>Speed</span><span>Size</span><span/></div>
        {data && !rows.length && <p className="mv-muted">No rounds yet. Run a head to head and vote.</p>}
        {rows.map((r, i) => <div key={r.model} className="sv-table__row" role="row">
          <b className={i === 0 ? "sv-gold" : ""}>{i + 1}</b>
          <span><b className="sv-mono">{r.model}</b></span>
          <span className="sv-bar"><b>{Math.round(r.winRate * 100)}%</b><i><i style={{ width: `${Math.round(r.winRate * 100)}%` }}/></i></span>
          <span>{r.wins}–{r.rounds - r.wins}</span>
          <span className="mv-muted">{r.avgSeconds ? `${r.avgSeconds} s` : "—"}</span>
          <span className="mv-muted">{size(r.model)}</span>
          <button type="button" className="zx-inset" disabled={r.model === brain || busy !== null} onClick={() => void choose(r.model)}>{r.model === brain ? "Current brain" : busy === r.model ? "Switching…" : "Make ZAE's brain"}</button>
        </div>)}
      </section>
      <aside className="sv-stack">
        <section className="zx-card"><h3>Installed models</h3>
          {(data?.models ?? []).filter(m => !/embed/i.test(m.name)).map(m => <div key={m.name} className="mv-row sv-line"><span className="sv-mono">{m.name}</span><span className="mv-muted">{m.parameters} · {(m.size / 1e9).toFixed(1)} GB</span></div>)}
        </section>
        <section className="zx-card"><h3>How it's scored</h3><p className="mv-muted">Each head to head you vote on is a win for one model. Speed is the average time to a full answer on this PC. Changing the brain is a desktop-only setting.</p></section>
      </aside>
    </div>
  </div>;
}

// ---------------------------------------------------------------- Security B and C (behind the Security unlock)
type Level = "strong" | "fair" | "weak" | "unknown";
type Area = { id: string; title: string; level: Level; evidence: string[]; risk: string; fix: string };
type SecEvent = { at: string; label: string; operation: string; severity: "info" | "warn" };
type Full = { posture: { score: number; level: Level; areas: Area[] }; activity: { events: SecEvent[]; routineAllowed: number; since: string | null }; session: { idleLeft: number } };

function useSecurityFull() {
  const [session, setSession] = useState<string | null>(securitySession);
  const [full, setFull] = useState<Full | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!session) return;
    api<Full>("POST", "/api/security/full", { session }).then(setFull, f => {
      setError(errorText(f)); setSecuritySession(null); setSession(null);
    });
  }, [session]);
  const unlocked = (next: string) => { setSecuritySession(next); setSession(next); };
  return { session, full, error, unlocked };
}

export function SecurityActivity() {
  const { session, full, error, unlocked } = useSecurityFull();
  const [filter, setFilter] = useState("");
  if (!session) return <div className="sec-panel"><Locked onUnlocked={unlocked}/>{error && <p className="mv-error">{error}</p>}</div>;
  if (!full) return <p className="mv-muted">{error ?? "Loading…"}</p>;
  const events = full.activity.events;
  const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - (6 - i)); return d; });
  const perDay = days.map(day => {
    const next = day.getTime() + 86400000;
    const inDay = events.filter(e => { const t = new Date(e.at).getTime(); return t >= day.getTime() && t < next; });
    return { day: day.toLocaleDateString(undefined, { weekday: "short" }), warn: inDay.filter(e => e.severity === "warn").length, info: inDay.filter(e => e.severity !== "warn").length };
  });
  const peak = Math.max(1, ...perDay.map(d => d.warn + d.info));
  const shown = events.filter(e => !filter.trim() || `${e.label} ${e.operation}`.toLowerCase().includes(filter.trim().toLowerCase()));
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">Who tried what · 7 days</span><h2 className="zx-title">Activity</h2>
      <span className="mv-muted">{full.activity.routineAllowed} routine allowed requests not listed.</span></div>
      <input className="zx-inset sv-filter" aria-label="Filter activity" placeholder="Filter: denied, voice, phone…" value={filter} onChange={e => setFilter(e.target.value)}/></div>
    <section className="zx-card">
      <div className="mv-row mv-muted"><span>Notable events per day</span><span><b className="sv-dot sv-dot--info"/> noted <b className="sv-dot sv-dot--warn"/> warnings</span></div>
      <div className="sv-bars">{perDay.map(d => <div key={d.day} className="sv-bars__col">
        <span className="sv-bars__stack"><i className="sv-bars__warn" style={{ height: `${d.warn / peak * 100}%` }}/><i className="sv-bars__info" style={{ height: `${d.info / peak * 100}%` }}/></span>
        <small>{d.day}</small></div>)}</div>
    </section>
    <section className="zx-card sv-log">
      {!shown.length && <p className="mv-muted">Nothing matches.</p>}
      {shown.slice(0, 120).map((e, i) => <div key={i} className="sv-log__row">
        <span className="sv-mono mv-muted">{new Date(e.at).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })}</span>
        <b className={e.severity === "warn" ? "sv-warn" : "sv-ok"}>{e.severity === "warn" ? "WARNING" : "NOTED"}</b>
        <span className="mv-muted">{e.operation || "—"}</span><span>{e.label}</span>
      </div>)}
    </section>
  </div>;
}

const PLAN_GROUPS: { name: string; ids: string[] }[] = [
  { name: "Who can get in", ids: ["signin", "voice", "clients"] },
  { name: "What it can touch", ids: ["network", "secrets", "mode", "packages", "git"] },
  { name: "If something goes wrong", ids: ["audit", "tests", "signals", "error"] },
];
export function SecurityPlan() {
  const { session, full, error, unlocked } = useSecurityFull();
  const [openFix, setOpenFix] = useState<string | null>(null);
  if (!session) return <div className="sec-panel"><Locked onUnlocked={unlocked}/>{error && <p className="mv-error">{error}</p>}</div>;
  if (!full) return <p className="mv-muted">{error ?? "Loading…"}</p>;
  const areas = full.posture.areas.filter(a => a.level !== "unknown" || a.fix);
  const done = areas.filter(a => a.level === "strong").length;
  const group = (ids: string[]) => areas.filter(a => ids.includes(a.id) || (ids.includes("error") && !PLAN_GROUPS.some(g => g.ids.includes(a.id))));
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">Your security plan</span><h2 className="zx-title">{done} of {areas.length} strong</h2></div>
      <span className="sv-progress" role="progressbar" aria-valuemin={0} aria-valuemax={areas.length} aria-valuenow={done}><i style={{ width: `${areas.length ? done / areas.length * 100 : 0}%` }}/></span></div>
    <div className="sv-cols">{PLAN_GROUPS.map(g => <section key={g.name} className="zx-card sv-stack">
      <h3>{g.name}</h3>
      {group(g.ids).map(a => <div key={`${a.id}-${a.title}`} className={`sv-check sv-check--${a.level}`}>
        <span className="sv-check__mark" aria-hidden="true">{a.level === "strong" ? "✓" : a.level === "weak" ? "!" : ""}</span>
        <span className="sv-check__text"><b>{a.title}</b><span className="mv-muted">{a.level === "strong" ? a.evidence[0] ?? "In place" : a.risk}</span>
          {openFix === a.title && a.fix && <span className="sv-check__fix">{a.fix}</span>}</span>
        {a.level !== "strong" && a.fix && <button type="button" onClick={() => setOpenFix(openFix === a.title ? null : a.title)}>{openFix === a.title ? "Hide" : "How to fix"}</button>}
      </div>)}
    </section>)}</div>
  </div>;
}
