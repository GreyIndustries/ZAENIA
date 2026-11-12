import { useCallback, useEffect, useState } from "react";
import { api, installUpdate, IN_TAURI } from "../../core/bridge";
import built from "../../config/versions.json";
import { ReleaseNotes } from "./ReleaseNotes";
import type { ReleaseNote } from "./ReleaseNotes";
import "./SettingsHub.css";

/**
 * Settings > Updates (Grey, 2026-11-09): updates are staged (scripts/stage_update.ps1) and Grey installs
 * them here. Install backs up the app and phone site, closes and reopens ZAE, and can restart the server.
 */
export type VersionItem = { name: string; version: string; note?: string; job?: string; model?: string };
export type VersionFile = {
  scheme?: string; system?: VersionItem; ui?: VersionItem;
  tabs?: Record<string, VersionItem>; modules?: Record<string, VersionItem>; nodes?: Record<string, VersionItem>;
  history?: { version: string; part: string; date: string; title: string; changes?: string[]; releaseNotes?: ReleaseNote[] }[];
};
type Pending = { releaseNotes?: ReleaseNote[]; id: string; title?: string; notes?: string[]; part?: string; version?: string; createdAt?: string;
  restartServer?: boolean; ready?: boolean; stale?: boolean; versions?: { system?: string; ui?: string }; builtFrom?: { commit?: string; uncommittedChanges?: boolean } };
type Installed = { releaseNotes?: ReleaseNote[]; id: string; title?: string; notes?: string[]; part?: string; version?: string; installedAt?: string; restartedServer?: boolean };
export type UpdatesData = { running?: VersionFile; pending?: Pending[]; installed?: Installed[];
  lastInstall?: { id: string; status: "running" | "ok" | "failed"; message: string; at: string } | null };

export const BUILT_VERSIONS = built as VersionFile;
export const partLabel = (part?: string) => !part ? "" : part === "ui" ? "Interface" : part === "system" ? "System"
  : part.startsWith("tab:") ? `${BUILT_VERSIONS.tabs?.[part.slice(4)]?.name ?? part.slice(4)} tab` : part;
const day = (iso?: string) => { if (!iso) return ""; const date = new Date(iso.length === 10 ? `${iso}T12:00` : iso); return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }); };

export function useUpdates() {
  const [data, setData] = useState<UpdatesData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setData(await api<UpdatesData>("GET", "/api/updates")); setError(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Couldn't read updates from the ZAE server."); }
  }, []);
  useEffect(() => { void load(); const timer=window.setInterval(() => { if(document.visibilityState === "visible") void load(); }, 5000); return () => window.clearInterval(timer); }, [load]);
  return { data, error, load };
}

