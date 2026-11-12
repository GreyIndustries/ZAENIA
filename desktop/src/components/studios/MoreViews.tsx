import { useCallback, useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./MainViews.css";

/**
 * More main views from Grey's preview picks (2026-10-30): Arena "Head to head" (A), Security "Shield" (A) and
 * Settings "Control center" (A). The existing panels stay as the next sub-tabs; nothing here bypasses the Security
 * lock (the shield shows only the public level, details stay behind the passkey).
 */
const needServer = (what: string) => <p className="mv-muted">{what} needs the ZÆNIA server: open it in the desktop app.</p>;

// ---------------------------------------------------------------- Arena: Head to head
type Model = { name: string; size: number; parameters: string };
type Answer = { model: string; answer: string; seconds: number | null; tokensPerSecond?: number | null; error?: string };
type Round = { id: string; question: string; answers: Answer[]; winner: string | null };

export function ArenaHeadToHead() {
  const [models, setModels] = useState<Model[]>([]);
  const [pair, setPair] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [round, setRound] = useState<Round | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voted, setVoted] = useState<string | null>(null);
  useEffect(() => { if (LIVE_API) api<{ models: Model[] }>("GET", "/api/arena").then(s => { setModels(s.models); }, f => setError(errorText(f))); }, []);
  const pickPair = useCallback(() => {
    const pool = models.filter(m => !/embed/i.test(m.name));
    const shuffled = [...pool].sort(() => Math.random() - 0.5);
    return shuffled.slice(0, 2).map(m => m.name);
  }, [models]);
  const ask = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    const chosen = pair.length === 2 ? pair : pickPair();
    setPair(chosen); setBusy(true); setError(null); setRound(null); setVoted(null);
    try { setRound(await api<Round>("POST", "/api/arena/round", { question: question.trim(), models: chosen }, { timeoutMs: 600_000 })); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  };
  const vote = async (model: string | null, label: string) => {
    if (!round) return;
    try { if (model) await api("POST", "/api/arena/vote", { round: round.id, model }); setVoted(label); }
    catch (failure) { setError(errorText(failure)); }
  };
  if (!LIVE_API) return needServer("The Arena");
  const answers = round?.answers ?? [];
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">Pick the best SE model</span><h2 className="zx-title">Arena</h2></div>
      <button type="button" className="mv-ghost" onClick={() => { setPair(pickPair()); setRound(null); setVoted(null); }}>New pair</button></div>
    <form className="mv-ask zx-inset" onSubmit={event => void ask(event)}>
      <input value={question} maxLength={2000} placeholder="Ask both models the same question…" aria-label="Question for the models" onChange={event => setQuestion(event.target.value)}/>
      <span className="mv-muted">names hidden until you vote</span>
      <button type="submit" className="mv-primary" disabled={busy || !question.trim() || models.length < 2}>{busy ? "Asking…" : "Ask both"}</button>
    </form>
    {error && <p className="mv-error" role="alert">{error}</p>}
    {busy && <p className="mv-muted" role="status">Both models are answering. Large ones can take a minute to load.</p>}
    {answers.length > 0 && <div className="mv-duel">{answers.map((a, i) => {
      const label = i === 0 ? "A" : "B";
      return <section key={a.model} className={`zx-card mv-duel__side${voted === label ? " mv-duel__side--won" : ""}`}>
        <div className="mv-row"><b>{voted ? a.model : `Model ${label}`}</b><code className="mv-muted">{a.seconds != null ? `${a.seconds.toFixed(1)} s` : ""}{a.tokensPerSecond ? ` · ${Math.round(a.tokensPerSecond)} tok/s` : ""}</code></div>
        <div className="mv-duel__text">{a.error ? <p className="mv-error">{a.error}</p> : a.answer.split("\n").map((line, k) => <p key={k}>{line}</p>)}</div>
        <button type="button" className={i === 0 ? "mv-primary" : "mv-ghost"} disabled={Boolean(voted)} onClick={() => void vote(a.model, label)}>{label} is better</button>
      </section>;
    })}</div>}
    {answers.length > 0 && !voted && <div className="mv-chips mv-center">
      <button type="button" onClick={() => void vote(null, "tie")}>Tie</button>
      <button type="button" onClick={() => void vote(null, "bad")}>Both bad</button>
    </div>}
    {voted && <p className="mv-note" role="status">{voted === "tie" ? "Tie noted." : voted === "bad" ? "Noted: neither was good." : `Vote saved: Model ${voted} was ${answers[voted === "A" ? 0 : 1]?.model}.`} The leaderboard is on the next tab.</p>}
  </div>;
}

// ---------------------------------------------------------------- Security: Shield
type Summary = { level: "strong" | "fair" | "weak" | "unknown"; score: number; toImprove: number; lastCheck: { at: string; status: "pass" | "warn" | "fail" } | null };
const LEVEL_TONE: Record<string, string> = { strong: "#4fe39a", fair: "#e0c08a", weak: "#ff8a7a", unknown: "#9fb6cf" };

