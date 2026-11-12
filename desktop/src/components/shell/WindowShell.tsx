import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { SnapLayouts } from "./SnapLayouts";
import { WindowControls } from "./windowControls";
import { isMaximized, resizeTiled, snapOrder, snapRectangles, type SnapCount } from "../../core/windowLayout";
import { boundedWindow, resizeWindow } from "../../core/windowLayout";
import type { ResizeEdge } from "../../core/windowLayout";
import type { Spot } from "../../core/layoutCommands";
import { LAYOUT_PHRASES } from "../../core/layoutPhrases";
import "./WindowShell.css";

/**
 * ZÆNIA shell: every workspace page is a window over the core, like a small
 * portable OS. Windows move, resize, minimise to the dock, and remember their
 * place. Positions are fractions of the stage so they survive window resizes.
 */
export type ShellWindow = { id: string; x: number; y: number; w: number; h: number; z: number; minimized: boolean; prev?: Rect; pinned?: boolean };
/** Screen tabs (Claude 2026-11-11): any page can open as its own tab; extra tabs of an app are "<app>~<n>". */
export const tabBase = (id: string) => id.split("~")[0];
type Rect = Pick<ShellWindow, "x" | "y" | "w" | "h">;

export const STORAGE_KEY = "zaenia.shellWindows";
const FULL_KEY = "zaenia.shellWindows.fullScreen";
const MIN_W = 0.26, MIN_H = 0.3;
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

function readSaved(): ShellWindow[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(saved)) return [];
    return saved.filter((item): item is ShellWindow => Boolean(item) && typeof item.id === "string"
      && ["x", "y", "w", "h", "z"].every(key => typeof item[key] === "number" && Number.isFinite(item[key])))
      .map(item => ({ ...item, ...boundedWindow(item), minimized: item.minimized === true,
        prev: item.prev && ["x", "y", "w", "h"].every(key => Number.isFinite((item.prev as Record<string, number>)[key])) ? boundedWindow(item.prev) : undefined }));
  } catch { return []; }
}

/** Grey (2026-11-09): tabs open using the full screen (still movable and resizable). */
function placement(_index: number): Rect {
  return { x: 0, y: 0, w: 1, h: 1 };
}

