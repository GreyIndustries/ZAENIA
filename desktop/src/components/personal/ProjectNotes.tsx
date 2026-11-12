import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { LiveTranscript } from "../notes/LiveTranscript";

type Note = { id: string; revision: number; title: string; body: string; pinned: boolean; archived: boolean; reference: boolean };
const PATH = "/api/platform/notes";

/** A project's notes: real notes from the Notes tab (shared everywhere), editable here, with live transcripts. */
export function ProjectNotes({ projectTitle, noteIds, onLink }: { projectTitle: string; noteIds: string[]; onLink: (ids: string[]) => Promise<void> | void }) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [all, setAll] = useState<{ id: string; title: string }[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    if (!LIVE_API) return;
    const found: Note[] = [];
    for (const id of noteIds) { try { found.push(await api<Note>("GET", `${PATH}/${id}`)); } catch { /* deleted elsewhere */ } }
    setNotes(found); setDrafts(Object.fromEntries(found.map(note => [note.id, note.body])));
  }, [noteIds.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [load]);

  const save = async (note: Note, body: string) => {
    if (body === note.body) return;
    setStatus(s => ({ ...s, [note.id]: "Saving…" }));
    try {
      const saved = await api<Note>("PUT", `${PATH}/${note.id}`, { title: note.title, body, pinned: note.pinned, archived: note.archived, reference: note.reference, revision: note.revision });
      setNotes(list => list.map(item => item.id === note.id ? saved : item)); setStatus(s => ({ ...s, [note.id]: "Saved" }));
    } catch (failure) { setStatus(s => ({ ...s, [note.id]: errorText(failure) })); }
  };
  const create = async () => {
    setError(null);
    try {
      const note = await api<Note>("POST", PATH, { title: `${projectTitle || "Project"}: note ${notes.length + 1}`.slice(0, 160), body: "", pinned: false, archived: false, reference: false });
      await onLink([...noteIds, note.id]);
    } catch (failure) { setError(errorText(failure)); }
  };

  return <fieldset className="project-notes"><legend>Project notes <small>shared with the Notes tab</small></legend>
    {error && <small className="project-notes__error">{error}</small>}
    {notes.map(note => <div className="project-notes__note" key={note.id}>
      <div className="project-notes__head"><strong>{note.title}</strong><small>{status[note.id] ?? ""}</small>
        <button type="button" onClick={() => void onLink(noteIds.filter(id => id !== note.id))} title="Unlink from this project (the note stays in Notes)">Unlink</button></div>
      <textarea rows={4} maxLength={30000} value={drafts[note.id] ?? ""} onChange={event => setDrafts(d => ({ ...d, [note.id]: event.target.value }))} onBlur={event => void save(note, event.target.value)}/>
      <LiveTranscript onText={text => setDrafts(d => { const body = (d[note.id] ? d[note.id].replace(/\s*$/, "") + "\n" : "") + text; void save(note, body); return { ...d, [note.id]: body }; })}/>
    </div>)}
    <div className="project-notes__actions">
      <button type="button" onClick={() => void create()}>New note for this project</button>
      <button type="button" onClick={() => all ? setAll(null) : void api<{ notes: { id: string; title: string }[] }>("GET", PATH).then(r => setAll(r.notes), f => setError(errorText(f)))}>{all ? "Cancel" : "Link an existing note"}</button>
    </div>
    {all && <div className="project-notes__pick">{all.filter(n => !noteIds.includes(n.id)).map(n => <button type="button" key={n.id} onClick={() => { setAll(null); void onLink([...noteIds, n.id]); }}>{n.title}</button>)}</div>}
  </fieldset>;
}
