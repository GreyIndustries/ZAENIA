/** Bounded, device-local work metadata. Never store input values, document bodies, audio or credentials. */
export type PageActivity = { key: string; app: string; navigator: string; page: string; label: string; subject: string; action: "edited" | "used"; at: number };
export const PAGE_ACTIVITY_KEY = "zaenia.pageActivity.v1";
const OFFER_KEY = "zaenia.resumeOffers.v1";
const MAX_AGE = 90 * 864e5;
const id = (value: unknown): value is string => typeof value === "string" && /^[a-z][a-z0-9-]{0,39}$/i.test(value);
const text = (value: unknown, max = 120): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= max && !/[\r\n\x00-\x1f]/.test(value);
export function normalizeActivities(value: unknown, now = Date.now()): PageActivity[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.filter((item): item is PageActivity => !!item && typeof item === "object" && id(item.app) && id(item.navigator) && id(item.page)
    && item.key === `${item.app}/${item.navigator}/${item.page}` && text(item.label) && text(item.subject)
    && ["edited", "used"].includes(item.action) && Number.isFinite(item.at) && item.at <= now && item.at > now - MAX_AGE)
    .sort((a, b) => b.at - a.at).filter(item => { if (seen.has(item.key)) return false; seen.add(item.key); return true; }).slice(0, 100)
    .map(({ key, app, navigator, page, label, subject, action, at }) => ({ key, app, navigator, page, label, subject, action, at }));
}
export function readPageActivities(): PageActivity[] {
  try { return normalizeActivities(JSON.parse(localStorage.getItem(PAGE_ACTIVITY_KEY) ?? "[]")); } catch { return []; }
}
export function recordPageActivity(activity: PageActivity) {
  const records = normalizeActivities([activity, ...readPageActivities()]);
  try { localStorage.setItem(PAGE_ACTIVITY_KEY, JSON.stringify(records)); } catch { /* optional */ }
  window.dispatchEvent(new Event("zae:page-activity"));
}
export function clearPageActivities() {
  try { localStorage.removeItem(PAGE_ACTIVITY_KEY); localStorage.removeItem(OFFER_KEY); } catch { /* optional */ }
  window.dispatchEvent(new Event("zae:page-activity-cleared"));
}
export function activityLine(activity: PageActivity) { return `You were recently working on ${activity.subject}, sir.`; }
export function resumeQuestion(activity: PageActivity) { return `${activityLine(activity)} Would you want to continue?`; }
export type ResumeAnswer = "continue" | "later" | "dismiss" | "finished";
export function parseResumeAnswer(input: string): ResumeAnswer | null {
  const words = input.toLowerCase().replace(/[’']/g, "").replace(/[.,!?]/g, "").replace(/^(?:zae|zaenia|zay)[, ]+/, "").trim().replace(/^(?:no|no thanks|not now|not right now) (?=(?:i|im|ill|lets)\b)/, "");
  if (/^(?:yes|yeah|yep|sure|okay|ok)(?: (?:please|continue|lets continue|resume|do that|go ahead))?$|^(?:continue|resume|lets continue|pick up where we left off)(?: please)?$/.test(words)) return "continue";
  if (/^(?:dont|do not|stop) (?:ask|asking)(?: me)?(?: about (?:that|this|it))?(?: again| anymore)?$|^never ask(?: me)?(?: about (?:that|this|it))? again$/.test(words)) return "dismiss";
  if (/^(?:i (?:already )?(?:finished|completed|did) (?:it|that|this)|(?:its|thats) (?:already )?(?:done|finished)|already done)$/.test(words)) return "finished";
  if (/^(?:no|no thanks|not now|not right now|maybe later|later|another time|some other time|not interested right now|tomorrow|put that aside|skip for now|leave it for (?:now|later)|skip (?:it|that|this)|im (?:busy|doing something else|working on something else)|i(?:ll| will| want to) (?:do|finish|work on|get to) (?:it|that|this) (?:later|tomorrow|another time)|lets do (?:it|that|this) later)(?: please| thanks)?$/.test(words)) return "later";
  if (/^(?:no|im|i(?:ll| will| need| have)|lets|maybe|not|put|skip|hold)/.test(words)
    && /\b(?:later|not (?:right )?now|another time|after (?:class|school|work|duty|dinner|lunch|the gym)|busy|something else|hold (?:off|that))\b/.test(words)
    && !/\b(?:remind|schedule|delete|send|open|press|set)\b/.test(words)) return "later";
  return null;
}
type Offer = { fingerprint: string; state: "asked" | ResumeAnswer; until: number; at: number };
const fingerprint = (activity: PageActivity) => `${activity.key}:${activity.subject}`;
function offers(): Record<string, Offer> {
  try {
    const value = JSON.parse(localStorage.getItem(OFFER_KEY) ?? "{}");
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([key, raw]) => {
      const item = raw as Offer;
      return text(key, 122) && item && text(item.fingerprint, 300) && ["asked","continue","later","dismiss","finished"].includes(item.state)
        && Number.isFinite(item.until) && Number.isFinite(item.at) && item.at > Date.now() - MAX_AGE;
    }).slice(-100)) as Record<string, Offer>;
  } catch { return {}; }
}
export class ResumeOffers {
  pending: { activity: PageActivity; expires: number } | null = null;
  private asked = new Set<string>();
  offer(activity: PageActivity, now = Date.now()): string | null {
    const token = fingerprint(activity); const previous = offers()[activity.key];
    if (this.asked.has(token) || (previous?.fingerprint === token && previous.until > now)) return null;
    this.asked.add(token); this.pending = { activity, expires: now + 90_000 };
    this.save(activity, "asked", now + MAX_AGE, now); return resumeQuestion(activity);
  }
  answer(input: string, now = Date.now()): { answer: ResumeAnswer; activity: PageActivity; reply: string } | null {
    if (!this.pending || this.pending.expires < now) { this.pending = null; return null; }
    const answer = parseResumeAnswer(input); if (!answer) return null;
    const activity = this.pending.activity; this.pending = null;
    this.save(activity, answer, answer === "later" ? now + 864e5 : now + MAX_AGE, now);
    return { answer, activity, reply: answer === "continue" ? "Continuing that work, sir."
      : answer === "later" ? "Understood, sir. I'll leave that for later."
      : answer === "finished" ? "Understood, sir. I won't offer to resume that activity."
      : "Understood, sir. I won't ask again about that activity." };
  }
  clearPending() { this.pending = null; }
  reset() { this.pending = null; this.asked.clear(); }
  private save(activity: PageActivity, state: Offer["state"], until: number, at: number) {
    const records = offers(); delete records[activity.key];
    records[activity.key] = { fingerprint: fingerprint(activity), state, until, at };
    try { localStorage.setItem(OFFER_KEY, JSON.stringify(Object.fromEntries(Object.entries(records).slice(-100)))); } catch { /* optional */ }
  }
}
