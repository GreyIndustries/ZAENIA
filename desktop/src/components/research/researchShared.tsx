import { useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";

export type Topic = { id: string; name: string; sources: number; updatedAt?: string };
export type AnalysisTask = "summary" | "facts_opinion" | "book" | "ask" | "what_happened" | "suggest" | "translate"
  | "sc_explain" | "sc_traditions" | "sc_compare" | "sc_crossrefs" | "sc_wordstudy" | "sc_translate"
  | "nb_summary" | "nb_compare" | "nb_claims" | "nb_timeline" | "nb_patterns" | "nb_next";
export type Material = { text?: string; url?: string; kind?: "article" | "book"; title?: string; term?: string; period?: string; topicId?: string };

export const UNTRUSTED_NOTE = "Free, legal sources only. Web, news and book text is untrusted: ZAE reads it, never follows it. Analysis runs on her own brain on your PC.";

export async function analyze(task: AnalysisTask, material: Material, question = ""): Promise<string> {
  const reply = await api<{ result: string }>("POST", "/api/research/analyze", { task, question, ...material }, { timeoutMs: 300_000 });
  return reply.result;
}

/** Her written answer, shown under the buttons that asked for it. */
export function AnalysisResult({ busy, result, error }: { busy: string | null; result: string; error: string | null }) {
  if (busy) return <p className="research__working" role="status">ZAE is reading… ({busy})</p>;
  if (error) return <p className="research__error" role="alert">{error}</p>;
  if (!result) return null;
  return <div className="research__result" aria-live="polite">{result.split("\n").map((line, index) => <p key={index}>{line.replace(/\*\*/g, "").replace(/^#+\s*/, "")}</p>)}</div>;
}

/** Runs one analysis at a time and keeps its answer. */
export function useAnalysis() {
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState("");
  const [error, setError] = useState<string | null>(null);
  const run = async (label: string, task: AnalysisTask, material: Material, question = "") => {
    setBusy(label); setError(null); setResult("");
    try { setResult(await analyze(task, material, question)); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(null); }
  };
  return { busy, result, error, run, clear: () => { setResult(""); setError(null); } };
}

/** "Add to notebook": pick a topic (or make one), then save the source there. */
export function AddToNotebook({ source, disabled }: { source: { title: string; kind: string; url?: string; text?: string; meta?: string; fetch?: boolean } | null; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [name, setName] = useState("");
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => {
    if (!open || !LIVE_API) return;
    api<{ topics: Topic[] }>("GET", "/api/research/notebook").then(reply => setTopics(reply.topics), failure => setNote(errorText(failure)));
  }, [open]);
  const save = async (topicId: string | null) => {
    if (!source) return;
    try {
      let id = topicId;
      if (!id) id = (await api<{ id: string }>("POST", "/api/research/notebook", { name: name.trim() })).id;
      await api("POST", `/api/research/notebook/${id}/sources`, { title: source.title.slice(0, 300), kind: source.kind, url: source.url ?? "",
        text: (source.text ?? "").slice(0, 20_000), meta: source.meta ?? "", fetch: Boolean(source.fetch) }, { timeoutMs: 60_000 });
      setNote("Added to your notebook."); setOpen(false); setName("");
    } catch (failure) { setNote(errorText(failure)); }
  };
  return <span className="research__add">
    <button type="button" disabled={disabled || !source} onClick={() => { setOpen(value => !value); setNote(null); }}>Add to notebook</button>
    {open && <span className="research__add-menu" role="menu">
      {topics.map(topic => <button type="button" role="menuitem" key={topic.id} onClick={() => void save(topic.id)}>{topic.name}</button>)}
      <form onSubmit={event => { event.preventDefault(); if (name.trim()) void save(null); }}>
        <input value={name} maxLength={120} placeholder="New topic…" aria-label="New topic name" onChange={event => setName(event.target.value)}/>
        <button type="submit" disabled={!name.trim()}>Add</button>
      </form>
    </span>}
    {note && <small className="research__add-note">{note}</small>}
  </span>;
}

export function NeedsServer({ what }: { what: string }) {
  return <p className="research__note">{what} needs the ZÆNIA server: open it in the desktop or phone app.</p>;
}
