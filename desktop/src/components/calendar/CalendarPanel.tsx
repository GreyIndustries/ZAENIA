import { useCallback, useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./CalendarPanel.css";

type CalendarEvent = {
  id: string; date: string; time: string; endTime: string | null; allDay: boolean; title: string;
  location: string | null; reminder: string | null; source: "zaenia" | "google" | "calendar" | "recurring"; deletable: boolean;
};
type DutyStatus = "on_duty" | "off_duty" | "class" | "leave";
type CalendarReply = { start: string; days: number; events: CalendarEvent[]; dayStatus: Record<string, string>; dutyOverrides?: Record<string, DutyStatus>; dutyRevision?: number; google: "live" | "unavailable"; notice: string | null };
type Draft = { id: number; day: string; title: string };
type Completion = { id: string; revision: number; title: string; completed: boolean };

const DRAFT_KEY = "zaenia-ui-v3-events";
const sourceLabel: Record<CalendarEvent["source"], string> = { zaenia: "ZÆNIA", google: "Google", calendar: "Calendar file", recurring: "Repeats" };
const dayKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const timeLabel = (value: string) => {
  const match = /^(\d{1,2}):(\d{2})/.exec(value);
  if (!match) return value;
  const date = new Date(2000, 0, 1, Number(match[1]), Number(match[2]));
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
};
function readDrafts(): Draft[] {
  try { const raw = localStorage.getItem(DRAFT_KEY); const list = raw ? JSON.parse(raw) as Draft[] : []; return Array.isArray(list) ? list.filter(d => d && typeof d.title === "string" && typeof d.day === "string") : []; }
  catch { return []; }
}
function writeDrafts(drafts: Draft[]) {
  try { if (drafts.length) localStorage.setItem(DRAFT_KEY, JSON.stringify(drafts)); else localStorage.removeItem(DRAFT_KEY); } catch { /* storage unavailable */ }
}

/**
 * Real calendar: ZÆNIA's calendar file, ZÆNIA events (scheduling service) and
 * live Google events, the same sources the brief reads. New events go to
 * ZÆNIA; Google stays read-only until two-way sign-in is set up.
 */
export function CalendarPanel({ refreshVersion = 0 }: { refreshVersion?: number }) {
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [selected, setSelected] = useState(() => dayKey(new Date()));
  const [data, setData] = useState<CalendarReply | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [time, setTime] = useState("09:00");
  const [repeat, setRepeat] = useState<"none" | "daily" | "weekly">("none");
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>(readDrafts);
  const [refresh, setRefresh] = useState(0);
  const [duty, setDuty] = useState<DutyStatus | "automatic">("automatic");
  const [savingDuty, setSavingDuty] = useState(false);
  const [dutyNotice, setDutyNotice] = useState<string | null>(null);
  const [completions, setCompletions] = useState<Completion[]>([]);
  const [completionNotice, setCompletionNotice] = useState('');
  const [savingCompletion, setSavingCompletion] = useState(false);
  const [completionRefresh, setCompletionRefresh] = useState(0);
  useEffect(() => {
    let active = true; setCompletions([]); setCompletionNotice('');
    if (LIVE_API) void api<{ items: Completion[] }>('GET', `/api/platform/calendar-completions?day=${selected}`)
      .then(result => { if (active) setCompletions(result.items); }, () => { if (active) setCompletionNotice('Completion records are unavailable. Your calendar is still shown.'); });
    return () => { active = false; };
  }, [selected, completionRefresh, refreshVersion]);
  async function reopenCompletion(item: Completion) {
    if (savingCompletion) return;
    setSavingCompletion(true);
    try { await api('PUT', `/api/platform/calendar-completions/${item.id}`, { completed: false, revision: item.revision }); setCompletionRefresh(value => value + 1); }
    catch (failure) { setCompletionNotice(errorText(failure)); }
    finally { setSavingCompletion(false); }
  }
  useEffect(() => { setDuty(data?.dutyOverrides?.[selected] ?? "automatic"); }, [selected, data?.dutyRevision]);
  useEffect(() => { setDutyNotice(null); }, [selected]);
  const changeMonth = (offset: number) => { const next = new Date(month.getFullYear(), month.getMonth() + offset, 1); setMonth(next); setSelected(dayKey(next)); };

  // The grid starts on the Sunday before the 1st and shows six weeks.
  const gridStart = useMemo(() => { const first = new Date(month); first.setDate(1 - first.getDay()); return first; }, [month]);
  const load = useCallback(async () => {
    if (!LIVE_API) return;
    setLoading(true); setError(null);
    try { setData(await api<CalendarReply>("GET", `/api/calendar?start=${dayKey(gridStart)}&days=42`, undefined, { timeoutMs: 60_000 })); }
    catch (failure) { setError(errorText(failure)); }
    finally { setLoading(false); }
  }, [gridStart]);
  useEffect(() => { void load(); }, [load, refresh, refreshVersion]);
  useEffect(() => {
    if (!confirmDelete) return;
    const timer = window.setTimeout(() => setConfirmDelete(null), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmDelete]);

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of data?.events ?? []) map.set(event.date, [...(map.get(event.date) ?? []), event]);
    return map;
  }, [data]);
  const cells = Array.from({ length: 42 }, (_, index) => { const date = new Date(gridStart); date.setDate(gridStart.getDate() + index); return date; });
  const dayEvents = (byDay.get(selected) ?? []).slice().sort((a, b) => (a.allDay ? "00:00" : a.time || "99:99").localeCompare(b.allDay ? "00:00" : b.time || "99:99"));
  const dayDrafts = drafts.filter(draft => draft.day === selected);
  const selectedDate = new Date(`${selected}T12:00:00`);

  async function addEvent(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true); setError(null);
    try {
      await api("POST", "/api/calendar/events", { title: title.trim(), date: selected, time, recurrence: repeat });
      setTitle(""); setRepeat("none"); setRefresh(value => value + 1);
    } catch (failure) { setError(errorText(failure)); }
    finally { setSaving(false); }
  }
  async function removeEvent(item: CalendarEvent) {
    if (confirmDelete !== item.id) { setConfirmDelete(item.id); return; }
    setConfirmDelete(null); setError(null);
    try { await api("DELETE", `/api/calendar/events/${encodeURIComponent(item.id)}`); setRefresh(value => value + 1); }
    catch (failure) { setError(errorText(failure)); }
  }
  async function saveDraft(draft: Draft) {
    setError(null);
    try {
      await api("POST", "/api/calendar/events", { title: draft.title.slice(0, 200), date: draft.day, time: "09:00", recurrence: "none" });
      const next = drafts.filter(item => item.id !== draft.id); setDrafts(next); writeDrafts(next); setRefresh(value => value + 1);
    } catch (failure) { setError(errorText(failure)); }
  }
  function discardDraft(draft: Draft) { const next = drafts.filter(item => item.id !== draft.id); setDrafts(next); writeDrafts(next); }

  async function saveDuty(event: FormEvent) {
    event.preventDefault();
    if (savingDuty || !data || data.dutyRevision === undefined) return;
    const day = selected;
    setSavingDuty(true); setError(null); setDutyNotice(null);
    try {
      await api("PUT", "/api/calendar/duty-status", { date: day, status: duty === "automatic" ? null : duty, revision: data.dutyRevision });
      await load();
      setDutyNotice(`Duty status saved for ${day}.`);
    } catch (failure) { setError(errorText(failure)); }
    finally { setSavingDuty(false); }
  }

  if (!LIVE_API) {
    return <div className="section-content cal-panel">
      <div className="section-content__tag">CALENDAR <span>NEEDS THE ZÆNIA SERVER</span></div>
      <p className="cal-panel__empty">Your real calendar shows here in the desktop app and the phone app: ZÆNIA's calendar, events you add, and Google Calendar.</p>
    </div>;
  }

  return <div className="section-content cal-panel">
    <div className="section-content__tag">YOUR CALENDAR <span>{data?.google === "live" ? "GOOGLE LIVE · ZÆNIA EVENTS" : "ZÆNIA EVENTS"}</span></div>
    <div className="calendar-header">
      <button type="button" onClick={() => changeMonth(-1)} aria-label="Previous month">‹</button>
      <strong>{month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</strong>
      <button type="button" onClick={() => changeMonth(1)} aria-label="Next month">›</button>
    </div>
    <div className={`calendar-grid cal-panel__grid${loading ? " cal-panel__grid--loading" : ""}`} aria-busy={loading}>
      {["S", "M", "T", "W", "T", "F", "S"].map((label, index) => <span className="calendar-head" key={index}>{label}</span>)}
      {cells.map(date => {
        const key = dayKey(date);
        const count = byDay.get(key)?.length ?? 0;
        const outside = date.getMonth() !== month.getMonth();
        const today = key === dayKey(new Date());
        return <button key={key} type="button" aria-pressed={selected === key}
          aria-label={`${date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}${count ? `, ${count} event${count > 1 ? "s" : ""}` : ""}${data?.dutyOverrides?.[key] ? `, ${data.dayStatus[key]}` : ""}`}
          className={`calendar-day${selected === key ? " calendar-day--selected" : ""}${count ? " calendar-day--event" : ""}${outside ? " cal-panel__day--outside" : ""}${today ? " cal-panel__day--today" : ""}`}
          onClick={() => setSelected(key)}>{date.getDate()}{count > 1 && <small className="cal-panel__count">{count}</small>}{data?.dutyOverrides?.[key] && <span className="cal-panel__status-dot" aria-hidden="true"/>}</button>;
      })}
    </div>
    {data?.notice && <p className="cal-panel__notice" role="status">{data.notice}</p>}
    {error && <p className="cal-panel__error" role="alert">{error}</p>}
    <section className="calendar-agenda cal-panel__agenda" aria-label="Selected day">
      <div className="cal-panel__dayhead">
        <strong>{selectedDate.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</strong>
        {data?.dayStatus[selected] && <span className="cal-panel__duty">{data.dayStatus[selected]}</span>}
      </div>
      <form className="cal-panel__duty-form" onSubmit={saveDuty} aria-label="Edit selected day's duty status">
        <label>Duty status<select value={duty} onChange={event => setDuty(event.target.value as DutyStatus | "automatic")} disabled={savingDuty || loading || data?.dutyRevision === undefined}>
          <option value="automatic">Use calendar status</option><option value="on_duty">On duty</option><option value="off_duty">Off duty / DONSA</option><option value="class">School / class</option><option value="leave">On leave</option>
        </select></label>
        <button type="submit" disabled={savingDuty || loading || data?.dutyRevision === undefined || duty === (data?.dutyOverrides?.[selected] ?? "automatic")}>{savingDuty ? "Saving…" : "Save status"}</button>
        <small>Your choice applies to this date and takes priority over inferred status. Events and reminders stay scheduled.</small>
      </form>
      {dutyNotice && <p className="cal-panel__notice" role="status">{dutyNotice}</p>}
      <details><summary>Briefing completion checks ({completions.filter(item => item.completed).length} completed)</summary>
        <p>Past events are checked during your brief. Completed occurrences stay quiet; a later recurrence is tracked separately.</p>
        <button type="button" onClick={() => setCompletionRefresh(value => value + 1)}>Refresh completion checks</button>
        {completionNotice && <p role="status">{completionNotice}</p>}
        {completions.map(item => <p key={item.id}>{item.title} · {item.completed ? 'Completed' : 'Unfinished'} {item.completed && <button type="button" disabled={savingCompletion} onClick={() => void reopenCompletion(item)}>Reopen</button>}</p>)}
      </details>
      {dayEvents.length === 0 && dayDrafts.length === 0 && <p className="cal-panel__empty">{loading ? "Loading…" : "Nothing scheduled."}</p>}
      <ul className="cal-panel__list">
        {dayEvents.map(item => <li key={`${item.id}-${item.date}`} className={`cal-panel__event cal-panel__event--${item.source}`}>
          <span className="cal-panel__time">{item.allDay ? "All day" : item.time ? timeLabel(item.time) : "—"}{item.endTime && !item.allDay && <small>– {timeLabel(item.endTime)}</small>}</span>
          <div className="cal-panel__body">
            <strong>{item.title}</strong>
            {item.location && <small>{item.location}</small>}
            {item.reminder && <small>{item.reminder}</small>}
          </div>
          <span className={`cal-panel__source cal-panel__source--${item.source}`}>{sourceLabel[item.source]}</span>
          {item.deletable && <button type="button" className={`cal-panel__delete${confirmDelete === item.id ? " cal-panel__delete--confirm" : ""}`}
            onClick={() => void removeEvent(item)} aria-label={confirmDelete === item.id ? `Tap again to delete ${item.title}` : `Delete ${item.title}`}>
            {confirmDelete === item.id ? "Delete?" : "✕"}</button>}
        </li>)}
        {dayDrafts.map(draft => <li key={`draft-${draft.id}`} className="cal-panel__event cal-panel__event--draft">
          <span className="cal-panel__time">Draft</span>
          <div className="cal-panel__body"><strong>{draft.title}</strong><small>Saved on this device only, from the old calendar.</small></div>
          <span className="cal-panel__draft-actions">
            <button type="button" onClick={() => void saveDraft(draft)}>Save to ZÆNIA (9 AM)</button>
            <button type="button" onClick={() => discardDraft(draft)}>Discard</button>
          </span>
        </li>)}
      </ul>
      <form className="inline-form cal-panel__form" onSubmit={addEvent}>
        <input aria-label="Event title" placeholder="Add an event…" value={title} maxLength={200} onChange={(e: ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)} disabled={saving}/>
        <input aria-label="Time" type="time" value={time} required onChange={(e: ChangeEvent<HTMLInputElement>) => setTime(e.target.value)} disabled={saving}/>
        <select aria-label="Repeat" value={repeat} onChange={(e: ChangeEvent<HTMLSelectElement>) => setRepeat(e.target.value as "none" | "daily" | "weekly")} disabled={saving}>
          <option value="none">Once</option><option value="daily">Daily</option><option value="weekly">Weekly</option>
        </select>
        <button type="submit" disabled={!title.trim() || !time || saving}>{saving ? "Adding…" : "+ Add"}</button>
      </form>
      <p className="cal-panel__foot">New events are saved in ZÆNIA, so your brief and reminders include them. Google Calendar events are shown live but can't be changed here yet.</p>
    </section>
  </div>;
}
