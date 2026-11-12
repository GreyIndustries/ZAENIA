import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "./bridge";

/**
 * Microphone for the ZÆNIA UI.
 *
 * - Dictate: one request, then the mic turns off (the mic button).
 * - Always listening: while the app is open, every time you speak the clip is
 *   transcribed on your PC (Vosk). A configured name anywhere in a request,
 *   an explicit attention call, or a conversational follow-up reaches chat.
 *
 * Audio is kept in memory only for the clip being sent, and is downsampled to
 * 16 kHz mono PCM like ZÆNIA's PC voice runtime.
 */
export type VoiceMode = "off" | "dictate" | "always";
export type VoiceStatus = "off" | "starting" | "listening" | "hearing" | "transcribing" | "paused" | "blocked" | "error";
export type Transcript = { text: string; addressed: boolean; command: string; dismiss: boolean; conversational?: boolean; acknowledgement?: boolean; forZae?: boolean; nameRequired?: boolean | null;
  /** Set when the turn wasn't checked as Grey's voice; nothing else in it is used. */
  rejected?: string; message?: string };

const TARGET_RATE = 16000;
const PREROLL_SECONDS = 0.35;
const END_SILENCE_SECONDS = 0.75;
const MIN_SPEECH_SECONDS = 0.35;
const MAX_SPEECH_SECONDS = 15;
const DICTATE_TIMEOUT_SECONDS = 8;
const PREF_KEY = "zaenia.alwaysListening";

const IS_IOS = typeof navigator !== "undefined" &&
  (/iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.userAgent.includes("Macintosh") && navigator.maxTouchPoints > 1));

export const MIC_SUPPORTED = LIVE_API && typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia &&
  typeof window !== "undefined" && (window.isSecureContext ?? false);

// Listening is on unless you turned it off yourself.
function readPref(): boolean { try { return localStorage.getItem(PREF_KEY) !== "0"; } catch { return true; } }
function writePref(on: boolean) { try { localStorage.setItem(PREF_KEY, on ? "1" : "0"); } catch { /* storage unavailable */ } }

/** Box-filter downsample to 16 kHz, then 16-bit little-endian PCM as base64. */
export function encodeClip(chunks: Float32Array[], inputRate: number): string {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const joined = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.length; }
  const ratio = inputRate / TARGET_RATE;
  const length = Math.floor(total / ratio);
  const pcm = new Int16Array(length);
  for (let i = 0; i < length; i++) {
    const start = Math.floor(i * ratio), end = Math.min(total, Math.max(start + 1, Math.floor((i + 1) * ratio)));
    let sum = 0;
    for (let j = start; j < end; j++) sum += joined[j];
    const value = Math.max(-1, Math.min(1, sum / (end - start)));
    pcm[i] = value < 0 ? value * 0x8000 : value * 0x7fff;
  }
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

type Options = {
  /** Called with every clip ZÆNIA understood. `barged` is true when you spoke over ZÆNIA. */
  onTranscript: (result: Transcript, mode: VoiceMode, barged: boolean) => void;
  /** True while ZÆNIA is speaking: the mic ignores (or on iPhone releases) audio. */
  paused: boolean;
  /**
   * Desktop: keep listening while ZÆNIA speaks, with a stricter threshold, so
   * you can talk over her. onBargeIn runs as soon as your voice is detected.
   */
  bargeIn?: boolean;
  onBargeIn?: () => void;
};

// Talking over ZÆNIA: louder than her echo, for about a quarter of a second.
const BARGE_START = 0.04;
const BARGE_CHUNKS = 3;
const BARGE_MAX_SECONDS = 8;

