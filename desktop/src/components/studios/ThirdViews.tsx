import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SEBrainMap } from "../tools/SEBrainMap";
import { api, errorText, LIVE_API } from "../../core/bridge";
import type { CoreTelemetry, ModulePhase } from "../../core/coreTelemetry";
import { ACCENTS, CORNERS, DENSITIES, FONTS, LOOKS } from "../../core/appearance";
import type { Appearance } from "../../core/appearance";
import type { Scan } from "../tools/CodeStudio";
import "./MainViews.css";
import "./SecondViews.css";
import "./ThirdViews.css";
import { DetailScreen } from "../shell/PageNavigator";

/**
 * Grey's 2nd and 3rd picks (2026-10-30), batch 3: Settings "Search" (B) and "Make ZAE yours" (C), Status "Readiness"
 * (A), Code Doctor "Side by side" (C) and "Editor" (B), and Assistant page 2: "Memory" (A) with "How ZAE works with
 * you" (C). Real data and real settings only.
 */
const needServer = (what: string) => <p className="mv-muted">{what} needs the ZÆNIA server: open it in the desktop app or the phone app.</p>;
const goTab = (page: string, tab: string) => window.dispatchEvent(new CustomEvent("zae:page-tab", { detail: { page, tab } }));

// ---------------------------------------------------------------- Settings B: search
export type SettingToggle = { id: string; name: string; detail: string; on: boolean; toggle: () => void; disabled?: boolean };
const PLACES: { name: string; where: string; help: string; page: string; tab: string; words: string }[] = [
  { name: "Accent colour and text size", where: "Settings › Control center", help: "The colour of glows, buttons and the core", page: "settings", tab: "center", words: "color colour theme size font" },
  { name: "Window style, fonts, corners, spacing", where: "Settings › Make ZAE yours", help: "Aurora, HUD, editorial or neon looks", page: "settings", tab: "look", words: "look style font corners spacing density motion panel glass" },
  { name: "Module diagnostics", where: "Settings › System & appearance", help: "Each part of ZAE and what it's doing", page: "settings", tab: "system", words: "modules diagnostics system appearance" },
  { name: "The Vault", where: "Settings › Vault", help: "Private files, opened with the Security unlock", page: "settings", tab: "vault", words: "vault private secret files" },
  { name: "Phone notifications", where: "Settings › Notifications", help: "Push to your phone, test a notification", page: "settings", tab: "notifications", words: "phone push notification alerts" },
  { name: "Reminders", where: "Status › Protocols", help: "Time-based nudges on screen, spoken or on your phone", page: "status", tab: "protocols", words: "reminder nudge time alarm protocols" },
  { name: "Workout and food reminders", where: "LIFE · Fitness & Health", help: "Training days, weigh-in and food log nudges", page: "fitness", tab: "", words: "workout food weigh reminder fitness training" },
  { name: "Backups", where: "Status › Self-Sustain", help: "Nightly backup of ZAE's data and the watchdog", page: "status", tab: "selfsustain", words: "backup restore watchdog self sustain" },
  { name: "Security unlock and passkey", where: "Security › Details", help: "Passkey, spoken phrase and voice check settings", page: "security", tab: "details", words: "passkey security unlock voice phrase password" },
  { name: "The SE's main model", where: "Arena › Leaderboard", help: "Which local model the Synergized Encephalon uses", page: "arena", tab: "leaders", words: "brain model llm llama qwen arena" },
  { name: "The SE and coding tools", where: "Arena › SE & tools", help: "Talk, Seek, Study, Keep, Ollama, Claude Code, Aider and OpenCode, live", page: "arena", tab: "brains", words: "se synergized encephalon brains brain talk seek study keep ollama models gpu claude aider opencode coding tools" },
  { name: "Build requests", where: "Code Doctor › Build requests", help: "Ask ZAE to change her own app; approve at the PC", page: "codedoctor", tab: "build", words: "build request code change upgrade yourself approve undo" },
  { name: "Memory and learned patterns", where: "Assistant › Memory & rules", help: "What ZAE keeps about you, and confirming patterns", page: "assistant", tab: "memory", words: "memory facts learn pattern remember forget" },
  { name: "Quiet hours and spoken notices", where: "Assistant › Assistant tools", help: "When ZAE speaks and when she stays quiet", page: "assistant", tab: "tools", words: "quiet hours spoken notices follow through timezone" },
  { name: "Phone remote and phone confirms", where: "PC remote (phone)", help: "Control the PC and approve from your phone", page: "remote", tab: "", words: "remote phone confirm qr approve" },
];
export function SettingsSearch({ toggles }: { toggles: SettingToggle[] }) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const matches = (text: string) => !q || q.split(/\s+/).every(word => text.toLowerCase().includes(word));
  const switches = toggles.filter(t => matches(`${t.name} ${t.detail}`));
  const places = PLACES.filter(p => matches(`${p.name} ${p.where} ${p.help} ${p.words}`));
  return <div className="mv">
    <label className="zx-card sv-search"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input aria-label="Search settings" placeholder="Search settings: reminder, colour, backup…" value={query} onChange={e => setQuery(e.target.value)} autoFocus/>
      <span className="mv-muted">{switches.length + places.length} results</span></label>
    <span className="mv-muted">Or tell ZAE, for example “make the accent blue” or “turn off speak replies”.</span>
    {switches.map(t => <div key={t.id} className="zx-card sv-result-row">
      <span><span className="mv-muted">Settings › Control center</span><b>{t.name}</b><span className="mv-muted">{t.detail}</span></span>
      <button type="button" role="switch" aria-checked={t.on} disabled={t.disabled} onClick={t.toggle} className="sv-switch"><i/></button>
    </div>)}
    {places.map(p => <div key={p.name} className="zx-card sv-result-row">
      <span><span className="mv-muted">{p.where}</span><b>{p.name}</b><span className="mv-muted">{p.help}</span></span>
      <button type="button" className="zx-inset" onClick={() => { window.dispatchEvent(new CustomEvent("zae:open-section", { detail: p.page === "settings" ? "system" : p.page })); if (p.tab) window.setTimeout(() => goTab(p.page, p.tab), 50); }}>Open</button>
    </div>)}
    {!switches.length && !places.length && <p className="mv-muted">Nothing matches “{query}”.</p>}
  </div>;
}

