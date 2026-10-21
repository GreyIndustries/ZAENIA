import { useEffect, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";

type Monitor = { number: number; width: number; height: number; primary: number };
type Status = { watching: boolean; monitor: Monitor | null; paused: string | null; monitors: Monitor[]; notes: { at: string; text: string }[] };

/** Pick a monitor for ZAE to watch live, or stop. Voice works too: "watch my second monitor". */
export function ScreenWatchSettings() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!LIVE_API) return;
    let cancelled = false;
    const load = () => api<Status>("GET", "/api/screen/watch").then(next => { if (!cancelled) setStatus(next); }, () => undefined);
    void load();
    const id = window.setInterval(() => { if (!document.hidden) void load(); }, 6000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);
  const change = async (monitor: number | null) => {
    setBusy(true); setError(null);
    try { setStatus(await api<Status>("POST", "/api/screen/watch", monitor === null ? { on: false } : { on: true, monitor })); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Screen watching couldn't change."); }
    finally { setBusy(false); }
  };
  const watching = status?.watching ? status.monitor?.number : undefined;
  const latest = status?.notes.length ? status.notes[status.notes.length - 1] : null;
  return <div className="detail-panel__block appearance-settings" aria-label="Screen watch">
    <div className="section-heading"><span className="subheading">SCREEN WATCH</span><span>{watching ? `WATCHING MONITOR ${watching}` : "OFF"}</span></div>
    <h2>Live monitor</h2>
    <p>ZAE keeps an eye on one monitor so you can ask what's on it or about an error. Pictures stay in memory only and pause while a private window is in front. You can also say “watch my second monitor” or “stop watching my screen”.</p>
    {!LIVE_API ? <p>Available in the live app.</p> : <>
      <div className="mode-grid">
        {(status?.monitors ?? []).map(monitor => <button key={monitor.number} type="button" disabled={busy}
          className={watching === monitor.number ? "choice choice--active" : "choice"} aria-pressed={watching === monitor.number}
          onClick={() => void change(watching === monitor.number ? null : monitor.number)}>
          Monitor {monitor.number}{monitor.primary ? " (main)" : ""} · {monitor.width}×{monitor.height}
        </button>)}
      </div>
      {watching && <button type="button" className="choice appearance-settings__reset" disabled={busy} onClick={() => void change(null)}>Stop watching</button>}
      {status?.paused && <p>Paused: {status.paused}.</p>}
      {latest && <p><small>Last look ({new Date(latest.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}): {latest.text}</small></p>}
      {error && <p role="alert">{error}</p>}
    </>}
  </div>;
}
