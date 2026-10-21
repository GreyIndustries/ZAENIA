import { parseTasks, PRIORITIES } from "./taskModel";
import type { Priority } from "./taskModel";

export type AssistantProposal =
  | { kind: "task.create"; title: string; parameters: { title: string; priority: Priority; deadline: string | null } }
  | { kind: "calendar.create"; title: string; parameters: { title: string; date: string; time: string; recurrence: "none" | "daily" | "weekly" } }
  | { kind: "memory.remember"; title: string; parameters: { key: string; value: string; category: string } }
  | { kind: "memory.forget"; title: string; parameters: { key: string } }
  | PlatformProposal;
export type PlatformProposal =
  | { kind: "app.launch"; title: string; parameters: { id: string; name: string } }
  | { kind: "workspace.restore"; title: string; parameters: { id: string; name: string; revision: number } };
export type AssistantActionState = { status: "ready" | "pending" | "succeeded" | "dismissed" | "failed" | "uncertain" | "expired"; detail?: string };

const record = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && !Array.isArray(value);
const only = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).every(key => keys.includes(key));
const titleText = (value: unknown, limit: number): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= limit;
const cleanTitle = (value: string) => value.trim().replace(/\s+/g, " ");
const validDate = (value: unknown): value is string => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
  Number(value.slice(0, 4)) > 0 && Number.isFinite(Date.parse(`${value}T12:00:00Z`)) && new Date(`${value}T12:00:00Z`).toISOString().slice(0, 10) === value;
const validClock = (value: unknown): value is string => typeof value === "string" && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
const validInstant = (value: unknown): value is string => typeof value === "string" && value.length <= 40 &&
  /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
  validDate(value.slice(0, 10)) && Number.isFinite(Date.parse(value));

/** Only explicit, supported structured proposals become review cards. Prose is never executable. */
export function parseAssistantProposal(value: unknown): AssistantProposal | null {
  if (!record(value) || !only(value, ["kind", "title", "parameters"]) || !titleText(value.title, 240) || !record(value.parameters)) return null;
  const p = value.parameters;
  if (value.kind === "app.launch" || value.kind === "workspace.restore") {
    if (!only(p, value.kind === "app.launch" ? ["id", "name"] : ["id", "name", "revision"]) ||
      !titleText(p.id, 100) || !/^[A-Za-z0-9_-]+$/.test(p.id) || !titleText(p.name, 100)) return null;
    if (value.kind === "app.launch") return { kind: value.kind, title: cleanTitle(value.title), parameters: { id: p.id, name: p.name } };
    if (typeof p.revision !== "number" || !Number.isSafeInteger(p.revision) || p.revision < 1) return null;
    return { kind: value.kind, title: cleanTitle(value.title), parameters: { id: p.id, name: p.name, revision: p.revision } };
  }
  if (value.kind === "memory.remember") {
    if (!only(p, ["key", "value", "category"]) || !titleText(p.key, 120) || !titleText(p.value, 800) ||
      !["fact", "preference", "goal", "person", "commitment"].includes(String(p.category))) return null;
    return { kind: "memory.remember", title: cleanTitle(value.title), parameters: { key: cleanTitle(p.key), value: p.value.trim(), category: String(p.category) } };
  }
  if (value.kind === "memory.forget") {
    if (!only(p, ["key"]) || !titleText(p.key, 120)) return null;
    return { kind: "memory.forget", title: cleanTitle(value.title), parameters: { key: cleanTitle(p.key) } };
  }
  if (value.kind === "task.create") {
    if (!only(p, ["title", "priority", "deadline"]) || !titleText(p.title, 180) || !PRIORITIES.includes(p.priority as Priority) ||
      !(p.deadline === null || validInstant(p.deadline))) return null;
    return { kind: "task.create", title: cleanTitle(value.title), parameters: { title: cleanTitle(p.title), priority: p.priority as Priority, deadline: p.deadline } };
  }
  if (value.kind === "calendar.create") {
    if (!only(p, ["title", "date", "time", "recurrence"]) || !titleText(p.title, 200) || !validDate(p.date) || !validClock(p.time) ||
      !(p.recurrence === "none" || p.recurrence === "daily" || p.recurrence === "weekly")) return null;
    return { kind: "calendar.create", title: cleanTitle(value.title), parameters: { title: cleanTitle(p.title), date: p.date, time: p.time, recurrence: p.recurrence } };
  }
  return null;
}

