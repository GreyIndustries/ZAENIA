import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
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
export type ShellWindow = { id: string; x: number; y: number; w: number; h: number; z: number; minimized: boolean };
type Rect = Pick<ShellWindow, "x" | "y" | "w" | "h">;

export const STORAGE_KEY = "zaenia.shellWindows";
const MIN_W = 0.26, MIN_H = 0.3;
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

function readSaved(): ShellWindow[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(saved)) return [];
    return saved.filter((item): item is ShellWindow => Boolean(item) && typeof item.id === "string"
      && ["x", "y", "w", "h", "z"].every(key => typeof item[key] === "number" && Number.isFinite(item[key])))
      .map(item => ({ ...item, ...boundedWindow(item), minimized: item.minimized === true }));
  } catch { return []; }
}

/** Cascade new windows so they never open exactly on top of each other. */
function placement(index: number): Rect {
  const step = (index % 5) * 0.035;
  // Module windows open nearly full-screen, like a magazine page (still movable and resizable).
  return { x: 0.03 + step / 2, y: 0.02 + step / 2, w: 0.92, h: 0.92 };
}

export function useWindowShell(known: readonly string[], aliases: Record<string, string> = {}) {
  const [windows, setWindows] = useState<ShellWindow[]>(() => readSaved().filter(win => known.includes(win.id)));
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
  const close = useCallback((id: string) => setWindows(current => current.filter(win => win.id !== id)), []);
  const minimize = useCallback((id: string) => setWindows(current => current.map(win => win.id === id ? { ...win, minimized: true } : win)), []);
  const showDesktop = useCallback(() => setWindows(current => current.map(win => ({ ...win, minimized: true }))), []);
  const closeAll = useCallback(() => setWindows([]), []);
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
  const active = windows.filter(win => !win.minimized).sort((a, b) => b.z - a.z)[0]?.id ?? null;
  const restore = useCallback((saved: ShellWindow[]) => {
    const checked = saved.filter(win => known.includes(win.id) && [win.x, win.y, win.w, win.h, win.z].every(Number.isFinite)).slice(0, known.length).map((win, index) => {
      const w = clamp(win.w, MIN_W, .98), h = clamp(win.h, MIN_H, .96);
      return { ...win, x: clamp(win.x, 0, 1 - w), y: clamp(win.y, 0, 1 - h), w, h, z: index + 11, minimized: Boolean(win.minimized) };
    });
    zTop.current = checked.length + 12; setWindows(checked);
  }, [known]);
  // A retired window id (e.g. "calendar", now part of Tasks & Calendar) opens its replacement.
  const real = (id: string) => aliases[id] ?? id;
  return { windows, active, closeAll, showDesktop, restoreAll, restore,
    open: (id: string) => open(real(id)), close: (id: string) => close(real(id)), minimize: (id: string) => minimize(real(id)),
    update: (id: string, rect: Partial<Rect>) => update(real(id), rect), setRect: (id: string, rect: Rect) => setRect(real(id), rect) };
}

type WindowProps = {
  win: ShellWindow; title: string; label: string; active: boolean; stage: () => DOMRect | null;
  onFocus: () => void; onClose: () => void; onMinimize: () => void; onChange: (rect: Partial<Rect>) => void; children: ReactNode;
  onAttention?: () => void;
};

