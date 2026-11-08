import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { api, errorText, IN_TAURI, LIVE_API } from "../../core/bridge";
import "../research/Research.css";
import "./ToolTabs.css";

type Language = "python" | "javascript" | "powershell";
type Result = { exitCode: number | null; timedOut: boolean; seconds: number; stdout: string; stderr: string; truncated: boolean; passed: boolean | null };
type Snippet = { id: string; title: string; language: Language; code: string; tests: string; updated: string };
const STARTERS: Record<Language, { code: string; tests: string }> = {
  python: { code: "def greet(name):\n    return f\"Hello, {name}\"\n\nprint(greet(\"Grey\"))\n", tests: "assert greet(\"ZAE\") == \"Hello, ZAE\"\n" },
  javascript: { code: "function greet(name) {\n  return `Hello, ${name}`;\n}\n\nconsole.log(greet(\"Grey\"));\n", tests: "if (greet(\"ZAE\") !== \"Hello, ZAE\") throw new Error(\"greet failed\");\n" },
  powershell: { code: "function Get-Greeting($Name) { \"Hello, $Name\" }\n\nGet-Greeting \"Grey\"\n", tests: "if ((Get-Greeting \"ZAE\") -ne \"Hello, ZAE\") { throw \"greeting failed\" }\n" },
};
const KEY = "zaenia.playground";

function saved(): { language: Language; code: string; tests: string; stdin: string; title: string; id: string } {
  try { const data = JSON.parse(localStorage.getItem(KEY) ?? ""); if (data.language in STARTERS) return data; } catch { /* first visit */ }
  return { language: "python", ...STARTERS.python, stdin: "", title: "Untitled", id: "" };
}

/** Tab inserts spaces instead of leaving the box, like a code editor. */
function indentKeys(event: KeyboardEvent<HTMLTextAreaElement>, set: (value: string) => void) {
  if (event.key !== "Tab") return;
  event.preventDefault();
  const box = event.currentTarget; const start = box.selectionStart; const end = box.selectionEnd;
  const next = box.value.slice(0, start) + "    " + box.value.slice(end);
  set(next);
  requestAnimationFrame(() => { box.selectionStart = box.selectionEnd = start + 4; });
}

