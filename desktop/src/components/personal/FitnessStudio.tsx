import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { FitnessPanel, type PersonalDraftCache } from "./PersonalPanels";
import { TrainingProgram } from "./TrainingProgram";
import "./FitnessStudio.css";

/**
 * Fitness & Health, reworked (Grey's picks, 2026-10-29): Progress first, then Today, then the Day log.
 * The Training program and the existing logs, plans, recipes and scanning stay as the last sub-tabs,
 * so nothing is lost. All numbers are ZAE's estimates and say so.
 */
const PATH = "/api/platform/personal";
type Targets = { ready: boolean; eat?: number; burn?: number; protein?: number; maintenance?: number; goalDate?: string | null; weeksToGoal?: number | null };
type Profile = { weightLb: number | null; goalWeightLb: number | null; rateLbPerWeek: number; reminders: { workout: string; weighIn: string; food: string } };
type Entry = { weightLb?: number; steps?: number; done?: Record<string, boolean>; sets?: { exercise: string; reps: number; weightLb: number }[];
  cardio?: { type: string; miles: number; minutes: number }[]; actual?: { name: string; minutes: number; miles: number; detail: string }[] | null; updatedAt?: string };
type Overview = { profile: Profile; targets: Targets; weights: { date: string; weightLb: number }[]; log: Record<string, Entry>;
  habits: { workouts: boolean[]; weighIns: boolean[]; dates: string[] }; muscles: Record<string, number>; planTitle: string };
type DayView = { date: string; workout: { label: string; exercises: { exercise: string; prescription: string }[] }; actual: { name: string; detail: string }[];
  entry: Entry; burned: { total: number; actual: { name: string; kcal: number; stats: string }[] }; eaten: { calories: number; protein: number; burned: number } | null; targets: Targets };
type Food = { id: string; title: string; calories: number; protein: number; createdAt?: string; updatedAt?: string };
type Tab = "progress" | "today" | "log" | "food" | "recipes" | "scan" | "program" | "plans";
// The old "Logs & plans" sub-tabs are F&H tabs now (Grey, 2026-10-30); this maps each to the page it shows.
const PANEL_PAGE: Partial<Record<Tab, string>> = { food: "Log", recipes: "Recipes", scan: "Scan food", plans: "Plans & targets" };
type Range = 28 | 84 | 365;

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d); };
const fmt = (n: number | null | undefined, digits = 0) => n === null || n === undefined ? "—" : n.toLocaleString([], { maximumFractionDigits: digits });
const time = (text?: string) => text ? new Date(text).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";

