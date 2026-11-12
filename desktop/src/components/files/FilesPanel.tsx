import { useCallback, useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import { api, DESKTOP_APPROVER, errorText, LIVE_API, nearPassActive } from "../../core/bridge";
import "./FilesPanel.css";
import { DetailScreen, PageNavigator } from "../shell/PageNavigator";
/** The Files views are pages (Claude 2026-11-11). */
const FILE_PAGES = [{ id: "recent", label: "Recent" }, { id: "browse", label: "Browse" }, { id: "changes", label: "Changes" }];

type FileEntry = { path: string; name: string; kind: "file" | "dir"; size?: number; modified?: string; editable?: boolean };
type FileContent = FileEntry & { text: string; sha256: string; lineEnding: "crlf" | "lf"; protected: boolean };
type Proposal = {
  id: string; path: string; note: string; status: "pending" | "applied" | "rejected" | "stale"; createdAt: string;
  decidedAt: string | null; stats: { added: number; removed: number }; backup: string | null; from: string;
};
type ProposalDetail = Proposal & { diff: string; diffTruncated: boolean; baseMatches: boolean };
type View = "recent" | "browse" | "changes";

const ago = (value?: string | null) => {
  if (!value) return "";
  const seconds = (Date.now() - Date.parse(value)) / 1000;
  if (!Number.isFinite(seconds)) return "";
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  return new Date(value).toLocaleDateString([], { month: "short", day: "numeric" });
};
const size = (bytes?: number) => bytes === undefined ? "" : bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`;
const statusLabel: Record<Proposal["status"], string> = { pending: "Waiting for PC", applied: "Applied", rejected: "Rejected", stale: "Out of date" };

/**
 * System files: recent changes, browsing, viewing and editing ZÆNIA's own
 * code and config. The desktop app saves directly (with a backup). The phone
 * sends changes for approval in the desktop app.
 */
export function FilesPanel({ onPendingChange }: { onPendingChange?: (count: number) => void }) {
  const [view, setView] = useState<View>("recent");
  const [recent, setRecent] = useState<FileEntry[] | null>(null);
  const [dir, setDir] = useState("");
  const [listing, setListing] = useState<{ dir: string; parent: string | null; entries: FileEntry[] } | null>(null);
  const [proposals, setProposals] = useState<Proposal[] | null>(null);
  const [file, setFile] = useState<FileContent | null>(null);
  const [proposal, setProposal] = useState<ProposalDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [approver, setApprover] = useState<{ paired: boolean; approver: boolean } | null>(null);

  const run = useCallback(async <T,>(task: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true); setError(null);
    try { return await task(); }
    catch (failure) { setError(errorText(failure)); return undefined; }
    finally { setBusy(false); }
  }, []);

  const loadProposals = useCallback(async () => {
    const reply = await run(() => api<{ proposals: Proposal[] }>("GET", "/api/files/proposals"));
    if (reply) { setProposals(reply.proposals); onPendingChange?.(reply.proposals.filter(p => p.status === "pending").length); }
  }, [run, onPendingChange]);

  useEffect(() => {
    if (!LIVE_API) return;
    void run(() => api<{ files: FileEntry[] }>("GET", "/api/files/recent?limit=40")).then(reply => reply && setRecent(reply.files));
    void loadProposals();
    if (DESKTOP_APPROVER) {
      api<{ paired: boolean; approver: boolean }>("GET", "/api/desktop/check", undefined, { desktop: true })
        .then(setApprover).catch(() => setApprover({ paired: false, approver: false }));
    } else setApprover({ paired: false, approver: false });
  }, [run, loadProposals]);

  useEffect(() => {
    if (!LIVE_API || view !== "browse") return;
    void run(() => api<{ dir: string; parent: string | null; entries: FileEntry[] }>("GET", `/api/files/list?dir=${encodeURIComponent(dir)}`)).then(reply => reply && setListing(reply));
  }, [view, dir, run]);

  async function openFile(path: string) {
    const reply = await run(() => api<FileContent>("GET", `/api/files/content?path=${encodeURIComponent(path)}`));
    if (reply) { setFile(reply); setProposal(null); setEditing(false); setDraft(reply.text); setNote(""); setMessage(null); }
  }
  async function openProposal(id: string) {
    const reply = await run(() => api<ProposalDetail>("GET", `/api/files/proposals/${id}`));
    if (reply) { setProposal(reply); setFile(null); setEditing(false); setMessage(null); }
  }
  const canApply = DESKTOP_APPROVER && approver?.approver === true;
  // Phone confirms at the PC (code + voice) let this phone approve a waiting change, not edit files directly.
  const [phoneConfirms, setPhoneConfirms] = useState(nearPassActive);
  useEffect(() => { const update = () => setPhoneConfirms(nearPassActive()); window.addEventListener("zae:near-pass", update); return () => window.removeEventListener("zae:near-pass", update); }, []);

  async function save() {
    if (!file) return;
    if (canApply) {
      const reply = await run(() => api<{ backup: string | null; unchanged?: boolean }>("PUT", "/api/files/content", { path: file.path, baseSha256: file.sha256, text: draft }, { desktop: true }));
      if (reply) {
        await openFile(file.path);
        setMessage(reply.unchanged ? "No changes to save." : `Saved. The previous version is backed up in ${reply.backup}.`);
      }
    } else {
      const reply = await run(() => api<Proposal>("POST", "/api/files/proposals", { path: file.path, baseSha256: file.sha256, text: draft, note }));
      if (reply) {
        setEditing(false);
        await loadProposals();
        setView("changes");
        await openProposal(reply.id);
        setMessage("Sent for approval. It applies only after you approve it in the desktop app on the PC.");
      }
    }
  }
  async function decide(action: "approve" | "reject") {
    if (!proposal) return;
    const reply = await run(() => api<Proposal>("POST", `/api/files/proposals/${proposal.id}/${action}`, undefined, { desktop: action === "approve" }));
    await loadProposals();
    if (reply) {
      await openProposal(proposal.id);
      setMessage(action === "approve" ? `Applied to ${reply.path}. Backup: ${reply.backup}.` : "Change rejected. The file was not touched.");
    } else await openProposal(proposal.id);
  }

  if (!LIVE_API) {
    return <div className="section-content files-panel">
      <div className="section-content__tag">SYSTEM FILES <span>NEEDS THE ZÆNIA SERVER</span></div>
      <p className="files-panel__empty">Recent system files, browsing and editing work in the desktop app and the phone app.</p>
    </div>;
  }

  const pending = proposals?.filter(p => p.status === "pending").length ?? 0;
  const detailOpen = file !== null || proposal !== null;
  return <div className={`section-content files-panel${detailOpen ? " files-panel--detail" : ""}`}>
    <div className="section-content__tag">SYSTEM FILES <span>{canApply ? "DESKTOP · SAVES WITH BACKUP" : DESKTOP_APPROVER ? "DESKTOP · NOT PAIRED" : "PHONE · CHANGES NEED PC APPROVAL"}</span></div>
    {DESKTOP_APPROVER && approver && !approver.approver && <p className="files-panel__banner">
      To save and approve changes here, pair this desktop app once. At the PC run <code>python -m core.api.server pair-desktop</code> and enter your passkey.
    </p>}
    {error && <p className="files-panel__error" role="alert">{error}</p>}
    <div className="files-panel__layout">
      <nav className="files-panel__side" aria-label="Files">
        <PageNavigator id="files-view" name="Files" items={FILE_PAGES.map(item => item.id === "changes" && pending > 0 ? { ...item, label: `Changes (${pending})` } : item)} current={view} onChoose={next => setView(next as View)}/>
        <div className="files-panel__tabs" hidden>
        </div>
        {view === "recent" && <ul className="files-panel__list">
          {recent === null && <li className="files-panel__empty">Loading…</li>}
          {recent?.map(entry => <li key={entry.path}><button type="button" className={file?.path === entry.path ? "is-active" : ""} onClick={() => void openFile(entry.path)}>
            <strong>{entry.name}</strong><small>{entry.path}</small><em>{ago(entry.modified)}</em>
          </button></li>)}
        </ul>}
        {view === "browse" && <>
          <div className="files-panel__crumbs">
            <button type="button" onClick={() => setDir("")} disabled={!dir}>ZÆNIA</button>
            {dir && dir.split("/").map((part, index, parts) => <span key={index}>/<button type="button" onClick={() => setDir(parts.slice(0, index + 1).join("/"))} disabled={index === parts.length - 1}>{part}</button></span>)}
          </div>
          <ul className="files-panel__list">
            {listing?.entries.length === 0 && <li className="files-panel__empty">Empty folder.</li>}
            {listing?.entries.map(entry => <li key={entry.path}><button type="button" className={file?.path === entry.path ? "is-active" : ""}
              onClick={() => entry.kind === "dir" ? setDir(entry.path) : void openFile(entry.path)}>
              <strong>{entry.kind === "dir" ? `${entry.name}/` : entry.name}</strong>{entry.kind === "file" && <em>{size(entry.size)} · {ago(entry.modified)}</em>}
            </button></li>)}
          </ul>
        </>}
        {view === "changes" && <ul className="files-panel__list">
          {proposals?.length === 0 && <li className="files-panel__empty">No changes yet. Edits from the phone appear here for approval.</li>}
          {proposals?.map(item => <li key={item.id}><button type="button" className={proposal?.id === item.id ? "is-active" : ""} onClick={() => void openProposal(item.id)}>
            <strong>{item.path.split("/").pop()}</strong><small>{item.path}</small>
            <em><span className={`files-panel__status files-panel__status--${item.status}`}>{statusLabel[item.status]}</span> +{item.stats.added} −{item.stats.removed} · {ago(item.createdAt)}</em>
          </button></li>)}
        </ul>}
      </nav>

      <section className="files-panel__main" aria-live="polite">
        {!detailOpen && <p className="files-panel__empty">Choose a file to view or edit it{pending ? `, or open Changes to review ${pending} waiting change${pending > 1 ? "s" : ""}` : ""}.</p>}
        {message && <p className="files-panel__message" role="status">{message}</p>}

        <DetailScreen id="files-open" name="Files" open={!!(file || proposal)} title={file?.path?.split(/[\\/]/).pop() || (proposal ? "Proposed change" : "File")}
          onOpen={() => { /* reopened from the list */ }} onClose={() => { setFile(null); setProposal(null); setEditing(false); }}/>
        {file && <article className="files-panel__file">
          <header>
            <button type="button" className="files-panel__back" onClick={() => setFile(null)} aria-label="Back to the list">‹</button>
            <div><strong>{file.name}</strong><small>{file.path} · {size(file.size)} · {file.lineEnding.toUpperCase()}</small></div>
            {!editing && file.editable && <button type="button" className="files-panel__primary" onClick={() => { setEditing(true); setDraft(file.text); setMessage(null); }}>Edit</button>}
          </header>
          {file.protected && <p className="files-panel__note">Security code is read-only here. Edit it at the PC in your code editor.</p>}
          {!file.protected && !file.editable && <p className="files-panel__note">This file is too large to edit in the UI.</p>}
          {editing
            ? <>
              <textarea className="files-panel__editor" value={draft} spellCheck={false} autoCapitalize="off" autoCorrect="off"
                onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setDraft(event.target.value)} aria-label={`Edit ${file.path}`}/>
              {!canApply && <input className="files-panel__noteinput" placeholder="What does this change do? (optional)" value={note} maxLength={300}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setNote(event.target.value)} aria-label="Note for the change"/>}
              <div className="files-panel__actions">
                <button type="button" onClick={() => { setEditing(false); setDraft(file.text); }} disabled={busy}>Cancel</button>
                <button type="button" className="files-panel__primary" onClick={() => void save()} disabled={busy || draft === file.text}>
                  {busy ? "Working…" : canApply ? "Save (backup first)" : "Send for approval"}</button>
              </div>
              {!canApply && <p className="files-panel__note">Nothing changes until you approve it in the desktop app on the PC.</p>}
            </>
            : <pre className="files-panel__code"><code>{file.text}</code></pre>}
        </article>}

        {proposal && <article className="files-panel__file">
          <header>
            <button type="button" className="files-panel__back" onClick={() => setProposal(null)} aria-label="Back to the list">‹</button>
            <div><strong>{proposal.path}</strong><small>{statusLabel[proposal.status]} · from the {proposal.from} · {ago(proposal.createdAt)}{proposal.note ? ` · “${proposal.note}”` : ""}</small></div>
          </header>
          {proposal.status === "pending" && !proposal.baseMatches && <p className="files-panel__note">The file changed since this edit was made, so it can't be applied. Reject it and edit again.</p>}
          <pre className="files-panel__diff">{proposal.diff.split("\n").map((line, index) => <span key={index}
            className={line.startsWith("+") && !line.startsWith("+++") ? "is-add" : line.startsWith("-") && !line.startsWith("---") ? "is-del" : line.startsWith("@@") ? "is-hunk" : ""}>{line || " "}{"\n"}</span>)}</pre>
          {proposal.diffTruncated && <p className="files-panel__note">Long change: only the first part is shown.</p>}
          {proposal.status === "pending" && <div className="files-panel__actions">
            <button type="button" onClick={() => void decide("reject")} disabled={busy}>{canApply ? "Reject" : "Withdraw"}</button>
            {canApply || phoneConfirms
              ? <button type="button" className="files-panel__primary" onClick={() => void decide("approve")} disabled={busy || !proposal.baseMatches}>Approve and apply</button>
              : <span className="files-panel__note">Approve it in the desktop app on the PC, or turn on Phone confirms in PC remote.</span>}
          </div>}
          {proposal.backup && <p className="files-panel__note">Backup of the old version: {proposal.backup}</p>}
        </article>}
      </section>
    </div>
  </div>;
}
