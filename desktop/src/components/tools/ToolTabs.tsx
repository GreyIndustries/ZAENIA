import { useCallback, useEffect, useState } from "react";
import { api, errorText, IN_TAURI, LIVE_API } from "../../core/bridge";
import { AnalysisResult } from "../research/researchShared";
import "../research/Research.css";
import "./ToolTabs.css";
import { DetailScreen, detailKey } from "../shell/PageNavigator";

const needServer = <p className="research__note">This needs the ZÆNIA server: open it in the desktop app.</p>;

// ---------------------------------------------------------------- Code Doctor
type Finding = { file: string; line: number; level: "error" | "warn" | "info"; message: string };
type Scan = { project: string; isZae: boolean; totals: { files: number; lines: number }; counts: Record<string, number>; findings: Finding[] };
type Fix = { changed: boolean; message?: string; diff?: string; text?: string; oldHash?: string; protected?: boolean };

export function CodeDoctorPanel() {
  const [project, setProject] = useState(() => { try { return localStorage.getItem("zaenia.codeDoctor") ?? "C:\\Projects\\ZAENIA"; } catch { return "C:\\Projects\\ZAENIA"; } });
  const [scan, setScan] = useState<Scan | null>(null);
  const [level, setLevel] = useState<"all" | "error" | "warn" | "info">("all");
  const [file, setFile] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [review, setReview] = useState("");
  const [fix, setFix] = useState<Fix | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const run = async (label: string, work: () => Promise<void>) => {
    setBusy(label); setError(null); setNote(null);
    try { await work(); } catch (failure) { setError(errorText(failure)); } finally { setBusy(null); }
  };
  const doScan = () => run("scanning", async () => {
    try { localStorage.setItem("zaenia.codeDoctor", project); } catch { /* optional */ }
    setScan(await api<Scan>("POST", "/api/code/scan", { project }, { timeoutMs: 120_000 })); setFile(null); setReview(""); setFix(null);
  });
  const fileFindings = (name: string) => (scan?.findings ?? []).filter(item => item.file === name).map(item => `line ${item.line}: ${item.message}`);
  const explain = () => file && run("reviewing", async () => { setFix(null); setReview((await api<{ review: string }>("POST", "/api/code/explain", { project, file, findings: fileFindings(file) }, { timeoutMs: 300_000 })).review); });
  const proposeFix = () => file && run("writing a fix", async () => { setFix(await api<Fix>("POST", "/api/code/fix", { project, file, findings: fileFindings(file) }, { timeoutMs: 300_000 })); });
  const apply = () => file && fix?.text && run("applying", async () => {
    const result = await api<{ backup: string }>("POST", "/api/code/apply", { project, file, text: fix.text, oldHash: fix.oldHash }, { desktop: true, timeoutMs: 60_000 });
    setNote(`Applied. The old version is kept at ${result.backup}.`); setFix(null);
  });
  if (!LIVE_API) return needServer;
  const shown = (scan?.findings ?? []).filter(item => level === "all" || item.level === level);
  const files = [...new Set(shown.map(item => item.file))];
  return <div className="research">
    <p className="research__note">Checks a code project without running it: syntax, common Python mistakes, config files that won't load, leftover TODOs and secrets in code. Pick a file to have ZAE explain its bugs or propose a fix; you see the exact change before anything is written, and a backup is kept. Her own security code can be reviewed but never changed here.</p>
    <form className="research__bar" onSubmit={event => { event.preventDefault(); void doScan(); }}>
      <input value={project} aria-label="Project folder" onChange={event => setProject(event.target.value)} placeholder="C:\\Projects\\MyProject"/>
      <button type="button" onClick={() => setProject("C:\\Projects\\ZAENIA")}>ZAE's code</button>
      <button type="submit" className="research__primary" disabled={!!busy}>{busy === "scanning" ? "Scanning…" : "Scan project"}</button>
    </form>
    {error && <p className="research__error" role="alert">{error}</p>}
    {note && <p className="research__meta">✓ {note}</p>}
    {scan && <>
      <p className="research__meta">{scan.totals.files} files · {scan.totals.lines.toLocaleString()} lines · {scan.counts.error} problems · {scan.counts.warn} warnings · {scan.counts.info} notes</p>
      <div className="research__actions">{(["all", "error", "warn", "info"] as const).map(item => <button type="button" key={item} aria-pressed={level === item}
        className={level === item ? "research__primary" : ""} onClick={() => setLevel(item)}>{item === "all" ? "All" : item === "error" ? "Problems" : item === "warn" ? "Warnings" : "Notes"}</button>)}</div>
      <div className="research__split">
        <div className="research__table-wrap"><table className="research__table"><tbody>{files.map(name => <tr key={name} className={file === name ? "research__row--on" : ""} onClick={() => { setFile(name); setReview(""); setFix(null); }}>
          <td><strong>{name}</strong>{shown.filter(item => item.file === name).slice(0, 6).map((item, index) =>
            <div key={index} className={`cd-finding cd-finding--${item.level}`}>{item.line ? `L${item.line}: ` : ""}{item.message}</div>)}</td></tr>)}</tbody></table>
          {!files.length && <p className="research__empty">Nothing found at this level. 🎉</p>}</div>
        <aside className="research__side">
          <DetailScreen id="scanner-file" name="Scanner" open={!!file} itemId={file ?? undefined} title={file?.split(/[\\/]/).pop() || "File"}
            onOpen={id => { const name = files.find(entry => detailKey(entry) === id); if (name) setFile(name); }} onClose={() => setFile(null)}/>
          {file ? <>
            <h3>{file}</h3>
            <div className="research__actions">
              <button type="button" className="research__primary" disabled={!!busy} onClick={() => void explain()}>{busy === "reviewing" ? "Reviewing…" : "Explain problems"}</button>
              <button type="button" disabled={!!busy} onClick={() => void proposeFix()}>{busy === "writing a fix" ? "Writing…" : "Propose a fix"}</button>
            </div>
            <AnalysisResult busy={busy === "reviewing" || busy === "writing a fix" ? busy : null} result={review} error={null}/>
            {fix && !fix.changed && <p className="research__meta">{fix.message}</p>}
            {fix?.changed && <>
              <pre className="cd-diff">{fix.diff?.split("\n").map((line, index) => <span key={index} className={line.startsWith("+") ? "cd-add" : line.startsWith("-") ? "cd-del" : ""}>{line}{"\n"}</span>)}</pre>
              {fix.protected ? <p className="research__meta">This is ZAE's security code: review only, so the fix can't be applied here.</p>
                : IN_TAURI ? <div className="research__actions"><button type="button" className="research__primary" disabled={!!busy} onClick={() => void apply()}>Apply this change (keeps a backup)</button><button type="button" onClick={() => setFix(null)}>Discard</button></div>
                : <p className="research__meta">Apply from the desktop app on your PC.</p>}
            </>}
          </> : <p className="research__empty">Pick a file on the left.</p>}
        </aside>
      </div>
    </>}
  </div>;
}

