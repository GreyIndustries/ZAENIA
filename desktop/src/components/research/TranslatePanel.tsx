import { useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { AddToNotebook, NeedsServer } from "./researchShared";
import "./Research.css";

type Result = { translation: string; detected: string; pieces: number; truncated: boolean; target: string; title: string; original: string };
const STYLE_LABELS: Record<string, string> = { natural: "Natural", literal: "Literal", notes: "With notes" };
const FALLBACK = ["English", "Spanish", "French", "German", "Hebrew", "Greek", "Arabic", "Latin", "Chinese", "Japanese"];
const KEY = "zaenia.translate";

function saved(): { target: string; source: string; style: string } {
  try { const data = JSON.parse(localStorage.getItem(KEY) ?? ""); return { target: data.target || "English", source: data.source || "auto", style: data.style || "natural" }; }
  catch { return { target: "English", source: "auto", style: "natural" }; }
}

/** Translate: paste text or a web address and ZAE translates it with her own brain on your PC. */
export function TranslatePanel() {
  const [languages, setLanguages] = useState<string[]>(FALLBACK);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [choice, setChoice] = useState(saved);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (LIVE_API) api<{ languages: string[] }>("GET", "/api/research/translate/languages").then(reply => setLanguages(reply.languages), () => undefined);
  }, []);
  const pick = (key: "target" | "source" | "style", value: string) => setChoice(current => {
    const next = { ...current, [key]: value };
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* optional */ }
    return next;
  });
  const run = async (fromUrl: boolean) => {
    setBusy(true); setError(null); setResult(null); setCopied(false);
    try {
      setResult(await api<Result>("POST", "/api/research/translate", { ...(fromUrl ? { url: url.trim() } : { text }), ...choice }, { timeoutMs: 600_000 }));
    } catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  };
  const swap = () => {
    if (!result || choice.source === "auto") return;
    setText(result.translation); setResult(null);
    setChoice(current => ({ ...current, source: current.target, target: current.source }));
  };
  const copy = async () => {
    if (!result) return;
    try { await navigator.clipboard.writeText(result.translation); setCopied(true); } catch { setError("Couldn't copy; select the text instead."); }
  };
  if (!LIVE_API) return <div className="research"><NeedsServer what="Translate"/></div>;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;

  return <div className="research">
    <p className="research__note">Translation runs on ZAE's own brain on your PC; nothing is sent to a translation service. Web pages are fetched as text and read as data, never as instructions. Long texts are translated in pieces.</p>
    <div className="research__bar">
      <label className="research__meta">From <select value={choice.source} onChange={event => pick("source", event.target.value)}>
        <option value="auto">Detect language</option>{languages.map(name => <option key={name}>{name}</option>)}</select></label>
      <button type="button" disabled={choice.source === "auto" || !result} title="Swap languages and translate back" onClick={swap}>⇄</button>
      <label className="research__meta">To <select value={choice.target} onChange={event => pick("target", event.target.value)}>
        {languages.map(name => <option key={name}>{name}</option>)}</select></label>
      <label className="research__meta">Style <select value={choice.style} onChange={event => pick("style", event.target.value)}>
        {Object.entries(STYLE_LABELS).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
    </div>
    <div className="research__split research__split--halves">
      <div className="research__side research__paste">
        <h3>Original <small>{words ? `${words} words` : ""}</small></h3>
        <textarea value={text} maxLength={200_000} rows={14} aria-label="Text to translate" placeholder="Paste or type text in any language…" onChange={event => setText(event.target.value)}/>
        <div className="research__actions">
          <button type="button" className="research__primary" disabled={busy || !text.trim()} onClick={() => void run(false)}>{busy ? "Translating…" : "Translate"}</button>
          <button type="button" disabled={busy || !text} onClick={() => { setText(""); setResult(null); }}>Clear</button>
        </div>
        <form className="research__bar" onSubmit={event => { event.preventDefault(); if (url.trim()) void run(true); }}>
          <input value={url} maxLength={1000} aria-label="Web address to translate" placeholder="…or a web address (article, page) to translate" onChange={event => setUrl(event.target.value)}/>
          <button type="submit" disabled={busy || !url.trim()}>Translate page</button>
        </form>
      </div>
      <div className="research__side">
        <h3>{result ? `${result.detected ? result.detected + " → " : ""}${result.target}` : "Translation"} {result?.title && <small>{result.title}</small>}</h3>
        {busy && <p className="research__working" role="status">ZAE is translating… long texts take a while on your PC.</p>}
        {error && <p className="research__error" role="alert">{error}</p>}
        {!busy && !result && !error && <p className="research__empty">The translation appears here.</p>}
        {result && <>
          <div className="research__result research__result--tall" aria-live="polite">{result.translation.split("\n").map((line, index) => <p key={index}>{line.replace(/\*\*/g, "")}</p>)}</div>
          {result.truncated && <p className="research__meta">Only the first 40,000 characters were translated.</p>}
          <div className="research__actions">
            <button type="button" onClick={() => void copy()}>{copied ? "Copied" : "Copy"}</button>
            {result.original && <button type="button" onClick={() => { setText(result.original); }}>Show original text</button>}
            <AddToNotebook source={{ title: `${result.title || "Translation"} (${result.target})`, kind: "web", url: url.trim() || undefined, text: result.translation, meta: `Translated ${result.detected ? "from " + result.detected + " " : ""}to ${result.target}` }}/>
          </div>
        </>}
      </div>
    </div>
  </div>;
}
