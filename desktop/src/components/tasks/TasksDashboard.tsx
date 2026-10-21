import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { PRIORITIES, STATUSES, changeStatus, compareTasks, migrateDrafts, parseTasks } from "../../core/taskModel";
import type { Priority, Status, TaskRecord } from "../../core/taskModel";
import { api, errorText } from "../../core/bridge";
import "./TasksDashboard.css";

const storageKey = "zaenia-ui-v4-tasks";
const movedKey = "zaenia-ui-v4-tasks-moved";
function readSaved() {
  try {
    const current = localStorage.getItem(storageKey);
    const legacy = current === null ? localStorage.getItem("zaenia-ui-v3-tasks") : null;
    return { tasks: current !== null ? parseTasks(JSON.parse(current)) : legacy !== null ?
      migrateDrafts(JSON.parse(legacy), new Date().toISOString()) : [], error: "" };
  } catch (error) {
    return { tasks: [] as TaskRecord[], error: `${error instanceof Error ? error.message : "Storage is unavailable."} Changes are disabled to protect saved data.` };
  }
}
const dateLabel = (value: string) => new Date(value).toLocaleString([], { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
function inputDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0, 16);
}
type Patch = Partial<Pick<TaskRecord, "priority" | "deadline" | "archived" | "status">>;
type ServerTasks = { tasks: TaskRecord[] };

/**
 * Tasks. With the ZÆNIA server (desktop app or phone app) the list lives on
 * the PC and is the same everywhere; otherwise it stays on this device.
 */
