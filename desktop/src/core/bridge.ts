import { Channel, invoke } from "@tauri-apps/api/core";
import { localStatusEndpoint } from "./coreTelemetry";
import type { AssistantProposal } from "./assistantActions";

/**
 * How the UI reaches the ZÆNIA server.
 *
 * - Desktop app (Tauri): status and chat go through the Rust bridge, so the API
 *   token stays inside the app and never reaches the page.
 * - Phone web app (`npm run build:web`, served by the ZÆNIA server at /app/):
 *   the page calls the same server it was loaded from, with the token entered
 *   once on the phone.
 * - Plain browser preview: read-only status from an opt-in loopback endpoint.
 */
export const IN_TAURI = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
export const WEB_APP = !IN_TAURI && import.meta.env.MODE === "web";
const endpoint = localStatusEndpoint();
export const canGoLive = IN_TAURI || WEB_APP || Boolean(endpoint);

const TOKEN_HEADER = "X-ZAENIA-API-TOKEN";
const TOKEN_KEY = "zaenia.phone.token";
const STATUS_TIMEOUT_MS = 10_000;
const CHAT_TIMEOUT_MS = 150_000;

export type BridgeFailure = "auth" | "offline" | "locked" | "server" | "conflict" | "invalid" | "forbidden" | "missing";
export class BridgeError extends Error {
  readonly kind: BridgeFailure;
  readonly status?: number;
  constructor(message: string, kind: BridgeFailure, status?: number) { super(message); this.name = "BridgeError"; this.kind = kind; this.status = status; }
}

// The token is kept only in this phone's web-app storage.
export function savedToken(): string | null {
  try { const raw = window.localStorage.getItem(TOKEN_KEY); return raw && raw.trim() ? raw.trim() : null; }
  catch { return null; }
}
export function saveToken(token: string): boolean {
  try { window.localStorage.setItem(TOKEN_KEY, token.trim()); return true; }
  catch { return false; }
}
export function forgetToken(): void {
  try { window.localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
}

export type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

// FastAPI sends `detail` as text, or as a list of field errors.
function detailText(data: unknown): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    if (first && typeof first.msg === "string") return first.msg;
  }
  return "";
}

function failureFor(status: number): BridgeFailure {
  if (status === 401) return "auth";
  if (status === 503) return "locked";
  if (status === 409) return "conflict";
  if (status === 403) return "forbidden";
  if (status === 404) return "missing";
  if (status === 400 || status === 422) return "invalid";
  if (status === 502 || status === 504) return "offline";
  return "server";
}

async function callServer(path: string, token: string, timeoutMs: number, body?: unknown, method?: Method, extra: Record<string, string> = {}): Promise<unknown> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers: Record<string, string> = { Accept: "application/json", [TOKEN_HEADER]: token };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let reply: Response;
  try {
    reply = await fetch(path, {
      method: method ?? (body === undefined ? "GET" : "POST"),
      cache: "no-store", credentials: "same-origin", referrerPolicy: "no-referrer",
      headers: { ...headers, ...extra, "X-ZAENIA-APP": "1" }, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) throw new BridgeError("ZÆNIA didn't answer in time. Your PC may be busy or asleep.", "offline");
    throw new BridgeError("Can't reach your PC. Check that it's on and that this phone is connected to it.", "offline");
  } finally { window.clearTimeout(timer); }
  if (reply.status === 401) {
    let detail = "";
    try { detail = detailText(await reply.json()); } catch { /* not JSON */ }
    throw new BridgeError(detail || "Sign in again with your voice or access token.", "auth", reply.status);
  }
  if (!reply.ok) {
    let detail = "";
    try { detail = detailText(await reply.json()); } catch { /* not JSON */ }
    if (reply.status === 503) throw new BridgeError(detail || "ZÆNIA is running but this feature is locked.", "locked", reply.status);
    if (reply.status === 502 || reply.status === 504) throw new BridgeError("Your PC is reachable but the ZÆNIA server isn't running.", "offline", reply.status);
    throw new BridgeError(detail || `ZÆNIA server error ${reply.status}.`, failureFor(reply.status), reply.status);
  }
  try { return await reply.json(); }
  catch { throw new BridgeError("ZÆNIA sent a reply this app couldn't read.", "server"); }
}

