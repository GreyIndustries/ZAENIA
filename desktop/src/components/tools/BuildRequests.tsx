import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API, restartServer } from "../../core/bridge";
import "./CodeStudio.css";
import { DetailScreen, detailKey } from "../shell/PageNavigator";
import { displayFiles, finalAnswer } from "../../core/buildText";

/**
 * Build requests (Grey's options 2 and 3, 2026-11-01): ZAE writes a brief, Claude Code or Aider makes the change in a
 * separate copy, her tests run there, and Grey approves at the PC. Approve and Undo need the desktop app; nothing
 * goes live otherwise. Her security code is locked: a change that touches it is thrown away.
 */
type Status = "draft" | "queued" | "working" | "ready" | "failed" | "approved" | "undone" | "rejected";
type Request = { id: string; request: string; title: string; brief: string; size: string; files?: string[]; tool: string | null; model?: string; attempt?: number;
  status: Status; step: string; createdAt: string; updatedAt: string; summary?: string; diff?: string; changed?: string[];
  checks?: { ok: boolean; text: string }; review?: { status: "reviewed" | "unavailable"; model?: string; text: string; at: string; advisory?: boolean };
  source?: string; needs?: { app: boolean; server: boolean } };
type View = { requests: Request[]; tools: { claude: boolean; aider: boolean }; running: boolean };

const LABEL: Record<Status, string> = { draft: "Check the brief", queued: "Waiting", working: "Working", ready: "Ready to review",
  failed: "Failed", approved: "Live", undone: "Undone", rejected: "Thrown away" };
const TONE: Record<Status, string> = { draft: "cs-warn", queued: "cs-info", working: "cs-info", ready: "cs-good", failed: "cs-bad",
  approved: "cs-good", undone: "cs-muted", rejected: "cs-muted" };
const TOOL: Record<string, string> = { claude: "Claude Code", aider: "Aider (local)" };

