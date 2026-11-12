/**
 * Display-only core progress schema. No user authority or backend commands are
 * represented by these fields. "ready" is informational only.
 */
export type ModulePhase = "ready" | "working" | "pending" | "error";
export type CoreModule = { id: string; name: string; phase: ModulePhase; detail?: string };
/** Live PC and server facts from GET /api/status (absent in preview data). */
export type SystemInfo = {
  mode: "full" | "unattended" | "voice_only";
  cpu: number | null;
  memory: number | null;
  uptimeSeconds: number;
  lastBriefAt: string | null;
  checkedAt: string;
};
export type CoreTelemetry = {
  codex?: { phase: "ready" | "working" | "offline" | "error"; detail: string; checkedAt: string };
  progress: number | null;
  phase: string;
  diagnostics: string;
  synchronization: string;
  modules: CoreModule[];
  system?: SystemInfo;
};

/** Clearly labeled sample. These values are not read from the local system. */
export const PREVIEW_TELEMETRY: CoreTelemetry = {
  progress: 78,
  phase: "INITIALIZING",
  diagnostics: "COMPLETE",
  synchronization: "IN PROGRESS",
  modules: [
    { id: "security", name: "Security", phase: "ready" },
    { id: "brain", name: "SE engine", phase: "ready" },
    { id: "voice", name: "Voice", phase: "working" },
    { id: "calendar", name: "Calendar", phase: "ready" },
    { id: "tasks", name: "Tasks", phase: "ready" },
    { id: "files", name: "Files", phase: "ready" },
    { id: "patterns", name: "Patterns", phase: "ready" },
    { id: "sync", name: "Synchronization", phase: "pending" },
  ],
};

function validPercent(value: unknown): number | null | undefined {
  if (value === null) return null;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100
    ? Math.round(value) : undefined;
}
const phases: ModulePhase[] = ["ready", "working", "pending", "error"];
/** null stays null; a 0-100 number is rounded; anything else is invalid (undefined). */
function optionalPercent(value: unknown): number | null | undefined {
  if (value === null) return null;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100 ? Math.round(value) : undefined;
}
const field = (x: unknown): string | null => typeof x === "string" && x.length <= 100 ? x : null;

/** Validates untrusted status JSON; malformed results never become displayed progress. */
export function parseCoreTelemetry(input: unknown): CoreTelemetry | null {
  if (!input || typeof input !== "object") return null;
  const x = input as Record<string, unknown>;
  const progress = validPercent(x.progress);
  if (progress === undefined || !Array.isArray(x.modules) || x.modules.length > 32) return null;
  const phase = field(x.phase);
  const diagnostics = field(x.diagnostics);
  const synchronization = field(x.synchronization);
  if (phase === null || diagnostics === null || synchronization === null) return null;
  const modules: CoreModule[] = [];
  for (const raw of x.modules) {
    if (!raw || typeof raw !== "object") return null;
    const m = raw as Record<string, unknown>;
    const id = field(m.id); const name = field(m.name);
    if (!id || !name || !phases.includes(m.phase as ModulePhase)) return null;
    const detail = m.detail === undefined ? undefined : field(m.detail);
    if (detail === null) return null;
    modules.push(detail ? { id, name, phase: m.phase as ModulePhase, detail } : { id, name, phase: m.phase as ModulePhase });
  }
  let codex: CoreTelemetry["codex"];
  if (x.codex !== undefined) {
    if (!x.codex || typeof x.codex !== "object") return null;
    const report = x.codex as Record<string, unknown>;
    const detail = field(report.detail);
    const checkedAt = field(report.checkedAt);
    if (!["ready", "working", "offline", "error"].includes(String(report.phase)) ||
      detail === null || checkedAt === null || !Number.isFinite(Date.parse(checkedAt))) return null;
    codex = { phase: report.phase as NonNullable<CoreTelemetry["codex"]>["phase"], detail, checkedAt };
  }
  let system: SystemInfo | undefined;
  if (x.system !== undefined) {
    if (!x.system || typeof x.system !== "object") return null;
    const s = x.system as Record<string, unknown>;
    const mode = s.mode === "full" || s.mode === "unattended" || s.mode === "voice_only" ? s.mode : null;
    const cpu = optionalPercent(s.cpu);
    const memory = optionalPercent(s.memory);
    const uptime = typeof s.uptime_seconds === "number" && Number.isFinite(s.uptime_seconds) && s.uptime_seconds >= 0 ? Math.floor(s.uptime_seconds) : null;
    const lastBrief = s.last_brief_at === null ? null : field(s.last_brief_at);
    const checkedAt = field(s.checked_at);
    if (!mode || cpu === undefined || memory === undefined || uptime === null || !checkedAt || !Number.isFinite(Date.parse(checkedAt))) return null;
    if (s.last_brief_at !== null && (lastBrief === null || !Number.isFinite(Date.parse(lastBrief)))) return null;
    system = { mode, cpu, memory, uptimeSeconds: uptime, lastBriefAt: lastBrief, checkedAt };
  }
  return { progress, phase, diagnostics, synchronization, modules, codex, system };
}

/**
 * Opt-in, read-only loopback endpoint. It is NOT auto-configured and it does
 * not carry secrets. A backend route must actually exist before enabling it.
 */
export function localStatusEndpoint(): string | null {
  const raw = import.meta.env.VITE_ZAENIA_STATUS_URL as string | undefined;
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) return null;
    if (url.username || url.password || url.search || url.hash) return null;
    return url.href;
  } catch { return null; }
}