function requireToken(): string {
  // A voice session is carried by an HttpOnly cookie, never JavaScript storage.
  return savedToken() ?? "";
}

/** Phone setup: confirm a token with the server before saving it. */
export async function checkToken(token: string): Promise<void> {
  await callServer("/api/auth/check", token.trim(), STATUS_TIMEOUT_MS);
}

export async function checkPhoneConnection(): Promise<void> {
  await callServer("/api/auth/check", requireToken(), STATUS_TIMEOUT_MS);
}

export type VoiceChallenge = { challenge_id: string; phrase: string; expires_in: number };
export async function beginVoiceLogin(): Promise<VoiceChallenge> {
  return await callServer("/api/auth/voice/challenge", "", STATUS_TIMEOUT_MS, {}) as VoiceChallenge;
}
export async function completeVoiceLogin(challengeId: string, audio: string): Promise<void> {
  await callServer("/api/auth/voice/verify", "", 120_000, { challenge_id: challengeId, audio });
  forgetToken();
}
export async function disconnectPhone(): Promise<void> {
  await callServer("/api/auth/logout", "", STATUS_TIMEOUT_MS, {});
  forgetToken();
}

export async function briefingAudio(sessionId: string): Promise<Blob> {
  if (IN_TAURI) {
    try {
      const bytes = await invoke<number[]>("zaenia_briefing_audio", { sessionId });
      return new Blob([new Uint8Array(bytes)], { type: "audio/wav" });
    } catch (error) { throw fromTauri(error); }
  }
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 30_000);
  try {
    const reply = await fetch(`/api/briefing/audio?session_id=${encodeURIComponent(sessionId)}`, {
      cache: "no-store", credentials: "same-origin", signal: controller.signal,
      headers: { [TOKEN_HEADER]: requireToken(), "X-ZAENIA-APP": "1" },
    });
    if (!reply.ok) throw new BridgeError(reply.status === 401 ? "Sign in again to hear your briefing." : "The briefing audio couldn't be loaded.", failureFor(reply.status), reply.status);
    return await reply.blob();
  } catch (error) {
    if (error instanceof BridgeError) throw error;
    throw new BridgeError("The briefing audio couldn't reach this phone. Try again.", "offline");
  } finally { window.clearTimeout(timer); }
}

/** Raw status JSON; the caller validates it with parseCoreTelemetry. */
export async function readStatus(signal?: AbortSignal): Promise<unknown> {
  if (IN_TAURI) return invoke<unknown>("zaenia_status");
  if (WEB_APP) return callServer("/api/status", requireToken(), STATUS_TIMEOUT_MS);
  if (!endpoint) throw new Error("No live status source in this preview");
  const reply = await fetch(endpoint, { method: "GET", cache: "no-store", credentials: "omit", headers: { Accept: "application/json" }, signal });
  if (!reply.ok) throw new Error(`HTTP ${reply.status}`);
  return reply.json();
}

/** One chat turn through ZÆNIA's protected conversation route. */
export async function askZaenia(message: string): Promise<string> {
  if (IN_TAURI) {
    let answer: unknown;
    try { answer = await invoke<unknown>("ask_zaenia", { message }); }
    catch (error) { throw fromTauri(error); }
    return typeof answer === "string" ? answer : JSON.stringify(answer);
  }
  if (WEB_APP) {
    const data = await callServer("/api/chat", requireToken(), CHAT_TIMEOUT_MS, { message }) as { reply?: unknown };
    if (typeof data.reply !== "string" || !data.reply.trim()) throw new BridgeError("ZÆNIA returned an empty reply.", "server");
    return data.reply;
  }
  throw new BridgeError("Chat needs the desktop app or the phone app.", "offline");
}

/** Live features (tasks, calendar, files, history, speech) need the server. */
export const LIVE_API = IN_TAURI || WEB_APP;
/** Only the desktop app holds the approval key for file changes. */
export const DESKTOP_APPROVER = IN_TAURI;

