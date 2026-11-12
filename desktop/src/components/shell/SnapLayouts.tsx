import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { snapRectangles, type SnapCount } from "../../core/windowLayout";

/**
 * Layout picker. Hover previews it after a short pause; a click always leaves it open (Claude 2026-11-11:
 * the earlier hover-open + click-toggle closed it again on a normal hover-then-click).
 */
export function SnapLayouts({ onChoose }: { onChoose: (count: SnapCount) => void }) {
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const trigger = useRef<HTMLButtonElement>(null); const box = useRef<HTMLDivElement>(null);
  const hoverTimer = useRef<number | null>(null); const openedAt = useRef(0);
  const place = () => {
    const rect = trigger.current?.getBoundingClientRect();
    if (rect) { openedAt.current = Date.now(); setPosition({ top: Math.max(8, Math.min(window.innerHeight - 190, rect.bottom + 7)), left: Math.max(8, Math.min(rect.right - 300, window.innerWidth - 308)) }); }
  };
  const cancelHover = () => { if (hoverTimer.current) window.clearTimeout(hoverTimer.current); hoverTimer.current = null; };
  useEffect(() => cancelHover, []);
  useEffect(() => {
    if (!position) return;
    const away = (event: PointerEvent) => { if (!box.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) setPosition(null); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setPosition(null); trigger.current?.focus(); } };
    const resized = () => setPosition(null);
    window.addEventListener("pointerdown", away); window.addEventListener("keydown", escape); window.addEventListener("resize", resized);
    return () => { window.removeEventListener("pointerdown", away); window.removeEventListener("keydown", escape); window.removeEventListener("resize", resized); };
  }, [position]);
  return <>
    <button ref={trigger} type="button" className="os-snap-trigger" title="Snap layouts: 2, 3 or 4 windows" aria-label="Snap layouts" aria-haspopup="true" aria-expanded={!!position}
      onMouseEnter={() => { cancelHover(); if (!position) hoverTimer.current = window.setTimeout(place, 350); }} onMouseLeave={cancelHover}
      onClick={() => { cancelHover(); if (!position) place(); else if (Date.now() - openedAt.current > 600) setPosition(null); }}>▦</button>
    {position && createPortal(<div ref={box} className="os-snap-picker" role="group" aria-label="Choose window layout" style={position}>
      <strong>Arrange your workspace</strong><div>{([2,3,4] as const).map(count => <button key={count} type="button" aria-label={`${count} windows`} onClick={() => { setPosition(null); onChoose(count); }}>
        <span className="os-snap-diagram" aria-hidden="true">{snapRectangles(count).map((rect, index) => <i key={index} style={{ left: `${rect.x * 100}%`, top: `${rect.y * 100}%`, width: `${rect.w * 100}%`, height: `${rect.h * 100}%` }}/>)}</span>
        <span>{count === 2 ? "Side by side" : count === 3 ? "One large, two small" : "Grid of four"}</span>
      </button>)}</div><small>Fills from open windows, then minimized and recent apps. Say “arrange three windows” or “undo window arrangement”.</small>
    </div>, document.body)}
  </>;
}