export function TasksDashboard({ remote = false, refreshVersion = 0 }: { remote?: boolean; refreshVersion?: number }) {
  const [saved] = useState(readSaved);
  const [tasks, setTasks] = useState<TaskRecord[]>(remote ? [] : saved.tasks);
  const [storageError, setStorageError] = useState(remote ? "" : saved.error);
  const [loaded, setLoaded] = useState(!remote);
  const [busy, setBusy] = useState(false);
  const [localLeft, setLocalLeft] = useState<TaskRecord[]>(remote && !saved.error ? saved.tasks : []);
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState<Priority>("Normal");
  const [deadline, setDeadline] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Status | "All">("All");
  const [showArchived, setShowArchived] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [now, setNow] = useState(Date.now);
  const locked = !remote && !!saved.error;

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(timer);
  }, []);
  // Device-only mode keeps the list in this browser's storage.
  useEffect(() => {
    if (remote || saved.error) return;
    try { localStorage.setItem(storageKey, JSON.stringify(tasks)); setStorageError(""); }
    catch { setStorageError("Changes are visible, but could not be saved on this device. Keep this screen open until storage is available."); }
  }, [tasks, saved.error, remote]);

  const call = useCallback(async (task: () => Promise<ServerTasks>) => {
    setBusy(true);
    try { const reply = await task(); setTasks(parseTasks(reply.tasks)); setStorageError(""); setLoaded(true); return true; }
    catch (failure) { setStorageError(errorText(failure)); return false; }
    finally { setBusy(false); }
  }, []);
  // Shared mode: load from the PC, and again whenever the app comes back.
  useEffect(() => {
    if (!remote) return;
    const load = () => { void call(() => api<ServerTasks>("GET", "/api/tasks")); };
    load();
    const onVisible = () => { if (!document.hidden) load(); };
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(load, 60_000);
    return () => { document.removeEventListener("visibilitychange", onVisible); window.clearInterval(timer); };
  }, [remote, call, refreshVersion]);
  useEffect(() => {
    if (!confirmDelete) return;
    const timer = window.setTimeout(() => setConfirmDelete(false), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmDelete]);

  const active = tasks.filter(task => !task.archived);
  const visible = useMemo(() => tasks.filter(task => task.archived === showArchived &&
    (filter === "All" || task.status === filter) && task.title.toLowerCase().includes(search.toLowerCase()))
    .sort(compareTasks), [tasks, showArchived, filter, search]);
  const selected = tasks.find(task => task.id === selectedId);
  const overdue = (task: TaskRecord) => task.status !== "Completed" && task.deadline !== null && Date.parse(task.deadline) < now;

  async function addTask(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || locked || busy) return;
    const due = deadline ? new Date(deadline).toISOString() : null;
    if (remote) {
      let createdId: string | null = null;
      const ok = await call(async () => { const reply = await api<ServerTasks & { task: TaskRecord }>("POST", "/api/tasks", { title: title.trim(), priority, deadline: due }); createdId = reply.task.id; return reply; });
      if (ok) { setTitle(""); setDeadline(""); setSelectedId(createdId); }
      return;
    }
    const at = new Date().toISOString();
    const task: TaskRecord = { id: crypto.randomUUID(), title: title.trim(), priority, deadline: due, status: "Pending",
      createdAt: at, updatedAt: at, archived: false, history: [{ at, status: "Pending", note: "Task created" }] };
    setTasks(previous => [...previous, task]); setTitle(""); setDeadline(""); setSelectedId(task.id);
  }
  function updateTask(id: string, patch: Patch, note: string) {
    if (remote) { void call(() => api<ServerTasks>("PATCH", `/api/tasks/${encodeURIComponent(id)}`, patch)); return; }
    const at = new Date().toISOString();
    setTasks(previous => previous.map(task => {
      if (task.id !== id) return task;
      const { status, ...rest } = patch;
      const next = status ? changeStatus(task, status, at) : task;
      return Object.keys(rest).length ? { ...next, ...rest, updatedAt: at, history: [...next.history, { at, status: next.status, note }] } : next;
    }));
  }
  function deleteTask(id: string) {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    setConfirmDelete(false); setSelectedId(null);
    if (remote) { void call(() => api<ServerTasks>("DELETE", `/api/tasks/${encodeURIComponent(id)}`)); return; }
    setTasks(previous => previous.filter(task => task.id !== id));
  }
  async function moveLocalTasks() {
    const ok = await call(() => api<ServerTasks>("POST", "/api/tasks/import", { tasks: localLeft }));
    if (!ok) return;
    try { localStorage.setItem(movedKey, JSON.stringify(localLeft)); localStorage.removeItem(storageKey); localStorage.removeItem("zaenia-ui-v3-tasks"); } catch { /* keep going */ }
    setLocalLeft([]);
  }

  return <div className="section-content task-dashboard">
    <div className="section-content__tag">YOUR TASKS <span>{remote ? "SAVED ON YOUR PC · SAME ON PHONE AND DESKTOP" : "SAVED ON THIS DEVICE"}</span></div>
    {storageError && <p className="task-warning" role="alert">{storageError}</p>}
    {remote && localLeft.length > 0 && <div className="task-move">
      <span>{localLeft.length} task{localLeft.length > 1 ? "s are" : " is"} saved only on this device.</span>
      <button type="button" onClick={() => void moveLocalTasks()} disabled={busy}>Move to ZÆNIA</button>
    </div>}
    <div className="task-stats" aria-label="Task summary">
      {STATUSES.map(status => <button type="button" key={status} aria-pressed={filter === status}
        onClick={() => { setFilter(filter === status ? "All" : status); setShowArchived(false); }}>
        <span>{status}</span><strong>{active.filter(task => task.status === status).length}</strong></button>)}
      <div><span>Overdue</span><strong className="task-overdue">{active.filter(overdue).length}</strong></div>
    </div>
    <form className="task-create" onSubmit={event => void addTask(event)}>
      <label>Task<input placeholder="What needs doing?" value={title} maxLength={180} required disabled={locked || busy} onChange={event => setTitle(event.target.value)}/></label>
      <label>Priority<select value={priority} disabled={locked} onChange={event => setPriority(event.target.value as Priority)}>{PRIORITIES.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Deadline <small>(optional)</small><input type="datetime-local" value={deadline} disabled={locked} onChange={event => setDeadline(event.target.value)}/></label>
      <button type="submit" disabled={!title.trim() || locked || busy}>+ Add task</button>
    </form>
    <div className="task-toolbar">
      <input aria-label="Search tasks" placeholder="Search tasks…" value={search} onChange={event => setSearch(event.target.value)}/>
      <select aria-label="Filter task status" value={filter} onChange={event => setFilter(event.target.value as Status | "All")}><option value="All">All statuses</option>{STATUSES.map(value => <option key={value}>{value}</option>)}</select>
      <button type="button" aria-pressed={showArchived} onClick={() => setShowArchived(value => !value)}>{showArchived ? "View active" : "View archive"}</button>
    </div>
    <p className="task-sort-note">Sorted by priority, then deadline. Completed tasks follow active tasks.</p>
    <div className="task-table" aria-live="polite" aria-busy={busy}>
      {!loaded ? <div className="empty-state"><strong>Loading your tasks…</strong><span>From ZÆNIA on your PC.</span></div>
        : visible.length === 0 ? <div className="empty-state"><strong>{tasks.length ? "No matching tasks" : "A clear desk. A fresh start."}</strong><span>{tasks.length ? "Adjust your search or filters." : "Add your first task above."}</span></div>
        : visible.map(task => <article className={`task-card ${selectedId === task.id ? "task-card--selected" : ""}`} key={task.id}>
        <button className="task-title" type="button" onClick={() => { setSelectedId(selectedId === task.id ? null : task.id); setConfirmDelete(false); }} aria-expanded={selectedId === task.id}>
          <strong className={task.status === "Completed" ? "task-completed" : ""}>{task.title}</strong>
          <span className={overdue(task) ? "task-overdue" : ""}>{task.deadline ? `${overdue(task) ? "Overdue · " : "Due "}${dateLabel(task.deadline)}` : "No deadline"}</span>
        </button>
        <span className={`task-priority task-priority--${task.priority.toLowerCase()}`}>{task.priority}</span>
        <select aria-label={`Status for ${task.title}`} value={task.status} disabled={locked || task.archived || busy}
          onChange={event => updateTask(task.id, { status: event.target.value as Status }, "Status changed")}>
          {STATUSES.map(value => <option key={value}>{value}</option>)}
        </select>
        <button type="button" disabled={locked || busy} onClick={() => updateTask(task.id, { archived: !task.archived }, task.archived ? "Task restored" : "Task archived")}>{task.archived ? "Restore" : "Archive"}</button>
      </article>)}
    </div>
    {selected && <section className="task-details" aria-label={`Details for ${selected.title}`}>
      <div className="task-details-heading"><strong>{selected.title}</strong><button type="button" onClick={() => setSelectedId(null)}>Close details</button></div>
      <div className="task-edit">
        <label>Priority<select value={selected.priority} disabled={locked || selected.archived || busy} onChange={event => updateTask(selected.id, { priority: event.target.value as Priority }, `Priority changed to ${event.target.value}`)}>{PRIORITIES.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Deadline<input type="datetime-local" value={inputDate(selected.deadline)} disabled={locked || selected.archived || busy}
          onChange={event => { const value = event.target.value; if (!value || Number.isFinite(new Date(value).getTime())) updateTask(selected.id, { deadline: value ? new Date(value).toISOString() : null }, value ? "Deadline updated" : "Deadline cleared"); }}/></label>
      </div>
      <h3>History</h3><ol className="task-history">{[...selected.history].reverse().map((event, index) => <li key={`${event.at}-${index}`}><span>{event.note}</span><time dateTime={event.at}>{dateLabel(event.at)}</time></li>)}</ol>
      <div className="task-delete"><button type="button" className={confirmDelete ? "task-delete--confirm" : ""} disabled={locked || busy} onClick={() => deleteTask(selected.id)}>
        {confirmDelete ? "Tap again to delete for good" : "Delete task"}</button></div>
    </section>}
  </div>;
}
