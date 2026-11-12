import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { api, LIVE_API } from "../../core/bridge";
import type { CoreTelemetry } from "../../core/coreTelemetry";
import "./OverviewFrame.css";

/**
 * Overview, blended (Grey, 2026-10-29): the Neural Core stays the hero in the middle, with live cards around it in the
 * style of the reference dashboard (Today, Fitness and System health on the left; ZAE's helpers, suggested actions and
 * Music/News on the right, a bottom row of week trends under the core); the existing status bar stays along the bottom.
 * "Calm" hides the cards but keeps the core the same size, and a spotlight under it cycles through what matters (next up,
 * tasks, fitness, news, music, system). Calm also comes on by itself after the idle time set in Settings.
 * Every number is read from ZAE's own records; anything missing shows "—" and never a made-up value.
 */
type Event = { id: string; date: string; time: string; allDay: boolean; title: string };
type Task = { id: string; title: string; status: string; deadline: string | null; updatedAt?: string };
type Reminder = { id: string; text: string; due: string; done?: boolean };
type Day = { workout: { label: string }; eaten: { calories: number; protein: number } | null; targets: { ready: boolean; eat?: number; protein?: number } };
type Bar = { cpu: number; ramUsedGb: number; ramTotalGb: number; gpu: { use: number } | null; diskFreeGb: number; backup: string | null; model: string; voice: string };
type Song = { title: string; archived: boolean; stage: string; releaseDate: string };
type Data = {
  events: Event[] | null; tasks: Task[] | null; reminders: Reminder[] | null; day: Day | null; bar: Bar | null;
  security: { level: string; score: number } | null; songs: Song[] | null; news: { title: string }[] | null;
  weather: { place: string; temperature: number | null; condition: string } | null;
  training: { weights: { date: string; weightLb: number }[]; habits: { workouts: boolean[]; dates: string[] } } | null;
  notes: { total: number; notes: { title: string; updatedAt: string }[] } | null; topics: { name: string; sources: number }[] | null;
  inbox: { title: string; message: string; dueAt: string }[] | null; jobs: { question: string; status: string; started: string }[] | null;
};
const EMPTY: Data = { events: null, tasks: null, reminders: null, day: null, bar: null, security: null, songs: null, news: null, weather: null,
  training: null, notes: null, topics: null, inbox: null, jobs: null };
const ago = (text?: string | null) => {
  if (!text) return "";
  const d = new Date(text);
  if (Number.isNaN(d.getTime())) return "";
  const days = Math.round((Date.now() - d.getTime()) / 864e5);
  return days <= 0 ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : days === 1 ? "yesterday" : days < 7 ? `${days}d ago` : d.toLocaleDateString([], { month: "short", day: "numeric" });
};
const IDLE_KEY = "zaenia.overview.idleMinutes";
export const IDLE_CHOICES = [0, 1, 2, 5, 10, 15, 30] as const;
export function idleMinutes(): number {
  try { const value = Number(localStorage.getItem(IDLE_KEY) ?? "5"); return (IDLE_CHOICES as readonly number[]).includes(value) ? value : 5; } catch { return 5; }
}
const SUGGESTIONS = ["Plan tomorrow", "Log food", "Start workout"];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const fmt = (n: number | null | undefined) => n === null || n === undefined ? "—" : Math.round(n).toLocaleString();
const clock = (time: string) => { const [h, m] = time.split(":").map(Number); return Number.isFinite(h) ? new Date(2000, 0, 1, h, m || 0).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : time; };
const greeting = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; };

