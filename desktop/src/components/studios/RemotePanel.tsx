import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./MainViews.css";
import "./RemotePanel.css";
import { NearPassCard } from "./NearPassCard";

/**
 * Phone as a remote for the PC (Grey, 2026-10-30). The phone queues a screen command; the desktop app on the PC
 * collects it within a couple of seconds and carries out only screen commands (open, close or minimise a tab,
 * Calm view). Saving files, launching programs and approvals stay on the PC.
 */
export type RemoteTab = { id: string; label: string };
type PcWindow = { id: string; title: string; minimized: boolean };
type PcState = { online: boolean; lastSeenSeconds: number | null; windows: PcWindow[]; active: string | null; calm: boolean; section: string; pending: number };

export function RemotePanel({ tabs }: { tabs: RemoteTab[] }) {
  const [pc, setPc] = useState<PcState | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const refresh = useCallback(() => {
    if (!LIVE_API) return;
    api<PcState>("GET", "/api/remote/state").then(state => { setPc(state); setError(null); }, failure => setError(errorText(failure)));
  }, []);
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 3000); return () => window.clearInterval(timer); }, [refresh]);
  const send = async (action: string, target = "", done = "Sent to the PC.") => {
    const key = `${action}:${target}`;
    setBusy(key); setNote(null); setError(null);
    try {
      const reply = await api<{ pcOnline: boolean }>("POST", "/api/remote/commands", { action, target });
      setNote(reply.pcOnline ? done : "Queued. The PC app isn't connected right now, so it runs if the app opens within two minutes.");
      window.setTimeout(refresh, 1800);
    } catch (failure) { setError(errorText(failure)); }
    finally { setBusy(null); }
  };
  if (!LIVE_API) return <p className="mv-muted">The remote needs the ZÆNIA server: open it from your phone app.</p>;
  const label = (id: string) => tabs.find(tab => tab.id === id)?.label ?? id;
  const open = pc?.windows ?? [];
  const closed = tabs.filter(tab => !open.some(win => win.id === tab.id));
  return <div className="remote">
    <section className="zx-card remote__pc">
      <span className={`remote__dot ${pc?.online ? "remote__dot--on" : ""}`} aria-hidden="true"/>
      <div>
        <p className="mv-kicker">Your PC</p>
        <b className="zx-title">{pc === null ? "Checking…" : pc.online ? pc.calm ? "In Calm view" : `On ${label(pc.active ?? pc.section ?? "overview")}` : "App not connected"}</b>
        <p className="mv-muted">{pc?.online ? `${open.filter(win => !win.minimized).length} tab${open.filter(win => !win.minimized).length === 1 ? "" : "s"} open, ${open.filter(win => win.minimized).length} minimised` : pc?.lastSeenSeconds ? `Last seen ${Math.round(pc.lastSeenSeconds / 60)} min ago` : "Open ZÆNIA on the PC to use the remote."}</p>
      </div>
    </section>
    <div className="remote__big">
      <button type="button" className="zx-inset" disabled={busy !== null} onClick={() => void send(pc?.calm ? "wake" : "calm", "", pc?.calm ? "Waking the PC." : "Calm view on the PC.")}>
        <span aria-hidden="true">{pc?.calm ? "☀" : "☾"}</span>{pc?.calm ? "Wake the PC" : "Calm view"}</button>
      <button type="button" className="zx-inset" disabled={busy !== null} onClick={() => void send("show_desktop", "", "Showing the dashboard.")}>
        <span aria-hidden="true">◎</span>Dashboard</button>
      <button type="button" className="zx-inset" disabled={busy !== null || !open.some(win => win.minimized)} onClick={() => void send("restore_all", "", "Bringing tabs back.")}>
        <span aria-hidden="true">⧉</span>Restore all</button>
    </div>
    <NearPassCard/>
    {note && <p className="mv-note" role="status">{note}</p>}
    {error && <p className="mv-error" role="alert">{error}</p>}
    <section className="zx-card">
      <p className="mv-kicker">Open on the PC</p>
      {open.length === 0 ? <p className="mv-muted">No tabs open.</p> : <ul className="remote__list">
        {open.map(win => <li key={win.id} className={`zx-inset ${win.id === pc?.active ? "remote__item--active" : ""}`}>
          <span>{label(win.id)}{win.minimized && <em> · minimised</em>}</span>
          <span className="remote__actions">
            <button type="button" disabled={busy !== null} onClick={() => void send("open", win.id, `Showing ${label(win.id)}.`)}>Show</button>
            {!win.minimized && <button type="button" disabled={busy !== null} onClick={() => void send("minimize", win.id, `Minimised ${label(win.id)}.`)}>Hide</button>}
            <button type="button" disabled={busy !== null} onClick={() => void send("close", win.id, `Closed ${label(win.id)}.`)} aria-label={`Close ${label(win.id)}`}>✕</button>
          </span>
        </li>)}
      </ul>}
    </section>
    <section className="zx-card">
      <p className="mv-kicker">Open a tab on the PC</p>
      <div className="remote__grid">
        {closed.map(tab => <button key={tab.id} type="button" className="zx-inset" disabled={busy !== null} onClick={() => void send("open", tab.id, `Opening ${tab.label}.`)}>{tab.label}</button>)}
      </div>
    </section>
    <p className="mv-muted">The remote only moves tabs and screens. Approving from the phone needs Phone confirms above; Security, the Vault and settings stay at the PC.</p>
  </div>;
}
