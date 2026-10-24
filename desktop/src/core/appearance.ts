/**
 * Appearance options: font, text size, accent colour and glow. Accent colours
 * re-tint the whole interface (core included) from its amber design, so every
 * theme keeps the same look in a different colour. Saved on this device only.
 */
export type FontChoice = "default" | "segoe" | "bahnschrift" | "mono" | "serif";
export type AccentChoice = "amber" | "gold" | "crimson" | "violet" | "blue" | "cyan" | "emerald" | "ice"
  | "tangerine" | "sunset" | "coral" | "scarlet" | "ruby" | "rose" | "pink" | "magenta" | "orchid" | "plum" | "lavender" | "indigo"
  | "sapphire" | "ocean" | "sky" | "aqua" | "teal" | "mint" | "forest" | "lime" | "chartreuse" | "lemon" | "copper" | "bronze"
  | "sand" | "slate" | "silver";
export type LookChoice = "aurora" | "hud" | "editorial" | "neon";
/** One module window's own style and colour; anything unset follows the app-wide choice. */
export type TabStyle = { look?: LookChoice; color?: AccentChoice };
export type TabId = "status" | "tasks" | "calendar" | "notes" | "assistant" | "files" | "system" | "news";
export type Appearance = { font: FontChoice; size: number; accent: AccentChoice; glow: number; look: LookChoice; tabs: Partial<Record<TabId, TabStyle>>;
  /** The six icons around the core: amber and blue ("mixed"), or all in the accent colour ("match"). */
  orbs: "mixed" | "match" };

export const DEFAULT_APPEARANCE: Appearance = { font: "default", size: 100, accent: "amber", glow: 100, look: "aurora", tabs: {}, orbs: "mixed" };

export const TABS: { id: TabId; label: string }[] = [
  { id: "status", label: "Status" }, { id: "tasks", label: "Tasks" }, { id: "calendar", label: "Calendar" }, { id: "notes", label: "Notes" },
  { id: "assistant", label: "Assistant" }, { id: "files", label: "Files" }, { id: "system", label: "System" }, { id: "news", label: "Tech News" },
];

/** Window styles for every module (Tech News included). */
export const LOOKS: { id: LookChoice; label: string; note: string }[] = [
  { id: "aurora", label: "Aurora glass", note: "Frosted panels, glowing banners, soft colour" },
  { id: "hud", label: "Holo HUD", note: "Jarvis-style lines, corner brackets, scanlines" },
  { id: "editorial", label: "Midnight editorial", note: "Magazine headlines, solid dark cards" },
  { id: "neon", label: "Neon bento", note: "Bold colour tiles with neon edges" },
];

export const FONTS: { id: FontChoice; label: string; stack: string }[] = [
  { id: "default", label: "Inter (default)", stack: 'Inter, "Segoe UI", system-ui, sans-serif' },
  { id: "segoe", label: "Segoe UI", stack: '"Segoe UI Variable", "Segoe UI", system-ui, sans-serif' },
  { id: "bahnschrift", label: "Bahnschrift (tech)", stack: 'Bahnschrift, "DIN Alternate", "Segoe UI", sans-serif' },
  { id: "mono", label: "Cascadia Mono", stack: '"Cascadia Mono", "Cascadia Code", Consolas, ui-monospace, monospace' },
  { id: "serif", label: "Georgia (serif)", stack: 'Georgia, Cambria, "Times New Roman", serif' },
];