export function useWindowShell(known: readonly string[], aliases: Record<string, string> = {}) {
  const [windows, setWindows] = useState<ShellWindow[]>(() => {
    const saved = readSaved().filter(win => known.includes(tabBase(win.id)));
    try {
      if (localStorage.getItem(FULL_KEY) === "1") return saved;
      localStorage.setItem(FULL_KEY, "1");
    } catch { return saved; }
    return saved.map(win => ({ ...win, x: 0, y: 0, w: 1, h: 1 }));
  });
  const snapBefore = useRef<ShellWindow[] | null>(null);
  const [canUndoSnap, setCanUndoSnap] = useState(false);
  const zTop = useRef(windows.reduce((top, win) => Math.max(top, win.z), 10));
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(windows)); } catch { /* layout is a convenience */ }
  }, [windows]);
  const raise = () => ++zTop.current;
  const open = useCallback((id: string) => setWindows(current => {
    const existing = current.find(win => win.id === id);
    if (existing) return current.map(win => win.id === id ? { ...win, minimized: false, z: raise() } : win);
    return [...current, { id, ...placement(current.length), z: raise(), minimized: false }];
  }), []);
  const closed = useRef<{ id: string; at: number; win?: ShellWindow }[]>([]);
  const [closedCount, setClosedCount] = useState(0);
  const close = useCallback((id: string) => setWindows(current => {
    const gone = current.find(win => win.id === id); if (gone) { closed.current = [{ id, at: Date.now(), win: gone }, ...closed.current.filter(item => item.id !== id)].slice(0, 10); setClosedCount(closed.current.length); }
    return current.filter(win => win.id !== id);
  }), []);
  /** Open a new tab of an app (a second Build requests next to Suggestions, …). Returns its id. */
  const openTab = (base: string): string => {
    const id = `${base}~${Date.now().toString(36)}`;
    setTiled(false);
    setWindows(current => [...current, { id, ...placement(current.length), z: raise(), minimized: false }]);
    return id;
  };
  /** Reopen the most recently closed tab (or a named one). */
  const restoreClosed = (id?: string): string | null => {
    const item = id ? closed.current.find(entry => entry.id === id) : closed.current[0];
    if (!item) return null;
    closed.current = closed.current.filter(entry => entry.id !== item.id); setClosedCount(closed.current.length);
    const saved = item.win;
    if (saved) { setTiled(false); setWindows(current => current.some(win => win.id === saved.id) ? current : [...current, { ...saved, minimized: false, z: raise() }]); }
    else open(item.id);
    return item.id;
  };
  /** Tab order (the strip and the manager show this order); pinned tabs stay first. */
  const move = (id: string, step: number) => setWindows(current => {
    const index = current.findIndex(win => win.id === id); const next = index + step;
    if (index < 0 || next < 0 || next >= current.length) return current;
    const copy = [...current]; [copy[index], copy[next]] = [copy[next], copy[index]]; return copy;
  });
  const pin = (id: string) => setWindows(current => { const updated = current.map(win => win.id === id ? { ...win, pinned: !win.pinned } : win);
    return [...updated.filter(win => win.pinned), ...updated.filter(win => !win.pinned)]; });
  /** Put a tab into a pane of the current layout (swaps places with whatever is there). */
  const moveToPane = (id: string, pane: number) => setWindows(current => {
    const panes = current.filter(win => !win.minimized).sort((a, b) => Math.abs(a.y - b.y) > .05 ? a.y - b.y : a.x - b.x);
    const target = panes[pane]; const mover = current.find(win => win.id === id);
    if (!target || !mover || target.id === id) return current;
    return current.map(win => win.id === id ? { ...win, x: target.x, y: target.y, w: target.w, h: target.h, minimized: false, z: raise() }
      : win.id === target.id ? (mover.minimized ? { ...win, minimized: true } : { ...win, x: mover.x, y: mover.y, w: mover.w, h: mover.h }) : win);
  });
  const minimize = useCallback((id: string) => setWindows(current => current.map(win => win.id === id ? { ...win, minimized: true } : win)), []);
  const showDesktop = useCallback(() => setWindows(current => current.map(win => ({ ...win, minimized: true }))), []);
  const closeAll = useCallback(() => setWindows(current => current.filter(win => win.pinned)), []);
  const restoreAll = useCallback(() => setWindows(current => current.map(win => ({ ...win, minimized: false, z: raise() }))), []);
  const update = useCallback((id: string, rect: Partial<Rect>) => setWindows(current => current.map(win => win.id === id ? {
    ...win, ...boundedWindow({ ...win, ...rect }),
  } : win)), []);
  /** Put a window exactly here (opening and raising it). */
  const setRect = useCallback((id: string, rect: Rect) => setWindows(current => {
    const existing = current.find(win => win.id === id);
    if (!existing) return [...current, { id, ...boundedWindow(rect), z: raise(), minimized: false }];
    return current.map(win => win.id === id ? { ...win, ...boundedWindow(rect), minimized: false, z: raise() } : win);
  }), []);
  const visible = windows.filter(win=>!win.minimized);
  const snapped = visible.length>=2 && visible.length<=4 && snapRectangles(visible.length as SnapCount).every(rect=>visible.some(win=>Math.abs(win.x-rect.x)<.001&&Math.abs(win.y-rect.y)<.001&&Math.abs(win.w-rect.w)<.001&&Math.abs(win.h-rect.h)<.001));
  const active = windows.filter(win => !win.minimized).sort((a, b) => b.z - a.z)[0]?.id ?? null;
  const restore = useCallback((saved: ShellWindow[]) => {
    const checked = saved.filter(win => known.includes(tabBase(win.id)) && [win.x, win.y, win.w, win.h, win.z].every(Number.isFinite)).slice(0, 24).map((win, index) => {
      const w = clamp(win.w, MIN_W, .98), h = clamp(win.h, MIN_H, .96);
      return { ...win, x: clamp(win.x, 0, 1 - w), y: clamp(win.y, 0, 1 - h), w, h, z: index + 11, minimized: Boolean(win.minimized) };
    });
    zTop.current = checked.length + 12; setWindows(checked);
  }, [known]);
  /** Tiled = the panes came from a 2/3/4 arrangement; edge resizing then moves shared edges too. */
  const [tiled, setTiled] = useState(false);
  const snap = (count: SnapCount, ids?: string[], options: { anchor?: string | null; recent?: string[] } = {}): string[] | null => {
    const selected = snapOrder(count, windows, { ids: ids?.map(id => aliases[id] ?? id), anchor: options.anchor ? aliases[options.anchor] ?? options.anchor : null,
      recent: options.recent?.map(id => aliases[id] ?? id), known: [...new Set([...known, ...windows.map(win => win.id)])] });
    if (!selected) return null;
    snapBefore.current = windows.map(win => ({ ...win })); setCanUndoSnap(true); setTiled(true);
    const rects = snapRectangles(count);
    setWindows(current => {
      const preserved = current.filter(win => !selected.includes(win.id)).map(win => ({ ...win, minimized: true }));
      return [...preserved, ...selected.map((id,index) => ({ ...(current.find(win => win.id === id) ?? {}), id, ...rects[index], prev: undefined, z: raise(), minimized: false }))];
    });
    return selected;
  };
  const undoSnap = () => {
    const snapshot = snapBefore.current; if (!snapshot) return false;
    setWindows(current => current.map(win => { const previous=snapshot.find(item => item.id===win.id);return previous ? {...win,x:previous.x,y:previous.y,w:previous.w,h:previous.h,minimized:previous.minimized,prev:previous.prev} : win; }));
    snapBefore.current=null;setCanUndoSnap(false);setTiled(false);return true;
  };
  /** Edge resizing: in a tiled layout the neighbours sharing that edge follow it. */
  const resize = useCallback((id: string, rect: Rect) => setWindows(current => {
    if (!tiled) return current.map(win => win.id === id ? { ...win, ...boundedWindow(rect) } : win);
    const moved = resizeTiled(current.filter(win => !win.minimized), id, rect);
    return current.map(win => moved.find(item => item.id === win.id) ?? win);
  }), [tiled]);
  /** Maximize remembers the pane's slot; restoring returns to it (also after a reload). */
  const maximize = useCallback((id: string) => setWindows(current => current.map(win => win.id !== id ? win
    : isMaximized(win) ? { ...win, minimized: false, z: raise() } : { ...win, prev: { x: win.x, y: win.y, w: win.w, h: win.h }, x: 0, y: 0, w: 1, h: 1, minimized: false, z: raise() })), []);
  const restoreSize = (id: string): boolean => {
    const win = windows.find(item => item.id === id);
    if (!win?.prev || !isMaximized(win)) return false;
    const prev = win.prev;
    setWindows(current => current.map(item => item.id === id ? { ...item, ...boundedWindow(prev), prev: undefined, minimized: false, z: raise() } : item));
    return true;
  };
  // A retired window id (e.g. "calendar", now part of Tasks & Calendar) opens its replacement.
  const real = (id: string) => aliases[id] ?? id;
  return { windows, active, snapped: snapped || (tiled && visible.length > 1), tiled, closeAll, showDesktop, restoreAll, restore, snap, undoSnap, canUndoSnap,
    resize: (id: string, rect: Rect) => resize(real(id), rect), maximize: (id: string) => maximize(real(id)), restoreSize: (id: string) => restoreSize(real(id)),
    untile: () => setTiled(false), openTab, restoreClosed, closedTabs: () => closed.current, closedCount, move, pin, moveToPane,
    open: (id: string) => { if (!windows.some(win => win.id === real(id))) setTiled(false); open(real(id)); }, close: (id: string) => { setTiled(false); close(real(id)); }, minimize: (id: string) => minimize(real(id)),
    update: (id: string, rect: Partial<Rect>) => update(real(id), rect), setRect: (id: string, rect: Rect) => setRect(real(id), rect) };
}

