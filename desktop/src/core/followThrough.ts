import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "./bridge";

export type AssistantNotice = {
  id: string; title: string; message: string; dueAt: string; snoozedUntil: string | null;
  canInterrupt: boolean; canSpeak: boolean;
};
type Inbox = { notifications: AssistantNotice[]; unreadCount: number; workerRunning: boolean };
const marker = (item: AssistantNotice) => `${item.id}:${item.snoozedUntil ?? "initial"}`;
const STORAGE = "zaenia.assistant.presented";
export function parseInbox(value: unknown): Inbox {
  if (!value || typeof value !== "object") throw new Error("The Assistant inbox could not be read.");
  const data = value as Record<string, unknown>;
  if (!Array.isArray(data.notifications) || typeof data.unreadCount !== "number" || !Number.isInteger(data.unreadCount) || data.unreadCount < 0 || typeof data.workerRunning !== "boolean") throw new Error("The Assistant inbox could not be read.");
  const notifications = data.notifications.map((raw: unknown) => {
    if (!raw || typeof raw !== "object") throw new Error("A notification could not be read.");
    const item = raw as Record<string, unknown>;
    if (typeof item.id !== "string" || !/^ft-[a-f0-9]{32}$/.test(item.id) || typeof item.title !== "string" || item.title.length > 500 ||
      typeof item.message !== "string" || item.message.length > 2000 || typeof item.dueAt !== "string" || !Number.isFinite(Date.parse(item.dueAt)) ||
      !(item.snoozedUntil === null || typeof item.snoozedUntil === "string" && Number.isFinite(Date.parse(item.snoozedUntil))) ||
      typeof item.canInterrupt !== "boolean" || typeof item.canSpeak !== "boolean") throw new Error("A notification could not be read.");
    return item as unknown as AssistantNotice;
  });
  return { notifications, unreadCount: data.unreadCount, workerRunning: data.workerRunning };
}

function presented(): Set<string> {
  try {
    const values: unknown = JSON.parse(localStorage.getItem(STORAGE) ?? "[]");
    if (Array.isArray(values)) return new Set(values.filter((value): value is string => typeof value === "string" && value.length < 120).slice(-500));
  } catch { /* A blocked or empty local store does not block the inbox. */ }
  return new Set();
}

export function useAssistantInbox() {
  const [notice, setNotice] = useState<AssistantNotice | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const seen = useRef<Set<string> | null>(null);
  if (seen.current === null) seen.current = presented();
  const loading = useRef(false);
  const alive = useRef(true);
  const refresh = useCallback(async () => {
    if (!LIVE_API || loading.current || document.visibilityState === "hidden") return;
    loading.current = true;
    try {
      const inbox = parseInbox(await api("GET", "/api/assistant/notifications"));
      if (!alive.current) return;
      setUnreadCount(inbox.unreadCount); setError(null);
      if (document.hidden) { setNotice(null); return; }
      setNotice(previous => previous && inbox.notifications.some(item => marker(item) === marker(previous) && item.canInterrupt) ? previous : null);
      const next = inbox.notifications.find(item => item.canInterrupt && !seen.current!.has(marker(item)));
      if (next) {
        seen.current!.add(marker(next));
        try { localStorage.setItem(STORAGE, JSON.stringify([...seen.current!].slice(-500))); } catch { /* optional */ }
        setNotice(next);
      }
    } catch (failure) { if (alive.current) { setError(errorText(failure)); setNotice(null); } }
    finally { loading.current = false; }
  }, []);
  useEffect(() => {
    alive.current = true;
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", visible);
    return () => { alive.current = false; window.clearInterval(timer); document.removeEventListener("visibilitychange", visible); };
  }, [refresh]);
  const acknowledge = async (item: AssistantNotice) => {
    try { await api("POST", `/api/assistant/notifications/${encodeURIComponent(item.id)}/ack`); setNotice(null); await refresh(); }
    catch (failure) { setError(errorText(failure)); }
  };
  const snooze = async (item: AssistantNotice) => {
    try { await api("POST", `/api/assistant/notifications/${encodeURIComponent(item.id)}/snooze`, { minutes: 15 }); setNotice(null); await refresh(); }
    catch (failure) { setError(errorText(failure)); }
  };
  return { notice, unreadCount, error, refresh, acknowledge, snooze };
}