export function BuildRequests() {
  const [view, setView] = useState<View | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [ask, setAsk] = useState("");
  const [brief, setBrief] = useState("");
  const [tool, setTool] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showChecks, setShowChecks] = useState(false);
  const load = useCallback(() => api<View>("GET", "/api/build").then(setView, failure => setError(errorText(failure))), []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  useEffect(() => {  // while something runs, follow its progress
    if (!view?.running) return;
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [view?.running, load]);
  useEffect(() => {
    const changed = () => void load();
    window.addEventListener("zae:records-changed", changed); return () => window.removeEventListener("zae:records-changed", changed);
  }, [load]);
  const items = view?.requests ?? [];
  const current = items.find(item => item.id === picked) ?? null;  // list first (preview 05); a request opens as its own screen
  useEffect(() => { setBrief(current?.brief ?? ""); setTool(""); setShowChecks(false); setNote(null); }, [current?.id, current?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (label: string, work: () => Promise<unknown>, done?: string) => {
    setBusy(label); setError(null); setNote(null);
    try { await work(); if (done) setNote(done); await load(); } catch (failure) { setError(errorText(failure)); } finally { setBusy(null); }
  };
  const create = () => act("writing the brief", async () => {
    const made = await api<Request>("POST", "/api/build", { request: ask.trim() }, { timeoutMs: 120_000 });
    setAsk(""); setPicked(made.id);
  });
  const post = (path: string, body?: unknown, desktop = false) => api<Request>("POST", `/api/build/${current!.id}/${path}`, body ?? {}, { desktop, timeoutMs: 120_000 });
  // After Approve or Undo: restart the server if her code changed (from this app, outside the server), then rebuild the
  // app if its screens changed (the app closes and reopens by itself).
  const goLive = async (path: "approve" | "undo") => {
    const id = current!.id;
    const done = await post(path, {}, true);
    if (done.needs?.server) {
      setBusy("restarting her server");
      await restartServer();
      for (let i = 0; i < 40; i++) { try { await api("GET", "/api/build"); break; } catch { await new Promise(r => window.setTimeout(r, 1500)); } }
    }
    if (done.needs?.app) {
      await api("POST", `/api/build/${id}/rebuild`, {}, { desktop: true, timeoutMs: 60_000 });
      return "The app is rebuilding. It will close and reopen with the change in about three minutes.";
    }
    return path === "approve" ? "Approved and live." : "Undone.";
  };
  const live = (path: "approve" | "undo", label: string) => {
    setBusy(label); setError(null); setNote(null);
    void goLive(path).then(text => setNote(text), failure => setError(errorText(failure))).finally(() => { setBusy(null); void load(); });
  };

  if (!LIVE_API) return <p className="cs-muted">Build requests need the ZÆNIA server: open them in the desktop app.</p>;
  return <div className="cs">
    <div className="cs-head">
      <div><span className="cs-kicker">Build requests</span><h2 className="zx-title">Ask ZAE to change her own app</h2></div>
      <span className="cs-muted">Claude Code {view?.tools.claude ? "ready" : "not installed"} · Aider (local) {view?.tools.aider ? "ready" : "not installed"}</span>
    </div>
    <p className="cs-muted">She writes a brief, a coding tool makes the change in a separate copy, and her tests run there. A separate local model can add advisory findings; only you can approve the change here on the PC, and every approved change can be undone. Her security code is locked. You can also say "ZAE, build … on the Health tab".</p>
    <form className="cs-row" onSubmit={event => { event.preventDefault(); if (ask.trim().length >= 4) void create(); }}>
      <input className="cs-grow" value={ask} onChange={event => setAsk(event.target.value)} maxLength={2000} placeholder="e.g. make the core rings blue when I'm tired" aria-label="What to change"/>
      <button type="submit" className="cs-primary" disabled={!!busy || ask.trim().length < 4}>Write the brief</button>
    </form>
    {busy && <p className="cs-muted" role="status">ZAE is {busy}…</p>}
    {note && <p className="cs-note">✓ {note}</p>}
    {error && <p className="cs-error" role="alert">{error}</p>}
    {!items.length && <p className="cs-muted">No build requests yet.</p>}
    {items.length > 0 && <div className="cs-queue" style={{ gap: "var(--zx-gap,12px)" }}>
      <div className="cs-queue__list cs-stack" style={{ gap: 6 }}>
        {items.map(item => <button key={item.id} type="button" className="zx-inset cs-qitem" aria-pressed={current?.id === item.id} onClick={() => setPicked(item.id)}>
          <span className={`cs-sev ${TONE[item.status]}`}>{LABEL[item.status].toUpperCase()}{item.source === "idea" ? " · FROM AN IDEA" : ""}</span>
          <b>{item.title}</b>
          <small className="cs-muted">{new Date(item.createdAt).toLocaleString()}{item.tool ? ` · ${TOOL[item.tool]}${item.model ? ` on ${item.model}` : ""}` : ""}</small>
        </button>)}
      </div>
      <DetailScreen id="build-request" name="Build requests" open={!!current} itemId={current?.id} quiet={picked === null} title={current?.title || "Request"}
        onOpen={id => { const item = items.find(entry => detailKey(entry.id) === id); if (item) setPicked(item.id); }} onClose={() => setPicked(null)}/>
      {current && <div className="cs-queue__main br-layout">
        <div className="br-main">
        {(current.status === "draft" || current.status === "failed") ? <>
          <label className="cs-stack" style={{ gap: 4 }}><span className="cs-kicker">Brief for the coding tool (edit it if needed)</span>
            <textarea value={brief} onChange={event => setBrief(event.target.value)} rows={6} maxLength={3000} style={{ width: "100%" }}/></label>
          {current.files?.length ? <p className="cs-muted">Files that may be involved: {current.files.join(", ")}</p> : null}
          <div className="cs-row">
            <label className="cs-field">Tool<select value={tool} onChange={event => setTool(event.target.value)}>
              <option value="">Local Aider — default for every task size</option>
              <option value="claude" disabled={!view?.tools.claude}>Claude Code — explicit opt-in; uses your Claude allowance</option>
              <option value="aider" disabled={!view?.tools.aider}>Aider (local, free)</option>
            </select></label>
            <button type="button" className="cs-primary" disabled={!!busy} onClick={() => void act("starting", () => post("start", { brief, tool: tool || null }, true), "Started. She'll tell you when it's ready.")}>
              {current.status === "failed" ? "Try again" : "Start"}</button>
            <button type="button" disabled={!!busy} onClick={() => void act("throwing it away", () => post("reject"))}>Throw away</button>
          </div>
        </> : <p className="cs-body">{current.brief}</p>}
        {finalAnswer(current.summary) && <div className="zx-inset cs-explain"><p><strong>What changed:</strong> {finalAnswer(current.summary)}</p></div>}
        {current.review && <section className="zx-inset cs-explain" aria-label="Independent second-pass review">
          <strong>Second-pass local review · {current.review.status === "reviewed" ? current.review.model : "unavailable"}</strong>
          <p className="cs-muted">Advisory only. It cannot approve, reject, or change this request. You remain the reviewer.</p>
          <pre className="cs-diff br-text">{finalAnswer(current.review.text)}</pre>
        </section>}
        {current.diff && ["ready", "failed", "approved"].includes(current.status) && <pre className="cs-diff" aria-label="The change">{current.diff.split("\n").map((line, i) =>
          <span key={i} className={line.startsWith("+") && !line.startsWith("+++") ? "cs-add" : line.startsWith("-") && !line.startsWith("---") ? "cs-del" : line.startsWith("@@") ? "cs-hunk" : ""}>{line}{"\n"}</span>)}</pre>}
        {current.status === "ready" && <div className="cs-row">
          <button type="button" className="cs-primary" disabled={!!busy} onClick={() => live("approve", "adding it to the live app")}>Approve at this PC</button>
          <button type="button" disabled={!!busy} onClick={() => void act("throwing it away", () => post("reject"))}>Reject</button>
        </div>}
        {current.status === "approved" && <div className="cs-row">
          <button type="button" disabled={!!busy} onClick={() => { if (window.confirm("Undo this change? It's reverted and the app rebuilds.")) live("undo", "undoing it"); }}>Undo this change</button>
        </div>}
        </div>
        <aside className="br-meta" aria-label="Request details">
        <div><span className={`cs-sev ${TONE[current.status]}`}>{LABEL[current.status].toUpperCase()}</span></div>
        <p className="cs-muted">You asked: “{current.request}”</p>
        <p className={current.status === "failed" ? "cs-error" : "cs-muted"} role="status">{["queued", "working"].includes(current.status) ? "⏳ " : ""}{current.step}</p>
        <p className="cs-muted">{current.tool ? TOOL[current.tool] : "Tool not chosen yet"} · created {new Date(current.createdAt).toLocaleString()}</p>
        {displayFiles(current.changed).length ? <div className="br-files"><span className="cs-kicker">Files</span><ul>{displayFiles(current.changed).map(file => <li key={file}><code>{file}</code></li>)}</ul></div> : null}
        {current.checks && <div>
          <button type="button" onClick={() => setShowChecks(open => !open)}>{current.checks.ok ? "✓ Tests passed" : "✗ Tests failed"} · {showChecks ? "hide" : "show"} details</button>
          {showChecks && <pre className="cs-diff" aria-label="Test results"><span>{current.checks.text}</span></pre>}
        </div>}
        </aside>
      </div>}
    </div>}
  </div>;
}
