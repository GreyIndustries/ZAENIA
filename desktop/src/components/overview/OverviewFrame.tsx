import { useCallback, useEffect, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { api, LIVE_API } from "../../core/bridge";
import type { CoreTelemetry } from "../../core/coreTelemetry";
import "./OverviewFrame.css";

/**
 * Overview, blended (Grey, 2026-10-29): the Neural Core stays the hero in the middle, with live cards around it in the
 * style of the reference dashboard (Today, Fitness and System health on the left; ZAE's helpers, suggested actions and
 * Music/News on the right); the existing status bar stays along the bottom. "Calm" hides the cards and leaves the core alone
 * (preview C). Every number is read from ZAE's own records; anything missing shows "—" and never a made-up value.
 */
type Event = { id: string; date: string; time: string; allDay: boolean; title: string };
type Task = { id: string; title: string; status: string; deadline: string | null };
type Reminder = { id: string; text: string; due: string; done?: boolean };
type Day = { workout: { label: string }; eaten: { calories: number; protein: number } | null; targets: { ready: boolean; eat?: number; protein?: number } };
type Bar = { cpu: number; ramUsedGb: number; ramTotalGb: number; gpu: { use: number } | null; diskFreeGb: number; backup: string | null; model: string; voice: string };
type Song = { title: string; archived: boolean; stage: string; releaseDate: string };
type Data = {
  events: Event[] | null; tasks: Task[] | null; reminders: Reminder[] | null; day: Day | null; bar: Bar | null;
  security: { level: string; score: number } | null; songs: Song[] | null; news: { title: string }[] | null;
  weather: { place: string; temperature: number | null; condition: string } | null;
};
const EMPTY: Data = { events: null, tasks: null, reminders: null, day: null, bar: null, security: null, songs: null, news: null, weather: null };
const SUGGESTIONS = ["Brief me", "Plan tomorrow", "Log food", "Start workout"];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const fmt = (n: number | null | undefined) => n === null || n === undefined ? "—" : Math.round(n).toLocaleString();
const clock = (time: string) => { const [h, m] = time.split(":").map(Number); return Number.isFinite(h) ? new Date(2000, 0, 1, h, m || 0).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : time; };
const greeting = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; };