export function useVoiceInput({ onTranscript, paused, bargeIn = false, onBargeIn }: Options) {
  const [mode, setMode] = useState<VoiceMode>("off");
  const [status, setStatus] = useState<VoiceStatus>("off");
  const [error, setError] = useState<string | null>(null);
  const [alwaysWanted, setAlwaysWanted] = useState(() => MIC_SUPPORTED && readPref());
  const alwaysRef = useRef(alwaysWanted);
  useEffect(() => { alwaysRef.current = alwaysWanted; }, [alwaysWanted]);
  // The mic level is written straight to this element's --mic-level, without re-rendering.
  const meterRef = useRef<HTMLElement | null>(null);
  const lastLevel = useRef(-1);
  const setLevel = (value: number) => {
    const rounded = Math.round(value * 10) / 10;
    if (rounded === lastLevel.current) return;
    lastLevel.current = rounded;
    meterRef.current?.style.setProperty("--mic-level", rounded.toFixed(1));
  };

  const modeRef = useRef<VoiceMode>("off");
  const pausedRef = useRef(paused);
  const onTranscriptRef = useRef(onTranscript);
  useEffect(() => { onTranscriptRef.current = onTranscript; }, [onTranscript]);
  const bargeRef = useRef(bargeIn && !IS_IOS);
  useEffect(() => { bargeRef.current = bargeIn && !IS_IOS; }, [bargeIn]);
  const onBargeInRef = useRef(onBargeIn);
  useEffect(() => { onBargeInRef.current = onBargeIn; }, [onBargeIn]);

  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const nodeRef = useRef<ScriptProcessorNode | null>(null);
  const vad = useRef({ speaking: false, barged: false, above: 0, quiet: 0, noise: 0.008, chunks: [] as Float32Array[], preroll: [] as Float32Array[], seconds: 0, waited: 0 });
  const queueRef = useRef<Promise<void>>(Promise.resolve());
  const busyRef = useRef(0);

  const resetVad = () => { const v = vad.current; v.speaking = false; v.barged = false; v.above = 0; v.quiet = 0; v.chunks = []; v.preroll = []; v.seconds = 0; };

  const send = useCallback((chunks: Float32Array[], rate: number, clipMode: VoiceMode, barged = false) => {
    const audio = encodeClip(chunks, rate);
    busyRef.current += 1;
    setStatus("transcribing");
    queueRef.current = queueRef.current.then(async () => {
      try {
        const result = await api<Transcript>("POST", "/api/voice/transcribe", { audio, wake: clipMode === "always" }, { timeoutMs: 60_000 });
        onTranscriptRef.current(result, clipMode, barged);
      } catch (failure) {
        setError(`Voice: ${errorText(failure)}`);
        // Nothing understood: let ZÆNIA carry on at full volume.
        if (barged) onTranscriptRef.current({ text: "", addressed: false, command: "", dismiss: false }, clipMode, true);
      } finally {
        busyRef.current -= 1;
        if (busyRef.current === 0) setStatus(modeRef.current === "off" ? "off" : pausedRef.current ? "paused" : "listening");
      }
    });
  }, []);

  const releaseMic = useCallback(() => {
    sourceRef.current?.disconnect();
    sourceRef.current = null;
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
  }, []);

  const stopAll = useCallback(() => {
    modeRef.current = "off";
    setMode("off");
    releaseMic();
    if (nodeRef.current) { nodeRef.current.onaudioprocess = null; nodeRef.current.disconnect(); nodeRef.current = null; }
    void ctxRef.current?.close().catch(() => undefined);
    ctxRef.current = null;
    resetVad();
    setLevel(0);
    if (busyRef.current === 0) setStatus("off");
  }, [releaseMic]);

  const handleAudio = useCallback((samples: Float32Array, rate: number) => {
    const v = vad.current;
    const seconds = samples.length / rate;
    let energy = 0;
    for (let i = 0; i < samples.length; i++) energy += samples[i] * samples[i];
    const rms = Math.sqrt(energy / samples.length);
    setLevel(Math.min(1, rms * 9));
    const paused = pausedRef.current;
    if (modeRef.current === "off" || (paused && !bargeRef.current)) { resetVad(); return; }
    const copy = new Float32Array(samples);
    // While ZÆNIA speaks, only a clearly louder voice counts (her own echo shouldn't).
    const start = paused ? Math.max(BARGE_START, v.noise * 5) : Math.max(0.014, v.noise * 2.8);
    const stop = v.barged ? Math.max(0.018, v.noise * 3) : Math.max(0.009, v.noise * 1.8);
    if (!v.speaking) {
      v.preroll.push(copy);
      while (v.preroll.length * seconds > PREROLL_SECONDS) v.preroll.shift();
      if (rms > start) v.above += 1;
      else { v.above = 0; if (!paused) v.noise = Math.max(0.002, v.noise * 0.95 + rms * 0.05); }
      if (modeRef.current === "dictate" && !paused) {
        v.waited += seconds;
        if (v.waited > DICTATE_TIMEOUT_SECONDS) { setError("Didn't hear anything. Tap the mic and speak."); if (finishDictation()) setStatus("listening"); return; }
      }
      if (v.above >= (paused ? BARGE_CHUNKS : 2)) {
        v.speaking = true; v.chunks = [...v.preroll]; v.preroll = []; v.seconds = v.chunks.length * seconds; v.quiet = 0;
        setStatus("hearing");
        if (paused) { v.barged = true; onBargeInRef.current?.(); }
      }
      return;
    }
    v.chunks.push(copy);
    v.seconds += seconds;
    v.quiet = rms < stop ? v.quiet + seconds : 0;
    if (v.quiet >= END_SILENCE_SECONDS || v.seconds >= (v.barged ? BARGE_MAX_SECONDS : MAX_SPEECH_SECONDS)) {
      const chunks = v.chunks, spoken = v.seconds - v.quiet, clipMode = modeRef.current, barged = v.barged;
      resetVad();
      if (spoken < MIN_SPEECH_SECONDS) {
        setStatus(busyRef.current ? "transcribing" : pausedRef.current ? "paused" : "listening");
        if (barged) onTranscriptRef.current({ text: "", addressed: false, command: "", dismiss: false }, clipMode, true);
        return;
      }
      send(chunks, rate, clipMode, barged);
      if (clipMode === "dictate") finishDictation();
    }
  }, [send, stopAll]); // eslint-disable-line react-hooks/exhaustive-deps

  // After a dictated request: back to always-listening if it's on, else mic off.
  // Returns true when listening continues.
  function finishDictation(): boolean {
    if (alwaysRef.current && nodeRef.current) { modeRef.current = "always"; setMode("always"); resetVad(); return true; }
    stopAll();
    return false;
  }

  const attachMic = useCallback(async () => {
    const ctx = ctxRef.current, node = nodeRef.current;
    if (!ctx || !node) return;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
    streamRef.current = stream;
    const source = ctx.createMediaStreamSource(stream);
    source.connect(node);
    sourceRef.current = source;
  }, []);

  /** Must run from a tap the first time (phones require it for audio). */
  const start = useCallback(async (next: Exclude<VoiceMode, "off">) => {
    if (!MIC_SUPPORTED) { setError(LIVE_API ? "The microphone needs the secure (https) address of ZÆNIA." : "The microphone works in the desktop and phone apps."); return; }
    setError(null);
    if (modeRef.current !== "off" && nodeRef.current) {
      modeRef.current = next; setMode(next); resetVad(); vad.current.waited = 0;
      if (!streamRef.current) { try { await attachMic(); } catch { /* handled below */ } }
      setStatus(pausedRef.current ? "paused" : "listening");
      return;
    }
    setStatus("starting");
    try {
      const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Context();
      ctxRef.current = ctx;
      const node = ctx.createScriptProcessor(4096, 1, 1);
      node.onaudioprocess = event => handleAudio(event.inputBuffer.getChannelData(0), ctx.sampleRate);
      node.connect(ctx.destination); // silent output; keeps the processor running
      nodeRef.current = node;
      await attachMic();
      if (ctx.state === "suspended") await ctx.resume().catch(() => undefined);
      modeRef.current = next; setMode(next); resetVad(); vad.current.waited = 0;
      setStatus(ctx.state === "running" ? (pausedRef.current ? "paused" : "listening") : "blocked");
    } catch (failure) {
      stopAll();
      const denied = failure instanceof DOMException && (failure.name === "NotAllowedError" || failure.name === "SecurityError");
      setError(denied ? "Microphone access was blocked. Allow the microphone for ZÆNIA, then try again." : `Microphone: ${errorText(failure)}`);
      setStatus("error");
    }
  }, [attachMic, handleAudio, stopAll]);

  const dictate = useCallback(() => {
    if (modeRef.current === "dictate") { if (finishDictation()) setStatus("listening"); return; }
    void start("dictate");
  }, [start]); // eslint-disable-line react-hooks/exhaustive-deps

  const setAlways = useCallback((on: boolean) => {
    writePref(on); setAlwaysWanted(on);
    if (on) void start("always"); else stopAll();
  }, [start, stopAll]);

  // ZÆNIA speaking: ignore the mic so it doesn't hear itself (on the desktop,
  // keep listening for you talking over her). iPhones also release the mic so
  // the reply plays through the speaker, not the earpiece.
  useEffect(() => {
    pausedRef.current = paused;
    if (modeRef.current === "off") return;
    if (paused) {
      if (!bargeRef.current) resetVad();
      if (busyRef.current === 0 && !vad.current.speaking) setStatus("paused");
      if (IS_IOS) releaseMic();
    } else {
      if (IS_IOS && !streamRef.current && nodeRef.current) {
        attachMic().then(() => { if (busyRef.current === 0) setStatus("listening"); })
          .catch(() => setStatus("blocked"));
      } else if (busyRef.current === 0 && !vad.current.speaking) setStatus("listening");
    }
  }, [paused, attachMic, releaseMic]);

  // Remembered "always listening": start when the app opens. If the browser
  // needs a tap first, the next tap anywhere starts it.
  useEffect(() => {
    if (!alwaysWanted || modeRef.current !== "off") return;
    void start("always");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (status !== "blocked") return;
    const resume = () => {
      const ctx = ctxRef.current;
      if (ctx) ctx.resume().then(() => setStatus(pausedRef.current ? "paused" : "listening")).catch(() => undefined);
      else if (alwaysWanted) void start("always");
    };
    // Also retry on a key press or every few seconds, so listening comes
    // back without having to tap the mic button.
    window.addEventListener("pointerdown", resume, { once: true });
    window.addEventListener("keydown", resume, { once: true });
    const retry = window.setInterval(resume, 3000);
    return () => { window.removeEventListener("pointerdown", resume); window.removeEventListener("keydown", resume); window.clearInterval(retry); };
  }, [status, alwaysWanted, start]);

  useEffect(() => () => stopAll(), [stopAll]);

  return { mode, status, error, alwaysWanted, meterRef, dictate, setAlways, stop: stopAll, clearError: () => setError(null), supported: MIC_SUPPORTED, bargeIn: bargeIn && !IS_IOS };
}
