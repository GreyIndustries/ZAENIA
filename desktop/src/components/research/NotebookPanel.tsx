import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import type { AnalysisTask, Topic } from "./researchShared";
import { AnalysisResult, NeedsServer, UNTRUSTED_NOTE, useAnalysis } from "./researchShared";
import { securitySession } from "../security/SecurityPanel";
import { LiveTranscript } from "../notes/LiveTranscript";
import "./Research.css";
import { DetailScreen, detailKey } from "../shell/PageNavigator";

type Source = { id: string; title: string; kind: string; url: string; meta: string; chars: number; addedAt: string };
type TopicDetail = { id: string; name: string; notes: string; noteId?: string; sources: Source[] };
type NoteSummary = { id: string; title: string };

const ACTIONS: { task: AnalysisTask; label: string }[] = [
  { task: "nb_summary", label: "Summary" }, { task: "nb_compare", label: "Compare sources" }, { task: "nb_claims", label: "Claims vs evidence" },
  { task: "nb_timeline", label: "Timeline" }, { task: "nb_patterns", label: "Patterns & causes" }, { task: "nb_next", label: "What to research next" },
];

/** Notebook: topics, the sources gathered for each (from Library, News or Historical connections), and your notes. */
export function NotebookPanel() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [current, setCurrent] = useState<TopicDetail | null>(null);
  const [newName, setNewName] = useState("");
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState("");
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [paste, setPaste] = useState<{ title: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const analysis = useAnalysis();
  const timer = useRef<number | null>(null);
  const notesRef = useRef(""); notesRef.current = notes;
  const [linkable, setLinkable] = useState<NoteSummary[] | null>(null);

  const loadTopics = useCallback(async () => {
    try { setTopics((await api<{ topics: Topic[] }>("GET", "/api/research/notebook")).topics); }
    catch (failure) { setError(errorText(failure)); }
  }, []);
  useEffect(() => { if (LIVE_API) void loadTopics(); }, [loadTopics]);
  const open = async (id: string) => {
    setError(null); analysis.clear(); setConfirmDelete(false); setSelectedSource(null);
    try { const topic = await api<TopicDetail>("GET", `/api/research/notebook/${id}`); setCurrent(topic); setNotes(topic.notes); setSaved(""); }
    catch (failure) { setError(errorText(failure)); }
  };
  // Notes save as you type (a moment after you stop).
  const typeNotes = (value: string) => {
    setNotes(value); setSaved("Saving…");
    if (timer.current) window.clearTimeout(timer.current);
    const id = current?.id;
    timer.current = window.setTimeout(() => {
      if (!id) return;
      api("PUT", `/api/research/notebook/${id}/notes`, { notes: value }).then(() => setSaved("Saved"), failure => setSaved(errorText(failure)));
    }, 800);
  };
  const create = async () => {
    if (!newName.trim()) return;
    try { const topic = await api<TopicDetail>("POST", "/api/research/notebook", { name: newName.trim() }); setNewName(""); await loadTopics(); await open(topic.id); }
    catch (failure) { setError(errorText(failure)); }
  };
  const remove = async () => {
    if (!current) return;
    if (!confirmDelete) { setConfirmDelete(true); return; }
    await api("DELETE", `/api/research/notebook/${current.id}`).catch(failure => setError(errorText(failure)));
    setCurrent(null); setConfirmDelete(false); await loadTopics();
  };
  const addPasted = async () => {
    if (!current || !paste?.title.trim()) return;
    try { setCurrent(await api<TopicDetail>("POST", `/api/research/notebook/${current.id}/sources`, { title: paste.title, kind: "pasted", text: paste.text.slice(0, 20_000) })); setPaste(null); }
    catch (failure) { setError(errorText(failure)); }
  };
  const removeSource = async () => {
    if (!current || !selectedSource) return;
    try { setCurrent(await api<TopicDetail>("DELETE", `/api/research/notebook/${current.id}/sources/${selectedSource}`)); setSelectedSource(null); }
    catch (failure) { setError(errorText(failure)); }
  };
  // The topic's notes are a note in the Notes tab already; this adds ZAE's analysis and the source list to it.
  const saveToNotes = async () => {
    if (!current?.noteId) return;
    const text = [analysis.result ? `ZAE's analysis:\n${analysis.result}` : "",
      current.sources.length ? `Sources:\n${current.sources.map(source => `- ${source.title}${source.url ? ` (${source.url})` : ""}`).join("\n")}` : ""].filter(Boolean).join("\n\n");
    if (!text) { setSaved("Nothing new to add"); return; }
    try { await api("POST", `/api/platform/notes/${current.noteId}/append`, { text }); await open(current.id); setSaved("Added to the note"); }
    catch (failure) { setError(errorText(failure)); }
  };
  const showLinkable = async () => {
    try { setLinkable((await api<{ notes: NoteSummary[] }>("GET", "/api/platform/notes")).notes); } catch (failure) { setError(errorText(failure)); }
  };
  const linkNote = async (noteId: string) => {
    try { const topic = await api<TopicDetail>("POST", `/api/research/notebook/link/${noteId}`); setLinkable(null); await loadTopics(); await open(topic.id); }
    catch (failure) { setError(errorText(failure)); }
  };
  const saveToVault = async () => {
    if (!current) return;
    const session = securitySession();
    if (!session) { setError("Unlock the Vault first: Settings → Vault (or the Security tab)."); return; }
    const body = [notes, analysis.result ? `\n\nZAE's analysis:\n${analysis.result}` : "",
      current.sources.length ? `\n\nSources:\n${current.sources.map(source => `- ${source.title}${source.url ? ` (${source.url})` : ""}`).join("\n")}` : ""].join("");
    try { await api("POST", "/api/vault/save", { session, title: `Research: ${current.name}`.slice(0, 200), text: body }, { desktop: true }); setSaved("Saved to the Vault"); }
    catch (failure) { setError(errorText(failure)); }
  };
  if (!LIVE_API) return <div className="research"><NeedsServer what="The Notebook"/></div>;
  const chosen = current?.sources.find(source => source.id === selectedSource);

  return <div className="research research--notebook">
    <p className="research__note">{UNTRUSTED_NOTE}</p>
    {error && <p className="research__error" role="alert">{error}</p>}
    <div className="research__three">
      <section className="research__side" aria-label="Topics">
        <h3>Topics</h3>
        <ul className="research__list">{topics.map(topic => <li key={topic.id}><button type="button" aria-pressed={current?.id === topic.id}
          onClick={() => void open(topic.id)}>{topic.name}<small>{topic.sources} source{topic.sources === 1 ? "" : "s"}</small></button></li>)}</ul>
        <form className="research__bar" onSubmit={event => { event.preventDefault(); void create(); }}>
          <input value={newName} maxLength={120} placeholder="New topic…" aria-label="New topic name" onChange={event => setNewName(event.target.value)}/>
          <button type="submit" disabled={!newName.trim()}>New</button>
        </form>
        <button type="button" onClick={() => linkable ? setLinkable(null) : void showLinkable()}>{linkable ? "Cancel" : "Use one of my notes"}</button>
        {linkable && <ul className="research__list">{linkable.map(note => <li key={note.id}><button type="button" onClick={() => void linkNote(note.id)}>{note.title}</button></li>)}</ul>}
        {current && <button type="button" className="research__danger" onClick={() => void remove()}>{confirmDelete ? "Tap again to delete (the note stays)" : "Delete topic"}</button>}
      </section>

      <section className="research__side" aria-label="Sources">
        <DetailScreen id="notebook-topic" name="Notebook" open={!!current} itemId={current?.id} title={current?.name || "Topic"}
          onOpen={key => { const topic = topics.find(item => detailKey(item.id) === key); if (topic) void open(topic.id); }} onClose={() => setCurrent(null)}/>
        <h3>Sources{current ? `: ${current.name}` : ""}</h3>
        {current ? <>
          <ul className="research__list">{current.sources.map((source, index) => <li key={source.id}><button type="button" aria-pressed={selectedSource === source.id}
            onClick={() => setSelectedSource(source.id)} onDoubleClick={() => source.url && openLink(source.url)}>
            <span>{index + 1}. {source.title}</span><small>{source.kind}{source.chars ? ` · ${Math.round(source.chars / 1000)}k chars` : " · title only"}</small></button></li>)}</ul>
          {!current.sources.length && <p className="research__empty">Add sources with “Add to notebook” in Library, News or Historical connections, or paste one.</p>}
          {paste ? <div className="research__paste">
            <input value={paste.title} maxLength={300} placeholder="Title" aria-label="Source title" onChange={event => setPaste({ ...paste, title: event.target.value })}/>
            <textarea value={paste.text} maxLength={20000} placeholder="Paste the text…" aria-label="Source text" onChange={event => setPaste({ ...paste, text: event.target.value })}/>
            <div className="research__actions"><button type="button" onClick={() => void addPasted()} disabled={!paste.title.trim()}>Add</button><button type="button" onClick={() => setPaste(null)}>Cancel</button></div>
          </div> : <div className="research__actions">
            <button type="button" onClick={() => setPaste({ title: "", text: "" })}>Paste a source</button>
            <button type="button" disabled={!chosen?.url} onClick={() => chosen?.url && openLink(chosen.url)}>Open</button>
            <button type="button" className="research__danger" disabled={!chosen} onClick={() => void removeSource()}>Remove</button>
          </div>}
        </> : <p className="research__empty">Make or pick a topic.</p>}
      </section>

      <section className="research__side research__notes" aria-label="My notes">
        <h3>My notes <small>{current ? (saved || "saved as you type") + " · shared with the Notes tab" : ""}</small></h3>
        <textarea value={notes} disabled={!current} maxLength={30000} aria-label="My notes" placeholder={current ? "Write as you research…" : "Pick a topic first."} onChange={event => typeNotes(event.target.value)}/>
        <LiveTranscript disabled={!current} onText={text => typeNotes((notesRef.current ? notesRef.current.replace(/\s*$/, "") + "\n" : "") + text)}/>
        <div className="research__grid-actions">
          {ACTIONS.map(action => <button type="button" key={action.task} disabled={!current || !current.sources.length || !!analysis.busy}
            onClick={() => current && void analysis.run(action.label.toLowerCase(), action.task, { topicId: current.id })}>{action.label}</button>)}
        </div>
        <AnalysisResult {...analysis}/>
        <div className="research__actions">
          <button type="button" className="research__primary" disabled={!current} onClick={() => void saveToVault()}>Save to Vault</button>
          <button type="button" disabled={!current || (!analysis.result && !current.sources.length)} onClick={() => void saveToNotes()}>Add analysis & sources to the note</button>
          <button type="button" disabled={!notes && !analysis.result} onClick={() => void navigator.clipboard?.writeText([notes, analysis.result].filter(Boolean).join("\n\n"))}>Copy</button>
        </div>
      </section>
    </div>
  </div>;
}
