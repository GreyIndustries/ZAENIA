import { useEffect, useRef, useState } from "react";
import { api, briefingAudio, BridgeError, errorText } from "../../core/bridge";
import { SILENT_WAV } from "../../core/speech";
import { BRIEF_EVENT } from "../../core/briefRequest";
import "./BrowserBriefing.css";

type Brief = { session_id: string; generated_at: string; briefing_text: string; audio_ready: boolean; needs_answer?: boolean; question_type?: string };
type Props = { onAuthLost?: () => void; onActive: (active: boolean) => void; beforePlay: () => void; showButton?: boolean };

/** On-demand, full calendar/weather/traffic brief. The "Brief me" button is gone (Grey, 2026-11-04): ask for it by
 * words ("on the road brief", "brief me"), which fires BRIEF_EVENT; the panel then opens, plays it and shows the text. */
export function BrowserBriefing({ onAuthLost, onActive, beforePlay, showButton = false }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const objectUrl = useRef<string | null>(null);
  const acknowledged = useRef(new Set<string>());
  const mounted = useRef(true);
  const inFlight = useRef(false);

  useEffect(() => { onActive(busy || playing); }, [busy, playing, onActive]);
  const start = useRef<() => void>(() => undefined);
  useEffect(() => {
    const ask = () => start.current();
    window.addEventListener(BRIEF_EVENT, ask);
    return () => window.removeEventListener(BRIEF_EVENT, ask);
  }, []);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false; audio.current?.pause(); onActive(false);
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    };
  }, [onActive]);

  function failed(failure: unknown) {
    if (!mounted.current) return;
    if (failure instanceof BridgeError && failure.kind === "auth") onAuthLost?.();
    else setError(errorText(failure));
  }

  async function loadAudio(next: Brief) {
    const blob = await briefingAudio(next.session_id);
    if (!mounted.current) return;
    const nextUrl = URL.createObjectURL(blob);
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = nextUrl; setUrl(nextUrl);
    const element = audio.current;
    if (!element) return;
    element.src = nextUrl;
    try { await element.play(); }
    catch { if (mounted.current) setNote("Your briefing is ready. Tap Play to listen."); }
  }

  async function generate() {
    if (inFlight.current) return;
    inFlight.current = true;
    beforePlay(); setOpen(true); setBusy(true); setError(null); setNote(null);
    const element = audio.current;
    if (element) {
      element.pause(); element.src = SILENT_WAV;
      void element.play().catch(() => undefined);
    }
    try {
      const next = await api<Brief>("POST", "/api/briefing", { request_id: `browser-${crypto.randomUUID()}` }, { timeoutMs: 150_000 });
      if (!mounted.current) return;
      setBrief(next);
      if (next.audio_ready) await loadAudio(next);
    } catch (failure) { failed(failure); }
    finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }

  // An explicit request asks for current information, even while a previous brief is visible.
  // generate's synchronous inFlight guard coalesces requests while that refresh is running.
  start.current = () => { void generate(); };

  async function retryAudio() {
    if (!brief || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try { await loadAudio(brief); } catch (failure) { failed(failure); }
    finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }

  async function answer(value: string) {
    if (!brief || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null); audio.current?.pause();
    try {
      const next = await api<Brief>('POST', '/api/briefing/answer', { session_id: brief.session_id, answer: value }, { timeoutMs: 150_000 });
      if (!mounted.current) return;
      setBrief(next); setNote(null);
      if (next.audio_ready) await loadAudio(next);
    } catch (failure) { failed(failure); }
    finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }

  async function played() {
    setPlaying(false);
    if (!brief || audio.current?.src === SILENT_WAV || acknowledged.current.has(brief.session_id)) return;
    try {
      await api("POST", "/api/briefing/played", { session_id: brief.session_id });
      acknowledged.current.add(brief.session_id);
    } catch (failure) { failed(failure); }
  }

  return <section className={`browser-briefing${open ? " browser-briefing--open" : ""}`} aria-label="Your briefing">
    {/* Gone on the desktop (ask for it by words); the phone keeps its button. */}
    {showButton && <button className="browser-briefing__toggle" type="button" aria-expanded={open} aria-controls="browser-briefing-panel"
      onClick={() => { if (open) { audio.current?.pause(); setOpen(false); } else if (brief) setOpen(true); else void generate(); }}>
      {open ? "Close briefing" : "Brief me"}
    </button>}
    <div id="browser-briefing-panel" className="browser-briefing__panel" hidden={!open}>
      <div className="browser-briefing__head"><strong>Your briefing</strong><span><button type="button" disabled={busy} onClick={() => void generate()}>{busy ? "Preparing…" : "Refresh"}</button>
        <button type="button" onClick={() => { audio.current?.pause(); setOpen(false); }}>Close</button></span></div>
      {busy && <p role="status">Checking your schedule, weather and traffic…</p>}
      {brief && <><p className="browser-briefing__text">{brief.briefing_text}</p><small>Updated {new Date(brief.generated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</small></>}
      {brief?.needs_answer && <div className="platform-inline" aria-label="Answer briefing question">
        <button disabled={busy} type="button" onClick={() => void answer('yes')}>{brief.question_type === 'calendar_completion' ? 'Completed' : 'Yes'}</button>
        <button disabled={busy} type="button" onClick={() => void answer('not yet')}>Not yet</button>
      </div>}
      <audio ref={audio} controls={Boolean(url)} hidden={!url} preload="none" onPlay={() => { if (objectUrl.current && audio.current?.src === objectUrl.current) { beforePlay(); setPlaying(true); } }}
        onPause={() => setPlaying(false)} onEnded={() => void played()} onError={() => { if (url) { setPlaying(false); setError("Audio couldn't play. Try loading it again."); } }}/>
      {note && <p role="status">{note}</p>}
      {error && <p className="browser-briefing__error" role="alert">{error}</p>}
      {brief && error && <button type="button" disabled={busy} onClick={() => void retryAudio()}>Load audio again</button>}
    </div>
  </section>;
}
