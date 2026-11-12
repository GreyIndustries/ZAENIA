import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, LIVE_API } from "../../core/bridge";
import { skipWhileAway } from "../../core/appBackground";
import "./NotificationCenter.css";

/**
 * The bell in the top bar (Grey, 2026-11-01) and its notification center, in three parts:
 * - Needs you: build requests to check or approve, file changes waiting, new suggestions, overdue tasks.
 * - New: ZAE's inbox (reminders, important emails, research done, builds ready), with Read and Snooze.
 * - Done today: what ZAE did for you (her action receipts), tasks you completed and builds that went live.
 * Everything comes from the existing local routes; nothing here can approve or change anything by itself.
 */
type Notice = { id: string; title: string; message: string; dueAt: string; readAt?: string | null; source?: string; snoozedUntil?: string | null };
type Build = { id: string; title: string; status: string; updatedAt: string };
type Task = { id: string; title: string; status: string; deadline: string | null; updatedAt: string; history?: { at: string; status: string }[] };
type Receipt = { id: string; kind: string; label: string; status: string; updatedAt?: string; createdAt?: string };
type Item = { key: string; title: string; detail?: string; at?: string; open?: [string, { page: string; tab: string }?] };

const today = () => new Date().toDateString();
const isToday = (iso?: string | null) => !!iso && new Date(iso).toDateString() === today();
const when = (iso?: string) => iso ? new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
const SOURCE: Record<string, string> = { reminder: "Reminder", email: "Email", web_agent: "Research", build: "Build request", build_ideas: "Ideas",
  training: "Training", phone: "Phone", calendar: "Calendar", task: "Task" };

