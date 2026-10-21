import { useEffect, useRef, useState } from "react";
import { api, DESKTOP_APPROVER, errorText, LIVE_API, openProfileTool, restartServer, startVoiceService } from "../../core/bridge";
import { ACTION_KINDS, displayPreferences, jobPercent } from "../../core/platformModel";
import type { BackgroundJob, PlatformPolicy } from "../../core/platformModel";
import type { usePlatformRuntime } from "../../core/usePlatformRuntime";
import type { ShellWindow } from "../shell/WindowShell";
import "./PlatformPanel.css";
import { ProjectPlanEditor } from "./ProjectPlanEditor";
import type { Plan } from "./ProjectPlanEditor";
import { OperatorPanel } from './OperatorPanel';

type Item = { id: string; revision: number; name: string; path: string };
type Workspace = { id: string; revision: number; name: string; note: string; windows: ShellWindow[]; apps: string[]; projectId: string | null };
type Step = { id: string; title: string; milestone: string; status: "pending" | "active" | "completed"; deadline: string | null; dependsOn: string[] };
type Project = { id: string; revision: number; title: string; goal: string; steps: Step[]; progress: number; nextStep: Step | null };
type Receipt = { id: string; label: string; kind: string; status: string; undoable: boolean; updatedAt: string };
type SearchResult = { rootId: string; folder: string; path: string; page: number | null; excerpt: string };
type Health = { checkedAt: string; components: { id: string; state: string; detail: string }[] };
type Readiness = { ready: boolean; checks: { id: string; ok: boolean; detail: string }[]; scope: string; manualChecks: string[]; portableExclusions: string[] };
const TABS = ["Work", "Operate", "Apps", "Workspaces", "Projects", "Documents", "Approvals", "Health", "Portable", "Hands"] as const;
type Tab = typeof TABS[number];
const pathFor = (route: string) => `/api/platform/${route}`;

export function BackgroundWorkBadge({ jobs, onOpen }: { jobs: BackgroundJob[]; onOpen: () => void }) {
  const active = jobs.filter(job => ["queued", "running"].includes(job.status));
  if (!active.length) return null;
  const first = active.find(job => job.priority) ?? active[0];
  return <button type="button" className="background-work-badge" onClick={onOpen} title={first.title} aria-label={`Open background work: ${first.stage}`}>
    <span className="background-work-badge__dot"/><strong>{first.priority ? "PRIORITY" : "BACKGROUND"}</strong><span>{first.stage}</span><small>{active.length > 1 ? `${active.length} jobs` : `${Math.round(first.elapsedSeconds)}s`}</small>
  </button>;
}

function JobCard({ job, cancel, disabled }: { job: BackgroundJob; cancel: () => void; disabled: boolean }) {
  const percent = jobPercent(job);
  return <article className="platform-card">
    <div className="platform-card__head"><strong>{job.title}</strong><span>{job.priority ? "Priority · " : ""}{job.status}</span></div>
    <p>{job.stage} · {Math.round(job.elapsedSeconds)}s</p>{job.detail && <small>{job.detail}</small>}
    {percent !== null && <><progress value={percent} max={100}/><small>{job.completedUnits} / {job.totalUnits} completed</small></>}
    {job.priority && ["queued", "running"].includes(job.status) && <small>Kept alongside conversation; never cancelled just because you ask another question.</small>}
    {["queued", "running"].includes(job.status) && <button type="button" disabled={disabled} onClick={cancel}>Cancel this job</button>}
    {job.result && <details><summary>Result</summary>{job.result.answer ? <pre>{job.result.answer}</pre> : <pre>{JSON.stringify(job.result, null, 2)}</pre>}</details>}
  </article>;
}

