/**
 * Custom hand shortcuts (Grey, 2026-11-05): pick a hand shape and type what it should do. The typed text is sent to ZAE
 * exactly as if it were typed in chat, so every normal approval still applies; the camera can't tell whose hand it is.
 * Saved on this PC only. Pure logic: no camera, no DOM.
 */
export type CustomShape = "one" | "two" | "three" | "rock" | "fist" | "peace" | "thumbsUp" | "thumbsDown";
export type CustomShortcut = { shape: CustomShape; text: string };

/** Shapes that don't clash with the fixed gestures: open palm stops speech, an open hand swipes, a pinch grabs. */
export const CUSTOM_SHAPES: { id: CustomShape; name: string }[] = [
  { id: "one", name: "One finger" }, { id: "two", name: "Two fingers" }, { id: "three", name: "Three fingers" },
  { id: "rock", name: "Rock sign" }, { id: "fist", name: "Fist" }, { id: "peace", name: "Peace sign" },
  { id: "thumbsUp", name: "Thumbs up" }, { id: "thumbsDown", name: "Thumbs down" },
];
export const SHORTCUTS_KEY = "zaenia.handShortcuts";
export const SHORTCUTS_EVENT = "zae:hand-shortcuts";
export const MAX_TEXT = 160;

const known = new Set<string>(CUSTOM_SHAPES.map(shape => shape.id));
/** Plain text only: control characters out, spaces tidied, cut to MAX_TEXT. */
export const cleanText = (value: unknown): string => typeof value === "string" ? value.replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, MAX_TEXT) : "";

/** A saved list made safe: known shapes only, one shortcut per shape (the first wins), no empty text. */
export function normalizeShortcuts(raw: unknown): CustomShortcut[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>(), out: CustomShortcut[] = [];
  for (const item of raw) {
    const shape = item && typeof item === "object" ? (item as { shape?: unknown }).shape : undefined;
    const text = cleanText(item && typeof item === "object" ? (item as { text?: unknown }).text : "");
    if (typeof shape !== "string" || !known.has(shape) || seen.has(shape) || !text) continue;
    seen.add(shape); out.push({ shape: shape as CustomShape, text });
  }
  return out;
}

/** Adds or replaces the shortcut for a shape. */
export function withShortcut(list: CustomShortcut[], shape: CustomShape, text: string): CustomShortcut[] {
  return normalizeShortcuts([{ shape, text }, ...list.filter(item => item.shape !== shape)]);
}
export const withoutShortcut = (list: CustomShortcut[], shape: CustomShape): CustomShortcut[] => list.filter(item => item.shape !== shape);

export function readShortcuts(): CustomShortcut[] {
  try { return normalizeShortcuts(JSON.parse(localStorage.getItem(SHORTCUTS_KEY) ?? "null")); } catch { return []; }
}
export function saveShortcuts(list: CustomShortcut[]) {
  try { localStorage.setItem(SHORTCUTS_KEY, JSON.stringify(normalizeShortcuts(list))); } catch { /* optional preference */ }
  window.dispatchEvent(new Event(SHORTCUTS_EVENT));
}
