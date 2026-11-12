import { PageNavigator } from "../shell/PageNavigator";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { DragEvent, FormEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import type { Priority, TaskRecord } from "../../core/taskModel";
import { PlanPanel } from "./PlanPanel";
import { parseQuickTask } from "../../core/quickTask";
import "./PlanStudio.css";

/**
 * Tasks & Calendar, reworked (Grey's picks, 2026-10-29): Week timeline is the main view, then the
 * Priority board, then the Day planner. The full month calendar, duty status and reminders stay as
 * the last sub-tab so nothing is lost. Everything reads and writes the same tasks, events and
 * reminders as before (one source of truth on the PC).
 */
type CalendarEvent = { id: string; date: string; time: string; endTime: string | null; allDay: boolean; title: string; source: string };
type Reminder = { id: string; text: string; due: string; done?: boolean };
type TrainingCell = { date: string; workout: string };
type Tab = "week" | "priorities" | "day" | "month" | "reminders";
type Item = { key: string; kind: "event" | "task" | "training" | "reminder"; title: string; time: string; minutes: number; task?: TaskRecord };

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const mondayOf = (d: Date) => { const x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x; };
const minutesOf = (hhmm: string) => { const m = /^(\d{1,2}):(\d{2})/.exec(hhmm); return m ? Number(m[1]) * 60 + Number(m[2]) : null; };
const clock = (mins: number) => new Date(2000, 0, 1, Math.floor(mins / 60), mins % 60).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const localTime = (isoText: string) => { const d = new Date(isoText); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
const open = (t: TaskRecord) => t.status !== "Completed" && !t.archived;
const QUADS: { priority: Priority; name: string; hint: string; tone: string }[] = [
  { priority: "Critical", name: "Do now", hint: "urgent and important", tone: "#ff9d8a" },
  { priority: "High", name: "Schedule", hint: "important, not urgent", tone: "#e0c08a" },
  { priority: "Normal", name: "Quick wins", hint: "small or urgent", tone: "#8fc8ff" },
  { priority: "Low", name: "Later", hint: "someday", tone: "#9fb6cf" },
];
export function PlanStudio({ tasksVersion = 0, calendarVersion = 0 }: { tasksVersion?: number; calendarVersion?: number }) {
  const [tab, setTab] = useState<Tab>(() => { try { return (localStorage.getItem("zaenia.plan.tab") as Tab) || "week"; } catch { return "week"; } });
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [training, setTraining] = useState<TrainingCell[]>([]);
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [day, setDay] = useState(() => iso(new Date()));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const choose = (next: Tab) => { setTab(next); try { localStorage.setItem("zaenia.plan.tab", next); } catch { /* optional */ } };

  // A reminder request opens its dedicated view, including when this window is already mounted.
  useEffect(() => {
    const openPlanTab = (event: Event) => {
      const next = (event as CustomEvent<Tab>).detail;
      if (next === "month" || next === "reminders") choose(next);
    };
    window.addEventListener("zae:plan-tab", openPlanTab);
    return () => window.removeEventListener("zae:plan-tab", openPlanTab);
  });

  const loadTasks = useCallback(() => api<{ tasks: TaskRecord[] }>("GET", "/api/tasks").then(r => setTasks(r.tasks), f => setError(errorText(f))), []);
  const loadRange = useCallback(async () => {
    const dayDate = new Date(`${day}T12:00:00`);
    const from = new Date(Math.min(weekStart.getTime(), mondayOf(dayDate).getTime(), addDays(dayDate, -1).getTime()));
    const to = new Date(Math.max(addDays(weekStart, 7).getTime(), addDays(dayDate, 1).getTime()));
    const span = Math.min(62, Math.max(1, Math.round((to.getTime() - from.getTime()) / 86400000) + 1));
    try {
      const reply = await api<{ events: CalendarEvent[] }>("GET", `/api/calendar?start=${iso(from)}&days=${span}`, undefined, { timeoutMs: 60_000 });
      setEvents(reply.events);
    } catch (f) { setError(errorText(f)); }
    const months = [...new Set([iso(weekStart).slice(0, 7), iso(addDays(weekStart, 6)).slice(0, 7), day.slice(0, 7)])];
    const cells: TrainingCell[] = [];
    for (const month of months) {
      try { const r = await api<{ calendar: TrainingCell[] }>("GET", `/api/platform/personal/training?month=${month}`); cells.push(...r.calendar); } catch { /* training is optional */ }
    }
    setTraining(cells);
  }, [weekStart, day]);
  const loadReminders = useCallback(() => api<{ reminders: Reminder[] }>("GET", "/api/reminders").then(r => setReminders(r.reminders), () => undefined), []);
  useEffect(() => { if (LIVE_API) void loadTasks(); }, [loadTasks, tasksVersion]);
  useEffect(() => { if (LIVE_API) { void loadRange(); void loadReminders(); } }, [loadRange, loadReminders, calendarVersion]);

  const patchTask = async (id: string, patch: Partial<Pick<TaskRecord, "priority" | "deadline" | "status" | "archived">>) => {
    setBusy(true); setError(null);
    try { const r = await api<{ tasks: TaskRecord[] }>("PATCH", `/api/tasks/${encodeURIComponent(id)}`, patch); setTasks(r.tasks); }
    catch (f) { setError(errorText(f)); } finally { setBusy(false); }
  };
  const addTask = async (text: string) => {
    const parsed = parseQuickTask(text);
    if (!parsed.title) return false;
    setBusy(true); setError(null);
    try { const r = await api<{ tasks: TaskRecord[] }>("POST", "/api/tasks", parsed); setTasks(r.tasks); return true; }
    catch (f) { setError(errorText(f)); return false; } finally { setBusy(false); }
  };

  /** Everything on one day: events, tasks due, the training day and reminders. */
  const itemsFor = useCallback((date: string): Item[] => {
    const list: Item[] = [];
    for (const e of events.filter(e => e.date === date)) {
      const start = e.allDay ? null : minutesOf(e.time); const end = e.endTime ? minutesOf(e.endTime) : null;
      list.push({ key: `e${e.id}`, kind: "event", title: e.title, time: e.allDay ? "All day" : e.time, minutes: start !== null && end !== null && end > start ? end - start : 60 });
    }
    for (const t of tasks.filter(t => !t.archived && t.deadline && iso(new Date(t.deadline)) === date))
      list.push({ key: `t${t.id}`, kind: "task", title: t.title, time: localTime(t.deadline!), minutes: 30, task: t });
    const workout = training.find(c => c.date === date)?.workout;
    if (workout) list.push({ key: `w${date}`, kind: "training", title: workout, time: "Workout", minutes: 60 });
    for (const r of reminders.filter(r => !r.done && iso(new Date(r.due)) === date))
      list.push({ key: `r${r.id}`, kind: "reminder", title: r.text, time: localTime(r.due), minutes: 0 });
    return list.sort((a, b) => (minutesOf(a.time) ?? -1) - (minutesOf(b.time) ?? -1));
  }, [events, tasks, training, reminders]);

  if (!LIVE_API) return <PlanPanel remote={false} tasksVersion={tasksVersion} calendarVersion={calendarVersion}/>;
  // The old Month & reminders sub-tabs (Both / Calendar / Tasks / Reminders) became Month (calendar with tasks) and Reminders (Grey, 2026-10-30).
  const tabs: [Tab, string][] = [["week", "Week"], ["priorities", "Priorities"], ["day", "Day"], ["month", "Month"], ["reminders", "Reminders"]];
  return <div className="ps">
    <PageNavigator id={"plan"} name={"Plan"} items={tabs.map(([id, label]) => ({ id, label }))} current={tab} onChoose={next => choose(next as Tab)}/>
    {error && <p className="ps-error" role="alert">{error}</p>}
    {tab === "week" && <Week start={weekStart} setStart={setWeekStart} itemsFor={itemsFor} onOpenDay={d => { setDay(d); choose("day"); }} onToggle={t => void patchTask(t.id, { status: t.status === "Completed" ? "Pending" : "Completed" })}/>}
    {tab === "priorities" && <Priorities tasks={tasks} busy={busy} onMove={(t, priority) => void patchTask(t.id, { priority })} onDone={t => void patchTask(t.id, { status: "Completed" })} onAdd={addTask}/>}
    {tab === "day" && <Day day={day} setDay={setDay} tasks={tasks} itemsFor={itemsFor} busy={busy} onAdd={addTask}
      onToggle={t => void patchTask(t.id, { status: t.status === "Completed" ? "Pending" : "Completed" })}
      onSchedule={(t, mins) => { const d = new Date(`${day}T00:00:00`); d.setMinutes(mins); void patchTask(t.id, { deadline: d.toISOString() }); }}/>}
    {tab === "month" && <PlanPanel remote fixed="both" tasksVersion={tasksVersion} calendarVersion={calendarVersion}/>}
    {tab === "reminders" && <PlanPanel remote fixed="reminders" tasksVersion={tasksVersion} calendarVersion={calendarVersion}/>}
  </div>;
}

// ---- C: Week timeline (main)
function Week({ start, setStart, itemsFor, onOpenDay, onToggle }: { start: Date; setStart: (d: Date) => void; itemsFor: (d: string) => Item[]; onOpenDay: (d: string) => void; onToggle: (t: TaskRecord) => void }) {
  const today = iso(new Date());
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const label = `${start.toLocaleDateString([], { month: "short", day: "numeric" })} – ${addDays(start, 6).toLocaleDateString([], { month: "short", day: "numeric" })}`;
  return <div className="ps-week">
    <div className="ps-row ps-row--between">
      <h2 className="zx-title">{label}</h2>
      <div className="ps-seg" role="group" aria-label="Week">
        <button type="button" onClick={() => setStart(addDays(start, -7))} aria-label="Previous week">‹</button>
        <button type="button" onClick={() => setStart(mondayOf(new Date()))}>This week</button>
        <button type="button" onClick={() => setStart(addDays(start, 7))} aria-label="Next week">›</button>
      </div>
    </div>
    <div className="ps-week__grid">
      {days.map(d => { const key = iso(d); const items = itemsFor(key); const booked = items.reduce((s, i) => s + i.minutes, 0) / 60;
        return <section key={key} className={`ps-day zx-card${key === today ? " ps-day--today" : ""}`}>
          <header><button type="button" className="ps-day__open" onClick={() => onOpenDay(key)}><b>{d.toLocaleDateString([], { weekday: "short" })}</b><span>{d.getDate()}</span></button>
            <span className="ps-load" title={`${booked.toFixed(1)} h booked`}><i style={{ width: `${Math.min(100, booked / 8 * 100)}%` }} className={booked > 5 ? "ps-load--busy" : ""}/></span>
            <small className="ps-muted">{booked ? `${booked.toFixed(1)} h` : "free"}</small></header>
          {items.map(i => <div key={i.key} className={`ps-item ps-item--${i.kind}${i.task?.status === "Completed" ? " ps-item--done" : ""}`}>
            {i.task ? <label><input type="checkbox" checked={i.task.status === "Completed"} onChange={() => onToggle(i.task!)}/><span>{i.title}</span></label> : <span>{i.title}</span>}
            <small>{i.kind === "task" ? `due ${clock(minutesOf(i.time) ?? 0)}` : minutesOf(i.time) !== null ? clock(minutesOf(i.time)!) : i.time}</small></div>)}
          {!items.length && <small className="ps-muted">Nothing planned</small>}
        </section>; })}
    </div>
    <div className="ps-legend"><span><i className="ps-dot ps-dot--event"/>Events</span><span><i className="ps-dot ps-dot--task"/>Tasks with a deadline</span><span><i className="ps-dot ps-dot--training"/>Training</span><span><i className="ps-dot ps-dot--reminder"/>Reminders</span>
      <span className="ps-muted">The bar under each day shows how full it is. Click a day to plan it hour by hour.</span></div>
  </div>;
}

// ---- B: Priority board
function Priorities({ tasks, busy, onMove, onDone, onAdd }: { tasks: TaskRecord[]; busy: boolean; onMove: (t: TaskRecord, p: Priority) => void; onDone: (t: TaskRecord) => void; onAdd: (text: string) => Promise<boolean> }) {
  const [over, setOver] = useState<Priority | null>(null);
  const [text, setText] = useState("");
  const now = Date.now();
  const weekAgo = now - 7 * 86400000;
  const doneWeek = tasks.filter(t => t.status === "Completed" && Date.parse(t.updatedAt) > weekAgo).length;
  const overdue = tasks.filter(t => open(t) && t.deadline && Date.parse(t.deadline) < now).length;
  const drop = (p: Priority) => (e: DragEvent) => { e.preventDefault(); setOver(null); const t = tasks.find(x => x.id === e.dataTransfer.getData("text/plain")); if (t && t.priority !== p) onMove(t, p); };
  const due = (t: TaskRecord) => { if (!t.deadline) return { text: "—", late: false }; const ms = Date.parse(t.deadline); const late = ms < now;
    const d = new Date(ms); const days = Math.round((new Date(iso(d)).getTime() - new Date(iso(new Date())).getTime()) / 86400000);
    return { text: late ? "Overdue" : days === 0 ? "Today" : days === 1 ? "Tomorrow" : d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }), late }; };
  return <div className="ps-prio">
    <div className="ps-row ps-row--between">
      <span className="ps-chip">This week: <b className="ps-good">{doneWeek} done</b> · <b>{tasks.filter(open).length} open</b> · <b className="ps-bad">{overdue} overdue</b></span>
      <form className="ps-row" onSubmit={async (e: FormEvent) => { e.preventDefault(); if (await onAdd(text)) setText(""); }}>
        <input className="ps-input" value={text} maxLength={400} placeholder="Add a task… e.g. renew registration fri !critical" aria-label="Add a task" onChange={e => setText(e.target.value)}/>
        <button type="submit" className="ps-primary" disabled={busy || !text.trim()}>+ Task</button>
      </form>
    </div>
    <div className="ps-prio__grid">
      {QUADS.map(q => { const list = tasks.filter(t => open(t) && t.priority === q.priority).sort((a, b) => (a.deadline ?? "9").localeCompare(b.deadline ?? "9"));
        return <section key={q.priority} className={`zx-card ps-quad${over === q.priority ? " ps-quad--over" : ""}`} style={{ borderColor: over === q.priority ? undefined : `color-mix(in srgb, ${q.tone} 35%, transparent)` }}
          onDragOver={e => { e.preventDefault(); setOver(q.priority); }} onDragLeave={() => setOver(null)} onDrop={drop(q.priority)}>
          <header><b style={{ color: q.tone }} className="zx-title">{q.name}</b><small className="ps-muted">{q.hint} · {list.length}</small></header>
          {list.map(t => { const d = due(t); return <div key={t.id} className="ps-task zx-inset" draggable onDragStart={e => e.dataTransfer.setData("text/plain", t.id)}>
            <button type="button" className="ps-check" aria-label={`Mark ${t.title} done`} onClick={() => onDone(t)}/>
            <span className="ps-task__t">{t.title}</span><small className={d.late ? "ps-bad" : "ps-muted"}>{d.text}</small></div>; })}
          {!list.length && <small className="ps-muted">Drag a task here</small>}
        </section>; })}
    </div>
    <small className="ps-muted">Drag between boxes to change priority: Do now = Critical, Schedule = High, Quick wins = Normal, Later = Low. Done tasks leave the board.</small>
  </div>;
}

