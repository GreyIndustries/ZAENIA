import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./CodeStudio.css";

/**
 * Code Doctor, reworked (Grey's picks, 2026-10-30: A, C, B): Health first (score, counts, problems worst first,
 * problems over time, biggest files), then the Review queue (fixes and ZAE's ideas one at a time, with the change
 * shown before anything is saved). The Playground stays as the editor (B), and the old scanner, Suggestions, Files and
 * Source stay as later sub-tabs. Saving still needs the desktop app and keeps a backup; ZAE's protected files are refused.
 */
type Finding = { file: string; line: number; level: "error" | "warn" | "info"; message: string };
export type Scan = { project: string; isZae: boolean; totals: { files: number; lines: number }; counts: Record<string, number>; findings: Finding[]; biggest?: { file: string; lines: number }[]; files?: { file: string; lines: number }[] };
type Fix = { changed: boolean; message?: string; diff?: string; text?: string; oldHash?: string; protected?: boolean };
type Suggestion = { id: string; for: string; title: string; why: string; how?: string; effort?: string; status: "new" | "approved" | "dismissed"; created: string };
type History = { at: string; error: number; warn: number; info: number }[];

const HISTORY_KEY = (project: string) => `zaenia.codeHealth.${project.toLowerCase()}`;
const remember = <T,>(key: string, fallback: T): T => { try { return JSON.parse(localStorage.getItem(key) ?? "") as T; } catch { return fallback; } };
const ago = (iso: string) => { const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000); return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} days ago`; };
/** 100 with nothing to fix; errors cost the most. */
export const healthScore = (counts: { error?: number; warn?: number; info?: number }) => Math.max(0, Math.min(100, Math.round(100 - (counts.error ?? 0) * 8 - (counts.warn ?? 0) * 1.5 - Math.min(12, (counts.info ?? 0) * 0.08))));
const isSecret = (f: Finding) => /looks like a secret/i.test(f.message);

export function useCodeScan() {
  const [project, setProject] = useState(() => { try { return localStorage.getItem("zaenia.codeDoctor") ?? "C:\\Projects\\ZAENIA"; } catch { return "C:\\Projects\\ZAENIA"; } });
  const [scan, setScan] = useState<Scan | null>(null);
  const [at, setAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      try { localStorage.setItem("zaenia.codeDoctor", project); } catch { /* optional */ }
      const next = await api<Scan>("POST", "/api/code/scan", { project }, { timeoutMs: 180_000 });
      const when = new Date().toISOString();
      setScan(next); setAt(when);
      const history = [...remember<History>(HISTORY_KEY(next.project), []), { at: when, error: next.counts.error ?? 0, warn: next.counts.warn ?? 0, info: next.counts.info ?? 0 }].slice(-10);
      try { localStorage.setItem(HISTORY_KEY(next.project), JSON.stringify(history)); } catch { /* optional */ }
    } catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  }, [project]);
  return { project, setProject, scan, at, busy, error, run };
}
type ScanState = ReturnType<typeof useCodeScan>;
import { CodeEditorView, CodeSideBySide } from "../studios/ThirdViews";
import { PlainEnglish } from "./PlainEnglish";

export function CodeHealth({ code, onReview }: { code: ScanState; onReview: (file: string) => void }) {
  const { scan } = code;
  const history = scan ? remember<History>(HISTORY_KEY(scan.project), []) : [];
  const peak = Math.max(1, ...history.map(h => h.error * 4 + h.warn + h.info / 10));
  const score = scan ? healthScore(scan.counts) : null;
  const ring = 2 * Math.PI * 32;
  const files = useMemo(() => {
    const byFile = new Map<string, Finding[]>();
    for (const f of scan?.findings ?? []) if (f.level !== "info") byFile.set(f.file, [...(byFile.get(f.file) ?? []), f]);
    return [...byFile.values()].map(list => list[0]).slice(0, 8);
  }, [scan]);
  if (!LIVE_API) return <p className="cs-muted">Code Doctor needs the ZÆNIA server: open it in the desktop app.</p>;
  return <div className="cs">
    <div className="cs-head">
      <div><span className="cs-kicker">Project health</span><h2 className="zx-title">{scan ? `${scan.project.split(/[\\/]/).pop()} · scanned ${code.at ? ago(code.at) : ""}` : "Scan a project to see its health"}</h2></div>
      <form className="cs-row" onSubmit={event => { event.preventDefault(); void code.run(); }}>
        <label className="cs-field">Project<input value={code.project} onChange={event => code.setProject(event.target.value)} aria-label="Project folder"/></label>
        <button type="submit" className="cs-primary" disabled={code.busy}>{code.busy ? "Scanning…" : "Scan now"}</button>
      </form>
    </div>
    {code.error && <p className="cs-error" role="alert">{code.error}</p>}
    <div className="cs-kpis">
      <div className="zx-card cs-score">
        <svg width="78" height="78" viewBox="0 0 78 78" role="img" aria-label={`Health score ${score ?? "not scanned"}`}>
          <circle cx="39" cy="39" r="32" className="cs-ring-bg"/><circle cx="39" cy="39" r="32" className="cs-ring" strokeDasharray={`${ring * (score ?? 0) / 100} ${ring}`} transform="rotate(-90 39 39)"/>
          <text x="39" y="45" textAnchor="middle">{score ?? "—"}</text></svg>
        <span><b>Health score</b><small>{history.length > 1 ? `${healthScore(history[history.length - 1]) - healthScore(history[history.length - 2]) >= 0 ? "+" : ""}${healthScore(history[history.length - 1]) - healthScore(history[history.length - 2])} since the last scan` : "Out of 100"}</small></span>
      </div>
      {[["Errors", scan?.counts.error, "cs-bad", "can break things"], ["Warnings", scan?.counts.warn, "cs-warn", "worth fixing"], ["Notes", scan?.counts.info, "cs-info", "TODOs and large files"],
        ["Secrets found", scan ? scan.findings.filter(isSecret).length : undefined, scan && scan.findings.some(isSecret) ? "cs-bad" : "cs-good", "in the code"],
        ["Size", scan ? `${scan.totals.files.toLocaleString()} files` : undefined, "", scan ? `${scan.totals.lines.toLocaleString()} lines` : ""]].map(([label, value, tone, note]) =>
        <div key={String(label)} className="zx-card cs-kpi"><small>{label}</small><b className={String(tone)}>{value ?? "—"}</b><span>{note}</span></div>)}
    </div>
    <div className="cs-split">
      <section className="zx-card">
        <div className="cs-row cs-row--between"><h3>Problems</h3><small className="cs-muted">worst first</small></div>
        {!scan && <p className="cs-muted">Nothing scanned yet.</p>}
        {scan && files.length === 0 && <p className="cs-muted">No errors or warnings. Nice.</p>}
        <ul className="cs-list">{files.map(f => <li key={`${f.file}:${f.line}`} className="zx-inset">
          <span className={`cs-sev cs-sev--${f.level}`}>{f.level === "error" ? "ERROR" : "WARN"}</span>
          <span className="cs-grow"><b>{f.message}</b><code>{f.file}{f.line ? `:${f.line}` : ""}</code></span>
          <button type="button" onClick={() => onReview(f.file)}>Review fix</button>
        </li>)}</ul>
      </section>
      <div className="cs-stack">
        <section className="zx-card">
          <h3>Problems over time</h3>
          <div className="cs-bars" aria-label="Problems in the last scans">{history.length ? history.map(h => <span key={h.at} title={`${new Date(h.at).toLocaleString()}: ${h.error} errors, ${h.warn} warnings, ${h.info} notes`}
            style={{ height: `${Math.max(4, (h.error * 4 + h.warn + h.info / 10) / peak * 100)}%` }}/>) : <small className="cs-muted">Each scan adds a bar.</small>}</div>
          <small className="cs-muted">Last {history.length || 0} scans</small>
        </section>
        <section className="zx-card">
          <h3>Biggest files</h3>
          <ul className="cs-files">{(scan?.biggest ?? []).map(f => <li key={f.file}><code>{f.file}</code><span>{f.lines.toLocaleString()}</span></li>)}</ul>
          {!scan?.biggest?.length && <small className="cs-muted">Shown after a scan.</small>}
        </section>
      </div>
    </div>
  </div>;
}

type QueueItem = { kind: "fix"; file: string; level: "error" | "warn"; findings: Finding[] } | { kind: "idea"; s: Suggestion };

export function ReviewQueue({ code, focusFile }: { code: ScanState; focusFile: string | null }) {
  const [ideas, setIdeas] = useState<Suggestion[]>([]);
  const [filter, setFilter] = useState<"all" | "fix" | "idea">("all");
  const [picked, setPicked] = useState<string | null>(null);
  const [fix, setFix] = useState<Fix | null>(null);
  const [explain, setExplain] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [skipped, setSkipped] = useState<string[]>([]);
  const loadIdeas = useCallback(() => { if (LIVE_API) api<{ suggestions: Suggestion[] }>("GET", "/api/suggestions").then(r => setIdeas(r.suggestions), () => undefined); }, []);
  useEffect(loadIdeas, [loadIdeas]);
  const items: QueueItem[] = useMemo(() => {
    const byFile = new Map<string, Finding[]>();
    for (const f of code.scan?.findings ?? []) if (f.level !== "info") byFile.set(f.file, [...(byFile.get(f.file) ?? []), f]);
    const fixes: QueueItem[] = [...byFile.entries()].map(([file, findings]) => ({ kind: "fix", file, findings, level: findings.some(f => f.level === "error") ? "error" : "warn" }));
    fixes.sort((a, b) => (a.kind === "fix" && a.level === "error" ? 0 : 1) - (b.kind === "fix" && b.level === "error" ? 0 : 1));
    return [...fixes, ...ideas.filter(s => s.status === "new").map(s => ({ kind: "idea", s }) as QueueItem)];
  }, [code.scan, ideas]);
  const key = (item: QueueItem) => item.kind === "fix" ? `fix:${item.file}` : `idea:${item.s.id}`;
  const shown = items.filter(item => !skipped.includes(key(item)) && (filter === "all" || item.kind === filter));
  useEffect(() => { if (focusFile) { setPicked(`fix:${focusFile}`); setFilter("all"); } }, [focusFile]);
  const current = shown.find(item => key(item) === picked) ?? shown[0] ?? null;
  useEffect(() => { setFix(null); setExplain(""); setNote(null); setError(null); }, [current && key(current)]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (label: string, work: () => Promise<void>) => {
    setBusy(label); setError(null); setNote(null);
    try { await work(); } catch (failure) { setError(errorText(failure)); } finally { setBusy(null); }
  };
  const lines = (f: QueueItem & { kind: "fix" }) => f.findings.map(x => `line ${x.line}: ${x.message}`);
  const skip = () => { if (current) setSkipped(list => [...list, key(current)]); };

  if (!LIVE_API) return <p className="cs-muted">The review queue needs the ZÆNIA server: open it in the desktop app.</p>;
  const fixes = items.filter(i => i.kind === "fix").length, ideaCount = items.length - fixes;
  return <div className="cs cs-queue">
    <aside className="zx-card cs-queue__list">
      <span className="cs-kicker">Waiting for you</span>
      <h2 className="zx-title">{fixes} fix{fixes === 1 ? "" : "es"} · {ideaCount} idea{ideaCount === 1 ? "" : "s"}</h2>
      <div className="cs-chips" role="group" aria-label="Show">{([["all", "All"], ["fix", "Fixes"], ["idea", "Ideas"]] as const).map(([id, label]) =>
        <button key={id} type="button" aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}</div>
      {!code.scan && <button type="button" className="cs-primary" disabled={code.busy} onClick={() => void code.run()}>{code.busy ? "Scanning…" : "Scan for fixes"}</button>}
      <ul className="cs-list">{shown.map(item => <li key={key(item)}>
        <button type="button" className="zx-inset cs-qitem" aria-pressed={current !== null && key(current) === key(item)} onClick={() => setPicked(key(item))}>
          {item.kind === "fix" ? <><small className={`cs-sev cs-sev--${item.level}`}>FIX · {item.level === "error" ? "ERROR" : "WARN"}</small><b>{item.findings[0].message}</b><code>{item.file}</code></>
            : <><small className="cs-sev cs-sev--idea">{item.s.for === "zae" ? "FEATURE" : item.s.for.toUpperCase()}</small><b>{item.s.title}</b><code>ZAE idea · {ago(item.s.created)}</code></>}
        </button></li>)}</ul>
      {shown.length === 0 && (code.scan || ideas.length > 0) && <p className="cs-muted">All caught up.</p>}
    </aside>
    <main className="cs-queue__main">
      {error && <p className="cs-error" role="alert">{error}</p>}
      {note && <p className="cs-note" role="status">{note}</p>}
      {!current && <p className="cs-muted">Nothing to review. Scan a project, or ask ZAE for ideas in Suggestions.</p>}
      {current?.kind === "fix" && <>
        <div className="cs-row cs-row--between">
          <div><span className={`cs-sev cs-sev--${current.level}`}>FIX · {current.level === "error" ? "ERROR" : "WARNING"}</span><h2 className="zx-title">{current.findings[0].message}</h2><code>{current.file} · {current.findings.length} finding{current.findings.length === 1 ? "" : "s"}</code></div>
          <div className="cs-row">
            <button type="button" onClick={skip}>Skip</button>
            <button type="button" disabled={Boolean(busy)} onClick={() => void act("explaining", async () => setExplain((await api<{ review: string }>("POST", "/api/code/explain", { project: code.project, file: current.file, findings: lines(current) }, { timeoutMs: 300_000 })).review))}>Explain</button>
            {!fix && <button type="button" className="cs-primary" disabled={Boolean(busy)} onClick={() => void act("writing a fix", async () => setFix(await api<Fix>("POST", "/api/code/fix", { project: code.project, file: current.file, findings: lines(current) }, { timeoutMs: 300_000 })))}>Write the fix</button>}
            {fix?.text && fix.changed && <button type="button" className="cs-primary" disabled={Boolean(busy)} onClick={() => void act("applying", async () => {
              const result = await api<{ backup: string }>("POST", "/api/code/apply", { project: code.project, file: current.file, text: fix.text, oldHash: fix.oldHash }, { desktop: true, timeoutMs: 60_000 });
              setNote(`Applied. The old version is kept at ${result.backup}.`); setFix(null); skip();
            })}>Approve and apply</button>}
          </div>
        </div>
        <ul className="cs-findings">{current.findings.slice(0, 8).map((f, i) => <li key={i}><code>line {f.line}</code> {f.message}</li>)}</ul>
        {busy && <p className="cs-muted" role="status">ZAE is {busy}…</p>}
        {explain && <div className="zx-inset cs-explain">{explain.split("\n").map((line, i) => <p key={i}>{line.replace(/\*\*/g, "")}</p>)}</div>}
        {fix && (fix.protected ? <p className="cs-error">This is one of ZAE's protected files, so it can't be changed from here.</p>
          : !fix.changed ? <p className="cs-muted">{fix.message ?? "ZAE didn't find a safe change to make."}</p>
          : <pre className="cs-diff" aria-label="Proposed change">{(fix.diff ?? "").split("\n").map((line, i) =>
            <span key={i} className={line.startsWith("+") && !line.startsWith("+++") ? "cs-add" : line.startsWith("-") && !line.startsWith("---") ? "cs-del" : line.startsWith("@@") ? "cs-hunk" : ""}>{line}{"\n"}</span>)}</pre>)}
        {fix?.changed && <p className="cs-muted">Nothing is saved until you approve. A backup is kept, and saving needs the desktop app.</p>}
      </>}
      {current?.kind === "idea" && <>
        <div className="cs-row cs-row--between">
          <div><span className="cs-sev cs-sev--idea">{current.s.for === "zae" ? "FEATURE" : current.s.for.toUpperCase()}{current.s.effort ? ` · ${current.s.effort}` : ""}</span><h2 className="zx-title">{current.s.title}</h2></div>
          <div className="cs-row">
            <button type="button" onClick={skip}>Skip</button>
            <button type="button" disabled={Boolean(busy)} onClick={() => void act("saving", async () => { await api("POST", `/api/suggestions/${current.s.id}`, { approve: false }); loadIdeas(); })}>Dismiss</button>
            <button type="button" className="cs-primary" disabled={Boolean(busy)} onClick={() => void act("saving", async () => { await api("POST", `/api/suggestions/${current.s.id}`, { approve: true }); setNote("Approved. It's on ZAE's list."); loadIdeas(); })}>Approve</button>
          </div>
        </div>
        <p className="cs-body">{current.s.why}</p>
        {current.s.how && <div className="zx-inset cs-explain"><p>{current.s.how}</p></div>}
      </>}
    </main>
  </div>;
}

/** The Code Doctor tab: Health and Review queue first (sharing one scan), then the existing tools. */
export function CodeDoctorStudio({ extra }: { extra: { id: string; label: string; render: () => React.ReactNode }[] }) {
  const code = useCodeScan();
  const [focusFile, setFocusFile] = useState<string | null>(null);
  const tabs = [{ id: "health", label: "Health" }, { id: "queue", label: "Review queue" }, { id: "side", label: "Side by side" }, { id: "editor", label: "Editor" }, { id: "plain", label: "Plain English" }, ...extra.map(({ id, label }) => ({ id, label }))];
  const [tab, setTab] = useState(() => { try { const saved = localStorage.getItem("zaenia.pageTab.codedoctor"); return tabs.some(t => t.id === saved) ? saved! : "health"; } catch { return "health"; } });
  const [opened, setOpened] = useState<string[]>([tab]);
  const choose = (next: string) => { setTab(next); setOpened(list => list.includes(next) ? list : [...list, next]); try { localStorage.setItem("zaenia.pageTab.codedoctor", next); } catch { /* optional */ } };
  useEffect(() => {
    const jump = (event: Event) => { const detail = (event as CustomEvent<{ page: string; tab: string }>).detail; if (detail?.page === "codedoctor") choose(detail.tab); };
    window.addEventListener("zae:page-tab", jump); return () => window.removeEventListener("zae:page-tab", jump);
  });
  return <div className="research-page">
    <nav className="research-page__tabs" role="tablist" aria-label="Code Doctor sections">
      {tabs.map(item => <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? "research-page__tab research-page__tab--on" : "research-page__tab"} onClick={() => choose(item.id)}>{item.label}</button>)}
    </nav>
    {opened.includes("health") && <div role="tabpanel" hidden={tab !== "health"}><CodeHealth code={code} onReview={file => { setFocusFile(file); choose("queue"); }}/></div>}
    {opened.includes("queue") && <div role="tabpanel" hidden={tab !== "queue"}><ReviewQueue code={code} focusFile={focusFile}/></div>}
    {opened.includes("side") && <div role="tabpanel" hidden={tab !== "side"}><CodeSideBySide code={code}/></div>}
    {opened.includes("editor") && <div role="tabpanel" hidden={tab !== "editor"}><CodeEditorView code={code}/></div>}
    {opened.includes("plain") && <div role="tabpanel" hidden={tab !== "plain"}><PlainEnglish code={code}/></div>}
    {extra.filter(item => opened.includes(item.id)).map(item => <div key={item.id} role="tabpanel" hidden={tab !== item.id}>{item.render()}</div>)}
  </div>;
}
