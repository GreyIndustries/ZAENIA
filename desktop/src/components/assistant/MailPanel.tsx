import { useCallback, useEffect, useRef, useState } from 'react';
import { api, connectGmail, errorText, IN_TAURI, LIVE_API } from '../../core/bridge';
import './MailPanel.css';
import { DetailScreen, detailKey } from "../shell/PageNavigator";

/**
 * Mail (Gmail over IMAP, core/email_watch). Reads ZAE's local copy of all mail; a reply is a draft
 * until Grey presses Approve and send, which needs the desktop app (or the phone confirmed at the PC).
 */
type Attachment = { index?: number; name: string; type?: string; size?: number };
type Mail = { id: string; threadId: string | null; fromName: string; fromAddress: string; to: string[]; cc: string[]; subject: string;
  internalDate: number; labels: string[]; snippet: string; attachments: Attachment[]; link: string; body?: string; category?: string | null; size?: number };
type Preview = { name: string; type: string; url?: string; text?: string };
type Reading = { index: number; name: string; kind: string; text: string; truncated: boolean; summary: string };
type Draft = { id: string; replyToId: string; to: string[]; cc: string[]; subject: string; body: string; status: string;
  verified: boolean; error: string | null; updatedAt: string };
type SyncState = { connected: boolean; address: string; stored: number; complete: boolean; lastSync: number | null; unread?: Record<string, number> };

// Gmail's inbox tabs (Primary, Promotions, Social, Updates) come from Gmail itself; then the usual folders.
const FOLDERS: { id: string; label: string; query: string; count?: string }[] = [
  { id: '', label: 'All mail', query: '' },
  { id: 'primary', label: 'Primary', query: '&category=primary', count: 'primary' },
  { id: 'promotions', label: 'Promotions', query: '&category=promotions', count: 'promotions' },
  { id: 'social', label: 'Social', query: '&category=social', count: 'social' },
  { id: 'updates', label: 'Updates', query: '&category=updates', count: 'updates' },
  { id: 'INBOX', label: 'Inbox', query: '&label=INBOX', count: 'inbox' },
  { id: 'UNREAD', label: 'Unread', query: '&label=UNREAD' },
  { id: 'STARRED', label: 'Starred', query: '&label=STARRED' },
  { id: 'SENT', label: 'Sent', query: '&label=SENT' },
];
const folderQuery = (id: string) => FOLDERS.find(item => item.id === id)?.query ?? '';
const FETCH_BYTES = 300_000; // bigger emails list their attachments from Gmail when opened
const size = (bytes?: number) => !bytes ? '' : bytes < 1024 ? `${bytes} B` : bytes < 1048576 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
const viewable = (type = '') => type.startsWith('image/') || type === 'application/pdf' || type.startsWith('text/');
const PAGE = 50;

const when = (ms: number) => ms ? new Date(ms).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';

