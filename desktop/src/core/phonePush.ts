import { api, IN_TAURI } from "./bridge";

export const PUSH_CATEGORIES = ["reminder", "calendar", "task", "training", "email", "research", "other"] as const;
export type PushCategory = typeof PUSH_CATEGORIES[number];
export type PushPreferences = { categories: PushCategory[]; preview: boolean };
export type PushDevice = { id: string; label: string; preferences: PushPreferences; added: string; lastAcceptedAt: string | null; lastResult: string | null; deliveryState: string | null; retryRecords: number };
export type PushStatus = { devices: PushDevice[]; transportAvailable: boolean; workerRunning: boolean; workerError: string | null };
export type PushState = "on" | "off" | "unregistered" | "blocked" | "unsupported";
const SCOPE = "/app/";

export function pushSupported(): boolean {
  return typeof window !== "undefined" && !IN_TAURI && window.isSecureContext &&
    "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function pushHint(): string {
  if (typeof window === "undefined") return "";
  if (IN_TAURI) return "Open ZAE's HTTPS address on your phone to connect it. This desktop app can show connected browsers below.";
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
  if (ios && !standalone) return "On iPhone or iPad: Share › Add to Home Screen, open ZAE from that icon, sign in, then turn on notifications here (iOS/iPadOS 16.4+).";
  if (!window.isSecureContext) return "Use ZAE's HTTPS phone address. An HTTP address on your local network cannot receive browser push.";
  if (!pushSupported()) return "This browser doesn't support Web Push. Try a supported phone browser or ZAE's Home Screen app.";
  return "";
}

function keyBytes(value: string): Uint8Array {
  const padded = (value + "=".repeat((4 - value.length % 4) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(padded), char => char.charCodeAt(0));
}

export async function localPush(): Promise<{ state: PushState; id: string | null }> {
  if (!pushSupported()) return { state: "unsupported", id: null };
  if (Notification.permission === "denied") return { state: "blocked", id: null };
  const registration = await navigator.serviceWorker.getRegistration(SCOPE);
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return { state: "off", id: null };
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(subscription.endpoint));
  const id = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("").slice(0, 32);
  return { state: "on", id };
}

export async function pushState(): Promise<PushState> {
  const local = await localPush();
  if (local.state !== "on") return local.state;
  const status = await api<PushStatus>("GET", "/api/push/status");
  return status.devices.some(device => device.id === local.id) ? "on" : "unregistered";
}

/** The permission call must stay before the first await: iOS requires a tap. */
export async function enablePush(): Promise<void> {
  if (!pushSupported()) throw new Error(pushHint());
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Notifications weren't allowed. Change ZAE's permission in this phone's notification settings, then try again.");
  const { key } = await api<{ key: string }>("GET", "/api/push/key");
  const registration = await navigator.serviceWorker.register(SCOPE + "sw.js", { scope: SCOPE, updateViaCache: "none" });
  let subscription = await registration.pushManager.getSubscription();
  const wanted = keyBytes(key);
  if (subscription?.options.applicationServerKey) {
    const current = new Uint8Array(subscription.options.applicationServerKey);
    if (current.length !== wanted.length || current.some((byte, index) => byte !== wanted[index])) {
      await api("POST", "/api/push/unsubscribe", { endpoint: subscription.endpoint });
      await subscription.unsubscribe();
      subscription = null;
    }
  }
  // Wait for this registration to activate, with a bounded timeout.
  if (!registration.active) await new Promise<void>((resolve, reject) => {
    const worker = registration.installing ?? registration.waiting;
    const cleanup = () => { window.clearTimeout(timer); worker?.removeEventListener("statechange", check); };
    const check = () => { if (worker?.state === "activated" || registration.active) { cleanup(); resolve(); } };
    const timer = window.setTimeout(() => { cleanup(); reject(new Error("The notification worker didn't start. Reload ZAE and try again.")); }, 15_000);
    worker?.addEventListener("statechange", check); check();
  });
  subscription ??= await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: wanted as BufferSource });
  // Keep a browser subscription after a failed server save, so Reconnect can repair it.
  await api("POST", "/api/push/subscribe", {
    subscription: subscription.toJSON(), appOrigin: window.location.origin,
    label: /iPhone/.test(navigator.userAgent) ? "iPhone" : /Android/.test(navigator.userAgent) ? "Android phone" : /iPad/.test(navigator.userAgent) || navigator.maxTouchPoints > 1 && /Macintosh/.test(navigator.userAgent) ? "iPad" : "Browser",
  });
}

export async function disablePush(): Promise<void> {
  const registration = await navigator.serviceWorker.getRegistration(SCOPE);
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    await api("POST", "/api/push/unsubscribe", { endpoint: subscription.endpoint });
    if (!await subscription.unsubscribe()) throw new Error("ZAE stopped sending here, but the browser couldn't remove its subscription. Reload and try again.");
  }
}

export function deliveryMessage(result: string | null, state?: string | null): string {
  if (!result) return "No delivery attempted yet.";
  if (state === "failed") return "This alert wasn't delivered after a permanent error or repeated failures. Reconnect on your phone and send a test.";
  if (result === "accepted") return "Accepted by the push service. Phone display isn't confirmed.";
  if (result === "network") return "Push service couldn't be reached; eligible alerts retry automatically.";
  if (result === "unchanged") return "A test was recently attempted. Wait 30 seconds before testing again.";
  if (result === "http_404" || result === "http_410") return "This subscription expired. Reconnect notifications on that phone.";
  if (result === "http_401" || result === "http_403" || result === "key_unavailable" || result === "invalid_subscription") return "Registration or push credentials need attention. Reconnect on your phone and test again.";
  return "The push service hasn't accepted this alert. Check the connection and try a test.";
}
