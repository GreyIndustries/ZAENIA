import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import { PhoneNotifications } from "../phone/PhoneNotifications";
import { BodyMap, TrainingSetup } from "./TrainingSetup";
import "./TrainingProgram.css";

const PATH = "/api/platform/personal/training";
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
type Exercise = { exercise: string; prescription: string };
type Day = { label: string; exercises: Exercise[] };
type Cardio = { type: string; miles: number; minutes: number };
type SetRow = { exercise: string; reps: number; weightLb: number };
type Activity = { name: string; type: string; detail: string; minutes: number; miles: number; met: number };
type Entry = { actual?: Activity[] | null; weightLb?: number; bodyFat?: number; steps?: number; workoutMinutes?: number; cardio?: Cardio[]; done?: Record<string, boolean>; sets?: SetRow[]; notes?: string };
type Profile = { age: number | null; sex: string; heightIn: number | null; weightLb: number | null; bodyFat: number | null; goalWeightLb: number | null;
  rateLbPerWeek: number; activity: string; gymDays: string[]; homeDays: string[]; reminders: { workout: string; weighIn: string; food: string } };
type Targets = { ready: boolean; assumedAge?: boolean; missing?: string[]; bmr?: number; maintenance?: number; dailyDeficit?: number; eat?: number; burn?: number; protein?: number; weeksToGoal?: number | null; goalDate?: string | null; note?: string };
type Source = { url: string; title: string; kind: string; suggested: { heightIn?: number; weightLb?: number; bodyFat?: number; advice?: string[] }; added: string };
type Overview = { profile: Profile; targets: Targets; plans: { id: string; title: string }[]; planId: string; planTitle: string; days: Day[]; weekdays: Record<string, string>;
  calendar: { date: string; workout: string; planned: number; done: number; weighed: boolean; steps?: number | null; cardio: boolean }[]; month: string;
  sources: Source[]; weights: { date: string; weightLb: number }[]; habits: { workouts: boolean[]; weighIns: boolean[]; dates: string[] }; muscles: Record<string, number>; cardioTypes: string[] };
type DayView = { date: string; workout: Day; actual: Activity[]; entry: Entry; burned: { steps: number; stepMiles: number; cardio: number; cardioMiles: number; lifting: number; total: number; actual: { name: string; kcal: number }[] };
  eaten: { calories: number; protein: number; burned: number } | null; targets: Targets };

