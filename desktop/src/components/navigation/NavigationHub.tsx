import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { CATEGORIES } from "../../core/categories";
import { clearAppVisits, readAppVisits } from "../../core/navigationActivity";
import { CATEGORY_META, CATEGORY_MODULES, PAGE_CATALOG, catalogNode, lastAppView, moduleMeta, type PageSpec } from "../../core/pageCatalog";
import { Accordion, BentoGrid, CategoryChips, CategorySeg, PageSearch, RecentCard, type Tile } from "../shell/Bento";
import type { PageRoute } from "../../core/voiceUi";
import { useCategoryPanels } from "../overview/CategoryPanels";
import "../overview/OverviewFrame.css";
import "./NavigationHub.css";

type App = { id: string; label: string; icon: ReactNode };
type View = { kind: "orbit" } | { kind: "workspace"; id: string; fromCore: boolean };
const DESCRIPTIONS: Record<string, string> = {
  tasks: "Calendar, reminders, meals and your day", fitness: "Food log, recipes and training plans",
  notes: "Capture something to return to later", research: "Explore sources and your research library",
  assistant: "Memory, follow-through and connected tools", music: "Projects, releases and song statistics",
  workbench: "Ideas, sketches, blueprints and projects", codedoctor: "Inspect code and review proposed changes",
  arena: "Compare and evaluate your models", system: "Preferences, status, security and updates",
};
const ALIASES: Record<string, string> = { fitness: "tasks", news: "research", files: "codedoctor", status: "system", security: "system" };
const POSITIONS = [[19, 17], [81, 17], [10, 49], [90, 49], [19, 81], [81, 81]];