function useOverviewData() {
  const [data, setData] = useState<Data>(EMPTY);
  const load = useCallback(async () => {
    if (!LIVE_API) return;
    const today = iso(new Date());
    const get = <T,>(path: string) => api<T>("GET", path, undefined, { timeoutMs: 30_000 }).then(value => value, () => null);
    const [events, tasks, reminders, day, bar, security, music, news, weather] = await Promise.all([
      get<{ events: Event[] }>(`/api/calendar?start=${today}&days=2`), get<{ tasks: Task[] }>("/api/tasks"), get<{ reminders: Reminder[] }>("/api/reminders"),
      get<Day>(`/api/platform/personal/training/day?day=${today}`), get<Bar>("/api/status/bar"), get<{ level: string; score: number }>("/api/security/summary"),
      get<{ songs: Song[] }>("/api/platform/personal/music/overview"), get<{ stories: { title: string }[] }>("/api/news/tech"),
      get<{ place: string; temperature: number | null; condition: string }>("/api/weather/now"),
    ]);
    setData({ events: events?.events ?? null, tasks: tasks?.tasks ?? null, reminders: reminders?.reminders ?? null, day, bar, security,
      songs: music?.songs ?? null, news: news?.stories ?? null, weather });
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

function Card({ kicker, title, tone, onOpen, children, side }: { kicker: string; title: string; tone?: string; onOpen?: () => void; children: ReactNode; side?: ReactNode }) {
  return <section className="ov-card zx-card" style={tone ? { "--ov-tone": tone } as CSSProperties : undefined}>
    <header><span className="ov-icon" aria-hidden="true"/><span className="ov-head"><small>{kicker}</small><b className="zx-title">{title}</b></span>
      {side}{onOpen && <button type="button" className="ov-open" onClick={onOpen} aria-label={`Open ${title}`}>↗</button>}</header>
    {children}
  </section>;
}

function Meter({ label, value, max = 100, tone }: { label: string; value: number | null; max?: number; tone?: string }) {
  const share = value === null ? 0 : Math.max(0, Math.min(1, value / max));
  return <div className="ov-meter"><span>{label}</span><b>{value === null ? "—" : `${Math.round(value)}${max === 100 ? "%" : ""}`}</b>
    <i><em style={{ width: `${share * 100}%`, background: tone }}/></i></div>;
}

export function OverviewFrame({ children, telemetry, look, style, onOpen, onAsk, calm, onCalm, docked, phone }: {
  children: ReactNode; telemetry: CoreTelemetry | null; look: string; style?: CSSProperties; docked: boolean; phone: boolean;
  onOpen: (section: string) => void; onAsk: (text: string) => void; calm: boolean; onCalm: (calm: boolean) => void;
}) {
  const data = useOverviewData();
  const [now, setNow] = useState(() => new Date());
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
  const musicCard = <Card kicker="Music & news" title="Following" tone="#e0c08a">
    <ul className="ov-lines">
      <li><button type="button" className="ov-link" onClick={() => onOpen("music")}>{songs === null ? "Music" : `${songs.length} song${songs.length === 1 ? "" : "s"} in progress`}</button>
        <b>{release ? `${release.title} · ${new Date(`${release.releaseDate}T00:00`).toLocaleDateString([], { month: "short", day: "numeric" })}` : "No release date"}</b></li>
      {(data.news ?? []).slice(0, 2).map((story, index) => <li key={index}><button type="button" className="ov-link" onClick={() => onOpen("news")}>{story.title}</button></li>)}
      {data.news?.length === 0 && <li className="ov-muted">No new stories.</li>}
    </ul>
  </Card>;
  const tags = <div className="ov-center__tags">
    <span className="ov-tag"><i/>{telemetry ? `${ready} / ${modules.length} modules ready` : "Core"}</span>
    <button type="button" className="ov-tag ov-tag--btn" aria-pressed={calm} onClick={() => onCalm(!calm)}>{calm ? "Show dashboard" : "Calm view"}</button>
  </div>;
  const hero = <div className="ov-hero">
    <span className="ov-kicker">{greeting()}, Grey{data.weather?.temperature !== null && data.weather ? ` · ${Math.round(data.weather.temperature!)}° ${data.weather.condition.toLowerCase()}` : ""}</span>
    <p>{headline}{taskLine}</p>
    <div className="ov-chips">{SUGGESTIONS.map(text => <button key={text} type="button" onClick={() => onAsk(text)}>{text}</button>)}</div>
  </div>;

  // While windows are open the core docks in a corner and the cards step aside.
  if (docked) return <>{children}</>;

  // Phone (sized for an iPhone 16 Pro, 402 × 874): one scrolling app screen. A smaller core, the greeting and quick asks
  // in a swipeable row, four widget tiles, then Today, Ask ZAE and Music & news as full-width cards.
  if (phone) return <div className="ov-wrap ov-wrap--phone" data-look={look} style={style}><div className="ov ov-phone">
    {tags}
    <div className="ov-phone__core">{children}</div>
    {hero}
    {!calm && <>
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
    </>}
  </div></div>;

  return <div className="ov-wrap" data-look={look} style={style}><div className={`ov${calm ? " ov--calm" : ""}`}>
    {!calm && <div className="ov-rail ov-rail--left">
      <Card kicker="Today" title={now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })} tone="#8fc8ff" onOpen={() => onOpen("tasks")}>
        <div className="ov-stats">
          <span><small>Open tasks</small><b>{open === null ? "—" : open.length}</b></span>
          <span><small>Due today</small><b>{open === null ? "—" : dueToday.length}</b></span>
          <span className={overdue.length ? "ov-warn" : ""}><small>Overdue</small><b>{open === null ? "—" : overdue.length}</b></span>
        </div>
        {todayLines}
      </Card>
      <Card kicker="Fitness & health" title={data.day?.workout.label || "Today's training"} tone="#7fe3a8" onOpen={() => onOpen("fitness")}>
        <div className="ov-big"><b>{fmt(kcalLeft)}</b><small>kcal left{eat !== null ? ` of ${fmt(eat)}` : ""}</small></div>
        <Meter label="Eaten" value={eaten} max={eat ?? 2000} tone="var(--accent)"/>
        <Meter label="Protein (g)" value={protein} max={proteinGoal ?? 150} tone="#5fb4ff"/>
      </Card>
      <Card kicker="System" title="Health" tone="#9fb6cf" onOpen={() => onOpen("status")} side={<span className="ov-pill">{data.security?.level ?? "—"}</span>}>
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
    </div>}

    <div className="ov-center">
      {tags}
      {children}
      {hero}
    </div>

    {!calm && <div className="ov-rail ov-rail--right">
      <Card kicker="Active" title="ZAE's systems" tone="#e0a353" onOpen={() => onOpen("system")} side={<span className="ov-pill">{ready} / {modules.length}</span>}>
        <ul className="ov-agents">{modules.slice(0, 5).map(m => <li key={m.id} className={`ov-agent ov-agent--${m.phase}`}>
          <span><i/>{m.name}</span><small>{m.phase === "ready" ? "Ready" : m.phase === "working" ? "Working" : m.phase === "pending" ? "Waiting" : "Needs a look"}</small>
          {m.detail && <em title={m.detail}>{m.detail}</em>}</li>)}
          {modules.length === 0 && <li className="ov-muted">Status feed unavailable.</li>}</ul>
      </Card>
      {askCard}
      {musicCard}
    </div>}
  </div></div>;
}
