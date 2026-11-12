import { useEffect, useRef, useState } from "react";
import { api, errorText } from "../../core/bridge";
import { encodeClip } from "../../core/voiceInput";

const CHUNK_SECONDS = 6;

/**
 * Record a live transcript into a note: the mic is turned into text on this PC every few seconds and each piece is
 * handed to onText. Any speaker (a lecture, a meeting, you thinking out loud); words only, never a command.
 */
export function LiveTranscript({ onText, disabled }: { onText: (text: string) => void; disabled?: boolean }) {
  const [on, setOn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  const parts = useRef<{ ctx: AudioContext; stream: MediaStream; node: ScriptProcessorNode; chunks: Float32Array[]; seconds: number } | null>(null);
  const textRef = useRef(onText);
  useEffect(() => { textRef.current = onText; }, [onText]);
  const queue = useRef(Promise.resolve());

  const flush = (final = false) => {
    const current = parts.current;
    if (!current || !current.chunks.length) return;
    const chunks = current.chunks;
    current.chunks = []; current.seconds = 0;
    const audio = encodeClip(chunks, current.ctx.sampleRate);
    queue.current = queue.current.then(async () => {
      try {
        const reply = await api<{ text: string }>("POST", "/api/voice/dictation", { audio, wake: false }, { timeoutMs: 60_000 });
        if (reply.text.trim()) textRef.current(reply.text.trim());
      } catch (failure) { if (final || !error) setError(errorText(failure)); }
    });
  };

  const stop = () => {
    const current = parts.current;
    if (!current) return;
    flush(true);
    current.node.disconnect();
    current.stream.getTracks().forEach(track => track.stop());
    void current.ctx.close();
    parts.current = null;
    setOn(false); setLevel(0);
  };

  const start = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const node = ctx.createScriptProcessor(4096, 1, 1);
      parts.current = { ctx, stream, node, chunks: [], seconds: 0 };
      node.onaudioprocess = event => {
        const current = parts.current;
        if (!current) return;
        const data = new Float32Array(event.inputBuffer.getChannelData(0));
        current.chunks.push(data);
        current.seconds += data.length / ctx.sampleRate;
        let sum = 0; for (let i = 0; i < data.length; i += 16) sum += data[i] * data[i];
        setLevel(Math.min(1, Math.sqrt(sum / (data.length / 16)) * 8));
        if (current.seconds >= CHUNK_SECONDS) flush();
      };
      source.connect(node); node.connect(ctx.destination);
      setOn(true);
    } catch (failure) { setError(`Microphone: ${errorText(failure)}`); }
  };

  useEffect(() => () => stop(), []); // eslint-disable-line react-hooks/exhaustive-deps

  return <span className="live-transcript">
    <button type="button" disabled={disabled && !on} className={on ? "live-transcript__btn live-transcript__btn--on" : "live-transcript__btn"}
      onClick={() => (on ? stop() : void start())} title="Turns speech into text on this PC and adds it to the note as it goes">
      {on ? "■ Stop recording" : "● Record live transcript"}</button>
    {on && <i className="live-transcript__level" style={{ width: `${Math.round(level * 60) + 6}px` }} aria-hidden="true"/>}
    {on && <small>Listening… text is added every few seconds.</small>}
    {error && <small className="live-transcript__error">{error}</small>}
  </span>;
}
