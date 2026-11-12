/** Display-only inventory. IDs match existing page handlers; this does not grant navigation or action permissions. */
export type PageSpec = { id: string; label: string; children?: PageSpec[] };
export type AppSpec = { id: string; label: string; pages: PageSpec[] };
const pages = (rows: [string, string][]): PageSpec[] => rows.map(([id, label]) => ({ id, label }));
export const PAGE_CATALOG: AppSpec[] = [
  { id: "overview", label: "Core", pages: pages([["dashboard","Dashboard"],["launcher","App launcher"],["recent","Recent activity"]]) },
  { id: "tasks", label: "LIFE", pages: [
    { id: "plan", label: "Schedule Board", children: pages([["week","Week"],["priorities","Priorities"],["day","Day"],["month","Month"],["reminders","Reminders"]]) },
    { id: "fitness", label: "Fitness & Health", children: [
      {id:"today",label:"Today"},
      {id:"training",label:"Training",children:pages([["program","Program"],["plans","Plans & targets"],["log","Food & exercise"]])},
      {id:"food",label:"Food",children:pages([["planner","Weekly meal planner"],["week","Made for this week"],["cookbook","Cookbook"],["scan","Scan food"]])},
    ] },
    { id:"mail",label:"Mail" },
    { id:"map",label:"GODSPEED",children:pages([["directions","Directions"],["traffic","Traffic"],["weather","Weather"],["air","Air"],["sea","Sea"]]) },
  ] },
  { id:"notes",label:"Notes",pages:pages([["board","Board"],["panes","Notebook"],["map","Map"],["editor","All notes"]]) },
  { id:"workbench",label:"Workbench",pages:pages([["lab","Project lab"],["blueprint","Blueprint"],["experiments","Experiments"],["projects","Projects"],["tools","Tools"],["labs","Labs"]]) },
  { id:"music",label:"Music",pages:pages([["dashboard","Dashboard"],["studio","Studio"],["song","Song"],["connections","Connections"]]) },
  { id:"research",label:"Research",pages:pages([["desk","Desk"],["workshop","Analysis workshop"],["reference","Learning explorer"],["cards","Study cards"],["reader","Reader"],["board","Evidence board"],["agent","Web agent"],["history","Historical Connections"],["notebook","Notebook"],["news","News"],["library","The Library"],["scripture","Scripture & ancient"],["translate","Translate"]]) },
  { id:"codedoctor",label:"Code Doctor & Files",pages:pages([["health","Health"],["queue","Review queue"],["side","Side by side"],["editor","Editor"],["plain","ENTHON"],["playground","Playground"],["doctor","Scanner"],["build","Build requests"],["suggestions","Suggestions"],["files","Files"],["source","Source"]]) },
  { id:"warroom",label:"War Room",pages:pages([["defense","Defense planning"],["business","Business plans"],["cameras","Cameras"]]) },
  { id:"arena",label:"LLM Training",pages:pages([["training","Training modules"],["learning","Learning health"],["duel","Response comparison"],["leaders","Leaderboard"],["bench","Test set"],["board","Rounds & SE model"],["brains","SE & tools"]]) },
  { id:"assistant",label:"Assistant",pages:[...pages([["front","Today"],["remembered","Everything remembered"],["memory","Memory & rules"]]),{id:"tools",label:"Assistant tools",children:pages([["work","Work"],["operate","Operate"],["apps","Apps"],["workspaces","Workspaces"],["projects","Projects"],["documents","Documents"],["approvals","Approvals"],["health","Health"],["portable","Portable"],["hands","Hands"]])}] },
  { id:"system",label:"Settings",pages:pages([["center","Control center"],["search","Search"],["look","Make ZAE yours"],["system","System & appearance"],["vault","Vault"],["notifications","Notifications"],["faceid","Phone Face ID"],["updates","Updates"],["about","About"]]) },
  { id:"status",label:"Status",pages:pages([["live","Live"],["automations","Automations"],["readiness","Readiness"],["uptime","Uptime"],["overview","Overview"],["protocols","Protocols"],["selfsustain","Self-Sustain"],["pc","This PC"]]) },
  { id:"remote",label:"PC remote",pages:pages([["desktop","Desktop controls"]]) },
  { id:"security",label:"Security",pages:pages([["shield","Shield"],["calm-password","Calm password"],["activity","Activity"],["plan","Plan"],["details","Details"]]) },
];
export function flattenPages(app: AppSpec) {
  const result: { id: string; label: string; path: string[] }[] = [];
  const visit = (items: PageSpec[], path: string[], labels: string[]) => {
    for (const item of items) {
      const next = [...path, item.id]; const names = [...labels, item.label];
      result.push({ id: next.join("/"), label: names.join(" / "), path: next });
      if (item.children) visit(item.children, next, names);
    }
  };
  visit(app.pages, [], []); return result;
}
const read = (key: string): string | null => { try { return localStorage.getItem(key); } catch { return null; } };
/** Read only allowlisted presentation keys; never inspect form drafts, credentials or chat storage. */
export function lastAppView(id: string, get: (key: string) => string | null = read): string | null {
  const canonical = id === "fitness" ? "tasks" : id;
  const app = PAGE_CATALOG.find(item => item.id === canonical);
  if (!app) return null;
  const known = (items: PageSpec[] | undefined, key: string) => items?.find(item => item.id === get(key));
  if (canonical === "tasks") {
    const section = id === "fitness" ? app.pages.find(item => item.id === "fitness") : known(app.pages,"zaenia.pageTab.life");
    if (!section) return null;
    const path = [section.label];
    if (section.id === "plan") { const child=known(section.children,"zaenia.plan.tab"); if(child) path.push(child.label); }
    if (section.id === "fitness") {
      const child=known(section.children,"zaenia.fitness.section");
      if(child){path.push(child.label);const leaf=known(child.children,`zaenia.fitness.${child.id}`);if(leaf)path.push(leaf.label);}
    }
    return path.join(" / ");
  }
  if (id === "system") {
    const group = get("zaenia.pageTab.settingshub");
    if (group === "status" || group === "security") {
      const nested = PAGE_CATALOG.find(item => item.id === group)!;
      return `${nested.label} / ${known(nested.pages,`zaenia.pageTab.${group}`)?.label ?? nested.pages[0].label}`;
    }
  }
  const key = id === "research" ? "zaenia.researchTab" : id === "music" ? "zaenia.music.tab" : `zaenia.pageTab.${id === "system" ? "settings" : id}`;
  return known(app.pages,key)?.label ?? null;
}