export function MailPanel() {
  const [sync, setSync] = useState<SyncState | null>(null);
  const [list, setList] = useState<Mail[]>([]);
  const [query, setQuery] = useState('');
  const [folder, setFolder] = useState('');
  const [more, setMore] = useState(false);
  const [open, setOpen] = useState<{ message: Mail; thread: Mail[] } | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [reply, setReply] = useState('');
  const [note, setNote] = useState('');
  const [replyAll, setReplyAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [files, setFiles] = useState<Attachment[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [reading, setReading] = useState<Reading | null>(null);
  const previewUrl = useRef<string | null>(null);
  const clearPreview = () => { if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); previewUrl.current = null; setPreview(null); };
  useEffect(() => () => { if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); }, []);

  // No search: every email copied to this PC, newest first (optionally one folder), 50 at a time.
  const load = useCallback(async (search = '', box = '') => {
    const filter = search.trim() ? `&q=${encodeURIComponent(search.trim())}` : folderQuery(box);
    const [state, messages, waiting] = await Promise.all([
      api<SyncState>('GET', '/api/email/sync'),
      api<{ messages: Mail[] }>('GET', `/api/email/messages?limit=${PAGE}${filter}`),
      api<{ drafts: Draft[] }>('GET', '/api/email/drafts'),
    ]);
    setSync(state); setList(messages.messages); setDrafts(waiting.drafts); setMore(!search.trim() && messages.messages.length === PAGE);
  }, []);

  const loadMore = () => run(async () => {
    const last = list[list.length - 1];
    if (!last) return;
    const next = await api<{ messages: Mail[] }>('GET', `/api/email/messages?limit=${PAGE}&before=${last.internalDate + 1}${folderQuery(folder)}`);
    const fresh = next.messages.filter(m => !list.some(c => c.id === m.id));
    setList(current => [...current, ...fresh]);
    setMore(next.messages.length === PAGE && fresh.length > 0);
  });

  useEffect(() => {
    if (!LIVE_API) return;
    load('', folder).catch(failure => setError(errorText(failure)));
  }, [load, folder]);

  // While the first copy is still running, refresh the list each minute so new mail appears by itself.
  useEffect(() => {
    if (!LIVE_API || !sync?.connected || sync.complete || query.trim()) return;
    const timer = window.setInterval(() => { load('', folder).catch(() => undefined); }, 60_000);
    return () => window.clearInterval(timer);
  }, [load, folder, query, sync?.connected, sync?.complete]);

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(null); setNotice(null);
    try { await action(); } catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  }

  const seenMail = useRef(new Map<string, string>());
  const openMail = (id: string) => run(async () => {
    const opened = await api<{ message: Mail; thread: Mail[] }>('GET', `/api/email/messages/${id}`);
    seenMail.current.set(detailKey(opened.message.id), opened.message.id);
    setOpen(opened); setReply(''); setNote(''); setReplyAll(false); clearPreview(); setReading(null);
    setFiles(opened.message.attachments);
    // The local copy keeps the first 300 KB of each email; ask Gmail for the exact list when there may be more.
    if (opened.message.attachments.length || (opened.message.size ?? 0) > FETCH_BYTES) {
      const exact = await api<{ attachments: Attachment[] }>('GET', `/api/email/messages/${id}/attachments`, undefined, { timeoutMs: 120_000 });
      setFiles(exact.attachments);
    }
  });

  const attachmentPath = (file: Attachment) => `/api/email/messages/${open!.message.id}/attachments/${file.index ?? 0}`;
  const view = (file: Attachment) => run(async () => {
    const got = await api<{ name: string; type: string; data: string }>('GET', attachmentPath(file), undefined, { timeoutMs: 120_000 });
    clearPreview(); setReading(null);
    const bytes = Uint8Array.from(atob(got.data), c => c.charCodeAt(0));
    if (got.type.startsWith('text/')) { setPreview({ name: got.name, type: got.type, text: new TextDecoder().decode(bytes) }); return; }
    const url = URL.createObjectURL(new Blob([bytes], { type: got.type }));
    previewUrl.current = url; setPreview({ name: got.name, type: got.type, url });
  });
  const readFile = (file: Attachment) => run(async () => {
    clearPreview();
    setReading(await api<Reading>('POST', `${attachmentPath(file)}/read`, {}, { timeoutMs: 180_000 }));
  });
  const saveFile = (file: Attachment) => run(async () => {
    const saved = await api<{ path: string }>('POST', `${attachmentPath(file)}/save`, {}, { timeoutMs: 120_000 });
    setNotice(`Saved to ${saved.path}`);
  });

  const disabled = busy || !LIVE_API;
  const waitingFor = open ? drafts.filter(d => d.replyToId === open.message.id) : [];

  return (
    <section className="assistant-panel__section mail-panel" aria-labelledby="mail-heading" aria-busy={busy}>
      <header className="assistant-panel__heading"><h2 id="mail-heading">Mail</h2>
        <span>{sync?.connected ? `${sync.address} · ${sync.stored.toLocaleString()} emails on this PC${sync.complete ? '' : ' (still copying)'}` : 'Not connected'}</span></header>
      {sync && !sync.connected && <div className="mail-panel__connect">
        <p className="assistant-panel__note">Gmail isn't connected yet, so there's no mail to show. Connect it with your Google app password; you type it in a window on the PC. No Google Cloud setup needed.</p>
        {IN_TAURI ? <button type="button" disabled={busy} onClick={() => void run(async () => { await connectGmail(); setNotice('A Connect Gmail window opened on the PC. Type your address and app password there, then press Check now.'); })}>Connect Gmail</button>
          : <small>Connect from the ZÆNIA desktop app on the PC.</small>}
      </div>}
      {error && <p className="assistant-panel__error" role="alert">{error}</p>}
      {notice && <p className="assistant-panel__success" role="status">{notice}</p>}

      {drafts.length > 0 && <div className="mail-panel__drafts">
        <h3>Waiting for your approval</h3>
        {drafts.map(draft => <article key={draft.id}>
          <strong>To {draft.to.join(', ')}{draft.cc.length ? ` · cc ${draft.cc.join(', ')}` : ''}</strong>
          <small>{draft.subject}</small>
          <p>{draft.body}</p>
          {draft.error && <small className="mail-panel__warn">{draft.error}</small>}
          <div className="mail-panel__actions">
            <button type="button" disabled={disabled} onClick={() => void run(async () => {
              const sent = await api<Draft>('POST', `/api/email/drafts/${draft.id}/send`, {}, { desktop: true, timeoutMs: 120_000 });
              setNotice(sent.verified ? `Sent to ${sent.to.join(', ')}. Gmail shows it in Sent.` : `Sent to ${sent.to.join(', ')}, but Gmail hasn't shown it in Sent yet. Check before resending.`);
              await load(query, folder);
            })}>Approve and send</button>
            <button type="button" className="mail-panel__quiet" disabled={disabled} onClick={() => void run(async () => {
              await api('POST', `/api/email/drafts/${draft.id}/discard`); setNotice('Draft discarded.'); await load(query, folder);
            })}>Discard</button>
          </div>
        </article>)}
      </div>}

      <div className="mail-panel__folders" role="tablist" aria-label="Mail folders">
        {FOLDERS.map(item => <button key={item.id || 'all'} type="button" role="tab" aria-selected={!query.trim() && folder === item.id}
          className={!query.trim() && folder === item.id ? 'is-on' : ''} disabled={disabled}
          onClick={() => { setQuery(''); if (folder === item.id) void run(() => load('', item.id)); else setFolder(item.id); }}>
          {item.label}{item.count && sync?.unread?.[item.count] ? <span className="mail-panel__count">{sync.unread[item.count]}</span> : null}</button>)}
      </div>

      <form className="assistant-panel__form mail-panel__search" onSubmit={event => { event.preventDefault(); void run(() => load(query, folder)); }}>
        <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search all mail (sender, subject, words)" maxLength={300} disabled={disabled} aria-label="Search mail"/>
        <button type="submit" disabled={disabled}>Search</button>
        <button type="button" className="mail-panel__quiet" disabled={disabled || !sync?.connected} onClick={() => void run(async () => {
          await api('POST', '/api/email/sync', {}, { timeoutMs: 150_000 }); await load(query, folder); setNotice('Checked Gmail.');
        })}>Check now</button>
      </form>

      <div className="mail-panel__body">
        <ul className="mail-panel__list" aria-label="Emails">
          {list.map(mail => <li key={mail.id}>
            <button type="button" className={`${open?.message.id === mail.id ? 'is-open' : ''}${mail.labels.includes('UNREAD') ? ' is-unread' : ''}`} onClick={() => void openMail(mail.id)}>
              <span>{mail.fromName || mail.fromAddress}</span><time>{when(mail.internalDate)}</time>
              <strong>{mail.subject || '(no subject)'}</strong><small>{mail.snippet}</small>
            </button>
          </li>)}
          {!list.length && sync?.connected && <li className="assistant-panel__note">{query ? 'No matches in the mail copied so far.' : sync.complete ? 'Nothing here.' : 'Copying your mail to this PC… it shows up here as it arrives.'}</li>}
          {more && <li><button type="button" className="mail-panel__more" disabled={disabled} onClick={() => void loadMore()}>Show older mail</button></li>}
        </ul>

        <DetailScreen id="mail-thread" name="Mail" open={!!open} itemId={open?.message.id} title={open?.message.subject || "(no subject)"}
          onOpen={key => { const id = seenMail.current.get(key ?? ""); if (id) void openMail(id); }} onClose={() => { setOpen(null); clearPreview(); setReading(null); }}/>
        <DetailScreen id="mail-attachment" name="Attachment" open={!!(preview || reading)} title={preview?.name || reading?.name || "Attachment"}
          onOpen={() => { /* a closed preview is re-opened from its attachment button */ }} onClose={() => { clearPreview(); setReading(null); }}/>
        {open && <article className="mail-panel__reader">
          <header>
            <h3>{open.message.subject || '(no subject)'}</h3>
            <a href={open.message.link} target="_blank" rel="noreferrer">Open in Gmail</a>
          </header>
          {open.thread.map(mail => <div key={mail.id} className="mail-panel__message">
            <small><strong>{mail.fromName || mail.fromAddress}</strong> &lt;{mail.fromAddress}&gt; · {when(mail.internalDate)}</small>
            <pre>{mail.body}</pre>
          </div>)}
          {files.length > 0 && <div className="mail-panel__files">
            <h4>Attachments</h4>
            {files.map(file => <div key={`${file.index ?? 0}-${file.name}`} className="mail-panel__file">
              <span>{file.name}<small>{[file.type, size(file.size)].filter(Boolean).join(' · ')}</small></span>
              <div className="mail-panel__actions">
                {viewable(file.type) && <button type="button" className="mail-panel__quiet" disabled={disabled || file.index === undefined} onClick={() => void view(file)}>View</button>}
                <button type="button" className="mail-panel__quiet" disabled={disabled || file.index === undefined} onClick={() => void readFile(file)}>Read with ZAE</button>
                <button type="button" disabled={disabled || file.index === undefined} onClick={() => void saveFile(file)}>Download</button>
              </div>
            </div>)}
            {preview && <div className="mail-panel__preview">
              <header><strong>{preview.name}</strong><button type="button" className="mail-panel__quiet" onClick={clearPreview}>Close</button></header>
              {preview.text !== undefined ? <pre>{preview.text}</pre>
                : preview.type.startsWith('image/') ? <img src={preview.url} alt={preview.name}/>
                : <iframe src={preview.url} title={preview.name}/>}
            </div>}
            {reading && <div className="mail-panel__preview">
              <header><strong>ZAE read {reading.name}</strong><button type="button" className="mail-panel__quiet" onClick={() => setReading(null)}>Close</button></header>
              {reading.summary && <p>{reading.summary}</p>}
              <details><summary>Text from the {reading.kind}{reading.truncated ? ' (first part)' : ''}</summary><pre>{reading.text || '(no readable text)'}</pre></details>
            </div>}
          </div>}
          <form className="assistant-panel__form" onSubmit={event => { event.preventDefault(); void run(async () => {
            await api<Draft>('POST', '/api/email/drafts', { messageId: open.message.id, body: reply, replyAll });
            setReply(''); setNotice('Draft saved. Read it above, then press Approve and send.'); await load(query, folder);
          }); }}>
            <label>Reply<textarea value={reply} onChange={event => setReply(event.target.value)} rows={5} maxLength={20000} disabled={disabled} placeholder="Write a reply, or ask ZAE to draft one below."/></label>
            <div className="mail-panel__actions">
              <input value={note} onChange={event => setNote(event.target.value)} maxLength={1000} disabled={disabled} placeholder="Note for ZAE, e.g. say yes and ask what time" aria-label="Note for ZAE's draft"/>
              <button type="button" className="mail-panel__quiet" disabled={disabled} onClick={() => void run(async () => {
                const written = await api<{ body: string }>('POST', '/api/email/suggest', { messageId: open.message.id, note }, { timeoutMs: 150_000 });
                setReply(written.body); setNotice('ZAE drafted a reply. Edit it before saving.');
              })}>Let ZAE draft</button>
            </div>
            <label className="mail-panel__check"><input type="checkbox" checked={replyAll} onChange={event => setReplyAll(event.target.checked)} disabled={disabled}/> Reply to everyone</label>
            <button type="submit" disabled={disabled || !reply.trim()}>Save draft</button>
            {waitingFor.length > 0 && <small>{waitingFor.length} draft{waitingFor.length > 1 ? 's' : ''} for this email waiting for approval above.</small>}
          </form>
        </article>}
      </div>
    </section>
  );
}
