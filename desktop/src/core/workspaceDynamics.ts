export type WorkspacePhase = "idle" | "listening" | "thinking" | "speaking";
export type WorkspaceSettings = { adaptive: boolean; conversationVh: number };
export const DEFAULT_WORKSPACE: WorkspaceSettings = { adaptive: true, conversationVh: 36 };

/** Keep saved or manually adjusted sizes inside a usable core/chat split. */
export function boundedConversationSize(value: number): number {
  return Number.isFinite(value) ? Math.min(58, Math.max(26, Math.round(value))) : 36;
}

export function parseWorkspaceSettings(value: string | null): WorkspaceSettings {
  if (value === null) return { ...DEFAULT_WORKSPACE };
  try {
    const saved: unknown = JSON.parse(value);
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) return { ...DEFAULT_WORKSPACE };
    const record = saved as Record<string, unknown>;
    return {
      adaptive: typeof record.adaptive === "boolean" ? record.adaptive : true,
      conversationVh: typeof record.conversationVh === "number" ? boundedConversationSize(record.conversationVh) : 36,
    };
  } catch { return { ...DEFAULT_WORKSPACE }; }
}

/** Only actual activity changes the display; enabling a microphone alone does not. */
export function workspacePhase(state: {
  hearing?: boolean; transcribing?: boolean; sending?: boolean; speaking?: boolean; preparingSpeech?: boolean;
}): WorkspacePhase {
  if (state.hearing) return "listening";
  if (state.speaking) return "speaking";
  if (state.transcribing || state.sending || state.preparingSpeech) return "thinking";
  return "idle";
}

export function workspaceLayout(settings: WorkspaceSettings, phase: WorkspacePhase, focused: boolean, animate: boolean) {
  const base = boundedConversationSize(settings.conversationVh);
  const adaptive = settings.adaptive && animate;
  const lift = adaptive ? ({ idle: 0, listening: 4, thinking: 10, speaking: 7 }[phase]) : 0;
  return {
    conversationVh: boundedConversationSize(base + Math.max(lift, adaptive && focused ? 10 : 0)),
    coreScale: adaptive ? ({ idle: 1, listening: 1.025, thinking: 0.975, speaking: 1.015 }[phase]) : 1,
    coreShift: adaptive && phase !== "idle" ? -3 : 0,
  };
}
