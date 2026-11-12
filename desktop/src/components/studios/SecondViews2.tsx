import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./MainViews.css";
import "./SecondViews.css";

/**
 * Grey's 2nd and 3rd picks (2026-10-30), batch 2: Workbench "Blueprint canvas" (B) and "Experiment log" (C),
 * Arena "Benchmark lab" (C) and Status "Uptime" (C). All on real data.
 */
const needServer = (what: string) => <p className="mv-muted">{what} needs the ZÆNIA server: open it in the desktop app or the phone app.</p>;
const PERSONAL = "/api/platform/personal";

// ---------------------------------------------------------------- Workbench B: blueprint canvas
type Ink = "#f2b95f" | "#75cfff" | "#a5eeaa" | "#f49cb8" | "#eeeeee";
type Stroke = { color: Ink; width: number; points: number[][] };
type ProjectRow = { id: string; title: string; status?: string };
type Project = Record<string, unknown> & { id: string; revision: number; title: string; body: string; unit: string; boardWidth: number; strokes: Stroke[]; referenceImage: string };
const RECORD_KEYS = ["title", "archived", "category", "tags", "noteIds", "color", "size", "status", "body", "blueprint", "scenarios", "unit", "boardWidth", "strokes", "referenceImage"];
const INKS: [Ink, string][] = [["#75cfff", "Blue"], ["#f2b95f", "Amber"], ["#a5eeaa", "Green"], ["#f49cb8", "Rose"], ["#eeeeee", "White"]];
type Tool = "pen" | "line" | "box" | "measure";
const TOOLS: [Tool, string, string][] = [["pen", "Pen", "Draw freehand"], ["line", "Line", "Straight line"], ["box", "Box", "Rectangle"], ["measure", "mm", "Measure without drawing"]];
const lengthOf = (points: number[][]) => points.slice(1).reduce((sum, p, i) => sum + Math.hypot(p[0] - points[i][0], p[1] - points[i][1]), 0);

