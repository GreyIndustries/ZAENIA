import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { CoreBackdrop } from "../core/CoreBackdrop";
import { beginVoiceLogin, BridgeError, checkToken, completeVoiceLogin, errorText, saveToken } from "../../core/bridge";
import type { VoiceChallenge } from "../../core/bridge";
import { recordLoginVoice } from "../../core/voiceLogin";
import { faceIdReady, signInWithFaceId } from "../../core/faceId";
import type { VoiceRecording } from "../../core/voiceLogin";
import "./PhoneConnect.css";

type Props = { notice?: string | null; onConnected: () => void };

/**
 * First screen of the phone web app. The token is checked with the ZÆNIA
 * server before it is saved, and it is only ever sent to that server.
 */
export function PhoneConnect({ notice, onConnected }: Props) {
  const [token, setToken] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<VoiceChallenge | null>(null);
  const [phase, setPhase] = useState<"idle" | "preparing" | "ready" | "starting" | "recording" | "verifying">("idle");
  const recording = useRef<VoiceRecording | null>(null);
  const abort = useRef<AbortController | null>(null);
  const timer = useRef<number | null>(null);
  const mounted = useRef(true);
  const voiceBusy = phase !== "idle";
  const micSupported = Boolean(window.isSecureContext && navigator.mediaDevices?.getUserMedia);
  const [faceId, setFaceId] = useState(false);
  useEffect(() => { void faceIdReady().then(ready => { if (mounted.current) setFaceId(ready); }); }, []);
  async function faceIdSignIn() {
    if (busy || voiceBusy) return;
    setError(null); setBusy(true);
    try { await signInWithFaceId(); if (mounted.current) onConnected(); }
    catch (failure) { if (mounted.current) setError(failure instanceof Error ? failure.message : "Face ID didn't work. Try again."); }
    finally { if (mounted.current) setBusy(false); }
  }

  function cancelVoice() {
    abort.current?.abort();
    recording.current?.cancel(); recording.current = null;
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    setChallenge(null); setPhase("idle");
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      abort.current?.abort(); recording.current?.cancel();
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, []);

  async function prepareVoice() {
    if (busy || voiceBusy) return;
    setError(null); setPhase("preparing");
    try {
      const next = await beginVoiceLogin();
      if (!mounted.current) return;
      setChallenge(next); setPhase("ready");
    } catch (failure) { if (mounted.current) { setError(errorText(failure)); setPhase("idle"); } }
  }

  async function verifyVoice(active: VoiceChallenge) {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    setPhase("verifying");
    try {
      const audio = recording.current?.finish(); recording.current = null;
      if (!audio) throw new Error("Start a fresh voice recording.");
      await completeVoiceLogin(active.challenge_id, audio);
      if (mounted.current) onConnected();
    } catch (failure) {
      if (mounted.current) { setError(errorText(failure)); cancelVoice(); }
    }
  }

  async function startRecording() {
    if (!challenge || phase !== "ready") return;
    const active = challenge;
    const controller = new AbortController(); abort.current = controller;
    setPhase("starting"); setError(null);
    try {
      const clip = await recordLoginVoice(controller.signal);
      if (!mounted.current || controller.signal.aborted) { clip.cancel(); return; }
      recording.current = clip; setPhase("recording");
      timer.current = window.setTimeout(() => void verifyVoice(active), 12_000);
    } catch (failure) { if (mounted.current && !controller.signal.aborted) { setError(errorText(failure)); cancelVoice(); } }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = token.trim();
    if (!value || busy || voiceBusy) return;
    setBusy(true); setError(null);
    try {
      await checkToken(value);
      if (!saveToken(value)) {
        setError("This phone won't let ZÆNIA save the token. Turn off Private Browsing and try again.");
        return;
      }
      setToken("");
      onConnected();
    } catch (e) {
      setError(e instanceof BridgeError
        ? (e.kind === "auth" ? "That token didn't work. Try again or use voice verification." : e.message)
        : "Something went wrong. Try again.");
    } finally { setBusy(false); }
  }

  return <div className="phone-connect">
    <CoreBackdrop/>
    <main className="phone-connect__body">
      <div className="phone-connect__mark" aria-hidden="true"><span/></div>
      <h1 className="phone-connect__brand">ZÆNIA</h1>
      <p className="phone-connect__lede">Your briefing and Zae, wherever you are.</p>
      {faceId && <section className="phone-connect__card" aria-label="Face ID sign-in">
        <strong>Sign in with Face ID</strong>
        <p className="phone-connect__help">Look at your iPhone. Your face stays on the phone; Zae only gets Apple's signed yes.</p>
        <button className="phone-connect__submit" type="button" disabled={busy || voiceBusy} onClick={() => void faceIdSignIn()}>{busy ? "Checking…" : "Use Face ID"}</button>
        {error && <p className="phone-connect__message phone-connect__message--error" role="alert">{error}</p>}
      </section>}
      <section className="phone-connect__card" aria-label="Voice sign-in">
        <strong>Sign in with your voice</strong>
        <p className="phone-connect__help">No token needed. Read a fresh prompt so Zae can check your enrolled voice on your PC.</p>
        {challenge && <p className="phone-connect__phrase" aria-live="polite">{challenge.phrase}</p>}
        {phase === "idle" && <button className="phone-connect__submit" type="button" disabled={busy || !micSupported} onClick={() => void prepareVoice()}>Verify my voice</button>}
        {phase === "ready" && <button className="phone-connect__submit" type="button" onClick={() => void startRecording()}>Record these words</button>}
        {phase === "recording" && <><p className="phone-connect__help" role="status">Listening. Say all six words, then tap Verify voice.</p><button className="phone-connect__submit" type="button" onClick={() => challenge && void verifyVoice(challenge)}>Verify voice</button></>}
        {(phase === "preparing" || phase === "starting" || phase === "verifying") && <p className="phone-connect__help" role="status">{phase === "preparing" ? "Getting a fresh prompt…" : phase === "starting" ? "Opening your microphone…" : "Checking your words and your voice…"}</p>}
        {voiceBusy && phase !== "preparing" && phase !== "verifying" && <button className="phone-connect__cancel" type="button" onClick={cancelVoice}>Cancel</button>}
        {!micSupported && <p className="phone-connect__help">Voice sign-in needs Zae’s secure https address and microphone access.</p>}
      </section>
      <form className="phone-connect__card" onSubmit={submit} noValidate>
        <label htmlFor="zaenia-token">ACCESS TOKEN</label>
        <div className="phone-connect__field">
          <input
            id="zaenia-token"
            type={show ? "text" : "password"}
            value={token}
            onChange={(e: ChangeEvent<HTMLInputElement>) => { setToken(e.target.value); if (error) setError(null); }}
            placeholder="Paste your ZÆNIA token"
            autoComplete="off" autoCapitalize="off" autoCorrect="off" spellCheck={false}
            maxLength={512}
            aria-describedby="zaenia-token-help"
            aria-invalid={error ? true : undefined}
            disabled={busy || voiceBusy}
          />
          <button type="button" className="phone-connect__reveal" onClick={() => setShow(v => !v)} aria-pressed={show} aria-label={show ? "Hide token" : "Show token"}>{show ? "HIDE" : "SHOW"}</button>
        </div>
        <p id="zaenia-token-help" className="phone-connect__help">You can also connect with your ZÆNIA access token. It's saved only on this phone.</p>
        {error
          ? <p className="phone-connect__message phone-connect__message--error" role="alert">{error}</p>
          : notice ? <p className="phone-connect__message" role="status">{notice}</p> : null}
        <button type="submit" className="phone-connect__submit" disabled={busy || voiceBusy || !token.trim()}>{busy ? "Connecting…" : "Connect with token"}</button>
      </form>
      <p className="phone-connect__foot">Voice recordings are checked locally and discarded. Owner actions still need your passkey at the PC.</p>
    </main>
  </div>;
}