/** Shared navigation surface. Opening it never closes windows or executes an assistant action. */
export function NavigationHub({ apps, enabled, phone, motion, onOpen, onRoute, onViewChange, voice }: {
  apps: App[]; enabled: boolean; phone: boolean; motion: boolean; onOpen: (id: string) => void;
  /** Open one exact page (Claude 2026-11-11): bento screen tiles and search results. */
  onRoute?: (route: PageRoute) => void;
  onViewChange?: (view: "orbit" | "workspace" | null) => void;
  /** Phone mic (Grey's M5): starts the existing app voice input; nothing new is authorised here. */
  voice?: { available: boolean; start: () => void };
}) {
  const [view, setView] = useState<View | null>(null);
  const [visits, setVisits] = useState(readAppVisits);
  const [query, setQuery] = useState("");
  const workspaceData = useCategoryPanels(enabled && view?.kind === "workspace" ? view.id : null);
  const panel = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const searchBox = useRef<HTMLInputElement>(null);
  const lastCategory = useRef("plan");
  // Phone accordion (M5): one module open at a time; the first is open by default.

  const close = useCallback(() => { setView(null); setQuery(""); }, []);
  const show = useCallback((next: View) => {
    if (!panel.current) opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setQuery(""); setView(next);
  }, []);
  useEffect(() => {
    const workspace = (event: Event) => {
      const id = (event as CustomEvent<unknown>).detail;
      if (enabled && typeof id === "string" && CATEGORIES.some(category => category.id === id)) show({ kind: "workspace", id, fromCore: false });
    };
    const category = (event: Event) => {
      const index = (event as CustomEvent<unknown>).detail;
      if (enabled && typeof index === "number" && Number.isInteger(index) && CATEGORIES[index]) show({ kind: "workspace", id: CATEGORIES[index].id, fromCore: true });
    };
    const orbit = () => { if (enabled) show({ kind: "orbit" }); };
    const findKey = (event: KeyboardEvent) => {
      if (!enabled || phone || event.key.toLowerCase() !== "k" || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
      event.preventDefault(); show({ kind: "workspace", id: lastCategory.current, fromCore: false });
      window.setTimeout(() => document.querySelector<HTMLInputElement>(".navhub [data-page-search]")?.focus(), 80);
    };
    window.addEventListener("keydown", findKey);
    const changed = () => setVisits(readAppVisits());
    window.addEventListener("zae:workspace", workspace);
    window.addEventListener("zae:core-category", category);
    window.addEventListener("zae:core-apps", orbit);
    window.addEventListener("zae:navigation-dismiss", close);
    window.addEventListener("zae:app-visits", changed);
    window.addEventListener("storage", changed);
    return () => {
      window.removeEventListener("zae:workspace", workspace);
      window.removeEventListener("zae:core-category", category);
      window.removeEventListener("zae:core-apps", orbit);
      window.removeEventListener("keydown", findKey);
      window.removeEventListener("zae:navigation-dismiss", close);
      window.removeEventListener("zae:app-visits", changed);
      window.removeEventListener("storage", changed);
    };
  }, [enabled, phone, show, close]);
  useEffect(() => { if (!enabled) close(); }, [enabled, close]);
  const back = useCallback(() => {
    if (view?.kind === "workspace" && view.fromCore) { setQuery(""); setView({ kind: "orbit" }); }
    else close();
  }, [view, close]);
  useEffect(() => {
    if (!view) return;
    const dismiss = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); back(); } };
    window.addEventListener("keydown", dismiss);
    window.addEventListener("zae:navigation-back", back);
    if (document.activeElement !== searchBox.current) heading.current?.focus();
    if (view.kind === "workspace") lastCategory.current = view.id;
    return () => { window.removeEventListener("keydown", dismiss); window.removeEventListener("zae:navigation-back", back); };
  }, [view, back]);
  const open = !!view && enabled;
  useEffect(() => {
    if (!open) return;
    // Keep the real top navigation usable; block covered windows, chat and hand targets.
    const background = document.querySelector<HTMLElement>(".workspace");
    const app = document.querySelector<HTMLElement>(".zaenia-app");
    const previousInert = background?.inert ?? false;
    if (background) background.inert = true;
    return () => {
      if (background) background.inert = previousInert;
      if (app) delete app.dataset.navigation;
      if (opener.current?.isConnected && !opener.current.closest("[inert]")) opener.current.focus();
    };
  }, [open]);
  useEffect(() => {
    const app = document.querySelector<HTMLElement>(".zaenia-app");
    if (app) { if (open) app.dataset.navigation = view!.kind; else delete app.dataset.navigation; }
    onViewChange?.(open ? view!.kind : null);
    window.dispatchEvent(new CustomEvent("zae:navigation-view", { detail: open && view?.kind === "workspace" ? view.id : null }));
  }, [open, view, onViewChange]);
  if (!open || !view) return null;
  const category = view.kind === "workspace" ? CATEGORIES.find(item => item.id === view.id)! : null;
  const resolve = (id: string): App | undefined => id === "fitness"
    ? apps.some(app => app.id === "tasks") ? { id, label: "Fitness & Health", icon: <svg viewBox="0 0 32 32" aria-hidden="true">{CATEGORIES[1].icon}</svg> } : undefined
    : apps.find(app => app.id === id) ?? apps.find(app => app.id === ALIASES[id]);
  const recent = visits.map(visit => ({ ...visit, app: resolve(visit.id) })).filter(item => item.app);
  const categoryRecent = recent.filter(item => !category || category.tabs.includes(item.id) || category.tabs.includes(ALIASES[item.id]));
  const appButton = (app: App) => {
    const last = lastAppView(app.id);
    const visit = visits.find(item => item.id === app.id || ALIASES[item.id] === app.id);
    const related = workspaceData.panels?.filter(item => item.tab === app.id || ALIASES[item.tab] === app.id || ALIASES[app.id] === item.tab) ?? [];
    const context = related.find(item => item.items?.length);
    return <button type="button" key={app.id} className="navhub__app navhub__app--preview" onClick={() => { close(); onOpen(app.id); }}>
      <span className="navhub__preview-head"><span className="navhub__app-icon">{app.icon}</span><span><strong>{app.label}</strong><small>{DESCRIPTIONS[app.id] ?? "Open this app"}</small></span><span aria-hidden="true">↗</span></span>
      <span className="navhub__preview-view"><small>{last ? "Last view" : "Open app"}</small><b>{last ?? "Start here"}</b>
        {visit && <time dateTime={new Date(visit.at).toISOString()}>Opened {new Date(visit.at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time>}</span>
      <span className="navhub__preview-content"><small>{context?.title ?? "Recent context"}</small>
        {context?.items?.slice(0, 2).map((item, index) => <span key={index}><b>{item.primary}</b>{item.meta && <em>{item.meta}</em>}</span>)}
        {!context && <span>{workspaceData.panels === null && view.kind === "workspace" ? "Loading saved context…" : "No saved preview available yet."}</span>}</span>
      <span className="navhub__preview-resume">{last ? "Resume last view" : "Open app"} <i aria-hidden="true">→</i></span>
    </button>;
  };
  const go = (route: PageRoute) => { close(); if (onRoute) onRoute(route); else onOpen(route.app); };
  // Category page = Grey's preview 05 (desktop) / M5 (phone): top row or M5 header, title, then the modules.
  if (category) {
    const modules = CATEGORY_MODULES[category.id] ?? [];
    const tiles: Tile[] = modules.map(module => {
      const spec = PAGE_CATALOG.find(item => item.id === module.app);
      const node = module.path ? catalogNode(module.app, module.path) : null;
      const screens: PageSpec[] = (node ? node.children : spec?.pages) ?? [];
      const meta = moduleMeta(module.app, module.path ?? []);
      const name = module.label ?? spec?.label ?? module.app;
      return { key: [module.app, ...(module.path ?? [])].join("/"), name, d: meta.d, icon: meta.icon, accent: meta.accent,
        onOpen: () => go({ app: module.app, path: module.path ?? [], label: name }),
        minis: screens.map(page => ({ key: page.id, name: page.label, label: page.children?.length ? `${page.children.length} inside` : "Screen",
          onOpen: () => go({ app: module.app, path: [...(module.path ?? []), page.id], label: `${spec?.label ?? name} / ${page.label}` }) })),
        span: modules.length === 1 || screens.length > 6 ? "wide" : modules.length === 3 ? "third" : "" };
    });
    const accent = CATEGORY_META[category.id]?.accent ?? "#e0a353";
    const pickCategory = (id: string) => { setQuery(""); setView({ kind: "workspace", id, fromCore: view.kind === "workspace" && view.fromCore }); };
    if (phone) {
      const last = categoryRecent[0];
      return <div ref={panel} className="navhub navhub--workspace navhub--phone navhub--m5 bx-root" data-app-navigation="workspace" role="region" aria-label={`${category.name} workspace`} style={{ "--a": accent } as CSSProperties}>
        <div className="bx-ph"><div className="bx-ph__tt"><div className="bx-ph__cr">Your workspace</div><h2 ref={heading} tabIndex={-1} className="bx-ph__t">{CATEGORY_META[category.id]?.name ?? category.name}</h2></div></div>
        <div className="bx-pbody">
          <PageSearch phone voice={voice} onQuery={setQuery}/>
          {!query.trim() && <>
            <CategoryChips current={category.id} onPick={pickCategory}/>
            {last && <RecentCard label="Continue" action="Open" what={`${last.app!.label}${lastAppView(last.id) ? ` · ${lastAppView(last.id)}` : ""}`}
              when={`Opened ${new Date(last.at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`} onContinue={() => { close(); onOpen(last.id); }}/>}
            <Accordion key={category.id} tiles={tiles}/>
          </>}
        </div>
      </div>;
    }
    return <div ref={panel} className="navhub navhub--workspace navhub--p05 bx-root" data-app-navigation="workspace" role="region" aria-label={`${category.name} workspace`} style={{ "--a": accent } as CSSProperties}>
      <div className="bx-top"><CategorySeg current={category.id} onPick={pickCategory}/><PageSearch/></div>
      <div className="bx-lvl"><div className="bx-tt"><h2 ref={heading} tabIndex={-1} className="bx-ttl">{CATEGORY_META[category.id]?.name ?? category.name}</h2></div></div>
      <BentoGrid tiles={tiles}/>
    </div>;
  }
  return <div ref={panel} className={`navhub navhub--${view.kind}${phone ? " navhub--phone" : ""}`} data-app-navigation={view.kind}
    data-motion={motion ? "on" : "off"} role="region" aria-label="Core app launcher">
    <header className="navhub__head">
      <div><span className="navhub__eyebrow">ZÆNIA · choose your next move</span>
        <h2 ref={heading} tabIndex={-1}>Around the core</h2>
        <p>{phone ? "Choose a category or return to a recent app." : "Your apps, connected. Select a category to explore."}</p></div>
      <button type="button" className="navhub__close" onClick={back} aria-label="Close navigation">✕ Close</button>
    </header>
    <div className="navhub__orbit" aria-label="App categories">
      <div className="navhub__ring" aria-hidden="true"/>
      <div className="navhub__nucleus" aria-hidden="true"><span>CORE</span><small>Choose a direction</small></div>
      {CATEGORIES.map((item, index) => <button type="button" key={item.id} className="navhub__node"
        style={{ "--node-x": `${POSITIONS[index][0]}%`, "--node-y": `${POSITIONS[index][1]}%`, "--node-index": index } as CSSProperties}
        onClick={() => setView({ kind: "workspace", id: item.id, fromCore: true })}>
        <svg viewBox="0 0 32 32" aria-hidden="true">{item.icon}</svg><span><strong>{item.name}</strong><small>{item.description}</small></span><i aria-hidden="true">↗</i>
      </button>)}
    </div>
    <div className="navhub__search"><label htmlFor="navhub-search">Find an app</label><input id="navhub-search" type="search" value={query} maxLength={100}
      placeholder="Notes, Workbench, Fitness…" onChange={event => setQuery(event.target.value)}/></div>
    {query.trim() && <div className="navhub__apps navhub__results" aria-label="Matching apps">
      {[...apps, resolve("fitness")].filter((app): app is App => !!app).filter(app => `${app.label} ${DESCRIPTIONS[app.id] ?? ""}`.toLowerCase().includes(query.trim().toLowerCase())).map(appButton)}
      {![...apps, resolve("fitness")].some(app => app && `${app.label} ${DESCRIPTIONS[app.id] ?? ""}`.toLowerCase().includes(query.trim().toLowerCase())) && <p role="status">No matching apps.</p>}
    </div>}
    <section className="navhub__recent" aria-label="Recent app activity">
      <header><div><h3>Recent activity</h3><small>Apps opened on this device · no chat or document contents saved</small></div>
        {recent.length > 0 && <button type="button" onClick={clearAppVisits}>Clear history</button>}</header>
      {recent.length > 0 ? <div className="navhub__recent-apps">{recent.slice(0, 6).map(item =>
        <button type="button" key={item.id} onClick={() => { close(); onOpen(item.id); }}>{item.app!.icon}<span><b>{item.app!.label}</b><small>{new Date(item.at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</small></span><i aria-hidden="true">↗</i></button>
      )}</div> : <p>Apps you open will appear here. Your existing work stays in place.</p>}
    </section>
  </div>;
}
