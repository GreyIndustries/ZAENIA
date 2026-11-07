import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import { AddToNotebook, NeedsServer } from "./researchShared";
import "./Research.css";

type Source = { n: number; title: string; url: string };
type Job = { id: string; question: string; status: "running" | "done" | "failed"; step: string; queries: string[]; sources: Source[]; answer: string; started: string; finished: string | null; error: string | null };
type Finding = { at: string; summary: string; sources: Source[] };
type Topic = { id: string; topic: string; added: string; lastChecked: string | null; findings: Finding[] };
type State = { jobs: Job[]; watch: Topic[] };

const when = (iso: string | null) => iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "not yet";

/** Her answer with [1]-style citations turned into links to the sources. */
function Cited({ text, sources }: { text: string; sources: Source[] }) {
  return <div className="research__result research__result--tall" aria-live="polite">{text.split("\n").map((line, index) =>
    <p key={index}>{line.replace(/\*\*/g, "").replace(/^#+\s*/, "").split(/(\[\d+\])/).map((part, i) => {
      const n = /^\[(\d+)\]$/.exec(part)?.[1];
      const source = n ? sources.find(s => s.n === Number(n)) : undefined;
      return source ? <button type="button" key={i} className="research__link wa-cite" title={source.title} onClick={() => openLink(source.url)}>{part}</button> : part;
    })}</p>)}</div>;
}

function Sources({ sources }: { sources: Source[] }) {
  return <ol className="wa-sources">{sources.map(source => <li key={source.n}>
    <button type="button" className="research__link" onClick={() => openLink(source.url)}>{source.title || source.url}</button>
    <small>{(() => { try { return new URL(source.url).hostname.replace(/^www\./, ""); } catch { return ""; } })()}</small></li>)}</ol>;
}

/** Web agent: ask anything and she researches the web; plus topics she watches every day. */
export function WebAgentPanel() {
  const [state, setState] = useState<State | null>(null);
  const [question, setQuestion] = useState("");
  const [topic, setTopic] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const load = useCallback(() => api<State>("GET", "/api/research/agent").then(next => { setState(next); return next; }, failure => { setError(errorText(failure)); return null; }), []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  const running = state?.jobs.some(job => job.status === "running") ?? false;
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(id);
  }, [running, load]);

  const ask = async () => {
    if (question.trim().length < 3) return;
    setError(null); setNote(null);
    try { const job = await api<Job>("POST", "/api/research/agent", { question: question.trim() }); setOpen(job.id); setQuestion(""); await load(); }
    catch (failure) { setError(errorText(failure)); }
  };
  const addTopic = async () => {
    if (topic.trim().length < 2) return;
    setError(null);
    try { const added = await api<Topic>("POST", "/api/research/watch", { topic: topic.trim() }); setTopic(""); await load(); void check(added.id); }
    catch (failure) { setError(errorText(failure)); }
  };
  const check = async (id: string) => {
    setChecking(id); setError(null); setNote(null);
    try { const reply = await api<{ finding: Finding | null }>("POST", `/api/research/watch/${id}/check`, {}, { timeoutMs: 300_000 }); setNote(reply.finding ? "Found something new." : "Nothing new since the last check."); await load(); }
    catch (failure) { setError(errorText(failure)); } finally { setChecking(null); }
  };
  if (!LIVE_API) return <div className="research"><NeedsServer what="The web agent"/></div>;
  const jobs = state?.jobs ?? [];
  const current = jobs.find(job => job.id === open) ?? jobs[0];

  return <div className="research">
    <p className="research__note">Ask ZAE to research anything: she searches the web, reads up to six pages and answers with numbered sources, on her SE (Synergized Encephalon). You can also say “research …” or “watch the topic …”. Only your search words and ordinary page requests leave the PC; page text is read as data, never as instructions.</p>
    <form className="research__bar" onSubmit={event => { event.preventDefault(); void ask(); }}>
      <input value={question} maxLength={500} aria-label="What should ZAE research?" placeholder="What should I research? e.g. best GPU under $500 right now" onChange={event => setQuestion(event.target.value)}/>
      <button type="submit" className="research__primary" disabled={question.trim().length < 3}>Research</button>
    </form>
    {error && <p className="research__error" role="alert">{error}</p>}
    <div className="research__split">
      <div className="research__side">
        {!current && <p className="research__empty">Nothing researched yet. Ask her something above.</p>}
        {current && <>
          <h3>{current.question}</h3>
          <p className="research__meta">{current.status === "running" ? current.step : current.status === "failed" ? `Stopped: ${current.error}` : `Researched ${when(current.finished)}`}{current.queries.length ? ` · searched: ${current.queries.join(" · ")}` : ""}</p>
          {current.status === "running" && <p className="research__working" role="status">ZAE is researching… {current.step}</p>}
          {current.status === "done" && <>
            <Cited text={current.answer} sources={current.sources}/>
            <strong className="sc-label">Sources</strong>
            <Sources sources={current.sources}/>
            <div className="research__actions">
              <AddToNotebook source={{ title: current.question, kind: "web", text: `${current.answer}\n\nSources:\n${current.sources.map(s => `[${s.n}] ${s.title} ${s.url}`).join("\n")}`, meta: "Web agent" }}/>
              <button type="button" onClick={() => void navigator.clipboard?.writeText(current.answer)}>Copy answer</button>
            </div>
          </>}
        </>}
      </div>
      <aside className="research__side">
        <h3>Watch list <small>checked about once a day</small></h3>
        <form className="research__bar" onSubmit={event => { event.preventDefault(); void addTopic(); }}>
          <input value={topic} maxLength={120} aria-label="Topic to watch" placeholder="Add a topic, e.g. RTX 5070 Ti price" onChange={event => setTopic(event.target.value)}/>
          <button type="submit" disabled={topic.trim().length < 2}>Watch</button>
        </form>
        {note && <p className="research__meta">✓ {note}</p>}
        {!state?.watch.length && <p className="research__empty">No topics yet. New findings show here, in your briefing and in Suggestions.</p>}
        <ul className="research__list wa-topics">{state?.watch.map(item => { const latest = item.findings[item.findings.length - 1];
          return <li key={item.id} className="research__side wa-topic">
            <div className="research__bar"><strong style={{ flex: 1 }}>{item.topic}</strong>
              <button type="button" disabled={checking === item.id} onClick={() => void check(item.id)}>{checking === item.id ? "Checking…" : "Check now"}</button>
              <button type="button" className="research__danger" aria-label={`Stop watching ${item.topic}`} onClick={() => void api("DELETE", `/api/research/watch/${item.id}`).then(load)}>✕</button></div>
            <small className="research__meta">Last checked {when(item.lastChecked)}</small>
            {latest && <><Cited text={latest.summary} sources={latest.sources}/><small className="research__meta">{when(latest.at)}</small></>}
          </li>; })}</ul>
        {jobs.length > 1 && <>
          <strong className="sc-label">Earlier research</strong>
          <ul className="research__list">{jobs.map(job => <li key={job.id} className="research__bar">
            <button type="button" style={{ flex: 1 }} aria-pressed={job.id === current?.id} onClick={() => setOpen(job.id)}>
              <span>{job.question}</span><small>{job.status === "running" ? "researching…" : job.status === "failed" ? "stopped" : when(job.finished)}</small></button>
            <button type="button" className="research__danger" aria-label="Delete this research" onClick={() => void api("DELETE", `/api/research/agent/${job.id}`).then(load)}>✕</button></li>)}</ul>
        </>}
      </aside>
    </div>
  </div>;
}