// ---------------------------------------------------------------- Settings C: make ZAE yours (live preview)
export function LookStudio({ appearance, onChange }: { appearance: Appearance; onChange: (next: Appearance) => void }) {
  const [draft, setDraft] = useState(appearance);
  useEffect(() => setDraft(appearance), [appearance]);
  const accent = ACCENTS.find(a => a.id === draft.accent) ?? ACCENTS[0];
  const font = FONTS.find(f => f.id === draft.font) ?? FONTS[0];
  const radius = { style: 14, sharp: 2, soft: 10, round: 20 }[draft.corners];
  const changed = JSON.stringify(draft) !== JSON.stringify(appearance);
  const set = <K extends keyof Appearance>(key: K, value: Appearance[K]) => setDraft(d => ({ ...d, [key]: value }));
  return <div className="sv-look">
    <main className="sv-look__stage zx-card" style={{ fontFamily: font.stack }}>
      <div><span className="mv-kicker" style={{ color: accent.swatch }}>Live preview</span><h2 className="zx-title">Make ZAE yours</h2></div>
      <div className="sv-look__screen" data-look={draft.look} style={{ ["--p-accent" as string]: accent.swatch, ["--p-glow" as string]: `${draft.glow / 100}`, ["--p-radius" as string]: `${radius}px`, ["--p-alpha" as string]: `${draft.panelOpacity / 100}`, fontSize: `${draft.size / 100 * 13}px` }}>
        <div className="sv-look__nav"><span>Overview</span><span className="on">Music</span><span>Fitness</span><span>Research</span></div>
        <div className="sv-look__core" aria-hidden="true"/>
        <div className="sv-look__card"><b>Today</b><span>3 tasks · gym at 5:30 PM</span></div>
        <div className="sv-look__chat">Ask ZÆNIA anything…</div>
      </div>
      <span className="mv-muted">Nothing changes until you press Use this look.</span>
    </main>
    <aside className="sv-look__side zx-card sv-stack">
      <h3>Window style</h3>
      <div className="sv-look__grid">{LOOKS.map(l => <button key={l.id} type="button" aria-pressed={draft.look === l.id} title={l.note} onClick={() => set("look", l.id)}>{l.label}</button>)}</div>
      <h3>Accent</h3>
      <div className="sv-look__dots" role="radiogroup" aria-label="Accent colour">{ACCENTS.map(a => <button key={a.id} type="button" role="radio" aria-checked={draft.accent === a.id} aria-label={a.label} title={a.label} style={{ background: a.swatch }} onClick={() => set("accent", a.id)}/>)}</div>
      <label className="sv-field"><span>Font</span><select value={draft.font} onChange={e => set("font", e.target.value as Appearance["font"])}>{FONTS.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}</select></label>
      <label className="sv-field"><span>Glow {draft.glow}%</span><input type="range" min={40} max={160} value={draft.glow} onChange={e => set("glow", Number(e.target.value))}/></label>
      <label className="sv-field"><span>Text size {draft.size}%</span><input type="range" min={85} max={130} step={5} value={draft.size} onChange={e => set("size", Number(e.target.value))}/></label>
      <label className="sv-field"><span>Panels see-through {100 - draft.panelOpacity}%</span><input type="range" min={40} max={100} value={draft.panelOpacity} onChange={e => set("panelOpacity", Number(e.target.value))}/></label>
      <label className="sv-field"><span>Corners</span><select value={draft.corners} onChange={e => set("corners", e.target.value as Appearance["corners"])}>{CORNERS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
      <label className="sv-field"><span>Spacing</span><select value={draft.density} onChange={e => set("density", e.target.value as Appearance["density"])}>{DENSITIES.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}</select></label>
      <label className="sv-field"><span>Motion</span><select value={draft.motion} onChange={e => set("motion", e.target.value as Appearance["motion"])}><option value="full">Full</option><option value="reduced">Reduced</option></select></label>
      <div className="sv-actions sv-look__go"><button type="button" disabled={!changed} onClick={() => setDraft(appearance)}>Reset</button><button type="button" className="mv-primary" disabled={!changed} onClick={() => onChange(draft)}>Use this look</button></div>
    </aside>
  </div>;
}

// ---------------------------------------------------------------- Status A: readiness
const READY_GROUPS = [{ name: "SE and safety", ids: ["brain", "brain_talk", "brain_seek", "brain_study", "brain_keep", "security"] }, { name: "Voice", ids: ["voice", "carplay"] }, { name: "Connections", ids: ["calendar", "weather", "traffic"] }];
const phaseOk = (phase: ModulePhase) => phase === "ready" || phase === "working";
export function StatusReadiness({ telemetry, onStartVoice }: { telemetry: CoreTelemetry | null; onStartVoice?: () => void }) {
  const [extra, setExtra] = useState<{ id: string; name: string; now: boolean | null; percent: number | null }[]>([]);
  useEffect(() => { if (LIVE_API) api<{ rows: { id: string; name: string; now: boolean | null; percent: number | null }[] }>("GET", "/api/status/uptime").then(r => setExtra(r.rows.filter(row => row.id === "backup" || row.id === "desktop")), () => undefined); }, []);
  const modules = telemetry?.modules ?? [];
  const parts = [...modules.map(m => ({ id: m.id, name: m.name, ok: phaseOk(m.phase), detail: m.detail ?? m.phase, phase: m.phase })),
    ...extra.map(r => ({ id: r.id, name: r.name, ok: r.now !== false, detail: r.now === null ? "Not checked yet" : r.now ? "Working" : "Not working right now", phase: (r.now === false ? "error" : "ready") as ModulePhase }))];
  const ready = parts.filter(p => p.ok).length;
  const groups = READY_GROUPS.map(g => ({ name: g.name, parts: parts.filter(p => g.ids.includes(p.id) || (g.name === "Connections" && !READY_GROUPS.some(x => x.ids.includes(p.id)))) }));
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">Readiness</span><h2 className="zx-title">{parts.length ? `${ready} of ${parts.length} parts ready` : "Checking…"}</h2></div></div>
    <SEBrainMap/>
    <div className="sv-cols">{groups.map(g => <section key={g.name} className="zx-card sv-stack">
      <h3 className="mv-muted">{g.name.toUpperCase()}</h3>
      {g.parts.map(p => <div key={p.id} className={`zx-inset sv-part ${p.ok ? "" : "sv-part--bad"}`}>
        <i className={`sv-led sv-led--${p.phase}`} aria-hidden="true"/>
        <span className="sv-check__text"><b>{p.name}</b><span className="mv-muted">{p.detail}</span></span>
        {!p.ok && p.id === "voice" && onStartVoice && <button type="button" onClick={onStartVoice}>Start voice</button>}
      </div>)}
      {!g.parts.length && <p className="mv-muted">Nothing reported.</p>}
    </section>)}</div>
    <VoiceTrial/>
  </div>;
}

type TrialSide = { tries: number; checked: number; accepted: number; acceptedWithoutCheck: number; tooShort: number; failed: number; scoreMin: number | null; scoreMax: number | null; scoreAverage: number | null };
type TrialView = { round: { who: "owner" | "other"; target: number; count: number } | null; threshold: number | null; verdict: "not_run" | "in_progress" | "pass" | "fail";
  summary: { owner: TrialSide; other: TrialSide }; attempts: { who: string; accepted: boolean; reason: string; score: number | null; at: number }[] };
const TRIAL_REASON: Record<string, string> = { recognised: "Recognised", not_recognised: "Not recognised", too_short: "Too short to check",
  short_reply_in_conversation: "Short reply, no check", check_failed: "Check failed", not_set_up: "Voice not set up" };
const VERDICT: Record<TrialView["verdict"], string> = { not_run: "Not run yet", in_progress: "In progress", pass: "Passed", fail: "Needs work" };

/** Owner / other-speaker voice trial: counts every app-mic voice check during a round. The gate itself is unchanged. */
export function VoiceTrial() {
  const [view, setView] = useState<TrialView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<TrialView>("GET", "/api/voice/trial").then(v => { setView(v); setError(null); }, f => setError(errorText(f))), []);
  useEffect(() => { if (!LIVE_API) return; void load(); const id = window.setInterval(() => void load(), view?.round ? 1500 : 6000); return () => window.clearInterval(id); }, [load, Boolean(view?.round)]);
  const change = async (body: { action: "start" | "stop" | "clear"; who?: "owner" | "other"; target?: number }) => {
    try { setView(await api<TrialView>("POST", "/api/voice/trial", body, { desktop: true })); setError(null); } catch (f) { setError(errorText(f)); }
  };
  const side = (who: "owner" | "other", label: string, good: (s: TrialSide) => string) => {
    const s = view?.summary[who];
    return <div className="zx-inset sv-trial__side">
      <b>{label}</b>
      <span className="sv-trial__big">{s ? `${s.accepted} of ${s.checked}` : "–"}<small> let in</small></span>
      <span className="mv-muted">{s ? good(s) : ""}</span>
      {s && s.scoreAverage != null && <span className="mv-muted">Scores {s.scoreMin} to {s.scoreMax} (average {s.scoreAverage})</span>}
      {s && (s.tooShort > 0 || s.failed > 0) && <span className="mv-muted">{s.tooShort} too short, {s.failed} not checked</span>}
      <button type="button" className="zx-inset" disabled={Boolean(view?.round)} onClick={() => void change({ action: "start", who, target: 10 })}>Start 10 tries</button>
    </div>;
  };
  return <section className="zx-card sv-stack sv-trial">
    <div className="sv-trial__head"><div><h3 className="mv-muted">VOICE TRIAL</h3>
      <p className="mv-muted">Turn on Listening, start a round, then speak normal sentences to ZAE (each try is one sentence of about 2 seconds or more). For "someone else", have another person speak, or play a recording of another voice. Only the result and score of each check are kept, not the audio or words.</p></div>
      <span className={`sv-chip sv-trial__verdict sv-trial__verdict--${view?.verdict ?? "not_run"}`}>{VERDICT[view?.verdict ?? "not_run"]}</span></div>
    {view?.round && <p className="sv-trial__live" role="status">Listening for <b>{view.round.who === "owner" ? "you" : "someone else"}</b>: try {view.round.count + 1} of {view.round.target}. <button type="button" className="zx-inset" onClick={() => void change({ action: "stop" })}>Stop round</button></p>}
    <div className="sv-cols">
      {side("owner", "You (Grey)", s => s.checked ? `${s.checked - s.accepted} wrongly turned away` : "Start this round first")}
      {side("other", "Someone else", s => s.checked || s.acceptedWithoutCheck ? `${s.accepted + s.acceptedWithoutCheck} wrongly let in${s.acceptedWithoutCheck ? ` (${s.acceptedWithoutCheck} as a short reply)` : ""}` : "Should be 0 let in")}
    </div>
    {view?.threshold != null && <p className="mv-muted">Pass mark: a score of {view.threshold} or higher on every part of the sentence. Passing the trial needs at least 5 checked tries each, you let in 8 of 10 times or better, and nobody else let in.</p>}
    {!!view?.attempts.length && <details><summary>Every try ({view.attempts.length})</summary>
      {view.attempts.map((a, i) => <div key={i} className="sv-rule"><span><b>{a.who === "owner" ? "You" : "Someone else"}: {TRIAL_REASON[a.reason] ?? a.reason}</b><span className="mv-muted">{new Date(a.at * 1000).toLocaleTimeString()}</span></span><span className="sv-chip">{a.score == null ? (a.accepted ? "let in" : "turned away") : `${a.score} · ${a.accepted ? "let in" : "turned away"}`}</span></div>)}
      <button type="button" className="zx-inset" onClick={() => void change({ action: "clear" })}>Clear results</button>
    </details>}
    {!LIVE_API && <p className="mv-muted">The voice trial needs the server.</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

// ---------------------------------------------------------------- Code Doctor: shared bits
type Finding = Scan["findings"][number];
type Fix = { changed: boolean; message?: string; text?: string; oldHash?: string; protected?: boolean };
type ScanState = { project: string; scan: Scan | null; busy: boolean; error: string | null; run: () => Promise<void> };
const byFile = (scan: Scan | null) => {
  const map = new Map<string, Finding[]>();
  for (const f of scan?.findings ?? []) { if (f.level === "info" || /looks like a secret/i.test(f.message)) continue; map.set(f.file, [...(map.get(f.file) ?? []), f]); }
  return [...map.entries()].sort((a, b) => b[1].filter(f => f.level === "error").length - a[1].filter(f => f.level === "error").length || b[1].length - a[1].length);
};
const lines = (findings: Finding[]) => findings.map(f => ({ line: f.line, level: f.level, message: f.message }));
/** The changed stretch of a file with 3 lines either side (a fix is usually one small area). */
function changedStretch(before: string, after: string) {
  const a = before.split("\n"), b = after.split("\n");
  let top = 0; while (top < a.length && top < b.length && a[top] === b[top]) top++;
  let end = 0; while (end < a.length - top && end < b.length - top && a[a.length - 1 - end] === b[b.length - 1 - end]) end++;
  const from = Math.max(0, top - 3);
  const side = (all: string[], kind: "-" | "+") => all.slice(from, all.length - end + 3).map((text, i) => ({ n: from + i + 1, text, changed: from + i >= top && from + i < all.length - end, kind }));
  return { before: side(a, "-"), after: side(b, "+") };
}
function useFix(project: string) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const run = async <T,>(label: string, work: () => Promise<T>) => {
    setBusy(label); setError(null); setNote(null);
    try { return await work(); } catch (f) { setError(errorText(f)); return null; } finally { setBusy(null); }
  };
  const load = (file: string) => api<{ text: string; hash: string }>("POST", "/api/code/load", { project, file });
  const write = (file: string, findings: Finding[]) => api<Fix>("POST", "/api/code/fix", { project, file, findings: lines(findings) }, { timeoutMs: 300_000 });
  const apply = (file: string, fix: Fix) => api<{ backup: string }>("POST", "/api/code/apply", { project, file, text: fix.text, oldHash: fix.oldHash }, { desktop: true, timeoutMs: 60_000 });
  const explain = (file: string, findings: Finding[]) => api<{ review: string }>("POST", "/api/code/explain", { project, file, findings: lines(findings) }, { timeoutMs: 300_000 });
  return { busy, error, note, setNote, run, load, write, apply, explain };
}
const ScanFirst = ({ code }: { code: ScanState }) => <section className="zx-card sv-stack"><p className="mv-muted">Scan {code.project} first.</p>
  {code.error && <p className="mv-error">{code.error}</p>}
  <button type="button" className="mv-primary" disabled={code.busy} onClick={() => void code.run()}>{code.busy ? "Scanning…" : "Scan now"}</button></section>;

// ---------------------------------------------------------------- Code Doctor C: side by side
export function CodeSideBySide({ code }: { code: ScanState }) {
  const files = useMemo(() => byFile(code.scan), [code.scan]);
  const [file, setFile] = useState<string | null>(null);
  const [view, setView] = useState<{ fix: Fix; before: string } | null>(null);
  const [done, setDone] = useState<string[]>([]);
  const act = useFix(code.project);
  const current = files.find(([f]) => f === file) ?? files.find(([f]) => !done.includes(f));
  const keptFix = useRef<typeof view>(null);
  useEffect(() => { setView(null); keptFix.current = null; }, [current?.[0]]);
  if (!LIVE_API) return needServer("Code Doctor");
  if (!code.scan) return <ScanFirst code={code}/>;
  const write = () => current && act.run("writing a fix", async () => {
    const [fix, original] = await Promise.all([act.write(current[0], current[1]), act.load(current[0])]);
    if (!fix.changed || !fix.text) act.setNote(fix.message ?? (fix.protected ? "That file is ZAE's security code, so Code Doctor won't change it." : "ZAE couldn't find a safe fix for this one."));
    else setView({ fix, before: original.text });
  });
  const apply = () => current && view && act.run("applying", async () => {
    const result = await act.apply(current[0], view.fix);
    act.setNote(`Applied. The old version is kept at ${result.backup}.`);
    setDone(d => [...d, current[0]]); setView(null); setFile(null);
  });
  const stretch = view?.fix.text ? changedStretch(view.before, view.fix.text) : null;
  const errors = (fs: Finding[]) => fs.filter(f => f.level === "error").length;
  return <div className="sv-review">
    <DetailScreen id="side-fix" name="Side by side" open={!!view} title={current ? `Proposed fix · ${current[0].split("/").pop()}` : "Proposed fix"}
      onOpen={() => { if (keptFix.current) setView(keptFix.current); }} onClose={() => { keptFix.current = view; setView(null); }}/>
    <aside className="zx-card sv-stack sv-review__queue">
      <span className="mv-kicker">Waiting for you</span><h3 className="zx-title">{files.length - done.length} file{files.length - done.length === 1 ? "" : "s"} to fix</h3>
      {files.map(([f, fs]) => <button key={f} type="button" className="sv-three__item" aria-pressed={current?.[0] === f} disabled={done.includes(f)} onClick={() => setFile(f)}>
        <span className="mv-row"><b className={errors(fs) ? "sv-warn" : "sv-gold"}>{errors(fs) ? `FIX · ${errors(fs)} ERROR${errors(fs) > 1 ? "S" : ""}` : "FIX · WARN"}</b>{done.includes(f) && <span className="sv-ok">applied</span>}</span>
        <b className="sv-clip">{fs[0].message}</b><span className="sv-mono mv-muted sv-clip">{f}:{fs[0].line}</span>
      </button>)}
      {!files.length && <p className="mv-muted">Nothing to fix. Nice.</p>}
    </aside>
    <main className="zx-card sv-stack sv-review__main">
      {current ? <>
        <div className="mv-head"><div><span className={errors(current[1]) ? "sv-warn" : "sv-gold"}>{errors(current[1]) ? "FIX · ERROR" : "FIX · WARNING"}</span>
          <h3 className="zx-title">{current[1][0].message}</h3><span className="sv-mono mv-muted">{current[0]} · {current[1].length} finding{current[1].length > 1 ? "s" : ""}</span></div>
          <span className="sv-actions">
            <button type="button" disabled={act.busy !== null} onClick={() => setDone(d => [...d, current[0]])}>Skip</button>
            {!view && <button type="button" className="mv-primary" disabled={act.busy !== null} onClick={() => void write()}>Write the fix</button>}
            {view && <button type="button" className="mv-primary" disabled={act.busy !== null} onClick={() => void apply()}>Approve and apply</button>}
          </span></div>
        <ul className="sv-findings">{current[1].slice(0, 6).map((f, i) => <li key={i}><span className="sv-mono">line {f.line}</span> {f.message}</li>)}</ul>
        {act.busy && <p className="mv-muted" role="status">ZAE is {act.busy}…</p>}
        {act.error && <p className="mv-error">{act.error}</p>}
        {act.note && <p className="mv-note">{act.note}</p>}
        {stretch && <div className="sv-diff">
          <div><span className="mv-muted">Before</span>{stretch.before.map(l => <code key={l.n} className={l.changed ? "del" : ""}><i>{l.n}</i>{l.text || " "}</code>)}</div>
          <div><span className="mv-muted">After</span>{stretch.after.map(l => <code key={l.n} className={l.changed ? "add" : ""}><i>{l.n}</i>{l.text || " "}</code>)}</div>
        </div>}
        {view && <span className="mv-muted">A backup is kept before saving. Applying needs the desktop app or Phone confirms.</span>}
      </> : <p className="mv-muted">{act.note ?? "Everything here is done."}</p>}
    </main>
  </div>;
}

// ---------------------------------------------------------------- Code Doctor B: editor
export function CodeEditorView({ code }: { code: ScanState }) {
  const files = useMemo(() => byFile(code.scan), [code.scan]);
  const [file, setFile] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [explained, setExplained] = useState<string | null>(null);
  const [fix, setFix] = useState<Fix | null>(null);
  const act = useFix(code.project);
  const open = useCallback(async (next: string) => {
    setFile(next); setText(null); setExplained(null); setFix(null);
    const loaded = await act.run("opening", () => act.load(next));
    if (loaded) setText(loaded.text);
  }, [code.project]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!file && files[0]) void open(files[0][0]); }, [files]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!LIVE_API) return needServer("Code Doctor");
  if (!code.scan) return <ScanFirst code={code}/>;
  const findings = files.find(([f]) => f === file)?.[1] ?? [];
  const marked = new Map(findings.map(f => [f.line, f]));
  const shown = files.filter(([f]) => !filter.trim() || f.toLowerCase().includes(filter.trim().toLowerCase()));
  const counts = code.scan.counts;
  return <div className="sv-ide zx-card">
    <header className="sv-ide__bar"><b className="sv-gold">&lt;/&gt; Code Doctor</b><span className="mv-muted sv-mono sv-clip">{code.project}</span>
      <span className="sv-actions"><button type="button" disabled={code.busy} onClick={() => void code.run()}>{code.busy ? "Scanning…" : "Scan again"}</button>
        <button type="button" onClick={() => goTab("codedoctor", "playground")}>Open Playground</button></span></header>
    <aside className="sv-ide__tree">
      <input className="zx-inset" aria-label="Filter files" placeholder="Filter files" value={filter} onChange={e => setFilter(e.target.value)}/>
      {shown.map(([f, fs]) => <button key={f} type="button" aria-pressed={f === file} onClick={() => void open(f)}><span className="sv-clip sv-mono">{f}</span><b className={fs.some(x => x.level === "error") ? "sv-warn" : "sv-gold"}>{fs.length}</b></button>)}
    </aside>
    <main className="sv-ide__code" aria-label={file ?? "No file"}>
      {text === null ? <p className="mv-muted">{act.busy ? "Opening…" : act.error ?? "Pick a file."}</p> :
        text.split("\n").map((line, i) => { const hit = marked.get(i + 1); return <div key={i} className={hit ? `hit hit--${hit.level}` : ""} title={hit?.message}><i>{i + 1}</i><span>{line || " "}</span></div>; })}
    </main>
    <aside className="sv-ide__side sv-stack">
      <b>ZAE on this file</b>
      {findings.slice(0, 6).map((f, i) => <div key={i} className={`sv-ide__finding sv-ide__finding--${f.level}`}><b>Line {f.line}</b><span>{f.message}</span></div>)}
      <span className="sv-actions">
        <button type="button" disabled={!file || act.busy !== null} onClick={() => file && void act.run("explaining", async () => setExplained((await act.explain(file, findings)).review))}>Explain</button>
        <button type="button" disabled={!file || act.busy !== null} onClick={() => file && void act.run("writing a fix", async () => { const f = await act.write(file, findings); setFix(f); if (!f.changed) act.setNote(f.message ?? "No safe fix found."); })}>Write the fix</button>
      </span>
      {act.busy && <p className="mv-muted" role="status">ZAE is {act.busy}…</p>}
      {explained && <p className="sv-ide__explain">{explained}</p>}
      {fix?.changed && fix.text && text !== null && <>
        <div className="sv-diff sv-diff--one">{changedStretch(text, fix.text).after.filter(l => l.changed).slice(0, 12).map(l => <code key={l.n} className="add"><i>{l.n}</i>{l.text || " "}</code>)}</div>
        <button type="button" className="mv-primary" disabled={act.busy !== null} onClick={() => file && void act.run("applying", async () => { const r = await act.apply(file, fix); act.setNote(`Applied. Backup: ${r.backup}`); setFix(null); await open(file); })}>Apply</button>
      </>}
      {act.note && <p className="mv-note">{act.note}</p>}
      {act.error && text !== null && <p className="mv-error">{act.error}</p>}
    </aside>
    <section className="sv-ide__term sv-mono">
      <span className="mv-muted">SCAN</span>
      <span>{code.scan.totals.files} files · {code.scan.totals.lines.toLocaleString()} lines</span>
      <span className={counts.error ? "sv-warn" : "sv-ok"}>{counts.error ?? 0} errors · {counts.warn ?? 0} warnings · {counts.info ?? 0} notes</span>
    </section>
  </div>;
}

