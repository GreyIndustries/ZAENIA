/**
 * Appearance options: font, text size, accent colour and glow. Accent colours
 * re-tint the whole interface (core included) from its amber design, so every
 * theme keeps the same look in a different colour. Saved on this device only.
 */
export type FontChoice = "default" | "segoe" | "bahnschrift" | "mono" | "serif";
export type AccentChoice = "amber" | "gold" | "crimson" | "violet" | "blue" | "cyan" | "emerald" | "ice";
export type Appearance = { font: FontChoice; size: number; accent: AccentChoice; glow: number };

export const DEFAULT_APPEARANCE: Appearance = { font: "default", size: 100, accent: "amber", glow: 100 };

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
];

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
  if (!/\b(?:colou?r|theme|accent|font|text|glow)\b/.test(text) && !/^(?:\w+[, ]+)?make (?:it|everything|the ui|the app|zae) \w+(?: please)?[.!]?$/.test(text.trim())) return null;
  const next = { ...current };
  let changed = false;
  for (const accent of ACCENTS) {
    const words = accent.label.toLowerCase().split(" ")[0];
    if (new RegExp(`\\b${words}\\b`).test(text) || (accent.id === "ice" && /\bwhite\b/.test(text)) || (accent.id === "crimson" && /\bred\b/.test(text))
      || (accent.id === "emerald" && /\bgreen\b/.test(text)) || (accent.id === "violet" && /\bpurple\b/.test(text)) || (accent.id === "amber" && /\b(?:orange|default colou?r)\b/.test(text))) {
      next.accent = accent.id; changed = true; break;
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
  return changed ? next : null;
}
