/**
 * Spoken or typed layout commands, run instantly by the app (no model call):
 * "open my calendar", "shrink and put it in the left corner",
 * "move tasks to the right", "clear the workspace", "hide the sidebar".
 */
export type LayoutTarget = "status" | "tasks" | "calendar" | "assistant" | "files" | "system" | "core" | "focused" | "notes" | "news";
export type Spot = "left" | "right" | "top" | "bottom" | "top-left" | "top-right" | "bottom-left" | "bottom-right" | "center";
export type LayoutAction =
  | { kind: "open"; target: LayoutTarget }
  | { kind: "close"; target: LayoutTarget | "all" }
  | { kind: "minimize"; target: LayoutTarget | "all" }
  | { kind: "restore"; target: LayoutTarget | "all" }
  | { kind: "maximize"; target: LayoutTarget }
  | { kind: "place"; target: LayoutTarget; spot: Spot; small: boolean }
  | { kind: "size"; target: LayoutTarget; grow: boolean; axis?: "width" | "height" }
  | { kind: "sidebar"; show: boolean }
  | { kind: "clear" };

const TARGETS: [RegExp, LayoutTarget][] = [
  [/\b(?:notes?|notebook)\b/, 'notes'],
  [/\b(?:news|headlines)\b/, 'news'],
  [/\b(?:system status|status|health|diagnostics?)\b/, "status"],
  [/\b(?:tasks?|to-?dos?|task list)\b/, "tasks"],
  [/\b(?:calendar|schedule|agenda|events?)\b/, "calendar"],
  [/\b(?:assistant|memory|memories|follow.?through|inbox)\b/, "assistant"],
  [/\b(?:files?|folders?|code)\b/, "files"],
  [/\b(?:system|settings|preferences)\b/, "system"],
  [/\b(?:core|sphere|orb|neural core|you|yourself)\b/, "core"],
];
const SPOTS: [RegExp, Spot][] = [
  [/\b(?:(?:top|upper)[ -]left|left[ -](?:top|upper))\b/, "top-left"], [/\b(?:(?:top|upper)[ -]right|right[ -](?:top|upper))\b/, "top-right"],
  [/\b(?:(?:bottom|lower)[ -]left|left[ -](?:bottom|lower))\b/, "bottom-left"], [/\b(?:(?:bottom|lower)[ -]right|right[ -](?:bottom|lower))\b/, "bottom-right"],
  [/\bleft corner\b/, "top-left"], [/\bright corner\b/, "top-right"],
  [/\b(?:center|centre|middle)\b/, "center"],
  [/\bleft\b/, "left"], [/\bright\b/, "right"], [/\btop\b/, "top"], [/\bbottom\b/, "bottom"],
];