/** Playground: write code, run it and test it on this PC before implementing it in a project. */
export function PlaygroundPanel() {
  const start = useRef(saved());
  const [language, setLanguage] = useState<Language>(start.current.language);
  const [code, setCode] = useState(start.current.code);
  const [tests, setTests] = useState(start.current.tests);
  const [stdin, setStdin] = useState(start.current.stdin);
  const [title, setTitle] = useState(start.current.title);
  const [snippetId, setSnippetId] = useState(start.current.id);
  const [timeout, setTimeoutSeconds] = useState(10);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [answer, setAnswer] = useState<{ text: string; code: string | null } | null>(null);
  const [question, setQuestion] = useState("");
  const [list, setList] = useState<Snippet[]>([]);
  const [target, setTarget] = useState({ project: "C:\\Projects", file: "", hash: "" });

  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify({ language, code, tests, stdin, title, id: snippetId })); } catch { /* optional */ } }, [language, code, tests, stdin, title, snippetId]);
  const loadList = useCallback(() => api<{ snippets: Snippet[] }>("GET", "/api/code/snippets").then(r => setList(r.snippets), () => undefined), []);
  useEffect(() => { if (LIVE_API) void loadList(); }, [loadList]);
  useEffect(() => { // a Python draft from the Plain English tab
    const load = (event: Event) => {
      const draft = (event as CustomEvent<{ code: string; tests: string; title: string }>).detail;
      if (!draft) return;
      setLanguage("python"); setCode(draft.code); setTests(draft.tests); setTitle(draft.title); setSnippetId(""); setResult(null); setAnswer(null);
      setNote("Loaded the Plain English draft. Run or test it here; nothing is saved to a project until you implement it.");
    };
    window.addEventListener("zae:playground-load", load); return () => window.removeEventListener("zae:playground-load", load);
  }, []);

  const act = async (label: string, action: () => Promise<void>) => {
    setBusy(label); setError(null); setNote(null);
    try { await action(); } catch (failure) { setError(errorText(failure)); } finally { setBusy(null); }
  };
  const run = (withTests: boolean) => act(withTests ? "test" : "run", async () => {
    setResult(await api<Result>("POST", "/api/code/run", { language, code, tests: withTests ? tests : "", stdin, timeout }, { desktop: true, timeoutMs: (timeout + 15) * 1000 }));
  });
  const ask = (q: string) => act("ask", async () => {
    const reply = await api<{ answer: string; code: string | null }>("POST", "/api/code/playground/ask", { language, code, tests, result, question: q }, { timeoutMs: 240_000 });
    setAnswer({ text: reply.answer.replace(/```[\s\S]*?```/g, "").trim(), code: reply.code });
  });
  const saveSnippet = () => act("save", async () => {
    const saved = await api<Snippet>("POST", "/api/code/snippets", { id: snippetId, title, language, code, tests });
    setSnippetId(saved.id); setNote("Saved to your snippets."); await loadList();
  });
  const loadFile = () => act("load", async () => {
    const found = await api<{ text: string; hash: string }>("POST", "/api/code/load", { project: target.project, file: target.file });
    setCode(found.text); setTarget({ ...target, hash: found.hash }); setNote(`Loaded ${target.file}. Edit and test it here, then implement.`);
  });
  const implement = () => act("implement", async () => {
    const done = await api<{ saved: string; backup: string | null; created: boolean }>("POST", "/api/code/implement", { project: target.project, file: target.file, code, oldHash: target.hash }, { desktop: true });
    setNote(done.created ? `Created ${done.saved}.` : `Updated ${done.saved}. The old version is backed up.`);
    setTarget({ ...target, hash: "" });
  });

  if (!LIVE_API) return <div className="research"><p className="research__note">The playground needs the ZÆNIA server: open it in the desktop app.</p></div>;
  const ok = result && !result.timedOut && result.exitCode === 0;

  return <div className="research pg">
    <p className="research__note">Write code and run it on this PC in a throwaway folder (time-limited, none of ZAE's keys or settings passed in) before you put it into a project. {IN_TAURI ? "" : "Running code works from the desktop app only."}</p>
    <div className="research__bar">
      <input value={title} maxLength={120} aria-label="Snippet name" onChange={e => setTitle(e.target.value)} style={{ flex: "1 1 200px" }}/>
      <select value={language} aria-label="Language" onChange={e => { const next = e.target.value as Language; setLanguage(next); if (!code.trim() || Object.values(STARTERS).some(s => s.code === code)) { setCode(STARTERS[next].code); setTests(STARTERS[next].tests); } }}>
        <option value="python">Python</option><option value="javascript">JavaScript (Node)</option><option value="powershell">PowerShell</option></select>
      <label className="research__meta" style={{ margin: 0 }}>Time limit <select value={timeout} onChange={e => setTimeoutSeconds(Number(e.target.value))}>{[5, 10, 30, 60].map(s => <option key={s} value={s}>{s}s</option>)}</select></label>
      <button type="button" className="research__primary" disabled={!!busy || !code.trim()} onClick={() => void run(false)}>{busy === "run" ? "Running…" : "▶ Run"}</button>
      <button type="button" disabled={!!busy || !code.trim() || !tests.trim()} onClick={() => void run(true)}>{busy === "test" ? "Testing…" : "Run tests"}</button>
      <button type="button" disabled={!!busy} onClick={() => void saveSnippet()}>Save</button>
      <button type="button" disabled={!!busy} onClick={() => { setSnippetId(""); setTitle("Untitled"); setCode(STARTERS[language].code); setTests(STARTERS[language].tests); setResult(null); setAnswer(null); }}>New</button>
    </div>
    {error && <p className="research__error" role="alert">{error}</p>}
    {note && <p className="research__meta">✓ {note}</p>}
    <div className="pg-grid">
      <div className="pg-editor">
        <label className="pg-label">Code<textarea className="pg-code" spellCheck={false} value={code} onChange={e => setCode(e.target.value)} onKeyDown={e => indentKeys(e, setCode)} rows={18}/></label>
        <label className="pg-label">Tests <small>(run after the code; any error or failed assert means they failed)</small><textarea className="pg-code pg-code--tests" spellCheck={false} value={tests} onChange={e => setTests(e.target.value)} onKeyDown={e => indentKeys(e, setTests)} rows={6}/></label>
        <details><summary className="research__meta">Input (stdin)</summary><textarea className="pg-code pg-code--tests" value={stdin} onChange={e => setStdin(e.target.value)} rows={3}/></details>
      </div>
      <div className="pg-side">
        <section className="research__side">
          <h3>Output {result && <small className={ok ? "pg-ok" : "pg-bad"}>{result.timedOut ? "stopped: time limit" : result.passed === true ? "✓ tests passed" : result.passed === false ? "✕ tests failed" : `exit ${result.exitCode}`} · {result.seconds}s</small>}</h3>
          {!result && <p className="research__empty">Run the code to see its output here.</p>}
          {result && <pre className="pg-out">{result.stdout || (result.stderr ? "" : "(no output)")}{result.stderr && <span className="pg-err">{result.stderr}</span>}{result.truncated ? "\n… output cut short" : ""}</pre>}
        </section>
        <section className="research__side">
          <h3>ZAE</h3>
          <div className="research__actions">
            <button type="button" disabled={!!busy || !code.trim()} onClick={() => void ask("")}>{busy === "ask" ? "Looking…" : result && !ok ? "Explain the error & fix" : "Review & improve"}</button>
            <button type="button" disabled={!!busy || !code.trim()} onClick={() => void ask("Write good tests for this code (only the test code, in one ```code block```), covering normal cases and edge cases.")}>Write tests</button>
          </div>
          <form className="research__bar" onSubmit={e => { e.preventDefault(); if (question.trim()) void ask(question.trim()); }}>
            <input value={question} maxLength={1000} placeholder="Ask about this code…" onChange={e => setQuestion(e.target.value)}/><button type="submit" disabled={!question.trim() || !!busy}>Ask</button></form>
          {answer && <div className="research__result">{answer.text.split("\n").map((line, i) => <p key={i}>{line}</p>)}
            {answer.code && <><pre className="pg-out">{answer.code}</pre><div className="research__actions">
              <button type="button" onClick={() => setCode(answer.code ?? code)}>Use as code</button>
              <button type="button" onClick={() => setTests(answer.code ?? tests)}>Use as tests</button></div></>}</div>}
        </section>
        <section className="research__side">
          <h3>Implement <small>put it into a project once it works</small></h3>
          <div className="research__bar"><input value={target.project} aria-label="Project folder" placeholder="Project folder, e.g. C:\\Projects\\MyApp" onChange={e => setTarget({ ...target, project: e.target.value, hash: "" })}/></div>
          <div className="research__bar"><input value={target.file} aria-label="File in the project" placeholder="File, e.g. src\\utils.py" onChange={e => setTarget({ ...target, file: e.target.value, hash: "" })}/>
            <button type="button" disabled={!!busy || !target.file.trim()} onClick={() => void loadFile()}>Load file</button></div>
          <div className="research__actions"><button type="button" className="research__primary" disabled={!!busy || !target.file.trim() || !code.trim()} onClick={() => void implement()}>{target.hash ? "Implement (replace the file)" : "Implement (new file)"}</button></div>
          <small className="research__meta">New files are created; to change an existing file, load it first. The old version is backed up, and ZAE's security code can't be changed here.</small>
        </section>
        {list.length > 0 && <section className="research__side"><h3>Snippets</h3>
          <ul className="research__list">{list.map(s => <li key={s.id} className="research__bar">
            <button type="button" style={{ flex: 1 }} onClick={() => { setSnippetId(s.id); setTitle(s.title); setLanguage(s.language); setCode(s.code); setTests(s.tests); setResult(null); setAnswer(null); }}>
              <span>{s.title}</span><small>{s.language} · {new Date(s.updated).toLocaleDateString()}</small></button>
            <button type="button" className="research__danger" aria-label={`Delete ${s.title}`} onClick={() => void api("DELETE", `/api/code/snippets/${s.id}`).then(loadList)}>✕</button></li>)}</ul></section>}
      </div>
    </div>
  </div>;
}
