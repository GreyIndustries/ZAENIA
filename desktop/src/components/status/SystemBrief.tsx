import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./SystemBrief.css";

type BriefItem = { level: "attention" | "improve" | "info"; area: string; title: string; detail: string; fix: string; action?: string };
type Brief = { generatedAt: string; mode: string; headline: string; ready: string[]; items: BriefItem[]; counts: { attention: number; improve: number; ready: number }; spoken: string };
type Props = { voice?: { play: (key: string, text: string) => void; stop: () => void; playing: string | null; loading: string | null }; onFix?: (action: string) => void };

const groups: { level: BriefItem["level"]; title: string }[] = [
  { level: "attention", title: "Needs attention" },
  { level: "improve", title: "Improve next" },
  { level: "info", title: "Good to know" },
];

/** What's working, what needs attention and what to improve next for ZÆNIA. */
export function SystemBrief({ voice, onFix }: Props) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    if (!LIVE_API) return;
    setLoading(true); setError(null);
    try { setBrief(await api<Brief>("GET", "/api/system/brief")); }
    catch (failure) { setError(errorText(failure)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (!LIVE_API) return null;
  const speaking = voice?.playing === "system-brief";
  return <section className="system-brief" aria-label="System brief" aria-busy={loading}>
    <header className="system-brief__head">
      <div>
        <span className="system-brief__eyebrow">SYSTEM BRIEF</span>
        <h2>{brief ? brief.headline : loading ? "Checking ZÆNIA…" : "System brief unavailable"}</h2>
        {brief && <small>{brief.counts.ready} ready · {brief.counts.attention} need attention · {brief.counts.improve} to improve · checked {new Date(brief.generatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</small>}
      </div>
      <div className="system-brief__actions">
        {voice && brief && <button type="button" onClick={() => speaking ? voice.stop() : voice.play("system-brief", brief.spoken)} disabled={voice.loading !== null && voice.loading !== "system-brief"}>
          {voice.loading === "system-brief" ? "Preparing…" : speaking ? "■ Stop" : "▶ Speak brief"}</button>}
        <button type="button" onClick={() => void load()} disabled={loading}>{loading ? "Checking…" : "Refresh"}</button>
      </div>
    </header>
    {error && <p className="system-brief__error" role="alert">{error}</p>}
    {brief && groups.map(group => {
      const items = brief.items.filter(item => item.level === group.level);
      if (!items.length) return null;
      return <div key={group.level} className={`system-brief__group system-brief__group--${group.level}`}>
        <h3>{group.title}</h3>
        <ul>{items.map((item, index) => <li key={`${item.area}-${index}`}>
          <strong>{item.title}</strong>
          {item.detail && <p>{item.detail}</p>}
          {item.fix && <p className="system-brief__fix"><span>Fix</span>{item.fix}</p>}
          {item.action && onFix && <button type="button" className="system-brief__fixit" onClick={() => onFix(item.action!)}>Fix it</button>}
        </li>)}</ul>
      </div>;
    })}
    {brief && brief.ready.length > 0 && <p className="system-brief__ready"><span>Working:</span> {brief.ready.join(" · ")}</p>}
  </section>;
}
