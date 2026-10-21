import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { boundedConversationSize, DEFAULT_WORKSPACE, parseWorkspaceSettings, workspaceLayout } from "../../core/workspaceDynamics";
import type { WorkspacePhase, WorkspaceSettings } from "../../core/workspaceDynamics";

const STORAGE_KEY = "zaenia.workspaceLayout";
function readSettings() {
  try { return parseWorkspaceSettings(localStorage.getItem(STORAGE_KEY)); }
  catch { return { ...DEFAULT_WORKSPACE }; }
}

export function useWorkspaceMotion(phase: WorkspacePhase, motion: boolean, ready: boolean) {
  const [settings, setSettings] = useState<WorkspaceSettings>(readSettings);
  const [focused, setFocused] = useState(false);
  const [settledPhase, setSettledPhase] = useState<WorkspacePhase>(phase);
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReduced(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); } catch { /* Optional device-only layout preference. */ }
  }, [settings]);
  useEffect(() => {
    if (phase !== "idle") { setSettledPhase(phase); return; }
    // A short pause between speech clips must not make the panels bounce.
    const timer = window.setTimeout(() => setSettledPhase("idle"), 1400);
    return () => window.clearTimeout(timer);
  }, [phase]);
  const layout = workspaceLayout(settings, settledPhase, focused, motion && ready && !reduced);
  const style = {
    "--workspace-chat-vh": `${layout.conversationVh}dvh`,
    "--workspace-core-scale": layout.coreScale,
    "--workspace-core-shift": `${layout.coreShift}px`,
  } as CSSProperties;
  return {
    settings, style, setFocused,
    phase: settledPhase,
    animate: motion && !reduced,
    toggle: () => setSettings(previous => ({ ...previous, adaptive: !previous.adaptive })),
    resize: (step: number) => setSettings(previous => ({ ...previous, conversationVh: boundedConversationSize(previous.conversationVh + step) })),
    reset: () => { setSettings({ ...DEFAULT_WORKSPACE }); setFocused(false); },
  };
}

export function WorkspaceMotionControls({ settings, toggle, resize, reset }: {
  settings: WorkspaceSettings; toggle: () => void; resize: (step: number) => void; reset: () => void;
}) {
  return <div className="workspace-motion-controls">
    <button className="setting-row" type="button" aria-pressed={settings.adaptive} onClick={toggle}>
      <span className="setting-row__content"><strong>Adaptive workspace</strong><small>Panels move with the conversation</small></span>
      <span className={`switch ${settings.adaptive ? "switch--on" : ""}`} aria-hidden="true"><i/></span>
    </button>
    <div className="workspace-size-controls" role="group" aria-label="Workspace panel sizes">
      <button type="button" onClick={() => resize(-6)} disabled={settings.conversationVh <= 26} title="Give the core more room">Larger core</button>
      <button type="button" onClick={() => resize(6)} disabled={settings.conversationVh >= 58} title="Give the conversation more room">Larger chat</button>
      <button type="button" onClick={reset} title="Restore balanced panel sizes and adaptive workspace">Reset</button>
    </div>
  </div>;
}
