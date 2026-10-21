export const PRIORITIES = ["Critical", "High", "Normal", "Low"] as const;
export const STATUSES = ["Pending", "In Progress", "Completed"] as const;
export type Priority = typeof PRIORITIES[number];
export type Status = typeof STATUSES[number];
export type TaskRecord = {
  id: string; title: string; priority: Priority; status: Status;
  deadline: string | null; createdAt: string; updatedAt: string;
  history: { at: string; status: Status; note: string }[];
  archived: boolean;
};
const validTime = (value: unknown): value is string => typeof value === "string" && Number.isFinite(Date.parse(value));
export function migrateDrafts(raw: unknown, now: string): TaskRecord[] {
  if (!Array.isArray(raw)) throw new Error("Saved task drafts could not be read.");
  return raw.map(value => {
    if (!value || typeof value !== "object") throw new Error("Invalid saved task.");
    const task = value as Record<string, unknown>;
    if (typeof task.title !== "string" || typeof task.done !== "boolean" ||
      typeof task.id !== "number" || !Number.isFinite(task.id) || !PRIORITIES.includes(task.priority as Priority))
      throw new Error("Invalid saved task draft.");
    const status: Status = task.done ? "Completed" : "Pending";
    return { id: `legacy-${task.id}`, title: task.title, priority: task.priority as Priority,
      status, deadline: null, createdAt: now, updatedAt: now, archived: false,
      history: [{ at: now, status, note: "Imported from the previous task board; original timestamps unavailable." }] };
  });
}
export function parseTasks(raw: unknown): TaskRecord[] {
  if (!Array.isArray(raw)) throw new Error("Saved tasks could not be read.");
  const ids = new Set<string>();
  return raw.map(value => {
    if (!value || typeof value !== "object") throw new Error("Invalid saved task.");
    const task = value as TaskRecord;
    if (typeof task.id !== "string" || ids.has(task.id) || typeof task.title !== "string" ||
      !PRIORITIES.includes(task.priority) || !STATUSES.includes(task.status) ||
      !(task.deadline === null || validTime(task.deadline)) || !validTime(task.createdAt) ||
      !validTime(task.updatedAt) || typeof task.archived !== "boolean" || !Array.isArray(task.history) ||
      !task.history.every(event => event && validTime(event.at) && STATUSES.includes(event.status) && typeof event.note === "string"))
      throw new Error("Saved task data is invalid. It has been preserved without changes.");
    ids.add(task.id);
    return task;
  });
}
export function compareTasks(a: TaskRecord, b: TaskRecord) {
  return Number(a.status === "Completed") - Number(b.status === "Completed") ||
    PRIORITIES.indexOf(a.priority) - PRIORITIES.indexOf(b.priority) ||
    (a.deadline ? Date.parse(a.deadline) : Infinity) - (b.deadline ? Date.parse(b.deadline) : Infinity) ||
    a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id);
}
export function changeStatus(task: TaskRecord, status: Status, at: string): TaskRecord {
  if (task.status === status) return task;
  return { ...task, status, updatedAt: at, history: [...task.history, { at, status, note: `${task.status} → ${status}` }] };
}
