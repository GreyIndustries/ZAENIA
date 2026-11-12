import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./SecurityChecks.css";
import { DetailScreen, detailKey } from "../shell/PageNavigator";

type CheckStatus = "pass" | "warn" | "fail";
type Check = { group: "tests" | "setup" | "activity"; id: string; title: string; status: CheckStatus; detail: string; fix: string };
type Summary = { id: string; at: string; trigger: "manual" | "daily"; status: CheckStatus; counts: Record<CheckStatus, number>; headline: string; seconds: number };
type Report = Summary & { checks: Check[] };
type State = { running: boolean; reports: Summary[]; latest: Report | null; retryAfter: number; error: string | null };

/** Fired by "run a security check" in chat so an open tab picks up the new run. */
export const SECURITY_CHECK_EVENT = "zaenia:security-check";

const groups: { id: Check["group"]; title: string }[] = [
  { id: "tests", title: "Isolated security tests" },
  { id: "setup", title: "Live setup" },
  { id: "activity", title: "Last 24 hours" },
];
const statusWord: Record<CheckStatus, string> = { pass: "PASSED", warn: "WARNINGS", fail: "FAILED" };
const when = (at: string) => new Date(at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

function ReportView({ report }: { report: Report }) {
  return <div className="security-checks__report">
    {groups.map(group => {
      const checks = report.checks.filter(check => check.group === group.id);
      if (!checks.length) return null;
      return <div key={group.id}>
        <h3>{group.title}</h3>
        <ul>{checks.map((check, index) => <li key={`${check.id}-${index}`} className={`security-checks__check security-checks__check--${check.status}`}>
          <span className="security-checks__mark" aria-label={check.status}>{check.status === "pass" ? "✓" : check.status === "warn" ? "!" : "✕"}</span>
          <div><strong>{check.title}</strong>{check.detail && <p>{check.detail}</p>}
            {check.fix && <p className="security-checks__fix"><span>Fix</span>{check.fix}</p>}</div>
        </li>)}</ul>
      </div>;
    })}
  </div>;
}

/** ZAE's security self-check: run one, see the latest result and every saved report. */
export function SecurityChecks() {
  const [state, setState] = useState<State | null>(null);
  const [open, setOpen] = useState<Report | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const load = useCallback(() => api<State>("GET", "/api/security/checks").then(setState, failure => setNote(errorText(failure))), []);
  useEffect(() => {
    if (!LIVE_API) return;
    void load();
    const refresh = () => void load();
    window.addEventListener(SECURITY_CHECK_EVENT, refresh);
    return () => window.removeEventListener(SECURITY_CHECK_EVENT, refresh);
  }, [load]);
  // While a check runs, look again every few seconds until its report is saved.
  useEffect(() => {
    if (!state?.running) return;
    const id = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(id);
  }, [state?.running, load]);
  // After the 10-minute wait, refresh so the button comes back.
  useEffect(() => {
    if (!state || state.running || state.retryAfter <= 0) return;
    const id = window.setTimeout(() => void load(), Math.min(state.retryAfter, 600) * 1000 + 500);
    return () => window.clearTimeout(id);
  }, [state, load]);

  async function run() {
    setStarting(true); setNote(null);
    try { setState(await api<State>("POST", "/api/security/checks")); setOpen(null); }
    catch (failure) { setNote(errorText(failure)); }
    finally { setStarting(false); }
  }
  async function view(id: string) {
    if (open?.id === id || state?.latest?.id === id) { setOpen(null); return; }  // the latest is always shown above
    try { setOpen(await api<Report>("GET", `/api/security/checks/${id}`)); }
    catch (failure) { setNote(errorText(failure)); }
  }

  if (!LIVE_API) return null;
  const latest = state?.latest ?? null;
  const running = state?.running || starting;
  return <section className="security-checks" aria-label="Security self-check" aria-busy={running}>
    <header className="security-checks__head">
      <div>
        <span className="security-checks__eyebrow">SECURITY SELF-CHECK</span>
        <h2>{running ? "Checking ZAE's security…" : latest ? latest.headline : state ? "No security check yet" : "Loading…"}</h2>
        <small>{running ? "Isolated tests and live-setup checks. This takes about half a minute."
          : latest ? `${latest.counts.pass} passed · ${latest.counts.warn} warnings · ${latest.counts.fail} failed · ${when(latest.at)} · ${latest.trigger === "daily" ? "daily check" : "run by you"}`
          : "Runs isolated security tests and checks the live setup without reading any secrets. Also runs once a day."}</small>
      </div>
      <div className="security-checks__actions">
        <button type="button" onClick={() => void run()} disabled={running || !state || state.retryAfter > 0}
          title={state && state.retryAfter > 0 ? `Available again in ${Math.ceil(state.retryAfter / 60)} min` : undefined}>
          {running ? "Running…" : state && state.retryAfter > 0 ? `Again in ${Math.ceil(state.retryAfter / 60)} min` : "Run security check"}</button>
      </div>
    </header>
    {note && <p className="security-checks__note" role="alert">{note}</p>}
    {state?.error && <p className="security-checks__note" role="alert">The last check stopped early ({state.error}).</p>}
    {latest && !running && <ReportView report={latest}/>}
    {state && state.reports.length > 0 && <>
      <h3 className="security-checks__history-title">Reports ({state.reports.length})</h3>
      <DetailScreen id="security-report" name="Security self-check" open={!!open} itemId={open?.id} title={open ? `Report · ${new Date(open.at).toLocaleString()}` : "Report"}
        onOpen={id => { const report = state.reports.find(entry => detailKey(entry.id) === id); if (report) void view(report.id); }} onClose={() => setOpen(null)}/>
      <ul className="security-checks__history">{state.reports.map(report => <li key={report.id}>
        <button type="button" aria-expanded={report.id === latest?.id || open?.id === report.id} onClick={() => void view(report.id)}>
          <span className={`security-checks__badge security-checks__badge--${report.status}`}>{statusWord[report.status]}</span>
          <strong>{when(report.at)}</strong>
          <small>{report.counts.pass}/{report.counts.pass + report.counts.warn + report.counts.fail} passed · {report.trigger === "daily" ? "daily" : "manual"}</small>
        </button>
        {open?.id === report.id && <ReportView report={open}/>}
      </li>)}</ul>
    </>}
  </section>;
}
