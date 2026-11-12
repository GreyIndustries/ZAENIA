import { useEffect, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";

/**
 * Inside a core category (Grey, 2026-10-30): panels of the recent things from that category's tabs, not the tabs
 * themselves. Each panel lists a few items and has "Open" for its tab. Everything is read from ZAE's own records;
 * a source that doesn't answer shows "Nothing yet" instead of guesses.
 */
type Item = { primary: string; secondary?: string; meta?: string };
export type CategoryPanel = { id: string; title: string; tab: string; tabLabel: string; items: Item[] | null };
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const when = (text?: string | null) => {
  if (!text) return "";
  const d = new Date(text);
  if (Number.isNaN(d.getTime())) return text;
  const days = Math.round((Date.now() - d.getTime()) / 864e5);
  return days <= 0 ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : days === 1 ? "yesterday" : days < 7 ? `${days} days ago` : d.toLocaleDateString([], { month: "short", day: "numeric" });
};
const clock = (time: string) => { const [h, m] = time.split(":").map(Number); return Number.isFinite(h) ? new Date(2000, 0, 1, h, m || 0).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : time; };
// One quiet retry: a busy moment on the server (a model loading) shouldn't leave a panel saying it couldn't load.
const get = <T,>(path: string) => api<T>("GET", path, undefined, { timeoutMs: 20_000 })
  .catch(() => new Promise(done => window.setTimeout(done, 1200)).then(() => api<T>("GET", path, undefined, { timeoutMs: 20_000 })))
  .then(value => value, () => null);
const P = "/api/platform/personal";

async function load(category: string): Promise<CategoryPanel[]> {
  const today = iso(new Date());
  if (category === "plan") {
    const [events, tasks, reminders, notes] = await Promise.all([
      get<{ events: { date: string; time: string; allDay: boolean; title: string }[] }>(`/api/calendar?start=${today}&days=7`),
      get<{ tasks: { title: string; status: string; deadline: string | null; updatedAt?: string }[] }>("/api/tasks"),
      get<{ reminders: { text: string; due: string; done?: boolean }[] }>("/api/reminders"),
      get<{ notes: { title: string; updatedAt: string; excerpt?: string }[] }>("/api/platform/notes?limit=5"),
    ]);
    return [
      { id: "events", title: "Coming up", tab: "tasks", tabLabel: "LIFE", items: events && events.events.slice(0, 8).map(e => ({ primary: e.title, meta: `${e.date === today ? "Today" : new Date(`${e.date}T00:00`).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}${e.allDay ? "" : ` · ${clock(e.time)}`}` })) },
      { id: "tasks", title: "Open tasks", tab: "tasks", tabLabel: "LIFE", items: tasks && tasks.tasks.filter(t => t.status !== "Completed")
        .sort((a, b) => (a.deadline ?? "9").localeCompare(b.deadline ?? "9")).slice(0, 8).map(t => ({ primary: t.title, secondary: t.status, meta: t.deadline ? (t.deadline.slice(0, 10) < today ? "Overdue" : `Due ${when(t.deadline)}`) : "" })) },
      { id: "reminders", title: "Reminders", tab: "tasks", tabLabel: "LIFE", items: reminders && reminders.reminders.filter(r => !r.done).slice(0, 8).map(r => ({ primary: r.text, meta: new Date(r.due).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }) })) },
      { id: "notes", title: "Recent notes", tab: "notes", tabLabel: "Notes", items: notes && notes.notes.slice(0, 8).map(n => ({ primary: n.title, secondary: (n.excerpt ?? "").slice(0, 90), meta: when(n.updatedAt) })) },
    ];
  }
  if (category === "health") {
    const [food, day, overview] = await Promise.all([
      get<{ items: { title: string; calories?: number; protein?: number; updatedAt?: string }[] }>(`${P}/food?day=${today}`),
      get<{ workout: { label: string; exercises: { exercise: string; prescription: string }[] }; eaten: { calories: number; protein: number } | null; targets: { ready: boolean; eat?: number; protein?: number } }>(`${P}/training/day?day=${today}`),
      get<{ weights: { date: string; weightLb: number }[]; habits: { workouts: boolean[] } }>(`${P}/training`),
    ]);
    return [
      { id: "food", title: "Eaten today", tab: "fitness", tabLabel: "LIFE · Fitness & Health", items: food && food.items.slice(0, 8).map(f => ({ primary: f.title, meta: f.calories != null ? `${Math.round(f.calories)} kcal${f.protein ? ` · ${Math.round(f.protein)} g protein` : ""}` : "" })) },
      { id: "training", title: day?.workout.label || "Today's training", tab: "fitness", tabLabel: "LIFE · Fitness & Health", items: day && day.workout.exercises.slice(0, 8).map(e => ({ primary: e.exercise, meta: e.prescription })) },
      { id: "totals", title: "Today so far", tab: "fitness", tabLabel: "LIFE · Fitness & Health", items: day && day.eaten ? [
        { primary: `${Math.round(day.eaten.calories)} kcal eaten`, meta: day.targets.eat ? `of ${Math.round(day.targets.eat)}` : "" },
        { primary: `${Math.round(day.eaten.protein)} g protein`, meta: day.targets.protein ? `of ${Math.round(day.targets.protein)} g` : "" }] : null },
      { id: "weight", title: "Recent weigh-ins", tab: "fitness", tabLabel: "LIFE · Fitness & Health", items: overview && overview.weights.slice(-8).reverse().map(w => ({ primary: `${w.weightLb.toFixed(1)} lb`, meta: when(`${w.date}T12:00`) })) },
    ];
  }
  if (category === "know") {
    const [topics, news, agent, inbox] = await Promise.all([
      get<{ topics: { name: string; sources: number; updatedAt?: string }[] }>("/api/research/notebook"),
      get<{ stories: { title: string; sources: string[]; published?: string | null }[] }>("/api/news/tech?limit=5"),
      get<{ jobs: { question: string; status: string; started: string }[] }>("/api/research/agent"),
      get<{ notifications: { title: string; message: string; dueAt: string }[] }>("/api/assistant/notifications?includeRead=true"),
    ]);
    return [
      { id: "topics", title: "Research topics", tab: "research", tabLabel: "Research", items: topics && topics.topics.slice(0, 8).map(t => ({ primary: t.name, meta: `${t.sources} sources${t.updatedAt ? ` · ${when(t.updatedAt)}` : ""}` })) },
      { id: "news", title: "Top stories", tab: "news", tabLabel: "News", items: news && news.stories.slice(0, 8).map(s => ({ primary: s.title, meta: `${s.sources.slice(0, 2).join(", ")}${s.published ? ` · ${when(s.published)}` : ""}` })) },
      { id: "agent", title: "Web research", tab: "research", tabLabel: "Research", items: agent && agent.jobs.slice(0, 8).map(j => ({ primary: j.question, meta: `${j.status} · ${when(j.started)}` })) },
      { id: "inbox", title: "From ZAE", tab: "assistant", tabLabel: "Assistant", items: inbox && inbox.notifications.slice(0, 8).map(n => ({ primary: n.title, secondary: n.message.slice(0, 100), meta: when(n.dueAt) })) },
    ];
  }
  if (category === "create") {
    const [music, projects] = await Promise.all([
      get<{ songs: { title: string; stage: string; archived: boolean; updatedAt?: string; releaseDate?: string }[] }>(`${P}/music/overview`),
      get<{ items: { title: string; category?: string; status?: string; updatedAt?: string }[] }>(`${P}/workbench?day=&archived=false&offset=0`),
    ]);
    const songs = music?.songs.filter(s => !s.archived) ?? null;
    return [
      { id: "songs", title: "Songs in progress", tab: "music", tabLabel: "Music", items: songs && songs.slice(0, 8).map(s => ({ primary: s.title, secondary: s.stage, meta: when(s.updatedAt) })) },
      { id: "releases", title: "Releases", tab: "music", tabLabel: "Music", items: songs && songs.filter(s => s.releaseDate).slice(0, 8).map(s => ({ primary: s.title, meta: s.releaseDate })) },
      { id: "projects", title: "Workbench projects", tab: "workbench", tabLabel: "Workbench", items: projects && projects.items.slice(0, 8).map(p => ({ primary: p.title, secondary: [p.category, p.status].filter(Boolean).join(" · "), meta: when(p.updatedAt) })) },
    ];
  }
  if (category === "build") {
    const [suggestions, proposals, arena] = await Promise.all([
      get<{ suggestions: { title: string; status: string; created: string }[] }>("/api/suggestions"),
      get<{ proposals: { status: string; path?: string; note?: string; createdAt?: string }[] }>("/api/files/proposals"),
      get<{ board: { model: string; wins: number; rounds: number }[]; rounds: { question?: string; prompt?: string; at?: string; created?: string }[] }>("/api/arena"),
    ]);
    return [
      { id: "suggestions", title: "Code Doctor ideas", tab: "codedoctor", tabLabel: "Code Doctor & Files", items: suggestions && suggestions.suggestions.filter(s => s.status === "new").slice(0, 8).map(s => ({ primary: s.title, meta: when(s.created) })) },
      { id: "files", title: "File changes", tab: "files", tabLabel: "Files", items: proposals && proposals.proposals.slice(0, 8).map(p => ({ primary: p.path ?? "Change", secondary: p.note, meta: `${p.status}${p.createdAt ? ` · ${when(p.createdAt)}` : ""}` })) },
      { id: "arena", title: "Arena leaderboard", tab: "arena", tabLabel: "Arena", items: arena && arena.board.slice(0, 8).map(b => ({ primary: b.model, meta: `${b.wins} of ${b.rounds} won` })) },
    ];
  }
  const [bar, checks, activity, security] = await Promise.all([
    get<{ model: string; brains?: { model: string }[]; voice: string; cpu: number; ramUsedGb: number; ramTotalGb: number; diskFreeGb: number; backup: string | null }>("/api/status/bar"),
    get<{ latest: { status: string; at?: string; counts?: Record<string, number> } | null }>("/api/security/checks"),
    get<{ events: { at: string; label: string; severity: string }[] }>("/api/security/activity?limit=6"),
    get<{ level: string; score: number }>("/api/security/summary"),
  ]);
  return [
    { id: "status", title: "This PC now", tab: "status", tabLabel: "Status", items: bar && [
      { primary: `CPU ${Math.round(bar.cpu)}% · RAM ${bar.ramUsedGb.toFixed(1)} of ${bar.ramTotalGb.toFixed(1)} GB` }, { primary: `SE: ${bar.brains?.[0] ? `Talk ${bar.brains[0].model}` : bar.model}`, meta: `Voice: ${bar.voice}` },
      { primary: `${Math.round(bar.diskFreeGb)} GB free`, meta: bar.backup ? `Backup ${bar.backup}` : "" }] },
    { id: "security", title: "Security", tab: "security", tabLabel: "Security", items: security && [
      { primary: `Score ${security.score} · ${security.level}`, meta: checks?.latest ? `Last check: ${checks.latest.status}${checks.latest.at ? `, ${when(checks.latest.at)}` : ""}` : "" }] },
    { id: "activity", title: "Recent security activity", tab: "security", tabLabel: "Security", items: activity && activity.events.slice(0, 8).map(e => ({ primary: e.label, meta: when(e.at) })) },
  ];
}