const todayIso = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
const shiftMonth = (month: string, by: number) => { const [y, m] = month.split("-").map(Number); const d = new Date(y, m - 1 + by, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };
const shortLabel = (label: string) => label.replace(/\s*\((?:gym|home\/outdoor|home|outdoor|outside)\)\s*/i, "").slice(0, 28);
const feet = (inches: number | null) => inches ? `${Math.floor(inches / 12)}'${Math.round(inches % 12)}"` : "";

function Bar({ label, value, target, unit }: { label: string; value: number; target?: number; unit: string }) {
  const pct = target ? Math.min(100, Math.round(value / target * 100)) : 0;
  return <div className="tp-bar"><div className="tp-bar__head"><span>{label}</span><strong>{Math.round(value)}{target ? ` / ${target}` : ""} {unit}</strong></div>
    <div className="tp-bar__track"><i style={{ width: `${pct}%` }}/></div></div>;
}

function Spark({ points }: { points: { date: string; weightLb: number }[] }) {
  if (points.length < 2) return <p className="tp-muted">{points.length ? `${points[0].weightLb} lb on ${points[0].date}` : "Log your weight to see the trend."}</p>;
  const values = points.map(p => p.weightLb); const min = Math.min(...values) - 1; const max = Math.max(...values) + 1;
  const path = points.map((p, i) => `${(i / (points.length - 1)) * 100},${40 - ((p.weightLb - min) / (max - min)) * 40}`).join(" ");
  return <svg className="tp-spark" viewBox="0 0 100 40" preserveAspectRatio="none" aria-label="Weight trend"><polyline points={path}/></svg>;
}

/** Training program: the plan on a calendar, a daily tracker, body log, calorie targets, sources and phone reminders. */
export function TrainingProgram({ askSetup = 0 }: { askSetup?: number }) {
  const [info, setInfo] = useState<Overview | null>(null);
  const [month, setMonth] = useState(todayIso().slice(0, 7));
  const [day, setDay] = useState(todayIso());
  const [view, setView] = useState<DayView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [link, setLink] = useState("");
  const [cardio, setCardio] = useState<Cardio>({ type: "run", miles: 0, minutes: 0 });
  const [setDraft, setSetDraft] = useState<Record<string, { reps: string; weight: string }>>({});
  const [different, setDifferent] = useState("");
  // ZAE's setup questions: open by themselves while she's missing what the calorie math needs, from the button,
  // or when she asks in chat ("set up my training").
  const [setup, setSetup] = useState(false);
  const [askedOnce, setAskedOnce] = useState(false);
  useEffect(() => { if (askSetup > 0) setSetup(true); }, [askSetup]);
  useEffect(() => {
    const open = () => setSetup(true);
    window.addEventListener("zae:training-setup", open);
    return () => window.removeEventListener("zae:training-setup", open);
  }, []);

  const load = useCallback(async () => {
    try { const next = await api<Overview>("GET", `${PATH}?month=${month}`); setInfo(next); setProfile(current => current ?? next.profile); }
    catch (failure) { setError(errorText(failure)); }
  }, [month]);
  const loadDay = useCallback(async () => {
    try { setView(await api<DayView>("GET", `${PATH}/day?day=${day}`)); } catch (failure) { setError(errorText(failure)); }
  }, [day]);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  useEffect(() => { if (LIVE_API) void loadDay(); }, [loadDay]);
  useEffect(() => {
    const changed = () => { void load(); void loadDay(); };
    window.addEventListener("zae:records-changed", changed);
    return () => window.removeEventListener("zae:records-changed", changed);
  }, [load, loadDay]);

  useEffect(() => {
    if (!info || info.targets.ready || askedOnce) return;
    setAskedOnce(true);
    let asked = false;
    try { asked = localStorage.getItem("zaenia.trainingSetupAsked") === "1"; localStorage.setItem("zaenia.trainingSetupAsked", "1"); } catch { /* optional */ }
    if (!asked) setSetup(true);
  }, [info, askedOnce]);
  const run = async (label: string, action: () => Promise<unknown>, done?: string) => {
    setBusy(label); setError(null); setNote(null);
    try { await action(); if (done) setNote(done); await Promise.all([load(), loadDay()]); }
    catch (failure) { setError(errorText(failure)); } finally { setBusy(null); }
  };
  const log = (changes: Partial<Entry>) => run("log", () => api("POST", `${PATH}/day?day=${day}`, { changes }));
  const saveProfile = (changes: Partial<Profile>) => run("profile", () => api("POST", `${PATH}/profile`, { changes }), "Saved.");

  const entry = view?.entry ?? {};
  const done = entry.done ?? {};
  const weekday = WEEKDAYS[(new Date(`${day}T12:00:00`).getDay() + 6) % 7];
  const targets = view?.targets ?? info?.targets;
  const eaten = view?.eaten?.calories ?? 0;
  const burnedToday = (view?.burned.total ?? 0) + (view?.eaten?.burned ?? 0);
  const firstOffset = useMemo(() => info ? (new Date(`${info.month}-01T12:00:00`).getDay() + 6) % 7 : 0, [info]);

  if (!LIVE_API) return <p className="tp-muted">The training program needs the ZÆNIA server: open it in the desktop or phone app.</p>;
  if (!info) return <p className="tp-muted">{error ?? "Loading your program…"}</p>;
  const p = profile ?? info.profile;
  const maxSets = Math.max(10, ...Object.values(info.muscles));

  return <div className="tp">
    {error && <p className="tp-error" role="alert">{error}</p>}
    {note && <p className="tp-note">✓ {note}</p>}
    {setup && <TrainingSetup profile={info.profile} videoGoal={info.sources.map(s => s.suggested.weightLb).find(Boolean) ?? null}
      onClose={() => setSetup(false)} onSave={async changes => { await api("POST", `${PATH}/profile`, { changes }); setProfile(null); setNote("Got it. Your targets and calendar are updated."); await Promise.all([load(), loadDay()]); }}/>}
    {!info.targets.ready && <div className="tp-row"><button type="button" onClick={() => setSetup(true)}>ZAE's setup questions</button></div>}

    <div className="tp-top">
      <label>Program<select value={info.planId} onChange={event => void run("program", () => api("POST", `${PATH}/program`, { planId: event.target.value, weekdays: {} }))}>
        {info.plans.length ? info.plans.map(plan => <option key={plan.id} value={plan.id}>{plan.title}</option>) : <option value="">No saved plans yet</option>}</select></label>
      <div className="tp-targets">
        {targets?.ready ? <>
          <Bar label="Eat" value={eaten} target={targets.eat} unit="kcal"/>
          <Bar label="Burn (exercise)" value={burnedToday} target={targets.burn} unit="kcal"/>
          <Bar label="Protein" value={view?.eaten?.protein ?? 0} target={targets.protein} unit="g"/>
          <small className="tp-muted">{targets.assumedAge ? "Age not given, so 30 is assumed. " : ""}Maintenance ≈ {targets.maintenance} kcal · goal deficit {targets.dailyDeficit} kcal/day{targets.goalDate ? ` · goal around ${targets.goalDate}` : ""}. Estimates.</small>
        </> : <p className="tp-muted">ZAE needs your {targets?.missing?.join(", ")} for daily calorie targets. <button type="button" className="tp-primary" onClick={() => setSetup(true)}>Answer ZAE's questions</button></p>}
      </div>
    </div>

    <div className="tp-flow">
      <section className="tp-card tp-calendar">
        <header><button type="button" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">‹</button>
          <strong>{new Date(`${info.month}-01T12:00:00`).toLocaleDateString([], { month: "long", year: "numeric" })}</strong>
          <button type="button" onClick={() => setMonth(shiftMonth(month, 1))} aria-label="Next month">›</button>
          <button type="button" onClick={() => { setMonth(todayIso().slice(0, 7)); setDay(todayIso()); }}>Today</button></header>
        <div className="tp-weekdays">{WEEKDAYS.map(name => <span key={name}>{name.slice(0, 3)}</span>)}</div>
        <div className="tp-days">
          {Array.from({ length: firstOffset }, (_, i) => <span key={`pad${i}`}/>)}
          {info.calendar.map(cell => { const pct = cell.planned ? cell.done / cell.planned : 0;
            return <button type="button" key={cell.date} onClick={() => setDay(cell.date)} aria-pressed={cell.date === day}
              className={`tp-day${cell.date === todayIso() ? " tp-day--today" : ""}${pct >= 1 ? " tp-day--done" : pct > 0 ? " tp-day--part" : ""}${!cell.workout ? " tp-day--rest" : ""}`}>
              <b>{Number(cell.date.slice(8))}</b><small>{cell.workout ? shortLabel(cell.workout) : "Rest"}</small>
              <span className="tp-day__marks">{cell.planned > 0 && <i style={{ width: `${Math.round(pct * 100)}%` }}/>}</span>
              <em>{cell.weighed ? "⚖" : ""}{cell.cardio ? "🏃" : ""}</em></button>; })}
        </div>
        <details className="tp-map"><summary>Which day is on which weekday</summary>
          {WEEKDAYS.map(name => <label key={name}>{name}<select value={info.weekdays[name] ?? ""} onChange={event => void run("map", () => api("POST", `${PATH}/program`, { planId: info.planId, weekdays: { ...info.weekdays, [name]: event.target.value } }))}>
            <option value="">Rest</option>{info.days.map(d => <option key={d.label} value={d.label}>{d.label}</option>)}</select></label>)}
        </details>
      </section>

      <section className="tp-card tp-today">
        <h3>{new Date(`${day}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })} <small>{view?.workout.label || `${weekday}: rest day`}</small></h3>
        {view && view.actual.length > 0 && <div className="tp-actual">
          <p className="tp-muted">What you did instead of the plan{view.workout.label ? ` (${shortLabel(view.workout.label)})` : ""}. Calories are ZAE's estimate from time and effort; fix a time if it's off.</p>
          <ul className="tp-exercises">{view.actual.map((item, i) => <li key={i} className="tp-ex tp-ex--done">
            <div className="tp-actual__row"><span><strong>{item.name}</strong><small>{item.detail}</small></span>
              {item.miles > 0 ? <label>mi<input type="number" step="0.1" min="0" defaultValue={item.miles} key={`am${day}${i}${item.miles}`}
                onBlur={event => Number(event.target.value) !== item.miles && void log({ actual: view.actual.map((a, j) => j === i ? { ...a, miles: Number(event.target.value) } : a) })}/></label>
              : <label>min<input type="number" step="1" min="0" defaultValue={item.minutes} key={`at${day}${i}${item.minutes}`}
                onBlur={event => Number(event.target.value) !== item.minutes && void log({ actual: view.actual.map((a, j) => j === i ? { ...a, minutes: Number(event.target.value) } : a) })}/></label>}
              <b>{view.burned.actual[i]?.kcal ?? 0} kcal</b>
              <button type="button" aria-label={`Remove ${item.name}`} onClick={() => void log({ actual: view.actual.length > 1 ? view.actual.filter((_, j) => j !== i) : null })}>✕</button></div>
          </li>)}</ul>
          <div className="tp-row"><button type="button" onClick={() => void run("plan", () => api("POST", `${PATH}/day?day=${day}`, { changes: { actual: null } }), "Back to the planned workout.")}>Back to the plan</button></div>
        </div>}
        {!view?.actual.length && (view?.workout.exercises.length ? <ul className="tp-exercises">{view.workout.exercises.map(item => { const draft = setDraft[item.exercise] ?? { reps: "", weight: "" };
          const logged = (entry.sets ?? []).filter(s => s.exercise === item.exercise);
          return <li key={item.exercise} className={done[item.exercise] ? "tp-ex tp-ex--done" : "tp-ex"}>
            <label><input type="checkbox" checked={Boolean(done[item.exercise])} onChange={event => void log({ done: { ...done, [item.exercise]: event.target.checked } })}/>
              <span><strong>{item.exercise}</strong><small>{item.prescription}</small></span></label>
            <div className="tp-set"><input inputMode="numeric" placeholder="reps" value={draft.reps} onChange={event => setSetDraft({ ...setDraft, [item.exercise]: { ...draft, reps: event.target.value } })}/>
              <input inputMode="decimal" placeholder="lb" value={draft.weight} onChange={event => setSetDraft({ ...setDraft, [item.exercise]: { ...draft, weight: event.target.value } })}/>
              <button type="button" disabled={!draft.reps} onClick={() => { void log({ sets: [...(entry.sets ?? []), { exercise: item.exercise, reps: Number(draft.reps), weightLb: Number(draft.weight || 0) }], done: { ...done, [item.exercise]: true } }); setSetDraft({ ...setDraft, [item.exercise]: { reps: "", weight: draft.weight } }); }}>+ set</button>
              {logged.length > 0 && <small>{logged.map(s => `${s.reps}${s.weightLb ? `×${s.weightLb}` : ""}`).join(", ")}</small>}</div>
          </li>; })}</ul> : <p className="tp-muted">Nothing planned. Recovery, steps or light cardio.</p>)}
        <details className="tp-different"><summary>{view?.actual.length ? "Change what you did" : "Did something different? Tell ZAE"}</summary>
          <textarea rows={4} value={different} maxLength={4000} placeholder="e.g. ACFT this morning: 3-rep max deadlift, hand-release push-ups for 2 min, sprint-drag-carry, plank, 2-mile run" onChange={event => setDifferent(event.target.value)}/>
          <button type="button" className="tp-primary" disabled={!different.trim() || busy === "actual"} onClick={() => void run("actual", async () => { await api("POST", `${PATH}/actual?day=${day}`, { text: different }, { timeoutMs: 180_000 }); setDifferent(""); }, "Updated with what you did, and the burn is recalculated.")}>{busy === "actual" ? "ZAE is working it out…" : "Use this for the day"}</button>
        </details>

        <div className="tp-body">
          <label>Weight (lb)<input type="number" step="0.1" defaultValue={entry.weightLb ?? ""} key={`w${day}${entry.weightLb}`} onBlur={event => event.target.value && Number(event.target.value) !== entry.weightLb && void log({ weightLb: Number(event.target.value) })}/></label>
          <label>Body fat %<input type="number" step="0.1" defaultValue={entry.bodyFat ?? ""} key={`f${day}${entry.bodyFat}`} onBlur={event => event.target.value && Number(event.target.value) !== entry.bodyFat && void log({ bodyFat: Number(event.target.value) })}/></label>
          <label>Steps<input type="number" defaultValue={entry.steps ?? ""} key={`s${day}${entry.steps}`} onBlur={event => event.target.value && Number(event.target.value) !== entry.steps && void log({ steps: Number(event.target.value) })}/></label>
          <label>Lifting minutes<input type="number" defaultValue={entry.workoutMinutes ?? ""} key={`m${day}${entry.workoutMinutes}`} onBlur={event => event.target.value && Number(event.target.value) !== entry.workoutMinutes && void log({ workoutMinutes: Number(event.target.value) })}/></label>
        </div>
        <div className="tp-cardio">
          <strong>Cardio</strong>
          {(entry.cardio ?? []).map((c, i) => <span key={i} className="tp-chip">{c.type}{c.miles ? ` ${c.miles} mi` : ""}{c.minutes ? ` ${c.minutes} min` : ""}
            <button type="button" aria-label="Remove" onClick={() => void log({ cardio: (entry.cardio ?? []).filter((_, j) => j !== i) })}>✕</button></span>)}
          <div className="tp-set"><select value={cardio.type} onChange={event => setCardio({ ...cardio, type: event.target.value })}>{info.cardioTypes.map(t => <option key={t}>{t}</option>)}</select>
            <input inputMode="decimal" placeholder="miles" value={cardio.miles || ""} onChange={event => setCardio({ ...cardio, miles: Number(event.target.value) })}/>
            <input inputMode="numeric" placeholder="min" value={cardio.minutes || ""} onChange={event => setCardio({ ...cardio, minutes: Number(event.target.value) })}/>
            <button type="button" disabled={!cardio.miles && !cardio.minutes} onClick={() => { void log({ cardio: [...(entry.cardio ?? []), cardio] }); setCardio({ ...cardio, miles: 0, minutes: 0 }); }}>Add</button></div>
        </div>
        {view && <p className="tp-muted">Burned today (estimates): steps {view.burned.steps} kcal ({view.burned.stepMiles} mi), cardio {view.burned.cardio} kcal ({view.burned.cardioMiles} mi), lifting {view.burned.lifting} kcal{view.eaten?.burned ? `, logged exercise ${Math.round(view.eaten.burned)} kcal` : ""}. Food comes from the Log page.</p>}
      </section>

      <section className="tp-card"><h3>Weight trend <small>{info.weights.length ? `${info.weights[info.weights.length - 1].weightLb} lb` : ""}</small></h3><Spark points={info.weights}/>
        {p.goalWeightLb && p.weightLb ? <small className="tp-muted">{Math.abs(p.weightLb - p.goalWeightLb).toFixed(1)} lb to your goal of {p.goalWeightLb} lb.</small> : null}</section>
      <section className="tp-card"><h3>Habits <small>last 30 days</small></h3>
        <div className="tp-habit"><span>Workouts</span><div>{info.habits.workouts.map((on, i) => <i key={i} className={on ? "on" : ""} title={info.habits.dates[i]}/>)}</div></div>
        <div className="tp-habit"><span>Weigh-ins</span><div>{info.habits.weighIns.map((on, i) => <i key={i} className={on ? "on" : ""} title={info.habits.dates[i]}/>)}</div></div></section>
      <section className="tp-card"><h3>Muscle groups <small>sets, last 7 days</small></h3><BodyMap sets={info.muscles}/>
        {Object.entries(info.muscles).map(([muscle, sets]) => <div className="tp-muscle" key={muscle}><span>{muscle}</span><div><i style={{ width: `${Math.round(sets / maxSets * 100)}%` }}/></div><b>{sets}</b></div>)}</section>

      <section className="tp-card"><h3>Sources <small>links ZAE reads to build and improve your program</small></h3>
        <form className="tp-row" onSubmit={event => { event.preventDefault(); if (link.trim()) void run("source", () => api("POST", `${PATH}/source`, { url: link.trim() }), "Read it.").then(() => setLink("")); }}>
          <input value={link} placeholder="Paste a TikTok, YouTube or article link" onChange={event => setLink(event.target.value)}/><button type="submit" disabled={busy === "source"}>{busy === "source" ? "Reading…" : "Add link"}</button></form>
        {info.sources.map(source => <div className="tp-source" key={source.url}>
          <button type="button" className="tp-link" onClick={() => openLink(source.url)}>{source.title || source.url}</button><small>{source.kind}</small>
          {(source.suggested.weightLb || source.suggested.heightIn) && <p>Says: {source.suggested.heightIn ? `${feet(source.suggested.heightIn)} ` : ""}{source.suggested.weightLb ? `${source.suggested.weightLb} lb` : ""}{source.suggested.bodyFat ? ` · ${source.suggested.bodyFat}% body fat` : ""}
            {source.suggested.weightLb && <button type="button" onClick={() => { setProfile({ ...p, goalWeightLb: source.suggested.weightLb ?? null }); void saveProfile({ goalWeightLb: source.suggested.weightLb }); }}>Use as my goal weight</button>}</p>}
          {source.suggested.advice?.length ? <ul>{source.suggested.advice.map((a, i) => <li key={i}>{a}</li>)}</ul> : null}
          <button type="button" className="tp-x" onClick={() => void run("remove", () => api("POST", `${PATH}/source`, { url: source.url, remove: true }))}>Remove</button></div>)}
        <button type="button" disabled={!info.sources.length || busy === "improve"} onClick={() => void run("improve", () => api("POST", `${PATH}/improve`, {}, { timeoutMs: 300_000 }), "ZAE wrote an improved program from your sources and made it active (your old plan is kept).")}>
          {busy === "improve" ? "ZAE is rewriting the program…" : "Improve my program from these sources"}</button>
      </section>

      <section className="tp-card"><h3>Your stats & goal</h3>
        <div className="tp-form">
          <label>Age<input type="number" value={p.age ?? ""} onChange={event => setProfile({ ...p, age: event.target.value ? Number(event.target.value) : null })}/></label>
          <label>Sex<select value={p.sex} onChange={event => setProfile({ ...p, sex: event.target.value })}><option value="">—</option><option value="male">Male</option><option value="female">Female</option></select></label>
          <label>Height (ft)<input type="number" value={p.heightIn ? Math.floor(p.heightIn / 12) : ""} onChange={event => setProfile({ ...p, heightIn: Number(event.target.value) * 12 + ((p.heightIn ?? 0) % 12) })}/></label>
          <label>(in)<input type="number" value={p.heightIn ? Math.round(p.heightIn % 12) : ""} onChange={event => setProfile({ ...p, heightIn: Math.floor((p.heightIn ?? 0) / 12) * 12 + Number(event.target.value) })}/></label>
          <label>Weight (lb)<input type="number" step="0.1" value={p.weightLb ?? ""} onChange={event => setProfile({ ...p, weightLb: event.target.value ? Number(event.target.value) : null })}/></label>
          <label>Body fat %<input type="number" step="0.1" value={p.bodyFat ?? ""} onChange={event => setProfile({ ...p, bodyFat: event.target.value ? Number(event.target.value) : null })}/></label>
          <label>Goal weight (lb)<input type="number" step="0.1" value={p.goalWeightLb ?? ""} onChange={event => setProfile({ ...p, goalWeightLb: event.target.value ? Number(event.target.value) : null })}/></label>
          <label>Pace (lb/week)<select value={p.rateLbPerWeek} onChange={event => setProfile({ ...p, rateLbPerWeek: Number(event.target.value) })}>{[0.5, 1, 1.5, 2].map(r => <option key={r} value={r}>{r}</option>)}</select></label>
          <label>Outside workouts<select value={p.activity} onChange={event => setProfile({ ...p, activity: event.target.value })}>{["sitting", "light", "active", "very active"].map(a => <option key={a}>{a}</option>)}</select></label>
        </div>
        {(["gymDays", "homeDays"] as const).map(key => <div className="tp-chips" key={key}><span>{key === "gymDays" ? "Gym days" : "Home / outdoor"}</span>
          {WEEKDAYS.map(name => { const on = p[key].includes(name); return <button type="button" key={name} aria-pressed={on} className={on ? "tp-chip tp-chip--on" : "tp-chip"}
            onClick={() => setProfile({ ...p, [key]: on ? p[key].filter(d => d !== name) : [...p[key], name] })}>{name.slice(0, 3)}</button>; })}</div>)}
        <button type="button" className="tp-primary" disabled={busy === "profile"} onClick={() => void saveProfile({ age: p.age, sex: p.sex, heightIn: p.heightIn, weightLb: p.weightLb, bodyFat: p.bodyFat, goalWeightLb: p.goalWeightLb, rateLbPerWeek: p.rateLbPerWeek, activity: p.activity, gymDays: p.gymDays, homeDays: p.homeDays })}>Save stats</button>
      </section>

      <section className="tp-card"><h3>Reminders on your phone</h3>
        <div className="tp-form">
          {([["workout", "Workout"], ["weighIn", "Weigh-in"], ["food", "Log food"]] as const).map(([key, label]) => <label key={key}>{label}<input type="time" value={p.reminders[key]} onChange={event => setProfile({ ...p, reminders: { ...p.reminders, [key]: event.target.value } })}/></label>)}
        </div>
        <button type="button" disabled={busy === "profile"} onClick={() => void saveProfile({ reminders: p.reminders })}>Save times</button>
        <PhoneNotifications/>
      </section>
    </div>
  </div>;
}
