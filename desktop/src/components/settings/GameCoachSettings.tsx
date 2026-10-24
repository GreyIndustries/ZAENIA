import { useEffect, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";

type Review = { game?: string; style?: string; decisions?: string[]; strengths?: string[]; mistakes?: string[]; tips?: string[] };
type Status = {
  enabled: boolean;
  session: { game: string; started: string; moments: number; latest: string | null } | null;
  games: { game: string; sessions: number; style: string | null }[];
  lastReview: Review | null;
};

/** Game coach: ZAE watches you play (game mode only) and learns your style. Voice: "watch me play" / "stop watching me play". */
export function GameCoachSettings() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!LIVE_API) return;
    let cancelled = false;
    const load = () => api<Status>("GET", "/api/gaming/coach").then(next => { if (!cancelled) setStatus(next); }, () => undefined);
    void load();
    const id = window.setInterval(() => { if (!document.hidden) void load(); }, 15000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);
  const toggle = async () => {
    if (!status) return;
    setBusy(true); setError(null);
    try { setStatus(await api<Status>("POST", "/api/gaming/coach", { on: !status.enabled })); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "The game coach couldn't change."); }
    finally { setBusy(false); }
  };
  const review = status?.lastReview;
  return <div className="detail-panel__block appearance-settings" aria-label="Game coach">
    <div className="section-heading"><span className="subheading">GAME COACH</span><span>{status?.session ? "WATCHING" : status?.enabled ? "ON" : "OFF"}</span></div>
    <h2>Watch me play</h2>
    <p>When a game is full screen, ZAE looks every 20 seconds, notes your decisions, and reviews your style when the game closes. She looks up the game and things on screen online (just the names, never the picture) and stays quiet unless you ask “how did I play?”.</p>
    {!LIVE_API ? <p>Available in the live app.</p> : <>
      <button type="button" className={status?.enabled ? "choice choice--active" : "choice"} disabled={busy || !status} aria-pressed={!!status?.enabled} onClick={() => void toggle()}>
        {status?.enabled ? "Coach on" : "Coach off"}
      </button>
      {status?.session && <p><small>Watching {status.session.game} · {status.session.moments} moments noted{status.session.latest ? `. Latest: ${status.session.latest}` : ""}</small></p>}
      {review?.style && <p><small><strong>Last review{review.game ? ` (${review.game})` : ""}:</strong> {review.style}{review.tips?.length ? ` Tip: ${review.tips[0]}` : ""}</small></p>}
      {!!status?.games.length && <p><small>Styles learned: {status.games.map(game => `${game.game} (${game.sessions})`).join(", ")}</small></p>}
      {error && <p role="alert">{error}</p>}
    </>}
  </div>;
}
