import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "./bridge";

// 20 ms of silence. Playing it inside a tap lets phones play the reply later.
export const SILENT_WAV = "data:audio/wav;base64,UklGRmQBAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YUABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==";

type SpeechReply = { audio: string; mime?: string; seconds?: number };

// The first piece is spoken as soon as a short clause is ready; later pieces wait for whole sentences.
const FIRST_MIN = 24;
const SENTENCE_MIN = 12;
const PIECE_MAX = 240;
const DUCKED_VOLUME = 0.15;

/**
 * Splits off the pieces of `text` that are ready to speak and returns them with
 * the text still waiting for more words. `first` allows an earlier, shorter cut.
 */
export function readyPieces(text: string, first: boolean, final: boolean): { pieces: string[]; rest: string } {
  const pieces: string[] = [];
  let rest = text;
  for (;;) {
    const min = first && pieces.length === 0 ? FIRST_MIN : SENTENCE_MIN;
    let cut = -1;
    // A sentence ends at . ! ? … (with closing quotes/brackets) followed by space, or at a line break.
    const sentence = /[.!?…]+["'”’)\]]*(?=\s)|\n+/g;
    let match: RegExpExecArray | null;
    while ((match = sentence.exec(rest)) !== null) {
      const end = match.index + match[0].length;
      if (rest.slice(0, end).trim().length >= min) { cut = end; break; }
    }
    // Very first piece: a clause break is enough, so ZÆNIA starts talking sooner.
    if (cut < 0 && first && pieces.length === 0) {
      const clause = /[,;:—–]\s/g;
      while ((match = clause.exec(rest)) !== null) {
        if (match.index + 1 >= 48) { cut = match.index + 1; break; }
      }
    }
    // A long stretch without punctuation: cut at a space.
    if (cut < 0 && rest.length > PIECE_MAX) {
      const space = rest.lastIndexOf(" ", PIECE_MAX);
      cut = space > PIECE_MAX / 2 ? space : PIECE_MAX;
    }
    if (cut < 0) break;
    const piece = rest.slice(0, cut).trim();
    rest = rest.slice(cut).replace(/^\s+/, "");
    if (/[\p{L}\p{N}]/u.test(piece)) pieces.push(piece);
  }
  if (final && /[\p{L}\p{N}]/u.test(rest)) { pieces.push(rest.trim()); rest = ""; }
  return { pieces, rest };
}

type Session = {
  gen: number;
  key: string;
  pending: string;
  spoken: string;
  clips: Promise<string | null>[];
  next: number;
  closed: boolean;
  wake: (() => void) | null;
  chain: Promise<unknown>;
  pumping: boolean;
};

/**
 * ZÆNIA's voice in the UI. The server makes WAV audio with the local Piper
 * voice; this hook speaks a reply sentence by sentence, starting while the
 * rest of the reply is still being written, and can be cut off at any time.
 *
 * - speak(key, text): speak a whole reply (Play buttons).
 * - beginReply(key) / feed(key, words) / finishReply(key): speak a reply as it streams in.
 * - stop(): silence immediately.
 */
export function useSpeech() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const genRef = useRef(0);
  const sessionRef = useRef<Session | null>(null);
  const urlsRef = useRef(new Set<string>());
  const finishPlay = useRef<(() => void) | null>(null);
  const duckedRef = useRef(false);
  const lastSpokenRef = useRef({ text: "", at: 0 });
  const [playing, setPlaying] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const element = useCallback(() => {
    if (!audioRef.current) {
      const audio = new Audio();
      audio.preload = "auto";
      audioRef.current = audio;
    }
    return audioRef.current;
  }, []);

  const release = (url: string | null) => {
    if (url && urlsRef.current.delete(url)) URL.revokeObjectURL(url);
  };

  /** Call from a tap or key press so a phone allows the reply to play later. */
  const prime = useCallback(() => {
    if (!LIVE_API) return;
    const audio = element();
    if (!audio.paused) return;
    try {
      audio.src = SILENT_WAV;
      const started = audio.play();
      if (started) started.then(() => { if (!sessionRef.current) audio.pause(); }).catch(() => { /* blocked; the Play button still works */ });
    } catch { /* ignore */ }
  }, [element]);

  const endSession = useCallback((session: Session) => {
    if (sessionRef.current === session) sessionRef.current = null;
    lastSpokenRef.current = { text: session.spoken, at: Date.now() };
    session.wake?.();
  }, []);

  const stop = useCallback(() => {
    genRef.current += 1;
    const session = sessionRef.current;
    if (session) { session.closed = true; endSession(session); }
    duckedRef.current = false;
    const audio = audioRef.current;
    if (audio) { audio.pause(); audio.volume = 1; }
    finishPlay.current?.();
    for (const url of urlsRef.current) URL.revokeObjectURL(url);
    urlsRef.current.clear();
    setPlaying(null);
    setLoading(null);
  }, [endSession]);

  const synthesize = useCallback(async (text: string, gen: number): Promise<string | null> => {
    const reply = await api<SpeechReply>("POST", "/api/speak", { text: text.slice(0, 1200) }, { timeoutMs: 60_000 });
    if (gen !== genRef.current) return null;
    const bytes = Uint8Array.from(atob(reply.audio), char => char.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: reply.mime || "audio/wav" }));
    urlsRef.current.add(url);
    return url;
  }, []);

  /** Plays one clip; resolves when it ends or is stopped. */
  const playClip = useCallback((url: string) => new Promise<void>((resolve, reject) => {
    const audio = element();
    const done = () => {
      audio.removeEventListener("ended", done);
      audio.removeEventListener("error", done);
      if (finishPlay.current === done) finishPlay.current = null;
      resolve();
    };
    audio.addEventListener("ended", done);
    audio.addEventListener("error", done);
    finishPlay.current = done;
    audio.src = url;
    audio.volume = duckedRef.current ? DUCKED_VOLUME : 1;
    audio.play().catch(failure => { done(); reject(failure); });
  }), [element]);

  const pump = useCallback(async (session: Session) => {
    if (session.pumping) return;
    session.pumping = true;
    const current = () => session.gen === genRef.current;
    try {
      while (current()) {
        if (session.next >= session.clips.length) {
          if (session.closed) break;
          await new Promise<void>(resolve => { session.wake = resolve; });
          session.wake = null;
          continue;
        }
        const clip = session.clips[session.next++];
        let url: string | null = null;
        try { url = await clip; }
        catch (failure) { if (current()) setError(`Voice: ${errorText(failure)}`); continue; }
        if (!current() || !url) { release(url); continue; }
        setLoading(null);
        setPlaying(session.key);
        try { await playClip(url); }
        catch (failure) {
          if (current()) {
            setError(failure instanceof DOMException && failure.name === "NotAllowedError"
              ? "Tap Play to hear this reply; the phone blocked automatic audio."
              : `Voice: ${errorText(failure)}`);
          }
          release(url);
          break;
        }
        release(url);
      }
    } finally {
      if (current()) {
        endSession(session);
        duckedRef.current = false;
        if (audioRef.current) audioRef.current.volume = 1;
        setPlaying(null);
        setLoading(null);
      }
    }
  }, [endSession, playClip]);

  const queuePieces = useCallback((session: Session, pieces: string[]) => {
    for (const piece of pieces) {
      session.spoken += (session.spoken ? " " : "") + piece;
      // One request at a time: the next sentence is made while this one plays.
      const clip = session.chain.then(() => session.gen === genRef.current ? synthesize(piece, session.gen) : null);
      session.chain = clip.catch(() => undefined);
      session.clips.push(clip);
    }
    if (pieces.length) { session.wake?.(); void pump(session); }
  }, [pump, synthesize]);

  /** Start speaking a reply that is still streaming in. Stops anything playing. */
  const beginReply = useCallback((key: string) => {
    stop();
    const session: Session = { gen: genRef.current, key, pending: "", spoken: "", clips: [], next: 0, closed: false, wake: null, chain: Promise.resolve(), pumping: false };
    sessionRef.current = session;
    setError(null);
    setLoading(key);
  }, [stop]);

  /** More words of the streaming reply. */
  const feed = useCallback((key: string, words: string) => {
    const session = sessionRef.current;
    if (!session || session.key !== key || session.closed) return;
    session.pending += words;
    const { pieces, rest } = readyPieces(session.pending, session.clips.length === 0, false);
    session.pending = rest;
    queuePieces(session, pieces);
  }, [queuePieces]);

  /** The reply is complete: speak what's left. */
  const finishReply = useCallback((key: string) => {
    const session = sessionRef.current;
    if (!session || session.key !== key || session.closed) return;
    const { pieces } = readyPieces(session.pending, session.clips.length === 0, true);
    session.pending = "";
    queuePieces(session, pieces);
    session.closed = true;
    if (session.clips.length === 0) {
      endSession(session);
      setLoading(null);
      return;
    }
    session.wake?.();
    void pump(session);
  }, [endSession, pump, queuePieces]);

  /** Speak a whole reply (Play buttons); the first sentence starts quickly. */
  const speak = useCallback(async (key: string, text: string) => {
    beginReply(key);
    feed(key, text.slice(0, 8000));
    finishReply(key);
  }, [beginReply, feed, finishReply]);

  /** Lower ZÆNIA's voice while you might be talking over her. */
  const duck = useCallback((on: boolean) => {
    duckedRef.current = on && sessionRef.current !== null;
    const audio = audioRef.current;
    if (audio) audio.volume = duckedRef.current ? DUCKED_VOLUME : 1;
  }, []);

  /** What ZÆNIA is saying (or said in the last few seconds): to ignore her own voice on the mic. */
  const recentText = useCallback((withinMs = 4000): string => {
    const session = sessionRef.current;
    if (session) return session.spoken + " " + session.pending;
    return Date.now() - lastSpokenRef.current.at <= withinMs ? lastSpokenRef.current.text : "";
  }, []);

  useEffect(() => () => {
    genRef.current += 1;
    audioRef.current?.pause();
    for (const url of urlsRef.current) URL.revokeObjectURL(url);
    urlsRef.current.clear();
  }, []);

  return { playing, loading, error, speak, stop, prime, beginReply, feed, finishReply, duck, recentText, clearError: () => setError(null) };
}
