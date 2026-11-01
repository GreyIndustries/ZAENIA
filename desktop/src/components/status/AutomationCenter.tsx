import { useCallback, useEffect, useMemo, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";
import "../research/Research.css";

type Task = { id: string; title: string; status: string; deadline?: string | null; updatedAt?: string; history?: { at: string; status: string }[]; archived?: boolean };
type Project = { id: string; title: string; progress: number; nextStep?: { title: string } | null; updatedAt?: string };
type Job = { id: string; title: string; status: string; updatedAt?: string; createdAt?: string };
type Protocol = { id: string; name: string; enabled: boolean };
type Snapshot = {
  tasks: Task[]; projects: Project[]; jobs: Job[]; protocols: Protocol[];
  notifications: { unreadCount: number; settings?: { quietHours?: { enabled?: boolean; start?: string; end?: string } } };
  selfcare: { issues: string[]; backup?: { at?: string }; watchdog: boolean };
  insights: { enabled: boolean; insights: unknown[] };
  brief: { generatedAt: string; headline: string; counts: { attention: number; improve: number } };
  platform: { jobs: Job[]; activeWorkspace?: string | null; policy?: unknown };
};

const open = (page: string, tab: string, assistantTab?: string) => {
  window.dispatchEvent(new CustomEvent("zae:page-tab", { detail: { page, tab } }));
  if (assistantTab) window.setTimeout(() => window.dispatchEvent(new CustomEvent("zae:assistant-tab", { detail: assistantTab })), 80);
};
const since = (value?: string) => value ? Date.now() - new Date(value).getTime() <= 7 * 86400_000 : false;

/** Read-only status board over the routines ZAE already runs. Weekly review is computed from local records. */
export function AutomationCenter() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [weekly, setWeekly] = useState(false);
  const load = useCallback(async () => {
    setError(null);
    const [tasks, projects, jobs, protocols, notifications, selfcare, insights, brief, platform] = await Promise.allSettled([
      api<{ tasks: Task[] }>("GET", "/api/tasks"), api<{ projects: Project[] }>("GET", "/api/platform/projects"),
      api<{ jobs: Job[] }>("GET", "/api/platform/jobs"), api<{ protocols: Protocol[] }>("GET", "/api/protocols"),
      api<{ unreadCount: number; settings?: Snapshot["notifications"]["settings"] }>("GET", "/api/assistant/notifications?includeRead=true"),
      api<Snapshot["selfcare"]>("GET", "/api/selfcare"), api<Snapshot["insights"]>("GET", "/api/assistant/insights"),
      api<Snapshot["brief"]>("GET", "/api/system/brief"), api<Snapshot["platform"]>("GET", "/api/platform/summary"),
    ]);
    const val = <T,>(result: PromiseSettledResult<T>, fallback: T): T => result.status === "fulfilled" ? result.value : fallback;
    const next: Snapshot = {
      tasks: val(tasks, { tasks: [] }).tasks, projects: val(projects, { projects: [] }).projects,
      jobs: val(jobs, { jobs: [] }).jobs, protocols: val(protocols, { protocols: [] }).protocols,
      notifications: val(notifications, { unreadCount: 0 }), selfcare: val(selfcare, { issues: [], watchdog: false }),
      insights: val(insights, { enabled: false, insights: [] }), brief: val(brief, { generatedAt: "", headline: "", counts: { attention: 0, improve: 0 } }),
      platform: val(platform, { jobs: [] }),
    };
    setData(next); setUpdated(new Date());
    if ([tasks, projects, jobs, protocols, notifications, selfcare, insights, brief, platform].every(item => item.status === "rejected")) setError("The local ZÆNIA server did not return automation status.");
  }, []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);

  const review = useMemo(() => {
    const activeTasks = data?.tasks.filter(task => !task.archived && !/complete|done/i.test(task.status)) ?? [];
    const overdue = activeTasks.filter(task => task.deadline && new Date(task.deadline).getTime() < Date.now());
    const completedThisWeek = (data?.tasks ?? []).filter(task => task.history?.some(item => /complete|done/i.test(item.status) && since(item.at))).length;
    const recentJobs = (data?.jobs ?? []).filter(job => since(job.updatedAt ?? job.createdAt));
    return { activeTasks, overdue, completedThisWeek, recentJobs, nextSteps: (data?.projects ?? []).filter(project => project.nextStep).slice(0, 5) };
  }, [data]);

  if (!LIVE_API) return <div className="research"><p className="research__note">Automation status is available when the local ZÆNIA server is connected.</p></div>;
  const cards = [
    { title: "Project checkpoints", text: `${data?.projects.length ?? "–"} plans · ${review.nextSteps.length} with an available next step.`, target: ["assistant", "tools", "Projects"], action: "Open project plans" },
    { title: "Independent change review", text: "Code changes run checks in an isolated copy and wait for your approval. The local second-pass review is advisory; it cannot approve a change.", target: ["codedoctor", "build"], action: "Open build reviews" },
    { title: "Preflight and completion checks", text: `${data?.brief.counts.attention ?? "–"} attention item(s) in the latest system brief.`, target: ["status", "readiness"], action: "Review system readiness" },
    { title: "Phrase routines", text: `${data?.protocols.filter(item => item.enabled).length ?? "–"} enabled routine(s). Routines use approved, fixed ZAE actions.`, target: ["status", "protocols"], action: "Manage routines" },
    { title: "Event follow-through", text: `${review.overdue.length} overdue task(s) · past calendar events use one-time completion check-ins.`, target: ["tasks", ""], action: "Review tasks" },
    { title: "Background work", text: `${data?.jobs.filter(job => ["queued", "running", "working"].includes(job.status)).length ?? "–"} queued or running · ${review.recentJobs.length} jobs updated this week.`, target: ["assistant", "tools", "Work"], action: "Open work queue" },
    { title: "Quiet notifications", text: `${data?.notifications.unreadCount ?? "–"} unread · quiet-hour preferences are respected by the notification worker.`, target: ["assistant", "tools"], action: "Review notifications" },
    { title: "Weekly review", text: "A read-only rollup of completed and overdue tasks, project next steps, and recent background work.", target: ["tasks", ""], action: weekly ? "Hide weekly review" : "Generate this week's review", activate: true },
    { title: "Health and recovery", text: `${data?.selfcare.issues.length ?? "–"} health issue(s) · last backup ${data?.selfcare.backup?.at ? new Date(data.selfcare.backup.at).toLocaleString() : "not recorded"}.`, target: ["status", "selfsustain"], action: "Open health and recovery" },
    { title: "Workflow learning", text: `Learning ${data?.insights.enabled ? "on" : "off"} · ${data?.insights.insights.length ?? "–"} reviewable insight(s). Learning never grants permissions.`, target: ["assistant", "memory"], action: "Review learned patterns" },
  ];
  return <div className="research">
    <div className="research__actions"><p className="research__note" style={{ flex: 1, margin: 0 }}>Ten connected assistant workflows. This page reads local ZÆNIA records; it does not modify tasks, approve actions, or grant permissions.</p><button type="button" onClick={() => void load()}>Refresh</button></div>
    {error && <p className="research__error" role="alert">{error}</p>}
    {updated && <p className="research__meta">Local status checked {updated.toLocaleTimeString()}</p>}
    <div className="research__split research__split--even">{cards.map(card => <section className="research__side" key={card.title}>
      <h3>{card.title}</h3><p>{card.text}</p>
      <button type="button" className="research__primary" onClick={() => card.activate ? setWeekly(value => !value) : open(card.target![0], card.target![1], card.target![2])}>{card.action}</button>
    </section>)}</div>
    {weekly && data && <section className="research__side" aria-live="polite">
      <h3>This week's review</h3><p>Read-only summary · generated {updated?.toLocaleString()}. No records were changed.</p>
      <ul><li>{review.completedThisWeek} task(s) marked complete in the past 7 days.</li><li>{review.activeTasks.length} active task(s); {review.overdue.length} are past their deadline.</li>
        <li>{review.recentJobs.length} background job(s) updated in the past 7 days.</li></ul>
      <h4>Overdue tasks</h4>{review.overdue.length ? <ul>{review.overdue.slice(0, 8).map(task => <li key={task.id}>{task.title} · due {new Date(task.deadline!).toLocaleDateString()}</li>)}</ul> : <p>No overdue tasks found in the available task records.</p>}
      <h4>Next project steps</h4>{review.nextSteps.length ? <ul>{review.nextSteps.map(project => <li key={project.id}>{project.title}: {project.nextStep?.title}</li>)}</ul> : <p>No unblocked next steps were returned.</p>}
    </section>}
  </div>;
}
