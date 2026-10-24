import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, IN_TAURI, LIVE_API, openSecurityTool, type SecurityTool } from "../../core/bridge";
import { SecurityChecks } from "../status/SecurityChecks";
import "./SecurityPanel.css";

type Level = "strong" | "fair" | "weak" | "unknown";
type Area = { id: string; title: string; level: Level; evidence: string[]; risk: string; fix: string; attack: string };
type Posture = { at: string; score: number; level: Level; counts: Record<Level, number>; areas: Area[] };
type Recommendation = { priority: "high" | "medium" | "low"; title: string; why: string; fix: string };
type Improvements = { trend: { id: string; at: string; status: "pass" | "warn" | "fail"; counts: Record<"pass" | "warn" | "fail", number>; score: number | null }[];
  fixed: string[]; broke: string[]; stronger: string[]; weaker: string[]; since: string | null };
type ActivityEvent = { at: string; label: string; operation: string; severity: "info" | "warn" };
type Activity = { events: ActivityEvent[]; routineAllowed: number; since: string | null; summary: { label: string; count: number }[]; logBytes: number };
type Session = { method: "passkey" | "voice"; unlocked: number; idleLeft: number };
type Full = { posture: Posture; recommendations: Recommendation[]; improvements: Improvements; activity: Activity; session: Session };