const clean = (text: string) => text.toLowerCase().replace(/[’‘]/g, "'").replace(/[^\p{L}\p{N}' -]+/gu, " ").replace(/\s+/g, " ").trim()
  // Politeness and her name don't change the command.
  .replace(/^(?:(?:hey |okay |ok )?(?:zae|zay|zaenia|zænia)[, ]*)?(?:(?:can|could|would|will) you |please |go ahead and |just )*/, "")
  .replace(/ (?:please|for me)$/, "")
  .replace(/\b(?:the )?(?:tab|window|panel|one) (?:i'm|i am) (?:working on|looking at|using)\b/g, "it")
  .replace(/\b(?:the )?(?:active|current|focused) (?:tab|window|panel)\b/g, "it")
  .replace(/\b(?:this|that) (?:tab|window|panel)\b/g, "it")
  .replace(/^get rid of (it|this|that)$/, "close $1")
  .replace(/^shut (?!down\b)/, "close ")
  .replace(/^tuck (it|this|that) away$/, "minimize $1")
  .replace(/^put (it|this|that) out of the way$/, "minimize $1")
  .replace(/^put (all(?: (?:the |my )?(?:tabs|windows|panels))?) away$/, "minimize $1")
  .replace(/^bring (all(?: (?:the |my )?(?:tabs|windows|panels))?|everything) back$/, "restore $1")
  .replace(/\bevery (?:tab|window|panel)\b/g, "all tabs")
  .replace(/\ball of them\b/g, "all");

function targetIn(text: string): LayoutTarget | null {
  for (const [pattern, target] of TARGETS) if (pattern.test(text)) return target;
  return null;
}
function spotIn(text: string): Spot | null {
  for (const [pattern, spot] of SPOTS) if (pattern.test(text)) return spot;
  return null;
}

/** The layout actions in a sentence, or null when it isn't a layout command. */
export function parseLayoutCommand(input: string): LayoutAction[] | null {
  const text = clean(input);
  if (!text || text.split(" ").length > 16) return null;
  const target = targetIn(text);
  const spot = spotIn(text);
  if (/^(?:hide|close|collapse) (?:the )?(?:sidebar|side bar|menu|navigation)\b/.test(text)) return [{ kind: "sidebar", show: false }];
  if (/^(?:show|open|bring back) (?:the )?(?:sidebar|side bar|menu|navigation)\b/.test(text)) return [{ kind: "sidebar", show: true }];
  if (/^(?:close|minimi[sz]e|hide|restore) (?:all|everything)(?: (?:the |my )?(?:tabs|windows|panels))?$/.test(text))
    return [{ kind: /^close/.test(text) ? "close" : /^restore/.test(text) ? "restore" : "minimize", target: "all" }];
  if (/^(?:close|minimi[sz]e|hide|restore) all\b/.test(text)) return null; // Do not ignore exceptions such as "except Calendar".
  if (/^restore(?: (?:it|this|that))?$/.test(text)) return [{ kind: "restore", target: "focused" }];
  if (/^(?:clear|clean up|tidy)(?: up)? (?:the |my )?(?:workspace|screen|desktop|everything|windows?)$/.test(text)) return [{ kind: "clear" }];
  if (/^(?:open|show|pull up|bring up|bring|go to|switch to|take me to|let me see)\b/.test(text) && target && target !== "core" && !spot) {
    return [{ kind: "open", target }];
  }
  if (/^close\b/.test(text) && (target || /^close(?: (?:it|this|that|the active tab|the current tab|this tab|that tab|this window|that window))?$/.test(text)))
    return [{ kind: "close", target: !target || target === "core" ? "focused" : target }];
  if (/^(?:minimi[sz]e|hide|put away)\b/.test(text)) return [{ kind: "minimize", target: target ?? "focused" }];
  if (/^(?:maximi[sz]e|full ?screen|make (?:it|that|this|\w+) full ?screen)\b/.test(text)) return [{ kind: "maximize", target: target ?? "focused" }];
  const shrink = /\b(?:shrink|smaller|minify|tiny|compact|narrower|shorter)\b/.test(text);
  const grow = /\b(?:enlarge|bigger|larger|expand|grow|wider|taller)\b/.test(text);
  const move = /\b(?:move|put|place|dock|send|push|drag)\b/.test(text) || (shrink && Boolean(spot));
  if (move && spot) return [{ kind: "place", target: target ?? "focused", spot, small: shrink || /\bcorner\b/.test(text) }];
  if ((shrink || grow) && /^(?:shrink|make|enlarge|expand|grow)\b/.test(text)) {
    const axis = /\b(?:wider|narrower)\b/.test(text) ? "width" : /\b(?:taller|shorter)\b/.test(text) ? "height" : undefined;
    return [{ kind: "size", target: target ?? "focused", grow, ...(axis ? { axis } : {}) }];
  }
  return null;
}

/** A short spoken/visible acknowledgement, in ZAE's voice. */
export function layoutAck(actions: LayoutAction[], titles: Record<string, string>): string {
  const action = actions[0];
  if (!action) return "There isn't an open tab to change.";
  const name = (target: string) => target === "core" ? "the core" : titles[target] ?? "that window";
  switch (action.kind) {
    case "open": return `Opened ${titles[action.target] ?? "it"}.`;
    case "close": return action.target === "all" ? "Closed everything, sir." : `Closed ${name(action.target)}.`;
    case "minimize": return action.target === "all" ? "Cleared." : "Tucked away.";
    case "restore": return action.target === "all" ? "Restored all tabs." : `Restored ${name(action.target)}.`;
    case "maximize": return "Full screen.";
    case "place": return `Moved ${action.target === "focused" ? "it" : name(action.target)} ${action.spot === "center" ? "to the center" : `to the ${action.spot.replace("-", " ")}`}.`;
    case "size": return action.axis === "width" ? action.grow ? "Wider." : "Narrower." : action.axis === "height" ? action.grow ? "Taller." : "Shorter." : action.grow ? "Larger." : "Smaller.";
    case "sidebar": return action.show ? "Sidebar's back." : "Sidebar hidden.";
    case "clear": return "Workspace cleared, sir.";
  }
}