// ---------------------------------------------------------------- Suggestions
type Kind = "day" | "upgrade" | "feature" | "fix";
type Suggestion = { id: string; for: Kind | "zae"; title: string; why: string; how?: string; effort?: string; remind: string; status: "new" | "approved" | "dismissed" | "never"; outcome?: string; created: string };
const KIND_LABEL: Record<Kind, string> = { day: "Your day", upgrade: "Upgrade", feature: "New feature", fix: "Fix (from last night)" };
const kindOf = (item: Suggestion): Kind => item.for === "zae" ? "feature" : item.for;

export function SuggestionsPanel() {
  const [items, setItems] = useState<Suggestion[]>([]);
  const [plan, setPlan] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [show, setShow] = useState<"new" | "approved" | "dismissed">("new");
  const [kind, setKind] = useState<Kind | "all">("all");
  const load = useCallback(() => api<{ suggestions: Suggestion[]; plan?: string }>("GET", "/api/suggestions").then(reply => { setItems(reply.suggestions); setPlan(reply.plan ?? ""); }, failure => setError(errorText(failure))), []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  const think = async (focus: "all" | "day" | "system", label: string) => {
    setBusy(label); setError(null); setNote(null);
    try { const reply = await api<{ new: Suggestion[] }>("POST", "/api/suggestions/think", { focus }, { timeoutMs: 300_000 }); setShow("new"); setNote(reply.new.length ? `${reply.new.length} new idea${reply.new.length === 1 ? "" : "s"}.` : "Nothing new this time."); await load(); }
    catch (failure) { setError(errorText(failure)); } finally { setBusy(null); }
  };
  const decide = async (id: string, approve: boolean) => {
    try { await api("POST", `/api/suggestions/${id}`, { approve }); await load(); } catch (failure) { setError(errorText(failure)); }
  };
  // Upgrades, features and nightly fixes can go straight to a build request (Code Doctor > Build requests).
  const buildIt = async (item: Suggestion) => {
    setBusy("writing a build request"); setError(null); setNote(null);
    try {
      await api("POST", "/api/build", { request: `${item.title}. ${item.how || item.why}`.slice(0, 2000), idea: item.id }, { timeoutMs: 120_000 });
      setNote("Sent to Build requests. Check the brief there and tap Start.");
      try { localStorage.setItem("zaenia.pageTab.codedoctor", "build"); } catch { /* optional */ }
      window.dispatchEvent(new CustomEvent("zae:page-tab", { detail: { page: "codedoctor", tab: "build" } }));
      await load();
    } catch (failure) { setError(errorText(failure)); } finally { setBusy(null); }
  };
  const never = async (id: string) => {
    try { await api("POST", `/api/build/ideas/${id}/never`, {}); await load(); } catch (failure) { setError(errorText(failure)); }
  };
  const copyPlan = async () => {
    try { await navigator.clipboard.writeText(plan); setNote("Upgrade plan copied. Paste it to Claude or Codex to have it built."); } catch { setError("Couldn't copy the plan."); }
  };
  if (!LIVE_API) return needServer;
  const inView = items.filter(item => item.status === show || (show === "dismissed" && item.status === "never"));
  const shown = inView.filter(item => kind === "all" || kindOf(item) === kind);
  return <div className="research">
    <p className="research__note">ZAE's own ideas: for your day (from your calendar, tasks and reminders), upgrades to her system (from the versions of Python, her packages, Ollama and her models against the latest releases, and your PC's RAM, GPU and disk) and new features she could have. Nothing happens unless you approve it. Approving a day idea with a time sets the reminder; approved upgrades and features go on her upgrade plan.</p>
    <div className="research__actions">
      <button type="button" className="research__primary" disabled={!!busy} onClick={() => void think("all", "everything")}>{busy === "everything" ? "Thinking…" : "Think of suggestions"}</button>
      <button type="button" disabled={!!busy} onClick={() => void think("system", "system")}>{busy === "system" ? "Checking her system…" : "Upgrades & new features"}</button>
      <button type="button" disabled={!!busy} onClick={() => void think("day", "day")}>{busy === "day" ? "Thinking…" : "Just my day"}</button>
    </div>
    <div className="research__actions">
      {(["new", "approved", "dismissed"] as const).map(item => <button type="button" key={item} aria-pressed={show === item} className={show === item ? "research__primary" : ""} onClick={() => setShow(item)}>
        {item === "new" ? "New" : item === "approved" ? "Approved" : "Dismissed"} ({items.filter(entry => entry.status === item).length})</button>)}
      <span className="research__meta" style={{ margin: "0 4px" }}>Show</span>
      {(["all", "day", "upgrade", "feature", "fix"] as const).map(item => <button type="button" key={item} aria-pressed={kind === item} className={kind === item ? "research__primary" : ""} onClick={() => setKind(item)}>
        {item === "all" ? "All" : KIND_LABEL[item]} ({item === "all" ? inView.length : inView.filter(entry => kindOf(entry) === item).length})</button>)}
      {show === "approved" && plan && <button type="button" onClick={() => void copyPlan()}>Copy upgrade plan</button>}
    </div>
    {busy && <p className="research__working" role="status">{busy === "system" ? "ZAE is checking her versions, models and your PC, then thinking…" : "ZAE is thinking…"}</p>}
    {note && <p className="research__meta">✓ {note}</p>}
    {error && <p className="research__error" role="alert">{error}</p>}
    {!shown.length && <p className="research__empty">{show === "new" ? "No new suggestions. Ask her to think of some." : "Nothing here yet."}</p>}
    <div className="wb-cards">{shown.map(item => { const k = kindOf(item);
      return <div className="research__side" key={item.id}>
        <span className="sg-tags"><span className={`sg-tag sg-tag--${k}`}>{KIND_LABEL[k]}</span>{item.effort && <span className="sg-tag sg-tag--effort">{item.effort} effort</span>}</span>
        <h3>{item.title}</h3>
        <p>{item.why}</p>
        {item.how && <p className="research__meta"><strong>How:</strong> {item.how}</p>}
        {item.remind && <p className="research__meta">Reminder if approved: {item.remind.replace("|", " · ")}</p>}
        {item.outcome && <p className="research__meta">✓ {item.outcome}</p>}
        {item.status === "new" && <div className="research__actions">
          {k !== "day" && <button type="button" className="research__primary" disabled={!!busy} onClick={() => void buildIt(item)}>Build it</button>}
          <button type="button" className={k === "day" ? "research__primary" : ""} onClick={() => void decide(item.id, true)}>{k === "day" ? "Approve" : "Add to plan"}</button>
          <button type="button" onClick={() => void decide(item.id, false)}>Not now</button>
          {k === "fix" && <button type="button" onClick={() => void never(item.id)}>Never</button>}</div>}
      </div>; })}</div>
  </div>;
}

