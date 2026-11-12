import { useEffect, useRef, useState } from 'react';
import { DetailScreen } from '../shell/PageNavigator';
import { api, errorText, LIVE_API } from '../../core/bridge';
import '../assistant/PlatformPanel.css';
import './NotesPanel.css';
import { LiveTranscript } from './LiveTranscript';

// Each note card gets its own size and tint (from its length and id) so the wall feels like a pinboard, not a form.
const TINTS = ['amber', 'blue', 'green', 'rose', 'violet'];
function look(item: { id: string; chars?: number }) {
  let hash = 0; for (const char of item.id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  const chars = item.chars ?? 0;
  const size = chars > 900 ? 'l' : chars > 250 ? (hash % 3 === 0 ? 'l' : 'm') : (hash % 4 === 0 ? 'm' : 's');
  return `note-card note-card--${size} note-card--${TINTS[hash % TINTS.length]}${hash % 2 ? ' note-card--tilt-l' : ' note-card--tilt-r'}`;
}

type Note = { id?: string; revision?: number; title: string; body: string; pinned: boolean; archived: boolean; reference: boolean; updatedAt?: string };
type Summary = { id: string; revision: number; title: string; excerpt: string; chars?: number; tags?: string[]; pinned: boolean; archived: boolean; reference: boolean; updatedAt: string };
type Listing = { notes: Summary[]; total: number; offset: number; nextOffset: number | null };
export type NotesDraft = { note: Note | null; dirty: boolean };
export const EMPTY_NOTES_DRAFT: NotesDraft = { note: null, dirty: false };
const PATH = '/api/platform/notes';
const blank = (): Note => ({ title: '', body: '', pinned: false, archived: false, reference: false });

export function NotesPanel({ draft: initialDraft, onDraft: rememberDraft }: { draft: NotesDraft; onDraft: (draft: NotesDraft) => void }) {
  const [draft, setDraft] = useState(initialDraft);
  function onDraft(next: NotesDraft) { setDraft(next); rememberDraft(next); }
  const [listing, setListing] = useState<Listing | null>(null);
  const [query, setQuery] = useState(''); const [archived, setArchived] = useState(false); const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('');
  // The note editor is its own screen (Claude 2026-11-11); Back returns to the wall and keeps the draft.
  const [editing, setEditing] = useState(false);
  useEffect(() => { const go = (event: Event) => { const detail = (event as CustomEvent<{ screen?: string; id?: string }>).detail; if (detail?.screen === "notes/editor" && detail.id) { open(detail.id); setEditing(true); } };
    window.addEventListener("zae:open-record", go); return () => window.removeEventListener("zae:open-record", go); });

  const locked = useRef(false); const ticket = useRef(0);
  const note = draft.note; const disabled = !LIVE_API || busy;
  const noteRef = useRef(note); noteRef.current = note;
  // Live transcript: each recognised piece goes on the end of the note being edited.
  function addTranscript(text: string) {
    const current = noteRef.current ?? blank();
    onDraft({ note: { ...current, title: current.title || `Transcript ${new Date().toLocaleString()}`, body: (current.body ? current.body.replace(/\s*$/, '') + '\n' : '') + text }, dirty: true });
  }

  async function load() {
    if (!LIVE_API) return;
    const current = ++ticket.current;
    const result = await api<Listing>('GET', `${PATH}?q=${encodeURIComponent(query)}&archived=${archived}&offset=${offset}`);
    if (current === ticket.current) setListing(result);
  }
  useEffect(() => {
    const timer = window.setTimeout(() => void load().catch(e => setError(errorText(e))), 250);
    return () => { window.clearTimeout(timer); ticket.current++; };
  }, [query, archived, offset]);

  async function perform(action: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError(''); setMessage('');
    try { await action(); await load(); } catch (e) { setError(errorText(e)); }
    finally { locked.current = false; setBusy(false); }
  }
  function edit(changes: Partial<Note>) {
    onDraft({ note: { ...(note ?? blank()), ...changes }, dirty: true }); setMessage('');
  }
  async function save(changes: Partial<Note> = {}) {
    if (!note) return;
    const value = { ...note, ...changes };
    const saved = await api<Note>(value.id ? 'PUT' : 'POST', value.id ? `${PATH}/${value.id}` : PATH, {
      title: value.title, body: value.body, pinned: value.pinned, archived: value.archived, reference: value.reference,
      ...(value.id ? { revision: value.revision } : {}),
    });
    onDraft({ note: saved, dirty: false });
    setMessage(changes.archived === true ? 'Note archived. Find it in Archived notes to restore it.' : changes.archived === false ? 'Note restored.' : 'Note saved.');
  }
  function open(id: string) {
    void perform(async () => { const saved = await api<Note>('GET', `${PATH}/${id}`); onDraft({ note: saved, dirty: false }); });
  }

  return <section className="platform-panel notes-panel" aria-label="Saved notes" aria-busy={busy}>
    <div className="platform-panel__heading"><div><span className="subheading">KEEP FOR LATER</span><h2>Your notes</h2></div>
      <button type="button" disabled={disabled || draft.dirty} onClick={() => { onDraft({ note: blank(), dirty: false }); setError(''); setMessage(''); setEditing(true); }}>New note</button>
    </div>
    {!LIVE_API && <p className="platform-note">Connect to ZAE to open and save your notes.</p>}
    {error && <p className="platform-error" role="alert">{error}</p>}
    {message && <p className="platform-note" role="status">{message}</p>}
    <DetailScreen id="note-editor" name="All notes" open={editing && !!note} title={note?.title.trim() || 'New note'} onOpen={() => setEditing(true)} onClose={() => setEditing(false)}/>
    {!editing && note && <button type="button" className="personal-resume" onClick={() => setEditing(true)}>Continue {note.title.trim() || 'new note'}{draft.dirty ? ' · unsaved draft' : ''}</button>}
    <div className="notes-controls" hidden={editing && !!note}>
      <label>Search notes<input type="search" value={query} maxLength={300} placeholder="Search titles and text…" onChange={e => { setQuery(e.target.value); setOffset(0); }}/></label>
      <label className="platform-check"><input type="checkbox" checked={archived} onChange={e => { setArchived(e.target.checked); setOffset(0); }}/>Show archived notes</label>
      <button type="button" disabled={disabled} onClick={() => void perform(async () => {})}>Refresh notes</button>
    </div>
    <div className="notes-workspace notes-workspace--wall">
      <div className="notes-editor" hidden={!(editing && note)}>
        {note ? <form onSubmit={e => { e.preventDefault(); void perform(() => save()); }}>
          <div className="platform-card__head"><strong>{note.id ? 'Edit note' : 'New note'}</strong><span>{draft.dirty ? 'Unsaved changes' : note.id ? 'Saved' : 'Not saved yet'}</span></div>
          <label>Note title<input value={note.title} maxLength={160} required disabled={disabled} onChange={e => edit({ title: e.target.value })}/></label>
          <label>Note text<textarea value={note.body} maxLength={30000} disabled={disabled} placeholder="Write anything you want to refer to later…" onChange={e => edit({ body: e.target.value })}/></label>
          <LiveTranscript disabled={disabled} onText={addTranscript}/>
          <small>{note.body.length.toLocaleString()} / 30,000 characters</small>
          <label className="platform-check"><input type="checkbox" checked={note.pinned} disabled={disabled} onChange={e => edit({ pinned: e.target.checked })}/>Pin this note</label>
          <label className="platform-check"><input type="checkbox" checked={note.reference} disabled={disabled} onChange={e => edit({ reference: e.target.checked })}/>Let ZAE reference this note in relevant conversations</label>
          <small>You can also ask “search my notes for…” when you want ZAE to look up a saved note.</small>
          <div className="platform-inline">
            <button type="submit" disabled={disabled || !note.title.trim() || (!draft.dirty && Boolean(note.id))}>Save note</button>
            {draft.dirty && <button type="button" disabled={disabled} onClick={() => void perform(async () => { onDraft({ note: note.id ? await api<Note>('GET', `${PATH}/${note.id}`) : null, dirty: false }); setMessage('Unsaved edits discarded.'); })}>Discard edits</button>}
            {note.id && <button type="button" disabled={disabled || draft.dirty} onClick={() => void perform(() => save({ archived: !note.archived }))}>{note.archived ? 'Restore note' : 'Archive note'}</button>}
          </div>
          {draft.dirty && <small>Save or discard edits before opening another note. Your draft stays here while you move between tabs.</small>}
          {note.updatedAt && <small>Last saved {new Date(note.updatedAt).toLocaleString()}</small>}
          {note.archived && <p className="platform-note">Archived. ZAE leaves this note out of conversation references until you restore it.</p>}
        </form> : <p className="platform-note">Pick a note below or select New note. Notes are shared with Research › Notebook and Workbench projects; in chat, say “add this to notes” or “update my ___ note with this”.</p>}
      </div>
      <div className="notes-wall" aria-label="Your notes" hidden={editing && !!note}>
        <small className="notes-wall__count">{listing ? `${listing.total} ${archived ? 'archived' : 'saved'} ${listing.total === 1 ? 'note' : 'notes'}` : 'Loading notes…'}</small>
        {listing?.notes.length === 0 && <p>{query ? 'No notes match this search.' : archived ? 'No archived notes.' : 'Save ideas, details and things you want to come back to.'}</p>}
        {listing?.notes.map(item => <button type="button" key={item.id} className={look(item)} aria-pressed={note?.id === item.id} disabled={disabled || draft.dirty} onClick={() => { open(item.id); setEditing(true); }}>
          <strong>{item.pinned ? '★ ' : ''}{item.title}</strong><span>{item.excerpt || 'Empty note'}</span>
          {item.tags?.length ? <em>{item.tags.join(' · ')}</em> : null}
          <small>{new Date(item.updatedAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}{item.reference ? ' · ZAE can reference' : ''}</small>
        </button>)}
        <div className="platform-inline notes-wall__pages">
          {offset > 0 && <button type="button" disabled={disabled} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous notes</button>}
          {listing?.nextOffset != null && <button type="button" disabled={disabled} onClick={() => setOffset(listing.nextOffset!)}>More notes</button>}
        </div>
      </div>
    </div>
  </section>;
}
