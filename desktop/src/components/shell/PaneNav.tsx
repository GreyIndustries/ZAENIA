import { DockSlot } from "../core/DockCore";
import { routeForActivity, type PageRoute } from "../../core/voiceUi";
import type { PageActivity } from "../../core/pageActivity";
import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { CategorySeg, PageSearch, Ico, openCategory, openTab } from "./Bento";
import { useWindowControls } from "./windowControls";
import { categoryForRoute } from "../../core/pageCatalog";
import { breadcrumb, dropBack, emptyHistory, pushStep, readHistories, rememberScroll, takeBack, takeForward, writeHistories, type NavStep, type PaneHistory } from "../../core/paneNav";

/**
 * One navigation context per screen (Claude, 2026-11-11): each desktop pane and the phone screen.
 * PageNavigators register here; changes become Back/Forward steps; scroll is remembered per location;
 * the deepest visible navigator renders the breadcrumb, title and sibling switcher.
 */
type Entry = { id: string; name: string; label: string };
type Registered = { name: string; choose: (page: string) => void };
export type PaneNavApi = {
  paneId: string; app: string; leaf: string | null; chain: Entry[]; canBack: boolean; canForward: boolean;
  register: (navigator: string, entry: Registered) => () => void;
  changed: (navigator: string, from: string | null, to: string) => void;
  back: () => boolean; forward: () => boolean;
};
const PaneNavContext = createContext<PaneNavApi | null>(null);
export const usePaneNav = () => useContext(PaneNavContext);

const session = { get: (key: string) => { try { return sessionStorage.getItem(key); } catch { return null; } }, set: (key: string, value: string) => { try { sessionStorage.setItem(key, value); } catch { /* optional */ } } };
let histories: Record<string, PaneHistory> = readHistories(session.get);
const registry = new Map<string, PaneNavApi>();
let appStepHandler: ((app: string) => void) | null = null;
let applyingApp: string | null = null;

/** App-level (phone) screens: record an app change as a step on that screen. */
export function recordAppStep(paneId: string, from: string, to: string) {
  if (applyingApp === to) { applyingApp = null; return; }
  histories = { ...histories, [paneId]: pushStep(histories[paneId] ?? emptyHistory(), { kind: "app", from, to }) };
  writeHistories(histories, session.set); window.dispatchEvent(new CustomEvent("zae:pane-history", { detail: paneId }));
}
export function setAppStepHandler(handler: ((app: string) => void) | null) { appStepHandler = handler; }
export function paneBack(paneId: string): boolean { return registry.get(paneId)?.back() ?? false; }
export function paneForward(paneId: string): boolean { return registry.get(paneId)?.forward() ?? false; }
export function paneHistory(paneId: string): PaneHistory { return histories[paneId] ?? emptyHistory(); }
export function forgetPane(paneId: string) { const { [paneId]: _gone, ...rest } = histories; histories = rest; writeHistories(histories, session.set); }

function scrollParent(node: HTMLElement | null): HTMLElement {
  for (let item = node?.parentElement ?? null; item; item = item.parentElement) {
    const style = getComputedStyle(item);
    if (/(auto|scroll)/.test(style.overflowY) && item.scrollHeight > item.clientHeight) return item;
    if (item.classList.contains("os-window__body")) return item;
  }
  return (document.scrollingElement as HTMLElement) ?? document.documentElement;
}
const shown = (node: HTMLElement) => !node.closest("[hidden],[inert]") && node.getClientRects().length > 0;