export function NotificationCenter({ pendingFiles, onOpen }: { pendingFiles: number; onOpen: (section: string, sub?: { page: string; tab: string }) => void }) {
  const [open, setOpen] = useState(false);
  const [fresh, setFresh] = useState<Notice[]>([]);
  const [needs, setNeeds] = useState<Item[]>([]);
  const [done, setDone] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement | null>(null);
  const panel = useRef<HTMLDivElement | null>(null);
  // The panel is drawn on the page itself (a portal), placed under the bell, so module windows never cover it.
  const [place, setPlace] = useState<{ top: number; right: number }>({ top: 80, right: 16 });

  const load = useCallback(async () => {
    if (!LIVE_API) return;
    const get = <T,>(path: string) => api<T>("GET", path).catch(() => null);
    const [inbox, builds, ideas, tasks, actions] = await Promise.all([
      get<{ notifications: Notice[] }>("/api/assistant/notifications?includeRead=true"),
      get<{ requests: Build[] }>("/api/build"),
      get<{ suggestions: { status: string }[] }>("/api/suggestions"),
      get<{ tasks: Task[] }>("/api/tasks"),
      get<{ actions: Receipt[] }>("/api/platform/actions"),
    ]);
    const notices = inbox?.notifications ?? [];
    setFresh(notices.filter(n => !n.readAt && !(n.snoozedUntil && Date.parse(n.snoozedUntil) > Date.now())));  // "Later" hides it until then
    const wanted: Item[] = [];
    for (const b of builds?.requests ?? []) {
      if (b.status === "draft") wanted.push({ key: `b${b.id}`, title: `Check the brief: ${b.title}`, detail: "Build request · tap Start when it looks right", at: b.updatedAt, open: ["suggestions", { page: "codedoctor", tab: "build" }] });
      if (b.status === "ready") wanted.push({ key: `b${b.id}`, title: `Approve or reject: ${b.title}`, detail: "Build request · tested and ready, approve at the PC", at: b.updatedAt, open: ["suggestions", { page: "codedoctor", tab: "build" }] });
    }
    if (pendingFiles > 0) wanted.push({ key: "files", title: `${pendingFiles} file change${pendingFiles > 1 ? "s" : ""} waiting for approval`, detail: "Files", open: ["files"] });
    const newIdeas = (ideas?.suggestions ?? []).filter(s => s.status === "new").length;
    if (newIdeas) wanted.push({ key: "ideas", title: `${newIdeas} new suggestion${newIdeas > 1 ? "s" : ""} to look at`, detail: "Suggestions", open: ["suggestions", { page: "codedoctor", tab: "suggestions" }] });
    const now = Date.now();
    for (const t of tasks?.tasks ?? []) {
      if (t.status !== "Completed" && t.deadline && Date.parse(t.deadline) < now) wanted.push({ key: `t${t.id}`, title: `Overdue: ${t.title}`, detail: `Was due ${new Date(t.deadline).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}`, open: ["tasks"] });
    }
    setNeeds(wanted);
    const finished: Item[] = [];
    for (const r of actions?.actions ?? []) {
      const at = r.updatedAt ?? r.createdAt;
      if (r.status === "completed" && isToday(at)) finished.push({ key: `r${r.id}`, title: r.label, detail: "ZAE did this", at });
    }
    for (const t of tasks?.tasks ?? []) {
      const doneAt = [...(t.history ?? [])].reverse().find(h => h.status === "Completed")?.at ?? (t.status === "Completed" ? t.updatedAt : undefined);
      if (t.status === "Completed" && isToday(doneAt)) finished.push({ key: `t${t.id}`, title: t.title, detail: "Task completed", at: doneAt, open: ["tasks"] });
    }
    for (const b of builds?.requests ?? []) if (b.status === "approved" && isToday(b.updatedAt)) finished.push({ key: `a${b.id}`, title: b.title, detail: "Build request went live", at: b.updatedAt, open: ["suggestions", { page: "codedoctor", tab: "build" }] });
    for (const n of notices) if (n.readAt && isToday(n.readAt)) finished.push({ key: `n${n.id}`, title: n.title, detail: `${SOURCE[n.source ?? ""] ?? "Notice"} · read`, at: n.readAt ?? undefined });
    setDone(finished.sort((a, b) => (b.at ?? "").localeCompare(a.at ?? "")).slice(0, 30));
  }, [pendingFiles]);

  useEffect(() => {
    if (!LIVE_API) return;
    void load();
    const away = { n: 0 };
    const timer = window.setInterval(() => { if (open || !skipWhileAway(away, 4)) void load(); }, open ? 15_000 : 30_000);
    const changed = () => void load();
    window.addEventListener("zae:records-changed", changed);
    return () => { window.clearInterval(timer); window.removeEventListener("zae:records-changed", changed); };
  }, [load, open]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => { const target = event.target as Node; if (!box.current?.contains(target) && !panel.current?.contains(target)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);

  const act = async (work: () => Promise<unknown>) => { setBusy(true); try { await work(); await load(); } catch { /* the list reloads either way */ } finally { setBusy(false); } };
  const read = (n: Notice) => act(() => api("POST", `/api/assistant/notifications/${encodeURIComponent(n.id)}/ack`));
  const snooze = (n: Notice) => act(() => api("POST", `/api/assistant/notifications/${encodeURIComponent(n.id)}/snooze`, { minutes: 60 }));
  const readAll = () => act(() => Promise.all(fresh.map(n => api("POST", `/api/assistant/notifications/${encodeURIComponent(n.id)}/ack`))));
  const go = (item: Item) => { if (item.open) { onOpen(item.open[0], item.open[1]); setOpen(false); } };
  const count = fresh.length + needs.length;

  if (!LIVE_API) return null;
  const row = (item: Item, tone: string) => <li key={item.key}>
    <button type="button" className={`nc-item nc-item--${tone}`} disabled={!item.open} onClick={() => go(item)}>
      <span className="nc-item__title">{item.title}</span>
      <small>{item.detail}{item.at ? ` · ${when(item.at)}` : ""}</small>
    </button></li>;
  return <div className="nc" ref={box}>
    <button type="button" className={`nc-bell${count ? " nc-bell--on" : ""}`} aria-label={count ? `Notifications: ${count} new` : "Notifications"} aria-expanded={open}
      aria-haspopup="dialog" title="Notifications" onClick={event => { const rect = event.currentTarget.getBoundingClientRect(); setPlace({ top: rect.bottom + 12, right: Math.max(8, window.innerWidth - rect.right - 8) }); setOpen(v => !v); if (!open) void load(); }}>
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
      {count > 0 && <span className="nc-bell__count">{count > 99 ? "99+" : count}</span>}
    </button>
    {open && createPortal(<div className="nc-panel" ref={panel} style={{ top: place.top, right: place.right }} role="dialog" aria-label="Notification center">
      <header className="nc-head"><strong>Notifications</strong>{fresh.length > 0 && <button type="button" disabled={busy} onClick={() => void readAll()}>Mark all read</button>}</header>
      <section><h4>Needs you <span>{needs.length}</span></h4>
        {needs.length ? <ul>{needs.map(item => row(item, "need"))}</ul> : <p className="nc-empty">Nothing is waiting on you.</p>}</section>
      <section><h4>New <span>{fresh.length}</span></h4>
        {fresh.length ? <ul>{fresh.map(n => <li key={n.id} className="nc-notice">
          <div><span className="nc-item__title">{n.title}</span><small>{SOURCE[n.source ?? ""] ?? "Notice"} · {when(n.dueAt)}</small>{n.message && <p>{n.message}</p>}</div>
          <div className="nc-notice__actions"><button type="button" disabled={busy} onClick={() => void read(n)}>Read</button><button type="button" disabled={busy} onClick={() => void snooze(n)}>Later</button></div>
        </li>)}</ul> : <p className="nc-empty">You're all caught up.</p>}</section>
      <section><h4>Done today <span>{done.length}</span></h4>
        {done.length ? <ul>{done.map(item => row(item, "done"))}</ul> : <p className="nc-empty">Nothing finished yet today.</p>}</section>
    </div>, document.body)}
  </div>;
}
