import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ChangeEvent, ClipboardEvent, DragEvent, FormEvent, KeyboardEvent, RefObject } from "react";
import { calendarWhenLabel, taskDeadlineLabel } from "../../core/assistantActions";
import type { AssistantActionState, AssistantProposal } from "../../core/assistantActions";
import "./HomeConversation.css";
import { preparePhoto } from "../../core/photos";
import type { ChatPhoto } from "../../core/photos";
import { fileSize, MAX_SHARED_FILES, readSharedFile } from "../../core/sharedFiles";
import type { ChatFile } from "../../core/sharedFiles";

export type ChatSource = { id?: string; title?: string; url?: string; path?: string; source_type?: string; excerpt?: string };
export type ChatMessage = { id: number; role: "user" | "assistant" | "error"; text: string; photos?: ChatPhoto[]; files?: string[]; sources?: ChatSource[]; at?: string; history?: boolean; streaming?: boolean; interrupted?: boolean; proposal?: AssistantProposal; action?: AssistantActionState };
export type HistoryState = "preview" | "loading" | "ready" | "unavailable";
export type ListenProps = {
  supported: boolean;
  mode: "off" | "dictate" | "always";
  status: "off" | "starting" | "listening" | "hearing" | "transcribing" | "paused" | "blocked" | "error";
  alwaysWanted: boolean;
  toggleAlways: () => void;
  dictate: () => void;
  meterRef: RefObject<HTMLElement | null>;
  note: string | null;
  error: string | null;
  followUp: boolean;
  /** No wake word: ZÆNIA hears everything and decides what is meant for her. */
  openMic?: boolean;
  /** Desktop: talking over ZÆNIA while she speaks cuts her off. */
  bargeIn: boolean;
  /** ZÆNIA's PC voice service (verified voice on the PC microphone). */
  pc: { running: boolean; state: string } | null;
  pcTakesOver: boolean;
  canStartPc: boolean;
  startPc: () => void;
};

type Props = {
  photos: ChatPhoto[];
  onPhotos: (photos: ChatPhoto[]) => void;
  files: ChatFile[];
  onFiles: (files: ChatFile[]) => void;
  messages: ChatMessage[];
  sending: boolean;
  /** ZÆNIA is writing or speaking: the Stop button (and Esc) cut her off. */
  busy: boolean;
  onStop: () => void;
  /** The reply currently streaming in, once its first words arrive. */
  streamingId: number | null;
  query: string;
  onQuery: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  live: boolean;
  history: HistoryState;
  voice: {
    available: boolean; on: boolean; toggle: () => void;
    playing: string | null; loading: string | null; error: string | null;
    play: (key: string, text: string) => void; stop: () => void;
  };
  listen: ListenProps;
  historyError?: string | null;
  onApplyProposal: (messageId: number) => void;
  onDismissProposal: (messageId: number) => void;
};

function EarIcon() {
  // A sound wave: "listening".
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4"/>
  </svg>;
}
function StopIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2.5" fill="currentColor"/></svg>;
}
function FileIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/></svg>;
}

function MicIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/>
  </svg>;
}

const listenText = (listen: ListenProps): string | null => {
  if (listen.status === "error") return "Microphone unavailable";
  if (listen.status === "blocked") return "Tap anywhere to turn the microphone on";
  if (listen.status === "starting") return "Starting the microphone…";
  return listen.pcTakesOver || listen.mode !== "off" ? "Listening" : null;
};

const clock = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  const today = new Date().toDateString() === date.toDateString();
  return today ? date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : date.toLocaleDateString([], { month: "short", day: "numeric" }) + " " + date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
};

function SpeakerIcon({ on }: { on: boolean }) {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/>
    {on ? <><path d="M15.5 9a4 4 0 0 1 0 6"/><path d="M18 6.5a7.5 7.5 0 0 1 0 11"/></> : <path d="m16 9.5 5 5m0-5-5 5"/>}
  </svg>;
}