export function WorkbenchBlueprint() {
  const [projects, setProjects] = useState<ProjectRow[] | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [tool, setTool] = useState<Tool>("line");
  const [ink, setInk] = useState<Ink>("#75cfff");
  const [live, setLive] = useState<Stroke | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const surface = useRef<SVGSVGElement>(null);
  const start = useRef<number[] | null>(null);
  useEffect(() => {
    if (LIVE_API) api<{ items: ProjectRow[] }>("GET", `${PERSONAL}/workbench?day=&archived=false&offset=0`).then(r => setProjects(r.items), f => setError(errorText(f)));
  }, []);
  const open = async (id: string) => {
    setError(null); setNote(null);
    try { const full = await api<Project>("GET", `${PERSONAL}/workbench/${id}`); setProject(full); setStrokes(full.strokes ?? []); }
    catch (f) { setError(errorText(f)); }
  };
  useEffect(() => { if (!project && projects?.[0]) void open(projects[0].id); }, [projects]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!LIVE_API) return needServer("The blueprint");
  const scale = project ? project.boardWidth / 1000 : 0.1;
  const unit = project?.unit ?? "mm";
  const point = (event: ReactPointerEvent<SVGSVGElement>) => {
    const box = surface.current!.getBoundingClientRect();
    return [Math.max(0, Math.min(1000, (event.clientX - box.left) / box.width * 1000)), Math.max(0, Math.min(600, (event.clientY - box.top) / box.height * 600))].map(v => Math.round(v * 10) / 10);
  };
  const shape = (a: number[], b: number[]): number[][] => tool === "box" ? [a, [b[0], a[1]], b, [a[0], b[1]], a] : [a, b];
  const down = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!project || event.button !== 0 || strokes.length >= 300) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const p = point(event); start.current = p;
    setLive({ color: ink, width: 2, points: [p] });
  };
  const move = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!start.current || !live) return;
    const p = point(event);
    setLive(tool === "pen" ? { ...live, points: [...live.points, p].slice(0, 5000) } : { ...live, points: shape(start.current, p) });
  };
  const up = () => {
    if (live && live.points.length > 1 && tool !== "measure") setStrokes(list => [...list, live]);
    if (tool !== "measure") setLive(null);
    start.current = null;
  };
  const dirty = Boolean(project && JSON.stringify(strokes) !== JSON.stringify(project.strokes ?? []));
  const save = async () => {
    if (!project) return;
    setBusy(true); setError(null);
    try {
      const record = Object.fromEntries(RECORD_KEYS.filter(k => k in project).map(k => [k, k === "strokes" ? strokes : project[k]]));
      const saved = await api<Project>("PUT", `${PERSONAL}/workbench/${project.id}`, { record, revision: project.revision });
      setProject(saved); setStrokes(saved.strokes ?? []); setNote("Blueprint saved.");
    } catch (f) { setError(errorText(f)); } finally { setBusy(false); }
  };
  const exportSvg = () => {
    if (!surface.current) return;
    const clone = surface.current.cloneNode(true) as SVGSVGElement;
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const url = URL.createObjectURL(new Blob([clone.outerHTML], { type: "image/svg+xml" }));
    const a = document.createElement("a"); a.href = url; a.download = `${project?.title ?? "blueprint"}.svg`; a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const parts = (project?.body ?? "").split("\n").map(l => l.trim()).filter(l => /^[-*•]\s+/.test(l)).map(l => l.replace(/^[-*•]\s+/, "")).slice(0, 12);
  const measured = live && live.points.length > 1 ? lengthOf(live.points) * scale : null;
  const last = strokes[strokes.length - 1];
  return <div className="sv-blue">
    <nav className="sv-blue__tools zx-card" aria-label="Drawing tools">
      {TOOLS.map(([id, short, label]) => <button key={id} type="button" aria-label={label} title={label} aria-pressed={tool === id} onClick={() => { setTool(id); setLive(null); }}>{short}</button>)}
      <span className="sv-blue__sep"/>
      {INKS.map(([color, name]) => <button key={color} type="button" aria-label={`${name} ink`} title={`${name} ink`} aria-pressed={ink === color} className="sv-blue__ink" style={{ background: color }} onClick={() => setInk(color)}/>)}
    </nav>
    <main className="sv-blue__board zx-card">
      <div className="sv-blue__top">
        <select className="zx-inset" aria-label="Project" value={project?.id ?? ""} onChange={e => void open(e.target.value)}>
          {(projects ?? []).map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
        <span className="mv-muted">Board {project?.boardWidth ?? "—"} × {project ? +(project.boardWidth * 0.6).toFixed(3) : "—"} {unit} · grid square = {project ? +(project.boardWidth / 50).toFixed(3) : "—"} {unit}</span>
      </div>
      {projects && !projects.length && <p className="mv-muted">Make a project in Projects first, then draw its blueprint here.</p>}
      <svg ref={surface} className="sv-blue__surface" viewBox="0 0 1000 600" role="img" aria-label={`Blueprint for ${project?.title ?? "a project"}`}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={() => { setLive(null); start.current = null; }}>
        <defs><pattern id="sv-grid-s" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#5fb4ff" strokeOpacity=".09"/></pattern>
          <pattern id="sv-grid" width="100" height="100" patternUnits="userSpaceOnUse"><rect width="100" height="100" fill="url(#sv-grid-s)"/><path d="M100 0H0V100" fill="none" stroke="#5fb4ff" strokeOpacity=".2"/></pattern></defs>
        <rect width="1000" height="600" fill="#0b1a2a"/>
        {project?.referenceImage && <image href={project.referenceImage} width="1000" height="600" opacity=".35" preserveAspectRatio="xMidYMid meet"/>}
        <rect width="1000" height="600" fill="url(#sv-grid)"/>
        {[...strokes, ...(live ? [live] : [])].map((s, i) => <polyline key={i} points={s.points.map(p => p.join(",")).join(" ")} fill="none" stroke={s.color} strokeWidth={s.width}
          strokeDasharray={live === s && tool === "measure" ? "6 6" : undefined} strokeLinecap="round" strokeLinejoin="round"/>)}
        {live && measured !== null && <text x={live.points[live.points.length - 1][0] + 8} y={live.points[live.points.length - 1][1] - 8} fill="#8fc8ff" fontSize="16" fontFamily="JetBrains Mono, monospace">{+measured.toFixed(2)} {unit}</text>}
      </svg>
      <div className="mv-row">
        <span className="mv-muted">{error ? <span className="mv-error">{error}</span> : note ?? (tool === "measure" ? "Drag to measure; nothing is drawn." : `${strokes.length} of 300 strokes`)}</span>
        <span className="sv-actions">
          <button type="button" disabled={!strokes.length} onClick={() => setStrokes(s => s.slice(0, -1))}>Undo</button>
          <button type="button" disabled={!strokes.length} onClick={exportSvg}>Export SVG</button>
          <button type="button" className="mv-primary" disabled={!dirty || busy} onClick={() => void save()}>Save</button>
        </span>
      </div>
    </main>
    <aside className="sv-stack zx-card sv-blue__side">
      <h3>{project?.title ?? "No project"}</h3>
      {project && <span className="mv-muted">{String(project.status ?? "")} · {String(project.category ?? "")}</span>}
      <div className="zx-inset sv-blue__stat"><span className="mv-muted">Last line</span><b>{last ? `${+(lengthOf(last.points) * scale).toFixed(2)} ${unit}` : "—"}</b></div>
      {measured !== null && <div className="zx-inset sv-blue__stat"><span className="mv-muted">Measuring</span><b>{+measured.toFixed(2)} {unit}</b></div>}
      <h3>Parts list</h3>
      {parts.length ? parts.map((p, i) => <div key={i} className="sv-line">{p}</div>) : <p className="mv-muted">Lines in the project's notes that start with “- ” show here as parts.</p>}
      <p className="mv-muted sv-blue__foot">Concept measurements. Confirm tolerances in CAD before you build.</p>
    </aside>
  </div>;
}

// ---------------------------------------------------------------- Workbench C: experiment log
type Reading = { day: number; values: (number | null)[]; note: string };
type Experiment = { id?: string; revision?: number; title: string; archived: boolean; projectId: string; hypothesis: string; variable: string; constants: string; measured: string; unit: string; groups: string[]; plannedDays: number; readings: Reading[]; result: string };
const EXP_KEYS = ["title", "archived", "projectId", "hypothesis", "variable", "constants", "measured", "unit", "groups", "plannedDays", "readings", "result"] as const;
const GROUP_COLORS = ["#5fb4ff", "#e0a353", "#7fe3a8", "#c08cff"];
const blankExperiment = (): Experiment => ({ title: "", archived: false, projectId: "", hypothesis: "", variable: "", constants: "", measured: "", unit: "", groups: ["A", "B"], plannedDays: 14, readings: [], result: "" });

export function ExperimentLog() {
  const [list, setList] = useState<{ id: string; title: string }[] | null>(null);
  const [exp, setExp] = useState<Experiment | null>(null);
  const [reading, setReading] = useState<{ day: string; values: string[]; note: string }>({ day: "", values: ["", ""], note: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async (pick?: string) => {
    const r = await api<{ items: { id: string; title: string }[] }>("GET", `${PERSONAL}/experiments?day=&archived=false&offset=0`);
    setList(r.items);
    const id = pick ?? r.items[0]?.id;
    if (id) setExp(await api<Experiment>("GET", `${PERSONAL}/experiments/${id}`));
  }, []);
  useEffect(() => { if (LIVE_API) load().catch(f => setError(errorText(f))); }, [load]);
  useEffect(() => { if (exp) setReading(r => ({ ...r, values: exp.groups.map((_, i) => r.values[i] ?? "") })); }, [exp?.groups.length]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!LIVE_API) return needServer("Experiments");
  const save = async (next: Experiment) => {
    setBusy(true); setError(null);
    try {
      const record = Object.fromEntries(EXP_KEYS.map(k => [k, next[k]]));
      const saved = await api<Experiment>(next.id ? "PUT" : "POST", next.id ? `${PERSONAL}/experiments/${next.id}` : `${PERSONAL}/experiments`, { record, ...(next.id ? { revision: next.revision } : {}) });
      setExp(saved);
      if (!next.id) await load(saved.id);
    } catch (f) { setError(errorText(f)); } finally { setBusy(false); }
  };
  const addReading = () => {
    if (!exp) return;
    const values = exp.groups.map((_, i) => reading.values[i]?.trim() ? Number(reading.values[i]) : null);
    const day = Number(reading.day);
    if (!Number.isInteger(day) || day < 0 || values.some(v => v !== null && !Number.isFinite(v)) || values.every(v => v === null)) { setError("Enter the day and at least one number."); return; }
    const readings = [...exp.readings.filter(r => r.day !== day), { day, values, note: reading.note.trim().slice(0, 300) }].sort((a, b) => a.day - b.day);
    void save({ ...exp, readings });
    setReading({ day: String(day + 1), values: exp.groups.map(() => ""), note: "" });
  };
  if (!exp) return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">Hypothesis · trials · result</span><h2 className="zx-title">Experiments</h2></div></div>
    {error && <p className="mv-error">{error}</p>}
    {list && !list.length && <section className="zx-card sv-stack"><p className="mv-muted">No experiments yet. Start one: what you think will happen, what you change, and what you measure.</p>
      <button type="button" className="mv-primary" onClick={() => setExp(blankExperiment())}>New experiment</button></section>}
  </div>;
  const editing = !exp.id;
  const all = exp.readings.flatMap(r => r.values.filter((v): v is number => v !== null));
  const top = Math.max(1, ...all), lastDay = Math.max(exp.plannedDays, ...exp.readings.map(r => r.day), 1);
  const x = (day: number) => 40 + day / lastDay * 550, y = (v: number) => 236 - v / top * 206;
  const field = (key: "title" | "hypothesis" | "variable" | "constants" | "measured" | "unit", label: string, long = false) =>
    <label className="sv-field"><span>{label}</span>{long ? <textarea rows={2} value={exp[key]} onChange={e => setExp({ ...exp, [key]: e.target.value })}/> : <input value={exp[key]} onChange={e => setExp({ ...exp, [key]: e.target.value })}/>}</label>;
  if (editing) return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">New experiment</span><h2 className="zx-title">Set it up</h2></div></div>
    <section className="zx-card sv-form">
      {field("title", "Name")}{field("hypothesis", "Hypothesis: what you think will happen", true)}
      {field("variable", "What you change")}{field("constants", "What you keep the same")}{field("measured", "What you measure")}{field("unit", "Unit (cm, °C, g…)")}
      <label className="sv-field"><span>Groups, comma-separated (up to 4)</span><input value={exp.groups.join(", ")} onChange={e => setExp({ ...exp, groups: e.target.value.split(",").map(s => s.trim()).filter(Boolean).slice(0, 4) })}/></label>
      <label className="sv-field"><span>Planned days</span><input type="number" min={1} value={exp.plannedDays} onChange={e => setExp({ ...exp, plannedDays: Math.max(1, Number(e.target.value) || 1) })}/></label>
      {error && <p className="mv-error">{error}</p>}
      <div className="sv-actions"><button type="button" onClick={() => void load().catch(() => setExp(null))}>Cancel</button><button type="button" className="mv-primary" disabled={busy || !exp.title.trim() || !exp.groups.length} onClick={() => void save(exp)}>Start experiment</button></div>
    </section>
  </div>;
  const latest = exp.readings[exp.readings.length - 1];
  return <div className="mv">
    <div className="mv-head">
      <div><span className="mv-kicker">Hypothesis · trials · result</span><h2 className="zx-title">{exp.title}</h2>{exp.hypothesis && <span className="mv-muted">Hypothesis: {exp.hypothesis}</span>}</div>
      <span className="sv-actions">
        {list && list.length > 1 && <select className="zx-inset" aria-label="Experiment" value={exp.id} onChange={e => void load(e.target.value)}>{list.map(i => <option key={i.id} value={i.id}>{i.title}</option>)}</select>}
        <button type="button" onClick={() => setExp(blankExperiment())}>New</button>
      </span>
    </div>
    <div className="sv-facts">
      <div className="zx-inset"><span className="mv-muted">What changes</span><b>{exp.variable || "—"}</b></div>
      <div className="zx-inset"><span className="mv-muted">Held the same</span><b>{exp.constants || "—"}</b></div>
      <div className="zx-inset"><span className="mv-muted">Measured</span><b>{exp.measured || "—"}{exp.unit ? ` (${exp.unit})` : ""}</b></div>
      <div className="zx-inset"><span className="mv-muted">Day</span><b>{latest ? latest.day : 0} of {exp.plannedDays}</b></div>
    </div>
    <div className="sv-split">
      <section className="zx-card">
        <div className="mv-row"><h3>Readings</h3><span className="mv-muted">{exp.groups.map((g, i) => <span key={g}><b style={{ color: GROUP_COLORS[i] }}>●</b> {g} </span>)}</span></div>
        <svg viewBox="0 0 600 260" className="sv-chart" role="img" aria-label={`Readings over ${lastDay} days`}>
          {[0, .33, .66, 1].map(f => <g key={f}><line x1="40" x2="590" y1={y(top * f)} y2={y(top * f)} stroke="var(--zx-line,#16253a)"/><text x="0" y={y(top * f) + 4} fontSize="11" fill="#7f97b3">{+(top * f).toFixed(1)}</text></g>)}
          {exp.groups.map((g, gi) => { const pts = exp.readings.filter(r => r.values[gi] != null).map(r => `${x(r.day)},${y(r.values[gi] as number)}`); return pts.length ? <polyline key={g} points={pts.join(" ")} fill="none" stroke={GROUP_COLORS[gi]} strokeWidth="3"/> : null; })}
        </svg>
        {!exp.readings.length && <p className="mv-muted">Log the first reading to start the chart.</p>}
      </section>
      <div className="sv-stack">
        <section className="zx-card sv-stack">
          <h3>Log a reading</h3>
          <div className="sv-reading">
            <label className="sv-field"><span>Day</span><input inputMode="numeric" value={reading.day} onChange={e => setReading({ ...reading, day: e.target.value })}/></label>
            {exp.groups.map((g, i) => <label key={g} className="sv-field"><span>{g}</span><input inputMode="decimal" value={reading.values[i] ?? ""} onChange={e => setReading({ ...reading, values: reading.values.map((v, j) => j === i ? e.target.value : v) })}/></label>)}
          </div>
          <label className="sv-field"><span>Note</span><input value={reading.note} onChange={e => setReading({ ...reading, note: e.target.value })}/></label>
          <button type="button" className="mv-primary" disabled={busy} onClick={addReading}>+ Log reading</button>
          {error && <p className="mv-error">{error}</p>}
        </section>
        <section className="zx-card sv-stack">
          <h3>Log</h3>
          {[...exp.readings].reverse().slice(0, 8).map(r => <div key={r.day} className="sv-logline"><span className="mv-muted">Day {r.day}</span><span>{r.note}</span><span className="sv-mono">{r.values.map(v => v ?? "–").join(" / ")}{exp.unit ? ` ${exp.unit}` : ""}</span></div>)}
        </section>
        <section className="zx-card sv-stack">
          <h3>Result so far</h3>
          <textarea className="zx-inset sv-result" rows={3} aria-label="Result" placeholder="What the readings show so far, in your words." value={exp.result} onChange={e => setExp({ ...exp, result: e.target.value })}/>
          <button type="button" disabled={busy} onClick={() => void save(exp)}>Save result</button>
        </section>
      </div>
    </div>
  </div>;
}

// ---------------------------------------------------------------- Arena C: benchmark lab
type BenchQ = { id: string; question: string; expect: string };
type BenchData = { questions: BenchQ[]; run: { at: string; models: string[]; cells: Record<string, Record<string, number>>; totals: Record<string, number>; seconds: Record<string, number>; questions: number } | null; running: { done: number; total: number } | null };
export function ArenaBench() {
  const [data, setData] = useState<BenchData | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [q, setQ] = useState(""); const [expect, setExpect] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<BenchData>("GET", "/api/arena/bench").then(setData, f => setError(errorText(f))), []);
  useEffect(() => {
    if (!LIVE_API) return;
    void load();
    api<{ models: { name: string }[] }>("GET", "/api/arena").then(r => { const names = r.models.map(m => m.name).filter(n => !/embed/i.test(n)); setModels(names); setPicked(names.slice(0, 4)); }, () => undefined);
  }, [load]);
  useEffect(() => { if (!data?.running) return; const t = window.setInterval(() => void load(), 2500); return () => window.clearInterval(t); }, [data?.running, load]);
  if (!LIVE_API) return needServer("The benchmark lab");
  const act = async (work: () => Promise<BenchData>) => { setError(null); try { setData(await work()); } catch (f) { setError(errorText(f)); } };
  const run = data?.run;
  const cols = run?.models ?? picked;
  const cell = (v: number | undefined) => v === undefined ? <span className="mv-muted">·</span> : <span className={`sv-grade sv-grade--${v === 1 ? "ok" : v === 0 ? "no" : "half"}`}>{v === 1 ? "✓" : v === 0 ? "✕" : "½"}</span>;
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">Your own test set</span><h2 className="zx-title">Benchmark lab</h2>
      <span className="mv-muted">The same questions you care about, run on every model, graded against what a good answer mentions.</span></div>
      <button type="button" className="mv-primary" disabled={Boolean(data?.running) || !data?.questions.length || !picked.length}
        onClick={() => void act(() => api<BenchData>("POST", "/api/arena/bench/run", { models: picked }))}>{data?.running ? `Running ${data.running.done} of ${data.running.total}…` : "Run all models"}</button></div>
    {error && <p className="mv-error">{error}</p>}
    <div className="mv-chips" role="group" aria-label="Models to run">{models.map(m => <button key={m} type="button" aria-pressed={picked.includes(m)} onClick={() => setPicked(p => p.includes(m) ? p.filter(x => x !== m) : [...p, m].slice(0, 6))}>{m}</button>)}</div>
    <div className="sv-split">
      <section className="zx-card sv-bench">
        <div className="sv-bench__row sv-bench__head" style={{ gridTemplateColumns: `minmax(0,2.4fr) repeat(${cols.length},minmax(60px,1fr)) 32px` }}><span>Question</span>{cols.map(m => <span key={m} className="sv-mono">{m}</span>)}<span/></div>
        {data && !data.questions.length && <p className="mv-muted">Add your first test question on the right.</p>}
        {(data?.questions ?? []).map(item => <div key={item.id} className="sv-bench__row" style={{ gridTemplateColumns: `minmax(0,2.4fr) repeat(${cols.length},minmax(60px,1fr)) 32px` }}>
          <span className="sv-clip" title={`${item.question} — expects: ${item.expect}`}>{item.question}</span>
          {cols.map(m => <span key={m}>{cell(run?.cells[item.id]?.[m])}</span>)}
          <button type="button" aria-label={`Remove “${item.question}”`} onClick={() => void act(() => api<BenchData>("DELETE", `/api/arena/bench/questions/${item.id}`))}>✕</button>
        </div>)}
        {run && <div className="sv-bench__row sv-bench__total" style={{ gridTemplateColumns: `minmax(0,2.4fr) repeat(${cols.length},minmax(60px,1fr)) 32px` }}><span>Total</span>{cols.map(m => <span key={m}>{run.totals[m] ?? "–"}/{run.questions}</span>)}<span/></div>}
      </section>
      <aside className="sv-stack">
        <section className="zx-card sv-stack">
          <h3>Add a test question</h3>
          <label className="sv-field"><span>Question</span><textarea rows={3} value={q} onChange={e => setQ(e.target.value)} placeholder="How many kcal is 150 g chicken breast?"/></label>
          <label className="sv-field"><span>A good answer mentions (comma-separated)</span><input value={expect} onChange={e => setExpect(e.target.value)} placeholder="240 kcal, 45 g protein"/></label>
          <button type="button" disabled={q.trim().length < 3 || !expect.trim()} onClick={() => void act(async () => { const next = await api<BenchData>("POST", "/api/arena/bench/questions", { question: q, expect }); setQ(""); setExpect(""); return next; })}>Add</button>
        </section>
        <section className="zx-card sv-stack">
          <h3>Last run</h3>
          {run ? <><span>{new Date(run.at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })} · {run.models.length} models</span>
            {run.models.map(m => <span key={m} className="mv-muted sv-mono">{m}: {run.seconds[m] ?? "–"} s total</span>)}</> : <p className="mv-muted">Not run yet. Models run one at a time so the graphics card holds one.</p>}
        </section>
      </aside>
    </div>
  </div>;
}

// ---------------------------------------------------------------- Status C: uptime
type Uptime = { days: string[]; rows: { id: string; name: string; days: (number | null)[]; percent: number | null; now: boolean | null }[]; events: { at: string; until?: string; part: string; name: string; kind: "down" | "back" | "off" }[]; last: string | null };
export function StatusUptime() {
  const [data, setData] = useState<Uptime | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (LIVE_API) api<Uptime>("GET", "/api/status/uptime").then(setData, f => setError(errorText(f))); }, []);
  if (!LIVE_API) return needServer("Uptime");
  const tone = (share: number | null) => share === null ? "none" : share >= 0.98 ? "ok" : share >= 0.6 ? "slow" : "down";
  const when = (iso: string) => new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">Uptime · last 30 days</span><h2 className="zx-title">How ZAE has been running</h2>
      <span className="mv-muted">Checked every 5 minutes{data?.last ? ` · last check ${when(data.last)}` : ""}. History starts from today's update.</span></div></div>
    {error && <p className="mv-error">{error}</p>}
    <section className="zx-card sv-stack">
      {(data?.rows ?? []).map(r => <div key={r.id} className="sv-uptime">
        <span>{r.name}{r.now === false && <b className="sv-warn"> · down now</b>}</span>
        <span className="sv-uptime__days">{r.days.map((d, i) => <i key={i} className={`sv-day sv-day--${tone(d)}`} title={`${data!.days[i]}: ${d === null ? "no data" : `${Math.round(d * 100)}%`}`}/>)}</span>
        <b className={r.percent === null ? "mv-muted" : r.percent >= 99 ? "sv-ok" : "sv-warn"}>{r.percent === null ? "—" : `${r.percent}%`}</b>
      </div>)}
      <div className="sv-legend mv-muted"><span><i className="sv-day sv-day--ok"/> fine</span><span><i className="sv-day sv-day--slow"/> partly down</span><span><i className="sv-day sv-day--down"/> mostly down</span><span><i className="sv-day sv-day--none"/> no data</span></div>
    </section>
    <section className="zx-card sv-stack">
      <h3>What happened</h3>
      {data && !data.events.length && <p className="mv-muted">Nothing yet. Changes show here as they happen.</p>}
      {(data?.events ?? []).map((e, i) => <div key={i} className="sv-logline">
        <span className="mv-muted">{when(e.at)}</span>
        <b className={e.kind === "back" ? "sv-ok" : "sv-warn"}>{e.kind === "off" ? "OFF" : e.kind === "down" ? "DOWN" : "BACK"}</b>
        <span>{e.kind === "off" ? `ZAE's server was off${e.until ? ` until ${when(e.until)}` : ""}` : `${e.name} ${e.kind === "down" ? "stopped working" : "working again"}`}</span>
      </div>)}
    </section>
  </div>;
}