// Tauri errors arrive as "ZÆNIA API error 409: detail".
function fromTauri(error: unknown): BridgeError {
  const text = error instanceof Error ? error.message : String(error);
  const match = /^ZÆNIA API error (\d{3}): ([\s\S]*)$/.exec(text);
  if (match) return new BridgeError(match[2], failureFor(Number(match[1])), Number(match[1]));
  if (/not reachable/i.test(text)) return new BridgeError("The ZÆNIA server isn't running on this PC.", "offline");
  if (/isn't paired|approval key/i.test(text)) return new BridgeError(text, "forbidden");
  return new BridgeError(text, "server");
}

/** One call to a protected ZÆNIA route, through the desktop bridge or the phone token. */
export async function api<T = unknown>(method: Method, path: string, body?: unknown, options: { desktop?: boolean; timeoutMs?: number } = {}): Promise<T> {
  if (IN_TAURI) {
    try { return await invoke<T>("zaenia_api", { method, path, body: body ?? null, desktop: Boolean(options.desktop) }); }
    catch (error) { throw fromTauri(error); }
  }
  if (WEB_APP) return await callServer(path, requireToken(), options.timeoutMs ?? 30_000, body, method,
    options.desktop && nearPass ? { [NEAR_HEADER]: nearPass.secret } : {}) as T;
  throw new BridgeError("This needs the ZÆNIA server. Open the desktop app or the phone app.", "offline");
}

/**
 * Phone confirms at the PC (Grey, 2026-10-30): the code on the PC screen plus a voice check on the phone, in either
 * order, let this phone approve the listed confirms for 10 minutes. The pass lives only in this page's memory.
 */
const NEAR_HEADER = "X-ZAENIA-NEAR-PASS";
export type NearPassState = { pass: boolean; code: boolean; voice: boolean; active: boolean; secondsLeft: number };
let nearPass: { secret: string; until: number; active: boolean } | null = null;
function nearChanged(state: NearPassState) {
  if (nearPass) { nearPass.active = state.active; nearPass.until = Date.now() + state.secondsLeft * 1000; }
  if (!state.pass) nearPass = null;
  window.dispatchEvent(new CustomEvent("zae:near-pass", { detail: state }));
  return state;
}
/** True while this phone can approve listed confirms. */
export function nearPassActive(): boolean { return Boolean(nearPass?.active && Date.now() < nearPass.until); }
export async function startNearPass(): Promise<NearPassState> {
  const reply = await callServer("/api/near/start", requireToken(), STATUS_TIMEOUT_MS, {}) as NearPassState & { secret: string };
  nearPass = { secret: reply.secret, until: 0, active: false };
  return nearChanged({ pass: reply.pass, code: reply.code, voice: reply.voice, active: reply.active, secondsLeft: reply.secondsLeft });
}
export async function nearPassStatus(): Promise<NearPassState> {
  if (!nearPass) return { pass: false, code: false, voice: false, active: false, secondsLeft: 0 };
  return nearChanged(await callServer("/api/near/status", requireToken(), STATUS_TIMEOUT_MS, undefined, "GET", { [NEAR_HEADER]: nearPass.secret }) as NearPassState);
}
export async function submitNearCode(code: string): Promise<NearPassState> {
  if (!nearPass) throw new BridgeError("Start again from the remote.", "invalid");
  try { return nearChanged(await callServer("/api/near/code", requireToken(), STATUS_TIMEOUT_MS, { code }, "POST", { [NEAR_HEADER]: nearPass.secret }) as NearPassState); }
  catch (error) { if (error instanceof BridgeError && error.status === 403) nearChanged({ pass: false, code: false, voice: false, active: false, secondsLeft: 0 }); throw error; }
}
export async function nearVoice(challengeId: string, audio: string): Promise<NearPassState> {
  if (!nearPass) throw new BridgeError("Start again from the remote.", "invalid");
  return nearChanged(await callServer("/api/auth/voice/near", "", 120_000, { challenge_id: challengeId, audio }, "POST", { [NEAR_HEADER]: nearPass.secret }) as NearPassState);
}
export async function endNearPass(): Promise<void> {
  const secret = nearPass?.secret;
  nearChanged({ pass: false, code: false, voice: false, active: false, secondsLeft: 0 });
  if (secret) await callServer("/api/near/end", requireToken(), STATUS_TIMEOUT_MS, {}, "POST", { [NEAR_HEADER]: secret }).catch(() => undefined);
}

export const errorText = (error: unknown) => error instanceof Error ? error.message : String(error);

/** Owner passphrases are entered in a real local console, never this page. */
export async function openProfileTool(mode: "export" | "restore" | "rollback" | "voice_only", request: string): Promise<void> {
  if (!IN_TAURI) throw new BridgeError("Use the Windows desktop app for owner-authenticated profile operations.", "forbidden");
  try { await invoke("run_profile_tool", { mode, request }); }
  catch (error) { throw fromTauri(error); }
}

export type SecurityTool = "unlock_passkey" | "unlock_voice" | "token_rotate" | "token_revoke" | "pair_desktop"
  | "phrase_setup" | "phrase_reset" | "mic_change" | "mic_reset" | "phone_voice_on" | "phone_voice_off";
/** Desktop only: the Security tab's owner console. The passkey or phrase is entered there, never this page. */
export async function openSecurityTool(mode: SecurityTool, request?: string): Promise<void> {
  if (!IN_TAURI) throw new BridgeError("The Security tab opens only in the ZÆNIA desktop app on the PC.", "forbidden");
  try { await invoke("run_security_tool", { mode, request: request ?? null }); }
  catch (error) { throw fromTauri(error); }
}

/** Desktop only: open the ZÆNIA Voice window on the PC (the passkey is typed there). */
export async function startVoiceService(): Promise<void> {
  if (!IN_TAURI) throw new BridgeError("Start the PC voice service from the desktop app.", "forbidden");
  try { await invoke("start_voice_service"); }
  catch (error) { throw fromTauri(error); }
}

/** Desktop only: restart the ZÆNIA API server with the project's restart script. */
export async function restartServer(): Promise<void> {
  if (!IN_TAURI) throw new BridgeError("Restart the server from the desktop app on the PC.", "forbidden");
  try { await invoke("restart_server"); }
  catch (error) { throw fromTauri(error); }
}

/** Desktop only: start the server with the API token (hidden) or the passkey (opens a window to type it). */
export async function startServer(mode: "token" | "passkey"): Promise<void> {
  if (!IN_TAURI) throw new BridgeError("Start the server from the desktop app on the PC.", "forbidden");
  try { await invoke("start_server", { mode }); }
  catch (error) { throw fromTauri(error); }
}

/** Desktop only: open the one-time Google Calendar sign-in window. */
export async function connectGoogleCalendar(): Promise<void> {
  if (!IN_TAURI) throw new BridgeError("Connect Google Calendar from the desktop app on the PC.", "forbidden");
  try { await invoke("connect_google_calendar"); }
  catch (error) { throw fromTauri(error); }
}

/** Desktop only: open the guided voice training window. */
export async function openVoiceTraining(): Promise<void> {
  if (!IN_TAURI) throw new BridgeError("Voice training runs on the PC, from the desktop app.", "forbidden");
  try { await invoke("open_voice_training"); }
  catch (error) { throw fromTauri(error); }
}

/** Desktop only: open the one-time Gmail (read-only) sign-in window. */
export async function connectGmail(): Promise<void> {
  if (!IN_TAURI) throw new BridgeError("Connect Gmail from the desktop app on the PC.", "forbidden");
  try { await invoke("connect_gmail"); }
  catch (error) { throw fromTauri(error); }
}

// ---- Streaming chat ------------------------------------------------------
export type StreamEvent =
  | { type: "start"; id: string }
  | { type: "route"; route: string; brain?: string; level?: number; model?: string }
  | { type: "delta"; text: string }
  | { type: "proposal"; proposal: AssistantProposal }
  | { type: "protocol"; open: string[] }
  | { type: "say"; text: string }
  | { type: "form"; form: string; description?: string }
  | { type: "clarify"; questions: { question: string; options: string[] }[]; original: string }
  | { type: "done"; reply: string; interrupted: boolean; route?: string; sources?: { id?: string; title?: string; url?: string; path?: string; source_type?: string; excerpt?: string }[] }
  | { type: "error"; detail: string };
export type ChatStream = { done: Promise<void>; cancel: () => void; id: string };
let conversationSession: string | null = null;

const newRequestId = () => {
  try { if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID().replace(/-/g, ""); } catch { /* fall through */ }
  return Array.from({ length: 24 }, () => Math.floor(Math.random() * 36).toString(36)).join("");
};

/**
 * One chat turn, streamed: onEvent gets the words as ZÆNIA writes them.
 * cancel() stops her at once (the server stops generating too).
 */
export function streamChat(message: string, onEvent: (event: StreamEvent) => void, photo?: { images?: string[]; photoHistory?: { role: "user" | "assistant"; content: string }[]; files?: { name: string; data: string }[] }): ChatStream {
  const id = newRequestId();
  if (conversationSession === null) conversationSession = newRequestId();
  const body = { message, requestId: id, conversationId: conversationSession, ...photo };
  let cancelled = false;
  const sendCancel = () => { void api("POST", "/api/chat/cancel", { requestId: id }).catch(() => undefined); };

  if (IN_TAURI) {
    // Channel messages can arrive just after the command returns, so the turn
    // ends with the "done" (or "error") event, or shortly after the command.
    let finished!: () => void;
    const terminal = new Promise<void>(resolve => { finished = resolve; });
    const channel = new Channel<StreamEvent>();
    channel.onmessage = event => {
      onEvent(event);
      if (event.type === "done" || event.type === "error") finished();
    };
    const done = invoke<void>("zaenia_stream", { path: "/api/chat/stream", body, onEvent: channel }).then(
      () => Promise.race([terminal, new Promise<void>(resolve => window.setTimeout(resolve, 2000))]),
      error => { throw fromTauri(error); });
    return { id, done, cancel: () => { if (!cancelled) { cancelled = true; sendCancel(); } } };
  }

  if (WEB_APP) {
    const controller = new AbortController();
    const done = (async () => {
      const token = requireToken();
      let reply: Response;
      try {
        reply = await fetch("/api/chat/stream", {
          method: "POST", cache: "no-store", credentials: "same-origin", referrerPolicy: "no-referrer", signal: controller.signal,
          headers: { Accept: "application/x-ndjson", "Content-Type": "application/json", [TOKEN_HEADER]: token, "X-ZAENIA-APP": "1" },
          body: JSON.stringify(body),
        });
      } catch {
        if (cancelled) return;
        throw new BridgeError("Can't reach your PC. Check that it's on and that this phone is connected to it.", "offline");
      }
      if (reply.status === 401) throw new BridgeError("Sign in again with your voice or access token.", "auth");
      if (!reply.ok || !reply.body) {
        let detail = "";
        try { detail = detailText(await reply.json()); } catch { /* not JSON */ }
        throw new BridgeError(detail || `ZÆNIA server error ${reply.status}.`, failureFor(reply.status));
      }
      const reader = reply.body.getReader();
      const decoder = new TextDecoder();
      let buffered = "";
      try {
        for (;;) {
          const { value, done: finished } = await reader.read();
          if (finished) break;
          buffered += decoder.decode(value, { stream: true });
          let end: number;
          while ((end = buffered.indexOf("\n")) >= 0) {
            const line = buffered.slice(0, end).trim();
            buffered = buffered.slice(end + 1);
            if (!line) continue;
            try { onEvent(JSON.parse(line) as StreamEvent); } catch { /* ignore a bad line */ }
          }
        }
      } catch {
        if (!cancelled) throw new BridgeError("The reply stopped coming in. Check the connection to your PC.", "offline");
      }
    })();
    return {
      id, done,
      cancel: () => {
        if (cancelled) return;
        cancelled = true;
        sendCancel();
        window.setTimeout(() => controller.abort(), 400);
      },
    };
  }

  return { id, done: Promise.reject(new BridgeError("Chat needs the desktop app or the phone app.", "offline")), cancel: () => undefined };
}

/** True when this app or server is too old for streaming (fall back to askZaenia). */
export const streamUnsupported = (error: unknown) => {
  const text = errorText(error);
  return /zaenia_stream|not found|command .* not|unknown command/i.test(text) || (error instanceof BridgeError && error.kind === "missing");
};
