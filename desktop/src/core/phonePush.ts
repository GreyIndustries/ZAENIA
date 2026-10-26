import { api } from "./bridge";

/** Phone notifications (Web Push): works in the phone app opened from the Home Screen (iOS 16.4+) or a desktop browser. */
export function pushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && window.isSecureContext;
}

export function pushHint(): string {
  if (typeof window === "undefined") return "";
  const ios = /iPhone|iPad/.test(navigator.userAgent);
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
  if (ios && !standalone) return "On iPhone, first add ZAE to your Home Screen (Share › Add to Home Screen), open her from there, then turn notifications on.";
  if (!pushSupported()) return "This window can't receive notifications. Open ZAE on your phone (from the Home Screen icon) to turn them on.";
  return "";
}

function keyBytes(base64url: string): Uint8Array {
  const padded = (base64url + "===".slice((base64url.length + 3) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  return Uint8Array.from(raw, char => char.charCodeAt(0));
}

export async function pushState(): Promise<"on" | "off" | "blocked" | "unsupported"> {
  if (!pushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "blocked";
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  return subscription ? "on" : "off";
}

/** Must run from a tap (iOS asks for permission only then). */
export async function enablePush(): Promise<void> {
  if (!pushSupported()) throw new Error(pushHint() || "Notifications aren't supported here.");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Notifications were not allowed. Turn them on for ZAE in Settings › Notifications.");
  const registration = await navigator.serviceWorker.register("sw.js");
  await navigator.serviceWorker.ready;
  const { key } = await api<{ key: string }>("GET", "/api/push/key");
  const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) as BufferSource });
  await api("POST", "/api/push/subscribe", { subscription: subscription.toJSON(), label: /iPhone/.test(navigator.userAgent) ? "iPhone" : "browser" });
}

export async function disablePush(): Promise<void> {
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    await api("POST", "/api/push/unsubscribe", { endpoint: subscription.endpoint });
    await subscription.unsubscribe();
  }
}