export function PaneNavProvider({ paneId, app, appId, children }: { paneId: string; app: string; appId?: string; children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const navigators = useRef(new Map<string, Registered>());
  const applying = useRef<{ navigator: string; page: string } | null>(null);
  const scrolls = useRef(new Map<string, number>());
  const location = useRef("");
  const scroller = useRef<HTMLElement | null>(null);
  const ignoreScrollUntil = useRef(0);
  const [view, setView] = useState<{ chain: Entry[]; leaf: string | null }>({ chain: [], leaf: null });
  const [version, setVersion] = useState(0);
  const history = histories[paneId] ?? emptyHistory();

  const onScroll = useCallback(() => {
    if (performance.now() < ignoreScrollUntil.current || !scroller.current) return;
    rememberScroll(scrolls.current, location.current, scroller.current.scrollTop);
  }, []);
  /** Recompute the visible navigator chain, then restore that location's scroll before paint. */
  const refresh = useCallback(() => {
    const scope = root.current; if (!scope) return;
    const visible = [...scope.querySelectorAll<HTMLElement>("[data-page-navigator]")].filter(shown);
    const chain = visible.map(node => ({ id: node.dataset.pageNavigator!, name: node.dataset.pageName ?? "", label: node.dataset.pageLabel ?? "" }));
    const leaf = chain[chain.length - 1]?.id ?? null;
    setView(current => {
      if (current.leaf === leaf && current.chain.map(item => `${item.id}:${item.label}`).join() === chain.map(item => `${item.id}:${item.label}`).join()) return current;
      window.setTimeout(() => window.dispatchEvent(new CustomEvent("zae:pane-location", { detail: paneId })), 0);
      return { chain, leaf };
    });
    const key = visible.map(node => `${node.dataset.pageNavigator}=${node.dataset.pageCurrent}`).join("/");
    const next = scrollParent(visible[0] ?? scope.firstElementChild as HTMLElement | null);
    if (next !== scroller.current) { scroller.current?.removeEventListener("scroll", onScroll); scroller.current = next; next.addEventListener("scroll", onScroll, { passive: true }); }
    if (key && key !== location.current) {
      if (location.current) rememberScroll(scrolls.current, location.current, next.scrollTop);
      location.current = key; ignoreScrollUntil.current = performance.now() + 150;
      next.scrollTop = scrolls.current.get(key) ?? 0;
    }
  }, [onScroll]);
  useLayoutEffect(() => () => scroller.current?.removeEventListener("scroll", onScroll), [onScroll]);
  useLayoutEffect(() => {
    const update = (event: Event) => { if ((event as CustomEvent<string>).detail === paneId) setVersion(value => value + 1); };
    window.addEventListener("zae:pane-history", update); return () => window.removeEventListener("zae:pane-history", update);
  }, [paneId]);

  const save = (next: PaneHistory) => { histories = { ...histories, [paneId]: next }; writeHistories(histories, session.set); setVersion(value => value + 1); };
  const replay = (step: NavStep, page: "from" | "to"): boolean => {
    if (step.kind === "app") { if (!appStepHandler) return false; applyingApp = step[page]; appStepHandler(step[page]); return true; }
    const target = navigators.current.get(step.navigator);
    if (!target) return false;
    applying.current = { navigator: step.navigator, page: step[page] }; target.choose(step[page]); return true;
  };
  const api = useMemo<PaneNavApi>(() => ({
    paneId, app, leaf: view.leaf, chain: view.chain, canBack: history.back.length > 0, canForward: history.forward.length > 0,
    register: (navigator, entry) => { navigators.current.set(navigator, entry); queueMicrotask(refresh); return () => { if (navigators.current.get(navigator) === entry) navigators.current.delete(navigator); queueMicrotask(refresh); }; },
    changed: (navigator, from, to) => {
      const expected = applying.current;
      if (expected && expected.navigator === navigator && expected.page === to) applying.current = null;
      else if (from && from !== to) save(pushStep(histories[paneId] ?? emptyHistory(), { kind: "page", navigator, from, to }));
      refresh();
    },
    back: () => {
      for (let tries = 0; tries < 10; tries++) {
        const taken = takeBack(histories[paneId] ?? emptyHistory()); if (!taken) return false;
        if (replay(taken.step, "from")) { save(taken.history); return true; }
        save(dropBack(histories[paneId] ?? emptyHistory()));
      }
      return false;
    },
    forward: () => {
      const taken = takeForward(histories[paneId] ?? emptyHistory()); if (!taken) return false;
      if (!replay(taken.step, "to")) { save({ ...taken.history, back: taken.history.back.slice(0, -1) }); return false; }
      save(taken.history); return true;
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [paneId, app, view, version, refresh]);
  useLayoutEffect(() => { registry.set(paneId, api); return () => { if (registry.get(paneId) === api) registry.delete(paneId); }; }, [paneId, api]);
  return <PaneNavContext.Provider value={api}><div ref={root} className="pane-nav-root bx-root" data-pane-root={paneId}>
    {paneId !== "phone" && <PaneTopRow appId={appId ?? paneId} api={api}/>}
    {children}</div></PaneNavContext.Provider>;
}

/** Breadcrumb trail for the deepest navigator in this screen. */
export function crumbsFor(api: PaneNavApi | null, navigator: string, fallbackApp: string): string[] {
  if (!api) return [fallbackApp];
  const index = api.chain.findIndex(item => item.id === navigator);
  return breadcrumb(api.app || fallbackApp, api.chain.slice(0, Math.max(0, index)));
}

/** Preview 05 top row for a pane: categories (no icons) · page search · Back · this window's controls. */
function PaneTopRow({ appId, api }: { appId: string; api: PaneNavApi }) {
  const controls = useWindowControls();
  const category = categoryForRoute(appId);
  const [focusKey, setFocusKey] = useState(0);
  useLayoutEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "k" || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
      const mine = document.querySelector(`.os-window--active [data-pane-root="${api.paneId}"]`);
      if (!mine) return;
      event.preventDefault(); event.stopImmediatePropagation(); setFocusKey(value => value + 1);
    };
    window.addEventListener("keydown", key, true); return () => window.removeEventListener("keydown", key, true);
  }, [api.paneId]);
  return <div className="bx-top pane-top">
    <DockSlot/>
    <CategorySeg current={category}/>
    <PageSearch focusKey={focusKey}/>
    <button type="button" className="bx-back" data-pane-back aria-label="Back" onClick={() => { if (!api.back()) openCategory(category); }}><Ico name="back"/>Back</button>
    <button type="button" className="bx-newtab" data-open-new-tab aria-label="Open this page in a new tab" title="Open in new tab (Ctrl+click or middle-click any tile also works)" onClick={() => openTab(hereRoute(api.paneId, appId))}>⧉</button>
    {controls && <div className="bx-ctl">{controls}</div>}
  </div>;
}

/** The page this pane shows, as a route (for "Open in new tab"). */
function hereRoute(paneId: string, appId: string): PageRoute {
  const root = document.querySelector(`[data-pane-root="${paneId}"]`);
  const navs = [...(root?.querySelectorAll<HTMLElement>("[data-page-navigator]") ?? [])].filter(node => node.offsetParent !== null || node.dataset.pageItems);
  for (const node of navs.reverse()) {
    const route = routeForActivity({ navigator: node.dataset.pageNavigator, page: node.dataset.pageCurrent } as PageActivity);
    if (route) return route;
  }
  return { app: appId, path: [], label: appId };
}
/** A pane's current location as labels (module page names → current page), for tab titles. */
export function paneLocation(paneId: string): string[] { return (registry.get(paneId)?.chain ?? []).map(entry => entry.label).filter(Boolean); }
