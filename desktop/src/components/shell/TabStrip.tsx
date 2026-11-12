import { useEffect, useState, type DragEvent, type MouseEvent } from "react";
import { SnapLayouts } from "./SnapLayouts";
import { paneLocation } from "./PaneNav";
import { tabBase, type ShellWindow } from "./WindowShell";
import type { SnapCount } from "../../core/windowLayout";
import "./TabStrip.css";

/**
 * Screen tabs, Chrome-style (Claude 2026-11-11). Every open page is a tab: switch, close (× or middle-click),
 * drag onto the left or right half to show two side by side, and open the manager for everything else
 * (reorder, pin, move to a pane, 2/3/4 layouts, recently closed, Undo). Windows are ZAE pages, not Windows apps.
 */
export type TabShell = {
  windows: ShellWindow[]; active: string | null; open: (id: string) => void; close: (id: string) => void; minimize: (id: string) => void;
  move: (id: string, step: number) => void; pin: (id: string) => void; moveToPane: (id: string, pane: number) => void;
  restoreClosed: (id?: string) => string | null; closedTabs: () => { id: string; at: number }[]; closedCount: number;
  snap: (count: SnapCount, ids?: string[]) => string[] | null; undoSnap: () => boolean; canUndoSnap: boolean;
  showDesktop: () => void; restoreAll: () => void; closeAll: () => void;
};
export function TabStrip({ shell, titles, onArrange, onUndo, onNewTab, onNote }: {
  shell: TabShell; titles: Record<string, string>; onArrange: (count: SnapCount) => void; onUndo: () => void; onNewTab: () => void; onNote: (text: string) => void;
}) {
  const [managing, setManaging] = useState(false);
  // The core moves into the chat mic while the tab manager covers Home (C5).
  useEffect(() => { window.dispatchEvent(new CustomEvent("zae:tab-manager-state", { detail: managing })); return () => { if (managing) window.dispatchEvent(new CustomEvent("zae:tab-manager-state", { detail: false })); }; }, [managing]);
  const [dragging, setDragging] = useState<string | null>(null);
  const [, setTick] = useState(0);
  useEffect(() => {
    const tick = () => setTick(value => value + 1);
    const manage = () => setManaging(true);
    window.addEventListener("zae:pane-history", tick); window.addEventListener("zae:page-preview", tick); window.addEventListener("zae:pane-location", tick); window.addEventListener("zae:tab-manager", manage);
    return () => { window.removeEventListener("zae:pane-history", tick); window.removeEventListener("zae:page-preview", tick); window.removeEventListener("zae:pane-location", tick); window.removeEventListener("zae:tab-manager", manage); };
  }, []);
  const title = (id: string) => titles[tabBase(id)] ?? tabBase(id);
  const where = (id: string) => paneLocation(id);
  const label = (id: string) => where(id).slice(-1)[0] || title(id);
  const visible = shell.windows.filter(win => !win.minimized);
  const drop = (side: "left" | "right") => (event: DragEvent) => {
    event.preventDefault(); const id = dragging ?? event.dataTransfer.getData("text/zae-tab"); setDragging(null);
    if (!id) return;
    const other = visible.filter(win => win.id !== id).sort((a, b) => b.z - a.z)[0]?.id ?? shell.windows.find(win => win.id !== id)?.id;
    if (!other) { onNote("Open another tab to show two side by side."); return; }
    const placed = shell.snap(2, side === "left" ? [id, other] : [other, id]);
    onNote(placed ? `Split: ${placed.map(label).join(" | ")}.` : "Couldn't split those tabs.");
  };
  const tabClick = (id: string) => (event: MouseEvent) => { if (event.button === 1) { event.preventDefault(); shell.close(id); return; } shell.open(id); };
  return <>
    <nav className="zt-strip" aria-label="Open tabs">
      {shell.windows.map(win => <div key={win.id} role="tab" aria-selected={shell.active === win.id} tabIndex={0} draggable
        className={`zt-tab${shell.active === win.id ? " on" : ""}${win.minimized ? " min" : ""}${win.pinned ? " pinned" : ""}`} data-tab-id={win.id}
        title={[title(win.id), ...where(win.id)].join(" › ")}
        onMouseDown={event => { if (event.button === 1) event.preventDefault(); }} onMouseUp={tabClick(win.id)}
        onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); shell.open(win.id); } if (event.key === "Delete") shell.close(win.id); }}
        onDragStart={event => { event.dataTransfer.setData("text/zae-tab", win.id); event.dataTransfer.effectAllowed = "move"; setDragging(win.id); }} onDragEnd={() => setDragging(null)}>
        {win.pinned && <span className="zt-pin" aria-hidden="true">•</span>}
        <span className="zt-t">{label(win.id)}</span>
        {!win.pinned && <button type="button" className="zt-x" aria-label={`Close ${label(win.id)} tab`} onMouseUp={event => event.stopPropagation()} onClick={event => { event.stopPropagation(); shell.close(win.id); }}>×</button>}
      </div>)}
      <button type="button" className="zt-new" aria-label="New tab" title="New tab" onClick={onNewTab}>+</button>
      <button type="button" className="zt-manage" aria-expanded={managing} aria-controls="zt-manager" onClick={() => setManaging(value => !value)}>Tabs <span>{shell.windows.length}</span></button>
    </nav>
    {dragging && <div className="zt-drop" aria-hidden="true">
      <div onDragOver={event => event.preventDefault()} onDrop={drop("left")}><span>Show on the left</span></div>
      <div onDragOver={event => event.preventDefault()} onDrop={drop("right")}><span>Show on the right</span></div>
    </div>}
    {managing && <section className="zt-manager" id="zt-manager" aria-label="Tab manager">
      <header><strong>Tabs</strong><button type="button" aria-label="Close tab manager" onClick={() => setManaging(false)}>×</button></header>
      <div className="zt-bulk">
        <SnapLayouts onChoose={onArrange}/>
        <button type="button" disabled={!shell.canUndoSnap} onClick={onUndo}>Undo layout</button>
        <button type="button" onClick={shell.showDesktop} disabled={!visible.length}>Minimise all</button>
        <button type="button" onClick={shell.restoreAll} disabled={!shell.windows.some(win => win.minimized)}>Restore all</button>
        <button type="button" onClick={shell.closeAll} disabled={!shell.windows.some(win => !win.pinned)}>Close all</button>
      </div>
      <ol className="zt-list">{shell.windows.map((win, index) => <li key={win.id} data-tab-id={win.id}>
        <button type="button" className="zt-go" aria-current={shell.active === win.id ? "page" : undefined} onClick={() => shell.open(win.id)}>
          <b>{label(win.id)}</b><small>{[title(win.id), ...where(win.id).slice(0, -1)].join(" › ")}{win.minimized ? " · minimised" : ""}{win.pinned ? " · pinned" : ""}</small></button>
        <span className="zt-acts">
          <button type="button" aria-label={`Move ${label(win.id)} up`} disabled={index === 0} onClick={() => shell.move(win.id, -1)}>↑</button>
          <button type="button" aria-label={`Move ${label(win.id)} down`} disabled={index === shell.windows.length - 1} onClick={() => shell.move(win.id, 1)}>↓</button>
          <button type="button" aria-pressed={!!win.pinned} aria-label={`${win.pinned ? "Unpin" : "Pin"} ${label(win.id)}`} onClick={() => shell.pin(win.id)}>{win.pinned ? "Unpin" : "Pin"}</button>
          {visible.length > 1 && visible.map((_, pane) => <button type="button" key={pane} aria-label={`Move ${label(win.id)} to pane ${pane + 1}`} onClick={() => shell.moveToPane(win.id, pane)}>{pane + 1}</button>)}
          <button type="button" aria-label={`Close ${label(win.id)}`} disabled={!!win.pinned} onClick={() => shell.close(win.id)}>×</button>
        </span>
      </li>)}</ol>
      {shell.closedCount > 0 && <div className="zt-closed"><strong>Recently closed</strong>
        {shell.closedTabs().map(item => <button type="button" key={item.id} onClick={() => shell.restoreClosed(item.id)}>{label(item.id)} <small>{new Date(item.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</small></button>)}</div>}
      <p className="zt-help">Middle-click or Ctrl+click any tile or page to open it in a new tab. Drag a tab to the left or right half to show two side by side. Say “show tabs”, “close this tab” or “split build requests and suggestions”.</p>
    </section>}
  </>;
}
