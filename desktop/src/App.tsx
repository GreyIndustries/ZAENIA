import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, FormEvent, ReactNode } from "react";
import { SystemProgressCore } from "./components/core/SystemProgressCore";
import { NeuralCore } from "./components/core/NeuralCore";
import { CoreBackdrop } from "./components/core/CoreBackdrop";
import { useWorkspaceMotion, WorkspaceMotionControls } from "./components/core/WorkspaceMotion";
import { workspacePhase } from "./core/workspaceDynamics";
import { usePlatformRuntime } from "./core/usePlatformRuntime";
import { PlatformPanel, BackgroundWorkBadge } from "./components/assistant/PlatformPanel";
import { HandControls } from "./components/shell/HandControls";
import type { GestureCommand } from "./core/handGestures";
import type { ShellWindow } from "./components/shell/WindowShell";
import { parseCoreTelemetry, PREVIEW_TELEMETRY } from "./core/coreTelemetry";
import { checkPhoneConnection, connectGmail, connectGoogleCalendar, disconnectPhone, openVoiceTraining, restartServer, startServer } from "./core/bridge";
import { api, askZaenia, BridgeError, canGoLive, errorText, forgetToken, IN_TAURI, LIVE_API, readStatus, savedToken, startVoiceService, streamChat, streamUnsupported, WEB_APP } from "./core/bridge";
import type { ChatStream } from "./core/bridge";
import { assistantProposalExpired, confirmedAssistantAction, parseAssistantProposal } from "./core/assistantActions";
import type { AssistantActionState, AssistantProposal } from "./core/assistantActions";
import { PhoneConnect } from "./components/phone/PhoneConnect";
import { BrowserBriefing } from "./components/phone/BrowserBriefing";
import { HomeConversation } from "./components/chat/HomeConversation";
import type { ChatPhoto } from "./core/photos";
import type { ChatFile } from "./core/sharedFiles";
import type { ChatMessage, HistoryState } from "./components/chat/HomeConversation";
import { useSpeech } from "./core/speech";
import { useVoiceInput } from "./core/voiceInput";
import type { Transcript, VoiceMode } from "./core/voiceInput";
import { acceptsVoiceTurn, FOLLOW_UP_MS, isQuietVoiceAcknowledgement } from "./core/voiceAttention";
import { ZAENIA_IDENTITY_DESCRIPTION, ZAENIA_IDENTITY_REPLY, isZaeniaIdentityQuestion } from "./core/identity";
import type { CoreTelemetry, ModulePhase } from "./core/coreTelemetry";
import { SECURITY_CHECK_EVENT } from "./components/status/SecurityChecks";
import { NotesPanel, EMPTY_NOTES_DRAFT } from './components/notes/NotesPanel';
import { NewsRail } from './components/news/NewsRail';
import { ModuleMasthead } from './components/shell/ModuleMasthead';
import './styles/glass-modules.css';
import './styles/module-looks.css';
import type { NotesDraft } from './components/notes/NotesPanel';
import { useAssistantInbox } from "./core/followThrough";
// Module windows load when first opened, so the core appears sooner.
const CalendarPanel = lazy(() => import("./components/calendar/CalendarPanel").then(module => ({ default: module.CalendarPanel })));
const FilesPanel = lazy(() => import("./components/files/FilesPanel").then(module => ({ default: module.FilesPanel })));
const TasksDashboard = lazy(() => import("./components/tasks/TasksDashboard").then(module => ({ default: module.TasksDashboard })));
const StatusPanel = lazy(() => import("./components/status/StatusPanel").then(module => ({ default: module.StatusPanel })));
const SecurityPanel = lazy(() => import("./components/security/SecurityPanel").then(module => ({ default: module.SecurityPanel })));
const AssistantPanel = lazy(() => import("./components/assistant/AssistantPanel").then(module => ({ default: module.AssistantPanel })));
const NewsPanel = lazy(() => import("./components/news/NewsPanel").then(module => ({ default: module.NewsPanel })));
import { useCoreStartup } from "./core/startup";
import { skipWhileAway, useAppInBackground } from "./core/appBackground";
import { AppWindow, Dock, useWindowShell, windowForText } from "./components/shell/WindowShell";
import { layoutAck, parseLayoutCommand } from "./core/layoutCommands";
import { ACCENTS, appearanceStyle, tabAppearance, DEFAULT_APPEARANCE, parseAppearance, parseAppearanceCommand } from "./core/appearance";
import type { Appearance } from "./core/appearance";
import { AppearanceSettings } from "./components/settings/AppearanceSettings";
import { ScreenWatchSettings } from "./components/settings/ScreenWatchSettings";
import { GameCoachSettings } from "./components/settings/GameCoachSettings";
import type { LayoutAction, LayoutTarget, Spot } from "./core/layoutCommands";
import { attendedWindow } from "./core/windowLayout";
import "./App.css";

type Section = "overview" | "status" | "security" | "tasks" | "calendar" | "files" | "system" | "assistant" | "notes" | "news";
type IconName = "core" | "home" | "chat" | "tasks" | "calendar" | "files" | "system" | "arrow" | "bolt" | "clock" | "check" | "send" | "trash" | "plus" | "pulse" | "chevron" | "panel" | "notes" | "news" | "shield";
type VisualMode = "blend" | "progress";

// Conversations live in the chat box under the core: its thread opens above the
// chat bar. Security is its own tab, locked behind the passkey or spoken phrase.
const nav: { id: Section; label: string; short: string; icon: IconName }[] = [
  { id: "overview", label: "Overview", short: "Core", icon: "home" },
  { id: "status", label: "Status", short: "Status", icon: "pulse" },
  { id: "security", label: "Security", short: "Security", icon: "shield" },
  { id: "tasks", label: "Tasks", short: "Tasks", icon: "tasks" },
  { id: "calendar", label: "Calendar", short: "Calendar", icon: "calendar" },
  { id: "notes", label: "Notes", short: "Notes", icon: "notes" },
  { id: "news", label: "Tech News", short: "News", icon: "news" },
  { id: "assistant", label: "Assistant", short: "Assistant", icon: "bolt" },
  { id: "files", label: "Files", short: "Files", icon: "files" },
  { id: "system", label: "System", short: "System", icon: "system" },
];
const sections: Record<Section, { title: string; label: string; description: string }> = {
  overview: { title: "The Core", label: "CENTRAL INTELLIGENCE", description: "A living neural network connecting ZÆNIA's subsystems. Signals travel from the nucleus through each branch to its module." },
  status: { title: "Status", label: "READINESS", description: "Live module readiness, PC load and ZAE's overall security level." },
  security: { title: "Security", label: "LOCKED · OWNER ONLY", description: "Live attack resistance, weak spots and how to fix them, improvements over time, security checks and the full activity log." },
  tasks: { title: "Tasks", label: "PRODUCTIVITY", description: "Set priorities, track deadlines, and follow each task from pending to completed. Kept on your PC, so the phone and desktop share one list." },
  calendar: { title: "Calendar", label: "SCHEDULE", description: "Your ZÆNIA calendar, events you add here and live Google Calendar: the same schedule your brief reads." },
  notes: { title: 'Notes', label: 'KEEP FOR LATER', description: 'Save ideas and details, search them later, and choose what ZAE can reference.' },
  news: { title: 'Tech News', label: 'TRACKED SOURCES', description: 'Headlines from ten credible tech newsrooms, checked every 30 minutes. Stories several sources report are marked.' },
  assistant: { title: "Assistant", label: "MEMORY & FOLLOW-THROUGH", description: "Review what ZÆNIA remembers and manage timely calendar and task follow-through." },
  files: { title: "Files", label: "SYSTEM FILES", description: "Recent changes and ZÆNIA's code and config. The desktop app saves with a backup; the phone sends changes for approval on the PC." },
  system: { title: "System", label: "DIAGNOSTICS", description: "Live module states from the ZÆNIA server, plus the core and appearance settings." },
};
// On desktop every workspace page opens as a window over the core.
const WINDOW_IDS: readonly string[] = ["status", "security", "tasks", "calendar", "notes", "news", "assistant", "files", "system"];
const phaseLabels: Record<ModulePhase, string> = { ready: "READY", working: "WORKING", pending: "PENDING", error: "ERROR" };

// One seamless wave period every 60 units; the SVG is twice as wide as its
// frame and slides left by half its width.
const WAVE_PATH = (() => {
  let d = "";
  for (let x = 0; x <= 120; x += 1.5) {
    const y = 12 + Math.sin(x / 60 * Math.PI * 4) * 7 * (0.55 + 0.45 * Math.sin(x / 60 * Math.PI * 2));
    d += `${x === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(2)}`;
  }
  return d;
})();

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    core: <><circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="10" ry="4.1" transform="rotate(-35 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4.1" transform="rotate(35 12 12)"/></>,
    home: <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-7h6v7"/></>,
    chat: <path d="M5 4h14a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H9l-5 4v-4H3V6a2 2 0 0 1 2-2Z"/>,
    tasks: <><rect x="3" y="3" width="18" height="18" rx="2"/><path d="m7 12 4 4 7-9"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h.01M12 14h.01M17 14h.01M7 18h.01M12 18h.01M17 18h.01"/></>,
    files: <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>,
    notes: <><path d="M6 3h9l4 4v14H6Z"/><path d="M14 3v5h5M9 12h7M9 16h7"/></>,
    news: <><path d="M4 5h13v14a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2Z"/><path d="M17 9h3v10a2 2 0 0 1-2 2M8 9h5M8 13h5M8 17h3"/></>,
    system: <><circle cx="12" cy="12" r="3"/><path d="M11 2h2l.6 2.3 1.8.7 2.1-1.2 1.4 1.4-1.2 2.1.7 1.8L21 10v2l-2.3.6-.7 1.8 1.2 2.1-1.4 1.4-2.1-1.2-1.8.7L13 20h-2l-.6-2.3-1.8-.7-2.1 1.2-1.4-1.4 1.2-2.1-.7-1.8L3 12v-2l2.3-.6.7-1.8-1.2-2.1 1.4-1.4 2.1 1.2 1.8-.7Z"/></>,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6"/>,
    bolt: <path d="m13 2-9 11h7l-1 9 10-12h-7Z"/>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    check: <path d="m5 12 5 5L20 7"/>,
    send: <><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v7M14 11v7"/></>,
    pulse: <path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>,
    shield: <><path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6Z"/><path d="m9 12 2 2 4-4"/></>,
    chevron: <path d="m6 9 6 6 6-6"/>,
    panel: <><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 13h18M10 16.5h4"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function Wave({ tone, live }: { tone: "amber" | "blue"; live: boolean }) {
  return <span className={`status-wave status-wave--${tone} ${live ? "status-wave--live" : ""}`} aria-hidden="true">
    <svg viewBox="0 0 120 24" preserveAspectRatio="none"><path d={WAVE_PATH}/></svg>
  </span>;
}