export function useOverviewData() {
  const [data, setData] = useState<Data>(EMPTY);
  const load = useCallback(async () => {
    if (!LIVE_API) return;
    const today = iso(new Date());
    const get = <T,>(path: string) => api<T>("GET", path, undefined, { timeoutMs: 30_000 }).then(value => value, () => null);
    const [events, tasks, reminders, day, bar, security, music, news, weather, training, notes, topics, inbox, jobs] = await Promise.all([
      get<{ events: Event[] }>(`/api/calendar?start=${today}&days=7`), get<{ tasks: Task[] }>("/api/tasks"), get<{ reminders: Reminder[] }>("/api/reminders"),
      get<Day>(`/api/platform/personal/training/day?day=${today}`), get<Bar>("/api/status/bar"), get<{ level: string; score: number }>("/api/security/summary"),
      get<{ songs: Song[] }>("/api/platform/personal/music/overview"), get<{ stories: { title: string }[] }>("/api/news/tech"),
      get<{ place: string; temperature: number | null; condition: string }>("/api/weather/now"),
      get<Data["training"]>("/api/platform/personal/training"), get<Data["notes"]>("/api/platform/notes?limit=5"),
      get<{ topics: { name: string; sources: number }[] }>("/api/research/notebook"),
      get<{ notifications: { title: string; message: string; dueAt: string }[] }>("/api/assistant/notifications?includeRead=true"),
      get<{ jobs: { question: string; status: string; started: string }[] }>("/api/research/agent"),
    ]);
    setData({ events: events?.events ?? null, tasks: tasks?.tasks ?? null, reminders: reminders?.reminders ?? null, day, bar, security,
      songs: music?.songs ?? null, news: news?.stories ?? null, weather, training, notes, topics: topics?.topics ?? null,
      inbox: inbox?.notifications ?? null, jobs: jobs?.jobs ?? null });
  }, []);
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 60_000);
    const changed = () => void load();
    window.addEventListener("zae:records-changed", changed);
    return () => { window.clearInterval(timer); window.removeEventListener("zae:records-changed", changed); };
  }, [load]);
  return data;
}

function Card({ kicker, title, tone, onOpen, children, side, hot }: { kicker: string; title: string; tone?: string; onOpen?: () => void; children: ReactNode; side?: ReactNode; hot?: boolean }) {
  return <section className={hot ? "ov-card ov-card--hot zx-card" : "ov-card zx-card"} style={tone ? { "--ov-tone": tone } as CSSProperties : undefined}>
    <header><span className="ov-icon" aria-hidden="true"/><span className="ov-head"><small>{kicker}</small><b className="zx-title">{title}</b></span>
      {side}{onOpen && <button type="button" className="ov-open" onClick={onOpen} aria-label={`Open ${title}`}>↗</button>}</header>
    {children}
  </section>;
}

/** True after `minutes` without a key, click, touch, scroll or mouse move (0 = never). */
export function useIdle(minutes: number) {
  const [idle, setIdle] = useState(false);
  useEffect(() => {
    if (!minutes) { setIdle(false); return; }
    let timer = window.setTimeout(() => setIdle(true), minutes * 60_000);
    const active = () => { setIdle(false); window.clearTimeout(timer); timer = window.setTimeout(() => setIdle(true), minutes * 60_000); };
    const events = ["pointermove", "pointerdown", "keydown", "wheel", "touchstart", "zae:hand-activity"] as const;
    events.forEach(name => window.addEventListener(name, active, { passive: true }));
    return () => { window.clearTimeout(timer); events.forEach(name => window.removeEventListener(name, active)); };
  }, [minutes]);
  return idle;
}

/** Settings tab: how long the Overview waits before switching itself to Calm view. */
export function OverviewIdleSetting() {
  const [value, setValue] = useState(idleMinutes);
  const choose = (next: number) => {
    setValue(next);
    try { localStorage.setItem(IDLE_KEY, String(next)); } catch { /* optional */ }
    window.dispatchEvent(new CustomEvent("zae:overview-idle", { detail: next }));
  };
  return <div className="detail-panel__block ov-idle-setting">
    <div className="section-heading"><span className="subheading">OVERVIEW</span><span>{value ? `${value} MIN` : "OFF"}</span></div>
    <h2>Calm view when idle</h2>
    <p>After this long without you touching the PC or phone, the Overview hides its cards and cycles through what matters. Any touch brings the cards back.</p>
    <div className="choice-row" role="radiogroup" aria-label="Calm view after">
      {IDLE_CHOICES.map(minutes => <button key={minutes} type="button" role="radio" aria-checked={value === minutes}
        className={value === minutes ? "choice choice--active" : "choice"} onClick={() => choose(minutes)}>{minutes ? `${minutes} min` : "Off"}</button>)}
    </div>
  </div>;
}

function Meter({ label, value, max = 100, tone }: { label: string; value: number | null; max?: number; tone?: string }) {
  const share = value === null ? 0 : Math.max(0, Math.min(1, value / max));
  return <div className="ov-meter"><span>{label}</span><b>{value === null ? "—" : `${Math.round(value)}${max === 100 ? "%" : ""}`}</b>
    <i><em style={{ width: `${share * 100}%`, background: tone }}/></i></div>;
}

