import { api, LIVE_API } from "./bridge";

/**
 * What ZAE knows right now, for her reply to a wake-up call or sleep phrase: a few quick local reads (calendar,
 * tasks, today's food, news, security). Anything that fails is simply left out; she never fills gaps with guesses.
 */
export type Situation = Record<string, unknown>;
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export async function situationNow(extra: Situation = {}): Promise<Situation> {
  const now = new Date();
  const today = iso(now);
  const base: Situation = { hour: now.getHours(), minute: now.getMinutes(), ...extra };
  if (!LIVE_API) return base;
  const get = <T,>(path: string) => api<T>("GET", path, undefined, { timeoutMs: 5000 }).then(value => value, () => null);
  const [events, tasks, day, news, security] = await Promise.all([
    get<{ events: { date: string; time: string; allDay: boolean; title: string }[] }>(`/api/calendar?start=${today}&days=2`),
    get<{ tasks: { status: string; deadline: string | null }[] }>("/api/tasks"),
    get<{ eaten: { calories: number } | null; targets: { ready: boolean; eat?: number } }>(`/api/platform/personal/training/day?day=${today}`),
    get<{ stories: unknown[] }>("/api/news/tech?limit=20"),
    get<{ score: number }>("/api/security/summary"),
  ]);
  const nowTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const next = events?.events.filter(e => e.date > today || (e.date === today && (e.allDay || e.time >= nowTime)))
    .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`))[0];
  if (next) {
    const at = new Date(`${next.date}T${next.allDay ? "09:00" : next.time}`);
    const when = next.allDay ? (next.date === today ? "today" : "tomorrow")
      : `at ${at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}${next.date === today ? "" : " tomorrow"}`;
    base.next = { title: next.title, when, hoursAway: Math.round((at.getTime() - now.getTime()) / 36e5 * 10) / 10 };
  }
  if (tasks) {
    const open = tasks.tasks.filter(t => t.status !== "Completed");
    base.dueToday = open.filter(t => t.deadline?.slice(0, 10) === today).length;
    base.overdue = open.filter(t => t.deadline && t.deadline.slice(0, 10) < today).length;
  }
  if (day?.targets.ready && day.targets.eat && day.eaten) base.kcalLeft = Math.max(0, Math.round(day.targets.eat - day.eaten.calories));
  if (news) base.news = news.stories.length;
  if (security) base.security = security.score;
  return base;
}
