import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { VoicePhase } from "./neuralField";
import { CoreSlot } from "./CoreStage";
import { burstFit } from "../../core/coreVisibility";
import "./MicCore.css";

// C5 "Core in the mic" (Grey's pick, 2026-11-11): off Home the one core sits inside the chat bar's mic button as a
// tiny spinning field. While ZAE listens, thinks or speaks it bursts into a ring around the mic with the state word
// to its left, then shrinks back. It never takes clicks; the mic button underneath keeps working as the mic.

const RING = 150;
const WORD: Record<VoicePhase, string> = { idle: "", listening: "Listening", thinking: "Thinking", speaking: "Speaking" };
/** Where the mic is, best first. Phone (M5) uses the "Say or type a page" bar's mic when the page has one. */
const DESKTOP_MIC = [".home-chat__composer .home-chat__mic", ".home-chat__composer .chat-dock__mark"];
const PHONE_MIC = [".bx-vbar .bx-mic", ...DESKTOP_MIC];

function findMic(phone: boolean) {
  for (const selector of phone ? PHONE_MIC : DESKTOP_MIC) {
    for (const el of document.querySelectorAll<HTMLElement>(selector)) {
      const box = el.getBoundingClientRect();
      if (box.width > 0 && box.height > 0 && !el.closest("[hidden]")) return el;
    }
  }
  return null;
}

function micCentre(phone: boolean) {
  const mic = findMic(phone);
  if (!mic) return null;
  const box = mic.getBoundingClientRect();
  return { x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) };
}

export function MicCore({ phase, accent, phone, layoutKey }: { phase: VoicePhase; accent: string; phone: boolean; layoutKey: string }) {
  // Placed at the mic in the first render, so the core glides straight into it.
  const [at, setAt] = useState<{ x: number; y: number } | null>(() => micCentre(phone));
  useEffect(() => {
    let frame = 0, late = 0, watched: HTMLElement | null = null;
    const sizes = new ResizeObserver(() => soon());
    const follow = () => {
      frame = 0;
      const mic = findMic(phone);
      if (mic !== watched) { if (watched) sizes.unobserve(watched); if (mic) sizes.observe(mic); watched = mic; }
      const next = micCentre(phone);
      if (!next) { setAt(null); return; }
      setAt(previous => previous && previous.x === next.x && previous.y === next.y ? previous : next);
    };
    function soon() {
      if (!frame) frame = requestAnimationFrame(follow);
      window.clearTimeout(late); late = window.setTimeout(follow, 350);
    }
    soon();
    window.addEventListener("resize", soon);
    document.addEventListener("scroll", soon, { capture: true, passive: true });
    document.addEventListener("transitionend", soon, true);
    return () => {
      cancelAnimationFrame(frame); window.clearTimeout(late); sizes.disconnect();
      window.removeEventListener("resize", soon);
      document.removeEventListener("scroll", soon, { capture: true });
      document.removeEventListener("transitionend", soon, true);
    };
  }, [phone, layoutKey]);
  // Keep the burst ring on screen (safe-area insets included): shift it toward the middle, shrink only if needed.
  const [safe, setSafe] = useState<HTMLSpanElement | null>(null);
  const [view, setView] = useState(() => ({ width: window.innerWidth, height: window.innerHeight }));
  useEffect(() => { const on = () => setView({ width: window.innerWidth, height: window.innerHeight }); window.addEventListener("resize", on); return () => window.removeEventListener("resize", on); }, []);
  const insets = safe ? getComputedStyle(safe) : null;
  const inset = (side: "Top" | "Right" | "Bottom" | "Left") => parseFloat(insets?.[`padding${side}`] ?? "0") || 0;
  const fit = at ? burstFit(at, RING, { ...view, top: inset("Top"), right: inset("Right"), bottom: inset("Bottom"), left: inset("Left") }) : { dx: 0, dy: 0, scale: 1 };
  const style = { left: at?.x ?? -9999, top: at?.y ?? -9999, "--core-accent": accent,
    "--burst-dx": `${fit.dx}px`, "--burst-dy": `${fit.dy}px`, "--burst-k": fit.scale, "--burst-r": `${(RING / 2) * fit.scale}px` } as CSSProperties;
  return <div className={`core-mic core-mic--${phase}${phase !== "idle" ? " core-mic--burst" : ""}`} style={style} data-core-mic="">
    <div className="core-mic__fx" aria-hidden="true"><i/><i/><i/></div>
    <div className="core-mic__core" aria-hidden="true"><CoreSlot priority={2}/></div>
    <span className="core-mic__word" role="status" aria-live="polite">{WORD[phase]}</span>
    <span className="core-mic__safe" ref={setSafe} aria-hidden="true"/>
  </div>;
}
