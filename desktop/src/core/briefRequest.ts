/**
 * Asking for the brief by words (Grey, 2026-11-04): the top-right "Brief me" button is gone, so "give me the on the road
 * brief", "brief on the road", "road brief", "drive briefing", "brief me" and the like start the same briefing the
 * button used to (calendar, weather and traffic, read aloud). Short, direct requests only: "write a brief summary of
 * this file" is not one.
 */
const LEAD = String.raw`^(?:(?:hey|ok|okay)\s+)?(?:(?:zae|zay|zaenia)[,\s]+)?(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?`;
const ROAD = String.raw`(?:on[\s-]+the[\s-]+road|for\s+the\s+road|road|driving|drive|carplay|commute|commuting|on[\s-]+the[\s-]+go)`;
const ASK = String.raw`(?:(?:give|get|read|play|pull\s+up|run|start|do|send|tell)(?:\s+me)?\s+|let(?:'s|\s+me)\s+(?:hear|get)\s+)?`;
const THE = String.raw`(?:(?:my|the|a|an|today's|todays)\s+)*`;

const PATTERNS = [
  // "(give me) the on the road brief", "road briefing", "drive brief please"
  new RegExp(LEAD + ASK + THE + ROAD + String.raw`\s+brief(?:ing)?(?:\s+(?:please|now))?$`, "i"),
  // "brief me on the road", "brief on the road", "brief me for the road"
  new RegExp(LEAD + String.raw`brief(?:\s+me)?\s+` + ROAD + String.raw`(?:\s+(?:please|now))?$`, "i"),
  // "brief me", "give me my brief", "give me the briefing", "morning brief"
  new RegExp(LEAD + String.raw`(?:brief\s+me|` + ASK + THE + String.raw`(?:morning\s+|daily\s+)?brief(?:ing)?)(?:\s+(?:please|now))?$`, "i"),
];

export function isBriefRequest(text: string): boolean {
  const clean = text.trim().replace(/[.!?]+$/, "");
  return clean.length > 0 && clean.length <= 70 && PATTERNS.some(pattern => pattern.test(clean));
}

/** The window event the briefing panel listens for. */
export const BRIEF_EVENT = "zae:brief";