/** Hue shift from the amber original, plus saturation for the near-white theme. */
export const ACCENTS: { id: AccentChoice; label: string; swatch: string; shift: number; saturate: number }[] = [
  { id: "amber", label: "Amber", swatch: "#ffb347", shift: 0, saturate: 1 },
  { id: "gold", label: "Gold", swatch: "#ffd55a", shift: 12, saturate: 1 },
  { id: "crimson", label: "Crimson", swatch: "#ff5a5a", shift: -32, saturate: 1.1 },
  { id: "violet", label: "Violet", swatch: "#b47cff", shift: 235, saturate: 1 },
  { id: "blue", label: "Blue", swatch: "#5aa2ff", shift: 185, saturate: 1 },
  { id: "cyan", label: "Cyan", swatch: "#44e0ff", shift: 155, saturate: 1 },
  { id: "emerald", label: "Emerald", swatch: "#4fe39a", shift: 110, saturate: 0.95 },
  { id: "ice", label: "Ice white", swatch: "#dfeaf5", shift: 175, saturate: 0.25 },
  { id: "tangerine", label: "Tangerine", swatch: "#ff9440", shift: -10, saturate: 1.05 },
  { id: "sunset", label: "Sunset", swatch: "#ff7a4d", shift: -20, saturate: 1.05 },
  { id: "coral", label: "Coral", swatch: "#ff7f6e", shift: -26, saturate: 0.9 },
  { id: "scarlet", label: "Scarlet", swatch: "#ff3b3b", shift: -36, saturate: 1.25 },
  { id: "ruby", label: "Ruby", swatch: "#e8325e", shift: -50, saturate: 1.15 },
  { id: "rose", label: "Rose", swatch: "#ff6f9d", shift: -58, saturate: 0.95 },
  { id: "pink", label: "Pink", swatch: "#ff8fd0", shift: -75, saturate: 0.85 },
  { id: "magenta", label: "Magenta", swatch: "#ff4fe0", shift: 272, saturate: 1.15 },
  { id: "orchid", label: "Orchid", swatch: "#d77cf0", shift: 255, saturate: 0.9 },
  { id: "plum", label: "Plum", swatch: "#a35bb8", shift: 250, saturate: 0.7 },
  { id: "lavender", label: "Lavender", swatch: "#b9a8ff", shift: 222, saturate: 0.6 },
  { id: "indigo", label: "Indigo", swatch: "#6d6dff", shift: 205, saturate: 1.1 },
  { id: "sapphire", label: "Sapphire", swatch: "#3f7bff", shift: 192, saturate: 1.2 },
  { id: "ocean", label: "Ocean", swatch: "#2fa4e0", shift: 170, saturate: 1.05 },
  { id: "sky", label: "Sky", swatch: "#8fd0ff", shift: 168, saturate: 0.75 },
  { id: "aqua", label: "Aqua", swatch: "#5ff0e6", shift: 145, saturate: 0.85 },
  { id: "teal", label: "Teal", swatch: "#2fc7b0", shift: 135, saturate: 1 },
  { id: "mint", label: "Mint", swatch: "#9cf5c8", shift: 118, saturate: 0.6 },
  { id: "forest", label: "Forest", swatch: "#3fae5a", shift: 92, saturate: 0.8 },
  { id: "lime", label: "Lime", swatch: "#a8f04a", shift: 55, saturate: 1.05 },
  { id: "chartreuse", label: "Chartreuse", swatch: "#d4f040", shift: 38, saturate: 1 },
  { id: "lemon", label: "Lemon", swatch: "#fff06a", shift: 22, saturate: 0.9 },
  { id: "copper", label: "Copper", swatch: "#d9814f", shift: -14, saturate: 0.75 },
  { id: "bronze", label: "Bronze", swatch: "#c79a5c", shift: -4, saturate: 0.55 },
  { id: "sand", label: "Sand", swatch: "#e6cf9e", shift: 6, saturate: 0.4 },
  { id: "slate", label: "Slate", swatch: "#8fa6c4", shift: 178, saturate: 0.35 },
  { id: "silver", label: "Silver", swatch: "#c9d0d8", shift: 175, saturate: 0.1 },
];

const isLook = (value: unknown): value is LookChoice => LOOKS.some(look => look.id === value);
const isAccent = (value: unknown): value is AccentChoice => ACCENTS.some(accent => accent.id === value);

function parseTabs(raw: unknown): Appearance["tabs"] {
  const tabs: Appearance["tabs"] = {};
  if (!raw || typeof raw !== "object") return tabs;
  for (const tab of TABS) {
    const saved = (raw as Record<string, unknown>)[tab.id] as TabStyle | undefined;
    if (!saved || typeof saved !== "object") continue;
    const style: TabStyle = {};
    if (isLook(saved.look)) style.look = saved.look;
    if (isAccent(saved.color)) style.color = saved.color;
    if (style.look || style.color) tabs[tab.id] = style;
  }
  return tabs;
}

/** The look and colour variables for one module window (its own choice, else the app-wide one). */
export function tabAppearance(appearance: Appearance, id: string): { look: LookChoice; style: Record<string, string> } {
  const own = appearance.tabs[id as TabId] ?? {};
  const color = own.color ? ACCENTS.find(accent => accent.id === own.color) : undefined;
  return {
    look: own.look ?? appearance.look,
    style: color ? { "--accent": color.swatch, "--accent-2": `color-mix(in srgb, ${color.swatch} 45%, white)` } : {},
  };
}

const clampNumber = (value: unknown, low: number, high: number, fallback: number) =>
  typeof value === "number" && Number.isFinite(value) ? Math.min(high, Math.max(low, Math.round(value))) : fallback;

