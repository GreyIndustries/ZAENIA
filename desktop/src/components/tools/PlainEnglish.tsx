import { useEffect, useMemo, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import type { useCodeScan } from "./CodeStudio";

/**
 * Plain English (Grey, 2026-11-08): read ZAE's code explained in everyday words, one file at a time or all of it, and
 * turn plain-English instructions into a Python draft. A draft is only text: running it stays in the Playground and
 * changing ZAE's code stays with Build requests, which test it in a copy and wait for Grey's approval.
 */
type ScanState = ReturnType<typeof useCodeScan>;
type OutlineItem = { line: number; kind: "file" | "class" | "function" | "method"; name: string; note: string };
type Explained = { file: string; lines: number; outline: OutlineItem[]; text: string; at: string | null; cached: boolean; parts: number };
type Written = { code: string; tests: string; english: string; check: string };

const CODE_FILE = /\.(py|tsx?|jsx?|rs|ps1)$/i;
const DONE_KEY = (project: string) => `zaenia.plainEnglish.done.${project.toLowerCase()}`;
const readDone = (project: string): string[] => { try { return JSON.parse(localStorage.getItem(DONE_KEY(project)) ?? "[]"); } catch { return []; } };
const paragraphs = (text: string) => text.split("\n").map((line, i) => line.trim()
  ? <p key={i} className={/^Part \d+ \(from line/.test(line) ? "pe-part" : undefined}>{line.replace(/\*\*/g, "").replace(/^#+\s*/, "")}</p> : null);

/** Loads Python into the Playground (mounted or not) and switches to it. */
export function openInPlayground(code: string, tests: string, title: string) {
  const draft = { language: "python", code, tests, stdin: "", title, id: "" };
  try { localStorage.setItem("zaenia.playground", JSON.stringify(draft)); } catch { /* optional */ }
  window.dispatchEvent(new CustomEvent("zae:playground-load", { detail: draft }));
  window.dispatchEvent(new CustomEvent("zae:page-tab", { detail: { page: "codedoctor", tab: "playground" } }));
}

function ReadCode({ code }: { code: ScanState }) {
  const [filter, setFilter] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const [shown, setShown] = useState<Explained | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string[]>(() => readDone(code.project));
  const [all, setAll] = useState<{ at: number; of: number; failed: number } | null>(null);
  const stop = useRef(false);
  const files = useMemo(() => (code.scan?.files ?? []).filter(f => CODE_FILE.test(f.file) && f.file.toLowerCase().includes(filter.toLowerCase())), [code.scan, filter]);
  useEffect(() => setDone(readDone(code.project)), [code.project]);
  const mark = (file: string) => setDone(list => {
    const next = list.includes(file) ? list : [...list, file];
    try { localStorage.setItem(DONE_KEY(code.project), JSON.stringify(next)); } catch { /* optional */ }
    return next;
  });
  const explain = async (file: string, refresh = false) =>
    api<Explained>("POST", "/api/code/explain", { project: code.project, file, mode: "plain", refresh }, { timeoutMs: 30 * 60_000 });
  const open = async (file: string, refresh = false) => {
    setPicked(file); setError(null); setShown(null); setBusy(refresh ? "explaining it again" : "reading it");
    try { const result = await explain(file, refresh); setShown(result); mark(file); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(null); }
  };
  const translateAll = async () => {
    stop.current = false; setError(null);
    const list = files.map(f => f.file);
    let failed = 0;
    for (let index = 0; index < list.length && !stop.current; index++) {
      setAll({ at: index + 1, of: list.length, failed });
      try { const result = await explain(list[index]); mark(list[index]); setPicked(list[index]); setShown(result); }
      catch { failed++; }
    }
    setAll(null);
    if (failed) setError(`${failed} file${failed === 1 ? "" : "s"} couldn't be explained (too large, unreadable, or her brain was busy). Try them one at a time.`);
  };

  if (!code.scan) return <div className="zx-card pe-empty">
    <p>ZAE needs to look through the project first.</p>
    <button type="button" className="cs-primary" disabled={code.busy} onClick={() => void code.run()}>{code.busy ? "Scanning…" : "Find the code files"}</button>
    {code.error && <p className="cs-error" role="alert">{code.error}</p>}
  </div>;
  const doneHere = files.filter(f => done.includes(f.file)).length;
  return <div className="cs-queue">
    <aside className="zx-card cs-queue__list">
      <span className="cs-kicker">{code.scan.project.split(/[\\/]/).pop()}</span>
      <h2 className="zx-title">{files.length.toLocaleString()} code files · {doneHere.toLocaleString()} explained</h2>
      <input className="pe-filter" value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter, e.g. brain/ or .tsx" aria-label="Filter files"/>
      {all ? <div className="pe-progress" role="status">
        <span>Translating {all.at} of {all.of}…</span><progress max={all.of} value={all.at - 1}/>
        <button type="button" onClick={() => { stop.current = true; }}>Stop after this file</button>
      </div> : <button type="button" disabled={Boolean(busy) || files.length === 0} onClick={() => void translateAll()}
        title="Goes through every file in the list. Files already explained and unchanged come straight from the saved copy.">
        Translate all {files.length.toLocaleString()} {filter ? "shown" : ""} files</button>}
      <ul className="cs-list">{files.slice(0, 400).map(f => <li key={f.file}>
        <button type="button" className="zx-inset cs-qitem" aria-pressed={picked === f.file} disabled={Boolean(all)} onClick={() => void open(f.file)}>
          <code>{f.file}</code><small className="cs-muted">{f.lines.toLocaleString()} lines{done.includes(f.file) ? " · explained" : ""}</small>
        </button></li>)}</ul>
      {files.length > 400 && <p className="cs-muted">Showing 400 of {files.length.toLocaleString()}. Filter to narrow it down.</p>}
    </aside>
    <main className="cs-queue__main">
      {error && <p className="cs-error" role="alert">{error}</p>}
      {!picked && <p className="cs-muted">Pick a file and ZAE explains what it does in everyday words. The first time takes a minute or two on her own brain; after that it's instant until the file changes.</p>}
      {picked && <div className="cs-row cs-row--between">
        <div><span className="cs-kicker">In plain English</span><h2 className="zx-title">{picked.split("/").pop()}</h2><code>{picked}{shown ? ` · ${shown.lines.toLocaleString()} lines` : ""}</code></div>
        {shown && !all && <button type="button" disabled={Boolean(busy)} onClick={() => void open(picked, true)}>Explain again</button>}
      </div>}
      {busy && <p className="cs-muted" role="status">ZAE is {busy}… long files are explained part by part.</p>}
      {shown && <>
        {shown.outline.length > 0 && <section className="zx-card">
          <h3>What's inside</h3>
          <ul className="pe-outline">{shown.outline.map(item => <li key={`${item.line}:${item.name}`}>
            <small className={`pe-kind pe-kind--${item.kind}`}>{item.kind}</small><b>{item.name}</b><span className="cs-muted">line {item.line}</span>
            {item.note && <span className="pe-note">{item.note}</span>}
          </li>)}</ul>
        </section>}
        <div className="zx-inset cs-explain pe-text">{paragraphs(shown.text)}</div>
        <small className="cs-muted">{shown.cached ? "Saved explanation" : "Just explained"}{shown.at ? ` · ${new Date(shown.at).toLocaleString()}` : ""}{shown.parts > 1 ? ` · ${shown.parts} parts` : ""}. Explanations come from her local model, so check anything important against the code.</small>
      </>}
    </main>
  </div>;
}

function WritePython({ code }: { code: ScanState }) {
  const [request, setRequest] = useState(() => { try { return localStorage.getItem("zaenia.plainEnglish.request") ?? ""; } catch { return ""; } });
  const [file, setFile] = useState("");
  const [written, setWritten] = useState<Written | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => { try { localStorage.setItem("zaenia.plainEnglish.request", request); } catch { /* optional */ } }, [request]);
  const pyFiles = useMemo(() => (code.scan?.files ?? []).filter(f => f.file.endsWith(".py")).map(f => f.file), [code.scan]);
  const act = async (label: string, work: () => Promise<void>) => {
    setBusy(label); setError(null); setNote(null);
    try { await work(); } catch (failure) { setError(errorText(failure)); } finally { setBusy(null); }
  };
  const write = () => act("writing the Python", async () => {
    setWritten(await api<Written>("POST", "/api/code/playground/ask", { language: "python", code: "", mode: "english", question: request, project: code.project, file }, { timeoutMs: 300_000 }));
  });
  const toBuild = () => act("sending it to Build requests", async () => {
    const ask = `${request.trim()}${file ? `\n(Work in ${file}.)` : ""}`.slice(0, 2000);
    await api("POST", "/api/build", { request: ask });
    setNote("Sent to Build requests. ZAE writes and tests it in a copy, and nothing changes until you approve it there.");
  });
  return <div className="pe-write">
    <section className="zx-card">
      <span className="cs-kicker">Plain English → Python</span>
      <h2 className="zx-title">Say what the code should do</h2>
      <textarea className="pe-request" value={request} onChange={event => setRequest(event.target.value)} rows={6} maxLength={4000}
        placeholder={"For example: Every morning, check the grow tent's water temperature. If it's above 26°C, add a reminder to top up cool water, and keep a log of the readings for a week."}
        aria-label="What the code should do"/>
      <div className="cs-row">
        <label className="cs-field">Fit with file (optional)<input list="pe-py-files" value={file} onChange={event => setFile(event.target.value)} placeholder="core/…/something.py"/></label>
        <datalist id="pe-py-files">{pyFiles.map(f => <option key={f} value={f}/>)}</datalist>
        <button type="button" className="cs-primary" disabled={Boolean(busy) || request.trim().length < 4} onClick={() => void write()}>{busy === "writing the Python" ? "Writing…" : "Write the Python"}</button>
      </div>
      <small className="cs-muted">ZAE only writes a draft here. Nothing runs and no file changes until you choose to test it or send it to Build requests.</small>
    </section>
    {error && <p className="cs-error" role="alert">{error}</p>}
    {note && <p className="cs-note" role="status">{note}</p>}
    {busy && <p className="cs-muted" role="status">ZAE is {busy}…</p>}
    {written && <>
      <section className="zx-card">
        <h3>What this code does, in plain English</h3>
        <div className="cs-explain pe-text">{paragraphs(written.english)}</div>
        {written.check && !/^nothing\.?$/i.test(written.check) && <><h3>ZAE assumed</h3><div className="cs-explain pe-text">{paragraphs(written.check)}</div></>}
        <small className="cs-muted">If this doesn't match what you meant, change your words above and write it again.</small>
      </section>
      <section className="zx-card">
        <div className="cs-row cs-row--between"><h3>Python</h3>
          <div className="cs-row">
            <button type="button" onClick={() => { void navigator.clipboard?.writeText(written.code).then(() => setNote("Copied."), () => undefined); }}>Copy</button>
            <button type="button" onClick={() => openInPlayground(written.code, written.tests, request.trim().split("\n")[0].slice(0, 60) || "Plain English draft")}>Test in Playground</button>
            <button type="button" className="cs-primary" disabled={Boolean(busy)} onClick={() => void toBuild()}>Send to Build requests</button>
          </div></div>
        <pre className="cs-diff" aria-label="Python draft"><span>{written.code}</span></pre>
        {written.tests && <><h3>Tests</h3><pre className="cs-diff" aria-label="Tests"><span>{written.tests}</span></pre></>}
      </section>
    </>}
  </div>;
}

/** The Plain English tab in Code Doctor. */
export function PlainEnglish({ code }: { code: ScanState }) {
  const [view, setView] = useState<"read" | "write">(() => { try { return localStorage.getItem("zaenia.plainEnglish.view") === "write" ? "write" : "read"; } catch { return "read"; } });
  const choose = (next: "read" | "write") => { setView(next); try { localStorage.setItem("zaenia.plainEnglish.view", next); } catch { /* optional */ } };
  if (!LIVE_API) return <p className="cs-muted">Plain English needs the ZÆNIA server: open it in the desktop app.</p>;
  return <div className="cs pe">
    <div className="cs-chips" role="group" aria-label="Plain English">
      <button type="button" aria-pressed={view === "read"} onClick={() => choose("read")}>Read ZAE's code</button>
      <button type="button" aria-pressed={view === "write"} onClick={() => choose("write")}>Write in plain English</button>
    </div>
    <div hidden={view !== "read"}><ReadCode code={code}/></div>
    <div hidden={view !== "write"}><WritePython code={code}/></div>
  </div>;
}
