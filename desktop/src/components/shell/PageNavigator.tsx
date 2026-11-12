import { DockSlot } from "../core/DockCore";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { readPageActivities, type PageActivity } from "../../core/pageActivity";
import { CATEGORY_META, PAGE_CATALOG, SCREEN_DESC, catalogNode, categoryForRoute, moduleMeta, navigatorFor } from "../../core/pageCatalog";
import { routeForActivity } from "../../core/voiceUi";
import { usePaneNav, type PaneNavApi } from "./PaneNav";
import { Accordion, BentoGrid, Ico, PageSearch, RecentCard, openCategory, openRoute, type Mini, type Tile } from "./Bento";
import { recordMinis } from "./records";
import "./PageNavigator.css";

/*
 * Every page in ZAE, drawn exactly as Grey's previews (Claude, 2026-11-11):
 *  - desktop = preview 05 "Module bento": (top row from PaneNav) · breadcrumb · 28px title · sibling pills ·
 *    bento of the level's children (home) or the recent-work card + the real screen (leaf);
 *  - phone = preview M5 "Voice-first accordion": header (Back, breadcrumb, 20px title) · say-or-type bar ·
 *    sibling dropdown · recent-work card · accordions (home) or the real screen (leaf).
 * A level with children opens on its "home" (the bento). Every change, including home, is a Back step.
 */
const PHONE = "(max-width: 760px)";
export function usePhone() {
  const [phone, setPhone] = useState(() => typeof window !== "undefined" && window.matchMedia(PHONE).matches);
  useEffect(() => { const media = window.matchMedia(PHONE); const change = () => setPhone(media.matches); media.addEventListener("change", change); return () => media.removeEventListener("change", change); }, []);
  return phone;
}
export const HOME = "home-view";
const TOP_NAVIGATORS = new Set(["life", "notes", "workbench", "music", "research", "codedoctor", "arena", "assistant", "settings", "status", "security"]);
const pendingHome = new Set<string>();
/** Show a level's home (its bento) — now if it is on screen, or as soon as it mounts. */
export function requestHome(navigator: string | null, pane?: string) {
  if (!navigator) return;
  pendingHome.add(navigator);
  window.dispatchEvent(new CustomEvent("zae:page-tab", { detail: { page: navigator, tab: HOME, pane } }));
}
const readHome = (id: string): boolean | null => { try { const value = sessionStorage.getItem(`zaenia.pageHome.${id}`); return value === null ? null : value === "1"; } catch { return null; } };
const saveHome = (id: string, home: boolean) => { try { sessionStorage.setItem(`zaenia.pageHome.${id}`, home ? "1" : "0"); } catch { /* optional */ } };

/** Which catalogue app a page navigator belongs to. */
export function appOfNavigator(id: string): string {
  if (["life", "plan", "fitness", "fitness-food", "fitness-training", "godspeed"].includes(id)) return "tasks";
  if (id === "settings") return "system";
  if (id === "assistant-tools") return "assistant";
  if (id === "scripture") return "research";
  if (id === "enthon" || id === "files-view") return "codedoctor";
  if (id === "song-text") return "music";
  return id;
}
const appLabel = (app: string) => PAGE_CATALOG.find(item => item.id === app)?.label ?? app;
/** Catalogue route of a navigator's page (null when the catalogue doesn't list it). */
const routeOf = (navigator: string, page: string) => routeForActivity({ navigator, page } as PageActivity);