// ---- A: Day planner
function Day({ day, setDay, tasks, itemsFor, busy, onAdd, onToggle, onSchedule }: { day: string; setDay: (d: string) => void; tasks: TaskRecord[]; itemsFor: (d: string) => Item[]; busy: boolean;
  onAdd: (text: string) => Promise<boolean>; onToggle: (t: TaskRecord) => void; onSchedule: (t: TaskRecord, mins: number) => void }) {
  const [text, setText] = useState("");
  const [month, setMonth] = useState(day.slice(0, 7));
  const [over, setOver] = useState<number | null>(null);
  const now = new Date(); const today = iso(now);
  const items = itemsFor(day);
  const hours = Array.from({ length: 18 }, (_, i) => i + 6);
  const timed = items.filter(i => minutesOf(i.time) !== null);
  const allDay = items.filter(i => minutesOf(i.time) === null);
  const first = new Date(`${month}-01T12:00:00`); const pad = (first.getDay() + 6) % 7;
  const inMonth = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const openTasks = tasks.filter(open);
  const lists = useMemo(() => ({
    today: openTasks.filter(t => t.deadline && iso(new Date(t.deadline)) === today).length,
    upcoming: openTasks.filter(t => t.deadline && iso(new Date(t.deadline)) > today).length,
    overdue: openTasks.filter(t => t.deadline && Date.parse(t.deadline) < now.getTime()).length,
    undated: openTasks.filter(t => !t.deadline).length,
  }), [tasks]); // eslint-disable-line react-hooks/exhaustive-deps
  const dayTasks = tasks.filter(t => !t.archived && (t.deadline ? iso(new Date(t.deadline)) === day : open(t) && day === today));
  const shift = (n: number) => { const d = new Date(`${month}-01T12:00:00`); d.setMonth(d.getMonth() + n); setMonth(iso(d).slice(0, 7)); };
  return <div className="ps-dayview">
    <aside className="ps-dayview__side">
      <div className="zx-card ps-mini">
        <div className="ps-row ps-row--between"><b>{first.toLocaleDateString([], { month: "long", year: "numeric" })}</b><span><button type="button" onClick={() => shift(-1)} aria-label="Previous month">‹</button><button type="button" onClick={() => shift(1)} aria-label="Next month">›</button></span></div>
        <div className="ps-mini__grid">{["M", "T", "W", "T", "F", "S", "S"].map((d, i) => <small key={i}>{d}</small>)}
          {Array.from({ length: pad }, (_, i) => <span key={`p${i}`}/>)}
          {Array.from({ length: inMonth }, (_, i) => { const key = `${month}-${String(i + 1).padStart(2, "0")}`;
            return <button type="button" key={key} aria-pressed={key === day} className={`${key === day ? "ps-mini--on" : ""}${key === today ? " ps-mini--today" : ""}${itemsFor(key).length ? " ps-mini--busy" : ""}`} onClick={() => setDay(key)}>{i + 1}</button>; })}
        </div>
      </div>
      <div className="zx-card ps-lists">
        <span>Due today<b>{lists.today}</b></span><span>Upcoming<b>{lists.upcoming}</b></span><span>Overdue<b className="ps-bad">{lists.overdue}</b></span><span>No date<b>{lists.undated}</b></span>
      </div>
    </aside>
    <main className="zx-card ps-timeline">
      <header className="ps-row ps-row--between"><h2 className="zx-title">{new Date(`${day}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}</h2>
        <small className="ps-muted">{items.length} things · drag a task onto an hour to time-block it</small></header>
      {allDay.length > 0 && <div className="ps-allday">{allDay.map(i => <span key={i.key} className={`ps-item ps-item--${i.kind}`}>{i.title}</span>)}</div>}
      <div className="ps-hours">
        {hours.map(h => { const inHour = timed.filter(i => Math.floor((minutesOf(i.time) ?? 0) / 60) === h);
          return <div key={h} className={`ps-hour${over === h ? " ps-hour--over" : ""}`} onDragOver={e => { e.preventDefault(); setOver(h); }} onDragLeave={() => setOver(null)}
            onDrop={e => { e.preventDefault(); setOver(null); const t = tasks.find(x => x.id === e.dataTransfer.getData("text/plain")); if (t) onSchedule(t, h * 60); }}>
            <small>{clock(h * 60)}</small>
            <div>{inHour.map(i => <span key={i.key} className={`ps-item ps-item--${i.kind}${i.task?.status === "Completed" ? " ps-item--done" : ""}`}><b>{i.title}</b><small>{clock(minutesOf(i.time)!)}{i.kind === "event" && i.minutes ? ` · ${i.minutes} min` : ""}</small></span>)}</div>
            {day === today && now.getHours() === h && <i className="ps-now" style={{ top: `${now.getMinutes() / 60 * 100}%` }}/>}
          </div>; })}
      </div>
    </main>
    <aside className="ps-dayview__side">
      <form className="ps-quick" onSubmit={async (e: FormEvent) => { e.preventDefault(); if (await onAdd(text)) setText(""); }}>
        <input className="ps-input" value={text} maxLength={400} aria-label="Add a task" placeholder="Add a task… call bank fri 3pm !high" onChange={e => setText(e.target.value)}/>
        <button type="submit" className="ps-primary" disabled={busy || !text.trim()}>Add</button>
      </form>
      <small className="ps-muted">Understands today, tomorrow, weekdays, times like 3pm and !critical / !high / !low.</small>
      <h3 className="zx-title">{day === today ? "Tasks today" : "Tasks this day"}</h3>
      {dayTasks.map(t => <label key={t.id} className="ps-task zx-inset" draggable onDragStart={e => e.dataTransfer.setData("text/plain", t.id)}>
        <input type="checkbox" checked={t.status === "Completed"} onChange={() => onToggle(t)}/>
        <span className="ps-task__t" style={t.status === "Completed" ? { textDecoration: "line-through", opacity: .6 } : undefined}>{t.title}</span>
        <small className="ps-muted">{t.deadline ? clock(minutesOf(localTime(t.deadline)) ?? 0) : "no time"}</small>
        <i className={`ps-pri ps-pri--${t.priority.toLowerCase()}`} title={t.priority}/></label>)}
      {!dayTasks.length && <small className="ps-muted">No tasks for this day.</small>}
    </aside>
  </div>;
}