export function AppWindow({ win, title, label, active, stage, onFocus, onClose, onMinimize, onChange, onAttention, children }: WindowProps) {
  const drag = useRef<{ mode: "move" | ResizeEdge; startX: number; startY: number; rect: Rect; box: DOMRect } | null>(null);
  const normalRect = useRef<Rect | null>(null);
  const maximized = win.w >= .95 && win.h >= .94;
  const toggleMaximize = () => {
    onFocus();
    if (maximized) onChange(normalRect.current ?? placement(0));
    else { normalRect.current = { x: win.x, y: win.y, w: win.w, h: win.h }; onChange({ x: 0, y: 0, w: 1, h: 1 }); }
  };
  const begin = (mode: "move" | ResizeEdge) => (event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest("button,input,select")) return;
    const box = stage();
    if (!box) return;
    onFocus();
    drag.current = { mode, startX: event.clientX, startY: event.clientY, rect: { x: win.x, y: win.y, w: win.w, h: win.h }, box };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  };
  const moveTo = (event: ReactPointerEvent<HTMLElement>) => {
    const state = drag.current;
    if (!state) return;
    const dx = (event.clientX - state.startX) / state.box.width, dy = (event.clientY - state.startY) / state.box.height;
    if (state.mode === "move") onChange(boundedWindow({ ...state.rect, x: state.rect.x + dx, y: state.rect.y + dy }));
    else onChange(resizeWindow(state.rect, state.mode, dx, dy));
  };
  const end = () => { drag.current = null; };
  return <section className={`os-window${active ? " os-window--active" : ""}`} data-window-id={win.id} aria-label={title} role="dialog" aria-modal="false"
    style={{ left: `${win.x * 100}%`, top: `${win.y * 100}%`, width: `${win.w * 100}%`, height: `${win.h * 100}%`, zIndex: win.z }}
    onPointerEnter={onAttention} onFocusCapture={onAttention}
    onPointerDownCapture={event => { if (!(event.target as HTMLElement).closest(".os-window__controls")) onFocus(); }}>
    <header className="os-window__bar" onPointerDown={begin("move")} onPointerMove={moveTo} onPointerUp={end} onPointerCancel={end}
      onDoubleClick={event => { if (!(event.target as HTMLElement).closest("button")) toggleMaximize(); }}>
      <span className="os-window__label">{label}</span>
      <strong>{title}</strong>
      <div className="os-window__controls">
        <button type="button" onClick={onMinimize} aria-label={`Minimise ${title}`} title="Minimise to the dock">–</button>
        <button type="button" onClick={toggleMaximize} aria-label={`${maximized ? "Restore size of" : "Maximize"} ${title}`} title={maximized ? "Restore size" : "Maximize"}>□</button>
        <button type="button" onClick={onClose} aria-label={`Close ${title}`} title="Close">×</button>
      </div>
    </header>
    <div className="os-window__body">{children}</div>
    {(["n", "s", "e", "w", "ne", "nw", "se", "sw"] as ResizeEdge[]).map(edge => <span key={edge}
      className={`os-window__resize os-window__resize--${edge}`} role="button" tabIndex={0}
      aria-label={`Resize ${title} from ${edge}. Drag or use arrow keys.`}
      onPointerDown={begin(edge)} onPointerMove={moveTo} onPointerUp={end} onPointerCancel={end}
      onKeyDown={event => { const delta = event.shiftKey ? .1 : .02; const dx = event.key === "ArrowLeft" ? -delta : event.key === "ArrowRight" ? delta : 0;
        const dy = event.key === "ArrowUp" ? -delta : event.key === "ArrowDown" ? delta : 0;
        if (dx || dy) { event.preventDefault(); onFocus(); onChange(resizeWindow(win, edge, dx, dy)); } }}/>) }
  </section>;
}

export function Dock({ windows, titles, active, onOpen, onClose, onMinimize, onCloseAll, onMinimizeAll, onRestoreAll, onChange, onTarget, onPlace }: {
  windows: ShellWindow[]; titles: Record<string, string>; active: string | null; onOpen: (id: string) => void;
  onClose: (id: string) => void; onMinimize: (id: string) => void; onCloseAll: () => void;
  onMinimizeAll: () => void; onRestoreAll: () => void; onChange: (id: string, rect: Partial<Rect>) => void;
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
  if (/\b(file|files|folder|code|config|source|script)\b/.test(words)) return "files";
  if (/\b(remember|memory|memories|learned|reminder|reminders|follow.?through)\b/.test(words)) return "assistant";
  if (/\b(status|health|cpu|memory usage|modules?|diagnostic|system check|server)\b/.test(words)) return "status";
  return null;
}