export function UpdatesPanel() {
  const { data, error, load } = useUpdates();
  const [restart, setRestart] = useState<Record<string, boolean>>({});
  const [confirm, setConfirm] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const running = data?.lastInstall?.status === "running";
  useEffect(() => { if (!running) return; const timer = window.setInterval(() => void load(), 4000); return () => window.clearInterval(timer); }, [running, load]);

  const install = async (item: Pending) => {
    if (confirm !== item.id) { setConfirm(item.id); return; }
    setConfirm(null); setNote("Installing. ZAE will close and reopen in a moment.");
    try { await installUpdate(item.id, restart[item.id] ?? Boolean(item.restartServer)); }
    catch (reason) { setNote(reason instanceof Error ? reason.message : "The install could not start."); }
  };

  const serverSystem = data?.running?.system?.version;
  const history = [...(BUILT_VERSIONS.history ?? [])];
  for (const entry of data?.running?.history ?? []) if (!history.some(h => h.version === entry.version && h.part === entry.part)) history.push(entry);
  history.sort((a, b) => b.date.localeCompare(a.date));

  return <div className="zu">
    <section className="zu-card">
      <p className="zu-kicker">Current version</p>
      <div className="zu-versions">
        <div><small>ZAENIA system</small><b>{serverSystem ?? BUILT_VERSIONS.system?.version}</b><small>capabilities and security</small></div>
        <div><small>Interface</small><b>{BUILT_VERSIONS.ui?.version}</b><small>this app's screens</small></div>
        <div><small>Settings tab</small><b>{BUILT_VERSIONS.tabs?.settings?.version}</b><small>each tab has its own</small></div>
      </div>
      <p className="zu-muted">Beta: everything stays below 1.0 until ZAE needs updates far less often. Every version is listed in About.</p>
    </section>

    {data?.lastInstall && <div className={`zu-banner zu-banner--${data.lastInstall.status}`} role="status">
      {data.lastInstall.status === "running" ? "Installing…" : data.lastInstall.message} <span className="zu-muted">· {day(data.lastInstall.at)}</span></div>}
    {note && <div className="zu-banner zu-banner--running" role="status">{note}</div>}

    <section className="zu-card">
      <p className="zu-kicker">Waiting to install</p>
      {error && <p className="zu-muted">{error}</p>}
      {!error && !data && <p className="zu-muted">Checking…</p>}
      {data && !data.pending?.some(item => !item.stale) && <p className="zu-muted">Nothing waiting. New updates show up here for you to install.</p>}
      {data?.pending?.filter(item => !item.stale).map(item => <div key={item.id} className="zu-update">
        <h3>{item.title ?? item.id}<span className="zu-tag">{partLabel(item.part)} {item.version}</span></h3>
        <p className="zu-muted">Built {day(item.createdAt)}{item.versions ? ` · system ${item.versions.system} · interface ${item.versions.ui}` : ""}</p>
        <ReleaseNotes entries={item.releaseNotes} fallback={item.notes}/>
        <div className="zu-actions">
          <label><input type="checkbox" checked={restart[item.id] ?? Boolean(item.restartServer)} onChange={event => setRestart(current => ({ ...current, [item.id]: event.target.checked }))}/>
            Restart the server too{item.restartServer ? " (recommended for this update)" : " (optional)"}</label>
          {IN_TAURI
            ? <button type="button" className="zu-btn" disabled={!item.ready || running} onClick={() => void install(item)}>
                {confirm === item.id ? "Install now: ZAE closes and reopens (unsaved notes are lost)" : "Install"}</button>
            : <span className="zu-muted">Install from the desktop app on your PC.</span>}
          {confirm === item.id && <button type="button" className="zu-btn zu-btn--quiet" onClick={() => setConfirm(null)}>Cancel</button>}
        </div>
        {!item.ready && <p className="zu-muted">This update is missing files and can't be installed.</p>}
        {(restart[item.id] ?? item.restartServer) && <p className="zu-muted">A restart starts the server in token mode, so owner features stay locked until you start it with your passkey.</p>}
      </div>)}
    </section>

    {data?.installed?.[0] && <section className="zu-card"><h3>What’s new in {data.installed[0].version}</h3><ReleaseNotes entries={data.installed[0].releaseNotes} fallback={data.installed[0].notes}/></section>}
    <section className="zu-card">
      <p className="zu-kicker">Past updates</p>
      <div className="zu-history">
        {data?.installed?.map(item => <article key={item.id}><b>{item.title ?? item.id}</b><span className="zu-tag">{partLabel(item.part)} {item.version}</span>
          <p className="zu-muted">Installed {day(item.installedAt)}{item.restartedServer ? " · server restarted" : ""}</p>
          <ReleaseNotes entries={item.releaseNotes} fallback={item.notes}/></article>)}
        {history.map(item => <article key={`${item.part}-${item.version}`}><b>{item.title}</b><span className="zu-tag">{partLabel(item.part)} {item.version}</span>
          <p className="zu-muted">{day(item.date)}</p>
          <ReleaseNotes entries={item.releaseNotes} fallback={item.changes}/></article>)}
      </div>
    </section>
  </div>;
}