export function useCategoryPanels(category: string | null) {
  const [panels, setPanels] = useState<CategoryPanel[] | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setPanels(null);
    if (!category) return;
    if (LIVE_API) void load(category).then(next => { if (live) setPanels(next); }).catch(() => { if (live) setPanels([]); });
    else setPanels([]);
    return () => { live = false; };
  }, [category, attempt]);
  return { panels, retry: () => setAttempt(n => n + 1) };
}

export function CategoryPanels({ name, description, onOpen, onBack, panels, onRetry }: {
  name: string; description: string; onOpen: (tab: string) => void; onBack: () => void;
  panels: CategoryPanel[] | null; onRetry: () => void;
}) {
  return <div className="ov-cat" role="region" aria-label={`${name}: recent things`}>
    <header className="ov-cat__head">
      <button type="button" className="ov-cat__back" onClick={onBack}>← Core</button>
      <div><span className="ov-kicker">{name}</span><h2 className="zx-title">{description}</h2></div>
    </header>
    {!LIVE_API && <p className="ov-muted">These panels need the ZÆNIA server: open them in the desktop or phone app.</p>}
    {LIVE_API && !panels && <p className="ov-muted" role="status">Gathering the latest…</p>}
    <div className={`ov-cat__grid ov-cat__grid--${Math.min(panels?.length ?? 0, 6)}`}>
      {panels?.map(panel => <section key={panel.id} className="ov-cat__panel zx-card">
        <header><b>{panel.title}</b><button type="button" onClick={() => onOpen(panel.tab)}>Open {panel.tabLabel} ↗</button></header>
        {panel.items && panel.items.length ? <ul>{panel.items.map((item, i) => <li key={i}><span>{item.primary}{item.secondary && <small>{item.secondary}</small>}</span>{item.meta && <em>{item.meta}</em>}</li>)}</ul>
          : panel.items ? <p className="ov-muted">Nothing yet.</p>
          : <p className="ov-muted">Couldn't load this right now. <button type="button" className="ov-cat__retry" onClick={onRetry}>Try again</button></p>}
      </section>)}
    </div>
  </div>;
}