export type AppTab = { id: string; label: string; icon: ReactNode };

export function OverviewFrame({ children, telemetry, look, style, onOpen, onAsk, calm, onCalm, docked, phone, apps = [] }: {
  children: ReactNode; telemetry: CoreTelemetry | null; look: string; style?: CSSProperties; docked: boolean; phone: boolean; apps?: AppTab[];
  onOpen: (section: string) => void; onAsk: (text: string) => void; calm: boolean; onCalm: (calm: boolean) => void;
}) {
  void apps;
  const data = useOverviewData();
  const [idleAfter, setIdleAfter] = useState(idleMinutes);
  useEffect(() => { const update = () => setIdleAfter(idleMinutes()); window.addEventListener("zae:overview-idle", update); return () => window.removeEventListener("zae:overview-idle", update); }, []);
  // Calm view is a full-screen layer now (App: CalmView), started by idle anywhere, the button or a sleep phrase.
  const idle = false;
  void idleAfter;
  const quiet = calm || idle;
  const [spot, setSpot] = useState(0);
  const holdUntil = useRef(0);
  const [now, setNow] = useState(() => new Date());
  // Navigation is owned by NavigationHub, shared with the top bar and phone.
  // After a wake-up call: ZAE's line on the dashboard and the card it's about brought forward (for a minute).
  const [woke, setWoke] = useState<{ line: string; focus: string } | null>(null);
  useEffect(() => {
    let timer = 0;
    const show = (event: globalThis.Event) => { setWoke((event as CustomEvent<{ line: string; focus: string }>).detail); window.clearTimeout(timer); timer = window.setTimeout(() => setWoke(null), 60_000); };
    window.addEventListener("zae:wake-focus", show);
    return () => { window.clearTimeout(timer); window.removeEventListener("zae:wake-focus", show); };
  }, []);
  const hot = (focus: string) => woke?.focus === focus;
  useEffect(() => { const timer = window.setInterval(() => setNow(new Date()), 30_000); return () => window.clearInterval(timer); }, []);
  const today = iso(now);
  const nowTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;

  const nextEvent = data.events?.filter(e => e.date > today || (e.date === today && (e.allDay || e.time >= nowTime)))
    .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`))[0] ?? null;
  const open = data.tasks?.filter(t => t.status !== "Completed") ?? null;
  const dueToday = open?.filter(t => t.deadline?.slice(0, 10) === today) ?? [];
  const overdue = open?.filter(t => t.deadline && t.deadline.slice(0, 10) < today) ?? [];
  const nextReminder = data.reminders?.filter(r => !r.done && new Date(r.due) >= now).sort((a, b) => a.due.localeCompare(b.due))[0] ?? null;
  const eat = data.day?.targets.ready ? data.day.targets.eat ?? null : null;
  const eaten = data.day?.eaten?.calories ?? null;
  const protein = data.day?.eaten?.protein ?? null;
  const proteinGoal = data.day?.targets.ready ? data.day.targets.protein ?? null : null;
  const ram = data.bar ? data.bar.ramUsedGb / Math.max(1, data.bar.ramTotalGb) * 100 : null;
  const health = data.security?.score ?? null;
  const modules = telemetry?.modules ?? [];
  const ready = modules.filter(m => m.phase === "ready" || m.phase === "working").length;
  const songs = data.songs?.filter(s => !s.archived) ?? null;
  const release = songs?.filter(s => s.releaseDate && s.releaseDate >= today).sort((a, b) => a.releaseDate.localeCompare(b.releaseDate))[0] ?? null;
  const ring = 2 * Math.PI * 52;

  const headline = nextEvent ? `Next: ${nextEvent.title}${nextEvent.allDay ? (nextEvent.date === today ? " today" : " tomorrow") : ` at ${clock(nextEvent.time)}${nextEvent.date === today ? "" : " tomorrow"}`}.` : "Nothing else on the calendar today.";
  const taskLine = open === null ? "" : dueToday.length || overdue.length ? ` ${dueToday.length} task${dueToday.length === 1 ? "" : "s"} due today${overdue.length ? `, ${overdue.length} overdue` : ""}.` : " No tasks due today.";

  const kcalLeft = eat !== null && eaten !== null ? Math.max(0, eat - eaten) : null;
  const todayLines = <ul className="ov-lines">
    {nextEvent && <li><span>{nextEvent.title}</span><b>{nextEvent.allDay ? "All day" : clock(nextEvent.time)}</b></li>}
    {nextReminder && <li><span>{nextReminder.text}</span><b>{new Date(nextReminder.due).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</b></li>}
    {[...overdue, ...dueToday].slice(0, 2).map(t => <li key={t.id}><span>{t.title}</span><b>{t.deadline!.slice(0, 10) < today ? "overdue" : "today"}</b></li>)}
    {!nextEvent && !nextReminder && dueToday.length + overdue.length === 0 && <li className="ov-muted">Clear for now.</li>}
  </ul>;
  const askCard = <Card kicker="Suggested" title="Ask ZAE" tone="#c08cff">
    <ol className="ov-actions">
      {nextEvent && <li><button type="button" onClick={() => onAsk(`Help me get ready for ${nextEvent.title}`)}><b>Get ready for {nextEvent.title}</b><small>From your calendar</small></button></li>}
      {overdue[0] && <li><button type="button" onClick={() => onAsk(`Help me finish "${overdue[0].title}"`)}><b>Finish "{overdue[0].title}"</b><small>Overdue task</small></button></li>}
      {kcalLeft !== null && kcalLeft > 300 && <li><button type="button" onClick={() => onAsk(`What should I eat to hit about ${fmt(kcalLeft)} more calories${proteinGoal && protein !== null ? ` and ${fmt(proteinGoal - protein)} g protein` : ""}?`)}>
        <b>Plan the rest of today's food</b><small>{fmt(kcalLeft)} kcal left</small></button></li>}
      <li><button type="button" onClick={() => onAsk("Plan tomorrow")}><b>Plan tomorrow</b><small>Calendar, tasks and training</small></button></li>
    </ol>
  </Card>;
  const musicCard = <Card kicker="Music & news" title="Following" tone="#e0c08a" hot={hot("news")}>
    <ul className="ov-lines">
      <li><button type="button" className="ov-link" onClick={() => onOpen("music")}>{songs === null ? "Music" : `${songs.length} song${songs.length === 1 ? "" : "s"} in progress`}</button>
        <b>{release ? `${release.title} · ${new Date(`${release.releaseDate}T00:00`).toLocaleDateString([], { month: "short", day: "numeric" })}` : "No release date"}</b></li>
      {(data.news ?? []).slice(0, 2).map((story, index) => <li key={index}><button type="button" className="ov-link" onClick={() => onOpen("news")}>{story.title}</button></li>)}
      {data.news?.length === 0 && <li className="ov-muted">No new stories.</li>}
    </ul>
  </Card>;
  const calmButton = <button type="button" className="ov-calm-btn" aria-pressed={quiet} onClick={() => onCalm(!quiet)}>
    {quiet ? "Show dashboard" : "Calm view"}</button>;
  const hero = <div className="ov-hero">
    {woke && <p className="ov-woke" role="status"><b>ZAE</b> {woke.line}</p>}
    <span className="ov-kicker">{greeting()}, Grey{data.weather?.temperature !== null && data.weather ? ` · ${Math.round(data.weather.temperature!)}° ${data.weather.condition.toLowerCase()}` : ""}</span>
    <p>{headline}{taskLine}</p>
    <div className="ov-chips">{SUGGESTIONS.map(text => <button key={text} type="button" onClick={() => onAsk(text)}>{text}</button>)}{calmButton}</div>
  </div>;

  // Week trends under the core, like the reference's bottom row.
  const week = Array.from({ length: 7 }, (_, i) => { const d = new Date(now); d.setDate(d.getDate() - 6 + i); return iso(d); });
  const doneByDay = week.map(day => data.tasks?.filter(t => t.status === "Completed" && t.updatedAt?.slice(0, 10) === day).length ?? 0);
  const doneTotal = doneByDay.reduce((a, b) => a + b, 0);
  const peakDone = Math.max(1, ...doneByDay);
  const weights = (data.training?.weights ?? []).slice(-30);
  const lastWeight = weights.length ? weights[weights.length - 1].weightLb : null;
  const weightChange = weights.length > 1 ? weights[weights.length - 1].weightLb - weights[0].weightLb : null;
  const wMin = Math.min(...weights.map(w => w.weightLb)), wMax = Math.max(...weights.map(w => w.weightLb));
  const spark = weights.map((w, i) => `${(i / Math.max(1, weights.length - 1)) * 200},${46 - ((w.weightLb - wMin) / Math.max(0.1, wMax - wMin)) * 40}`).join(" ");
  const workouts = data.training?.habits.workouts.slice(-7) ?? [];
  const sources = data.topics?.reduce((sum, t) => sum + t.sources, 0) ?? null;
  // Day board (from preview 3, made small): the next few things, flight-board style.
  const tomorrow = iso(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1));
  const boardRows = [
    ...(data.events ?? []).filter(e => e.date > today || (e.date === today && (e.allDay || e.time >= nowTime)))
      .map(e => ({ at: `${e.date} ${e.allDay ? "00:00" : e.time}`, time: e.allDay ? "ALL DAY" : e.time.slice(0, 5), what: e.title, status: e.date === today ? "TODAY" : e.date === tomorrow ? "TOMORROW" : e.date.slice(5), tone: "#8fc8ff" })),
    ...overdue.map(task => ({ at: "0", time: "LATE", what: task.title, status: "OVERDUE", tone: "#ffb4a2" })),
    ...dueToday.map(task => ({ at: `${today} ${task.deadline!.slice(11, 16) || "23:59"}`, time: task.deadline!.slice(11, 16) || "TODAY", what: task.title, status: "DUE", tone: "#e0a353" })),
    ...(data.reminders ?? []).filter(r => !r.done && new Date(r.due) >= now).map(r => { const d = new Date(r.due); return { at: `${iso(d)} ${d.toTimeString().slice(0, 5)}`, time: d.toTimeString().slice(0, 5), what: r.text, status: "REMINDER", tone: "#c08cff" }; }),
  ].sort((a, b) => a.at.localeCompare(b.at)).slice(0, 5);
  const boardTasks = (open ?? []).filter(task => !overdue.includes(task) && !dueToday.includes(task)).slice(0, Math.max(0, 5 - boardRows.length))
    .map(task => ({ at: "z", time: task.deadline ? task.deadline.slice(5, 10) : "OPEN", what: task.title, status: "TASK", tone: "#9fb6cf" }));
  boardRows.push(...boardTasks);
  // Rails (Grey, 2026-10-31: fill the blank space): the rest of the week, ZAE's inbox, research and notes.
  const weekLater = (data.events ?? []).filter(e => e.date > tomorrow).sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`)).slice(0, 5);
  const weekCard = <Card kicker="This week" title="Coming up" tone="#8fc8ff" onOpen={() => onOpen("tasks")}>
    <ul className="ov-lines">{weekLater.map(e => <li key={e.id}><span>{e.title}</span>
      <b>{new Date(`${e.date}T00:00`).toLocaleDateString([], { weekday: "short" })}{e.allDay ? "" : ` ${clock(e.time)}`}</b></li>)}
      {weekLater.length === 0 && <li className="ov-muted">Nothing else on the calendar this week.</li>}</ul>
  </Card>;
  const inboxCard = <Card kicker="Follow-ups" title="From ZAE" tone="#c08cff" onOpen={() => onOpen("assistant")}>
    <ul className="ov-lines">{(data.inbox ?? []).slice(0, 4).map((n, i) => <li key={i}><span title={n.message}>{n.title}</span><b>{ago(n.dueAt)}</b></li>)}
      {data.inbox?.length === 0 && <li className="ov-muted">Nothing new from ZAE.</li>}
      {data.inbox === null && <li className="ov-muted">Inbox unavailable.</li>}</ul>
  </Card>;
  const researchCard = <Card kicker="Research & notes" title="Recently" tone="#7fd1c8" onOpen={() => onOpen("research")}>
    <ul className="ov-lines">
      {(data.jobs ?? []).slice(0, 2).map((j, i) => <li key={`j${i}`}><button type="button" className="ov-link" onClick={() => onOpen("research")}>{j.question}</button><b>{j.status === "done" ? "ready" : j.status}</b></li>)}
      {(data.notes?.notes ?? []).slice(0, 4).map((n, i) => <li key={`n${i}`}><button type="button" className="ov-link" onClick={() => onOpen("notes")}>{n.title}</button><b>{ago(n.updatedAt)}</b></li>)}
      {!(data.jobs?.length) && !(data.notes?.notes.length) && <li className="ov-muted">No research or notes yet.</li>}
    </ul>
  </Card>;
  const bottomRow = <div className="ov-bottom">
    <Card kicker="Day board" title="Next up" tone="#e0a353" onOpen={() => onOpen("tasks")} hot={hot("calendar")}>
      <ul className="ov-board">{boardRows.map((row, i) => <li key={i}><b>{row.time}</b><span>{row.what}</span><em style={{ color: row.tone }}>● {row.status}</em></li>)}
        {boardRows.length === 0 && <li className="ov-muted">Nothing scheduled.</li>}</ul>
    </Card>
    <Card kicker="Activity · this week" title="Tasks done" tone="#8fc8ff" onOpen={() => onOpen("tasks")} side={<span className="ov-pill">{data.tasks === null ? "—" : doneTotal}</span>}>
      <div className="ov-week" aria-label={`Tasks completed each day this week: ${doneByDay.join(", ")}`}>
        {doneByDay.map((count, i) => <span key={week[i]}><i style={{ height: `${Math.max(4, count / peakDone * 100)}%` }} className={count ? "" : "ov-week--none"}/>
          <small>{new Date(`${week[i]}T00:00`).toLocaleDateString([], { weekday: "narrow" })}</small></span>)}
      </div>
    </Card>
    <Card kicker="Fitness · 30 days" title="Weight trend" tone="#7fe3a8" onOpen={() => onOpen("fitness")}
      side={<span className="ov-pill">{weightChange === null ? "—" : `${weightChange > 0 ? "+" : ""}${weightChange.toFixed(1)} lb`}</span>}>
      <div className="ov-trend">
        <span><b>{lastWeight === null ? "—" : lastWeight.toFixed(1)}</b><small>lb now</small></span>
        {weights.length > 1 ? <svg viewBox="0 0 200 50" preserveAspectRatio="none" aria-hidden="true"><polyline points={spark}/></svg> : <small className="ov-muted">Log weigh-ins to see the trend.</small>}
      </div>
      <div className="ov-dots" aria-label={`Workouts this week: ${workouts.filter(Boolean).length} of ${workouts.length}`}>
        {workouts.map((done, i) => <i key={i} className={done ? "ov-dot--on" : ""}/>)}<small>{workouts.filter(Boolean).length} workouts this week</small></div>
    </Card>
    <Card kicker="Knowledge" title="Notes & research" tone="#c08cff" onOpen={() => onOpen("notes")}>
      <div className="ov-stats">
        <span><small>Notes</small><b>{data.notes ? data.notes.total : "—"}</b></span>
        <span><small>Topics</small><b>{data.topics ? data.topics.length : "—"}</b></span>
        <span><small>Sources</small><b>{sources ?? "—"}</b></span>
      </div>
      <ul className="ov-lines">{(data.notes?.notes ?? []).slice(0, 2).map((note, i) => <li key={i}><span>{note.title}</span><b>{new Date(note.updatedAt).toLocaleDateString([], { month: "short", day: "numeric" })}</b></li>)}</ul>
    </Card>
  </div>;

  // Calm view's spotlight: one thing at a time, cycling every 8 seconds. Picking a dot holds that item for 20 seconds;
  // resting the mouse over it does not stop it (when idle, the mouse is usually left there).
  const spotlight: { kicker: string; big: string; detail: string; tab: string; tone: string }[] = [
    { kicker: "Next up", big: nextEvent ? nextEvent.title : "Nothing else today", tone: "#8fc8ff", tab: "tasks",
      detail: nextEvent ? `${nextEvent.allDay ? "All day" : clock(nextEvent.time)}${nextEvent.date === today ? " today" : " tomorrow"}` : nextReminder ? `Reminder: ${nextReminder.text}` : "Your calendar is clear." },
    ...(open === null ? [] : [{ kicker: "Tasks", big: `${dueToday.length} due today${overdue.length ? ` · ${overdue.length} overdue` : ""}`, tone: "#ffb4a2", tab: "tasks",
      detail: [...overdue, ...dueToday].slice(0, 2).map(t => t.title).join(" · ") || `${open.length} open, none due today.` }]),
    ...(kcalLeft === null ? [] : [{ kicker: "Fitness & health", big: `${fmt(kcalLeft)} kcal left`, tone: "#7fe3a8", tab: "fitness",
      detail: `${protein === null ? "—" : fmt(protein)}${proteinGoal ? ` of ${fmt(proteinGoal)}` : ""} g protein · ${data.day?.workout.label || "today's training"}` }]),
    ...(data.news ?? []).slice(0, 3).map(story => ({ kicker: "News", big: story.title, detail: "Tech news you follow", tab: "news", tone: "#c08cff" })),
    ...(songs === null ? [] : [{ kicker: "Music", big: release ? `${release.title} releases ${new Date(`${release.releaseDate}T00:00`).toLocaleDateString([], { month: "short", day: "numeric" })}` : `${songs.length} song${songs.length === 1 ? "" : "s"} in progress`,
      detail: songs.slice(0, 2).map(song => `${song.title} · ${song.stage}`).join("  ·  ") || "No songs yet.", tab: "music", tone: "#e0c08a" }]),
    { kicker: "System", big: health === null ? "Status" : `Security ${health} · ${data.security?.level ?? ""}`, tone: "#9fb6cf", tab: "status",
      detail: `${modules.length ? `${ready} of ${modules.length} parts ready` : "Status feed unavailable"}${data.bar ? ` · CPU ${Math.round(data.bar.cpu)}%` : ""}` },
  ];
  useEffect(() => {
    if (!quiet) return;
    const timer = window.setInterval(() => { if (Date.now() > holdUntil.current) setSpot(index => index + 1); }, 8000);
    return () => window.clearInterval(timer);
  }, [quiet]);
  const current = spotlight[spot % spotlight.length];
  const spotlightPanel = <section className="ov-spotlight zx-card" style={{ "--ov-tone": current.tone } as CSSProperties} aria-live="polite">
    <button key={spot % spotlight.length} type="button" className="ov-spotlight__body" onClick={() => onOpen(current.tab)}>
      <small>{current.kicker}</small><b>{current.big}</b><span>{current.detail}</span></button>
    <div className="ov-spotlight__dots" role="tablist" aria-label="Spotlight">
      {spotlight.map((item, i) => <button key={i} type="button" role="tab" aria-selected={i === spot % spotlight.length} aria-label={`${item.kicker}: ${item.big}`} onClick={() => { holdUntil.current = Date.now() + 20_000; setSpot(i); }}/>)}
    </div>
  </section>;

  // While windows are open the core docks in a corner and the cards step aside.
  if (docked) return <>{children}</>;

  // Phone (sized for an iPhone 16 Pro, 402 × 874): one scrolling app screen. A smaller core, the greeting and quick asks
  // in a swipeable row, four widget tiles, then Today, Ask ZAE and Music & news as full-width cards.
  if (phone) return <div className="ov-wrap ov-wrap--phone" data-look={look} style={style}><div className={`ov ov-phone`}>
    <div className="ov-phone__core">{children}</div>
    {hero}
    {quiet && spotlightPanel}
    {!quiet && <>
      <div className="ov-tiles">
        <button type="button" className="ov-tile zx-card" style={{ "--ov-tone": "#8fc8ff" } as CSSProperties} onClick={() => onOpen("tasks")}>
          <small>Tasks</small><b>{open === null ? "—" : open.length}</b><span>{open === null ? "open" : `${dueToday.length} due · ${overdue.length} overdue`}</span></button>
        <button type="button" className="ov-tile zx-card" style={{ "--ov-tone": "#7fe3a8" } as CSSProperties} onClick={() => onOpen("fitness")}>
          <small>Calories left</small><b>{fmt(kcalLeft)}</b><span>{protein === null ? "protein —" : `${fmt(protein)}${proteinGoal ? ` / ${fmt(proteinGoal)}` : ""} g protein`}</span>
          <i className="ov-tile__bar"><em style={{ width: `${eat && eaten !== null ? Math.min(100, eaten / eat * 100) : 0}%` }}/></i></button>
        <button type="button" className="ov-tile zx-card" style={{ "--ov-tone": "var(--accent)" } as CSSProperties} onClick={() => onOpen("status")}>
          <small>Security</small><b>{health ?? "—"}</b><span>{data.security?.level ?? "—"}</span>
          <i className="ov-tile__bar"><em style={{ width: `${health ?? 0}%` }}/></i></button>
        <button type="button" className="ov-tile zx-card" style={{ "--ov-tone": "#e0a353" } as CSSProperties} onClick={() => onOpen("status")}>
          <small>ZAE's systems</small><b>{modules.length ? `${ready}/${modules.length}` : "—"}</b><span>{modules.find(m => m.phase === "working")?.name ? `${modules.find(m => m.phase === "working")!.name} working` : "ready"}</span></button>
      </div>
      <Card kicker="Today" title={now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })} tone="#8fc8ff" onOpen={() => onOpen("tasks")}>{todayLines}</Card>
      {askCard}
      {musicCard}
      {bottomRow}
    </>}
  </div></div>;

  return <div className="ov-wrap" data-look={look} style={style}><div className={`ov${quiet ? " ov--calm" : ""}`}>
    <div className="ov-rail ov-rail--left" aria-hidden={quiet || undefined} inert={quiet || undefined}>
      <Card kicker="Today" title={now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })} tone="#8fc8ff" onOpen={() => onOpen("tasks")} hot={hot("tasks")}>
        <div className="ov-stats">
          <span><small>Open tasks</small><b>{open === null ? "—" : open.length}</b></span>
          <span><small>Due today</small><b>{open === null ? "—" : dueToday.length}</b></span>
          <span className={overdue.length ? "ov-warn" : ""}><small>Overdue</small><b>{open === null ? "—" : overdue.length}</b></span>
        </div>
        {todayLines}
      </Card>
      <Card kicker="Fitness & health" title={data.day?.workout.label || "Today's training"} tone="#7fe3a8" onOpen={() => onOpen("fitness")} hot={hot("fitness")}>
        <div className="ov-big"><b>{fmt(kcalLeft)}</b><small>kcal left{eat !== null ? ` of ${fmt(eat)}` : ""}</small></div>
        <Meter label="Eaten" value={eaten} max={eat ?? 2000} tone="var(--accent)"/>
        <Meter label="Protein (g)" value={protein} max={proteinGoal ?? 150} tone="#5fb4ff"/>
      </Card>
      <Card kicker="System" title="Health" tone="#9fb6cf" onOpen={() => onOpen("status")} hot={hot("system")} side={<span className="ov-pill">{data.security?.level ?? "—"}</span>}>
        <div className="ov-health">
          <svg viewBox="0 0 120 120" role="img" aria-label={`Security score ${health ?? "unknown"}`}>
            <circle cx="60" cy="60" r="52" className="ov-ring-bg"/>
            <circle cx="60" cy="60" r="52" className="ov-ring" strokeDasharray={`${ring * (health ?? 0) / 100} ${ring}`} transform="rotate(-90 60 60)"/>
            <text x="60" y="58" textAnchor="middle" className="ov-ring-num">{health ?? "—"}</text><text x="60" y="76" textAnchor="middle" className="ov-ring-label">SECURITY</text>
          </svg>
          <div className="ov-health__meters">
            <Meter label="CPU" value={data.bar?.cpu ?? telemetry?.system?.cpu ?? null}/>
            <Meter label="Memory" value={ram ?? telemetry?.system?.memory ?? null}/>
            <Meter label="GPU" value={data.bar?.gpu?.use ?? null}/>
          </div>
        </div>
      </Card>
      {weekCard}
      {inboxCard}
    </div>

    <div className="ov-center">
      {children}
      {hero}
      {quiet ? spotlightPanel : bottomRow}
    </div>

    <div className="ov-rail ov-rail--right" aria-hidden={quiet || undefined} inert={quiet || undefined}>
      <Card kicker="Active" title="ZAE's systems" tone="#e0a353" onOpen={() => onOpen("system")} side={<span className="ov-pill">{ready} / {modules.length}</span>}>
        <ul className="ov-agents">{modules.slice(0, 5).map(m => <li key={m.id} className={`ov-agent ov-agent--${m.phase}`}>
          <span><i/>{m.name}</span><small>{m.phase === "ready" ? "Ready" : m.phase === "working" ? "Working" : m.phase === "pending" ? "Waiting" : "Needs a look"}</small>
          {m.detail && <em title={m.detail}>{m.detail}</em>}</li>)}
          {modules.length === 0 && <li className="ov-muted">Status feed unavailable.</li>}</ul>
      </Card>
      {askCard}
      {musicCard}
      {researchCard}
    </div>
  </div></div>;
}