function ActionCard({ message, live, onApply, onDismiss }: { message: ChatMessage; live: boolean; onApply: (id: number) => void; onDismiss: (id: number) => void }) {
  const proposal = message.proposal;
  if (!proposal) return null;
  const status = message.action?.status ?? "ready";
  const disabled = !live || Boolean(message.streaming || message.interrupted) || !["ready", "failed"].includes(status);
  const task = proposal.kind === "task.create";
  const memory = proposal.kind.startsWith("memory.");
  const label = proposal.kind === "app.launch" ? "Open registered target" : proposal.kind === "workspace.restore" ? "Restore workspace" : task ? "Create task" : proposal.kind === "calendar.create" ? "Add to calendar" : proposal.kind === "memory.remember" ? "Remember this" : "Forget this memory";
  return <section className={`message-action message-action--${status}`} aria-label={`Review ${memory ? "personal memory" : task ? "task" : "calendar event"}`} aria-busy={status === "pending"}>
    <span className="message-action__eyebrow">{status === "succeeded" ? "SAVED ON YOUR PC" : status === "dismissed" ? "DISMISSED" : status === "expired" ? "START TIME HAS PASSED" : "REVIEW BEFORE SAVING"}</span>
    <strong>{proposal.kind === "memory.remember" || proposal.kind === "memory.forget" ? proposal.parameters.key : proposal.kind === "app.launch" || proposal.kind === "workspace.restore" ? proposal.parameters.name : proposal.parameters.title}</strong>
    <dl>
      {proposal.kind === "task.create" ? <>
        <div><dt>Priority</dt><dd>{proposal.parameters.priority}</dd></div>
        <div><dt>Due</dt><dd>{proposal.parameters.deadline ? taskDeadlineLabel(proposal.parameters.deadline) : "No deadline"}</dd></div>
      </> : proposal.kind === "calendar.create" ? <>
        <div><dt>When</dt><dd>{calendarWhenLabel(proposal.parameters.date, proposal.parameters.time)}</dd></div>
        <div><dt>Repeat</dt><dd>{proposal.parameters.recurrence === "none" ? "Once" : proposal.parameters.recurrence === "daily" ? "Daily" : "Weekly"}</dd></div>
      </> : proposal.kind === "memory.remember" ? <>
        <div><dt>Category</dt><dd>{proposal.parameters.category}</dd></div>
        <div><dt>Value</dt><dd>{proposal.parameters.value}</dd></div>
      </> : proposal.kind === "memory.forget" ? <div><dt>Action</dt><dd>Remove this exact key from saved personal memory</dd></div> : <div><dt>Action</dt><dd>{proposal.kind === "app.launch" ? "Open this previously registered local target" : "Restore the saved layout and open its registered apps"}</dd></div>}
    </dl>
    <small>{memory ? "Saved locally on your PC. Review and correct personal memory in Assistant." : "Follow-through appears in the Assistant inbox when enabled. Speech is optional."}</small>
    <div className="message-action__buttons">
      <button type="button" onClick={() => onApply(message.id)} disabled={disabled}>{status === "pending" ? "Saving…" : status === "succeeded" ? "Saved" : status === "expired" ? "Time passed" : label}</button>
      <button type="button" onClick={() => onDismiss(message.id)} disabled={disabled}>Dismiss</button>
    </div>
    {message.action?.detail && <p className="message-action__status" role="status">{message.action.detail}</p>}
    {!live && <p className="message-action__status">Saving needs the desktop app or the connected phone app.</p>}
  </section>;
}

// Floating conversation: no chat panel. Recent lines hover over the UI and
// fade with age; focusing the input brings the last few back.
const FLOAT_LINES = 6;
const FADE_START_MS = 20_000;
const FADE_END_MS = 60_000;
const ageOf = (message: ChatMessage, now: number) => {
  const at = message.at ? Date.parse(message.at) : NaN;
  return Number.isFinite(at) ? Math.max(0, now - at) : 0;
};

/**
 * Talk to ZÆNIA from any page: an input bar plus a transparent, fading
 * transcript floating above it. Recent memory still loads on the PC.
 */
