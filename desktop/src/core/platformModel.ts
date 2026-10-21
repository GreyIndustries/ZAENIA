/** Bounded display data and device-only preferences for assistant capabilities. */
export type BackgroundJob = { id: string; title: string; priority: boolean; status: string; stage: string; detail: string; completedUnits: number | null; totalUnits: number | null; elapsedSeconds: number; result?: { answer?: string; indexed?: number; errors?: unknown[]; draft?: { title: string; goal: string; steps: { id: string; title: string; milestone: string; status: "pending" | "active" | "completed"; deadline: string | null; dependsOn: string[] }[] } } | null };
export type PlatformPolicy = { voiceAutomatic: string[]; chatAutomatic: string[] };
export type PlatformSummary = { jobs: BackgroundJob[]; policy: PlatformPolicy; metricsSource: "pcVoice" | "api"; activeWorkspace: { workspaceId: string; revision: number } | null; metrics: { firstTextP50Ms: number | null; firstTextP95Ms: number | null; samples: { stage: string; ms: number; kind?: string }[] } };
export const DISPLAY_KEYS = ["zaenia.shellWindows", "zaenia.workspaceLayout", "zaenia.appearance", "zaenia.speakReplies", "zaenia.visualMode", "zaenia.motion", "zaenia.sidebarHidden", "zaenia.coreDock"] as const;
export const ACTION_KINDS = ["task.create", "calendar.create", "memory.remember", "app.launch", "workspace.restore"] as const;
const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && !Array.isArray(value);
const identifier = (value: unknown): value is string => typeof value === "string" && /^[A-Za-z0-9_-]{1,100}$/.test(value);
export function parsePlatformSummary(value: unknown): PlatformSummary | null {
  if (!object(value) || !Array.isArray(value.jobs) || !object(value.policy) || !object(value.metrics)) return null;
  const jobs = value.jobs.filter((row): row is Record<string, unknown> => object(row) && identifier(row.id) && typeof row.title === "string" && typeof row.stage === "string" && typeof row.status === "string").slice(0, 100).map(row => ({
    id: String(row.id), title: String(row.title).slice(0, 200), priority: row.priority === true, status: String(row.status), stage: String(row.stage), detail: typeof row.detail === "string" ? row.detail.slice(0, 600) : "",
    completedUnits: typeof row.completedUnits === "number" && Number.isFinite(row.completedUnits) ? Math.max(0, row.completedUnits) : null,
    totalUnits: typeof row.totalUnits === "number" && Number.isFinite(row.totalUnits) ? Math.max(0, row.totalUnits) : null,
    elapsedSeconds: typeof row.elapsedSeconds === "number" && Number.isFinite(row.elapsedSeconds) ? Math.max(0, row.elapsedSeconds) : 0,
    result: object(row.result) ? row.result as BackgroundJob["result"] : null,
  }));
  const allowed = (values: unknown) => Array.isArray(values) ? values.filter((kind): kind is string => typeof kind === "string" && (ACTION_KINDS as readonly string[]).includes(kind)) : [];
  const milliseconds = (value: unknown) => typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
  return { jobs, metricsSource: value.metricsSource === "pcVoice" ? "pcVoice" : "api", policy: { voiceAutomatic: allowed(value.policy.voiceAutomatic), chatAutomatic: allowed(value.policy.chatAutomatic) },
    activeWorkspace: object(value.activeWorkspace) && identifier(value.activeWorkspace.workspaceId) && typeof value.activeWorkspace.revision === "number" ? value.activeWorkspace as PlatformSummary["activeWorkspace"] : null,
    metrics: { firstTextP50Ms: milliseconds(value.metrics.firstTextP50Ms), firstTextP95Ms: milliseconds(value.metrics.firstTextP95Ms), samples: Array.isArray(value.metrics.samples) ? value.metrics.samples.filter((row): row is { stage: string; ms: number } => object(row) && typeof row.stage === "string" && milliseconds(row.ms) !== null).slice(-40) : [] } };
}
export function jobPercent(job: Pick<BackgroundJob, "completedUnits" | "totalUnits">): number | null {
  return job.completedUnits !== null && job.totalUnits !== null && job.totalUnits > 0 ? Math.min(100, Math.max(0, 100 * job.completedUnits / job.totalUnits)) : null;
}
export function displayPreferences(storage: Pick<Storage, "getItem">): Record<string, string> {
  const values: Record<string, string> = {};
  for (const key of DISPLAY_KEYS) { const value = storage.getItem(key); if (value !== null && value.length <= 100_000) values[key] = value; }
  return values;
}