type WindowProps = {
  win: ShellWindow; title: string; label: string; active: boolean; stage: () => DOMRect | null;
  onFocus: () => void; onClose: () => void; onMinimize: () => void; onChange: (rect: Partial<Rect>) => void; children: ReactNode;
  onAttention?: () => void; onArrange?: (count: SnapCount, anchor: string) => void;
  /** Edge resize (tiled layouts move shared edges); move drags use onChange. */
  onResize?: (rect: Rect) => void; onMaximize?: () => void; onRestoreSize?: () => void; onMoveStart?: () => void;
};

export function AppWindow({ win, title, label, active, stage, onFocus, onClose, onMinimize, onChange, onAttention, onArrange, onResize, onMaximize, onRestoreSize, onMoveStart, children }: WindowProps) {
  const drag = useRef<{ mode: "move" | ResizeEdge; startX: number; startY: number; rect: Rect; box: DOMRect; moved: boolean } | null>(null);
  const maximized = isMaximized(win);
  const toggleMaximize = () => {
    onFocus();
    if (maximized) { if (onRestoreSize) onRestoreSize(); else onChange(win.prev ?? placement(0)); }
    else if (onMaximize) onMaximize(); else onChange({ x: 0, y: 0, w: 1, h: 1 });
  };
  const begin = (mode: "move" | ResizeEdge) => (event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest("button,input,select")) return;
    const box = stage();
    if (!box) return;
    onFocus();
    drag.current = { mode, startX: event.clientX, startY: event.clientY, rect: { x: win.x, y: win.y, w: win.w, h: win.h }, box, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  };
  const moveTo = (event: ReactPointerEvent<HTMLElement>) => {
    const state = drag.current;
    if (!state) return;
    const dx = (event.clientX - state.startX) / state.box.width, dy = (event.clientY - state.startY) / state.box.height;
    if (state.mode === "move") {
      if (!state.moved && Math.hypot(event.clientX - state.startX, event.clientY - state.startY) < 4) return;
      if (!state.moved) { state.moved = true; onMoveStart?.(); }
      onChange(boundedWindow({ ...state.rect, x: state.rect.x + dx, y: state.rect.y + dy }));
    }
    else (onResize ?? onChange)(resizeWindow(state.rect, state.mode, dx, dy));
  };
  const end = () => { drag.current = null; };
  return <section className={`os-window${active ? " os-window--active" : ""}`} data-window-id={win.id} aria-label={title} role="dialog" aria-modal="false" hidden={win.minimized}
    style={{ left: `${win.x * 100}%`, top: `${win.y * 100}%`, width: `${win.w * 100}%`, height: `${win.h * 100}%`, zIndex: win.z }}
    onPointerEnter={onAttention} onFocusCapture={onAttention}
    onPointerDownCapture={event => { if (!(event.target as HTMLElement).closest(".os-window__controls")) onFocus(); }}>
    <header className="os-window__bar" onPointerDown={begin("move")} onPointerMove={moveTo} onPointerUp={end} onPointerCancel={end}
      onDoubleClick={event => { if (!(event.target as HTMLElement).closest("button")) toggleMaximize(); }}>
      <span className="os-window__label">{label}</span>
      <strong>{title}</strong>
      <div className="os-window__controls">
        {onArrange && <SnapLayouts onChoose={count => onArrange(count, win.id)}/>}
        <button type="button" onClick={onMinimize} aria-label={`Minimise ${title}`} title="Minimise to the dock">–</button>
        <button type="button" onClick={toggleMaximize} aria-label={`${maximized ? "Restore size of" : "Maximize"} ${title}`} title={maximized ? "Restore size" : "Maximize"}>□</button>
        <button type="button" onClick={onClose} aria-label={`Close ${title}`} title="Close">×</button>
      </div>
    </header>
    <div className="os-window__body" tabIndex={-1}><WindowControls.Provider value={<>
      {onArrange && <SnapLayouts onChoose={count => onArrange(count, win.id)}/>}
      <button type="button" onClick={onMinimize} aria-label={`Minimise ${title}`} title="Minimise">–</button>
      <button type="button" onClick={toggleMaximize} aria-label={`${maximized ? "Restore size of" : "Maximize"} ${title}`} title={maximized ? "Restore size" : "Maximize"}>□</button>
      <button type="button" onClick={onClose} aria-label={`Close ${title}`} title="Close">×</button>
    </>}>{children}</WindowControls.Provider></div>
    {(["n", "s", "e", "w", "ne", "nw", "se", "sw"] as ResizeEdge[]).map(edge => <span key={edge}
      className={`os-window__resize os-window__resize--${edge}`} role="button" tabIndex={0}
      aria-label={`Resize ${title} from ${edge}. Drag or use arrow keys.`}
      onPointerDown={begin(edge)} onPointerMove={moveTo} onPointerUp={end} onPointerCancel={end}
      onKeyDown={event => { const delta = event.shiftKey ? .1 : .02; const dx = event.key === "ArrowLeft" ? -delta : event.key === "ArrowRight" ? delta : 0;
        const dy = event.key === "ArrowUp" ? -delta : event.key === "ArrowDown" ? delta : 0;
        if (dx || dy) { event.preventDefault(); onFocus(); (onResize ?? onChange)(resizeWindow(win, edge, dx, dy)); } }}/>) }
  </section>;
}

