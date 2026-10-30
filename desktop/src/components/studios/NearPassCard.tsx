import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { beginVoiceLogin, endNearPass, errorText, nearPassStatus, nearVoice, startNearPass, submitNearCode } from "../../core/bridge";
import type { NearPassState, VoiceChallenge } from "../../core/bridge";
import { recordLoginVoice } from "../../core/voiceLogin";
import type { VoiceRecording } from "../../core/voiceLogin";

/**
 * Confirm from the phone while it's at the PC (Grey, 2026-10-30: code plus voice, ZAE picks the order at random). Once both are
 * done, this phone can approve waiting file changes, Code Doctor fixes and app launches for 10 minutes.
 */
const OFF: NearPassState = { pass: false, code: false, voice: false, active: false, secondsLeft: 0 };
const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

export function NearPassCard() {
  const [state, setState] = useState<NearPassState>(OFF);
  const [left, setLeft] = useState(0);
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState<VoiceChallenge | null>(null);
  const [voicePhase, setVoicePhase] = useState<"idle" | "recording" | "checking">("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recording = useRef<VoiceRecording | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    const update = (event: Event) => { const next = (event as CustomEvent<NearPassState>).detail; setState(next); setLeft(next.secondsLeft); };
    window.addEventListener("zae:near-pass", update);
    void nearPassStatus().then(next => { setState(next); setLeft(next.secondsLeft); }).catch(() => undefined);
    return () => { window.removeEventListener("zae:near-pass", update); abort.current?.abort(); recording.current?.cancel(); };
  }, []);
  // Count down here; the server has the final say every 10 s (it ends the pass when time is up).
  useEffect(() => {
    if (!state.pass) return;
    let seconds = 0;
    const tick = window.setInterval(() => {
      setLeft(value => Math.max(0, value - 1));
      if (++seconds % 10 === 0) void nearPassStatus().catch(() => setState(OFF));
    }, 1000);
    return () => window.clearInterval(tick);
  }, [state.pass]);

  const run = async (work: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await work(); } catch (failure) { setError(errorText(failure)); } finally { setBusy(false); }
  };
  const sendCode = (event: FormEvent) => { event.preventDefault(); void run(async () => { await submitNearCode(code); setCode(""); }); };
  const getPrompt = () => run(async () => { setChallenge(await beginVoiceLogin()); });
  const record = () => run(async () => {
    recording.current?.cancel();
    abort.current = new AbortController();
    recording.current = await recordLoginVoice(abort.current.signal);
    setVoicePhase("recording");
  });
  const checkVoice = () => run(async () => {
    const audio = recording.current?.finish(); recording.current = null;
    if (!audio || !challenge) throw new Error("Get a fresh prompt and record again.");
    setVoicePhase("checking");
    try { await nearVoice(challenge.challenge_id, audio); setChallenge(null); }
    finally { setVoicePhase("idle"); }
  });
  const stop = () => { recording.current?.cancel(); recording.current = null; setChallenge(null); setVoicePhase("idle"); void endNearPass(); };

  if (state.active) return <section className="zx-card near near--on">
    <p className="mv-kicker">Phone confirms</p>
    <b className="zx-title">On for {clock(left)}</b>
    <p className="mv-muted">This phone can approve waiting file changes, Code Doctor fixes and opening your saved apps until then.</p>
    <button type="button" onClick={stop}>Turn off now</button>
  </section>;

  if (!state.pass) return <section className="zx-card near">
    <p className="mv-kicker">Phone confirms</p>
    <p className="mv-muted">At the PC? Type the code it shows and pass a voice check (ZAE picks which comes first), and this phone can approve things for 10 minutes.</p>
    <button type="button" className="near__start" disabled={busy} onClick={() => void run(startNearPass)}>Confirm from this phone</button>
    {error && <p className="mv-error" role="alert">{error}</p>}
  </section>;

  // ZAE picks which step comes first; the second opens once the first is done.
  const codeStep = (number: number, open: boolean) => <div key="code" className={`near__step zx-inset ${state.code ? "near__step--done" : open ? "" : "near__step--later"}`}>
    <b>{state.code ? "✓ Code matched" : `${number}. Code on the PC screen`}</b>
    {!state.code && open && <form onSubmit={sendCode} className="near__code">
      <input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9 ]*" maxLength={7} placeholder="6 digits" value={code}
        onChange={event => setCode(event.target.value)} aria-label="Code shown on the PC"/>
      <button type="submit" disabled={busy || code.replace(/\D/g, "").length !== 6}>Check</button>
    </form>}
    {!state.code && !open && <p className="mv-muted">Opens after the voice check.</p>}
  </div>;
  const voiceStep = (number: number, open: boolean) => <div key="voice" className={`near__step zx-inset ${state.voice ? "near__step--done" : open ? "" : "near__step--later"}`}>
    <b>{state.voice ? "✓ Voice matched" : `${number}. Voice check`}</b>
    {!state.voice && open && !challenge && <button type="button" disabled={busy} onClick={() => void getPrompt()}>Get words to say</button>}
    {!state.voice && open && challenge && <>
      <p className="near__phrase">“{challenge.phrase}”</p>
      {voicePhase === "idle" && <button type="button" disabled={busy} onClick={() => void record()}>Start recording</button>}
      {voicePhase === "recording" && <button type="button" disabled={busy} onClick={() => void checkVoice()}>Said it, check my voice</button>}
      {voicePhase === "checking" && <p className="mv-muted" role="status">Checking on your PC…</p>}
    </>}
    {!state.voice && !open && <p className="mv-muted">Opens after the code.</p>}
  </div>;

  return <section className="zx-card near">
    <div className="mv-row"><p className="mv-kicker">Phone confirms · {clock(left)} to finish</p><button type="button" className="near__cancel" onClick={stop}>Cancel</button></div>
    {(state.first === "voice" ? [voiceStep, codeStep] : [codeStep, voiceStep]).map((step, index) => step(index + 1, index === 0 || (state.first === "voice" ? state.voice : state.code)))}
    {error && <p className="mv-error" role="alert">{error}</p>}
  </section>;
}
