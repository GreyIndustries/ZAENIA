import { AMBER, RED, SLATE, TEAL, type RGB } from "./engine";

export type Strength = "strong" | "fair" | "weak" | "unknown";
/** Teal strong, amber fair, red weak, grey not measured. */
export const LEVEL_COLOR: Record<Strength, RGB> = { strong: TEAL, fair: AMBER, weak: RED, unknown: SLATE };