export function Dock({ windows, titles, active, onOpen, onClose, onMinimize, onCloseAll, onMinimizeAll, onRestoreAll, onChange, onTarget, onPlace, onArrange, onUndoArrange, canUndoArrange }: {
  windows: ShellWindow[]; titles: Record<string, string>; active: string | null; onOpen: (id: string) => void;
  onClose: (id: string) => void; onMinimize: (id: string) => void; onCloseAll: () => void;
  onMinimizeAll: () => void; onRestoreAll: () => void; onChange: (id: string, rect: Partial<Rect>) => void;
  onArrange?: (count: SnapCount) => void; onUndoArrange?: () => void; canUndoArrange?: boolean;
  onTarget: (id: string) => void; onPlace: (id: string, spot: Spot) => void;
}) {
  const [managing, setManaging] = useState(false);
  const [selected, setSelected] = useState<string | null>(active);
  useEffect(() => { if (active) setSelected(active); }, [active]);
  const win = windows.find(item => item.id === selected) ?? windows.find(item => item.id === active) ?? windows[0];
  return <nav className="os-dock" aria-label="Open windows">
    <button className="os-dock__item os-dock__manager" type="button" aria-expanded={managing} aria-controls="tab-manager" onClick={() => setManaging(value => !value)}>Manage tabs <span>{windows.length}</span></button>
    {windows.map(win => <button key={win.id} type="button" className={`os-dock__item${win.minimized ? " os-dock__item--min" : ""}${active === win.id ? " os-dock__item--active" : ""}`}
      onClick={() => { onTarget(win.id); onOpen(win.id); }} title={win.minimized ? `Restore ${titles[win.id]}` : `Focus ${titles[win.id]}`}>{titles[win.id]}</button>)}
    {managing && <section className="os-tab-manager" id="tab-manager" aria-label="Tab manager">
      <header><strong>Tab manager</strong><button type="button" aria-label="Hide tab manager" onClick={() => setManaging(false)}>×</button></header>
      <div className="os-tab-manager__bulk">
        {onArrange && <SnapLayouts onChoose={onArrange}/>}
        {onUndoArrange && <button type="button" disabled={!canUndoArrange} onClick={onUndoArrange}>Undo arrangement</button>}
        <button type="button" onClick={onMinimizeAll} disabled={!windows.some(item => !item.minimized)}>Minimize all</button>
        <button type="button" onClick={onRestoreAll} disabled={!windows.some(item => item.minimized)}>Restore all</button>
        <button type="button" onClick={onCloseAll} disabled={!windows.length}>Close all</button>
      </div>
      <ul>{Object.entries(titles).map(([id, title]) => {
        const item = windows.find(candidate => candidate.id === id);
        return <li key={id}>
          <button className="os-tab-manager__select" type="button" aria-pressed={win?.id === id} onClick={() => { setSelected(id); onTarget(id); if (!item) onOpen(id); }}>
            <span>{title}</span><small>{item ? item.minimized ? "Minimized" : active === id ? "Active" : "Open" : "Closed"}</small>
          </button>
          <button type="button" aria-label={`${item?.minimized ? "Restore" : item ? "Focus" : "Open"} ${title}`} onClick={() => { setSelected(id); onTarget(id); onOpen(id); }}>{item?.minimized ? "Restore" : item ? "Focus" : "Open"}</button>
          {item && <button type="button" aria-label={`Close ${title} from manager`} onClick={() => onClose(id)}>×</button>}
        </li>;
      })}</ul>
      {win ? <div className="os-tab-manager__size">
        <strong>{titles[win.id]} size & position</strong>
        <label>Width <output>{Math.round(win.w * 100)}%</output><input aria-label={`${titles[win.id]} width`} type="range" min="26" max="100" value={Math.round(win.w * 100)} onChange={event => onChange(win.id, { w: Number(event.target.value) / 100 })}/></label>
        <label>Height <output>{Math.round(win.h * 100)}%</output><input aria-label={`${titles[win.id]} height`} type="range" min="30" max="100" value={Math.round(win.h * 100)} onChange={event => onChange(win.id, { h: Number(event.target.value) / 100 })}/></label>
        <div className="os-tab-manager__positions">{(["top-left", "top-right", "bottom-left", "bottom-right", "center"] as Spot[]).map(spot => <button key={spot} type="button" onClick={() => onPlace(win.id, spot)}>{spot.replace("-", " ")}</button>)}</div>
        <div className="os-tab-manager__bulk"><button type="button" onClick={() => onChange(win.id, { x: 0, y: 0, w: 1, h: 1 })}>Maximize</button><button type="button" disabled={win.minimized} onClick={() => onMinimize(win.id)}>Minimize</button></div>
      </div> : <p>Open a tab above to set its size and position.</p>}
      <p className="os-tab-manager__help">Drag any edge or corner to resize. Voice commands use the last tab you point to or work in, even after you click the chat.</p>
      <details className="os-tab-manager__phrases"><summary>Voice command examples</summary>{LAYOUT_PHRASES.map(group => <div key={group.label}><strong>{group.label}</strong><p>{group.examples.slice(0, 3).map(phrase => `“${phrase}”`).join(" · ")}</p></div>)}</details>
    </section>}
  </nav>;
}

/** Which workspace a sentence is about, so the shell can bring it forward. */
export function windowForText(text: string): string | null {
  if (/\b(workbench|project board|blueprints?)\b/i.test(text)) return 'workbench';
  if (/\b(music|songs?|garageband)\b/i.test(text)) return 'music';
  if (/\b(fitness|nutrition|workouts?)\b/i.test(text)) return 'fitness';
  const words = text.toLowerCase();
  if (/\b(notes?|notebook)\b/.test(words)) return 'notes';
  if (/\b(tech news|headlines)\b/.test(words)) return 'news';
  if (/\b(calendar|schedule|meeting|appointment|event|tomorrow at|next week|agenda)\b/.test(words)) return "calendar";
  if (/\b(task|tasks|to-?do|todo|checklist|deadline)\b/.test(words)) return "tasks";
  if (/\b(remind(?:er|ers)?|nudge|alarm)\b/.test(words)) return "tasks";
  if (/\b(file|files|folder|code|config|source|script)\b/.test(words)) return "files";
  if (/\b(remember|memory|memories|learned|follow.?through)\b/.test(words)) return "assistant";
  if (/\b(status|health|cpu|memory usage|modules?|diagnostic|system check|server)\b/.test(words)) return "status";
  return null;
}