export function PlatformPanel({ runtime, windows, onRestore, hands, toggleHands, handNote, handsSupported }: {
  runtime: ReturnType<typeof usePlatformRuntime>; windows: ShellWindow[]; onRestore: (windows: ShellWindow[]) => void;
  hands: boolean; toggleHands: () => void; handNote: string | null; handsSupported: boolean;
}) {
  const [tab, setTab] = useState<Tab>("Work");
  const [busy, setBusy] = useState(false); const busyRef = useRef(false);
  const [error, setError] = useState<string | null>(null); const [note, setNote] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState(""); const [priority, setPriority] = useState(false);
  const [apps, setApps] = useState<Item[]>([]); const [suggestions, setSuggestions] = useState<{ name: string; path: string }[]>([]);
  const [targetName, setTargetName] = useState(""); const [targetPath, setTargetPath] = useState("");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]); const [workspaceName, setWorkspaceName] = useState(""); const [workspaceNote, setWorkspaceNote] = useState(""); const [workspaceApps, setWorkspaceApps] = useState<string[]>([]); const [workspaceProject, setWorkspaceProject] = useState("");
  const [projects, setProjects] = useState<Project[]>([]); const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectTitle, setProjectTitle] = useState(""); const [projectGoal, setProjectGoal] = useState(""); const [stepLines, setStepLines] = useState("");
  const [generatedDraft, setGeneratedDraft] = useState<Plan | null>(null);
  const [stepTitle, setStepTitle] = useState(""); const [milestone, setMilestone] = useState(""); const [deadline, setDeadline] = useState(""); const [dependsOn, setDependsOn] = useState<string[]>([]);
  const [folders, setFolders] = useState<Item[]>([]); const [folderName, setFolderName] = useState(""); const [folderPath, setFolderPath] = useState(""); const [query, setQuery] = useState(""); const [results, setResults] = useState<SearchResult[]>([]);
  const [policy, setPolicy] = useState<PlatformPolicy>({ voiceAutomatic: [], chatAutomatic: [] });
  const [receipts, setReceipts] = useState<Receipt[]>([]); const [undoAsked, setUndoAsked] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null); const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [profileMode, setProfileMode] = useState<"export" | "restore">("export"); const [profilePath, setProfilePath] = useState(""); const [restoreMode, setRestoreMode] = useState("merge"); const [profileRequests, setProfileRequests] = useState<{ id: string; mode: string; status: string; path: string }[]>([]);
  const [snapshot, setSnapshot] = useState<{ id: string; files: number; bytes: number } | null>(null);
  const [importedDisplay, setImportedDisplay] = useState<{ values: Record<string, string>; needsReview: boolean } | null>(null);
  const [autoRecovery, setAutoRecovery] = useState(() => { try { return localStorage.getItem("zaenia.autoRecovery") === "1"; } catch { return false; } });
  const disabled = busy || !LIVE_API;
  const desktopDisabled = disabled || !DESKTOP_APPROVER;

  async function load(next: Tab = tab) {
    if (!LIVE_API) return;
    if (next === "Apps") { const [registered, proposed] = await Promise.all([api<{ apps: Item[] }>("GET", pathFor("apps")), api<{ suggestions: { name: string; path: string }[] }>("GET", pathFor("apps/suggestions"))]); setApps(registered.apps); setSuggestions(proposed.suggestions); }
    if (next === "Workspaces") { const [saved, registered, plans] = await Promise.all([api<{ workspaces: Workspace[]; importedDisplay: typeof importedDisplay }>("GET", pathFor("workspaces")), api<{ apps: Item[] }>("GET", pathFor("apps")), api<{ projects: Project[] }>("GET", pathFor("projects"))]); setWorkspaces(saved.workspaces); setImportedDisplay(saved.importedDisplay); setApps(registered.apps); setProjects(plans.projects); }
    if (next === "Projects") { const reply = await api<{ projects: Project[] }>("GET", pathFor("projects")); setProjects(reply.projects); }
    if (next === "Documents") { const reply = await api<{ folders: Item[] }>("GET", pathFor("documents")); setFolders(reply.folders); }
    if (next === "Approvals") { const [settings, actions] = await Promise.all([api<PlatformPolicy>("GET", pathFor("approvals")), api<{ actions: Receipt[] }>("GET", pathFor("actions"))]); setPolicy(settings); setReceipts(actions.actions); }
    if (next === "Health") setHealth(await api<Health>("GET", pathFor("health")));
    if (next === "Portable") { const [checks, requests] = await Promise.all([api<Readiness>("GET", pathFor("readiness")), api<{ requests: typeof profileRequests }>("GET", pathFor("profile/requests"))]); setReadiness(checks); setProfileRequests(requests.requests); }
    if (next === "Work") await runtime.refresh();
  }
  async function perform(action: () => Promise<unknown>, message?: string) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(null); setNote(null);
    try { await action(); if (message) setNote(message); await runtime.refresh(); await load(); }
    catch (failure) { setError(errorText(failure)); }
    finally { busyRef.current = false; setBusy(false); }
  }
  useEffect(() => { let active = true; setError(null); void load(tab).catch(failure => { if (active) setError(errorText(failure)); }); return () => { active = false; }; }, [tab]);
  useEffect(() => {
    const select = (event: Event) => { const requested = (event as CustomEvent<string>).detail; if ((TABS as readonly string[]).includes(requested)) setTab(requested as Tab); };
    window.addEventListener("zae:assistant-tab", select); return () => window.removeEventListener("zae:assistant-tab", select);
  }, []);
  const changeProject = (project: Project, updates: Partial<Project>) => perform(async () => {
    const reply = await api<Project>("PATCH", pathFor(`projects/${project.id}`), { title: updates.title ?? project.title, goal: updates.goal ?? project.goal, steps: updates.steps ?? project.steps, revision: project.revision });
    setSelectedProject(reply);
  }, "Project saved from your verified step updates.");

  return <section className="section-content platform-panel" aria-label="Assistant capabilities" aria-busy={busy}>
    <div className="platform-panel__heading"><div><span className="subheading">ASSISTANT TOOLS</span><h2>Work with ZAE</h2></div><button type="button" disabled={disabled} onClick={() => void perform(() => load())}>Refresh</button></div>
    <nav className="platform-tabs" aria-label="Assistant capability sections">{TABS.map(name => <button type="button" key={name} aria-pressed={tab === name} onClick={() => setTab(name)}>{name}</button>)}</nav>
    {!LIVE_API && <p className="platform-note">Connect the desktop or phone app to use these tools. Camera control remains optional and device-local.</p>}
    {error && <p className="platform-error" role="alert">{error}</p>}{note && <p className="platform-note" role="status">{note}</p>}
    {tab === "Operate" && <OperatorPanel/>}
    {tab === "Work" && <>
      <p>Ask ZAE normally while analysis runs. Mark work as priority when you want it kept alongside the conversation.</p>
      <form onSubmit={event => { event.preventDefault(); void perform(async () => { await api("POST", pathFor("jobs"), { question: analysis, priority }); setAnalysis(""); }, "Background analysis queued; its actual stages and results appear below."); }}>
        <label>Analysis to do<textarea value={analysis} onChange={event => setAnalysis(event.target.value)} maxLength={6000} required placeholder="Compare the next steps for my project…"/></label>
        <label className="platform-check"><input type="checkbox" checked={priority} onChange={event => setPriority(event.target.checked)}/>Priority: keep running while we talk</label>
        <button type="submit" disabled={disabled || !analysis.trim()}>Start background analysis</button>
      </form>
      {runtime.error && <p className="platform-error">{runtime.error}</p>}
      <div className="platform-metrics"><span>{runtime.summary?.metricsSource === "pcVoice" ? "PC voice" : "API"} model first text · median <strong>{runtime.summary?.metrics.firstTextP50Ms === null || !runtime.summary ? "Not measured" : `${runtime.summary.metrics.firstTextP50Ms} ms`}</strong></span><span>95th percentile <strong>{runtime.summary?.metrics.firstTextP95Ms === null || !runtime.summary ? "Not measured" : `${runtime.summary.metrics.firstTextP95Ms} ms`}</strong></span></div>
      <small>Measurements cover local processing, not physical microphone/speaker latency. Percentages appear only for steps with a known total.</small>
      {(runtime.summary?.jobs ?? []).length === 0 && <p className="platform-note">No background jobs yet.</p>}
      {(runtime.summary?.jobs ?? []).slice(0, 30).map(job => <JobCard key={job.id} job={job} disabled={disabled} cancel={() => void perform(() => api("POST", pathFor(`jobs/${job.id}/cancel`)))}/>)}
      <details><summary>Recent processing measurements</summary><ul>{runtime.summary?.metrics.samples.slice(-12).map((sample, index) => <li key={index}>{sample.stage.replace(/_/g, " ")} · {sample.ms} ms</li>)}</ul></details>
    </>}
    {tab === "Apps" && <>
      <p>Register exact local targets, then say “open Blender” or the name you chose. Changing an executable requires registering it again.</p>
      {!DESKTOP_APPROVER && <p className="platform-note">Add and open local targets from the paired desktop app.</p>}
      <form onSubmit={event => { event.preventDefault(); void perform(async () => { await api("POST", pathFor("apps"), { name: targetName, path: targetPath }, { desktop: true }); setTargetName(""); setTargetPath(""); }, "Target registered. ZAE can now propose opening it by name."); }}>
        <label>Name<input value={targetName} onChange={event => setTargetName(event.target.value)} maxLength={100} required placeholder="Blender"/></label><label>Local application, file, or folder<input value={targetPath} onChange={event => setTargetPath(event.target.value)} maxLength={1000} required placeholder="C:\Program Files\…\blender.exe"/></label><button type="submit" disabled={desktopDisabled}>Register reviewed target</button>
      </form>
      {suggestions.length > 0 && <div className="platform-inline"><span>Detected choices:</span>{suggestions.map(item => <button type="button" key={item.path} disabled={desktopDisabled} onClick={() => { setTargetName(item.name); setTargetPath(item.path); }}>{item.name}</button>)}</div>}
      {apps.map(item => <article className="platform-card" key={item.id}><strong>{item.name}</strong><small>{item.path}</small><div className="platform-inline"><button type="button" disabled={desktopDisabled} onClick={() => void perform(() => api("POST", pathFor(`apps/${item.id}/launch`), undefined, { desktop: true }), `Opened registered target ${item.name}.`)}>Open {item.name}</button><button type="button" disabled={desktopDisabled} onClick={() => void perform(() => api("DELETE", pathFor(`apps/${item.id}`), undefined, { desktop: true }), "Target permission removed; the app/file itself was left in place.")}>Remove permission</button></div></article>)}
    </>}
    {tab === "Workspaces" && <>
      <p>Save this layout, working notes and selected registered apps. Resume with “restore coding workspace,” using your chosen name.</p>
      <form onSubmit={event => { event.preventDefault(); void perform(async () => { await api("POST", pathFor("workspaces"), { name: workspaceName, windows, note: workspaceNote, apps: workspaceApps, projectId: workspaceProject || null }); setWorkspaceName(""); }, "Current layout and session context saved."); }}>
        <label>Workspace name<input value={workspaceName} onChange={event => setWorkspaceName(event.target.value)} maxLength={80} required placeholder="Coding"/></label><label>Where you left off<textarea value={workspaceNote} onChange={event => setWorkspaceNote(event.target.value)} maxLength={2000} placeholder="Next: verify the inspection checklist…"/></label>
        <label>Project<select value={workspaceProject} onChange={event => setWorkspaceProject(event.target.value)}><option value="">No linked project</option>{projects.map(project => <option value={project.id} key={project.id}>{project.title}</option>)}</select></label>
        <fieldset><legend>Registered apps to reopen with approval</legend>{apps.length === 0 ? <small>Register targets in Apps first.</small> : apps.map(app => <label className="platform-check" key={app.id}><input type="checkbox" checked={workspaceApps.includes(app.id)} onChange={event => setWorkspaceApps(values => event.target.checked ? [...values, app.id] : values.filter(id => id !== app.id))}/>{app.name}</label>)}</fieldset>
        <button type="submit" disabled={disabled}>Save current workspace</button>
      </form>
      {workspaces.map(workspace => <article className="platform-card" key={workspace.id}><strong>{workspace.name}</strong><p>{workspace.note || "No session note."}</p><small>{workspace.windows.length} windows · {workspace.apps.length} registered apps</small><div className="platform-inline">
        <button type="button" disabled={disabled} onClick={() => void perform(async () => { const reply = await api<{ workspace: Workspace }>("POST", pathFor(`workspaces/${workspace.id}/restore`), { launchApps: false, revision: workspace.revision }); onRestore(reply.workspace.windows); }, "Workspace layout and context restored.")}>Restore layout</button>
        <button type="button" disabled={desktopDisabled} onClick={() => void perform(async () => { const reply = await api<{ workspace: Workspace; apps: { status: string }[] }>("POST", pathFor(`workspaces/${workspace.id}/restore`), { launchApps: true, revision: workspace.revision }, { desktop: true }); onRestore(reply.workspace.windows); if (reply.apps.some(app => app.status === "failed")) throw new Error("Layout restored; some registered apps could not be opened."); }, "Layout restored and registered apps opened.")}>Restore with apps</button>
        <button type="button" disabled={disabled} onClick={() => void perform(() => api("PATCH", pathFor(`workspaces/${workspace.id}`), { name: workspace.name, windows, apps: workspace.apps, projectId: workspace.projectId, note: workspaceNote || workspace.note, revision: workspace.revision }), "Saved this layout over the reviewed workspace.")}>Update from current layout</button>
        <button type="button" disabled={disabled} onClick={() => void perform(() => api("DELETE", pathFor(`workspaces/${workspace.id}`)), "Saved workspace removed; apps/files were left in place.")}>Remove saved layout</button>
      </div></article>)}
      {importedDisplay?.needsReview && <button type="button" onClick={() => { const allowed = displayPreferences({ getItem: key => importedDisplay.values[key] ?? null }); for (const [key, value] of Object.entries(allowed)) localStorage.setItem(key, value); window.location.reload(); }}>Apply imported display preferences and reload</button>}
    </>}
    {tab === "Projects" && <>
      <p>Plans start as proposals. Progress changes only when you update steps; prerequisite steps must be completed first.</p>
      <form onSubmit={event => { event.preventDefault(); void perform(async () => { const project = await api<Project>("POST", pathFor("projects"), { title: projectTitle, goal: projectGoal, steps: stepLines.split("\n").filter(line => line.trim()).map(title => ({ title, status: "pending" })) }); setSelectedProject(project); setProjectTitle(""); setStepLines(""); }, "Editable project created."); }}>
        <label>Project<input value={projectTitle} onChange={event => setProjectTitle(event.target.value)} maxLength={200} required/></label><label>Goal<textarea value={projectGoal} onChange={event => setProjectGoal(event.target.value)} maxLength={2000}/></label><label>Initial steps · one per line<textarea value={stepLines} onChange={event => setStepLines(event.target.value)} placeholder="Inspect current setup\nBuild and verify the next change"/></label><button type="submit" disabled={disabled}>Create project</button>
      </form>
      <button type="button" disabled={disabled || !projectTitle.trim() || !projectGoal.trim()} onClick={() => void perform(() => api("POST", pathFor("projects/plan"), { title: projectTitle, goal: projectGoal }), "The local brain is drafting proposed steps; review the completed draft below before saving.")}>Draft steps from this goal with the local brain</button>
      {(runtime.summary?.jobs ?? []).filter(job => job.status === "completed" && job.result?.draft).slice(0, 5).map(job => <button type="button" key={job.id} onClick={() => setGeneratedDraft(job.result!.draft!)}>Review draft: {job.title}</button>)}
      {generatedDraft && <article className="platform-card"><h3>Review proposed plan</h3><p>No tasks have been created or completed from this draft.</p><ProjectPlanEditor plan={generatedDraft} version={JSON.stringify(generatedDraft)} disabled={disabled} onSave={plan => perform(async () => { const saved = await api<Project>("POST", pathFor("projects"), plan); setSelectedProject(saved); setGeneratedDraft(null); }, "Reviewed project plan saved.")}/></article>}
      <div className="platform-inline">{projects.map(project => <button type="button" key={project.id} aria-pressed={selectedProject?.id === project.id} onClick={() => setSelectedProject(project)}>{project.title} · {project.progress}%</button>)}</div>
      {selectedProject && <article className="platform-card"><h3>{selectedProject.title}</h3><p>{selectedProject.goal}</p><progress value={selectedProject.progress} max={100}/><p>Next available step: {selectedProject.nextStep?.title ?? "No unblocked unfinished steps."}</p>
        <details><summary>Edit titles, milestones, deadlines and dependencies</summary><ProjectPlanEditor plan={selectedProject} version={`${selectedProject.id}:${selectedProject.revision}`} disabled={disabled} onSave={plan => changeProject(selectedProject, plan)}/></details>
        <ol className="platform-steps">{selectedProject.steps.map(step => <li key={step.id}><strong>{step.title}</strong><small>{step.milestone}{step.deadline ? ` · due ${step.deadline}` : ""}{step.dependsOn.length ? ` · ${step.dependsOn.length} prerequisites` : ""}</small><select value={step.status} disabled={disabled} aria-label={`Status for ${step.title}`} onChange={event => void changeProject(selectedProject, { steps: selectedProject.steps.map(item => item.id === step.id ? { ...item, status: event.target.value as Step["status"] } : item) })}><option value="pending">Pending</option><option value="active">In progress</option><option value="completed">Completed</option></select></li>)}</ol>
        <form onSubmit={event => { event.preventDefault(); void changeProject(selectedProject, { steps: [...selectedProject.steps, { id: crypto.randomUUID().replace(/-/g, ""), title: stepTitle, milestone: milestone || "Work", status: "pending", deadline: deadline || null, dependsOn }] }); setStepTitle(""); setDependsOn([]); }}><label>New step<input value={stepTitle} onChange={event => setStepTitle(event.target.value)} required maxLength={300}/></label><div className="platform-columns"><label>Milestone<input value={milestone} onChange={event => setMilestone(event.target.value)} maxLength={120}/></label><label>Deadline<input type="date" value={deadline} onChange={event => setDeadline(event.target.value)}/></label></div><fieldset><legend>Prerequisites</legend>{selectedProject.steps.map(step => <label className="platform-check" key={step.id}><input type="checkbox" checked={dependsOn.includes(step.id)} onChange={event => setDependsOn(values => event.target.checked ? [...values, step.id] : values.filter(id => id !== step.id))}/>{step.title}</label>)}</fieldset><button type="submit" disabled={disabled}>Add step</button></form>
      </article>}
    </>}
    {tab === "Documents" && <>
      <p>Only explicitly selected folders are indexed. PDF results cite actual pages; Word/text results cite the file. Changed files are withheld until reindexed.</p>
      <form onSubmit={event => { event.preventDefault(); void perform(async () => { await api("POST", pathFor("documents"), { name: folderName, path: folderPath }, { desktop: true }); setFolderName(""); setFolderPath(""); }, "Folder selected. Choose Index to read its supported documents locally."); }}><label>Folder label<input value={folderName} onChange={event => setFolderName(event.target.value)} maxLength={100} required/></label><label>Local folder<input value={folderPath} onChange={event => setFolderPath(event.target.value)} maxLength={1000} required placeholder="C:\Users\…\Documents\Project notes"/></label><button type="submit" disabled={desktopDisabled}>Approve this folder</button></form>
      {folders.map(folder => <article className="platform-card" key={folder.id}><strong>{folder.name}</strong><small>{folder.path}</small><div className="platform-inline"><button type="button" disabled={desktopDisabled} onClick={() => void perform(() => api("POST", pathFor(`documents/${folder.id}/index`), undefined, { desktop: true }), "Indexing started; progress appears in Work.")}>Index / refresh</button><button type="button" disabled={desktopDisabled} onClick={() => void perform(() => api("DELETE", pathFor(`documents/${folder.id}`), undefined, { desktop: true }), "Folder permission and its index removed. Original documents were left in place.")}>Remove permission and index</button></div></article>)}
      <form onSubmit={event => { event.preventDefault(); void perform(async () => { const reply = await api<{ results: SearchResult[] }>("GET", pathFor(`documents/search?q=${encodeURIComponent(query)}`)); setResults(reply.results); }); }}><label>Search selected documents<input value={query} onChange={event => setQuery(event.target.value)} maxLength={500} required/></label><button type="submit" disabled={disabled}>Search</button></form>
      {results.map((result, index) => <article className="platform-card" key={`${result.rootId}-${result.path}-${result.page}-${index}`}><strong>{result.folder} / {result.path}{result.page ? ` · page ${result.page}` : " · text excerpt"}</strong><p>{result.excerpt}</p><button type="button" disabled={desktopDisabled} onClick={() => void perform(() => api("POST", pathFor("documents/open"), { rootId: result.rootId, path: result.path }, { desktop: true }))}>Open source document</button></article>)}
    </>}
    {tab === "Approvals" && <>
      <p>Choose automatic behavior separately for verified PC voice and chat. Other actions keep review; forgetting a memory always requires it. Local launches also require a registered target and desktop/owner authority.</p>
      <div className="platform-policy"><span>Action</span><strong>Verified voice</strong><strong>Chat</strong>{ACTION_KINDS.map(kind => <div className="platform-policy__row" key={kind}><span>{kind.replace(".", " · ")}</span>{(["voiceAutomatic", "chatAutomatic"] as const).map(channel => <label className="platform-check" key={channel}><input type="checkbox" checked={policy[channel].includes(kind)} onChange={event => setPolicy(values => ({ ...values, [channel]: event.target.checked ? [...values[channel], kind] : values[channel].filter(item => item !== kind) }))} disabled={desktopDisabled}/>Automatic</label>)}</div>)}</div>
      <button type="button" disabled={desktopDisabled} onClick={() => void perform(() => api("PUT", pathFor("approvals"), policy, { desktop: true }), "Approval preferences saved. They take effect on new requests.")}>Save approval choices</button>
      <h3>Action history</h3><small>Undo supports unchanged local task creation/edits, local events without connected Google writes, and newly saved memories. Memory corrections keep no extra copy of old fact values.</small>
      {receipts.map(receipt => <article className="platform-card" key={receipt.id}><strong>{receipt.label}</strong><small>{receipt.status} · {new Date(receipt.updatedAt).toLocaleString()}</small>{receipt.undoable && receipt.status === "completed" && <div className="platform-inline"><button type="button" disabled={desktopDisabled} onClick={() => { if (undoAsked !== receipt.id) { setUndoAsked(receipt.id); return; } setUndoAsked(null); void perform(() => api("POST", pathFor(`actions/${receipt.id}/undo`), undefined, { desktop: true }), "Supported action undone after checking for later edits."); }}>{undoAsked === receipt.id ? "Confirm Undo this action" : "Review Undo"}</button>{undoAsked === receipt.id && <button type="button" onClick={() => setUndoAsked(null)}>Keep it</button>}</div>}</article>)}
    </>}
    {tab === "Health" && <>
      <p>Voice-only startup uses your Windows-protected enrollment. Unlock the existing encrypted enrollment once to migrate it; later normal starts skip the passkey while voice requests still verify the enrolled speaker. Encrypted profile recovery keeps its separate backup passphrase.</p>
      <button type="button" disabled={desktopDisabled} onClick={() => void perform(() => openProfileTool("voice_only", "00000000000000000000000000000000"), "Opened one-time voice-only setup. Unlock the existing encrypted profile in that local console; your passkey is never stored.")}>Set up voice-only startup</button>
      {health?.components.map(component => <article className="platform-card" key={component.id}><div className="platform-card__head"><strong>{component.id}</strong><span>{component.state}</span></div><p>{component.detail}</p></article>)}
      <div className="platform-inline"><button type="button" disabled={desktopDisabled} onClick={() => void perform(() => api("POST", pathFor("health/recover"), { action: "warm_model" }, { desktop: true }), "Local model warm-up completed.")}>Warm local model</button><button type="button" disabled={desktopDisabled} onClick={() => void perform(startVoiceService, "Voice console opened. After voice-only setup, startup needs no passkey.")}>Start verified voice</button><button type="button" disabled={desktopDisabled} onClick={() => void perform(restartServer, "Requested the existing local API restart.")}>Restart API</button></div>
      <label className="platform-check"><input type="checkbox" checked={autoRecovery} disabled={!DESKTOP_APPROVER} onChange={event => { const value = event.target.checked; setAutoRecovery(value); localStorage.setItem("zaenia.autoRecovery", value ? "1" : "0"); window.dispatchEvent(new Event("zae:recovery-settings")); }}/>Automatically recover the API after repeated connection failures, only when its last known mode was token mode</label>
      <button type="button" disabled={desktopDisabled} onClick={() => void perform(async () => setSnapshot(await api("POST", pathFor("snapshots"), undefined, { desktop: true })), "Private source rollback snapshot verified and saved.")}>Create pre-update source snapshot</button>
      {snapshot && <article className="platform-card"><strong>Snapshot {snapshot.id.slice(0, 8)}</strong><small>{snapshot.files} source/config files · {Math.round(snapshot.bytes / 1024)} KiB. Personal data and executables excluded.</small><button type="button" disabled={desktopDisabled} onClick={() => void perform(() => openProfileTool("rollback", snapshot.id), "Owner rollback console opened; it shows the exact source restore and requires confirmation.")}>Review rollback in owner console</button></article>}
    </>}
    {tab === "Portable" && <>
      <p>Carry encrypted preferences, personal memories, inferred insights, projects, and layouts. Machine credentials, enrollment, app grants and document-folder access stay on their original PC.</p>
      <form onSubmit={event => { event.preventDefault(); void perform(async () => { const request = await api<{ id: string }>("POST", pathFor("profile/requests"), { mode: profileMode, path: profilePath, restoreMode, uiSettings: profileMode === "export" ? displayPreferences(localStorage) : {} }, { desktop: true }); await openProfileTool(profileMode, request.id); }, "Prepared the exact profile operation and opened its local owner console. Enter the passkey there; secrets never enter this page."); }}><label>Operation<select value={profileMode} onChange={event => setProfileMode(event.target.value as "export" | "restore")}><option value="export">Encrypted export</option><option value="restore">Restore encrypted profile</option></select></label><label>Local .zae-profile path<input value={profilePath} onChange={event => setProfilePath(event.target.value)} required maxLength={1000} placeholder="D:\ZAE\profile.zae-profile"/></label>{profileMode === "restore" && <label>Existing information<select value={restoreMode} onChange={event => setRestoreMode(event.target.value)}><option value="merge">Keep existing items when keys/IDs conflict</option><option value="overwrite_conflicts">Replace conflicting items after owner review</option></select></label>}<button type="submit" disabled={desktopDisabled}>Prepare and open owner console</button></form>
      {profileRequests.slice(0, 5).map(request => <article className="platform-card" key={request.id}><strong>{request.mode} · {request.status}</strong><small>{request.path}</small></article>)}
      <h3>SSD readiness</h3>{readiness && <><p>{readiness.scope}</p><ul>{readiness.checks.map(check => <li key={check.id}><strong>{check.ok ? "Ready" : "Needs attention"}</strong> · {check.detail}</li>)}</ul><h4>Hardware/destination acceptance still required</h4><ul>{readiness.manualChecks.map(check => <li key={check}>{check}</li>)}</ul></>}
    </>}
    {tab === "Hands" && <>
      <p>Hands-only tracking runs in a local worker so camera processing does not block the interface. Camera frames stay in memory and are discarded.</p>
      <button type="button" aria-pressed={hands} disabled={!handsSupported} onClick={toggleHands}>{hands ? "Turn camera hand controls off" : "Enable local hand controls"}</button>
      {handNote && <p className="platform-note" role="status">{handNote}</p>}
      <ul><li>Point with the index finger and hold briefly to focus a window.</li><li>Pinch thumb and index finger to drag the focused window.</li><li>Extend index and middle fingers, then spread them to resize.</li><li>Move a closed hand left/right to switch windows, or down to minimize.</li><li>Hold an open palm briefly to stop the current reply.</li></ul><small>Turns off when the app is hidden. No face detection, facial interpretation, recordings, or cloud camera calls. Mouse/keyboard controls remain available.</small>
    </>}
  </section>;
}