export const taskDeadlineLabel = (value: string) => new Date(value).toLocaleString([], { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
export const calendarWhenLabel = (date: string, time: string) => `${new Date(`${date}T12:00:00Z`).toLocaleDateString([], { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" })} at ${time} Pacific time`;

function pacificParts(value: string) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "America/Los_Angeles", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(value));
  const get = (kind: string) => parts.find(part => part.type === kind)?.value;
  return { date: `${get("year")}-${get("month")}-${get("day")}`, time: `${get("hour")}:${get("minute")}` };
}

/** Recheck on Apply: a reviewed calendar proposal may have sat open for hours. */
export function assistantProposalExpired(proposal: AssistantProposal, now = new Date()): boolean {
  if (proposal.kind !== "calendar.create") return false;
  const current = pacificParts(now.toISOString());
  // Events start at the beginning of the proposed minute, so that minute is already due.
  return `${proposal.parameters.date}T${proposal.parameters.time}` <= `${current.date}T${current.time}`;
}

/** A successful HTTP response alone does not prove the requested entity was saved. */
export function confirmedAssistantAction(proposal: AssistantProposal, response: unknown): string | null {
  if (!record(response)) return null;
  if (proposal.kind === "app.launch") {
    return response.id === proposal.parameters.id && response.name === proposal.parameters.name && ["opened", "launched"].includes(String(response.status)) ? `Opened the registered target “${proposal.parameters.name}”.` : null;
  }
  if (proposal.kind === "workspace.restore") {
    const workspace = response.workspace;
    if (!record(workspace) || workspace.id !== proposal.parameters.id || workspace.name !== proposal.parameters.name || workspace.revision !== proposal.parameters.revision || !Array.isArray(response.apps)) return null;
    return `Requested workspace “${proposal.parameters.name}”.${response.apps.some(item => record(item) && item.status === "failed") ? " Some registered apps could not be opened; review Assistant." : " Its layout is ready in the connected app."}`;
  }
  if (proposal.kind === "memory.remember") {
    const saved = response.memory, p = proposal.parameters;
    if (!record(saved) || !titleText(saved.id, 100) || typeof saved.key !== "string" ||
      saved.key !== p.key.toLowerCase().replace(/^my\s+/, "") || saved.value !== p.value || saved.category !== p.category || saved.source !== "explicit_owner") return null;
    return `Saved the personal memory “${saved.key}”. You can review or correct it in Assistant.`;
  }
  if (proposal.kind === "memory.forget") {
    if (typeof response.forgotten !== "boolean" || response.key !== proposal.parameters.key) return null;
    return response.forgotten ? `Removed “${response.key}” from personal memory.` : `No saved personal memory matches “${response.key}”.`;
  }
  if (proposal.kind === "task.create") {
    try {
      const [task] = parseTasks([response.task]);
      const p = proposal.parameters;
      if (!task.id || task.title !== p.title || task.priority !== p.priority || task.status !== "Pending" || task.archived ||
        (p.deadline === null ? task.deadline !== null : task.deadline === null || Date.parse(task.deadline) !== Date.parse(p.deadline))) return null;
      return `Created task “${task.title}” with ${task.priority.toLowerCase()} priority${task.deadline ? `, due ${taskDeadlineLabel(task.deadline)}` : ", with no deadline"}. Saved deadlines appear in Assistant follow-through when enabled.`;
    } catch { return null; }
  }
  const event = response.event;
  const p = proposal.parameters;
  if (!record(event) || !titleText(event.id, 100) || event.title !== p.title || !validInstant(event.start) || event.recurrence !== p.recurrence ||
    !Array.isArray(event.channels) || event.channels.length !== 1 || event.channels[0] !== "console") return null;
  const when = pacificParts(event.start);
  if (when.date !== p.date || when.time !== p.time) return null;
  return `Added “${event.title}” to your ZÆNIA calendar for ${calendarWhenLabel(when.date, when.time)}${event.recurrence === "none" ? "" : `, repeating ${event.recurrence}`}. Follow-through appears in Assistant when enabled.`;
}