export function SecurityShield({ onDetails }: { onDetails: () => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const load = useCallback(() => { if (LIVE_API) api<Summary>("GET", "/api/security/summary").then(setSummary, () => undefined); }, []);
  useEffect(() => { load(); const id = window.setInterval(load, 60_000); return () => window.clearInterval(id); }, [load]);
  const check = async () => {
    try { await api("POST", "/api/security/checks", {}, { timeoutMs: 30_000 }); setNote("Full check started. Results show here in a minute."); window.setTimeout(load, 15_000); }
    catch (failure) { setNote(errorText(failure)); }
  };
  if (!LIVE_API) return needServer("Security");
  const tone = LEVEL_TONE[summary?.level ?? "unknown"];
  const ago = summary?.lastCheck ? Math.round((Date.now() - new Date(summary.lastCheck.at).getTime()) / 36e5) : null;
  return <div className="mv mv-shieldview">
    <section className="zx-card mv-shield" style={{ "--shield": tone } as CSSProperties}>
      <span className="mv-kicker">Owner only · details stay locked</span>
      <svg viewBox="0 0 220 250" role="img" aria-label={`Security level ${summary?.level ?? "unknown"}, ${summary?.score ?? "—"} out of 100`}>
        <path d="M110 10 L200 45 V120 C200 180 160 225 110 240 C60 225 20 180 20 120 V45 Z" className="mv-shield__shape"/>
        <text x="110" y="128" textAnchor="middle" className="mv-shield__num">{summary?.score ?? "—"}</text>
        <text x="110" y="160" textAnchor="middle" className="mv-shield__word">{(summary?.level ?? "checking").toUpperCase()}</text>
      </svg>
      <span className="mv-muted">{summary?.lastCheck ? `Last full check ${summary.lastCheck.status === "pass" ? "passed" : summary.lastCheck.status === "warn" ? "passed with warnings" : "failed"} ${ago! < 1 ? "within the hour" : `${ago} h ago`}` : "No full check yet"}</span>
      <button type="button" className="mv-primary mv-wide" onClick={() => void check()}>Run a full check</button>
      <button type="button" className="mv-ghost mv-wide" onClick={onDetails}>Open details (passkey)</button>
      {note && <p className="mv-note" role="status">{note}</p>}
    </section>
    <section className="zx-card">
      <h3>Make it stronger</h3>
      <p className="mv-muted">{summary ? (summary.toImprove ? `${summary.toImprove} area${summary.toImprove === 1 ? "" : "s"} could be stronger. The list of areas, what each means and the fixes are in Details, which needs your passkey.` : "Every area is strong right now.") : "Checking…"}</p>
      <div className="mv-areas">{["Network", "Passkey guessing", "Secrets at rest", "App and phone access", "Voice impersonation", "Security code tests", "Audit trail", "Signs of attack"].map(name =>
        <div key={name} className="zx-inset"><i style={{ background: tone }}/><span>{name}</span></div>)}</div>
      <small className="mv-muted">The overall level covers these eight areas. Each area's own result is shown only after unlocking.</small>
    </section>
  </div>;
}

// ---------------------------------------------------------------- Settings: Control center
export type ControlToggle = { id: string; name: string; detail: string; on: boolean; toggle: () => void; disabled?: boolean };
export function ControlCenter({ toggles, colors, color, onColor, size, onSize, onOpen }: {
  toggles: ControlToggle[]; colors: { id: string; label: string; swatch: string }[]; color: string; onColor: (id: string) => void;
  size: number; onSize: (size: number) => void; onOpen: (tab: string) => void;
}) {
  return <div className="mv">
    <div className="mv-head"><div><span className="mv-kicker">System · appearance · vault</span><h2 className="zx-title">Control center</h2></div></div>
    <div className="mv-toggles">{toggles.map(t => <button key={t.id} type="button" aria-pressed={t.on} disabled={t.disabled} className="mv-toggle zx-card" onClick={t.toggle}>
      <span className="mv-row"><b>{t.name}</b><i className="mv-switch" aria-hidden="true"><i/></i></span><small>{t.detail}</small></button>)}</div>
    <div className="mv-three">
      <section className="zx-card"><h3>Look</h3>
        <div className="mv-swatches" role="radiogroup" aria-label="Accent colour">{colors.map(c => <button key={c.id} type="button" role="radio" aria-checked={color === c.id} aria-label={c.label} style={{ background: c.swatch }} onClick={() => onColor(c.id)}/>)}</div>
        <label className="mv-range">Text size <b>{size}%</b><input type="range" min={85} max={125} step={5} value={size} onChange={event => onSize(Number(event.target.value))}/></label>
        <button type="button" className="mv-ghost" onClick={() => onOpen("system")}>All appearance options</button>
      </section>
      <section className="zx-card"><h3>Notifications</h3><p className="mv-muted">Phone alerts, reminders and the morning brief.</p><button type="button" className="mv-ghost" onClick={() => onOpen("notifications")}>Open notifications</button></section>
      <section className="zx-card"><h3>Vault</h3><p className="mv-muted">Keys and passwords ZAE uses, encrypted on this PC. Opening it needs your passkey.</p><button type="button" className="mv-ghost" onClick={() => onOpen("vault")}>Open the vault</button></section>
    </div>
  </div>;
}