/** Category → modules, in the order the workspace shows them (module ids are catalogue/window ids). */
export const CATEGORY_MODULES: Record<string, { app: string; label?: string; path?: string[] }[]> = {
  plan: [{ app: "tasks" }, { app: "notes" }],
  warroom: [{ app: "warroom" }],
  know: [{ app: "research" }, { app: "assistant" }],
  create: [{ app: "music" }],
  build: [{ app: "workbench" }, { app: "codedoctor" }, { app: "arena" }],
  system: [{ app: "system" }, { app: "status" }, { app: "security" }],
};
/** The catalogue node at a path inside an app (null for the app itself or an unknown path). */
export function catalogNode(app: string, path: string[]): PageSpec | null {
  let items = PAGE_CATALOG.find(item => item.id === app)?.pages; let found: PageSpec | null = null;
  for (const id of path) { found = items?.find(item => item.id === id) ?? null; if (!found) return null; items = found.children; }
  return found;
}
/** Count every screen below a node (children, grandchildren…). */
export function screensInside(spec: { children?: PageSpec[]; pages?: PageSpec[] }): number {
  const list = spec.children ?? spec.pages ?? [];
  return list.reduce((sum, item) => sum + 1 + screensInside(item), 0);
}

/* ---- Preview 05 / M1 metadata (Claude 2026-11-11): what each tile says, its colour and icon. Display only. ---- */
export const CATEGORY_META: Record<string, { name: string; accent: string; icon: string; d: string }> = {
  plan: { name: "Life", accent: "#e0a353", icon: "cal", d: "Schedule, fitness & health, mail and notes" },
  warroom: { name: "War Room", accent: "#ff7a7a", icon: "shield", d: "Defense, cameras and business planning" },
  know: { name: "Know", accent: "#4fd1c5", icon: "book", d: "Research and your assistant" },
  create: { name: "Create", accent: "#7aa8ff", icon: "music", d: "Music production" },
  build: { name: "Build", accent: "#8fd16a", icon: "code", d: "Workbench, code and model teaching" },
  system: { name: "Settings", accent: "#9fb6cf", icon: "gear", d: "Settings, status and security" },
};
export const MODULE_META: Record<string, { accent: string; icon: string; d: string }> = {
  tasks: { accent: "#5fd39a", icon: "cal", d: "Calendar, reminders, meals and your day" },
  "tasks/fitness": { accent: "#ff9e6b", icon: "heart", d: "Workouts, training plans and food" },
  notes: { accent: "#a68bff", icon: "note", d: "Capture something to return to later" },
  research: { accent: "#4fd1c5", icon: "book", d: "Sources, reading and evidence" },
  assistant: { accent: "#f07fb8", icon: "spark", d: "Memory and tools" },
  music: { accent: "#7aa8ff", icon: "music", d: "Studio, songs and tracks" },
  workbench: { accent: "#ffb454", icon: "tool", d: "Projects, experiments and tools" },
  codedoctor: { accent: "#8fd16a", icon: "code", d: "Review, fix and browse code" },
  arena: { accent: "#e6c35c", icon: "brain", d: "Teach protocols, actions and responses" },
  warroom: { accent: "#ff7a7a", icon: "shield", d: "Defense, cameras and extensive business plans" },
  system: { accent: "#9fb6cf", icon: "gear", d: "Make ZAE yours" },
  status: { accent: "#5fd39a", icon: "pulse", d: "Live system status" },
  security: { accent: "#ff9e6b", icon: "shield", d: "Shield and protection" },
};
/** One-line descriptions for screens, keyed "app/path". Missing ones show no description. */
export const SCREEN_DESC: Record<string, string> = {
  "tasks/plan": "Schedule Board: your week and day", "tasks/mail": "Inbox and threads", "arena/training": "Model-specific teaching examples and practice", "arena/learning": "Learning settings and reviewed insights", "warroom/defense": "Defensive security plans", "warroom/business": "Detailed business plans", "warroom/cameras": "Your registered camera viewers", "research/workshop": "Evidence-based analysis", "research/reference": "Offline reference explorer", "research/cards": "Saved study cards", "tasks/plan/week": "Seven-day board", "tasks/plan/priorities": "What matters most", "tasks/plan/day": "Hour-by-hour", "tasks/plan/month": "Month calendar", "tasks/plan/reminders": "All reminders",
  "tasks/fitness": "Workouts, training plans and food", "tasks/fitness/today": "Today's workout, meals and targets", "tasks/fitness/training": "Program and plans",
  "tasks/fitness/training/program": "Your current training program", "tasks/fitness/training/plans": "Training plans and goals", "tasks/fitness/training/log": "Logged meals and sessions",
  "tasks/fitness/food": "Meals, recipes and scanning", "tasks/fitness/food/planner": "Plan the week's meals", "tasks/fitness/food/week": "Recipes picked for this week", "tasks/fitness/food/cookbook": "Saved recipes", "tasks/fitness/food/scan": "Barcode and label scanning",
  "tasks/map": "Live map", "tasks/map/traffic": "Live traffic", "tasks/map/directions": "Routes and active trip", "tasks/map/weather": "Radar", "tasks/map/air": "Aircraft overhead", "tasks/map/sea": "Ships nearby",
  "notes/board": "Pinned and recent notes", "notes/panes": "Three-pane notebook", "notes/map": "Links between notes", "notes/editor": "Every note",
  "research/desk": "Question and chosen sources", "research/reader": "Reading view", "research/board": "Claims and evidence", "research/agent": "Web research runs", "research/history": "Linked terms in history", "research/notebook": "Topics and sources", "research/news": "Articles and news rail", "research/library": "Your books", "research/scripture": "Passages and ancient texts", "research/translate": "Translation",
  "assistant/front": "The ZAE Daily", "assistant/mail": "Inbox and threads", "assistant/remembered": "All memories", "assistant/memory": "What ZAE keeps", "assistant/tools": "Ten tool pages",
  "music/dashboard": "Overview", "music/studio": "Tracks", "music/song": "Song editor", "music/connections": "Links and services",
  "workbench/lab": "Project gallery", "workbench/blueprint": "Plans and drawings", "workbench/experiments": "Running experiments", "workbench/projects": "All projects", "workbench/tools": "Stopwatch and timer", "workbench/labs": "Lab space",
  "codedoctor/health": "Project health at a glance",
  "codedoctor/queue": "Fixes waiting for review",
  "codedoctor/side": "Before and after, side by side",
  "codedoctor/editor": "Edit a file",
  "codedoctor/playground": "Try code safely",
  "codedoctor/doctor": "Scan for bugs",
  "codedoctor/build": "Ask ZAE to change her app",
  "codedoctor/suggestions": "Ideas ZAE has for you",
  "codedoctor/source": "ZAE's own code",
  "arena/duel": "Two models, one task",
  "arena/leaders": "Who's winning",
  "arena/bench": "Benchmark runs",
  "arena/board": "Scoreboard",
  "arena/brains": "The four brains",
  "assistant/tools/work": "Work in progress",
  "assistant/tools/operate": "Let ZAE operate apps",
  "assistant/tools/apps": "Apps she can use",
  "assistant/tools/workspaces": "Saved workspaces",
  "assistant/tools/projects": "Your projects",
  "assistant/tools/documents": "Documents",
  "assistant/tools/approvals": "Waiting for your OK",
  "assistant/tools/health": "Assistant health",
  "assistant/tools/portable": "Take ZAE with you",
  "assistant/tools/hands": "Hand controls",
  "system/center": "Everything at a glance",
  "system/search": "Find any setting",
  "system/look": "Colours, voice and style",
  "system/system": "Display and behaviour",
  "system/vault": "Passwords and secrets",
  "system/notifications": "What ZAE tells you",
  "system/faceid": "Face sign-in",
  "system/updates": "Install new versions",
  "system/about": "Version and credits",
  "status/live": "Live system status",
  "status/automations": "Running automations",
  "status/readiness": "Is everything ready",
  "status/uptime": "How long it's been up",
  "status/overview": "Status summary",
  "status/protocols": "Protocols",
  "status/selfsustain": "Self-sustain checks",
  "status/pc": "This PC",
  "remote/desktop": "Control your PC",
  "security/shield": "Protection on",
  "security/calm-password": "Calm dashboard password",
  "security/activity": "Recent security events",
  "security/plan": "Security plan",
  "security/details": "Full details",
};
export const moduleMeta = (app: string, path: string[] = []) => MODULE_META[[app, ...path].join("/")] ?? MODULE_META[app] ?? { accent: "#e0a353", icon: "page", d: "" };
/** The category a catalogue route lives in (fitness under Life by default). */
export function categoryForRoute(app: string): string {
  return Object.entries(CATEGORY_MODULES).find(([, modules]) => modules.some(module => module.app === app && !module.path))?.[0] ?? "plan";
}
/** The page navigator that lists the children of a catalogue node, when the app has one. */
export function navigatorFor(app: string, path: string[]): string | null {
  const key = [app, ...path].join("/");
  const map: Record<string, string> = {
    tasks: "life", "tasks/plan": "plan", "tasks/fitness": "fitness", "tasks/fitness/food": "fitness-food", "tasks/fitness/training": "fitness-training", "tasks/map": "godspeed",
    notes: "notes", workbench: "workbench", music: "music", research: "research", "research/scripture": "scripture", codedoctor: "codedoctor", "codedoctor/plain": "enthon", "codedoctor/files": "files-view",
    warroom: "warroom", arena: "arena", assistant: "assistant", "assistant/tools": "assistant-tools", system: "settings", status: "status", security: "security",
  };
  return map[key] ?? null;
}