export function HomeConversation({ photos, onPhotos, files, onFiles, messages, sending, busy, onStop, streamingId, query, onQuery, onSubmit, inputRef, live, history, voice, listen, historyError, onApplyProposal, onDismissProposal }: Props) {
  const photoInput = useRef<HTMLInputElement>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);
  // Photos go to her photo model; every other file is read and discussed as text.
  async function attach(chosen: FileList | File[] | null) {
    const list = Array.from(chosen ?? []);
    if (!list.length || preparing) return;
    setPhotoError(null); setPreparing(true);
    try {
      const images = list.filter(file => ['image/jpeg', 'image/png', 'image/webp'].includes(file.type));
      const others = list.filter(file => !images.includes(file));
      if (images.length + photos.length > 4) throw new Error('Choose up to four photos. Remove one to add another.');
      if (others.length + files.length > MAX_SHARED_FILES) throw new Error(`Share up to ${MAX_SHARED_FILES} files at a time. Remove one to add another.`);
      const [addedPhotos, addedFiles] = await Promise.all([Promise.all(images.map(preparePhoto)), Promise.all(others.map(readSharedFile))]);
      if (addedPhotos.length) onPhotos([...photos, ...addedPhotos]);
      if (addedFiles.length) onFiles([...files, ...addedFiles]);
    } catch (error) { setPhotoError(error instanceof Error ? error.message : 'This file could not be opened.'); }
    finally { setPreparing(false); if (photoInput.current) photoInput.current.value = ''; }
  }
  const [dragging, setDragging] = useState(false);
  const onDrop = (event: DragEvent<HTMLElement>) => {
    if (!event.dataTransfer?.files?.length) return;
    event.preventDefault(); setDragging(false);
    void attach(event.dataTransfer.files);
  };
  const onDragOver = (event: DragEvent<HTMLElement>) => {
    if (!Array.from(event.dataTransfer?.types ?? []).includes("Files")) return;
    event.preventDefault(); if (!dragging) setDragging(true);
  };
  const onPaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const pasted = Array.from(event.clipboardData?.files ?? []);
    if (!pasted.length) return;
    event.preventDefault(); void attach(pasted);
  };
  // Up arrow brings back your earlier messages (newest first), down goes forward again, like a terminal.
  const recall = useRef(-1);
  const unsent = useRef("");
  useEffect(() => { recall.current = -1; }, [messages.length]);
  // The box grows with what you type (up to about ten lines); Enter sends, Shift+Enter starts a new line.
  useLayoutEffect(() => {
    const box = inputRef.current;
    if (!box) return;
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, 240)}px`;
  }, [query, inputRef]);
  const recallKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
      return;
    }
    if ((event.key !== "ArrowUp" && event.key !== "ArrowDown") || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    // In a multi-line message the arrows move between lines; history only from the first or last line.
    const box = event.currentTarget;
    if (event.key === "ArrowUp" && box.value.slice(0, box.selectionStart).includes("\n")) return;
    if (event.key === "ArrowDown" && box.value.slice(box.selectionEnd).includes("\n")) return;
    const sent = messages.filter(message => message.role === "user" && message.text.trim()).map(message => message.text).reverse();
    if (!sent.length) return;
    const next = event.key === "ArrowUp" ? Math.min(recall.current + 1, sent.length - 1) : recall.current - 1;
    if (event.key === "ArrowDown" && recall.current < 0) return;
    event.preventDefault();
    if (recall.current < 0) unsent.current = query;
    recall.current = next;
    const text = next < 0 ? unsent.current : sent[next];
    onQuery(text);
    requestAnimationFrame(() => { const input = event.currentTarget ?? inputRef.current; input?.setSelectionRange?.(text.length, text.length); });
  };
  const logRef = useRef<HTMLDivElement | null>(null);
  const shownCount = useRef(0);
  const pinnedReply = useRef(-1);
  const tail = messages.length ? messages[messages.length - 1].text.length : 0;
  // New messages scroll into view; a streaming reply follows along unless you scrolled up to read.
  // A reply taller than the space stays pinned at its first line, so you read it from the start.
  useEffect(() => {
    const log = logRef.current;
    if (!log) return;
    const added = messages.length !== shownCount.current;
    shownCount.current = messages.length;
    const last = log.lastElementChild as HTMLElement | null;
    if (last && last.offsetHeight > log.clientHeight - 8) {
      if (pinnedReply.current !== messages.length) { pinnedReply.current = messages.length; log.scrollTop = last.offsetTop - 4; }
      return;
    }
    if (added || log.scrollHeight - log.scrollTop - log.clientHeight < 140) log.scrollTop = log.scrollHeight;
  }, [messages.length, tail, sending, history]);

  const label = (role: ChatMessage["role"]) => role === "user" ? "YOU" : role === "assistant" ? "ZÆNIA" : "BRIDGE ERROR";
  const [now, setNow] = useState(() => Date.now());
  const [peek, setPeek] = useState(false);
  // History: the whole conversation (earlier sessions too), scrollable, nothing fading, every message copyable.
  const [browsing, setBrowsing] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);
  const copy = (message: ChatMessage) => {
    void navigator.clipboard?.writeText(message.text).then(() => { setCopied(message.id); window.setTimeout(() => setCopied(current => current === message.id ? null : current), 1500); });
  };
  useEffect(() => {
    if (!browsing) return;
    const close = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") setBrowsing(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [browsing]);
  useEffect(() => { if (browsing && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [browsing]);
  const recent = browsing ? messages : messages.filter(message => !message.history).slice(-FLOAT_LINES);
  // A line stays while it streams, is being spoken, or still needs a decision.
  const pinned = (message: ChatMessage) => Boolean(message.streaming) || voice.playing === `m${message.id}` || voice.loading === `m${message.id}`
    || (Boolean(message.proposal) && ["ready", "failed", "pending"].includes(message.action?.status ?? "ready"));
  const opacity = (message: ChatMessage) => {
    if (browsing || peek || pinned(message)) return 1;
    const age = ageOf(message, now);
    return age <= FADE_START_MS ? 1 : Math.max(0, 1 - (age - FADE_START_MS) / (FADE_END_MS - FADE_START_MS));
  };
  const fading = recent.some(message => ageOf(message, now) < FADE_END_MS + 1000);
  useEffect(() => {
    if (!fading) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [fading, messages.length]);
  useEffect(() => { setNow(Date.now()); }, [messages.length]);
  const strip = listenText(listen);
  const listening = listen.mode !== "off" || listen.pcTakesOver;
  return <section onDragOver={onDragOver} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false); }} onDrop={onDrop}
    className={`home-chat home-chat--float${dragging ? " home-chat--drop" : ""}${peek ? " home-chat--peek" : ""}${listen.mode !== "off" ? " home-chat--mic" : ""}${listen.status === "hearing" ? " home-chat--hearing" : ""}`}
    aria-label="Conversation with ZÆNIA" ref={listen.meterRef as RefObject<HTMLElement>}
    onFocus={() => setPeek(true)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setPeek(false); }}>
    <header className="home-chat__head">
      {messages.length > 0 && <button type="button" className={`home-chat__voice${browsing ? " home-chat__voice--on" : ""}`} aria-pressed={browsing}
        onClick={() => setBrowsing(value => !value)} title={browsing ? "Close the conversation history (Esc)" : "Scroll through the whole conversation and copy any message"}>
        <span aria-hidden="true">☰</span><span>{browsing ? "Close history" : "History"}</span>
      </button>}
      {listen.supported && <button type="button" className={`home-chat__voice home-chat__listen${listening ? " home-chat__voice--on" : ""}`}
        aria-pressed={listen.alwaysWanted || listen.pcTakesOver} onClick={listen.toggleAlways} disabled={listen.pcTakesOver}
        aria-label={listen.pcTakesOver ? "PC voice service is listening" : listen.alwaysWanted ? "Stop listening" : listen.openMic ? "Start listening" : "Listen for ZAE"}
        title={listen.pcTakesOver ? "The PC voice service is listening on this PC" : listen.alwaysWanted ? "ZÆNIA is listening while this app is open. Tap to stop." : listen.openMic ? "ZÆNIA listens while this app is open and decides what's meant for her; no name needed" : "Use ZAE anywhere in a request, or say “hey assistant”, while this app is open"}>
        <EarIcon/><span>{listen.pcTakesOver ? "PC voice on" : listen.alwaysWanted ? "Listening" : "Listen"}</span>
      </button>}
      {voice.available && <button type="button" className={`home-chat__voice${voice.on ? " home-chat__voice--on" : ""}`}
        aria-pressed={voice.on} onClick={voice.toggle} title={voice.on ? "ZÆNIA speaks each reply. Tap to turn off." : "Turn on spoken replies"}>
        <SpeakerIcon on={voice.on}/><span>{voice.on ? "Voice on" : "Voice off"}</span>
      </button>}
    </header>
    {(strip || listen.canStartPc) && <div className="home-chat__strip" role="status">
      {strip && <><span className={`home-chat__dot${listen.status === "hearing" || listen.pc?.state === "hearing" ? " home-chat__dot--hot" : ""}`} aria-hidden="true"/>
        <span>{strip}</span>
        {listen.mode !== "off" && <span className="home-chat__meter" aria-hidden="true"><i/></span>}</>}
      {listen.canStartPc && <button type="button" className="home-chat__pc" onClick={listen.startPc}
        title="Opens the ZÆNIA Voice window on this PC. Enter your passkey there.">Start PC voice</button>}
    </div>}
    <div className={`home-chat__log${browsing ? " home-chat__log--browse" : ""}`} ref={logRef} role="log" aria-live="polite" aria-busy={sending || history === "loading"}>
      {history === "unavailable" && peek && <p className="home-chat__note">Earlier conversation couldn't be loaded{historyError ? `: ${historyError}` : "."}</p>}
      {recent.map(message => {
        const key = `m${message.id}`;
        const alpha = opacity(message);
        if (alpha <= 0) return null;
        return <div key={message.id} className={`message message--${message.role}${message.streaming ? " message--streaming" : ""}`} style={{ opacity: alpha }}>
          <span>{label(message.role)}{message.at && <time dateTime={message.at}>{clock(message.at)}</time>}{message.interrupted && <em className="message__cut">STOPPED</em>}</span>
          <p>{message.text}{message.streaming && <i className="message__caret" aria-hidden="true"/>}</p>
          {!!message.sources?.length && <div className="message__sources"><small>Sources</small>{message.sources.map((source, index) => <div key={`${source.id ?? index}-${source.url ?? source.path ?? ""}`}>
            {source.url?.startsWith("https://") ? <a href={source.url} target="_blank" rel="noreferrer">[{source.id ?? index + 1}] {source.title || source.url}</a> : <span>[{source.id ?? index + 1}] {source.title || source.path || "Local evidence"}</span>}
          </div>)}</div>}
          {message.files && <div className="message__files">{message.files.map((name, index) => <span key={index} className="message__file"><FileIcon/>{name}</span>)}</div>}
          {message.photos && <div className="message__photos">{message.photos.map((photo, index) => <img key={index} src={photo.data} alt={photo.name}/>)}</div>}
          {message.role === "assistant" && <ActionCard message={message} live={live} onApply={onApplyProposal} onDismiss={onDismissProposal}/>}
          {!message.streaming && (peek || browsing) && message.text.trim() && <button type="button" className="message__play message__copy"
            onClick={() => copy(message)} aria-label="Copy this message">{copied === message.id ? "✓ Copied" : "Copy"}</button>}
          {message.role === "assistant" && voice.available && !message.streaming && (peek || browsing) && <button type="button" className="message__play"
            onClick={() => voice.playing === key ? voice.stop() : voice.play(key, message.text)}
            aria-label={voice.playing === key ? "Stop speaking" : "Speak this reply"} disabled={voice.loading !== null && voice.loading !== key}>
            {voice.loading === key ? "Preparing voice…" : voice.playing === key ? "■ Stop" : "▶ Play"}
          </button>}
        </div>;
      })}
      {sending && streamingId === null && <div className="message message--assistant message--pending"><span>ZÆNIA</span><p>Thinking…</p></div>}
    </div>
    {voice.error && <p className="home-chat__error" role="status">{voice.error}</p>}
    {(listen.error || listen.note) && <p className={listen.error ? "home-chat__error" : "home-chat__hint"} role="status">{listen.error ?? listen.note}</p>}
    {photoError && <p className="home-chat__error" role="alert">{photoError}</p>}
    {photos.length > 0 && <div className="home-chat__photos" aria-label="Photos for Zae">
      <div className="home-chat__photo-list">{photos.map((photo, index) => <div key={index} className="home-chat__photo">
        <img src={photo.data} alt={photo.name}/><button type="button" aria-label={`Remove photo ${index + 1}`} onClick={() => onPhotos(photos.filter((_, i) => i !== index))} disabled={sending || preparing}>×</button>
      </div>)}</div>
      <span>Ask about these photos by typing or speaking. Photos stay for follow-up questions.</span>
      <button type="button" onClick={() => onPhotos([])} disabled={sending || preparing}>Done with photos</button>
    </div>}
    {files.length > 0 && <div className="home-chat__photos home-chat__files" aria-label="Files for Zae">
      <div className="home-chat__file-list">{files.map((file, index) => <span key={index} className="home-chat__file"><FileIcon/>
        <span>{file.name}<small>{fileSize(file.size)}</small></span>
        <button type="button" aria-label={`Remove ${file.name}`} onClick={() => onFiles(files.filter((_, i) => i !== index))} disabled={sending || preparing}>×</button>
      </span>)}</div>
      <span>Ask about these files by typing or speaking. They stay for follow-up questions, and a copy is kept on your PC.</span>
      <button type="button" onClick={() => onFiles([])} disabled={sending || preparing}>Done with files</button>
    </div>}
    {dragging && <div className="home-chat__dropzone" aria-hidden="true">Drop files to share them with ZAE</div>}
    <form className="chat-dock home-chat__composer" onSubmit={onSubmit}>
      <input ref={photoInput} type="file" multiple hidden aria-label="Choose files or photos" onChange={event => void attach(event.target.files)}/>
      <button type="button" className="home-chat__attach" aria-label="Share files or photos with Zae" title="Share files or photos (or drag them here, or paste)" disabled={sending || preparing || (photos.length >= 4 && files.length >= MAX_SHARED_FILES)} onClick={() => photoInput.current?.click()}>{preparing ? '…' : <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m21.4 11.6-8.5 8.5a5.5 5.5 0 0 1-7.8-7.8l8.5-8.5a3.7 3.7 0 0 1 5.2 5.2l-8.5 8.5a1.8 1.8 0 0 1-2.6-2.6l7.8-7.8"/></svg>}</button>
      <span className="chat-dock__mark" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M5 4h14a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H9l-5 4v-4H3V6a2 2 0 0 1 2-2Z"/></svg></span>
      <label htmlFor="zaenia-query" className="sr-only">Ask ZÆNIA</label>
      <textarea id="zaenia-query" ref={inputRef} rows={1} value={query} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => { recall.current = -1; onQuery(event.target.value); }} onPaste={onPaste} onKeyDown={recallKey}
        placeholder={listen.mode === "dictate" ? "Listening…" : busy ? "Type to interrupt, or press Esc to stop" : "Ask ZÆNIA anything…"} autoComplete="off" maxLength={4000} enterKeyHint="send"/>
      {listen.supported && <button type="button" className={`home-chat__mic${listen.mode === "dictate" ? " home-chat__mic--on" : ""}`}
        onClick={listen.dictate} aria-pressed={listen.mode === "dictate"}
        aria-label={listen.mode === "dictate" ? "Stop listening" : "Speak to ZÆNIA"} title={listen.mode === "dictate" ? "Stop listening" : "Speak to ZÆNIA"}>
        <MicIcon/>
      </button>}
      {busy && !query.trim()
        ? <button type="button" className="home-chat__stop" onClick={onStop} aria-label="Stop ZÆNIA" title="Stop ZÆNIA (Esc)"><StopIcon/></button>
        : <button type="submit" disabled={preparing || (!query.trim() && !photos.length && !files.length)} aria-label="Send message to ZÆNIA" title={busy ? "Stop ZÆNIA and send this instead" : "Send message to ZÆNIA"}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
        </button>}
    </form>
  </section>;
}
