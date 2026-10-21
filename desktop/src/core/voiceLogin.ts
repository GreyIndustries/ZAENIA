import { encodeClip } from "./voiceInput";

export type VoiceRecording = { finish: () => string; cancel: () => void };

/** Captures only after a tap. Audio stays in memory and tracks stop on every exit. */
export async function recordLoginVoice(signal: AbortSignal): Promise<VoiceRecording> {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    throw new Error("Open Zae at its secure https address to use voice sign-in.");
  }
  const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const context = new Context();
  let stream: MediaStream | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  let node: ScriptProcessorNode | null = null;
  let chunks: Float32Array[] = [];
  let samples = 0;
  let stopped = false;
  const cancel = () => {
    if (stopped) return;
    stopped = true;
    if (node) { node.onaudioprocess = null; node.disconnect(); }
    source?.disconnect();
    stream?.getTracks().forEach(track => track.stop());
    void context.close().catch(() => undefined);
    signal.removeEventListener("abort", cancel);
  };
  signal.addEventListener("abort", cancel, { once: true });
  try {
    if (signal.aborted) throw new Error("Voice check cancelled.");
    await context.resume();
    stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }, video: false });
    if (signal.aborted || stopped) { stream.getTracks().forEach(track => track.stop()); throw new Error("Voice check cancelled."); }
    source = context.createMediaStreamSource(stream);
    node = context.createScriptProcessor(4096, 1, 1);
    node.onaudioprocess = event => {
      if (samples >= context.sampleRate * 14) return;
      const chunk = new Float32Array(event.inputBuffer.getChannelData(0));
      chunks.push(chunk); samples += chunk.length;
    };
    source.connect(node);
    node.connect(context.destination);
    if (context.state !== "running") throw new Error("Tap Record again to allow microphone audio.");
    return {
      finish: () => {
        if (stopped) throw new Error("The voice recording was cancelled. Start again.");
        cancel();
        if (samples < context.sampleRate * 2) { chunks = []; throw new Error("Say all six words before tapping Verify voice."); }
        const encoded = encodeClip(chunks, context.sampleRate);
        chunks = [];
        return encoded;
      },
      cancel: () => { cancel(); chunks = []; },
    };
  } catch (error) { cancel(); chunks = []; throw error; }
}
