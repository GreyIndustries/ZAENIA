import { useEffect, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";

type Event = { at: string; label: string; operation: string; severity: "info" | "warn" };
type Activity = { events: Event[]; routineAllowed: number; since: string | null; summary: { label: string; count: number }[]; logBytes: number };

/** Read-only: notable security events from the audit log (denials, sign-ins, voice checks, memory changes). */
export function SecurityActivity() {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    if (!LIVE_API) return;
    let cancelled = false;
    const load = () => api<Activity>("GET", "/api/security/activity?limit=60").then(next => { if (!cancelled) setActivity(next); }, () => undefined);
    void load();
    const id = window.setInterval(() => { if (!document.hidden) void load(); }, 60000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);
  const warnings = activity?.events.filter(event => event.severity === "warn").length ?? 0;
  const shown = (activity?.events ?? []).slice(0, showAll ? 60 : 6);
  return <div className="detail-panel__block appearance-settings" aria-label="Security activity">
    <div className="section-heading"><span className="subheading">SECURITY ACTIVITY</span><span>{activity ? (warnings ? `${warnings} TO REVIEW` : "ALL CLEAR") : "—"}</span></div>
    <h2>What was allowed or blocked</h2>
    <p>Notable events from ZAE's audit log: denials, sign-ins, voice checks and memory changes. Routine allowed requests are only counted. Read-only.</p>
    {!LIVE_API ? <p>Available in the live app.</p> : !activity ? <p>Loading…</p> : <>
      <p><small>{activity.routineAllowed.toLocaleString()} routine requests allowed{activity.since ? ` since ${new Date(activity.since).toLocaleString()}` : ""}.</small></p>
      {!activity.events.length && <p>Nothing notable recently.</p>}
      <ul className="security-activity">{shown.map((event, index) => <li key={index} className={event.severity === "warn" ? "security-activity__warn" : undefined}>
        <strong>{event.label}</strong><small>{new Date(event.at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}{event.operation ? ` · ${event.operation}` : ""}</small>
      </li>)}</ul>
      {activity.events.length > 6 && <button type="button" className="choice appearance-settings__reset" onClick={() => setShowAll(v => !v)}>{showAll ? "Show fewer" : `Show all ${activity.events.length}`}</button>}
    </>}
  </div>;
}
