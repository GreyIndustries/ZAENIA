import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useOverviewData } from "./OverviewFrame";
import "./CalmView.css";

/**
 * Calm view (Grey's pick A, "Split", 2026-10-30): the core and background dimmed, a clock and three rings on the left
 * (how much of the day, the calories and today's tasks are done), and most of the screen cycling one important thing at
 * a time on the right, with the next four queued below. It covers every screen; waking always returns to the dashboard.
 * It wakes on Grey's wake-up calls (his voice only); holding "Wake" for two seconds is the fallback when the mic is off.
 */
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const clock = (time: string) => { const [h, m] = time.split(":").map(Number); return Number.isFinite(h) ? new Date(2000, 0, 1, h, m || 0).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : time; };
const fmt = (n: number | null | undefined) => n === null || n === undefined ? "—" : Math.round(n).toLocaleString();
type Slide = { kicker: string; head: string; detail: string; facts: [string, string][]; tone: string };

export function CalmView({ listening, note, onHoldWake }: { listening: boolean; note: string | null; onHoldWake: () => void }) {
  const data = useOverviewData();
  const [now, setNow] = useState(() => new Date());
  const [spot, setSpot] = useState(0);
  const hold = useRef<number | null>(null);
  const [holding, setHolding] = useState(false);
  useEffect(() => { const timer = window.setInterval(() => setNow(new Date()), 15_000); return () => window.clearInterval(timer); }, []);
  useEffect(() => { const timer = window.setInterval(() => setSpot(i => i + 1), 9000); return () => window.clearInterval(timer); }, []);

  const today = iso(now);
  const nowTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const next = data.events?.filter(e => e.date > today || (e.date === today && (e.allDay || e.time >= nowTime)))
    .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`))[0] ?? null;
  const tasks = data.tasks ?? [];
  const open = tasks.filter(t => t.status !== "Completed");
  const due = open.filter(t => t.deadline?.slice(0, 10) === today);
  const overdue = open.filter(t => t.deadline && t.deadline.slice(0, 10) < today);
  const doneToday = tasks.filter(t => t.status === "Completed" && t.updatedAt?.slice(0, 10) === today).length;
  const eat = data.day?.targets.ready ? data.day.targets.eat ?? null : null;
  const eaten = data.day?.eaten?.calories ?? null;
  const protein = data.day?.eaten?.protein ?? null;
  const left = eat !== null && eaten !== null ? Math.max(0, eat - eaten) : null;
  const songs = data.songs?.filter(s => !s.archived) ?? [];

  // The three rings: the waking day (6 AM to midnight), calories eaten of target, today's tasks done.
  const dayShare = Math.min(1, Math.max(0, (now.getHours() + now.getMinutes() / 60 - 6) / 18));
  const kcalShare = eat && eaten !== null ? Math.min(1, eaten / eat) : 0;
  const taskShare = doneToday + due.length ? doneToday / (doneToday + due.length) : 0;

  const slides: Slide[] = [
    { kicker: "Next up", tone: "#e0a353", head: next ? next.title : "A clear calendar.",
      detail: next ? `${next.allDay ? "All day" : clock(next.time)} ${next.date === today ? "today" : "tomorrow"}.` : "Nothing else is scheduled.",
      facts: [["When", next ? (next.allDay ? "All day" : clock(next.time)) : "—"], ["Day", next ? (next.date === today ? "Today" : "Tomorrow") : "—"], ["After that", `${due.length} due today`]] },
    { kicker: "Tasks", tone: "#ffb4a2", head: overdue.length ? `${overdue.length} overdue, ${due.length} due today.` : due.length ? `${due.length} due today.` : "Nothing due today.",
      detail: [...overdue, ...due].slice(0, 2).map(t => t.title).join(" · ") || `${open.length} open in total.`,
      facts: [["Open", String(open.length)], ["Done today", String(doneToday)], ["Overdue", String(overdue.length)]] },
    ...(left === null ? [] : [{ kicker: "Fitness & health", tone: "#4fd1c5", head: `${fmt(left)} kcal left.`,
      detail: `${fmt(eaten)} of ${fmt(eat)} eaten${data.day?.workout.label ? ` · ${data.day.workout.label}` : ""}.`,
      facts: [["Protein", protein === null ? "—" : `${fmt(protein)}${data.day?.targets.protein ? ` / ${fmt(data.day.targets.protein)}` : ""} g`], ["Eaten", `${fmt(eaten)} kcal`], ["Target", `${fmt(eat)} kcal`]] as [string, string][] }]),
    ...(data.news ?? []).slice(0, 3).map((story, i) => ({ kicker: "News you follow", tone: "#c08cff", head: story.title, detail: "Tech news from the newsrooms you follow.",
      facts: [["Story", `${i + 1} of ${Math.min(3, data.news!.length)}`], ["New today", String(data.news!.length)], ["Say", "“Tell me more”"]] as [string, string][] })),
    ...(songs.length ? [{ kicker: "Studio", tone: "#e0c08a", head: `${songs[0].title}: ${songs[0].stage}.`, detail: `${songs.length} song${songs.length === 1 ? "" : "s"} in progress.`,
      facts: [["Songs", String(songs.length)], ["Stage", songs[0].stage || "—"], ["Release", songs[0].releaseDate || "Not set"]] as [string, string][] }] : []),
    { kicker: "System", tone: "#8fc8ff", head: data.security ? `Security ${data.security.score}, ${data.security.level.toLowerCase()}.` : "Systems standing by.",
      detail: data.bar?.backup ? `Backup ${data.bar.backup}.` : "Background work continues while calm.",
      facts: [["CPU", data.bar ? `${Math.round(data.bar.cpu)}%` : "—"], ["Memory", data.bar ? `${data.bar.ramUsedGb.toFixed(1)} GB` : "—"], ["Disk free", data.bar ? `${fmt(data.bar.diskFreeGb)} GB` : "—"]] },
  ];
  const index = spot % slides.length;
  const slide = slides[index];
  const queue = [1, 2, 3, 4].map(k => slides[(index + k) % slides.length]).filter((_, k) => k < slides.length - 1);
  const ring = (r: number, share: number) => ({ strokeDasharray: `${2 * Math.PI * r * share} ${2 * Math.PI * r}` });

  const startHold = () => { setHolding(true); hold.current = window.setTimeout(() => { setHolding(false); onHoldWake(); }, 2000); };
  const stopHold = () => { setHolding(false); if (hold.current) window.clearTimeout(hold.current); hold.current = null; };

  return <div className="calm" role="dialog" aria-modal="true" aria-label="Calm view">
    <aside className="calm__side">
      <div className="calm__core">
        <svg viewBox="0 0 340 340" aria-hidden="true">
          <circle cx="170" cy="170" r="160" className="calm__track" strokeWidth="10"/><circle cx="170" cy="170" r="160" className="calm__ring calm__ring--day" strokeWidth="10" style={ring(160, dayShare)} transform="rotate(-90 170 170)"/>
          <circle cx="170" cy="170" r="140" className="calm__track" strokeWidth="6"/><circle cx="170" cy="170" r="140" className="calm__ring calm__ring--kcal" strokeWidth="6" style={ring(140, kcalShare)} transform="rotate(-90 170 170)"/>
          <circle cx="170" cy="170" r="124" className="calm__track" strokeWidth="3"/><circle cx="170" cy="170" r="124" className="calm__ring calm__ring--tasks" strokeWidth="3" style={ring(124, taskShare)} transform="rotate(-90 170 170)"/>
        </svg>
        <span className="calm__sphere" aria-hidden="true"/>
      </div>
      <div className="calm__legend"><span><i className="calm__dot--day"/>Day {Math.round(dayShare * 100)}%</span><span><i className="calm__dot--kcal"/>Kcal {Math.round(kcalShare * 100)}%</span><span><i className="calm__dot--tasks"/>Tasks {doneToday}/{doneToday + due.length}</span></div>
      <div className="calm__clock"><b>{now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).replace(/\s?[AP]M$/i, "")}</b>
        <span>{now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}{data.weather?.temperature != null ? ` · ${Math.round(data.weather.temperature)}° ${data.weather.condition}` : ""}</span></div>
      <div className="calm__wake">
        <span>{note ?? (listening ? "Say a wake-up call to come back" : "The mic is off. Hold Wake to come back")}</span>
        <button type="button" className={holding ? "calm__hold calm__hold--on" : "calm__hold"} onPointerDown={startHold} onPointerUp={stopHold} onPointerLeave={stopHold}
          onKeyDown={event => { if ((event.key === "Enter" || event.key === " ") && !holding) startHold(); }} onKeyUp={stopHold} aria-label="Hold for two seconds to wake">Wake</button>
      </div>
    </aside>
    <main className="calm__main" style={{ "--calm-tone": slide.tone } as CSSProperties}>
      <div className="calm__top"><span><i/>{slide.kicker}</span><span>{index + 1} / {slides.length}</span></div>
      <div key={index} className="calm__slide">
        <h1>{slide.head}</h1>
        <p>{slide.detail}</p>
        <div className="calm__facts">{slide.facts.map(([label, value]) => <div key={label}><small>{label}</small><b>{value}</b></div>)}</div>
      </div>
      <div className="calm__bottom">
        <div className="calm__segments">{slides.map((_, i) => <span key={i} style={{ background: i === index ? slide.tone : undefined }}/>)}</div>
        <div className="calm__queue">{queue.map((q, k) => <div key={k} style={{ opacity: 1 - k * 0.2 }}><small>{k === 0 ? `Up next · ${q.kicker}` : q.kicker}</small><span>{q.head}</span></div>)}</div>
      </div>
    </main>
  </div>;
}
