/**
 * Grey's wake-up calls and sleep phrases (2026-10-30). Wake-up calls only count by voice (the app mic, or the PC voice
 * through core/voice_listener/calm_state.py, which keeps a copy of these lists), after the turn has been checked as Grey's voice; sleep phrases work spoken or typed. Matching allows small wording changes but not
 * long sentences that merely contain the words, so normal conversation doesn't trigger them.
 */
export type CalmPhrase = { kind: "wake" | "sleep"; id: number; phrase: string };

export const WAKE_CALLS = [
  ["wake up sleepy we have work to do", "wake up sleepy we got work to do", "wake up sleepy"],
  ["sleeping on the job"],
  ["the boss is here", "boss is here"],
  ["zae you're still there", "zae are you still there", "you still there zae"],
  ["day is not yet over", "the day is not over yet", "the night is still young", "night is still young"],
] as const;

export const SLEEP_PHRASES = [
  ["take everything to the background", "take it all to the background"],
  ["i'm going to sleep", "i am going to sleep", "going to sleep"],
  ["let's put a pin in this and continue tomorrow", "put a pin in this and continue tomorrow", "let's put a pin in this"],
  ["calm view", "go to calm view", "calm mode"],
] as const;

const NAMES = /\b(?:zae|zay|zai|zeh|zaenia|xenia|zania)\b/g;

export function normalize(text: string): string {
  return text.toLowerCase().replace(/[’']/g, "'").replace(/\bi am\b/g, "i'm").replace(/\blet us\b/g, "let's")
    .replace(/[^a-z0-9' ]+/g, " ").replace(/\s+/g, " ").trim();
}

function close(said: string, phrase: string): boolean {
  const words = said.replace(NAMES, " ").replace(/\b(?:hey|ok|okay|so|well|um|uh|yo)\b/g, " ").replace(/\s+/g, " ").trim().split(" ").filter(Boolean);
  const target = phrase.replace(NAMES, " ").replace(/\s+/g, " ").trim().split(" ").filter(Boolean);
  if (!target.length || words.length > target.length + 3) return false;
  const have = new Set(words);
  const hits = target.filter(word => have.has(word)).length;
  return hits / target.length >= (target.length <= 3 ? 1 : 0.8);
}

/** The wake-up call or sleep phrase in what Grey said or typed, or null. */
export function matchCalmPhrase(text: string): CalmPhrase | null {
  const said = normalize(text);
  if (!said) return null;
  for (const [kind, list] of [["wake", WAKE_CALLS], ["sleep", SLEEP_PHRASES]] as const) {
    for (let id = 0; id < list.length; id++) {
      if (list[id].some(phrase => close(said, normalize(phrase)))) return { kind, id: id + 1, phrase: list[id][0] };
    }
  }
  return null;
}

/** Words that may mean "rest now" (kept in step with SLEEP_CUE in core/voice_listener/calm_state.py); the server's
 *  Talk model decides whether the sentence really is a sleep request. */
export const SLEEP_CUE = /\b(?:sleep|bed|good ?night|nap|background|rest|calm|pin in|call it a (?:day|night)|that'?s (?:all|it) for (?:now|today|tonight)|take a break|signing off|done for (?:the day|today|tonight)|stand ?by|power down|shut ?down for)\b/i;
