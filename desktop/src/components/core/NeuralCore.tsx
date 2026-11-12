import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { nodeWakeLevel } from "../../core/coreWake";
import { coreVisible, OPAQUE_SURFACES, renderScale, samplePoints } from "../../core/coreVisibility";
import type { CoreHit } from "../../core/coreVisibility";
import type { CoreTelemetry, ModulePhase } from "../../core/coreTelemetry";
import { BRANCHES, computeLayout, createNeuralField } from "./neuralField";
import { rememberCore } from "./CoreStage";
import type { BranchKey, CoreExtras, FieldLayout, NeuralField, VoicePhase } from "./neuralField";
import "./NeuralCore.css";

type Section = "status" | "security" | "tasks" | "calendar" | "files" | "system";
type Props = {
  telemetry: CoreTelemetry | null;
  source: "preview" | "local";
  motion: boolean;
  /** App in the background and ZAE idle: the core holds still and draws nothing new. */
  paused?: boolean;
  processing?: boolean;
  startup: { progress: number; ready: boolean };
  onSelect?: (section: Section) => void;
  /** Live assistant state; the core listens, thinks and speaks visibly. */
  phase?: VoicePhase;
  /** When the no-name follow-up window closes (ms since epoch), or 0. */
  followUntil?: () => number;
  /** The six category icons (in slot order) that replace the module orbs on the dashboard. */
  categories?: readonly { name: string; description: string; icon: ReactNode }[];
  onCategory?: (index: number) => void;
  /** Clicking the sphere itself (the dashboard shows every tab). */
  onCore?: () => void;
  /** The core by itself with its nerves as Saturn-like rings, and no module or category icons (Grey, 2026-10-31). */
  ringed?: boolean;
  /** Background jobs running now: one bead each orbits the middle ring (Grey's upgrade 3, 2026-10-31). */
  activeJobs?: number;
  /** Changes whenever windows, sheets or the dock move, so the core re-checks whether it can be seen. */
  layoutKey?: string;
  /** Hex accent that recolours the core (C1: the page's module colour while it is docked in the top row). */
  tint?: string;
};

const phaseCopy: Record<VoicePhase, string> = { idle: "STANDING BY", listening: "LISTENING", thinking: "THINKING", speaking: "SPEAKING" };

/** Seconds left in the follow-up window, refreshed while it is open. */
function useFollowUpLeft(followUntil: (() => number) | undefined, phase: VoicePhase) {
  const [left, setLeft] = useState(0);
  useEffect(() => {
    if (!followUntil) { setLeft(0); return; }
    const tick = () => setLeft(Math.max(0, followUntil() - Date.now()));
    tick();
    const id = window.setInterval(tick, 250);
    return () => window.clearInterval(id);
  }, [followUntil, phase]);
  return left;
}

const phaseName: Record<ModulePhase, string> = { ready: "READY", working: "WORKING", pending: "PENDING", error: "ERROR" };
const target: Record<BranchKey, Section> = {
  security: "security", calendar: "calendar", status: "status", files: "files", tasks: "tasks", system: "system",
};

function ModuleIcon({ name }: { name: BranchKey }) {
  const shapes: Record<BranchKey, ReactNode> = {
    security: <><rect x="7" y="13" width="18" height="15" rx="3"/><path d="M11 13V9.5a5 5 0 0 1 10 0V13"/><circle cx="16" cy="20.5" r="1.6"/></>,
    status: <path d="M3.5 16.5h6l3.2-8.5 6.3 16 3.2-7.5h6.3"/>,
    tasks: <><rect x="6" y="6" width="20" height="20" rx="3"/><path d="m11 16.5 3.6 3.6L21.5 12"/></>,
    calendar: <><rect x="5" y="8" width="22" height="19" rx="3"/><path d="M10.5 5v6M21.5 5v6M5 14h22M10.5 19h.01M16 19h.01M21.5 19h.01M10.5 23h.01M16 23h.01"/></>,
    files: <path d="M4 10a2 2 0 0 1 2-2h7l3 3.5h10a2 2 0 0 1 2 2V25a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z"/>,
    system: <><circle cx="16" cy="16" r="4"/><path d="M14.4 3.5h3.2l.7 3.2 2.3 1 2.8-1.8 2.3 2.3-1.8 2.8 1 2.3 3.2.7v3.2l-3.2.7-1 2.3 1.8 2.8-2.3 2.3-2.8-1.8-2.3 1-.7 3.2h-3.2l-.7-3.2-2.3-1-2.8 1.8-2.3-2.3 1.8-2.8-1-2.3-3.2-.7v-3.2l3.2-.7 1-2.3-1.8-2.8 2.3-2.3 2.8 1.8 2.3-1Z"/></>,
  };
  return <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}