const IDLE_SECONDS = 600;
const PING_EVERY = 45_000;   // at most one activity ping per 45 s
const REFRESH_EVERY = 30_000; // live readings
const levelWord: Record<Level, string> = { strong: "STRONG", fair: "FAIR", weak: "WEAK", unknown: "NOT MEASURED" };
const when = (at: string) => new Date(at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

// The unlock session lives only in this app's memory (never saved), so reopening
// the window within the idle time stays unlocked; the server enforces the timer.
let heldSession: string | null = null;

const ACTIONS: { mode: SecurityTool; title: string; note: string; danger?: boolean }[] = [
  { mode: "token_rotate", title: "Rotate API token", note: "New token for the phone; the old one stops working." },
  { mode: "token_revoke", title: "Revoke API token", note: "Signs out every phone and client using it.", danger: true },
  { mode: "pair_desktop", title: "Re-pair this desktop", note: "Replaces the desktop approval key." },
  { mode: "phrase_setup", title: "Set up spoken phrase", note: "Say your new phrase twice." },
  { mode: "phrase_reset", title: "Remove spoken phrase", note: "Turns off phrase unlocking until you set one up.", danger: true },
  { mode: "mic_change", title: "Change approved mic", note: "Pick the only microphone voice checks may use." },
  { mode: "mic_reset", title: "Remove approved mic", note: "Voice checks stop until you pick one.", danger: true },
  { mode: "phone_voice_on", title: "Turn on voice check", note: "Needed for phrase unlocking and phone voice sign-in." },
  { mode: "phone_voice_off", title: "Turn off voice check", note: "Signs out phones signed in by voice.", danger: true },
];

function Gauge({ score, level }: { score: number; level: Level }) {
  const angle = Math.max(0, Math.min(100, score)) * 3.6;
  return <div className={`sec-gauge sec-gauge--${level}`} style={{ background: `conic-gradient(var(--sec-level) ${angle}deg, var(--sec-track) ${angle}deg)` }}
    role="img" aria-label={`Security strength ${score} out of 100, ${levelWord[level].toLowerCase()}`}>
    <div><strong>{score}</strong><small>/ 100</small></div>
  </div>;
}

function Locked({ onUnlocked }: { onUnlocked: (session: string) => void }) {
  const [waiting, setWaiting] = useState<"passkey" | "voice" | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const request = useRef<string | null>(null);

  useEffect(() => {
    if (!waiting) return;
    const id = window.setInterval(() => {
      const current = request.current;
      if (!current) return;
      api<{ status: string; session?: string }>("GET", `/api/security/unlock/${current}`).then(result => {
        if (result.status === "unlocked" && result.session) { request.current = null; setWaiting(null); onUnlocked(result.session); }
        else if (result.status === "expired") { request.current = null; setWaiting(null); setNote("The unlock window timed out. Try again."); }
      }, failure => { request.current = null; setWaiting(null); setNote(errorText(failure)); });
    }, 1500);
    return () => window.clearInterval(id);
  }, [waiting, onUnlocked]);

  async function start(method: "passkey" | "voice") {
    setNote(null);
    try {
      const begun = await api<{ request: string }>("POST", "/api/security/unlock");
      request.current = begun.request;
      await openSecurityTool(method === "passkey" ? "unlock_passkey" : "unlock_voice", begun.request);
      setWaiting(method);
    } catch (failure) { request.current = null; setNote(errorText(failure)); }
  }

  return <section className="sec-locked" aria-label="Security tab locked">
    <svg viewBox="0 0 24 24" width="54" height="54" aria-hidden="true"><path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6Z"/><rect x="9" y="11" width="6" height="5" rx="1"/><path d="M10 11V9.5a2 2 0 0 1 4 0V11"/></svg>
    <h2>Security is locked</h2>
    <p>Unlock with your passkey or your spoken phrase. A window opens on this PC; the passkey and phrase are never typed into the app.
      Your phrase only works if your voice matches too. The tab locks again after 10 minutes without activity.</p>
    {!IN_TAURI ? <p className="sec-note">The Security tab opens only in the ZÆNIA desktop app on the PC.</p> : waiting
      ? <p className="sec-note" role="status">{waiting === "passkey" ? "Type your passkey in the ZAENIA - Security window." : "Say your security phrase in the ZAENIA - Security window."} Waiting…
          <button type="button" className="choice" onClick={() => { request.current = null; setWaiting(null); }}>Cancel</button></p>
      : <div className="sec-locked__actions">
          <button type="button" onClick={() => void start("passkey")}><strong>Unlock with passkey</strong><small>Typed in the PC window</small></button>
          <button type="button" onClick={() => void start("voice")}><strong>Unlock with spoken phrase</strong><small>Phrase and your voice are both checked</small></button>
        </div>}
    {note && <p className="sec-note sec-note--error" role="alert">{note}</p>}
  </section>;
}

function AreaCard({ area }: { area: Area }) {
  return <article className={`sec-area sec-area--${area.level}`}>
    <header><div><strong>{area.title}</strong>{area.attack && <small>Defends against: {area.attack}</small>}</div><span className="sec-badge">{levelWord[area.level]}</span></header>
    <ul>{area.evidence.map((line, index) => <li key={index}>{line}</li>)}</ul>
    {area.risk && <p className="sec-area__risk"><span>Weak spot</span>{area.risk}</p>}
    {area.fix && <p className="sec-area__fix"><span>Fix</span>{area.fix}</p>}
  </article>;
}

function ImprovementsView({ data }: { data: Improvements }) {
  const points = data.trend.slice(-14);
  const value = (point: Improvements["trend"][number]) => point.score ?? Math.round(100 * point.counts.pass / Math.max(1, point.counts.pass + point.counts.warn + point.counts.fail));
  const changes = [
    ...data.stronger.map(title => ({ kind: "up", text: `${title} got stronger` })),
    ...data.fixed.map(title => ({ kind: "up", text: `${title} now passes` })),
    ...data.weaker.map(title => ({ kind: "down", text: `${title} got weaker` })),
    ...data.broke.map(title => ({ kind: "down", text: `${title} now fails or warns` })),
  ];
  return <section className="sec-block" aria-label="Security improvements">
    <h3>Improvements</h3>
    {points.length < 2 ? <p className="sec-muted">Improvements show once there are two security checks to compare. {points.length ? "One check so far." : "No checks yet."}</p> : <>
      <div className="sec-trend" role="img" aria-label={`Strength over the last ${points.length} checks`}>
        {points.map(point => <div key={point.id} className={`sec-trend__bar sec-trend__bar--${point.status}`} style={{ height: `${Math.max(6, value(point))}%` }}
          title={`${when(point.at)}: ${point.score !== null ? `strength ${point.score}/100` : `${point.counts.pass} checks passed`}`}/>)}
      </div>
      <p className="sec-muted">{points[0].score !== null || points[points.length - 1].score !== null ? "Bar height: strength score (older checks: share of checks passed)." : "Bar height: share of checks passed."} Oldest left, newest right.</p>
      <h4>Since the check on {data.since ? when(data.since) : "—"}</h4>
      {changes.length ? <ul className="sec-changes">{changes.map((change, index) => <li key={index} className={`sec-changes__${change.kind}`}>{change.kind === "up" ? "▲" : "▼"} {change.text}</li>)}</ul>
        : <p className="sec-muted">No change between the last two checks.</p>}
    </>}
  </section>;
}

function ActivityView({ activity }: { activity: Activity }) {
  const [filter, setFilter] = useState<"all" | "warn">("all");
  const [query, setQuery] = useState("");
  const [count, setCount] = useState(25);
  const words = query.trim().toLowerCase();
  const events = activity.events.filter(event => (filter === "all" || event.severity === "warn")
    && (!words || `${event.label} ${event.operation}`.toLowerCase().includes(words)));
  return <section className="sec-block" aria-label="Full security activity">
    <h3>Activity log</h3>
    <p className="sec-muted">{activity.routineAllowed.toLocaleString()} routine requests allowed{activity.since ? ` since ${when(activity.since)}` : ""} · log {(activity.logBytes / 1024 ** 2).toFixed(1)} MB.
      {activity.summary.length > 0 && ` Most frequent: ${activity.summary.slice(0, 4).map(item => `${item.label} (${item.count})`).join(", ")}.`}</p>
    <div className="sec-filter">
      <button type="button" className={filter === "all" ? "choice choice--active" : "choice"} onClick={() => setFilter("all")}>All ({activity.events.length})</button>
      <button type="button" className={filter === "warn" ? "choice choice--active" : "choice"} onClick={() => setFilter("warn")}>To review ({activity.events.filter(event => event.severity === "warn").length})</button>
      <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search events" aria-label="Search security events"/>
    </div>
    {!events.length ? <p className="sec-muted">Nothing matches.</p> : <ul className="sec-activity">{events.slice(0, count).map((event, index) =>
      <li key={index} className={event.severity === "warn" ? "sec-activity__warn" : undefined}><strong>{event.label}</strong><small>{when(event.at)}{event.operation ? ` · ${event.operation}` : ""}</small></li>)}</ul>}
    {events.length > count && <button type="button" className="choice" onClick={() => setCount(value => value + 50)}>Show more ({events.length - count} left)</button>}
  </section>;
}

/** The locked Security tab: live strength, weak spots, fixes, improvements, checks, the full log and owner actions. */
export function SecurityPanel() {
  const [session, setSession] = useState<string | null>(heldSession);
  const [full, setFull] = useState<Full | null>(null);
  const [idleLeft, setIdleLeft] = useState(IDLE_SECONDS);
  const [note, setNote] = useState<string | null>(null);
  const lastPing = useRef(0);
  const expiresAt = useRef(Date.now() + IDLE_SECONDS * 1000);  // corrected by every server reply
  const sync = (left: number) => { expiresAt.current = Date.now() + left * 1000; setIdleLeft(left); };
  const panel = useRef<HTMLDivElement>(null);

  const lock = useCallback((message?: string) => {
    const current = heldSession;
    heldSession = null;
    setSession(null); setFull(null);
    if (message) setNote(message);
    if (current) void api("POST", "/api/security/session/lock", { session: current }).catch(() => undefined);
  }, []);
  const unlocked = useCallback((next: string) => {
    heldSession = next; lastPing.current = Date.now();
    setNote(null); sync(IDLE_SECONDS); setSession(next);
  }, []);

  const load = useCallback(() => {
    if (!heldSession) return;
    api<Full>("POST", "/api/security/full", { session: heldSession }).then(next => { setFull(next); sync(next.session.idleLeft); },
      failure => { const text = errorText(failure); if (/locked|401/i.test(text)) lock("The Security tab locked after 10 minutes without activity."); else setNote(text); });
  }, [lock]);

  useEffect(() => {
    if (!session) return;
    load();
    const id = window.setInterval(() => { if (!document.hidden) load(); }, REFRESH_EVERY);
    return () => window.clearInterval(id);
  }, [session, load]);

  // Activity on the tab (pointer, keys, scrolling) restarts the server's 10-minute idle timer.
  useEffect(() => {
    if (!session) return;
    const element = panel.current;
    const mark = () => {
      if (Date.now() - lastPing.current < PING_EVERY || !heldSession) return;
      lastPing.current = Date.now();
      api<Session>("POST", "/api/security/session", { session: heldSession }).then(next => sync(next.idleLeft),
        () => lock("The Security tab locked after 10 minutes without activity."));
    };
    const events = ["pointerdown", "pointermove", "keydown", "wheel", "scroll"] as const;
    events.forEach(name => element?.addEventListener(name, mark, { passive: true, capture: true }));
    const tick = window.setInterval(() => {
      const left = Math.max(0, Math.round((expiresAt.current - Date.now()) / 1000));
      setIdleLeft(left);
      if (left <= 0) lock("The Security tab locked after 10 minutes without activity.");
    }, 1000);
    return () => { events.forEach(name => element?.removeEventListener(name, mark, { capture: true })); window.clearInterval(tick); };
  }, [session, lock]);

  async function action(mode: SecurityTool) {
    setNote(null);
    try { await openSecurityTool(mode); setNote("Opened the ZAENIA - Security window on this PC. Each change asks for your passkey there."); }
    catch (failure) { setNote(errorText(failure)); }
  }

  if (!LIVE_API) return <p className="sec-muted">The Security tab needs the live ZÆNIA server.</p>;
  if (!session) return <div className="sec-panel"><Locked onUnlocked={unlocked}/>{note && <p className="sec-note" role="status">{note}</p>}</div>;
  const posture = full?.posture;
  const minutes = Math.ceil(idleLeft / 60);
  return <div className="sec-panel" ref={panel}>
    <div className="sec-sessionbar" role="status">
      <span>Unlocked with {full?.session.method === "voice" ? "your phrase and voice" : "your passkey"} · locks after {minutes} min without activity</span>
      <button type="button" className="choice" onClick={() => lock()}>Lock now</button>
    </div>
    {note && <p className="sec-note" role="status">{note}</p>}
    {!posture ? <p className="sec-muted">Measuring ZAE's security…</p> : <>
      <section className="sec-hero" aria-label="Live security strength">
        <Gauge score={posture.score} level={posture.level}/>
        <div>
          <span className="sec-eyebrow">LIVE ATTACK RESISTANCE</span>
          <h2>Security is {levelWord[posture.level].toLowerCase()}</h2>
          <p>{posture.counts.strong} strong · {posture.counts.fair} fair · {posture.counts.weak} weak{posture.counts.unknown ? ` · ${posture.counts.unknown} not measured` : ""}. Measured live {when(posture.at)}, refreshed every 30 seconds.</p>
          <small>A self-assessment of ZAE's own defenses from live readings on this PC, not a penetration test.</small>
        </div>
      </section>
      <section className="sec-block" aria-label="Defenses and vulnerabilities">
        <h3>Defenses and weak spots</h3>
        <div className="sec-areas">{[...posture.areas].sort((a, b) => ["weak", "fair", "unknown", "strong"].indexOf(a.level) - ["weak", "fair", "unknown", "strong"].indexOf(b.level))
          .map(area => <AreaCard key={area.id} area={area}/>)}</div>
      </section>
      <section className="sec-block" aria-label="Recommendations">
        <h3>Recommendations</h3>
        {!full.recommendations.length ? <p className="sec-muted">Nothing to fix right now.</p> : <ol className="sec-recs">{full.recommendations.map((item, index) =>
          <li key={index} className={`sec-recs__${item.priority}`}><span className="sec-badge">{item.priority.toUpperCase()}</span><div><strong>{item.title}</strong>{item.why && <p>{item.why}</p>}<p className="sec-area__fix"><span>Fix</span>{item.fix}</p></div></li>)}</ol>}
      </section>
      <ImprovementsView data={full.improvements}/>
    </>}
    <SecurityChecks/>
    {full && <ActivityView activity={full.activity}/>}
    <section className="sec-block" aria-label="Owner security actions">
      <h3>Owner actions</h3>
      <p className="sec-muted">Each opens the ZAENIA - Security window on this PC and asks for your passkey there. Voice training retrains how ZAE recognises you.</p>
      <div className="sec-actions">{ACTIONS.map(item => <button type="button" key={item.mode} className={item.danger ? "sec-actions__danger" : undefined} onClick={() => void action(item.mode)}>
        <strong>{item.title}</strong><small>{item.note}</small></button>)}</div>
    </section>
  </div>;
}
