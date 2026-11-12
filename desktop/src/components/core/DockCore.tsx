import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { VoicePhase } from "./neuralField";
import { CoreSlot } from "./CoreStage";
import "./DockCore.css";

// C1 "Docked companion" (Grey's pick, 2026-11-11, replacing C5). Off Home the one core docks as a living orb in a
// slot at the left end of the page's top row (preview-05 row on desktop, the M5 header on the phone). Only the
// focused pane's row holds it. Voice states widen the slot and swell the orb; there is no status word.

/** The reserved space at the left of a top row. Decorative: the orb is drawn over it by DockCore. */
export function DockSlot() {
  return <span className="core-dock-slot" aria-hidden="true"/>;
}

const ORB = 96; // drawing box; idle shows ~57 px, voice swells it
/** Which row's slot holds the orb, best first. */
function findSlot(sheet: boolean) {
  const order = sheet
    ? [".navhub .core-dock-slot"]
    : [".os-window--active .core-dock-slot", ".core-dock-slot"];
  for (const selector of order) {
    for (const el of document.querySelectorAll<HTMLElement>(selector)) {
      const box = el.getBoundingClientRect();
      if (box.width > 0 && box.height > 0 && !el.closest("[hidden]")) return el;
    }
  }
  return null;
}

function slotCentre(sheet: boolean) {
  const slot = findSlot(sheet);
  if (!slot) return null;
  const box = slot.getBoundingClientRect();
  return { slot, x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) };
}

export function DockCore({ phase, accent, sheet, layoutKey }: { phase: VoicePhase; accent: string; sheet: boolean; layoutKey: string }) {
  // Placed on the slot in the first render, so the core glides straight into it.
  const [at, setAt] = useState<{ x: number; y: number } | null>(() => { const c = slotCentre(sheet); return c && { x: c.x, y: c.y }; });
  useEffect(() => {
    let frame = 0, late = 0, held: HTMLElement | null = null;
    const sizes = new ResizeObserver(() => soon());
    const follow = () => {
      frame = 0;
      const found = slotCentre(sheet);
      const slot = found?.slot ?? null;
      if (slot !== held) {
        if (held) { sizes.unobserve(held); held.removeAttribute("data-dock-on"); }
        if (slot) { sizes.observe(slot); slot.setAttribute("data-dock-on", ""); }
        held = slot;
      }
      if (!found) { setAt(null); return; }
      setAt(previous => previous && previous.x === found.x && previous.y === found.y ? previous : { x: found.x, y: found.y });
    };
    function soon() {
      if (!frame) frame = requestAnimationFrame(follow);
      window.clearTimeout(late); late = window.setTimeout(follow, 350);
    }
    follow();
    window.addEventListener("resize", soon);
    document.addEventListener("scroll", soon, { capture: true, passive: true });
    document.addEventListener("transitionend", soon, true);
    return () => {
      cancelAnimationFrame(frame); window.clearTimeout(late); sizes.disconnect();
      held?.removeAttribute("data-dock-on");
      window.removeEventListener("resize", soon);
      document.removeEventListener("scroll", soon, { capture: true });
      document.removeEventListener("transitionend", soon, true);
    };
  }, [sheet, layoutKey]);
  const style = { left: at?.x ?? -9999, top: at?.y ?? -9999, width: ORB, height: ORB, "--core-accent": accent } as CSSProperties;
  return <div className={`core-dock core-dock--${phase}`} style={style} aria-hidden="true" data-core-overlay="">
    <div className="core-dock__fx"><i/><i/><i/></div>
    <div className="core-dock__core"><CoreSlot priority={2}/></div>
  </div>;
}