// ---------------------------------------------------------------- Arena
type Model = { name: string; size: number; parameters: string; quantization: string };
type Answer = { model: string; answer: string; seconds: number | null; tokensPerSecond?: number | null; loadSeconds?: number; error?: string };
type Round = { id: string; question: string; answers: Answer[]; winner: string | null };
type ArenaState = { models: Model[]; board: { model: string; rounds: number; wins: number; winRate: number; avgSeconds: number | null }[]; rounds: Round[]; brain: { model: string; override: string | null } };

export function ArenaPanel() {
  const [state, setState] = useState<ArenaState | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [round, setRound] = useState<Round | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<ArenaState>("GET", "/api/arena").then(next => { setState(next); setPicked(current => current.length ? current : next.models.slice(0, 2).map(m => m.name)); }, failure => setError(errorText(failure))), []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  const fight = async () => {
    setBusy(true); setError(null); setRound(null);
    try { setRound(await api<Round>("POST", "/api/arena/round", { question, models: picked }, { timeoutMs: 600_000 })); }
    catch (failure) { setError(errorText(failure)); } finally { setBusy(false); }
  };
  const vote = async (model: string) => {
    if (!round) return;
    try { const next = await api<ArenaState>("POST", "/api/arena/vote", { round: round.id, model }); setState(current => current ? { ...current, ...next } : current); setRound({ ...round, winner: model }); }
    catch (failure) { setError(errorText(failure)); }
  };
  const useBrain = async (model: string | null) => {
    try { await api("POST", "/api/arena/brain", { model }, { desktop: true }); await load(); } catch (failure) { setError(errorText(failure)); }
  };
  if (!LIVE_API) return needServer;
  return <div className="research">
    <p className="research__note">Ask two or three of your local models the same question, see their answers side by side, and vote for the best. The leaderboard shows which model suits you; you can make the winner the SE's main model (and switch back any time). Models run one at a time, so this takes a little while.</p>
    {error && <p className="research__error" role="alert">{error}</p>}
    {state && <>
      <p className="research__meta">The SE's main model now: <strong>{state.brain.model}</strong>{state.brain.override ? " (picked in the Arena)" : ""}{state.brain.override && <> · <button type="button" className="research__link" onClick={() => void useBrain(null)}>go back to the configured model</button></>}</p>
      <div className="research__actions">{state.models.map(model => <label key={model.name} className="research__meta ar-model">
        <input type="checkbox" checked={picked.includes(model.name)} disabled={!picked.includes(model.name) && picked.length >= 3}
          onChange={event => setPicked(current => event.target.checked ? [...current, model.name] : current.filter(name => name !== model.name))}/>
        {model.name} <small>{model.parameters} · {model.size} GB</small></label>)}</div>
      <form className="research__bar" onSubmit={event => { event.preventDefault(); if (question.trim() && picked.length >= 2) void fight(); }}>
        <input value={question} maxLength={1000} placeholder="Ask them something you care about…" aria-label="Question" onChange={event => setQuestion(event.target.value)}/>
        <button type="submit" className="research__primary" disabled={busy || picked.length < 2 || !question.trim()}>{busy ? "They're answering…" : "Start round"}</button>
      </form>
    </>}
    {round && <div className="ar-answers">{round.answers.map(answer => <div className={`research__side${round.winner === answer.model ? " ar-winner" : ""}`} key={answer.model}>
      <h3>{answer.model} <small>{answer.seconds != null ? `${answer.seconds}s` : ""}{answer.tokensPerSecond ? ` · ${answer.tokensPerSecond} tok/s` : ""}</small></h3>
      {answer.error ? <p className="research__error">Didn't answer ({answer.error}).</p> : <div className="research__result">{answer.answer.split("\n").map((line, index) => <p key={index}>{line}</p>)}</div>}
      <div className="research__actions">
        <button type="button" className={round.winner === answer.model ? "research__primary" : ""} disabled={!!answer.error} onClick={() => void vote(answer.model)}>{round.winner === answer.model ? "★ Best" : "This one's best"}</button>
        {IN_TAURI && <button type="button" disabled={!!answer.error || state?.brain.model === answer.model} onClick={() => void useBrain(answer.model)}>Use in the SE</button>}
      </div>
    </div>)}</div>}
    {state && state.board.length > 0 && <div className="research__side"><h3>Leaderboard</h3>
      <table className="research__table"><thead><tr><th>Model</th><th>Wins</th><th>Rounds</th><th>Win rate</th><th>Avg time</th></tr></thead>
        <tbody>{state.board.map(entry => <tr key={entry.model}><td>{entry.model}</td><td>{entry.wins}</td><td>{entry.rounds}</td><td>{Math.round(entry.winRate * 100)}%</td><td>{entry.avgSeconds ?? "—"}s</td></tr>)}</tbody></table></div>}
  </div>;
}

// ---------------------------------------------------------------- Source (inside Files)
export function SourceSearch() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ file: string; line: number; text: string }[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const search = async () => {
    try { setHits((await api<{ hits: { file: string; line: number; text: string }[] }>("GET", `/api/code/search?q=${encodeURIComponent(query)}`, undefined, { timeoutMs: 60_000 })).hits); setError(null); }
    catch (failure) { setError(errorText(failure)); }
  };
  if (!LIVE_API) return needServer;
  return <div className="research">
    <p className="research__note">Search ZAE's own code (the same folders the Files tab shows). Open a file in the Files tab to read or change it there.</p>
    <form className="research__bar" onSubmit={event => { event.preventDefault(); if (query.trim().length >= 2) void search(); }}>
      <input value={query} maxLength={120} placeholder="e.g. game_coach or def transcribe" aria-label="Search code" onChange={event => setQuery(event.target.value)}/>
      <button type="submit" className="research__primary" disabled={query.trim().length < 2}>Search</button>
    </form>
    {error && <p className="research__error" role="alert">{error}</p>}
    {hits && (hits.length ? <div className="research__table-wrap"><table className="research__table"><tbody>{hits.map((hit, index) =>
      <tr key={index}><td className="cd-path">{hit.file}:{hit.line}</td><td><code>{hit.text}</code></td></tr>)}</tbody></table></div>
      : <p className="research__empty">No matches.</p>)}
  </div>;
}
