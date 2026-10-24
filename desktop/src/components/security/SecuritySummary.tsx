import { useEffect, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";
import "./SecurityPanel.css";

type Level = "strong" | "fair" | "weak" | "unknown";
type Summary = { level: Level; score: number; toImprove: number; lastCheck: { at: string; status: "pass" | "warn" | "fail" } | null };
const checkWord = { pass: "passed", warn: "passed with warnings", fail: "failed" } as const;

function ago(at: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(at).getTime()) / 60000));
  return minutes < 60 ? `${minutes} min ago` : minutes < 48 * 60 ? `${Math.round(minutes / 60)} h ago` : `${Math.round(minutes / 1440)} days ago`;
}

/** Status tab: ZAE's live security level only. Details stay on the locked Security tab. */
export function SecuritySummary({ onOpen }: { onOpen?: () => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!LIVE_API) return;
    let cancelled = false;
    const load = () => api<Summary>("GET", "/api/security/summary").then(next => { if (!cancelled) { setSummary(next); setFailed(false); } }, () => { if (!cancelled) setFailed(true); });
    void load();
    const id = window.setInterval(() => { if (!document.hidden) void load(); }, 60000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);
  if (!LIVE_API) return null;
  const angle = summary ? Math.max(0, Math.min(100, summary.score)) * 3.6 : 0;
  return <section className="sec-summary" aria-label="Security level">
    <div className={`sec-gauge sec-gauge--${summary?.level ?? "unknown"}`} style={{ background: `conic-gradient(var(--sec-level) ${angle}deg, rgba(116,144,185,.18) ${angle}deg)` }} aria-hidden="true">
      <div><strong>{summary ? summary.score : "—"}</strong></div>
    </div>
    <div>
      <strong>{summary ? `Security is ${summary.level}` : failed ? "Security level unavailable" : "Measuring security…"}</strong>
      <small>{summary ? `${summary.score}/100 live · ${summary.toImprove ? `${summary.toImprove} area${summary.toImprove === 1 ? "" : "s"} to improve` : "nothing to improve"} · `
        + (summary.lastCheck ? `last check ${checkWord[summary.lastCheck.status]} ${ago(summary.lastCheck.at)}` : "no check yet")
        : failed ? "The ZÆNIA server didn't answer." : "Live from the ZÆNIA server."} Details are on the Security tab.</small>
    </div>
    {onOpen && <button type="button" onClick={onOpen}>Open Security</button>}
  </section>;
}
