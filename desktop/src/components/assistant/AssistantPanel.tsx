import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./AssistantPanel.css";
import { KnowledgePanel } from './KnowledgePanel';
import { ProfileReview } from './ProfileReview';

type Category = "fact" | "preference" | "goal" | "person" | "commitment";
type Memory = { id: string; key: string; value: string; category: Category; source: string; created_at: string; updated_at: string };
type MemoryDraft = Pick<Memory, "key" | "value" | "category">;
type Insight = { id: string; text: string; kind: string; count: number; first_seen: string; last_seen: string; source?: string; confidence?: string; evidence?: string; stale?: boolean; revision?: number };
type Settings = { enabled: boolean; spoken: boolean; quietHoursEnabled: boolean; quietStart: string; quietEnd: string; timezone: string };
type Notification = {
  id: string; source: string; kind: string; title: string; message: string; occurrence: string;
  dueAt: string; createdAt: string | null; readAt: string | null; snoozedUntil: string | null;
  canInterrupt: boolean; canSpeak: boolean;
};
type Inbox = { notifications: Notification[]; unreadCount: number; settings: Settings; workerRunning: boolean; quiet: boolean };
const CATEGORIES: Category[] = ["fact", "preference", "goal", "person", "commitment"];
const EMPTY_MEMORY: MemoryDraft = { key: "", value: "", category: "fact" };
const PACIFIC = "America/Los_Angeles";
const dateLabel = (value: string | null) => {
  if (!value || !Number.isFinite(Date.parse(value))) return "Time unavailable";
  return new Date(value).toLocaleString(undefined, { timeZone: PACIFIC, month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
};

/** Explicit personal memory and the shared, local follow-through inbox. */
export function AssistantPanel({ refreshVersion = 0, onChanged }: { refreshVersion?: number; onChanged?: () => void }) {
  const [memories, setMemories] = useState<Memory[] | null>(null);
  const [insights, setInsights] = useState<Insight[] | null>(null);
  const [learning, setLearning] = useState(true);
  const [correctingInsight, setCorrectingInsight] = useState<string | null>(null);
  const [insightText, setInsightText] = useState('');
  const [clearAsked, setClearAsked] = useState(false);
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [inboxError, setInboxError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<MemoryDraft>(EMPTY_MEMORY);
  const [forgetId, setForgetId] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [settingsDirty, setSettingsDirty] = useState(false);
  const [showRead, setShowRead] = useState(false);
  const mounted = useRef(true);
  const inFlight = useRef(false);
  const reloadRequested = useRef(false);
  const dirty = useRef(false);
  const valueInput = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(async (): Promise<void> => {
    if (!LIVE_API || inFlight.current) return;
    inFlight.current = true;
    if (mounted.current) setLoading(true);
    try {
      const [memoryReply, inboxReply, insightReply] = await Promise.allSettled([
        api<{ memories: Memory[] }>("GET", "/api/assistant/memory"),
        api<Inbox>("GET", "/api/assistant/notifications?includeRead=true"),
        api<{ insights: Insight[]; enabled: boolean }>("GET", "/api/assistant/insights"),
      ]);
      if (!mounted.current) return;
      if (insightReply.status === "fulfilled") { setInsights(insightReply.value.insights); setLearning(insightReply.value.enabled); }
      if (memoryReply.status === "fulfilled") { setMemories(memoryReply.value.memories); setMemoryError(null); }
      else setMemoryError(errorText(memoryReply.reason));
      if (inboxReply.status === "fulfilled") {
        setInbox(inboxReply.value); setInboxError(null);
        if (!dirty.current) setSettings(inboxReply.value.settings);
      } else setInboxError(errorText(inboxReply.reason));
    } finally {
      inFlight.current = false;
      if (mounted.current) setLoading(false);
      if (mounted.current && reloadRequested.current) { reloadRequested.current = false; void load(); }
    }
  }, []);

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (inFlight.current) reloadRequested.current = true;
    else void load();
  }, [load, refreshVersion]);
  useEffect(() => {
    if (!LIVE_API) return;
    const visibleLoad = () => { if (document.visibilityState === "visible") void load(); };
    const timer = window.setInterval(visibleLoad, 30_000);
    document.addEventListener("visibilitychange", visibleLoad);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", visibleLoad); };
  }, [load]);
  useEffect(() => {
    if (!forgetId) return;
    const timer = window.setTimeout(() => setForgetId(null), 10_000);
    return () => window.clearTimeout(timer);
  }, [forgetId]);
  useEffect(() => { if (editing) valueInput.current?.focus(); }, [editing]);

  async function mutate<T>(operation: () => Promise<T>, success: (result: T) => void) {
    if (!LIVE_API || inFlight.current) return;
    inFlight.current = true; setBusy(true); setActionError(null); setMessage(null);
    let changed = false;
    try {
      const result = await operation();
      if (mounted.current) { success(result); changed = true; }
    } catch (failure) { if (mounted.current) setActionError(errorText(failure)); }
    finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
      if (mounted.current && reloadRequested.current) { reloadRequested.current = false; void load(); }
    }
    if (changed) { onChanged?.(); void load(); }
  }

  function resetDraft() { setEditing(null); setDraft(EMPTY_MEMORY); }
  function saveMemory(event: FormEvent) {
    event.preventDefault();
    if (!draft.key.trim() || !draft.value.trim()) return;
    void mutate(() => api<{ memory: Memory }>("POST", "/api/assistant/memory", { ...draft, key: draft.key.trim(), value: draft.value.trim() }), ({ memory }) => {
      setMemories(current => [memory, ...(current ?? []).filter(item => item.id !== memory.id)]);
      resetDraft(); setMessage(`Saved “${memory.key}”.`);
    });
  }
  function editMemory(memory: Memory) {
    setEditing(memory.id); setDraft({ key: memory.key, value: memory.value, category: memory.category });
    setForgetId(null); setActionError(null); setMessage(null);
  }
  function forgetMemory(memory: Memory) {
    if (forgetId !== memory.id) { setForgetId(memory.id); return; }
    void mutate(() => api<{ deleted: string }>("DELETE", `/api/assistant/memory/${encodeURIComponent(memory.id)}`), () => {
      setMemories(current => current?.filter(item => item.id !== memory.id) ?? []);
      if (editing === memory.id) resetDraft();
      setForgetId(null); setMessage(`Forgot “${memory.key}”.`);
    });
  }
  function updateDraftSettings(patch: Partial<Settings>) {
    dirty.current = true; setSettingsDirty(true);
    setSettings(current => current ? { ...current, ...patch } : current);
  }
  function saveSettings(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    void mutate(() => api<{ settings: Settings }>("PATCH", "/api/assistant/settings", { ...settings, timezone: PACIFIC }), result => {
      dirty.current = false; setSettingsDirty(false); setSettings(result.settings);
      setInbox(current => current ? { ...current, settings: result.settings } : current);
      setMessage("Follow-through settings saved.");
    });
  }
  function notificationAction(item: Notification, action: "ack" | "snooze") {
    void mutate(() => api("POST", `/api/assistant/notifications/${encodeURIComponent(item.id)}/${action}`, action === "snooze" ? { minutes: 15 } : undefined), () => {
      setMessage(action === "ack" ? "Notification marked read." : "Notification snoozed for 15 minutes.");
    });
  }

  if (!LIVE_API) return <div className="section-content assistant-panel">
    <div className="section-content__tag">ASSISTANT <span>NEEDS THE ZÆNIA SERVER</span></div>
    <p className="assistant-panel__note">Open the desktop app or connect the phone app to manage personal memory and follow-through.</p>
  </div>;

  const disabled = busy || loading;
  const notifications = inbox?.notifications.filter(item => showRead || !item.readAt) ?? [];
  return <div className="section-content assistant-panel">
    <div className="assistant-panel__top">
      <div className="section-content__tag">ASSISTANT <span>MEMORY & FOLLOW-THROUGH</span></div>
      <button type="button" onClick={() => void load()} disabled={disabled}>{loading ? "Refreshing…" : "Refresh"}</button>
    </div>
    {actionError && <p className="assistant-panel__error" role="alert">{actionError}</p>}
    {message && <p className="assistant-panel__success" role="status">{message}</p>}
    <div className="assistant-panel__sections">
      <div className="assistant-panel__col">
      <KnowledgePanel/>
      <section className="assistant-panel__section" aria-labelledby="assistant-memory-heading" aria-busy={loading}>
        <header className="assistant-panel__heading"><h2 id="assistant-memory-heading">Personal memory</h2><span>{memories?.length ?? "—"} saved</span></header>
        <p className="assistant-panel__note">Facts, preferences, and goals you explicitly save stay available across conversations. You can correct or forget them here.</p>
        {memoryError && <p className="assistant-panel__error" role="alert">{memoryError}</p>}
        <form className="assistant-panel__form" onSubmit={saveMemory}>
          <div className="assistant-panel__form-title">{editing ? "Correct this memory" : "Add a memory"}</div>
          <label>Key<input value={draft.key} required maxLength={120} readOnly={Boolean(editing)} disabled={disabled}
            placeholder="e.g. preferred name" onChange={event => setDraft(current => ({ ...current, key: event.target.value }))}/></label>
          {editing && <small className="assistant-panel__note">The key stays the same when correcting a saved memory.</small>}
          <label>Category<select value={draft.category} disabled={disabled} onChange={event => setDraft(current => ({ ...current, category: event.target.value as Category }))}>
            {CATEGORIES.map(category => <option key={category} value={category}>{category[0].toUpperCase() + category.slice(1)}</option>)}
          </select></label>
          <label>Value<textarea ref={valueInput} value={draft.value} required maxLength={800} rows={3} disabled={disabled}
            placeholder="What would you like ZAE to remember?" onChange={event => setDraft(current => ({ ...current, value: event.target.value.replace(/[\r\n]+/g, " ") }))}/></label>
          <div className="assistant-panel__actions"><small>{draft.value.length}/800</small>
            {editing && <button type="button" onClick={resetDraft} disabled={disabled}>Cancel edit</button>}
            <button type="submit" className="assistant-panel__primary" disabled={disabled || !draft.key.trim() || !draft.value.trim()}>{busy ? "Saving…" : editing ? "Save correction" : "Save memory"}</button>
          </div>
          <small className="assistant-panel__note">An existing key updates that memory. Credentials belong in ZAE’s secure credential settings.</small>
        </form>
        {memories === null && !memoryError && <p className="assistant-panel__empty">Loading personal memory…</p>}
        {memories?.length === 0 && <p className="assistant-panel__empty">No personal memories saved yet.</p>}
        <ul className="assistant-panel__list" aria-label="Saved personal memories">
          {memories?.map(memory => <li className={`assistant-panel__item${editing === memory.id ? " assistant-panel__item--editing" : ""}`} key={memory.id}>
            <div className="assistant-panel__item-head"><strong>{memory.key}</strong><span className="assistant-panel__badge">{memory.category}</span></div>
            <p>{memory.value}</p>
            <small className="assistant-panel__meta">{memory.source === "explicit_owner" ? "Explicitly saved by you" : `Source: ${memory.source}`} · <time dateTime={memory.updated_at} title={`First saved ${dateLabel(memory.created_at)}`}>Updated {dateLabel(memory.updated_at)}</time></small>
            {forgetId === memory.id && <p className="assistant-panel__confirmation">Forget “{memory.key}”? This removes this saved memory.</p>}
            <div className="assistant-panel__actions">
              <button type="button" onClick={() => editMemory(memory)} disabled={disabled}>Correct</button>
              {forgetId === memory.id && <button type="button" onClick={() => setForgetId(null)} disabled={disabled}>Cancel</button>}
              <button type="button" className={forgetId === memory.id ? "assistant-panel__danger" : ""} onClick={() => forgetMemory(memory)} disabled={disabled}
                aria-label={forgetId === memory.id ? `Confirm forgetting ${memory.key}` : `Forget ${memory.key}`}>{forgetId === memory.id ? "Confirm forget" : "Forget"}</button>
            </div>
          </li>)}
        </ul>
        {memories && memories.length >= 100 && <p className="assistant-panel__note">Showing the 100 most recently updated memories.</p>}
      </section>
      </div>
      <div className="assistant-panel__col">
      <section className="assistant-panel__section" aria-labelledby="assistant-learned-heading" aria-busy={loading}>
        <header className="assistant-panel__heading"><h2 id="assistant-learned-heading">What ZÆNIA has learned</h2><span>{insights?.length ?? "—"} points</span></header>
        <p className="assistant-panel__note">{learning
          ? "Zae learns from your own words, keeps evidence, and distinguishes tentative patterns from points you confirm. Correct or reject anything wrong. Older unconfirmed points stop being used after 90 days. Stored only on this PC."
          : "Learning is turned off in brain_config.yaml (learning.enabled)."}</p>
        {insights?.length === 0 && <p className="assistant-panel__empty">Nothing learned yet. She distills key points every few conversations.</p>}
        <ul className="assistant-panel__list" aria-label="Learned key points">
          {insights?.map(insight => <li className="assistant-panel__item" key={insight.id}>
            <div className="assistant-panel__item-head"><strong>{insight.text}</strong><span className="assistant-panel__badge">{insight.kind.replace("_", " ")}</span></div>
            <small className="assistant-panel__meta">{insight.source === 'user_confirmed' ? 'Confirmed by you' : insight.confidence === 'supported' ? 'Repeated pattern · still inferred' : 'Tentative · may be wrong'} · {insight.count} evidence batches · last {dateLabel(insight.last_seen)}{insight.stale && insight.source !== 'user_confirmed' ? ' · Older point, not used in replies' : ''}</small>
            {insight.evidence && <small className="assistant-panel__meta">Your supporting words: “{insight.evidence}”</small>}
            {correctingInsight === insight.id && <form className="assistant-panel__form" onSubmit={event => {
              event.preventDefault(); void mutate(() => api<{insight:Insight}>('PATCH',`/api/assistant/insights/${insight.id}`,{text:insightText,revision:insight.revision ?? 1}), result => {
                setInsights(current => current?.map(item => item.id === insight.id ? result.insight : item) ?? []); setCorrectingInsight(null); setMessage('Corrected and confirmed. The old guess will not be relearned.');
              });
            }}><label>Correct learned point<textarea value={insightText} onChange={event => setInsightText(event.target.value)} minLength={8} maxLength={240} required disabled={disabled}/></label>
              <button type="submit" disabled={disabled}>Save correction</button><button type="button" onClick={() => setCorrectingInsight(null)}>Cancel correction</button>
            </form>}
            <div className="assistant-panel__actions">
              {insight.source !== 'user_confirmed' && <button type="button" disabled={disabled} aria-label={`Confirm learned point: ${insight.text}`} onClick={() => void mutate(() => api<{insight:Insight}>('PATCH',`/api/assistant/insights/${insight.id}`,{revision:insight.revision ?? 1}), result => {
                setInsights(current => current?.map(item => item.id === insight.id ? result.insight : item) ?? []); setMessage('Confirmed that learned point.');
              })}>That's right</button>}
              <button type="button" disabled={disabled} aria-label={`Correct learned point: ${insight.text}`} onClick={() => {setCorrectingInsight(insight.id); setInsightText(insight.text);}}>Correct</button>
              <button type="button" onClick={() => void mutate(() => api("DELETE", `/api/assistant/insights/${encodeURIComponent(insight.id)}`), () => {
                setInsights(current => current?.filter(item => item.id !== insight.id) ?? []); setMessage("Rejected that learned point. Matching guesses will not be relearned.");
              })} disabled={disabled} aria-label={`Delete learned point: ${insight.text}`}>Delete</button>
            </div>
          </li>)}
        </ul>
        {Boolean(insights?.length) && <div className="assistant-panel__actions">
          {clearAsked && <button type="button" onClick={() => setClearAsked(false)} disabled={disabled}>Cancel</button>}
          <button type="button" className={clearAsked ? "assistant-panel__danger" : ""} disabled={disabled} onClick={() => {
            if (!clearAsked) { setClearAsked(true); return; }
            void mutate(() => api("DELETE", "/api/assistant/insights"), () => { setInsights([]); setClearAsked(false); setMessage("Cleared everything she learned."); });
          }}>{clearAsked ? "Confirm: delete all learned points" : "Delete all learned points"}</button>
        </div>}
      </section>
      <ProfileReview/>
      </div>
      <div className="assistant-panel__col">
      <section className="assistant-panel__section" aria-labelledby="assistant-followthrough-heading" aria-busy={loading}>
        <header className="assistant-panel__heading"><h2 id="assistant-followthrough-heading">Follow-through</h2><span>{inbox?.unreadCount ?? "—"} unread</span></header>
        <p className="assistant-panel__note">Keep ZAE’s local service running and this app connected for reminders about saved ZAE events and task deadlines.</p>
        {inboxError && <p className="assistant-panel__error" role="alert">{inboxError}</p>}
        {inbox && <p className={`assistant-panel__worker${inbox.workerRunning && inbox.settings.enabled ? " assistant-panel__worker--active" : ""}`} role="status">
          {!inbox.settings.enabled ? "Follow-through paused in settings." : inbox.workerRunning ? "Following saved tasks and events." : "Follow-through is inactive. Restart ZAE’s local server to resume reminders."}
          {inbox.quiet && inbox.settings.enabled && " Quiet hours are active; reminders stay in this inbox."}
        </p>}
        {settings && <form className="assistant-panel__form" onSubmit={saveSettings}>
          <fieldset disabled={disabled}><legend>Delivery settings</legend>
            <label className="assistant-panel__check"><input type="checkbox" checked={settings.enabled} onChange={event => updateDraftSettings({ enabled: event.target.checked })}/>Enable local follow-through</label>
            <label className="assistant-panel__check"><input type="checkbox" checked={settings.spoken} onChange={event => updateDraftSettings({ spoken: event.target.checked })}/>Read eligible reminders aloud</label>
            <label className="assistant-panel__check"><input type="checkbox" checked={settings.quietHoursEnabled} onChange={event => updateDraftSettings({ quietHoursEnabled: event.target.checked })}/>Use quiet hours</label>
            <div className="assistant-panel__times">
              <label>Quiet from<input type="time" value={settings.quietStart} required disabled={!settings.quietHoursEnabled} onChange={event => updateDraftSettings({ quietStart: event.target.value })}/></label>
              <label>Until<input type="time" value={settings.quietEnd} required disabled={!settings.quietHoursEnabled} onChange={event => updateDraftSettings({ quietEnd: event.target.value })}/></label>
            </div>
            <small className="assistant-panel__note">Pacific time · Speech starts only after you enable it and is paused during quiet hours.</small>
          </fieldset>
          <div className="assistant-panel__actions">{settingsDirty && <small>Unsaved changes</small>}<button type="submit" className="assistant-panel__primary" disabled={disabled || !settingsDirty}>{busy ? "Saving…" : "Save settings"}</button></div>
        </form>}
        <div className="assistant-panel__inbox-head"><h3>Notification inbox</h3><label className="assistant-panel__check"><input type="checkbox" checked={showRead} onChange={event => setShowRead(event.target.checked)}/>Show read</label></div>
        {!inbox && !inboxError && <p className="assistant-panel__empty">Loading follow-through…</p>}
        {inbox && notifications.length === 0 && <p className="assistant-panel__empty">{showRead ? "No reminders yet. Upcoming saved events and task deadlines will appear here." : "No unread reminders."}</p>}
        <ul className="assistant-panel__list" aria-label="Follow-through notifications">
          {notifications.map(item => {
            const snoozed = Boolean(item.snoozedUntil && Date.parse(item.snoozedUntil) > Date.now());
            return <li key={item.id} className={`assistant-panel__item${item.readAt ? " assistant-panel__item--read" : ""}`}>
              <div className="assistant-panel__item-head"><strong>{item.title}</strong><span className="assistant-panel__badge">{item.readAt ? "Read" : snoozed ? "Snoozed" : "Unread"}</span></div>
              <p>{item.message}</p>
              <small className="assistant-panel__meta">{item.source === "task" ? "Task deadline" : "ZAE event"} · <time dateTime={item.occurrence}>{dateLabel(item.occurrence)}</time></small>
              {snoozed && <small className="assistant-panel__meta">Snoozed until {dateLabel(item.snoozedUntil)}</small>}
              {!item.readAt && <div className="assistant-panel__actions"><button type="button" onClick={() => notificationAction(item, "ack")} disabled={disabled}>Mark read</button><button type="button" onClick={() => notificationAction(item, "snooze")} disabled={disabled}>Snooze 15 min</button></div>}
            </li>;
          })}
        </ul>
        <p className="assistant-panel__note">Calendar reminders: one hour, 15 minutes, and scheduled start. Tasks: one hour before the deadline and once overdue. Missed reminders catch up for 24 hours.</p>
      </section>
      </div>
    </div>
  </div>;
}
