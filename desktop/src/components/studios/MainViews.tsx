import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./MainViews.css";

/**
 * New main views from Grey's preview picks (2026-10-30): Notes "Pinboard" (A), Workbench "Project lab" (A) and
 * Status "Live gauges" (B). Each sits first in its tab; the existing editors stay as the next sub-tab.
 * All on the shared look tokens, all read from ZAE's own records.
 */
const ago = (iso?: string) => {
  if (!iso) return "";
  const d = new Date(iso); const days = Math.floor((Date.now() - d.getTime()) / 864e5);
  return days <= 0 ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : days === 1 ? "yesterday" : days < 7 ? d.toLocaleDateString([], { weekday: "short" }) : d.toLocaleDateString([], { month: "short", day: "numeric" });
};
const needServer = (what: string) => <p className="mv-muted">{what} needs the ZÆNIA server: open it in the desktop or phone app.</p>;
const TINTS = ["amber", "blue", "green", "violet", "rose"] as const;
const hash = (text: string) => [...text].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);

// ---------------------------------------------------------------- Notes: Pinboard
type Note = { id: string; title: string; excerpt: string; updatedAt: string; pinned: boolean; chars: number; reference?: boolean };

export function NotesBoard({ onOpenEditor }: { onOpenEditor: () => void }) {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [tag, setTag] = useState("All");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const load = useCallback(() => { if (LIVE_API) api<{ notes: Note[] }>("GET", "/api/platform/notes?limit=100").then(r => setNotes(r.notes), f => setError(errorText(f))); }, []);
  useEffect(load, [load]);
  const tagsOf = (note: Note) => [...new Set((`${note.title} ${note.excerpt}`.match(/#[a-z0-9][\w-]*/gi) ?? []).map(t => t.toLowerCase()))];
  const tags = useMemo(() => ["All", ...new Set((notes ?? []).flatMap(tagsOf))].slice(0, 14), [notes]);
  const shown = (notes ?? []).filter(note => tag === "All" || tagsOf(note).includes(tag));
  const add = async (event: FormEvent) => {
    event.preventDefault();
    const body = text.trim();
    if (!body) return;
    const title = body.split("\n")[0].replace(/#[\w-]+/g, "").trim().slice(0, 80) || "Quick note";
    try { await api("POST", "/api/platform/notes", { title, body }); setText(""); setSaved("Saved."); load(); }
    catch (failure) { setError(errorText(failure)); }
  };
  if (!LIVE_API) return needServer("The notes board");
  return <div className="mv">
    <div className="mv-head">
      <div><span className="mv-kicker">Keep for later</span><h2 className="zx-title">Notes</h2></div>
      <form className="mv-quick zx-inset" onSubmit={event => void add(event)}>
        <span aria-hidden="true">+</span>
        <input value={text} maxLength={30000} onChange={event => { setText(event.target.value); setSaved(null); }} placeholder="Jot something… add #tag to file it" aria-label="Quick note"/>
        <button type="submit" disabled={!text.trim()}>Save</button>
      </form>
    </div>
    {error && <p className="mv-error" role="alert">{error}</p>}
    {saved && <p className="mv-note" role="status">{saved}</p>}
    <div className="mv-chips" role="group" aria-label="Filter by tag">{tags.map(name => <button key={name} type="button" aria-pressed={tag === name} onClick={() => setTag(name)}>{name}</button>)}</div>
    {!notes && <p className="mv-muted">Loading…</p>}
    {notes && shown.length === 0 && <p className="mv-muted">No notes{tag === "All" ? " yet" : ` tagged ${tag}`}.</p>}
    <div className="mv-board">{shown.map(note => {
      const big = note.pinned || note.chars > 600;
      const tint = TINTS[hash(tagsOf(note)[0] ?? note.title) % TINTS.length];
      return <button key={note.id} type="button" className={`mv-note-card mv-tint--${tint}${big ? " mv-note-card--big" : ""}`} onClick={onOpenEditor} title="Open in the editor">
        <span className="mv-note-meta"><span>{note.pinned ? "★ Pinned" : tagsOf(note)[0] ?? (note.reference ? "Reference" : "Note")}</span><span>{ago(note.updatedAt)}</span></span>
        <b>{note.title}</b>
        <span className="mv-note-body">{note.excerpt}</span>
      </button>;
    })}</div>
  </div>;
}

// ---------------------------------------------------------------- Workbench: Project lab
type Project = { id?: string; title: string; category?: string; tags?: string[]; color?: string; status?: string; updatedAt?: string };
const STAGE_PCT: Record<string, number> = { idea: 10, research: 35, planning: 30, prototype: 60, building: 60, testing: 80, complete: 100, done: 100 };

export function WorkbenchLab({ onOpenEditor }: { onOpenEditor: () => void }) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [subject, setSubject] = useState("All");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (LIVE_API) api<{ items: Project[] }>("GET", "/api/platform/personal/workbench?day=&archived=false&offset=0").then(r => setProjects(r.items), f => setError(errorText(f))); }, []);
  const subjects = useMemo(() => ["All", ...new Set((projects ?? []).map(p => p.category).filter(Boolean) as string[])], [projects]);
  const shown = (projects ?? []).filter(p => subject === "All" || p.category === subject);
  if (!LIVE_API) return needServer("The project lab");
  return <div className="mv">
    <div className="mv-head">
      <div><span className="mv-kicker">Ideas into projects</span><h2 className="zx-title">Workbench</h2></div>
      <button type="button" className="mv-primary" onClick={onOpenEditor}>+ New project</button>
    </div>
    {error && <p className="mv-error" role="alert">{error}</p>}
    <div className="mv-chips" role="group" aria-label="Subjects">{subjects.map(name => <button key={name} type="button" aria-pressed={subject === name} onClick={() => setSubject(name)}>{name}</button>)}</div>
    {!projects && !error && <p className="mv-muted">Loading…</p>}
    {projects && shown.length === 0 && <p className="mv-muted">No projects yet. Start one with "+ New project".</p>}
    <div className="mv-lab">{shown.map((p, i) => {
      const stage = p.status || "Idea";
      const pct = STAGE_PCT[stage.toLowerCase()] ?? 20;
      return <button key={p.id ?? i} type="button" className="mv-project zx-card" onClick={onOpenEditor}>
        <span className="mv-cover" style={{ "--cover": p.color && /^#/.test(p.color) ? p.color : undefined } as CSSProperties}><em>{stage}</em></span>
        <span className="mv-project__body">
          <b>{p.title || "Untitled project"}</b>
          <small>{[p.category, ...(p.tags ?? [])].filter(Boolean).slice(0, 3).join(" · ") || "No subject"}</small>
          <small>Updated {ago(p.updatedAt)}</small>
          <i className="mv-progress"><i style={{ width: `${pct}%` }}/></i>
        </span>
      </button>;
    })}</div>
  </div>;
}

// ---------------------------------------------------------------- Status: Live gauges
type Bar = { cpu: number; ramUsedGb: number; ramTotalGb: number; gpu: { use: number; memoryUsedGb: number; memoryTotalGb: number; temperature: number } | null; diskFreeGb: number; model: string; brains?: { model: string }[] };
type Proc = { name: string; cpu: number; memGb: number };

function Gauge({ label, value, share, sub, tone }: { label: string; value: string; share: number; sub: string; tone: string }) {
  const len = Math.PI * 60;
  return <section className="mv-gauge zx-card">
    <svg viewBox="0 0 150 90" role="img" aria-label={`${label} ${value}`}>
      <path d="M15 80 A60 60 0 0 1 135 80" className="mv-gauge__track"/>
      <path d="M15 80 A60 60 0 0 1 135 80" className="mv-gauge__fill" style={{ stroke: tone, strokeDasharray: `${len * Math.max(0, Math.min(1, share))} ${len}` }}/>
    </svg>
    <b>{value}</b><span>{label}</span><small>{sub}</small>
  </section>;
}

export function StatusGauges() {
  const [bar, setBar] = useState<Bar | null>(null);
  const [history, setHistory] = useState<{ cpu: number; gpu: number }[]>([]);
  const [procs, setProcs] = useState<Proc[]>([]);
  useEffect(() => {
    if (!LIVE_API) return;
    let alive = true;
    const tick = () => api<Bar>("GET", "/api/status/bar").then(next => { if (!alive) return; setBar(next); setHistory(list => [...list, { cpu: next.cpu, gpu: next.gpu?.use ?? 0 }].slice(-120)); }, () => undefined);
    const procTick = () => api<{ processes: Proc[] }>("GET", "/api/status/processes").then(r => { if (alive) setProcs(r.processes); }, () => undefined);
    tick(); procTick();
    const a = window.setInterval(tick, 5000), b = window.setInterval(procTick, 15000);
    return () => { alive = false; window.clearInterval(a); window.clearInterval(b); };
  }, []);
  if (!LIVE_API) return needServer("Live gauges");
  const line = (key: "cpu" | "gpu") => history.map((h, i) => `${(i / Math.max(1, 119)) * 600},${170 - h[key] * 1.6}`).join(" ");
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">This PC, live</span><h2 className="zx-title">Performance</h2></div><small className="mv-muted">Updates every 5 seconds while open</small></div>
    <div className="mv-gauges">
      <Gauge label="CPU" value={bar ? `${Math.round(bar.cpu)}%` : "—"} share={(bar?.cpu ?? 0) / 100} sub="All cores" tone="#5fb4ff"/>
      <Gauge label="Memory" value={bar ? `${bar.ramUsedGb.toFixed(1)} GB` : "—"} share={bar ? bar.ramUsedGb / bar.ramTotalGb : 0} sub={bar ? `of ${bar.ramTotalGb.toFixed(1)} GB` : ""} tone="#5fb4ff"/>
      <Gauge label="GPU memory" value={bar?.gpu ? `${bar.gpu.memoryUsedGb.toFixed(1)} GB` : "—"} share={bar?.gpu ? bar.gpu.memoryUsedGb / bar.gpu.memoryTotalGb : 0} sub={bar?.gpu ? `of ${bar.gpu.memoryTotalGb.toFixed(0)} GB · ${Math.round(bar.gpu.temperature)}°C` : "No GPU data"} tone="var(--accent, #e0a353)"/>
      <Gauge label="Disk free" value={bar ? `${Math.round(bar.diskFreeGb)} GB` : "—"} share={bar ? Math.min(1, bar.diskFreeGb / 1000) : 0} sub="C: drive" tone="#4fe39a"/>
    </div>
    <div className="mv-split">
      <section className="zx-card">
        <div className="mv-row"><h3>Last 10 minutes</h3><small className="mv-muted"><b style={{ color: "#5fb4ff" }}>●</b> CPU <b style={{ color: "var(--accent, #e0a353)" }}>●</b> GPU</small></div>
        <svg viewBox="0 0 600 180" className="mv-chart" aria-label="CPU and GPU use over the last 10 minutes">
          <g className="mv-chart__grid"><line x1="0" y1="50" x2="600" y2="50"/><line x1="0" y1="90" x2="600" y2="90"/><line x1="0" y1="130" x2="600" y2="130"/></g>
          {history.length > 1 && <><polyline points={line("cpu")} className="mv-chart__cpu"/><polyline points={line("gpu")} className="mv-chart__gpu"/></>}
        </svg>
        <small className="mv-muted">{history.length > 1 ? `SE: ${bar?.brains?.[0] ? `Talk ${bar.brains[0].model}` : bar?.model ?? "—"}. GPU spikes are usually the SE thinking.` : "The chart fills in while this page is open."}</small>
      </section>
      <section className="zx-card">
        <h3>What's using it</h3>
        <ul className="mv-procs">{procs.map(p => <li key={p.name}><span>{p.name}</span><code>{p.cpu.toFixed(1)}%</code><code>{p.memGb >= 1 ? `${p.memGb.toFixed(1)} GB` : `${Math.round(p.memGb * 1000)} MB`}</code></li>)}</ul>
        {procs.length === 0 && <small className="mv-muted">Checking…</small>}
      </section>
    </div>
  </div>;
}
