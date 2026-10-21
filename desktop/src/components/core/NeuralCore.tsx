import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { nodeWakeLevel } from "../../core/coreWake";
import type { CoreTelemetry, ModulePhase } from "../../core/coreTelemetry";
import { BRANCHES, computeLayout, createNeuralField } from "./neuralField";
import type { BranchKey, FieldLayout, NeuralField, VoicePhase } from "./neuralField";
import "./NeuralCore.css";

type Section = "status" | "tasks" | "calendar" | "files" | "system";
type Props = {
  telemetry: CoreTelemetry | null;
  source: "preview" | "local";
  motion: boolean;
  processing?: boolean;
  startup: { progress: number; ready: boolean };
  onSelect?: (section: Section) => void;
  /** Live assistant state; the core listens, thinks and speaks visibly. */
  phase?: VoicePhase;
  /** When the no-name follow-up window closes (ms since epoch), or 0. */
  followUntil?: () => number;
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
  security: "status", calendar: "calendar", status: "status", files: "files", tasks: "tasks", system: "system",
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
export function NeuralCore({ telemetry, source, motion, processing = false, startup, onSelect, phase = "idle", followUntil }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fieldRef = useRef<NeuralField | null>(null);
  const [layout, setLayout] = useState<FieldLayout | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const reduced = usePrefersReducedMotion();
  const animate = motion && !reduced;

  useEffect(() => {
    const wrap = wrapRef.current, canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const field = createNeuralField(canvas);
    if (!field) { setUnavailable(true); return; }
    fieldRef.current = field;
    const measure = () => {
      const box = wrap.getBoundingClientRect();
      if (box.width < 40 || box.height < 40) return;
      const next = computeLayout(box.width, box.height);
      field.setLayout(next);
      setLayout(next);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(wrap);
    measure();
    return () => { observer.disconnect(); field.destroy(); fieldRef.current = null; };
  }, []);

  useEffect(() => {
    fieldRef.current?.setState({ progress: startup.progress, motion: animate, processing, phase });
  }, [startup.progress, animate, processing, phase, layout]);
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
    return (detail ?? "").split(/s+/).filter(Boolean).slice(0, 2).join(" ") || "Protected locally";
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
    className={`neural-core neural-core--${phase} ${layout?.compact ? "neural-core--compact" : ""} ${processing ? "neural-core--processing" : ""}`}
    role="group"
    aria-label={`ZÆNIA neural core with six connected modules. ${source === "preview" ? "Module statuses are illustrative preview data." : "Module statuses reflect available local telemetry."}`}
  >
    <canvas ref={canvasRef} className="neural-core__canvas" aria-hidden="true"/>
    {unavailable && <div className="neural-core__fallback">Core visual unavailable. Module navigation remains available.</div>}
    {layout && <>
      <div className={`core-boot ${startup.ready ? "core-boot--done" : ""}`} style={{ left: layout.cx, top: layout.cy }} aria-hidden="true">
        <strong>{startup.progress}</strong>
        <span>INITIALISING</span>
      </div>
      {startup.ready && <>
        <svg className={`core-hud${animate ? " core-hud--motion" : ""}`} style={{ left: layout.cx, top: layout.cy, width: layout.r * 2.56, height: layout.r * 2.56 }} viewBox="0 0 200 200" aria-hidden="true">
          <circle className="core-hud__ticks" cx="100" cy="100" r="97"/>
          <circle className="core-hud__segments" cx="100" cy="100" r="92"/>
          {following && <circle className="core-hud__follow" cx="100" cy="100" r="88" pathLength="100" strokeDasharray={`${(followLeft / 30000 * 100).toFixed(2)} 100`}/>}
        </svg>
        <div className="core-state" role="status" aria-live="polite" style={{ left: layout.cx, top: layout.cy + layout.r * (layout.compact ? 1.04 : 1.2) }}>
          <i aria-hidden="true"/>{following ? <>FOLLOW-UP OPEN <small>{Math.ceil(followLeft / 1000)}s · no name needed</small></> : phaseCopy[phase]}
        </div>
      </>}
      {BRANCHES.map((branch, index) => {
        const place = layout.orbs[index];
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
