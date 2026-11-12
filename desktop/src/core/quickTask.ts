import type { Priority } from "./taskModel";

/** Quick-add for Tasks & Calendar: "call bank fri 3pm !high" becomes a title, deadline and priority. */
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
export { iso as isoDay };
const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

export function parseQuickTask(text: string, now = new Date()): { title: string; deadline: string | null; priority: Priority } {
  let rest = ` ${text} `;
  let priority: Priority = "Normal";
  const bang = /\s!(critical|urgent|high|normal|low)\b/i.exec(rest);
  if (bang) { const p = bang[1].toLowerCase(); priority = p === "critical" || p === "urgent" ? "Critical" : p === "high" ? "High" : p === "low" ? "Low" : "Normal"; rest = rest.replace(bang[0], " "); }
  let day: Date | null = null;
  const rel = /\s(today|tonight|tomorrow|tmrw)\b/i.exec(rest);
  if (rel) { day = addDays(now, /tom|tmrw/i.test(rel[1]) ? 1 : 0); rest = rest.replace(rel[0], " "); }
  const wd = /\s(?:on\s)?(sun|mon|tue|wed|thu|fri|sat)(?:day|sday|nesday|rsday|urday|s)?\b/i.exec(rest);
  if (!day && wd) { const target = DAYS.indexOf(wd[1].toLowerCase()); day = addDays(now, ((target - now.getDay() + 7) % 7) || 7); rest = rest.replace(wd[0], " "); }
  const date = /\s(\d{4}-\d{2}-\d{2})\b/.exec(rest);
  if (!day && date) { day = new Date(`${date[1]}T12:00:00`); rest = rest.replace(date[0], " "); }
  let mins: number | null = null;
  const tm = /\s(?:at\s)?(\d{1,2})(?::(\d{2}))?\s?(am|pm)?\b/i.exec(rest);
  if (tm && (tm[3] || tm[2])) { let h = Number(tm[1]) % 12; if (tm[3]?.toLowerCase() === "pm") h += 12; if (!tm[3]) h = Number(tm[1]); mins = h * 60 + Number(tm[2] ?? 0); rest = rest.replace(tm[0], " "); }
  if (rel && /tonight/i.test(rel[1]) && mins === null) mins = 20 * 60;
  let deadline: string | null = null;
  if (day || mins !== null) { const d = day ?? new Date(now); d.setHours(mins !== null ? Math.floor(mins / 60) : 17, mins !== null ? mins % 60 : 0, 0, 0); deadline = d.toISOString(); }
  return { title: rest.replace(/\s+/g, " ").trim(), deadline, priority };
}