type Crumb = { label: string; go?: () => void };
/** Breadcrumb for this screen: Category › Module › ancestors (each opens that level's home) › here. */
function trail(pane: PaneNavApi | null, id: string, hereLabel: string, home: boolean): { crumbs: Crumb[]; category: string; app: string } {
  const chain = pane?.chain ?? [];
  const index = chain.findIndex(item => item.id === id);
  const upto = index < 0 ? chain : chain.slice(0, index);
  const app = appOfNavigator(chain[0]?.id ?? id);
  const category = categoryForRoute(app);
  const crumbs: Crumb[] = [{ label: CATEGORY_META[category]?.name ?? "Life", go: () => openCategory(category) }];
  const topNav = chain[0]?.id ?? id;
  const atTopHome = home && index <= 0;
  // "Settings › Settings": a module named like its category shows once (Claude 2026-11-11).
  if (appLabel(app) !== crumbs[0].label) crumbs.push({ label: appLabel(app), go: atTopHome ? undefined : () => requestHome(topNav, pane?.paneId) });
  else if (!atTopHome) crumbs[0] = { label: crumbs[0].label, go: () => requestHome(topNav, pane?.paneId) };
  upto.forEach((entry, at) => {
    const next = chain[at + 1]; const isHere = home && at === upto.length - 1;
    crumbs.push({ label: entry.label, go: isHere ? undefined : () => next ? requestHome(next.id, pane?.paneId) : undefined });
  });
  if (!home) crumbs.push({ label: hereLabel });
  return { crumbs, category, app };
}
function Crumbs({ crumbs, phone }: { crumbs: Crumb[]; phone: boolean }) {
  if (phone) return <div className="bx-ph__cr page-nav__crumbs">{crumbs.map(crumb => crumb.label).slice(0, -1).join(" > ") || "Your workspace"}</div>;
  return <nav className="bx-crumbs page-nav__crumbs" aria-label="Breadcrumb">{crumbs.map((crumb, at) => <span key={`${crumb.label}-${at}`} style={{ display: "contents" }}>
    {at > 0 && <span className="sep" aria-hidden="true">›</span>}
    {at === crumbs.length - 1 ? <span className="here">{crumb.label}</span> : <button type="button" onClick={crumb.go}>{crumb.label}</button>}
  </span>)}</nav>;
}
/** "Recent work here" for a page, from the device-local activity log. Continue moves focus into the page's content. */
function Recent({ navigator, page, box, label }: { navigator: string; page: string; box: React.RefObject<HTMLElement | null>; label: string }) {
  const [tick, setTick] = useState(0);
  useEffect(() => { const update = () => setTick(value => value + 1); window.addEventListener("zae:page-activity-cleared", update); window.addEventListener("storage", update); return () => { window.removeEventListener("zae:page-activity-cleared", update); window.removeEventListener("storage", update); }; }, []);
  void tick;
  const recent = readPageActivities().find(item => item.navigator === navigator && item.page === page);
  const when = recent ? `${recent.action === "edited" ? "Edited" : "Used"} · ${new Date(recent.at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}` : "Nothing recorded on this page yet";
  return <RecentCard what={recent?.subject ?? label} when={when} onContinue={() => {
    let next = box.current?.nextElementSibling as HTMLElement | null;
    while (next && next.offsetParent === null) next = next.nextElementSibling as HTMLElement | null;
    const target = next?.querySelector<HTMLElement>("input:not([type=hidden]),textarea,select,button,[tabindex]");
    next?.scrollIntoView({ block: "start", behavior: "smooth" }); target?.focus({ preventScroll: true });
  }}/>;
}
/** Sibling switcher: pills, or a dropdown when narrow / on the phone. */
function Siblings({ items, current, pick, narrow, name }: { items: readonly { id: string; label: string }[]; current: string; pick: (id: string) => void; narrow: boolean; name: string }) {
  if (items.length < 2) return null;
  if (narrow) return <select className="bx-sibsel page-nav__picker" aria-label={`Other pages in ${name}`} value={current} onChange={event => pick(event.target.value)}>
    {items.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select>;
  return <div className="bx-sibs page-nav__siblings" role="tablist" aria-label={`Other pages in ${name}`}>
    {items.map(item => <button type="button" role="tab" key={item.id} aria-selected={item.id === current} aria-current={item.id === current ? "page" : undefined}
      className={`bx-sib${item.id === current ? " on" : ""}`} onClick={() => pick(item.id)}>{item.label}</button>)}</div>;
}
/** Phone M5 header: Back, breadcrumb line, 20px title. */
function PhoneHeader({ crumbs, title, onBack }: { crumbs: Crumb[]; title: string; onBack?: () => void }) {
  return <div className="bx-ph">
    <DockSlot/>
    {onBack && <button type="button" className="bx-bk" data-pane-back aria-label="Back" onClick={onBack}><Ico name="back"/></button>}
    <div className="bx-ph__tt"><Crumbs crumbs={crumbs} phone/><h2 className="bx-ph__t">{title}</h2></div>
  </div>;
}

/** The Back-step key for a record id (letters, digits, - and _ only). onOpen receives this key. */
export const detailKey = (id: string) => id.replace(/[^a-z0-9_-]/gi, "").slice(0, 60);

/**
 * A record (a note, recipe, project…) as its own leaf screen inside the current page. It registers like a
 * navigator ("list" / one key per record), so opening a record is a Back step; while open it draws the leaf
 * header (Back, breadcrumb, title, recent work). Closing returns to the list; unsaved drafts stay with the owner.
 */
export function DetailScreen({ id, name, open, title, onOpen, onClose, itemId, quiet = false }: {
  id: string; name: string; open: boolean; title: string; onOpen: (itemId?: string) => void; onClose: () => void;
  itemId?: string; quiet?: boolean;
}) {
  const pane = usePaneNav(); const phone = usePhone(); const box = useRef<HTMLElement>(null);
  const safeItem = itemId ? `i-${detailKey(itemId)}` : null;
  const page = open ? safeItem ?? "detail" : "list";
  const quietRef = useRef(quiet); quietRef.current = quiet;
  const handlers = useRef({ onOpen, onClose }); handlers.current = { onOpen, onClose };
  const previous = useRef<string | null>(null);
  const hasPane = !!pane;
  useLayoutEffect(() => pane?.register(id, { name, choose: next => next === "list" ? handlers.current.onClose() : handlers.current.onOpen(next.startsWith("i-") ? next.slice(2) : undefined) }),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [hasPane, id, name]);
  useLayoutEffect(() => { pane?.changed(id, quietRef.current ? null : previous.current, page); previous.current = page;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, page]);
  const { crumbs } = trail(pane, id, title, false);
  const back = () => { if (!pane?.back()) handlers.current.onClose(); };
  return <nav ref={box} className="page-nav page-nav--leaf page-nav--detail bx-page" hidden={!open} data-page-navigator={id} data-page-current={page} data-page-label={open ? title : name} data-page-name={name} aria-label={`${name} details`}>
    {phone ? <PhoneHeader crumbs={crumbs} title={title} onBack={back}/>
      : <div className="bx-lvl"><button type="button" className="bx-back page-nav__back" data-pane-back onClick={back} aria-label="Back"><Ico name="back"/>Back</button>
        <div className="bx-tt"><Crumbs crumbs={crumbs} phone={false}/><h2 className="bx-ttl">{title}</h2></div></div>}
    {open && <Recent navigator={id} page={page} box={box} label={title}/>}
  </nav>;
}

export function PageNavigator({ id, name, items, current, onChoose }: {
  id: string; name: string; items: readonly { id: string; label: string }[];
  current: string; onChoose: (id: string) => void;
}) {
  const pane = usePaneNav(); const phone = usePhone();
  const box = useRef<HTMLElement>(null);
  const [narrow, setNarrow] = useState(false);
  const [searching, setSearching] = useState(false);
  const deep = items.some(item => { const route = routeOf(id, item.id); return !!route && (catalogNode(route.app, route.path)?.children?.length ?? 0) > 0; }) || TOP_NAVIGATORS.has(id);
  const [home, setHomeState] = useState(() => { if (pendingHome.delete(id)) return true; const saved = readHome(id); return saved ?? (TOP_NAVIGATORS.has(id) && !!pane); });
  const setHome = (value: boolean) => { setHomeState(value); saveHome(id, value); };
  const selected = items.find(item => item.id === current) ?? items[0];
  const choose = useRef(onChoose); choose.current = onChoose;
  const previous = useRef<string | null>(null);
  useEffect(() => { window.dispatchEvent(new CustomEvent("zae:page-preview", { detail: { page: id, tab: selected?.id } })); }, [id, selected?.id]);
  const [, setMinisTick] = useState(0);
  useEffect(() => { const update = () => setMinisTick(value => value + 1); window.addEventListener("zae:record-minis", update); return () => window.removeEventListener("zae:record-minis", update); }, []);
  useEffect(() => {
    const jump = (event: Event) => { const detail = (event as CustomEvent<{ page?: string; tab?: string; pane?: string }>).detail; if (detail?.page !== id) return;
      if (detail.pane && pane && detail.pane !== pane.paneId) return;
      if (detail.tab === HOME) { pendingHome.delete(id); setHome(true); return; }
      if (items.some(item => item.id === detail.tab)) { setHome(false); choose.current(detail.tab!); } };
    window.addEventListener("zae:page-tab", jump); return () => window.removeEventListener("zae:page-tab", jump);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, items]);
  const known = useRef(items); known.current = items;
  const hasPane = !!pane;
  useLayoutEffect(() => pane?.register(id, { name, choose: page => { if (page === HOME) setHome(true); else if (known.current.some(item => item.id === page)) { setHome(false); choose.current(page); } } }),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [hasPane, id, name]);
  const showingHome = home && !!pane;
  const page = showingHome ? HOME : selected?.id;
  useLayoutEffect(() => { if (!page) return; pane?.changed(id, previous.current, page); previous.current = page;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, page]);
  useEffect(() => {
    const node = box.current; if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setNarrow(entry.contentRect.width < 560));
    observer.observe(node); return () => observer.disconnect();
  }, []);
  if (!selected) return null;
  const leaf = !pane || pane.leaf === null || pane.leaf === id;
  const pick = (next: string) => { if (items.some(item => item.id === next)) { setHome(false); choose.current(next); } };
  const attrs = { "data-page-navigator": id, "data-page-current": showingHome ? HOME : selected.id, "data-page-label": showingHome ? "" : selected.label, "data-page-name": name } as Record<string, string>;
  // Parent levels draw nothing; their child owns the screen.
  if (!leaf) return <nav ref={box} className="page-nav page-nav--parent" {...attrs} data-home={showingHome ? "1" : undefined} data-page-items={items.map(item => `${item.id}:${item.label}`).join("|")} aria-hidden="true"/>;

  const app = appOfNavigator(pane?.chain[0]?.id ?? id);
  const chain = pane?.chain ?? []; const at = chain.findIndex(item => item.id === id);
  const parent = at > 0 ? chain[at - 1] : null;
  const nodeRoute = parent ? routeOf(parent.id, chain[at - 1] ? (document.querySelector<HTMLElement>(`[data-page-navigator="${parent.id}"]`)?.dataset.pageCurrent ?? "") : "") : null;
  const basePath = nodeRoute?.path ?? [];
  const homeTitle = parent ? parent.label : appLabel(app);
  const title = showingHome ? homeTitle : selected.label;
  const { crumbs, category } = trail(pane, id, selected.label, showingHome);
  const meta = moduleMeta(app, basePath.length ? basePath.slice(0, 1) : []);
  const back = () => { if (!pane?.back()) { if (!showingHome && deep) setHome(true); else openCategory(category); } };
  // Siblings: on a home page, the level's own siblings (other modules, or the parent's pages); on a leaf, this level's pages.
  const homeSiblings = (() => {
    if (parent) { const node = document.querySelector<HTMLElement>(`[data-page-navigator="${parent.id}"]`);
      const parentItems = (node?.dataset.pageItems ?? "").split("|").filter(Boolean).map(entry => { const [key, ...rest] = entry.split(":"); return { id: key, label: rest.join(":") }; });
      return { items: parentItems, current: node?.dataset.pageCurrent ?? "", pick: (next: string) => { window.dispatchEvent(new CustomEvent("zae:page-tab", { detail: { page: parent.id, tab: next, pane: pane?.paneId } })); const route = routeOf(parent.id, next); requestHome(route ? navigatorFor(route.app, route.path) : null, pane?.paneId); } };
    }
    const modules = (Object.entries(CATEGORY_META).find(([key]) => key === category) ? CATEGORY_MODULE_LIST(category) : []);
    return { items: modules.map(module => ({ id: module.key, label: module.label })), current: modules.find(module => module.app === app)?.key ?? "", pick: (key: string) => { const module = modules.find(entry => entry.key === key); if (module) openRoute({ app: module.app, path: module.path, label: module.label }); } };
  })();
  const tiles: Tile[] = items.map(item => {
    const route = routeOf(id, item.id); const node = route ? catalogNode(route.app, route.path) : null;
    const children = node?.children ?? [];
    const records: Mini[] = route ? recordMinis(route.app, route.path) : [];
    const minis: Mini[] = [...children.map(child => ({ key: child.id, name: child.label, label: child.children?.length ? `${child.children.length} inside` : "Screen",
      route: { app: route!.app, path: [...route!.path, child.id], label: `${appLabel(route!.app)} / ${child.label}` },
      onOpen: () => openRoute({ app: route!.app, path: [...route!.path, child.id], label: `${appLabel(route!.app)} / ${child.label}` }, pane?.paneId) })), ...records];
    const childNav = route && children.length ? navigatorFor(route.app, route.path) : null;
    return { key: item.id, name: item.label, d: route ? SCREEN_DESC[[route.app, ...route.path].join("/")] ?? "" : "", icon: children.length || records.length ? "folder" : "page",
      accent: meta.accent, minis, span: items.length === 1 || children.length > 6 ? "wide" : "", route: route ?? undefined,
      onOpen: () => { setHome(false); choose.current(item.id); requestHome(childNav, pane?.paneId); } };
  });
  const cls = `page-nav page-nav--leaf bx-page${phone ? " bx-page--phone" : ""}`;
  const style = { "--a": meta.accent } as CSSProperties;
  const homeAttrs = { "data-home": showingHome ? "1" : undefined, "data-searching": searching ? "1" : undefined, "data-page-items": items.map(item => `${item.id}:${item.label}`).join("|") };
  let body: ReactNode;
  if (phone) {
    const sib = showingHome ? homeSiblings : { items, current: selected.id, pick };
    body = <>
      <PhoneHeader crumbs={crumbs} title={title} onBack={back}/>
      <div className="bx-pbody">
        <PageSearch phone onQuery={query => setSearching(!!query.trim())}/>
        {!searching && <>
          <Siblings items={sib.items} current={sib.current} pick={sib.pick} narrow name={title}/>
          <Recent navigator={id} page={showingHome ? HOME : selected.id} box={box} label={title}/>
          {showingHome && <Accordion tiles={tiles}/>}
        </>}
      </div>
    </>;
  } else if (showingHome) {
    body = <>
      <div className="bx-lvl"><div className="bx-tt"><Crumbs crumbs={crumbs} phone={false}/><h2 className="bx-ttl">{title}</h2></div></div>
      <Siblings items={homeSiblings.items} current={homeSiblings.current} pick={homeSiblings.pick} narrow={narrow && homeSiblings.items.length > 6} name={title}/>
      <BentoGrid tiles={tiles}/>
    </>;
  } else {
    body = <>
      <div className="bx-lvl"><button type="button" className="bx-back page-nav__back" data-pane-back onClick={back} aria-label="Back"><Ico name="back"/>Back</button>
        <div className="bx-tt"><Crumbs crumbs={crumbs} phone={false}/><h2 className="bx-ttl">{title}</h2></div></div>
      <Siblings items={items} current={selected.id} pick={pick} narrow={narrow} name={name}/>
      <Recent navigator={id} page={selected.id} box={box} label={title}/>
    </>;
  }
  return <nav ref={box} className={cls} style={style} {...attrs} {...homeAttrs} aria-label={`${title} page`}>{body}</nav>;
}

/** The modules of a category, as sibling entries. */
function CATEGORY_MODULE_LIST(category: string): { key: string; label: string; app: string; path: string[] }[] {
  const list = (CATEGORY_MODULES_REF[category] ?? []);
  return list.map(module => ({ key: [module.app, ...(module.path ?? [])].join("/"), label: module.label ?? appLabel(module.app), app: module.app, path: module.path ?? [] }));
}
import { CATEGORY_MODULES as CATEGORY_MODULES_REF } from "../../core/pageCatalog";