/** "#5fd39a" → "95,211,154"; anything else → undefined. */
function hexRgb(hex?: string) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex ?? "");
  if (!m) return undefined;
  const n = parseInt(m[1], 16);
  return `${n >> 16},${(n >> 8) & 255},${n & 255}`;
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReduced(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  return reduced;
}

/**
 * The Core: one canvas draws the sphere, its six nerves and their signals so
 * the branches belong to the organism. Module orbs and labels sit on top as
 * real buttons for keyboard and screen-reader access.
 */
export function NeuralCore({ telemetry, source, motion, paused = false, processing = false, startup, onSelect, phase = "idle", followUntil, categories, onCategory, onCore, ringed = true, activeJobs = 0, layoutKey = "", tint }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fieldRef = useRef<NeuralField | null>(null);
  const [layout, setLayout] = useState<FieldLayout | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const reduced = usePrefersReducedMotion();
  // Preview switches for the core upgrades (localStorage "zaenia.corePreview": {"mood":true,"phase":"listening",...}).
  const [preview] = useState<{ phase?: VoicePhase } & CoreExtras>(() => { try { return JSON.parse(localStorage.getItem("zaenia.corePreview") ?? "{}"); } catch { return {}; } });
  // Night side after sunset (upgrade 5): from 7 pm to 6 am local time, checked every minute.
  const nightNow = () => { const h = new Date().getHours(); return h >= 19 || h < 6; };
  const [night, setNight] = useState(nightNow);
  useEffect(() => { const id = window.setInterval(() => setNight(nightNow()), 60_000); return () => window.clearInterval(id); }, []);
  // Live upgrades (Grey picked 1, 2, 3 and 5): mood-coloured rings, voice ripples while she speaks, a bead per running job, the night side.
  const extras: CoreExtras = { ...preview, mood: preview.mood ?? true, pulse: preview.pulse ?? true, beads: preview.beads ?? Math.min(6, activeJobs), night: preview.night ?? night, tint: hexRgb(tint) };
  const ringedRef = useRef(ringed);
  ringedRef.current = ringed;
  const animate = motion && !reduced;
  // Pause while nothing of the core can be seen (Claude, 2026-11-11): under an opaque window or sheet,
  // off-screen, or between slots. Checked on layout events, never by polling.
  const [visible, setVisible] = useState(true);
  const recheck = useRef<() => void>(() => undefined);

  useEffect(() => {
    const wrap = wrapRef.current, canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const field = createNeuralField(canvas);
    if (!field) { setUnavailable(true); return; }
    fieldRef.current = field;
    // Lay out in the box's own CSS size; draw at the size actually shown (e.g. orbit view's 0.68 scale).
    let drawn = "";
    const measure = () => {
      const width = wrap.offsetWidth, height = wrap.offsetHeight;
      if (width < 40 || height < 40) return;
      const scale = renderScale(wrap.getBoundingClientRect().width, width);
      const key = `${width}x${height}@${scale}:${ringedRef.current}`;
      if (key === drawn) return;
      drawn = key;
      const next = computeLayout(width, height, ringedRef.current);
      field.setLayout(next, scale);
      setLayout(next);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(wrap);
    measure();
    let onScreen = true, frame = 0, late = 0;
    const check = () => {
      frame = 0;
      const box = wrap.getBoundingClientRect();
      // A docked orb is drawn above every page (pointer-events: none), so nothing under it can cover it.
      const above = Boolean(wrap.closest("[data-core-overlay]"));
      const hits: CoreHit[] = samplePoints(box).map(([x, y]) => {
        if (above) return x < 0 || y < 0 || x >= window.innerWidth || y >= window.innerHeight ? "outside" : "core";
        if (x < 0 || y < 0 || x >= window.innerWidth || y >= window.innerHeight) return "outside";
        const hit = document.elementFromPoint(x, y);
        if (!hit) return "outside";
        if (wrap.contains(hit)) return "core";
        const surface = hit.closest(OPAQUE_SURFACES);
        return surface && !surface.contains(wrap) ? "opaque" : "other";
      });
      setVisible(coreVisible({ connected: wrap.isConnected, onScreen, width: box.width, height: box.height, hits }));
      if (wrap.isConnected) rememberCore(wrap);
      measure();
    };
    const soon = () => {
      if (!frame) frame = requestAnimationFrame(check);
      // Once more after window/sheet/dock transitions settle.
      window.clearTimeout(late); late = window.setTimeout(check, 700);
    };
    recheck.current = soon;
    const seen = new IntersectionObserver(([entry]) => { onScreen = entry.isIntersecting; soon(); });
    seen.observe(wrap);
    window.addEventListener("resize", soon);
    window.addEventListener("zae:core-moved", soon);
    document.addEventListener("transitionend", soon, true);
    document.addEventListener("animationend", soon, true);
    document.addEventListener("visibilitychange", soon);
    soon();
    return () => {
      observer.disconnect(); seen.disconnect(); cancelAnimationFrame(frame); window.clearTimeout(late);
      window.removeEventListener("resize", soon); window.removeEventListener("zae:core-moved", soon);
      document.removeEventListener("transitionend", soon, true); document.removeEventListener("animationend", soon, true);
      document.removeEventListener("visibilitychange", soon);
      recheck.current = () => undefined;
      field.destroy(); fieldRef.current = null;
    };
  }, []);
  useEffect(() => { recheck.current(); }, [layoutKey]);

  useEffect(() => {
    fieldRef.current?.setState({ progress: startup.progress, motion: animate && !paused && visible, processing, phase: preview.phase ?? phase, ringed, extras });
  }, [startup.progress, animate, paused, visible, processing, phase, layout, ringed, extras.beads, extras.night, extras.tint]);
  const followLeft = useFollowUpLeft(followUntil, phase);
  const following = phase === "idle" && followLeft > 0;

  const phaseFor = (key: BranchKey) => telemetry?.modules.find(m => m.id === key)?.phase;
  const readyCount = telemetry?.modules.filter(m => m.phase === "ready" || m.phase === "working").length ?? 0;
  const moduleCount = telemetry?.modules.length ?? 0;
  // Under-icon readouts: system status, and security as good/fix + two words.
  const security = telemetry?.modules.find(m => m.id === "security");
  const securityWords = (detail?: string) => {
    const text = (detail ?? "").toLowerCase();
    if (/passkey is not set up/.test(text)) return "Passkey missing";
    if (/token is not set up/.test(text)) return "Token missing";
    if (/token mode/.test(text)) return "Token mode";
    if (/unlocked/.test(text)) return "Passkey unlocked";
    return (detail ?? "").split(/\s+/).filter(Boolean).slice(0, 2).join(" ") || "Protected locally";
  };
  const underIcon = (key: BranchKey): { tone: "good" | "fix" | "idle"; text: string } | null => {
    if (key === "status") {
      if (source === "preview") return { tone: "idle", text: "Preview" };
      if (!telemetry) return { tone: "fix", text: "Offline" };
      return { tone: readyCount === moduleCount ? "good" : "fix", text: `${readyCount}/${moduleCount} ready` };
    }
    if (key === "security") {
      if (source === "preview" || !security) return { tone: "idle", text: source === "preview" ? "Preview" : "No data" };
      const good = security.phase === "ready" || security.phase === "working";
      return { tone: good ? "good" : "fix", text: `${good ? "Good" : "Needs fixing"} · ${securityWords(security.detail)}` };
    }
    return null;
  };
  const statusFor = (key: BranchKey) => {
    if (source === "preview") return "PREVIEW";
    if (!telemetry) return "NO DATA";
    if (key === "status") return moduleCount ? `${readyCount} / ${moduleCount} READY` : "NO DATA";
    if (key === "system") return telemetry.diagnostics;
    if (key === "tasks" || key === "files") return "ON THIS PC";
    const phase = phaseFor(key);
    return phase ? phaseName[phase] : "NO DATA";
  };

  return <div
    ref={wrapRef}
    data-core-paused={visible ? undefined : ""}
    className={`neural-core neural-core--${phase} ${layout?.compact ? "neural-core--compact" : ""} ${processing ? "neural-core--processing" : ""}`}
    role="group"
    aria-label={`ZÆNIA neural core with six connected modules. ${source === "preview" ? "Module statuses are illustrative preview data." : "Module statuses reflect available local telemetry."}`}
  >
    <canvas ref={canvasRef} className="neural-core__canvas" aria-hidden="true"/>
    {unavailable && <div className="neural-core__fallback">Core visual unavailable. Module navigation remains available.</div>}
    {layout && <>
      {startup.ready && <>
        <svg className={`core-hud${animate ? " core-hud--motion" : ""}`} style={{ left: layout.cx, top: layout.cy, width: layout.r * 2.56, height: layout.r * 2.56 }} viewBox="0 0 200 200" aria-hidden="true">
          {following && <circle className="core-hud__follow" cx="100" cy="100" r="88" pathLength="100" strokeDasharray={`${(followLeft / 30000 * 100).toFixed(2)} 100`}/>}
        </svg>
        <div className="core-state" role="status" aria-live="polite" style={{ left: layout.cx, top: layout.cy + layout.r * (layout.compact || ringed ? 1.06 : 1.2) }}>
          <i aria-hidden="true"/>{following ? <>FOLLOW-UP OPEN <small>{Math.ceil(followLeft / 1000)}s · no name needed</small></> : phaseCopy[phase]}
        </div>
      </>}
      {onCore && startup.ready && <button type="button" className="core-tap" aria-label="Open core app launcher"
        style={{ left: layout.cx, top: layout.cy, width: layout.r * 1.7, height: layout.r * 1.7 }} onClick={onCore}/>}
      {!ringed && BRANCHES.map((branch, index) => {
        const place = layout.orbs[index];
        const category = categories?.[index];
        if (category) {
          const wakeLevel = nodeWakeLevel(startup.progress, index);
          return <button key={branch.key} type="button"
            className={`core-orb core-orb--${branch.tone} core-orb--${branch.side < 0 ? "left" : "right"}${place.labelAbove ? " core-orb--label-above" : ""}`}
            style={{ left: place.x, top: place.y, width: layout.orbR * 2, height: layout.orbR * 2, opacity: 0.12 + wakeLevel * 0.88 } as CSSProperties}
            onClick={() => onCategory?.(index)} aria-label={`${category.name}: ${category.description}`}>
            <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{category.icon}</svg>
            <span className="core-orb__plate" aria-hidden="true"><strong>{category.name}</strong><small>{category.description}</small></span>
          </button>;
        }
        const wake = nodeWakeLevel(startup.progress, index);
        const status = statusFor(branch.key);
        const style = { left: place.x, top: place.y, width: layout.orbR * 2, height: layout.orbR * 2, opacity: 0.12 + wake * 0.88 } as CSSProperties;
        return <button
          key={branch.key}
          type="button"
          className={`core-orb core-orb--${branch.tone} core-orb--${branch.side < 0 ? "left" : "right"}${place.labelAbove ? " core-orb--label-above" : ""}`}
          style={style}
          onClick={() => onSelect?.(target[branch.key])}
          aria-label={`Open ${branch.name}. ${status}`}
        >
          <ModuleIcon name={branch.key}/>
          <span className="core-orb__plate" aria-hidden="true">
            <strong>{branch.name}</strong>
            <small>{branch.description}</small>
            {underIcon(branch.key)
              ? <em className={`core-orb__plate-status core-orb__plate-status--${underIcon(branch.key)!.tone}`}><i aria-hidden="true"/>{underIcon(branch.key)!.text}</em>
              : <em>{status}</em>}
          </span>
        </button>;
      })}
    </>}
  </div>;
}