// Phone layout: bottom tab bar, pinned chat box and a slide-up status sheet.
const PHONE_QUERY = "(max-width: 760px)";
function useIsPhone() {
  const [phone, setPhone] = useState(() => window.matchMedia(PHONE_QUERY).matches);
  useEffect(() => {
    const media = window.matchMedia(PHONE_QUERY);
    const change = () => setPhone(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  return phone;
}
// Quiet time before the conversation folds down and the core takes the stage.
const REST_MS = 45_000;
// Streamed words are drawn at most this often.
const DRAW_MS = 50;
// "Stop", "wait", "never mind"… on their own just cut ZÆNIA off.
const STOP_WORDS = /^(?:(?:ok(?:ay)?|zay|hey|no)[\s,]+)*(?:stop|wait|hold on|hang on|never ?mind|quiet|be quiet|shush|enough|that'?s enough|cancel|pause)\b/i;
const isStopRequest = (words: string) => STOP_WORDS.test(words.trim()) && words.trim().split(/\s+/).length <= 5;
const wordsOf = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}' ]+/gu, " ").split(/\s+/).filter(Boolean);
/** True when the mic mostly heard ZÆNIA's own words (her voice through the speakers). */
function isEcho(heard: string, spoken: string): boolean {
  if (isStopRequest(heard)) return false;
  const said = new Set(wordsOf(spoken));
  const words = wordsOf(heard);
  if (!words.length || !said.size) return false;
  return words.filter(word => said.has(word)).length / words.length >= 0.6;
}
const sentenceCase = (text: string) => text ? text.charAt(0).toUpperCase() + text.slice(1).toLowerCase() : text;

// Phone web app: ask for the token once, then show the full UI. The desktop app
// and the browser preview go straight to the UI.
export default function App() {
  const [connected, setConnected] = useState<boolean | null>(() => !WEB_APP || savedToken() !== null ? true : null);
  const [notice, setNotice] = useState<string | null>(null);
  const onConnected = useCallback(() => { setNotice(null); setConnected(true); }, []);
  const onForgetPhone = useCallback(() => {
    void disconnectPhone().then(() => { setNotice(null); setConnected(false); })
      .catch(error => setNotice(errorText(error)));
  }, []);
  const onAuthLost = useCallback(() => {
    forgetToken();
    setNotice("Please sign in again with your voice or your current access token.");
    setConnected(false);
  }, []);
  useEffect(() => {
    if (connected !== null) return;
    let active = true;
    checkPhoneConnection().then(() => { if (active) setConnected(true); }, () => { if (active) setConnected(false); });
    return () => { active = false; };
  }, [connected]);
  if (connected === null) return <div className="phone-connect"><main className="phone-connect__body"><p role="status">Reconnecting to ZÆNIA…</p></main></div>;
  if (!connected) return <PhoneConnect notice={notice} onConnected={onConnected}/>;
  return <ZaeniaApp connectionNotice={notice} onForgetPhone={WEB_APP ? onForgetPhone : undefined} onAuthLost={WEB_APP ? onAuthLost : undefined}/>;
}

function ZaeniaApp({ onForgetPhone, onAuthLost, connectionNotice }: { onForgetPhone?: () => void; onAuthLost?: () => void; connectionNotice?: string | null }) {
  const [section, setSection] = useState<Section>("overview");
  const notesDraft = useRef<NotesDraft>(EMPTY_NOTES_DRAFT);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (notesDraft.current.dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, []);
  const [mode, setMode] = useState<VisualMode>("blend");
  const [motion, setMotion] = useState(true);
  // The desktop and phone apps always show live data; sample values exist only in the browser preview.
  const [source, setSource] = useState<"preview" | "local">(() => canGoLive ? "local" : "preview");
  const [startupReplay, setStartupReplay] = useState(0);
  const startup = useCoreStartup(startupReplay);
  const [localTelemetry, setLocalTelemetry] = useState<CoreTelemetry | null>(null);
  const [connection, setConnection] = useState("Not connected");
  const [time, setTime] = useState(() => new Date());
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState("");
  const [photos, setPhotos] = useState<ChatPhoto[]>([]);
  const photosRef = useRef<ChatPhoto[]>([]);
  const photoTurns = useRef<{ role: "user" | "assistant"; content: string }[]>([]);
  const changePhotos = (items: ChatPhoto[]) => { photosRef.current = items; photoTurns.current = []; setPhotos(items); };
  // Files shared in the chat stay attached for follow-up questions until cleared.
  const [sharedFiles, setSharedFiles] = useState<ChatFile[]>([]);
  const filesRef = useRef<ChatFile[]>([]);
  const changeFiles = (items: ChatFile[]) => { filesRef.current = items; setSharedFiles(items); };
  const [sending, setSending] = useState(false);
  const [identityHovered, setIdentityHovered] = useState(false);
  const [identityRevealed, setIdentityRevealed] = useState(false);
  const [voiceConversationActive, setVoiceConversationActive] = useState(false);
  const identityTimerRef = useRef<number | null>(null);
  const messageCounter = useRef(0);
  const queryRef = useRef<HTMLInputElement | null>(null);
  const [history, setHistory] = useState<HistoryState>(LIVE_API ? "loading" : "preview");
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState(0);
  const [assistantRefresh, setAssistantRefresh] = useState(0);
  const inbox = useAssistantInbox();
  const sendingRef = useRef(false);
  const followUntil = useRef(0);
  // The reply being written: each turn has a number, so a stopped reply can't touch the chat later.
  const turnRef = useRef(0);
  const streamRef = useRef<ChatStream | null>(null);
  const replyRef = useRef<{ id: number; text: string; added: boolean; at: string; proposal?: AssistantProposal } | null>(null);
  // Synchronous guard as well as React state: a second click cannot duplicate a write.
  const actionStates = useRef(new Map<number, AssistantActionState["status"]>());
  const [actionRefresh, setActionRefresh] = useState({ tasks: 0, calendar: 0 });
  const [streamingId, setStreamingId] = useState<number | null>(null);
  const [voiceNote, setVoiceNote] = useState<string | null>(null);
  // No wake word: the PC decides what is meant for ZÆNIA, so there is no follow-up window to show.
  const [openMic, setOpenMic] = useState(true);
  const [pcVoice, setPcVoice] = useState<{ running: boolean; state: string; recognising?: boolean | null } | null>(null);
  const speech = useSpeech();
  const [briefingActive, setBriefingActive] = useState(false);
  const [speakReplies, setSpeakReplies] = useState(() => { try { return localStorage.getItem("zaenia.speakReplies") === "1"; } catch { return false; } });
  const toggleSpeak = useCallback(() => setSpeakReplies(on => {
    const next = !on;
    try { localStorage.setItem("zaenia.speakReplies", next ? "1" : "0"); } catch { /* storage unavailable */ }
    if (!next) speech.stop();
    return next;
  }), [speech]);
  const [selectedModule, setSelectedModule] = useState("security");
  const [confirmForget, setConfirmForget] = useState(false);
  const info = sections[section];
  const isPhone = useIsPhone();
  // Desktop shell: pages open as movable windows; the phone keeps full screens.
  const windowed = !isPhone;
  const shell = useWindowShell(WINDOW_IDS);
  const attendedTab = useRef<string | null>(null);
  const layerRef = useRef<HTMLDivElement | null>(null);
  const platformRuntime = usePlatformRuntime();
  const [hands, setHands] = useState(false);
  const [handNote, setHandNote] = useState<string | null>(null);
  const handsSupported = !isPhone && typeof Worker !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
  const gestureDrag = useRef<{ kind: "move" | "resize"; id: string; x: number; y: number; span: number; rect: ShellWindow } | null>(null);
  const restoredRequest = useRef<string | null>(null);
  const restorePending = useRef(false);
  const automaticCandidates = useRef(new Set<number>());
  const policyRef = useRef(platformRuntime.summary?.policy);
  policyRef.current = platformRuntime.summary?.policy;
  const lastApiMode = useRef<string | null>(null);
  const transportFailure = useRef(false);
  const lastRecovery = useRef(0);
  const [autoRecoveryEnabled, setAutoRecoveryEnabled] = useState(() => { try { return localStorage.getItem("zaenia.autoRecovery") === "1"; } catch { return false; } });
  useEffect(() => {
    const update = () => { try { setAutoRecoveryEnabled(localStorage.getItem("zaenia.autoRecovery") === "1"); } catch { setAutoRecoveryEnabled(false); } };
    window.addEventListener("zae:recovery-settings", update); return () => window.removeEventListener("zae:recovery-settings", update);
  }, []);
  const restoreWindows = (windows: ShellWindow[]) => {
    if (isPhone) { const first = windows.filter(win => !win.minimized).sort((a, b) => b.z - a.z)[0]; if (first && WINDOW_IDS.includes(first.id as typeof WINDOW_IDS[number])) openSection(first.id as Section); }
    else shell.restore(windows);
  };
  useEffect(() => {
    const request = platformRuntime.summary?.activeWorkspace;
    if (!request || restorePending.current) return;
    const key = `${request.workspaceId}:${request.revision}`;
    if (restoredRequest.current === key) return;
    restorePending.current = true;
    void api<{ workspaces: { id: string; windows: ShellWindow[] }[] }>("GET", "/api/platform/workspaces").then(reply => {
      const workspace = reply.workspaces.find(item => item.id === request.workspaceId);
      if (workspace) { restoreWindows(workspace.windows); restoredRequest.current = key; }
    }).catch(() => { /* Retry a still-current request on a later poll. */ }).finally(() => { restorePending.current = false; });
  }, [platformRuntime.summary]);
  function handleGesture(action: GestureCommand) {
    if (action.kind === "stop") { interrupt(); return; }
    if (action.kind === "release") { gestureDrag.current = null; return; }
    const current = shell.windows.filter(win => !win.minimized).sort((a, b) => b.z - a.z);
    if (action.kind === "minimize") { if (shell.active) shell.minimize(shell.active); return; }
    if (action.kind === "next" || action.kind === "previous") {
      const all = [...shell.windows].sort((a, b) => a.id.localeCompare(b.id));
      const index = all.findIndex(win => win.id === shell.active);
      const next = all[(index + (action.kind === "next" ? 1 : -1) + all.length) % all.length];
      if (next) shell.open(next.id); return;
    }
    if (action.x === undefined || action.y === undefined) return;
    const x = action.x * window.innerWidth, y = action.y * window.innerHeight;
    const under = document.elementsFromPoint(x, y).map(element => element.closest<HTMLElement>("[data-window-id]")?.dataset.windowId).find(Boolean);
    if (action.kind === "point") { if (under && under !== shell.active) shell.open(under); return; }
    const box = layerRef.current?.getBoundingClientRect();
    if (!box || box.width <= 0 || box.height <= 0) return;
    if (!gestureDrag.current || gestureDrag.current.kind !== action.kind) {
      const target = current.find(win => win.id === under) ?? current.find(win => win.id === shell.active);
      if (!target) return;
      shell.open(target.id);
      gestureDrag.current = { kind: action.kind, id: target.id, x, y, span: Math.max(.1, action.span ?? 1), rect: { ...target } };
    }
    const drag = gestureDrag.current;
    if (action.kind === "move") shell.update(drag.id, { x: Math.max(0, Math.min(1 - drag.rect.w, drag.rect.x + (x - drag.x) / box.width)), y: Math.max(0, Math.min(1 - drag.rect.h, drag.rect.y + (y - drag.y) / box.height)) });
    else {
      const scale = Math.max(.5, Math.min(2, (action.span ?? drag.span) / drag.span));
      shell.update(drag.id, { w: Math.max(.26, Math.min(1 - drag.rect.x, drag.rect.w * scale)), h: Math.max(.3, Math.min(1 - drag.rect.y, drag.rect.h * scale)) });
    }
  }
  const stageSection: Section = windowed ? "overview" : section;
  const openSection = (next: Section) => {
    setSection(next);
    if (!windowed) return;
    if (next === "overview") shell.showDesktop(); else shell.open(next);
  };
  // Fonts and colours (System → Appearance), saved on this device.
  const [appearance, setAppearance] = useState<Appearance>(() => { try { return parseAppearance(localStorage.getItem("zaenia.appearance")); } catch { return { ...DEFAULT_APPEARANCE }; } });
  useEffect(() => { try { localStorage.setItem("zaenia.appearance", JSON.stringify(appearance)); } catch { /* optional */ } }, [appearance]);
  // Where the core sits: "auto" docks it top-left while you work in windows.
  const [coreSpot, setCoreSpot] = useState<Spot | "auto">("auto");
  const [sidebarHidden, setSidebarHidden] = useState(() => { try { return localStorage.getItem("zaenia.sidebarHidden") === "1"; } catch { return false; } });
  useEffect(() => { try { localStorage.setItem("zaenia.sidebarHidden", sidebarHidden ? "1" : "0"); } catch { /* optional */ } }, [sidebarHidden]);
  const working = windowed && shell.windows.some(win => !win.minimized);
  const coreDock: Spot = coreSpot !== "auto" ? coreSpot : working ? "top-left" : "center";
  const [brandOpen, setBrandOpen] = useState(false);
  const [restartNote, setRestartNote] = useState<string | null>(null);
  // Starting from the Start menu: if the server is off, start it with the API
  // token or the passkey. A remembered choice starts it automatically.
  const [autoStart, setAutoStart] = useState<"" | "token" | "passkey">(() => { try { const v = localStorage.getItem("zaenia.autoStart"); return v === "token" || v === "passkey" ? v : ""; } catch { return ""; } });
  const [rememberStart, setRememberStart] = useState(false);
  const [launchNote, setLaunchNote] = useState<string | null>(null);
  const [launchDismissed, setLaunchDismissed] = useState(false);
  const autoStarted = useRef(false);
  function launchServer(mode: "token" | "passkey", remember: boolean) {
    if (remember) { setAutoStart(mode); try { localStorage.setItem("zaenia.autoStart", mode); } catch { /* optional */ } }
    setLaunchNote(mode === "token" ? "Starting ZÆNIA's server with the API token…" : "Type your passkey in the ZÆNIA Server window that just opened.");
    startServer(mode).catch(failure => setLaunchNote(errorText(failure)));
  }
  const [weather, setWeather] = useState<{ place: string; temperature: number | null; condition: string; high: number | null; low: number | null } | null>(null);
  useEffect(() => {
    // Preview mode shows sample weather so the layout is complete.
    if (!LIVE_API) { setWeather({ place: "Lacey", temperature: 60, condition: "clear", high: 64, low: 47 }); return; }
    let cancelled = false;
    let timer = 0;
    const load = () => api<{ place: string; temperature: number | null; condition: string; high: number | null; low: number | null }>("GET", "/api/weather/now", undefined, { timeoutMs: 30_000 })
      .then(reply => { if (cancelled) return; if (!reply || typeof reply.place !== "string" || typeof reply.condition !== "string" || ![reply.temperature, reply.high, reply.low].every(value => value === null || typeof value === "number" && Number.isFinite(value))) throw new Error("Weather data is unavailable."); setWeather(reply); timer = window.setTimeout(load, 15 * 60_000); })
      // Not available yet (server restarting, no network): try again in a minute.
      .catch(() => { if (!cancelled) timer = window.setTimeout(load, 60_000); });
    load();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, []);
  // The title and sidebar follow the window in front.
  useEffect(() => { if (windowed) setSection((shell.active ?? "overview") as Section); }, [windowed, shell.active]);
  const [sheetOpen, setSheetOpen] = useState(false);
  const sheetTouch = useRef<number | null>(null);
  // The sheet closes whenever you move to another screen or leave phone width.
  useEffect(() => { setSheetOpen(false); }, [section, isPhone]);
  useEffect(() => {
    if (!sheetOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setSheetOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sheetOpen]);

  // The desktop panel can show the expanded identity for public name questions.
  // Voice UI integration is optional: dispatch the events below from the voice
  // frontend when speech starts/ends; no microphone or TTS is started here.
  useEffect(() => {
    const startVoice = () => setVoiceConversationActive(true);
    const stopVoice = () => setVoiceConversationActive(false);
    const questionFromVoice = () => {
      setIdentityRevealed(true);
      if (identityTimerRef.current !== null) window.clearTimeout(identityTimerRef.current);
      identityTimerRef.current = window.setTimeout(() => setIdentityRevealed(false), 10000);
    };
    window.addEventListener("zaenia:voice-conversation-start", startVoice);
    window.addEventListener("zaenia:voice-conversation-end", stopVoice);
    window.addEventListener("zaenia:identity-question", questionFromVoice);
    return () => {
      window.removeEventListener("zaenia:voice-conversation-start", startVoice);
      window.removeEventListener("zaenia:voice-conversation-end", stopVoice);
      window.removeEventListener("zaenia:identity-question", questionFromVoice);
      if (identityTimerRef.current !== null) window.clearTimeout(identityTimerRef.current);
    };
  }, []);
  const showExpandedIdentity = identityHovered || identityRevealed || voiceConversationActive;
  function revealIdentity() {
    setIdentityRevealed(true);
    if (identityTimerRef.current !== null) window.clearTimeout(identityTimerRef.current);
    identityTimerRef.current = window.setTimeout(() => setIdentityRevealed(false), 10000);
  }
  useEffect(() => { const id = window.setInterval(() => setTime(new Date()), 30_000); return () => window.clearInterval(id); }, []);
  // The input is disabled while a message is sent; give it focus back after the reply.
  const wasSending = useRef(false);
  useEffect(() => {
    if (wasSending.current && !sending && !isPhone) queryRef.current?.focus();
    wasSending.current = sending;
  }, [sending, isPhone]);
  // File changes waiting for approval: a badge on Files and the quick tool.
  useEffect(() => {
    if (!LIVE_API) return;
    const load = () => {
      api<{ proposals: { status: string }[] }>("GET", "/api/files/proposals")
        .then(reply => setPendingFiles(reply.proposals.filter(item => item.status === "pending").length))
        .catch(() => { /* badge stays as it was */ });
    };
    load();
    const onVisible = () => { if (!document.hidden) load(); };
    const timer = window.setInterval(load, 60_000);
    document.addEventListener("visibilitychange", onVisible);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", onVisible); };
  }, []);
  // Recent conversation from ZÆNIA's memory on the PC, shown once at start.
  useEffect(() => {
    if (!LIVE_API) return;
    let cancelled = false;
    api<{ messages: { role: "user" | "assistant"; text: string; at: string }[] }>("GET", "/api/chat/history?limit=30")
      .then(reply => {
        if (cancelled) return;
        const earlier: ChatMessage[] = reply.messages.map(item => ({ id: ++messageCounter.current, role: item.role, text: item.text, at: item.at, history: true }));
        setChat(previous => [...earlier, ...previous]);
        setHistory("ready");
      })
      .catch(failure => { if (!cancelled) { setHistory("unavailable"); setHistoryError(errorText(failure)); } });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (source !== "local" || !canGoLive) return;
    let mounted = true; let controller: AbortController | null = null;
    const getStatus = async () => {
      controller?.abort(); controller = new AbortController();
      try {
        const parsed = parseCoreTelemetry(await readStatus(controller.signal));
        if (!parsed) throw new Error("Invalid status schema");
        if (mounted) { setLocalTelemetry(parsed); setConnection(parsed.system?.mode === "voice_only" ? "Live · voice recognition ready" : parsed.system?.mode === "unattended" ? "Live · token mode (owner features need the passkey)" : "Live · unlocked with the passkey"); }
        lastApiMode.current = parsed.system?.mode ?? null; transportFailure.current = false;
      } catch (e) {
        if (!mounted || (e instanceof DOMException && e.name === "AbortError")) return;
        if (e instanceof BridgeError && e.kind === "auth" && onAuthLost) { onAuthLost(); return; }
        setLocalTelemetry(null); setConnection(`Unavailable: ${e instanceof Error ? e.message : String(e)}`);
        transportFailure.current = (e instanceof BridgeError && e.kind === "offline") || (typeof e === "string" && /not reachable|connection refused|connect error/i.test(e));
      }
    };
    // Phones pause timers in the background; refresh as soon as the app is back.
    const onVisible = () => { if (!document.hidden) void getStatus(); };
    // Every 8 s in use; every 32 s while the window is in the background.
    const away = { n: 0 };
    void getStatus(); const id = window.setInterval(() => { if (!skipWhileAway(away, 4)) void getStatus(); }, 8_000);
    document.addEventListener("visibilitychange", onVisible);
    return () => { mounted = false; controller?.abort(); window.clearInterval(id); document.removeEventListener("visibilitychange", onVisible); };
  }, [source, onAuthLost]);
  // "Forget this phone" asks for a second tap within four seconds.
  useEffect(() => {
    if (!confirmForget) return;
    const id = window.setTimeout(() => setConfirmForget(false), 4_000);
    return () => window.clearTimeout(id);
  }, [confirmForget]);
  const telemetry = useMemo<CoreTelemetry | null>(() => source === "preview" ? { ...PREVIEW_TELEMETRY, progress: startup.progress, phase: startup.ready ? "ONLINE" : "INITIALIZING" } : localTelemetry, [source, startup.progress, startup.ready, localTelemetry]);
  const readyCount = telemetry?.modules.filter(m => m.phase === "ready" || m.phase === "working").length ?? 0;
  const moduleTotal = telemetry?.modules.length ?? 0;
  // Preview shows an illustrative load figure; Live shows the PC's real processor and memory use.
  const systemLoad = source === "preview" ? Math.round(28 * startup.progress / 100) : (telemetry?.system?.cpu ?? null);
  const memoryLoad = source === "local" ? (telemetry?.system?.memory ?? null) : null;
  const live = source === "local" && telemetry !== null;
  const serverDown = IN_TAURI && source === "local" && localTelemetry === null && connection.startsWith("Unavailable");
  useEffect(() => {
    if (!serverDown) { setLaunchNote(null); return; }
    if (autoStart && !autoStarted.current) { autoStarted.current = true; launchServer(autoStart, false); }
  }, [serverDown, autoStart]); // eslint-disable-line react-hooks/exhaustive-deps
  const liveMotion = motion && startup.ready;
  useEffect(() => {
    if (!IN_TAURI || !autoRecoveryEnabled || !serverDown) return;
    let failures = 0;
    const timer = window.setInterval(() => {
      if (!transportFailure.current || lastApiMode.current !== "unattended") return;
      failures += 1;
      if (failures < 3 || Date.now() - lastRecovery.current < 120_000) return;
      lastRecovery.current = Date.now(); failures = 0;
      void restartServer().then(() => setVoiceNote("Recovering the token-mode API after repeated connection failures.")).catch(failure => setVoiceNote(errorText(failure)));
    }, 8000);
    return () => window.clearInterval(timer);
  }, [serverDown, autoRecoveryEnabled]);

  function sendChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = query.trim() || (photosRef.current.length ? "Describe these photos and their important details."
      : filesRef.current.length ? "Summarize what's in these files and anything important I should know." : "");
    if (!message) return;
    setQuery("");
    submit(message);
  }

  function dismissProposal(messageId: number) {
    const message = chat.find(item => item.id === messageId);
    const status = actionStates.current.get(messageId) ?? message?.action?.status ?? "ready";
    if (!message?.proposal || message.streaming || !["ready", "failed"].includes(status)) return;
    actionStates.current.set(messageId, "dismissed");
    setChat(previous => previous.map(item => item.id === messageId ? { ...item, action: { status: "dismissed", detail: "Dismissed without saving." } } : item));
  }

  async function applyProposal(messageId: number) {
    const message = chat.find(item => item.id === messageId);
    const status = actionStates.current.get(messageId) ?? message?.action?.status ?? "ready";
    const proposal = parseAssistantProposal(message?.proposal);
    if (!LIVE_API || !proposal || message?.streaming || message?.interrupted || !["ready", "failed"].includes(status)) return;
    const update = (action: AssistantActionState) => {
      actionStates.current.set(messageId, action.status);
      setChat(previous => previous.map(item => item.id === messageId ? { ...item, action } : item));
    };
    if (assistantProposalExpired(proposal)) {
      update({ status: "expired", detail: "This event's Pacific start time has passed. Ask ZÆNIA for a fresh calendar proposal before saving." });
      return;
    }
    update({ status: "pending", detail: "Saving to ZÆNIA on your PC…" });
    interrupt();
    if (speakReplies) speech.prime();
    const destination = proposal.kind.startsWith("memory.") || proposal.kind === "app.launch" || proposal.kind === "workspace.restore" ? "Assistant" : proposal.kind === "task.create" ? "Tasks" : "Calendar";
    const uncertain = () => update({ status: "uncertain", detail: `I couldn't verify whether it saved. Check ${destination} before creating it again; this card is locked to avoid a duplicate.` });
    try {
      // The model supplies data only. These two fixed routes are the entire action surface.
      let response: unknown;
      if (proposal.kind === "task.create") response = await api("POST", "/api/tasks", { ...proposal.parameters, fromConversation: true });
      else if (proposal.kind === "calendar.create") response = await api("POST", "/api/calendar/events", { ...proposal.parameters, fromConversation: true });
      else if (proposal.kind === "memory.remember") response = await api("POST", "/api/assistant/memory", proposal.parameters);
      else if (proposal.kind === "memory.forget") response = await api("POST", "/api/assistant/memory/forget", proposal.parameters);
      else if (proposal.kind === "app.launch") response = await api("POST", `/api/platform/apps/${proposal.parameters.id}/launch`, undefined, { desktop: true });
      else response = await api("POST", `/api/platform/workspaces/${proposal.parameters.id}/restore`, { launchApps: true, revision: proposal.parameters.revision }, { desktop: true });
      const confirmation = confirmedAssistantAction(proposal, response);
      if (!confirmation) { uncertain(); return; }
      update({ status: "succeeded", detail: `Saved. Open ${destination} to view it.` });
      setActionRefresh(previous => proposal.kind === "task.create" ? { ...previous, tasks: previous.tasks + 1 } : { ...previous, calendar: previous.calendar + 1 });
      setAssistantRefresh(previous => previous + 1);
      void inbox.refresh();
      const id = ++messageCounter.current;
      setChat(previous => [...previous, { id, role: "assistant", text: confirmation, at: new Date().toISOString() }]);
      if (speakReplies && !sendingRef.current) void speech.speak(`m${id}`, confirmation);
    } catch (failure) {
      // A definite client rejection can be retried. Connection/server failures may follow a committed write.
      if (failure instanceof BridgeError && failure.status !== undefined && failure.status >= 400 && failure.status < 500 && failure.status !== 408) {
        update({ status: "failed", detail: `Not saved: ${errorText(failure)} You can try this card again after resolving the issue.` });
      } else uncertain();
    }
  }

  useEffect(() => {
    if (sending || !automaticCandidates.current.size) return;
    const id = [...automaticCandidates.current].find(candidate => chat.some(message => message.id === candidate && !message.streaming && !message.interrupted && message.proposal));
    if (id === undefined) return;
    automaticCandidates.current.delete(id);
    void applyProposal(id);
  }, [chat, sending]);

  /** Cut ZÆNIA off: stop her voice and the reply she's writing. What she already said stays. */
  function interrupt() {
    speech.stop();
    const stream = streamRef.current;
    if (!sendingRef.current && !stream) return;
    turnRef.current += 1;
    streamRef.current = null;
    stream?.cancel();
    const reply = replyRef.current;
    replyRef.current = null;
    if (reply && reply.text.trim()) {
      const stopped: ChatMessage = { id: reply.id, role: "assistant", text: reply.text.trim(), at: reply.at, streaming: false, interrupted: true };
      const shown = reply.added;
      setChat(prev => shown ? prev.map(item => item.id === reply.id ? stopped : item) : [...prev, stopped]);
    }
    sendingRef.current = false;
    setSending(false);
    setStreamingId(null);
    followUntil.current = Date.now() + FOLLOW_UP_MS;
  }
  const interruptRef = useRef(interrupt);
  interruptRef.current = interrupt;

  // Spoken or typed layout commands run instantly, without the model.
  const RECTS: Record<Spot, { x: number; y: number; w: number; h: number }> = {
    left: { x: 0, y: 0, w: 0.5, h: 1 }, right: { x: 0.5, y: 0, w: 0.5, h: 1 },
    top: { x: 0, y: 0, w: 1, h: 0.5 }, bottom: { x: 0, y: 0.5, w: 1, h: 0.5 },
    "top-left": { x: 0, y: 0, w: 0.42, h: 0.48 }, "top-right": { x: 0.58, y: 0, w: 0.42, h: 0.48 },
    "bottom-left": { x: 0, y: 0.52, w: 0.42, h: 0.48 }, "bottom-right": { x: 0.58, y: 0.52, w: 0.42, h: 0.48 },
    center: { x: 0.2, y: 0.08, w: 0.6, h: 0.84 },
  };
  function runLayout(actions: LayoutAction[]) {
    const resolve = (target: LayoutTarget): string | null => target === "focused" ? attendedWindow(shell.windows, attendedTab.current, shell.active) : target;
    const applied: LayoutAction[] = [];
    for (const action of actions) {
      if (action.kind === "sidebar") { applied.push(action); setSidebarHidden(!action.show); continue; }
      if (action.kind === "clear") { applied.push(action); shell.showDesktop(); setCoreSpot("auto"); continue; }
      const target = action.target === "all" ? "all" : action.kind === "restore" && action.target === "focused"
        ? shell.windows.find(win => win.id === attendedTab.current)?.id ?? shell.active : resolve(action.target);
      if (!target) continue;
      applied.push({ ...action, target } as LayoutAction);
      if (target !== "all" && target !== "core") attendedTab.current = target;
      if (action.kind === "open") { if (target !== "core" && target !== "all") openSection(target as Section); continue; }
      if (action.kind === "close") { if (target === "all") shell.closeAll(); else if (target !== "core") shell.close(target); continue; }
      if (action.kind === "minimize") { if (target === "all") shell.showDesktop(); else if (target === "core") setCoreSpot("top-left"); else shell.minimize(target); continue; }
      if (action.kind === "restore") { if (target === "all") shell.restoreAll(); else if (target !== "core") shell.open(target); continue; }
      if (action.kind === "maximize") { if (target === "core") { shell.showDesktop(); setCoreSpot("center"); } else shell.setRect(target, { x: 0, y: 0, w: 1, h: 1 }); continue; }
      if (action.kind === "place") {
        if (target === "core") { setCoreSpot(action.spot); continue; }
        const rect = { ...RECTS[action.spot] };
        if (action.small && ["left", "right", "top", "bottom"].includes(action.spot)) { rect.w = Math.min(rect.w, 0.36); rect.h = Math.min(rect.h, 0.6); }
        shell.setRect(target, rect);
        continue;
      }
      if (action.kind === "size") {
        if (target === "core") { setCoreSpot(action.grow ? "center" : coreDock === "center" ? "top-left" : coreDock); continue; }
        const win = shell.windows.find(item => item.id === target);
        if (!win) continue;
        const scale = action.grow ? 1.25 : 0.75;
        const w = action.axis === "height" ? win.w : Math.min(1, Math.max(0.26, win.w * scale));
        const h = action.axis === "width" ? win.h : Math.min(1, Math.max(0.3, win.h * scale));
        shell.setRect(target, { x: Math.min(win.x, 1 - w), y: Math.min(win.y, 1 - h), w, h });
      }
    }
    return applied;
  }
  // Your request is the authorization: creates save straight away (deleting a memory still asks).
  const applyRef = useRef<(id: number) => void>(() => undefined);
  applyRef.current = (id: number) => { void applyProposal(id); };

  // Development only: ?preview=home|work|menu|settings stages a sample scene for screenshots.
  const previewScene = useRef(import.meta.env.DEV ? new URLSearchParams(location.search).get("preview") : null);
  useEffect(() => {
    const scene = previewScene.current;
    if (!scene) return;
    const timer = window.setTimeout(() => {
      const at = new Date().toISOString();
      const line = (role: "user" | "assistant", text: string) => ({ id: ++messageCounter.current, role, text, at });
      const tint = new URLSearchParams(location.search).get("accent");
      if (tint && ACCENTS.some(item => item.id === tint)) setAppearance(current => ({ ...current, accent: tint as Appearance["accent"] }));
      if (scene === "work") {
        runLayout([{ kind: "open", target: "tasks" }]);
        runLayout([{ kind: "open", target: "calendar" }]);
        runLayout([{ kind: "place", target: "calendar", spot: "right", small: false }]);
        setChat([line("user", "open my calendar"), line("assistant", "Opened Calendar."), line("user", "move calendar to the right"), line("assistant", "Moved Calendar to the right.")]);
      } else if (scene === "settings") {
        runLayout([{ kind: "open", target: "system" }]);
        runLayout([{ kind: "maximize", target: "system" }]);
      } else {
        setChat([line("user", "hello"), line("assistant", "Good morning, sir."), line("user", "what's the weather like"), line("assistant", "Clear and 60 degrees in Lacey, sir. High of 64.")]);
        if (scene === "menu") { setBrandOpen(true); setIdentityHovered(true); }
      }
    }, 8500);
    return () => window.clearTimeout(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fixes ZÆNIA can run herself, from a "Fix it" button or by voice.
  function runFix(action: string): string | null {
    if (action === "start_voice") { void startPcVoice(); return "Starting the PC voice service. Enter your passkey in its window."; }
    if (action === "start_passkey") { void startServer("passkey").catch(failure => setVoiceNote(errorText(failure))); return "Opening the server window. Type your passkey there."; }
    if (action === "restart_token") { void restartServer().catch(failure => setVoiceNote(errorText(failure))); return "Restarting the server, sir."; }
    if (action === "connect_google") { void connectGoogleCalendar().catch(failure => setVoiceNote(errorText(failure))); return "Opening the Google sign-in. Click Allow in your browser."; }
    if (action === "voice_training") { void openVoiceTraining().catch(failure => setVoiceNote(errorText(failure))); return "Opening voice training. Have your passkey ready, sir."; }
    if (action === "connect_gmail") { void connectGmail().catch(failure => setVoiceNote(errorText(failure))); return "Opening the Gmail sign-in. It's read-only; click Allow in your browser."; }
    if (action === "open_files") { openSection("files"); return "Files are up."; }
    if (action === "open_tasks") { openSection("tasks"); return "Tasks are up."; }
    if (action === "open_status") { openSection("status"); return "Status is up."; }
    if (action === "open_security") { openSection("security"); return "Security is up. Unlock it with your passkey or your phrase."; }
    if (action === "run_security_check") {
      void api("POST", "/api/security/checks")
        .then(() => window.dispatchEvent(new Event(SECURITY_CHECK_EVENT)), failure => setVoiceNote(errorText(failure)));
      return "Running a security check, sir. It takes about half a minute; the report will be on the Security tab.";
    }
    return null;
  }
  const FIX_COMMANDS: [RegExp, string][] = [
    [/^(?:please )?(?:start|turn on|fix)(?: up)? (?:the )?(?:pc )?voice(?: service)?\b/, "start_voice"],
    [/^(?:please )?(?:restart|start)(?: up)? (?:the )?server with (?:the |my )?passkey\b|^(?:unlock|switch to) (?:full|owner) (?:mode|features)\b/, "start_passkey"],
    [/^(?:please )?(?:restart|reboot|fix) (?:the )?server\b/, "restart_token"],
    [/^(?:please )?(?:connect|link|set up|sync) (?:my )?(?:g ?mail|e-?mail|inbox)\b/, "connect_gmail"],
    [/^(?:please )?(?:train|retrain|calibrate|re-?enroll) (?:my |your )?voice\b|^voice training\b/, "voice_training"],
    [/^(?:please )?(?:connect|link|set up|sync) (?:my )?google(?: calendar)?\b/, "connect_google"],
    [/^(?:please )?(?:can you |could you )?(?:run|do|start|perform)(?: a| an| your)? (?:security (?:check|scan|self[- ]?check|test)|self[- ]?check)\b|^check (?:your|my) security\b/, "run_security_check"],
  ];

  /** One message to ZÆNIA, typed or spoken. Sending while she's busy interrupts her. */
  function submit(message: string) {
    interrupt();
    const sharedPhotos = photosRef.current;
    const photoQuestion = sharedPhotos.length > 0;
    const photoHistory = photoTurns.current.slice(-6);
    const attachedFiles = filesRef.current;
    const fileQuestion = attachedFiles.length > 0;
    const fixCommand = IN_TAURI && !photoQuestion && !fileQuestion ? FIX_COMMANDS.find(([pattern]) => pattern.test(message.toLowerCase().replace(/^(?:zae|zay|zaenia)[, ]+/, "").trim())) : undefined;
    const fixReply = fixCommand ? runFix(fixCommand[1]) : null;
    if (fixReply) {
      const at = new Date().toISOString();
      setChat(prev => [...prev, { id: ++messageCounter.current, role: "user", text: message, at }, { id: ++messageCounter.current, role: "assistant", text: fixReply, at }]);
      if (speakReplies) { speech.prime(); void speech.speak(`fix-${messageCounter.current}`, fixReply); }
      return;
    }
    const restyle = photoQuestion || fileQuestion ? null : parseAppearanceCommand(message, appearance);
    if (restyle) {
      setAppearance(restyle);
      const accent = ACCENTS.find(item => item.id === restyle.accent)?.label ?? "it";
      const ack = restyle.accent !== appearance.accent ? `${accent} it is, sir.` : "Done.";
      const at = new Date().toISOString();
      setChat(prev => [...prev, { id: ++messageCounter.current, role: "user", text: message, at }, { id: ++messageCounter.current, role: "assistant", text: ack, at }]);
      if (speakReplies) { speech.prime(); void speech.speak(`look-${messageCounter.current}`, ack); }
      followUntil.current = Date.now() + FOLLOW_UP_MS;
      return;
    }
    const layout = photoQuestion || fileQuestion ? null : parseLayoutCommand(message);
    if (layout) {
      const applied = runLayout(layout);
      const ack = layoutAck(applied, Object.fromEntries(Object.entries(sections).map(([id, value]) => [id, value.title])));
      const at = new Date().toISOString();
      setChat(prev => [...prev, { id: ++messageCounter.current, role: "user", text: message, at }, { id: ++messageCounter.current, role: "assistant", text: ack, at }]);
      if (speakReplies) { speech.prime(); void speech.speak(`layout-${messageCounter.current}`, ack); }
      followUntil.current = Date.now() + FOLLOW_UP_MS;
      return;
    }
    // What you talk about comes forward: "my calendar" opens Calendar, and so on.
    if (windowed && !photoQuestion) { const target = windowForText(message); if (target) shell.open(target); }
    setChat(prev => [...prev, { id: ++messageCounter.current, role: "user", text: message, photos: photoQuestion ? sharedPhotos : undefined, files: fileQuestion ? attachedFiles.map(file => file.name) : undefined, at: new Date().toISOString() }]);
    if (speakReplies) speech.prime();
    // Public identity information is safe to answer before authentication.
    // Everything else goes through the protected bridge (Tauri or phone token).
    if (!photoQuestion && !fileQuestion && isZaeniaIdentityQuestion(message)) {
      revealIdentity();
      setChat(prev => [...prev, { id: ++messageCounter.current, role: "assistant", text: ZAENIA_IDENTITY_REPLY, at: new Date().toISOString() }]);
      followUntil.current = Date.now() + FOLLOW_UP_MS;
      return;
    }
    const turn = ++turnRef.current;
    const live = () => turn === turnRef.current;
    const id = ++messageCounter.current;
    const key = `m${id}`;
    const reply: { id: number; text: string; added: boolean; at: string; proposal?: AssistantProposal } = { id, text: "", added: false, at: new Date().toISOString() };
    replyRef.current = reply;
    sendingRef.current = true;
    setSending(true);
    const speakIt = speakReplies && LIVE_API;
    if (speakIt) speech.beginReply(key);
    let timer: number | null = null;

    const draw = () => {
      timer = null;
      if (!live() || !reply.text) return;
      const text = reply.text;
      if (!reply.added) {
        reply.added = true;
        setStreamingId(id);
        setChat(prev => [...prev, { id, role: "assistant", text, at: reply.at, streaming: true, proposal: reply.proposal }]);
      } else setChat(prev => prev.map(item => item.id === id ? { ...item, text, proposal: reply.proposal } : item));
    };
    const end = () => {
      if (timer !== null) { window.clearTimeout(timer); timer = null; }
      streamRef.current = null;
      replyRef.current = null;
      sendingRef.current = false;
      setSending(false);
      setStreamingId(null);
      followUntil.current = Date.now() + FOLLOW_UP_MS;
    };
    const complete = (answer: string, interrupted: boolean) => {
      if (!live()) return;
      const streamed = reply.text;
      const text = (streamed.trim() ? streamed : answer).trim() || (reply.proposal && !interrupted ? "Review the details below, then save when you're ready." : "");
      reply.text = text;
      if (photoQuestion && text && !interrupted && photosRef.current === sharedPhotos) {
        photoTurns.current = [...photoHistory, { role: "user", content: message.slice(0, 4000) }, { role: "assistant", content: text.slice(0, 4000) }].slice(-6) as typeof photoHistory;
      }
      if (text) {
        const done: ChatMessage = { id, role: "assistant", text, at: reply.at, streaming: false, interrupted, proposal: interrupted ? undefined : reply.proposal };
        if (reply.proposal && !interrupted && policyRef.current?.chatAutomatic.includes(reply.proposal.kind) && (IN_TAURI || !["app.launch", "workspace.restore"].includes(reply.proposal.kind))) automaticCandidates.current.add(id);
        const shown = reply.added;
        reply.added = true;
        setChat(prev => shown ? prev.map(item => item.id === id ? done : item) : [...prev, done]);
        if (reply.proposal && !interrupted && reply.proposal.kind !== "memory.forget") window.setTimeout(() => applyRef.current(id), 60);
      }
      if (speakIt) {
        if (!streamed.trim() && text) speech.feed(key, text);
        speech.finishReply(key);
      }
      end();
    };
    const fail = (failure: unknown) => {
      if (!live()) return;
      const text = failure instanceof BridgeError ? failure.message : `Local ZÆNIA bridge: ${errorText(failure)}`;
      if (reply.text.trim()) complete(reply.text, true);
      else { if (speakIt) speech.stop(); end(); }
      setChat(prev => [...prev, { id: ++messageCounter.current, role: "error", text }]);
    };

    const outcome: { reply: string | null; interrupted: boolean; failure: string | null } = { reply: null, interrupted: false, failure: null };
    const stream = streamChat(message, event => {
      if (!live()) return;
      if (event.type === "delta") {
        reply.text += event.text;
        if (speakIt) speech.feed(key, event.text);
        if (timer === null) timer = window.setTimeout(draw, DRAW_MS);
      } else if (event.type === "proposal") {
        const proposal = parseAssistantProposal(event.proposal);
        if (proposal && !reply.proposal) {
          reply.proposal = proposal;
          if (windowed) shell.open(proposal.kind.startsWith("memory.") ? "assistant" : proposal.kind === "task.create" ? "tasks" : "calendar");
          if (timer === null) timer = window.setTimeout(draw, DRAW_MS);
        }
      } else if (event.type === "done") {
        outcome.reply = event.reply;
        outcome.interrupted = event.interrupted;
      } else if (event.type === "error") outcome.failure = event.detail;
    }, photoQuestion || fileQuestion ? {
      ...(photoQuestion ? { images: sharedPhotos.map(photo => photo.data.split(",")[1]), photoHistory } : {}),
      ...(fileQuestion ? { files: attachedFiles.map(file => ({ name: file.name, data: file.data })) } : {}),
    } : undefined);
    streamRef.current = stream;
    stream.done.then(() => {
      if (!live()) return;
      if (outcome.failure) { fail(new BridgeError(outcome.failure, "server")); return; }
      if (outcome.reply === null && !reply.text.trim() && !reply.proposal) { fail(new BridgeError("ZÆNIA returned an empty reply.", "server")); return; }
      complete(outcome.reply ?? reply.text, outcome.reply === null || outcome.interrupted);
    }, async (failure: unknown) => {
      if (!live()) return;
      if (photoQuestion || reply.text || !streamUnsupported(failure)) { fail(failure); return; }
      // An older ZÆNIA server or desktop app: the whole reply at once.
      try { complete(await askZaenia(message), false); }
      catch (error) { fail(error); }
    });
  }

  // ---- Microphone: tap-to-talk and always listening (while the app is open).
  // Names work anywhere in a sentence. Questions and directed replies continue
  // the current conversation, without admitting every nearby utterance.
  function onTranscript(result: Transcript, clipMode: VoiceMode, barged: boolean) {
    if (result.rejected) {
      // Not recognised as Grey's voice: drop it. Explain only when he was
      // clearly talking to the app (button press) or something needs fixing.
      if (barged) speech.duck(false);
      if (clipMode === "dictate" || result.rejected === "not_set_up") setVoiceNote(result.message || "That didn't sound like you.");
      return;
    }
    if (typeof result.nameRequired === "boolean") setOpenMic(!result.nameRequired);
    const words = (result.addressed ? result.command : result.text).trim();
    if (barged) {
      // Rule: the moment she hears you she has already stopped talking and
      // writing (onBargeIn) and is back to listening; what you said next is
      // treated as part of the conversation.
      followUntil.current = Date.now() + FOLLOW_UP_MS;
      if (!words || isEcho(result.text, speech.recentText())) { speech.duck(false); return; }
      if (isQuietVoiceAcknowledgement(result, true)) {
        speech.duck(false); followUntil.current = Date.now() + FOLLOW_UP_MS; setVoiceNote(null); return;
      }
      if (!acceptsVoiceTurn(result, true) && !isStopRequest(words) && !result.dismiss) { speech.duck(false); return; }
      interrupt();
      if (result.dismiss || isStopRequest(words)) { setVoiceNote("Stopped. Go ahead when you're ready."); return; }
      setVoiceNote(null); submit(words);
      return;
    }
    if (clipMode === "dictate") {
      if (!words) { setVoiceNote("Didn't catch that. Tap the mic and try again."); return; }
      setVoiceNote(null); submit(words);
      return;
    }
    if (isQuietVoiceAcknowledgement(result, sendingRef.current || Date.now() < followUntil.current)) {
      followUntil.current = Date.now() + FOLLOW_UP_MS;
      setVoiceNote(null);
      return;
    }
    if (sendingRef.current) {
      // While she's thinking: "Zay, stop" stops her; "Zay, <something else>" replaces the request.
      if (!acceptsVoiceTurn(result, Date.now() < followUntil.current)) return;
      if (!words || result.dismiss || isStopRequest(words)) { interrupt(); setVoiceNote("Stopped. Go ahead when you're ready."); return; }
      setVoiceNote(null); submit(words);
      return;
    }
    const inFollowUp = Date.now() < followUntil.current;
    if (result.dismiss && (result.addressed || inFollowUp)) {
      followUntil.current = 0;
      setVoiceNote("Standing by.");
      return;
    }
    if (result.addressed && !words) {
      followUntil.current = Date.now() + FOLLOW_UP_MS;
      setVoiceNote("Listening.");
    } else if ((acceptsVoiceTurn(result, inFollowUp) || parseLayoutCommand(words) || parseAppearanceCommand(words, appearance)) && words) {
      setVoiceNote(null); submit(words);
    }
  }
  const micPaused = briefingActive || speech.playing !== null || speech.loading !== null;
  // Desktop: talking over ZÆNIA lowers her voice at once, then stops her once your words are understood.
  const listen = useVoiceInput({ onTranscript, paused: micPaused, bargeIn: IN_TAURI && !briefingActive, onBargeIn: () => interruptRef.current() });
  const busy = sending || micPaused;
  // "/" from anywhere in the app jumps to the input, like a command bar.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
      if (target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))) return;
      event.preventDefault(); queryRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (!busy) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") interruptRef.current(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy]);
  // The follow-up window starts when ZÆNIA finishes speaking.
  const wasPlaying = useRef<string | null>(null);
  useEffect(() => {
    if (wasPlaying.current && !speech.playing) followUntil.current = Date.now() + FOLLOW_UP_MS;
    wasPlaying.current = speech.playing;
  }, [speech.playing]);
  const [followUpTick, setFollowUpTick] = useState(0);
  useEffect(() => {
    if (listen.mode !== "always") return;
    const id = window.setInterval(() => setFollowUpTick(v => v + 1), 2000);
    return () => window.clearInterval(id);
  }, [listen.mode]);
  const followUp = followUpTick >= 0 && Date.now() < followUntil.current;
  // ZÆNIA's PC voice service. On the PC itself it takes over listening so two
  // microphones don't answer the same "Zay".
  useEffect(() => {
    if (!LIVE_API) return;
    let cancelled = false;
    const load = () => api<{ running: boolean; state: string; recognising?: boolean | null; nameRequired?: boolean }>("GET", "/api/voice/status")
      .then(reply => {
        if (cancelled) return;
        setPcVoice({ running: reply.running, state: reply.state, recognising: reply.recognising });
        if (typeof reply.nameRequired === "boolean") setOpenMic(!reply.nameRequired);
      })
      .catch(() => { if (!cancelled) setPcVoice(null); });
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);
  // PC Voice only takes over while it recognises the owner's voice; when it
  // keeps rejecting him, the app keeps listening with its own mic.
  const pcTakesOver = IN_TAURI && pcVoice?.running === true && pcVoice.recognising !== false;
  const spokenNotices = useRef(new Set<string>());
  const allowNoticeSpeech = useRef(false);
  allowNoticeSpeech.current = !busy && !pcTakesOver && listen.status !== "hearing" && listen.status !== "transcribing";
  useEffect(() => {
    const notice = inbox.notice;
    if (!notice?.canSpeak || !allowNoticeSpeech.current || document.visibilityState === "hidden") return;
    const key = `${notice.id}:${notice.snoozedUntil ?? "initial"}`;
    if (spokenNotices.current.has(key)) return;
    spokenNotices.current.add(key);
    void api<{ id: string; claimed: boolean }>("POST", `/api/assistant/notifications/${encodeURIComponent(notice.id)}/claim`, { channel: "speech" })
      .then(result => {
        if (result.id === notice.id && result.claimed === true && allowNoticeSpeech.current && document.visibilityState === "visible") void speech.speak(`notice-${notice.id}`, notice.message);
      }).catch(() => { /* The inbox remains available if optional speech cannot be claimed. */ });
  }, [inbox.notice, busy, pcTakesOver, listen.status, speech.speak]);
  const tookOver = useRef(false);
  useEffect(() => {
    if (pcTakesOver) {
      tookOver.current = true;
      if (listen.mode === "always") listen.stop();
    } else if (tookOver.current) {
      // The PC service stopped: the app listens again if you had it on.
      tookOver.current = false;
      if (listen.alwaysWanted && listen.mode === "off") listen.setAlways(true);
    }
  }, [pcTakesOver, listen.mode]); // eslint-disable-line react-hooks/exhaustive-deps
  function toggleListening() {
    setVoiceNote(null); listen.clearError();
    listen.setAlways(!listen.alwaysWanted);
  }
  async function startPcVoice() {
    setVoiceNote("Opening the ZÆNIA Voice window on this PC. Enter your passkey there.");
    try { await startVoiceService(); }
    catch (failure) { setVoiceNote(`PC voice: ${errorText(failure)}`); }
  }

  const moduleInfo = telemetry?.modules.find(m => m.id === selectedModule);
  const headerStatus = source === "preview" ? (startup.ready ? "SYSTEM ONLINE · PREVIEW" : "SYSTEM STARTING") : (localTelemetry ? (localTelemetry.system?.mode === "unattended" ? "SYSTEM ONLINE · TOKEN MODE" : "SYSTEM ONLINE · LIVE") : "STATUS UNAVAILABLE");
  // The live phase drives the core at once; the workspace layout settles more slowly.
  const voicePhase = workspacePhase({
    hearing: listen.status === "hearing" || pcVoice?.state === "hearing",
    transcribing: listen.status === "transcribing",
    sending,
    speaking: speech.playing !== null || pcVoice?.state === "replying",
    preparingSpeech: speech.loading !== null,
  });
  const workspaceMotion = useWorkspaceMotion(voicePhase, motion, startup.ready);
  const coreBusy = sending || listen.status === "hearing" || pcVoice?.state === "hearing" || pcVoice?.state === "replying";
  // Window unfocused or hidden while ZAE is idle: the core holds still and animations pause.
  const background = useAppInBackground(voicePhase !== "idle" || coreBusy);
  const readFollowUntil = useCallback(() => followUntil.current, []);
  // Only the app's own always-on microphone uses this window; the PC voice service keeps its own.
  const showFollowUp = listen.mode === "always" && !pcTakesOver && !openMic;
  // Resting: after a quiet spell the conversation folds down and the core takes
  // the stage; any voice activity, new message, hover or focus brings it back.
  const [resting, setResting] = useState(false);
  const lastActive = useRef(Date.now());
  const wake = useCallback(() => { lastActive.current = Date.now(); setResting(false); }, []);
  useEffect(() => { if (voicePhase !== "idle") wake(); }, [voicePhase, wake]);
  useEffect(() => { wake(); }, [chat.length, section, wake]);
  useEffect(() => {
    const id = window.setInterval(() => {
      const quiet = Date.now() - lastActive.current > REST_MS && Date.now() > followUntil.current;
      if (quiet && !document.querySelector(".home-chat:focus-within")) setResting(true);
    }, 2000);
    return () => window.clearInterval(id);
  }, []);
  const restingNow = resting && workspaceMotion.settings.adaptive && voicePhase === "idle";

  const coreSettings = <>
          <AppearanceSettings value={appearance} onChange={setAppearance}/>
          <ScreenWatchSettings/>
          <GameCoachSettings/>
          <div className="detail-panel__block"><div className="section-heading"><span className="subheading">VISUAL SOURCE</span><span>LOCAL</span></div><h2>Neural Core</h2><p>The sphere and its six nerves are one network. Signals leave the nucleus and travel each branch to its module.</p><div className="mode-grid">{([{id:"blend",label:"Neural View"},{id:"progress",label:"Technical"}] as {id:VisualMode;label:string}[]).map(o=><button key={o.id} type="button" className={mode===o.id?"choice choice--active":"choice"} onClick={()=>{setMode(o.id);openSection("overview");}} aria-pressed={mode===o.id}>{o.label}</button>)}</div>
            <button className="setting-row" type="button" aria-pressed={motion} onClick={()=>setMotion(v=>!v)}><span className="setting-row__icon"><Icon name="bolt" size={18}/></span><span className="setting-row__content"><strong>Ambient motion</strong><small>Rotation and travelling signals</small></span><span className={`switch ${motion?"switch--on":""}`}><i/></span></button>
            <WorkspaceMotionControls settings={workspaceMotion.settings} toggle={workspaceMotion.toggle} resize={workspaceMotion.resize} reset={workspaceMotion.reset}/></div>
          <div className="detail-panel__block status-block"><div className="section-heading"><span className="subheading">MODULE STATUS</span><span>{String(readyCount).padStart(2,"0")} / {String(moduleTotal).padStart(2,"0")}</span></div><div className="module-list">{telemetry?.modules.map(m=><button type="button" className="module-button" key={m.id} title={m.detail} onClick={()=>{setSelectedModule(m.id);openSection("system");}}><span className={`module-item__dot module-item__dot--${m.phase}`}/><span>{m.name}</span><small className={`module-phase module-phase--${m.phase}`}>{phaseLabels[m.phase]}</small></button>)??<div className="hint">Status feed unavailable.</div>}</div></div>
          <div className="detail-panel__block"><span className="subheading">SYSTEM DATA</span><p>{source==="preview"?"Sample values. Switch to Live for real readiness from the ZÆNIA server.":connection}</p>{!canGoLive && <div className="choice-row"><button className={source==="preview"?"choice choice--active":"choice"} type="button" onClick={()=>setSource("preview")}>Preview</button><button className={source==="local"?"choice choice--active":"choice"} type="button" onClick={()=>setSource("local")} disabled title="Live status is available inside the desktop app">Live</button></div>}<div className="startup-control"><span>{startup.ready ? "STARTUP COMPLETE" : "STARTING CORE"} <strong>{startup.progress}%</strong></span><progress max="100" value={startup.progress}/><button className="choice" type="button" onClick={()=>setStartupReplay(v=>v+1)}>Replay 7-second startup</button><small>Visual startup only. Service readiness is shown in Status & Security.</small></div>{onForgetPhone && <div className="phone-forget"><button className={`choice${confirmForget ? " choice--danger" : ""}`} type="button" onClick={()=>{ if (confirmForget) onForgetPhone(); else setConfirmForget(true); }}>{confirmForget ? "Tap again to forget" : "Forget this phone"}</button><small>Signs out this phone. Reconnect with your voice or access token.</small></div>}</div>
  </>;

  // Every module shares the Tech News look: a masthead and glass panels.
  function glassBody(id: Section, masthead = true): ReactNode {
    const tab = tabAppearance(appearance, id);
    return <div className={`glass-module glass-module--${id}`} data-look={tab.look} style={tab.style as CSSProperties}>
      {masthead && id !== "news" && <ModuleMasthead label={sections[id].label} title={sections[id].title} description={sections[id].description}/>}
      <Suspense fallback={<p className="hint">Loading…</p>}>{sectionBody(id)}</Suspense>
    </div>;
  }

  function sectionBody(id: Section): ReactNode {
    switch (id) {
      case 'notes': return <NotesPanel draft={notesDraft.current} onDraft={next => { notesDraft.current = next; }}/>;
      case 'news': return <NewsPanel/>;
      case "security": return <SecurityPanel/>;
      case "status": return <StatusPanel onFix={runFix} onOpenSecurity={() => openSection("security")} telemetry={telemetry} source={source} connection={connection} startupReady={startup.ready} voice={LIVE_API ? { play: (key: string, text: string) => void speech.speak(key, text), stop: speech.stop, playing: speech.playing, loading: speech.loading } : undefined}/>;
      case "tasks": return <TasksDashboard remote={LIVE_API} refreshVersion={actionRefresh.tasks}/>;
      case "calendar": return <CalendarPanel refreshVersion={actionRefresh.calendar}/>;
      case "assistant": return <><PlatformPanel runtime={platformRuntime} windows={shell.windows} onRestore={restoreWindows} hands={hands} handsSupported={handsSupported} handNote={handNote} toggleHands={() => { setHands(value => !value); setHandNote(null); }}/><AssistantPanel refreshVersion={assistantRefresh} onChanged={() => { void inbox.refresh(); speech.prime(); }}/></>;
      case "files": return <FilesPanel onPendingChange={setPendingFiles}/>;
      case "system": return <><div className="section-content"><div className="section-content__tag">MODULE DIAGNOSTICS <span>{source==="preview"?"PREVIEW ONLY":"LOCAL STATUS MODE"}</span></div><div className="system-list">{telemetry?.modules.map(m=><button type="button" key={m.id} className={`system-module ${selectedModule===m.id?"system-module--selected":""}`} onClick={()=>setSelectedModule(m.id)}><span className={`module-item__dot module-item__dot--${m.phase}`}/><strong>{m.name}</strong><small>{phaseLabels[m.phase]}</small></button>) ?? <div className="empty-state">No validated module data received.</div>}</div><div className="file-detail"><span>SELECTED MODULE</span><strong>{moduleInfo?.name ?? "No module selected"}</strong><p>{moduleInfo ? `Reported state: ${phaseLabels[moduleInfo.phase]}. ${source==="preview" ? "This is illustrative sample data, not a verified runtime check." : moduleInfo.detail ? moduleInfo.detail + "." : "Read-only status from the live feed."}` : "Choose a module to inspect its displayed status."}</p><small>{source==="local" ? connection : "No real module control or authentication changes from this panel."}</small></div></div><div className="core-settings" aria-label="Neural core settings">{coreSettings}</div></>;
      default: return null;
    }
  }

  return <div className={`zaenia-app zaenia-app--dynamic${workspaceMotion.animate ? " zaenia-app--motion" : ""}${isPhone ? " zaenia-app--phone" : ""}${isPhone && sheetOpen ? " zaenia-app--sheet" : ""}${restingNow ? " zaenia-app--resting" : ""}${background ? " zaenia-app--background" : ""}${appearance.orbs === "match" ? " zaenia-app--orbs-match" : ""}${sidebarHidden ? " zaenia-app--no-sidebar" : ""}${isPhone ? "" : " zaenia-app--no-aside"}${appearance.font !== "default" ? " zaenia-app--font" : ""}${appearance.size !== 100 ? " zaenia-app--sized" : ""}${appearance.accent !== "amber" || appearance.glow !== 100 ? " zaenia-app--tinted" : ""}`} style={{ ...workspaceMotion.style, ...appearanceStyle(appearance) } as CSSProperties} data-workspace-phase={workspaceMotion.phase}>
    <CoreBackdrop/>
    <HandControls enabled={hands} onDisable={reason => { setHands(false); setHandNote(reason ?? "Camera hand controls off."); gestureDrag.current = null; }} onCommand={handleGesture}/>
    {isPhone && sheetOpen && <div className="sheet-scrim" aria-hidden="true" onClick={()=>setSheetOpen(false)}/>}
    <header className="identity-header" aria-label="ZÆNIA identity and desktop status">
      <div className="brand-menu" onMouseEnter={() => { setBrandOpen(true); setIdentityHovered(true); }} onMouseLeave={() => { setBrandOpen(false); setIdentityHovered(false); }}>
        <button type="button" className="identity-header__panel" onClick={() => setBrandOpen(open => !open)} aria-expanded={brandOpen} aria-haspopup="menu"
          aria-label="ZÆNIA: show every part of the app and its status">
          <span className="brand-glyph"><Icon name="system" size={29}/></span>
          <span className="brand-type"><strong>ZÆNIA</strong><span className={showExpandedIdentity ? "brand-type__definition" : "brand-type__subtitle"}>{showExpandedIdentity ? ZAENIA_IDENTITY_DESCRIPTION : "Z.A.E.N.I.A. · Zack’s Ædaptive, Neural, Intelligent Agent"}</span></span>
        </button>
        {brandOpen && <div className="brand-menu__drop" role="menu" aria-label="Parts of ZÆNIA">
          <div className="brand-menu__group">WORKSPACE</div>
          {nav.map(item => <button key={item.id} type="button" role="menuitem" className="brand-menu__item" onClick={() => { openSection(item.id); setBrandOpen(false); }}>
            <Icon name={item.icon} size={15}/><span>{item.label}</span>
            {item.id === "files" && pendingFiles > 0 && <em className="brand-menu__pill brand-menu__pill--pending">{pendingFiles} waiting</em>}
          </button>)}
          <div className="brand-menu__group">SYSTEMS</div>
          <div className="brand-menu__item brand-menu__item--static"><span className={`module-item__dot module-item__dot--${live ? "ready" : "error"}`}/><span>Server</span><em className="brand-menu__pill">{live ? "Connected" : "Unavailable"}</em></div>
          <div className="brand-menu__item brand-menu__item--static"><span className={`module-item__dot module-item__dot--${pcVoice?.running ? "ready" : "pending"}`}/><span>PC voice</span><em className="brand-menu__pill">{pcVoice?.running ? "Listening" : "Off"}</em></div>
          {telemetry?.modules.map(m => <div key={m.id} className="brand-menu__item brand-menu__item--static" title={m.detail}><span className={`module-item__dot module-item__dot--${m.phase}`}/><span>{m.name}</span><em className="brand-menu__pill">{phaseLabels[m.phase]}</em></div>)}
          {IN_TAURI && <div className="brand-menu__restarts">
            <button type="button" className="brand-menu__restart" onClick={() => {
              setRestartNote("Restarting the server with the API token…");
              restartServer().then(() => setRestartNote("Restart started. Give it about 20 seconds.")).catch(failure => setRestartNote(errorText(failure)));
            }}>Restart (API token)</button>
            <button type="button" className="brand-menu__restart" onClick={() => {
              setRestartNote("Type your passkey in the ZÆNIA Server window.");
              startServer("passkey").catch(failure => setRestartNote(errorText(failure)));
            }}>Restart with passkey</button>
          </div>}
          {IN_TAURI && <label className="brand-menu__auto"><span>When the app opens and the server is off</span>
            <select value={autoStart} onChange={event => { const v = event.target.value as "" | "token" | "passkey"; setAutoStart(v); try { localStorage.setItem("zaenia.autoStart", v); } catch { /* optional */ } }}>
              <option value="">Ask me</option><option value="token">Start with API token</option><option value="passkey">Start with passkey</option>
            </select></label>}
          {restartNote && <p className="brand-menu__note" role="status">{restartNote}</p>}
        </div>}
      </div>
      <div className="topbar"><div className="topbar__meta">
        <span className="preview-status"><span className="preview-status__dot"/>{headerStatus}</span>
        {weather && weather.temperature !== null && <span className="topbar__weather" title={`${weather.place}: high ${Math.round(weather.high ?? 0)}°, low ${Math.round(weather.low ?? 0)}°`}>{Math.round(weather.temperature)}° <small>{sentenceCase(weather.condition)}</small></span>}
        <BackgroundWorkBadge jobs={platformRuntime.summary?.jobs ?? []} onOpen={() => { openSection("assistant"); window.setTimeout(() => window.dispatchEvent(new CustomEvent("zae:assistant-tab", { detail: "Work" })), 60); }}/>
        <span className="topbar__time"><Icon name="clock" size={14}/>{time.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })} · {time.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</span>
        {isPhone && <button type="button" className="sheet-toggle" aria-label={sheetOpen ? "Close core panel" : "Open core panel"} aria-expanded={sheetOpen} aria-controls="core-panel" onClick={()=>setSheetOpen(v=>!v)}><Icon name="panel" size={18}/></button>}
      </div></div>
    </header>
    {!sidebarHidden && <aside className="sidebar" aria-label="Main navigation">
      <div className="sidebar__group-label">WORKSPACE</div>
      <nav className="sidebar__nav">{nav.map(item => <button key={item.id} className={`nav-item ${section===item.id?"nav-item--active":""}`} aria-current={section===item.id?"page":undefined} type="button" onClick={()=>openSection(item.id)} title={item.label}><Icon name={item.icon}/><span>{isPhone ? item.short : item.label}</span>{item.id === "files" && pendingFiles > 0 && <span className="nav-item__badge" aria-label={`${pendingFiles} file change${pendingFiles > 1 ? "s" : ""} waiting`}>{pendingFiles}</span>}{section===item.id && <span className="nav-item__indicator"/>}</button>)}</nav>
      <div className="sidebar__bottom"><div className="sidebar__separator"/><div className="identity-card"><div className="identity-card__initial">Z</div><div><strong>Desktop Interface</strong><span>Local-first UI</span></div></div><span className="sidebar__version">ZÆNIA / NEURAL CORE 06</span></div>
    </aside>}
    <main className="workspace">
      <div className="dashboard">
        <section className={`main-stage main-stage--${stageSection}`} aria-labelledby="main-title"
          onPointerOverCapture={event => { if (restingNow && (event.target as HTMLElement).closest(".home-chat")) wake(); }}
          onFocusCapture={event => { if ((event.target as HTMLElement).closest(".home-chat")) wake(); workspaceMotion.setFocused(Boolean((event.target as HTMLElement).closest(".home-chat"))); }}
          onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) workspaceMotion.setFocused(false); }}>
          {stageSection === "overview"
            ? <h1 id="main-title" className="sr-only">{info.title}</h1>
            : <div className="stage-copy"><div className="eyebrow"><span className="eyebrow__line"/>{info.label}</div><h1 id="main-title">{info.title}<span>.</span></h1><p>{info.description}</p></div>}
          {stageSection === "overview" && <div className={`progress-stage progress-stage--${coreDock}`}>{mode === "blend" ? <NeuralCore telemetry={telemetry} source={source} motion={motion} paused={background} processing={coreBusy} startup={startup} onSelect={(next)=>openSection(next)} phase={voicePhase} followUntil={showFollowUp ? readFollowUntil : undefined}/> : <SystemProgressCore telemetry={telemetry} source={source} motion={motion} visualMode={mode}/>}</div>}
          {!windowed && section !== "overview" && glassBody(section, false)}
          {windowed && <div className={`os-layer os-layer--${voicePhase}${restingNow ? " os-layer--resting" : ""}`} ref={layerRef}>
            {shell.windows.filter(win => !win.minimized).map(win => <AppWindow key={win.id} win={win} title={sections[win.id as Section].title} label={sections[win.id as Section].label}
              active={shell.active === win.id} stage={() => layerRef.current?.getBoundingClientRect() ?? null}
              onAttention={() => { attendedTab.current = win.id; }}
              onFocus={() => { attendedTab.current = win.id; shell.open(win.id); }} onClose={() => shell.close(win.id)} onMinimize={() => shell.minimize(win.id)} onChange={rect => shell.update(win.id, rect)}>
              {glassBody(win.id as Section)}
            </AppWindow>)}
          </div>}
          {windowed && <Dock windows={shell.windows} titles={Object.fromEntries(WINDOW_IDS.map(id => [id, sections[id as Section].title]))} active={shell.active} onOpen={shell.open}
            onTarget={id => { attendedTab.current = id; }} onClose={shell.close} onMinimize={shell.minimize}
            onCloseAll={shell.closeAll} onMinimizeAll={shell.showDesktop} onRestoreAll={shell.restoreAll} onChange={shell.update}
            onPlace={(id, spot) => runLayout([{ kind: "place", target: id as LayoutTarget, spot, small: true }])}/>}
          {stageSection === "overview" && inbox.notice && <section className="assistant-notice" role="status" aria-label="ZÆNIA follow-through">
            <strong>{inbox.notice.title}</strong><p>{inbox.notice.message}</p>
            <div><button type="button" onClick={() => openSection("assistant")}>Open Assistant{inbox.unreadCount > 0 ? ` (${inbox.unreadCount})` : ""}</button>
              <button type="button" onClick={() => void inbox.acknowledge(inbox.notice!)}>Mark read</button>
              <button type="button" onClick={() => void inbox.snooze(inbox.notice!)}>Snooze 15 min</button>
              <button type="button" onClick={() => { speech.prime(); void speech.speak(`notice-${inbox.notice!.id}`, inbox.notice!.message); }}>Read aloud</button></div>
          </section>}
          {serverDown && !launchDismissed && <section className="launch-card" role="dialog" aria-label="Start ZÆNIA's server">
            <span className="launch-card__eyebrow">SERVER OFFLINE</span>
            <h2>Start ZÆNIA</h2>
            <p>{launchNote ?? "Her server isn't running. How should it start?"}</p>
            <div className="launch-card__buttons">
              <button type="button" onClick={() => launchServer("token", rememberStart)}><strong>API token</strong><small>Starts quietly. Chat, tasks, calendar and status.</small></button>
              <button type="button" onClick={() => launchServer("passkey", rememberStart)}><strong>Passkey</strong><small>Full owner features. You type the passkey once.</small></button>
            </div>
            <label className="launch-card__remember"><input type="checkbox" checked={rememberStart} onChange={event => setRememberStart(event.target.checked)}/> Always start this way</label>
            <button type="button" className="launch-card__later" onClick={() => setLaunchDismissed(true)}>Not now</button>
          </section>}
          {connectionNotice && <p className="phone-connect__message" role="status">{connectionNotice}</p>}
          {LIVE_API && <BrowserBriefing onAuthLost={onAuthLost} onActive={setBriefingActive} beforePlay={speech.stop}/>}
          {/* Talk to ZÆNIA from every page: input bar plus a floating transcript. */}
          <HomeConversation
            photos={photos} onPhotos={changePhotos} files={sharedFiles} onFiles={changeFiles}
            messages={chat} sending={sending} busy={busy} onStop={interrupt} streamingId={streamingId} query={query} onQuery={setQuery} onSubmit={sendChat} inputRef={queryRef}
            live={LIVE_API} history={history}
            onApplyProposal={messageId => void applyProposal(messageId)} onDismissProposal={dismissProposal}
            voice={{ available: LIVE_API, on: speakReplies, toggle: toggleSpeak, playing: speech.playing, loading: speech.loading, error: speech.error,
              play: (key, text) => void speech.speak(key, text), stop: speech.stop }}
            historyError={historyError}
            listen={{ supported: listen.supported, mode: listen.mode, status: listen.status, alwaysWanted: listen.alwaysWanted,
              toggleAlways: toggleListening, dictate: () => { setVoiceNote(null); listen.clearError(); if (listen.mode !== "dictate") interrupt(); if (speakReplies) speech.prime(); listen.dictate(); },
              meterRef: listen.meterRef, note: voiceNote, error: listen.error, followUp: followUp && listen.mode === "always", openMic, bargeIn: listen.bargeIn,
              pc: pcVoice, pcTakesOver, canStartPc: IN_TAURI && pcVoice !== null && !pcVoice.running, startPc: () => void startPcVoice() }}
          />
          <div className="stage-footer"><div><span className="stage-footer__line"/>{source==="preview"?"VISUAL PREVIEW ACTIVE":live?"LIVE STATUS":"STATUS OFFLINE"}<span className="stage-footer__dim"> / {photos.length ? "PHOTO CONVERSATION · THIS SESSION ONLY" : LIVE_API ? "CONVERSATION SAVED IN ZÆNIA MEMORY" : "PREVIEW"}</span></div><button type="button" className="text-action" onClick={()=>openSection(section==="system"?"overview":"system")}>{section==="system"?"BACK TO CORE":"SYSTEM DETAILS"} <Icon name="arrow" size={17}/></button></div>
        </section>
        {/* Desktop: tech headlines down the right side (hide with the › button). */}
        {!isPhone && <NewsRail onOpenAll={() => openSection("news")}/>}
        {isPhone && <aside
          id="core-panel"
          className="detail-panel"
          aria-label="Core status and controls"
          aria-hidden={isPhone && !sheetOpen ? true : undefined}
          onTouchStart={(e)=>{ if (isPhone && e.currentTarget.scrollTop <= 0) sheetTouch.current = e.touches[0].clientY; }}
          onTouchEnd={(e)=>{ const start = sheetTouch.current; sheetTouch.current = null; if (start !== null && e.changedTouches[0].clientY - start > 70) setSheetOpen(false); }}
        >
          {isPhone && <button type="button" className="sheet-handle" aria-label="Close core panel" onClick={()=>setSheetOpen(false)}><span/></button>}
          <div className="detail-panel__block core-status">
            <div className="section-heading"><span className="subheading">01 / CORE STATUS</span><span>{source==="preview"?"PREVIEW":live?"LIVE":"OFFLINE"}</span></div>
            <div className="status-row"><span>Neural Core</span><Wave tone="blue" live={liveMotion}/><strong className="tone-blue">{!startup.ready ? `${startup.progress}%` : source === "local" && !live ? "OFFLINE" : "ONLINE"}</strong></div>
            <div className="status-row"><span>System Load</span><span className="status-bar"><i style={{width:`${systemLoad ?? 0}%`}}/></span><strong className="tone-blue">{systemLoad === null ? "—" : `${systemLoad}%`}</strong></div>
            {memoryLoad !== null && <div className="status-row"><span>Memory</span><span className="status-bar"><i style={{width:`${memoryLoad}%`}}/></span><strong className="tone-blue">{memoryLoad}%</strong></div>}
            <div className="status-row"><span>Neural Activity</span><Wave tone="amber" live={liveMotion}/><strong className="tone-amber">{sending ? "PROCESSING" : !startup.ready ? "WAKING" : motion ? "ACTIVE" : "PAUSED"}</strong></div>
            <div className="status-row"><span>Sync Status</span><span/><strong>{telemetry ? sentenceCase(telemetry.synchronization) : "Unavailable"}</strong></div>
            <div className="status-row"><span>Modules</span><span/><strong className="tone-amber">{readyCount} / {moduleTotal}</strong></div>
          </div>
          <div className="detail-panel__block glass-quick-tools"><span className="subheading">QUICK TOOLS</span><div className="quick-tools"><button type="button" onClick={()=>openSection("tasks")}><Icon name="plus"/>New Task</button><button type="button" onClick={()=>{setSheetOpen(false);window.setTimeout(()=>queryRef.current?.focus(),60);}}><Icon name="chat"/>Ask ZÆNIA</button><button type="button" onClick={()=>openSection("files")}><Icon name="files"/>Files{pendingFiles > 0 && <span className="quick-tools__badge">{pendingFiles}</span>}</button><button type="button" onClick={()=>openSection("status")}><Icon name="pulse"/>System Check</button></div></div>
          {coreSettings}
          <div className="detail-panel__foot"><Icon name="check" size={16}/><span>{WEB_APP ? "This phone uses your verified voice session or token for briefings, chat, tasks and calendar. File changes made here wait for your approval in the desktop app. Owner security stays behind the passkey at the PC." : LIVE_API ? "Chat, tasks, calendar and files go through the protected desktop bridge. File saves keep a backup; owner security stays behind the passkey." : "Preview mode: sample status and device-only tasks. Open the desktop or phone app for live features."}</span></div>
        </aside>}
      </div>
    </main>
  </div>;
}
