import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useOverviewData } from "./OverviewFrame";
import "./AssistantFront.css";

/**
 * Assistant, front page (Grey's pick, 2026-10-30: "like 4 · Editorial · Dashboard"): ZAE's day as a morning paper.
 * The lead is what's next, the columns are fitness, news and the studio, "by the numbers" holds the counts, and the
 * briefs are her follow-ups. Everything comes from the same live data as the Overview; nothing is made up.
 */
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const clock = (time: string) => { const [h, m] = time.split(":").map(Number); return Number.isFinite(h) ? new Date(2000, 0, 1, h, m || 0).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : time; };
const fmt = (n: number | null | undefined) => n === null || n === undefined ? "—" : Math.round(n).toLocaleString();

export function AssistantFront({ onAsk, onOpen, notice, unread }: { onAsk: (text: string) => void; onOpen: (section: string) => void;
  notice: { title: string; message: string } | null; unread: number }) {
  const data = useOverviewData();
  const [now, setNow] = useState(() => new Date());
  const [question, setQuestion] = useState("");
  useEffect(() => { const timer = window.setInterval(() => setNow(new Date()), 60_000); return () => window.clearInterval(timer); }, []);
  const today = iso(now);
  const nowTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const next = data.events?.filter(e => e.date > today || (e.date === today && (e.allDay || e.time >= nowTime)))
    .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`))[0] ?? null;
  const open = data.tasks?.filter(t => t.status !== "Completed") ?? null;
  const due = open?.filter(t => t.deadline?.slice(0, 10) === today) ?? [];
  const overdue = open?.filter(t => t.deadline && t.deadline.slice(0, 10) < today) ?? [];
  const eat = data.day?.targets.ready ? data.day.targets.eat ?? null : null;
  const eaten = data.day?.eaten?.calories ?? null;
  const protein = data.day?.eaten?.protein ?? null;
  const left = eat !== null && eaten !== null ? Math.max(0, eat - eaten) : null;
  const weights = data.training?.weights ?? [];
  const change = weights.length > 1 ? weights[weights.length - 1].weightLb - weights[Math.max(0, weights.length - 30)].weightLb : null;
  const songs = data.songs?.filter(s => !s.archived) ?? [];
  const story = data.news?.[0] ?? null;
  const lead = next ? `${next.title}${next.allDay ? (next.date === today ? " today" : " tomorrow") : ` at ${clock(next.time)}${next.date === today ? "" : " tomorrow"}`}` : "A clear calendar";
  const leadBody = [
    due.length || overdue.length ? `${due.length} task${due.length === 1 ? "" : "s"} due today${overdue.length ? ` and ${overdue.length} overdue` : ""}${(overdue[0] ?? due[0]) ? `, starting with "${(overdue[0] ?? due[0]).title}"` : ""}.` : "No tasks are due today.",
    left !== null ? `You have ${fmt(left)} calories${protein !== null && data.day?.targets.protein ? ` and ${fmt(Math.max(0, data.day.targets.protein - protein))} g of protein` : ""} to go.` : "",
    data.day?.workout.label ? `Training: ${data.day.workout.label}.` : "",
  ].filter(Boolean).join(" ");
  const ask = (event: FormEvent) => { event.preventDefault(); if (question.trim()) { onAsk(question.trim()); setQuestion(""); } };

  return <div className="af">
    <header className="af-mast">
      <span>{now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}{data.weather?.temperature != null ? ` · ${Math.round(data.weather.temperature)}° ${data.weather.condition.toLowerCase()}` : ""}</span>
      <b className="af-title">The ZAE Daily</b>
      <span>Edition {now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}{data.security ? ` · security ${data.security.score}` : ""}</span>
    </header>
    <div className="af-cols">
      <article className="af-lead">
        <span className="af-kicker">Lead · next up</span>
        <h1>{lead}</h1>
        <p>{leadBody}</p>
        <div className="af-chips">{["Plan tomorrow", "Log food", "What did I miss?"].map(text => <button key={text} type="button" onClick={() => onAsk(text)}>{text}</button>)}</div>
      </article>
      <div className="af-rule" aria-hidden="true"/>
      <div className="af-stories">
        <article><span className="af-kicker af-kicker--green">Fitness &amp; health</span>
          <button type="button" className="af-head" onClick={() => onOpen("fitness")}>{change === null ? "Log weigh-ins to see your trend" : `${change <= 0 ? "Down" : "Up"} ${Math.abs(change).toFixed(1)} lb this month`}</button>
          <p>{weights.length ? `${weights[weights.length - 1].weightLb.toFixed(1)} lb at the last weigh-in.` : ""} {left !== null ? `${fmt(left)} kcal left today.` : ""}</p></article>
        <article><span className="af-kicker af-kicker--purple">Tech news</span>
          <button type="button" className="af-head" onClick={() => onOpen("news")}>{story ? story.title : "No new stories yet"}</button>
          <p>{data.news ? `${data.news.length} stories from the newsrooms you follow.` : ""}</p></article>
        <article><span className="af-kicker af-kicker--gold">Studio</span>
          <button type="button" className="af-head" onClick={() => onOpen("music")}>{songs[0] ? `${songs[0].title} · ${songs[0].stage}` : "No songs in progress"}</button>
          <p>{songs.length ? `${songs.length} song${songs.length === 1 ? "" : "s"} in progress.` : ""}</p></article>
      </div>
      <div className="af-rule" aria-hidden="true"/>
      <aside className="af-side">
        <span className="af-kicker af-kicker--muted">By the numbers</span>
        {[["Calories left", fmt(left)], ["Protein", protein === null ? "—" : `${fmt(protein)} g`], ["Open tasks", open === null ? "—" : String(open.length)],
          ["Security score", data.security ? String(data.security.score) : "—"], ["Notes", data.notes ? String(data.notes.total) : "—"]].map(([label, value]) =>
          <div key={label} className="af-number"><span>{label}</span><b>{value}</b></div>)}
        <span className="af-kicker af-kicker--muted">Briefs{unread ? ` · ${unread} new` : ""}</span>
        {notice ? <p className="af-brief"><b>{notice.title}.</b> {notice.message}</p> : <p className="af-brief">Nothing waiting on you from ZAE.</p>}
        {data.bar?.backup && <p className="af-brief">Backup {data.bar.backup}.</p>}
      </aside>
    </div>
    <form className="af-ask" onSubmit={ask}>
      <label htmlFor="af-question">Ask the editor:</label>
      <input id="af-question" value={question} maxLength={2000} placeholder="What should I know before tomorrow?" onChange={event => setQuestion(event.target.value)}/>
      <button type="submit" disabled={!question.trim()}>Ask ZAE</button>
    </form>
  </div>;
}