export function parseAppearance(raw: string | null): Appearance {
  if (!raw) return { ...DEFAULT_APPEARANCE };
  try {
    const saved = JSON.parse(raw) as Partial<Appearance>;
    return {
      font: FONTS.some(font => font.id === saved.font) ? saved.font as FontChoice : "default",
      size: clampNumber(saved.size, 85, 125, 100),
      accent: ACCENTS.some(accent => accent.id === saved.accent) ? saved.accent as AccentChoice : "amber",
      glow: clampNumber(saved.glow, 40, 140, 100),
      look: isLook(saved.look) ? saved.look : "aurora",
      tabs: parseTabs(saved.tabs),
      orbs: saved.orbs === "match" ? "match" : "mixed",
    };
  } catch { return { ...DEFAULT_APPEARANCE }; }
}

/** CSS variables for the app root. */
export function appearanceStyle(appearance: Appearance): Record<string, string> {
  const accent = ACCENTS.find(item => item.id === appearance.accent) ?? ACCENTS[0];
  const font = FONTS.find(item => item.id === appearance.font) ?? FONTS[0];
  return {
    "--app-font": font.stack,
    "--app-zoom": String(appearance.size / 100),
    "--accent-shift": `${accent.shift}deg`,
    "--accent-saturate": String(accent.saturate * appearance.glow / 100),
  };
}

/** Spoken/typed appearance changes: "make it blue", "use the mono font", "bigger text". */
export function parseAppearanceCommand(input: string, current: Appearance): Appearance | null {
  const text = input.toLowerCase();
  // Only clear appearance requests: they mention colour/theme/font/text/glow,
  // or are a short "make it blue" style command.
  // "Make the tasks tab blue" changes one window's colour instead of the whole app.
  const tab = TABS.find(item => new RegExp(`\\b${item.label.toLowerCase().split(" ")[0]}\\b (?:tab|window|module|panel)\\b`).test(text));
  if (!tab && !/\b(?:colou?rs?|theme|accent|font|text|glow)\b/.test(text) && !/^(?:\w+[, ]+)?make (?:it|everything|the ui|the app|zae) \w+(?: please)?[.!]?$/.test(text.trim())) return null;
  const next = { ...current };
  let changed = false;
  for (const accent of ACCENTS) {
    const words = accent.label.toLowerCase().split(" ")[0];
    if (new RegExp(`\\b${words}\\b`).test(text) || (accent.id === "ice" && /\bwhite\b/.test(text)) || (accent.id === "crimson" && /\bred\b/.test(text))
      || (accent.id === "emerald" && /\bgreen\b/.test(text)) || (accent.id === "violet" && /\bpurple\b/.test(text)) || (accent.id === "amber" && /\b(?:orange|default colou?r)\b/.test(text))) {
      if (tab) next.tabs = { ...current.tabs, [tab.id]: { ...current.tabs[tab.id], color: accent.id } };
      else next.accent = accent.id;
      changed = true; break;
    }
  }
  if (/\bfont\b/.test(text)) {
    const font = /\bmono|code|terminal\b/.test(text) ? "mono" : /\bserif|georgia\b/.test(text) ? "serif" : /\bbahnschrift|tech\b/.test(text) ? "bahnschrift"
      : /\bsegoe|windows\b/.test(text) ? "segoe" : /\b(?:default|normal|inter)\b/.test(text) ? "default" : null;
    if (font) { next.font = font; changed = true; }
  }
  if (/\b(?:bigger|larger) text\b|\btext (?:bigger|larger)\b/.test(text)) { next.size = Math.min(125, current.size + 10); changed = true; }
  if (/\bsmaller text\b|\btext smaller\b/.test(text)) { next.size = Math.max(85, current.size - 10); changed = true; }
  if (/\b(?:more|brighter|stronger) glow\b/.test(text)) { next.glow = Math.min(140, current.glow + 20); changed = true; }
  if (/\b(?:less|dimmer|softer) glow\b/.test(text)) { next.glow = Math.max(40, current.glow - 20); changed = true; }
  // "Make the core icons the same colour" / "... two colours again".
  if (/\b(?:core |module )?(?:icons?|orbs?)\b/.test(text)) {
    if (/\b(?:same|one|matching|single) colou?r\b|\bmatch\b/.test(text)) { next.orbs = "match"; changed = true; }
    else if (/\b(?:two|different|mixed|original) colou?rs?\b/.test(text)) { next.orbs = "mixed"; changed = true; }
  }
  return changed ? next : null;
}