export function FitnessStudio({ drafts }: { drafts: PersonalDraftCache }) {
  const [tab, setTab] = useState<Tab>(() => { try { const saved = localStorage.getItem("zaenia.fitness.tab"); return saved === "logs" ? "food" : (saved as Tab) || "progress"; } catch { return "progress"; } });
  const [info, setInfo] = useState<Overview | null>(null);
  const [week, setWeek] = useState<DayView[]>([]);
  const [food, setFood] = useState<Food[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const today = iso(new Date());
  const choose = (next: Tab) => { setTab(next); try { localStorage.setItem("zaenia.fitness.tab", next); } catch { /* optional */ } };

  const load = useCallback(async () => {
    try {
      const [overview, foods, ...days] = await Promise.all([
        api<Overview>("GET", `${PATH}/training`),
        api<{ items: Food[] }>("GET", `${PATH}/food?day=${today}`),
        ...Array.from({ length: 7 }, (_, i) => api<DayView>("GET", `${PATH}/training/day?day=${daysAgo(6 - i)}`)),
      ]);
      setInfo(overview); setFood(foods.items); setWeek(days);
    } catch (failure) { setError(errorText(failure)); }
  }, [today]);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  useEffect(() => { const changed = () => void load(); window.addEventListener("zae:records-changed", changed); return () => window.removeEventListener("zae:records-changed", changed); }, [load]);
  useEffect(() => {
    const setup = () => choose("program"); const meal = () => choose("food");
    window.addEventListener("zae:training-setup", setup); window.addEventListener("zae:food-meal", meal);
    return () => { window.removeEventListener("zae:training-setup", setup); window.removeEventListener("zae:food-meal", meal); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (action: () => Promise<string | void>) => {
    setBusy(true); setError(null); setNote(null);
    try { const done = await action(); if (done) setNote(done); await load(); } catch (failure) { setError(errorText(failure)); } finally { setBusy(false); }
  };
  const quickLog = (text: string) => act(async () => (await api<{ reply: string }>("POST", `${PATH}/training/quick-log`, { text }, { timeoutMs: 180_000 })).reply);
  const logDay = (changes: Partial<Entry>, done?: string) => act(async () => { await api("POST", `${PATH}/training/day?day=${today}`, { changes }); return done; });

  // "Scan barcode": open Logs & plans › Scan food with the camera already on.
  const scanFood = () => { choose("scan"); window.dispatchEvent(new Event("zae:food-scan")); };
  const tabs: [Tab, string][] = [["progress", "Progress"], ["today", "Today"], ["log", "Day log"], ["food", "Food & exercise"], ["recipes", "Recipes"], ["scan", "Scan food"], ["program", "Training program"], ["plans", "Plans & targets"]];
  return <div className="fs">
    <nav className="research-page__tabs" role="tablist" aria-label="Fitness sections">
      {tabs.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={tab === id}
        className={tab === id ? "research-page__tab research-page__tab--on" : "research-page__tab"} onClick={() => choose(id)}>{label}</button>)}
    </nav>
    {error && <p className="fs-error" role="alert">{error}</p>}
    {note && <p className="fs-note" role="status">✓ {note}</p>}
    {!LIVE_API && (tab === "progress" || tab === "today" || tab === "log") && <p className="fs-muted">These views need the ZÆNIA server: open them in the desktop or phone app.</p>}
    {LIVE_API && !info && (tab === "progress" || tab === "today" || tab === "log") && <p className="fs-muted">{error ? "" : "Loading…"}</p>}
    {info && tab === "progress" && <Progress info={info} week={week}/>}
    {info && tab === "today" && week.length > 0 && <Today info={info} view={week[6]} food={food} busy={busy} onLog={logDay} onGo={choose} onScan={scanFood}/>}
    {info && tab === "log" && week.length > 0 && <DayLog info={info} view={week[6]} food={food} busy={busy} onQuick={quickLog} onScan={scanFood}/>}
    {/* Kept mounted so ZAE's "open the setup questions" and "review this meal" still reach them. */}
    <div hidden={tab !== "program"}><TrainingProgram/></div>
    <div hidden={!PANEL_PAGE[tab]}><FitnessPanel drafts={drafts} embedded page={PANEL_PAGE[tab] ?? "Log"}/></div>
  </div>;
}

// ---- B: Progress (first)
function Progress({ info, week }: { info: Overview; week: DayView[] }) {
  const [range, setRange] = useState<Range>(84);
  const since = daysAgo(range);
  const weights = info.weights.filter(w => w.date >= since);
  const first = weights[0]; const last = weights[weights.length - 1];
  const lost = first && last ? first.weightLb - last.weightLb : null;
  const workouts = info.habits.workouts.filter(Boolean).length;
  const proteinDays = week.filter(d => d.eaten && d.eaten.calories > 0);
  const proteinAvg = proteinDays.length ? proteinDays.reduce((s, d) => s + (d.eaten?.protein ?? 0), 0) / proteinDays.length : null;
  const target = info.targets;
  const deficits = week.filter(d => d.eaten && d.eaten.calories > 0 && target.maintenance).map(d => (target.maintenance ?? 0) + d.burned.total - (d.eaten?.calories ?? 0));
  const avgDeficit = deficits.length ? deficits.reduce((a, b) => a + b, 0) / deficits.length : null;
  // Weight chart: points over the range and the plan line from the first weigh-in at the chosen rate.
  const W = 700, H = 280, pad = 36;
  const chart = useMemo(() => {
    if (weights.length < 2) return null;
    const t0 = Date.parse(weights[0].date), t1 = Date.parse(weights[weights.length - 1].date) || t0 + 1;
    const planEnd = weights[0].weightLb - info.profile.rateLbPerWeek * ((t1 - t0) / 604800000);
    const values = [...weights.map(w => w.weightLb), planEnd, info.profile.goalWeightLb ?? planEnd];
    const lo = Math.floor(Math.min(...values) - 1), hi = Math.ceil(Math.max(...values) + 1);
    const x = (t: number) => pad + (t - t0) / Math.max(1, t1 - t0) * (W - pad - 10);
    const y = (v: number) => 10 + (hi - v) / Math.max(1, hi - lo) * (H - 30);
    return { lo, hi, y, line: weights.map(w => `${x(Date.parse(w.date)).toFixed(1)},${y(w.weightLb).toFixed(1)}`).join(" "),
      plan: `${x(t0)},${y(weights[0].weightLb)} ${x(t1)},${y(planEnd)}`, lastX: x(t1), lastY: y(weights[weights.length - 1].weightLb) };
  }, [weights, info.profile.rateLbPerWeek, info.profile.goalWeightLb]);
  const top = Math.max(1, ...week.map(d => Math.max(d.eaten?.calories ?? 0, d.burned.total)));
  const muscles = Object.entries(info.muscles);
  return <div className="fs-progress">
    <div className="fs-row fs-row--between">
      <h2 className="zx-title">{info.profile.weightLb ? `${fmt(info.profile.weightLb, 1)} lb` : "No weight yet"}{info.profile.goalWeightLb ? ` → ${fmt(info.profile.goalWeightLb)} lb` : ""}</h2>
      <div className="fs-seg" role="group" aria-label="Range">{([[28, "4 weeks"], [84, "12 weeks"], [365, "All"]] as [Range, string][]).map(([id, label]) =>
        <button key={id} type="button" aria-pressed={range === id} onClick={() => setRange(id)}>{label}</button>)}</div>
    </div>
    <div className="fs-kpis">
      <div className="zx-card"><small>Lost in range</small><b>{lost === null ? "—" : `${fmt(lost, 1)} lb`}</b><span className="fs-muted">{target.goalDate ? `goal around ${new Date(`${target.goalDate}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" })}` : "set a goal in Training program"}</span></div>
      <div className="zx-card"><small>Workouts, 30 days</small><b>{workouts}</b><span className="fs-muted">{info.habits.weighIns.filter(Boolean).length} weigh-ins</span></div>
      <div className="zx-card"><small>Protein, 7-day average</small><b>{proteinAvg === null ? "—" : `${fmt(proteinAvg)} g`}</b>
        <span className={proteinAvg !== null && target.protein && proteinAvg < target.protein ? "fs-bad" : "fs-muted"}>{target.protein ? `target ${target.protein} g` : ""}</span></div>
      <div className="zx-card"><small>Deficit, 7-day average</small><b>{avgDeficit === null ? "—" : `${fmt(avgDeficit)} kcal`}</b><span className="fs-muted">eaten vs maintenance + exercise</span></div>
    </div>
    <div className="fs-split">
      <section className="zx-card fs-chart">
        <header className="fs-row fs-row--between"><h3 className="zx-title">Weight vs plan</h3><small className="fs-muted">line: weigh-ins · dashed: {info.profile.rateLbPerWeek} lb/week plan</small></header>
        {chart ? <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Weight from ${first?.weightLb} to ${last?.weightLb} pounds`}>
          {[0, 1, 2, 3].map(i => { const v = chart.hi - (chart.hi - chart.lo) * i / 3; return <g key={i}><line x1={pad} x2={W - 10} y1={chart.y(v)} y2={chart.y(v)} className="fs-grid"/><text x={2} y={chart.y(v) + 4} className="fs-axis">{fmt(v)}</text></g>; })}
          <polyline points={chart.plan} className="fs-plan"/>
          <polyline points={chart.line} className="fs-line"/>
          <circle cx={chart.lastX} cy={chart.lastY} r={5} className="fs-dotmark"/>
        </svg> : <p className="fs-muted">Log at least two weigh-ins to see your trend.</p>}
      </section>
      <div className="fs-stack">
        <section className="zx-card">
          <h3 className="zx-title">Calories, last 7 days</h3>
          <div className="fs-bars">{week.map(d => <div key={d.date}><span><i className="fs-eat" style={{ height: `${(d.eaten?.calories ?? 0) / top * 100}%` }}/><i className="fs-burn" style={{ height: `${d.burned.total / top * 100}%` }}/></span>
            <small>{new Date(`${d.date}T12:00:00`).toLocaleDateString([], { weekday: "narrow" })}</small></div>)}</div>
          <small className="fs-muted"><i className="fs-key fs-eat"/>eaten <i className="fs-key fs-burn"/>burned in exercise (estimates)</small>
        </section>
        <section className="zx-card">
          <h3 className="zx-title">Sets per muscle, this week</h3>
          {muscles.map(([name, sets]) => <div key={name} className="fs-muscle"><span>{name}</span><span className="fs-meter"><i style={{ width: `${Math.min(100, sets / 20 * 100)}%` }} className={sets < 10 ? "fs-low" : ""}/></span><b>{sets}</b></div>)}
        </section>
      </div>
    </div>
  </div>;
}

// ---- A: Today (second)
function Ring({ r, value, target, tone }: { r: number; value: number; target: number; tone: string }) {
  const c = 2 * Math.PI * r; const pct = target ? Math.min(1, value / target) : 0;
  return <><circle cx="130" cy="130" r={r} className="fs-ring-bg"/><circle cx="130" cy="130" r={r} fill="none" stroke={tone} strokeWidth="18" strokeLinecap="round"
    strokeDasharray={`${(c * pct).toFixed(1)} ${c.toFixed(1)}`} transform="rotate(-90 130 130)"/></>;
}
function Today({ info, view, food, busy, onLog, onGo, onScan }: { info: Overview; view: DayView; food: Food[]; busy: boolean; onLog: (c: Partial<Entry>, done?: string) => void; onGo: (t: Tab) => void; onScan: () => void }) {
  const [weight, setWeight] = useState("");
  const [steps, setSteps] = useState("");
  const t = view.targets; const eaten = view.eaten?.calories ?? 0; const burned = view.burned.total + (view.eaten?.burned ?? 0); const protein = view.eaten?.protein ?? 0;
  const done = view.entry.done ?? {};
  const exercises = view.actual.length ? [] : view.workout.exercises;
  return <div className="fs-today">
    <div className="fs-row fs-row--between">
      <h2 className="zx-title">{view.actual.length ? "What you did today" : view.workout.label || "Rest day"}</h2>
      <div className="fs-row">
        <button type="button" onClick={onScan}>Scan barcode</button>
        <button type="button" onClick={() => onGo("food")}>Log food</button>
        <button type="button" className="fs-primary" onClick={() => onGo("program")}>Open the workout</button>
      </div>
    </div>
    <div className="fs-split fs-split--today">
      <section className="zx-card fs-rings">
        {t.ready ? <svg width="260" height="260" viewBox="0 0 260 260" role="img" aria-label={`Eaten ${eaten} of ${t.eat} kcal, burned ${burned} of ${t.burn}, protein ${protein} of ${t.protein} grams`}>
          <Ring r={112} value={eaten} target={t.eat ?? 0} tone="#4fe39a"/><Ring r={88} value={burned} target={t.burn ?? 0} tone="var(--accent, #e0a353)"/><Ring r={64} value={protein} target={t.protein ?? 0} tone="#5fb4ff"/>
          <text x="130" y="126" textAnchor="middle" className="fs-ring-big">{fmt(Math.max(0, (t.eat ?? 0) - eaten))}</text>
          <text x="130" y="148" textAnchor="middle" className="fs-ring-small">kcal left to eat</text>
        </svg> : <p className="fs-muted">Answer the setup questions in Training program to get daily targets.</p>}
        <div className="fs-three">
          <span><small className="fs-eat-t">EAT</small><b>{fmt(eaten)} / {fmt(t.eat)}</b></span>
          <span><small className="fs-burn-t">BURN</small><b>{fmt(burned)} / {fmt(t.burn)}</b></span>
          <span><small className="fs-pro-t">PROTEIN</small><b>{fmt(protein)} / {fmt(t.protein)} g</b></span>
        </div>
        <div className="fs-three fs-three--line">
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); const v = Number(weight); if (v > 0) { onLog({ weightLb: v }, `Logged ${v} lb.`); setWeight(""); } }}>
            <small className="fs-muted">Weight</small><b>{fmt(view.entry.weightLb ?? info.profile.weightLb, 1)} lb</b>
            <span className="fs-mini"><input inputMode="decimal" aria-label="Log weight" placeholder="new" value={weight} onChange={e => setWeight(e.target.value)}/><button type="submit" disabled={busy || !weight}>Log</button></span></form>
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); const v = Number(steps.replace(/,/g, "")); if (v >= 0) { onLog({ steps: v }, `Logged ${v.toLocaleString()} steps.`); setSteps(""); } }}>
            <small className="fs-muted">Steps</small><b>{fmt(view.entry.steps)}</b>
            <span className="fs-mini"><input inputMode="numeric" aria-label="Log steps" placeholder="steps" value={steps} onChange={e => setSteps(e.target.value)}/><button type="submit" disabled={busy || !steps}>Log</button></span></form>
          <span><small className="fs-muted">Goal</small><b>{fmt(info.profile.goalWeightLb)} lb</b><small className="fs-muted">{t.goalDate ? `around ${new Date(`${t.goalDate}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" })}` : ""}</small></span>
        </div>
      </section>
      <div className="fs-stack">
        <section className="zx-card">
          <header className="fs-row fs-row--between"><h3 className="zx-title">{view.actual.length ? "Activities" : "Today's workout"}</h3>
            <small className="fs-muted">{view.actual.length ? `${view.burned.actual.reduce((s, a) => s + a.kcal, 0)} kcal (estimate)` : `${exercises.filter(e => done[e.exercise]).length} of ${exercises.length} done`}</small></header>
          {view.actual.length > 0 && view.burned.actual.map((a, i) => <div key={i} className="fs-ex fs-ex--done"><span className="fs-tick">✓</span><span><b>{a.name}</b><small>{a.stats || view.actual[i]?.detail}</small></span><small>{a.kcal} kcal</small></div>)}
          {exercises.map(e => <label key={e.exercise} className={`fs-ex${done[e.exercise] ? " fs-ex--done" : ""}`}>
            <input type="checkbox" checked={Boolean(done[e.exercise])} disabled={busy} onChange={ev => onLog({ done: { ...done, [e.exercise]: ev.target.checked } })}/>
            <span><b>{e.exercise}</b><small>{e.prescription}</small></span>
            <small>{(view.entry.sets ?? []).filter(s => s.exercise === e.exercise).map(s => `${s.weightLb ? `${s.weightLb}×` : ""}${s.reps}`).join(", ")}</small></label>)}
          {!view.actual.length && !exercises.length && <p className="fs-muted">Nothing planned today. Steps, a walk or mobility work count.</p>}
        </section>
        <section className="zx-card">
          <header className="fs-row fs-row--between"><h3 className="zx-title">Food today</h3><small className="fs-muted">Tell ZAE: "150g protein, 2,100 cal" or "I ate 2 eggs"</small></header>
          <div className="fs-meals">{food.map(f => <span key={f.id} className="zx-inset"><small className="fs-muted">{time(f.createdAt ?? f.updatedAt)}</small><b>{fmt(f.calories)} kcal</b><span>{f.title}</span></span>)}
            {!food.length && <p className="fs-muted">Nothing logged yet today.</p>}</div>
        </section>
      </div>
    </div>
  </div>;
}

// ---- C: Day log (third)
function DayLog({ info, view, food, busy, onQuick, onScan }: { info: Overview; view: DayView; food: Food[]; busy: boolean; onQuick: (text: string) => void; onScan: () => void }) {
  const [text, setText] = useState("");
  const t = view.targets; const eaten = view.eaten?.calories ?? 0; const protein = view.eaten?.protein ?? 0;
  type Row = { at: string; title: string; detail: string; value: string; tone: string };
  const rows: Row[] = [];
  if (view.entry.weightLb) rows.push({ at: "", title: "Weighed in", detail: "Body log", value: `${fmt(view.entry.weightLb, 1)} lb`, tone: "#5fb4ff" });
  for (const f of food) rows.push({ at: f.createdAt ?? f.updatedAt ?? "", title: f.title, detail: `${fmt(f.protein)} g protein`, value: `${fmt(f.calories)} kcal`, tone: "#4fe39a" });
  view.burned.actual.forEach((a, i) => rows.push({ at: "", title: a.name, detail: a.stats || view.actual[i]?.detail || "", value: `${a.kcal} kcal`, tone: "var(--accent, #e0a353)" }));
  for (const c of view.entry.cardio ?? []) rows.push({ at: "", title: `Cardio · ${c.type}`, detail: `${c.miles ? `${c.miles} mi ` : ""}${c.minutes ? `${c.minutes} min` : ""}`, value: "", tone: "var(--accent, #e0a353)" });
  const doneList = Object.entries(view.entry.done ?? {}).filter(([, v]) => v).map(([k]) => k);
  if (!view.actual.length && doneList.length) rows.push({ at: "", title: view.workout.label || "Workout", detail: doneList.join(" · "), value: `${doneList.length} done`, tone: "var(--accent, #e0a353)" });
  if (view.entry.steps) rows.push({ at: "", title: "Steps", detail: "All day", value: fmt(view.entry.steps), tone: "#9fb6cf" });
  rows.sort((a, b) => (a.at || "~").localeCompare(b.at || "~"));
  const open = view.actual.length ? [] : view.workout.exercises.filter(e => !(view.entry.done ?? {})[e.exercise]).map(e => e.exercise);
  const reminders = Object.entries(info.profile.reminders).filter(([, v]) => v).map(([k, v]) => ({ name: k === "weighIn" ? "Weigh-in" : k === "food" ? "Food reminder" : "Workout reminder", at: v }));
  return <div className="fs-split fs-split--log">
    <main className="fs-stack">
      <div className="fs-chips"><span className="fs-chip fs-chip--eat">Eat {fmt(eaten)} / {fmt(t.eat)}</span><span className="fs-chip fs-chip--burn">Burn {fmt(view.burned.total)} / {fmt(t.burn)}</span>
        <span className="fs-chip fs-chip--pro">Protein {fmt(protein)} / {fmt(t.protein)} g</span><span className="fs-chip">Steps {fmt(view.entry.steps)}</span></div>
      <ol className="fs-timeline">
        {rows.map((r, i) => <li key={i} style={{ ["--tone" as string]: r.tone }}><span className="fs-when">{time(r.at) || "Today"}</span>
          <div className="zx-card"><span><b>{r.title}</b><small className="fs-muted">{r.detail}</small></span><b className="fs-val">{r.value}</b></div></li>)}
        {!rows.length && <li><span className="fs-when">Today</span><div className="zx-card"><span className="fs-muted">Nothing logged yet.</span></div></li>}
      </ol>
      <form className="fs-quick zx-card" onSubmit={(e: FormEvent) => { e.preventDefault(); if (text.trim()) { onQuick(text.trim()); setText(""); } }}>
        <span className="fs-plus">+</span><input aria-label="Log anything" value={text} maxLength={4000} placeholder='Log anything: "ran 2 miles in 16:30", "150g protein today", "weighed 195.4"' onChange={e => setText(e.target.value)}/>
        <button type="button" onClick={onScan} aria-label="Scan a food barcode">Scan</button>
        <button type="submit" className="fs-primary" disabled={busy || !text.trim()}>{busy ? "Logging…" : "Log"}</button>
      </form>
    </main>
    <aside className="fs-stack">
      <section className="zx-card"><h3 className="zx-title">Where today stands</h3>
        <ul className="fs-notes">
          {t.ready && <li>{fmt(Math.max(0, (t.eat ?? 0) - eaten))} kcal and {fmt(Math.max(0, (t.protein ?? 0) - protein))} g of protein left to your targets.</li>}
          {open.length > 0 && <li>Still open from {view.workout.label}: {open.join(", ")}.</li>}
          {t.goalDate && <li>At this pace you reach {fmt(info.profile.goalWeightLb)} lb around {new Date(`${t.goalDate}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" })}.</li>}
          {!t.ready && <li>Answer the setup questions in Training program to get targets.</li>}
        </ul>
        <small className="fs-muted">Estimates from what's logged. You decide what to do with them.</small></section>
      <section className="zx-card"><h3 className="zx-title">Coming up</h3>
        {reminders.map(r => <div key={r.name} className="fs-up"><span>{r.name}</span><b>{r.at}</b></div>)}
        {!reminders.length && <p className="fs-muted">No fitness reminders set.</p>}
      </section>
    </aside>
  </div>;
}