// ---------------------------------------------------------------- Assistant page 2: memory (A) + how ZAE works with you (C)
type Memory = { id: string; key: string; value: string; category: string; source: string; created_at: string; updated_at: string };
type Insight = { id: string; text: string; kind: string; count: number; source?: string; revision?: number; stale?: boolean };
type Rules = { enabled: boolean; spoken: boolean; quietHoursEnabled: boolean; quietStart: string; quietEnd: string };
export function AssistantMemoryRules({ toggles }: { toggles: SettingToggle[] }) {
  const [memories, setMemories] = useState<Memory[] | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [rules, setRules] = useState<Rules | null>(null);
  const [cat, setCat] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    if (!LIVE_API) return;
    Promise.all([api<{ memories: Memory[] }>("GET", "/api/assistant/memory"), api<{ insights: Insight[] }>("GET", "/api/assistant/insights"),
      api<{ settings: Rules }>("GET", "/api/assistant/notifications?includeRead=false").catch(() => null)])
      .then(([m, i, n]) => { setMemories(m.memories); setInsights(i.insights); if (n) setRules(n.settings); }, f => setError(errorText(f)));
  }, []);
  useEffect(load, [load]);
  if (!LIVE_API) return needServer("Memory");
  const act = async (work: () => Promise<unknown>) => { setError(null); try { await work(); load(); } catch (f) { setError(errorText(f)); } };
  const cats = ["all", ...new Set((memories ?? []).map(m => m.category))];
  const rows = [
    ...insights.map(i => ({ key: `i-${i.id}`, text: i.text, type: "Pattern", from: i.source === "user_confirmed" ? "Confirmed by you" : `Noticed ${i.count}×`, review: i.source !== "user_confirmed",
      keep: () => act(() => api("PATCH", `/api/assistant/insights/${i.id}`, { revision: i.revision ?? 1 })), forget: () => act(() => api("DELETE", `/api/assistant/insights/${i.id}`)) })),
    ...(memories ?? []).filter(m => cat === "all" || m.category === cat).map(m => ({ key: `m-${m.id}`, text: `${m.key}: ${m.value}`, type: m.category, from: `${m.source} · ${new Date(m.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`, review: false,
      keep: undefined, forget: () => act(() => api("DELETE", `/api/assistant/memory/${encodeURIComponent(m.id)}`)) })),
  ].filter(r => cat === "all" || r.type === cat || r.type === "Pattern" && cat === "Pattern");
  const pending = insights.filter(i => i.source !== "user_confirmed").length;
  const talk = toggles.filter(t => ["speak", "listen"].includes(t.id));
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">What ZAE keeps about you</span><h2 className="zx-title">Memory</h2>
      <span className="mv-muted">Every saved fact shows where it came from. Nothing here changes what ZAE is allowed to do.</span></div>
      {pending > 0 && <span className="zx-inset sv-pill">{pending} pattern{pending > 1 ? "s" : ""} waiting for your review</span>}</div>
    {error && <p className="mv-error">{error}</p>}
    <div className="mv-chips" role="group" aria-label="Categories">{[...cats, "Pattern"].map(c => <button key={c} type="button" aria-pressed={cat === c} onClick={() => setCat(c)}>
      {c === "all" ? `All · ${(memories?.length ?? 0) + insights.length}` : c === "Pattern" ? `Patterns · ${insights.length}` : `${c} · ${(memories ?? []).filter(m => m.category === c).length}`}</button>)}</div>
    <section className="zx-card sv-mem">
      <div className="sv-mem__row sv-table__head"><span>Fact</span><span>Type</span><span>From</span><span>Status</span><span/></div>
      {memories && !rows.length && <p className="mv-muted">Nothing saved here yet.</p>}
      {rows.map(r => <div key={r.key} className="sv-mem__row"><span>{r.text}</span><span className="mv-muted">{r.type}</span><span className="mv-muted">{r.from}</span>
        <b className={r.review ? "sv-gold" : "sv-ok"}>{r.review ? "REVIEW" : "SAVED"}</b>
        <span className="sv-actions">{r.keep && <button type="button" onClick={() => void r.keep!()}>Keep</button>}<button type="button" className="sv-forget" onClick={() => void r.forget()}>Forget</button></span></div>)}
    </section>
    <div className="mv-head"><div><span className="mv-kicker">How ZAE works with you</span><h2 className="zx-title">Your rules</h2>
      <span className="mv-muted">Rules ZAE follows. Change any of them; ZAE assists, you decide.</span></div></div>
    <div className="sv-cols">
      <section className="zx-card sv-stack"><h3>Talking</h3>
        {talk.map(t => <div key={t.id} className="sv-rule"><span><span>{t.name}</span><span className="mv-muted">{t.detail}</span></span><button type="button" role="switch" aria-checked={t.on} disabled={t.disabled} className="sv-switch" onClick={t.toggle}><i/></button></div>)}
        <div className="sv-rule"><span><span>Questions</span><span className="mv-muted">As cards with options</span></span><b className="sv-chip">Cards</b></div>
      </section>
      <section className="zx-card sv-stack"><h3>Acting</h3>
        <div className="sv-rule"><span><span>Deleting</span><span className="mv-muted">Always asks first</span></span><b className="sv-chip">Ask</b></div>
        <div className="sv-rule"><span><span>Code and file changes</span><span className="mv-muted">Only after you approve, with a backup</span></span><b className="sv-chip">Approve</b></div>
        <div className="sv-rule"><span><span>Phone approvals</span><span className="mv-muted">QR on the PC plus your voice</span></span><b className="sv-chip">At the PC</b></div>
      </section>
      <section className="zx-card sv-stack"><h3>Notices</h3>
        {rules ? <>
          <div className="sv-rule"><span><span>Follow-through notices</span><span className="mv-muted">Reminders about tasks and events</span></span><b className="sv-chip">{rules.enabled ? "On" : "Off"}</b></div>
          <div className="sv-rule"><span><span>Spoken notices</span><span className="mv-muted">Read out loud when they arrive</span></span><b className="sv-chip">{rules.spoken ? "On" : "Off"}</b></div>
          <div className="sv-rule"><span><span>Quiet hours</span><span className="mv-muted">No spoken notices</span></span><b className="sv-chip">{rules.quietHoursEnabled ? `${rules.quietStart}–${rules.quietEnd}` : "Off"}</b></div>
          <button type="button" className="zx-inset" onClick={() => goTab("assistant", "tools")}>Change notices</button>
        </> : <p className="mv-muted">Loading…</p>}
      </section>
    </div>
    <div className="zx-card sv-first"><b>First rule:</b> ZAE is a system that helps you. She talks and acts on request, never claims feelings or a life of her own, and leaves the work and the decisions to you.</div>
  </div>;
}
