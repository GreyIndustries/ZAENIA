import { DetailScreen, PageNavigator, detailKey } from "../shell/PageNavigator";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { DragEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./MusicStudio.css";
/** Lyrics and session notes are separate pages of a song (Claude 2026-11-11). */
const SONG_TEXT = [{ id: "lyrics", label: "Lyrics" }, { id: "notes", label: "Session notes" }];

const PATH = "/api/platform/personal/music";
const STAGES = ["Idea", "Writing", "Recording", "Mixing", "Mastering", "Released"] as const;
const PLATFORMS = ["Spotify", "YouTube", "SoundCloud", "Apple Music"] as const;
const MAIN_METRIC: Record<string, string> = { Spotify: "Plays", YouTube: "Views", SoundCloud: "Plays", "Apple Music": "Plays" };
const PLATFORM_COLOR: Record<string, string> = { Spotify: "#4fe39a", YouTube: "#ff7a6b", SoundCloud: "#ff9d4f", "Apple Music": "#c08cff" };
const ART: Record<string, string> = { amber: "#8a5a1e", blue: "#1f4a7a", green: "#1f5a3f", rose: "#7a2f4a", violet: "#4a2f7a", teal: "#1f5a5a" };
const METRICS = ["Plays", "Views", "Listeners", "Likes", "Saves"];

type Stat = { platform: string; date: string; metric: string; value: number; source: string; method: "manual" };
type Release = { platform: string; url: string };
type Session = { date: string; minutes: number; note: string };
type Song = { id?: string; revision?: number; updatedAt?: string; createdAt?: string; title: string; archived: boolean; stage: string; projectFile: string;
  bpm: number | null; key: string; body: string; releases: Release[]; stats: Stat[]; lyrics: string; releaseDate: string;
  checklist: Record<string, boolean>; sessions: Session[]; art: string };
type Connection = { platform: string; metric: string; status: string; needs: string };
type Overview = { songs: Song[]; checklist: string[]; connections: Connection[] };
type Tab = "dashboard" | "studio" | "song" | "connections";
type Range = "7" | "30" | "all";

const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const today = () => iso(new Date());
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d); };
const blank = (title: string): Song => ({ title, archived: false, stage: "Idea", projectFile: "", bpm: null, key: "", body: "", releases: [], stats: [],
  lyrics: "", releaseDate: "", checklist: {}, sessions: [], art: "amber" });
const fmt = (n: number) => n.toLocaleString();

/** Latest observed value of a platform's main metric for one song, on or before a date. */
function latest(song: Song, platform: string, onOrBefore: string): number {
  const rows = song.stats.filter(s => s.platform === platform && s.metric === MAIN_METRIC[platform] && s.date <= onOrBefore);
  return rows.length ? rows.reduce((a, b) => (b.date >= a.date ? b : a)).value : 0;
}
const songTotal = (song: Song, day: string) => PLATFORMS.reduce((sum, p) => sum + latest(song, p, day), 0);
const platformTotal = (songs: Song[], platform: string, day: string) => songs.reduce((sum, s) => sum + latest(s, platform, day), 0);

function rangeStart(range: Range, songs: Song[]): string {
  if (range !== "all") return daysAgo(Number(range));
  const dates = songs.flatMap(s => s.stats.map(x => x.date)).sort();
  return dates[0] ?? daysAgo(30);
}
function seriesDays(start: string, points = 14): string[] {
  const from = new Date(`${start}T12:00:00`).getTime(); const to = new Date(`${today()}T12:00:00`).getTime();
  return Array.from({ length: points }, (_, i) => iso(new Date(from + (to - from) * (i / (points - 1)))));
}
const change = (now: number, before: number) => before > 0 ? `${now >= before ? "+" : "−"}${Math.abs(Math.round((now - before) / before * 100))}%` : now > 0 ? "new" : "—";
function progress(song: Song, items: number): number {
  const stage = Math.max(0, STAGES.indexOf(song.stage as typeof STAGES[number])) / (STAGES.length - 1);
  const done = items ? Object.values(song.checklist).filter(Boolean).length / items : 0;
  return song.stage === "Released" ? 100 : Math.round((stage * 0.65 + done * 0.35) * 100);
}
const nextStep = (song: Song, items: string[]) => items.find(item => !song.checklist[item]) ?? (song.stage === "Released" ? "Check the numbers" : "Move to the next stage");
const studioMinutes = (songs: Song[], since: string) => songs.reduce((sum, s) => sum + s.sessions.filter(x => x.date >= since).reduce((a, x) => a + x.minutes, 0), 0);

export function MusicStudio() {
  const [data, setData] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>(() => { try { return (localStorage.getItem("zaenia.music.tab") as Tab) || "dashboard"; } catch { return "dashboard"; } });
  const [selected, setSelected] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api<Overview>("GET", `${PATH}/overview`).then(setData, failure => setError(errorText(failure))), []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  useEffect(() => { const changed = () => void load(); window.addEventListener("zae:records-changed", changed); return () => window.removeEventListener("zae:records-changed", changed); }, [load]);
  const choose = (next: Tab) => { setTab(next); try { localStorage.setItem("zaenia.music.tab", next); } catch { /* optional */ } };
  const openSong = (id: string) => { setSelected(id); choose("song"); };

  /** Save a whole song (new or existing); returns the saved row. */
  const save = async (song: Song, done?: string): Promise<Song | null> => {
    setBusy(true); setError(null); setNote(null);
    try {
      const { id, revision, updatedAt: _u, createdAt: _c, ...record } = song;
      const saved = await api<Song>(id ? "PUT" : "POST", `${PATH}${id ? `/${id}` : ""}`, id ? { record, revision } : { record });
      await load(); if (done) setNote(done);
      return saved;
    } catch (failure) { setError(errorText(failure)); return null; }
    finally { setBusy(false); }
  };

  if (!LIVE_API) return <p className="ms-muted">The Music studio needs the ZÆNIA server: open it in the desktop or phone app.</p>;
  if (!data) return <p className="ms-muted">{error ?? "Loading your songs…"}</p>;
  const songs = data.songs;
  const tabs: [Tab, string][] = [["dashboard", "Dashboard"], ["studio", "Studio"], ["song", "Song"], ["connections", "Connections"]];

  return <div className="ms">
    <PageNavigator id="music" name="Music" items={tabs.map(([id, label]) => ({ id, label }))} current={tab} onChoose={next => choose(next as Tab)}/>
    {error && <p className="ms-error" role="alert">{error}</p>}
    {note && <p className="ms-note" role="status">✓ {note}</p>}
    {tab === "dashboard" && <Dashboard songs={songs} connections={data.connections} items={data.checklist} busy={busy} onOpen={openSong} onSave={save}
      onConnections={() => choose("connections")} onStudio={() => choose("studio")}/>}
    {tab === "studio" && <Studio songs={songs} items={data.checklist} busy={busy} onOpen={openSong} onSave={save}/>}
    {tab === "song" && <SongWorkspace songs={songs} items={data.checklist} selected={selected} onSelect={setSelected} busy={busy} onSave={save}/>}
    {tab === "connections" && <Connections connections={data.connections}/>}
  </div>;
}

// ---- B: Dashboard (main view)
function Dashboard({ songs, connections, items, busy, onOpen, onSave, onConnections, onStudio }: { songs: Song[]; connections: Connection[]; items: string[]; busy: boolean;
  onOpen: (id: string) => void; onSave: (song: Song, done?: string) => Promise<Song | null>; onConnections: () => void; onStudio: () => void }) {
  const [range, setRange] = useState<Range>("30");
  const [log, setLog] = useState({ song: "", platform: "Spotify", metric: "Plays", value: "" });
  const start = rangeStart(range, songs); const now = today(); const days = useMemo(() => seriesDays(start), [start]);
  const ranked = songs.filter(s => s.stats.length || s.stage === "Released")
    .map(s => ({ s, now: songTotal(s, now), before: songTotal(s, start) })).sort((a, b) => b.now - a.now);
  const upcoming = songs.filter(s => s.releaseDate && s.releaseDate >= now).sort((a, b) => a.releaseDate.localeCompare(b.releaseDate)).slice(0, 4);
  const inProgress = songs.filter(s => s.stage !== "Released").length;
  const released = songs.filter(s => s.stage === "Released").length;
  const status = (p: string) => connections.find(c => c.platform === p)?.status === "connected" ? "Live" : "Manual";
  const logSong = songs.find(s => s.id === (log.song || songs[0]?.id));

  if (!songs.length) return <div className="ms-empty"><h3>No songs yet</h3><p>Add your first song in the Studio and it shows up here with its releases and numbers.</p>
    <button type="button" className="ms-primary" onClick={onStudio}>Open the Studio</button></div>;

  return <div className="ms-dash">
    <div className="ms-row ms-row--between">
      <div className="ms-kpis">
        <span><small>In progress</small><b>{inProgress} songs</b></span>
        <span><small>Released</small><b>{released} songs</b></span>
        <span><small>Studio time, 7 days</small><b>{Math.floor(studioMinutes(songs, daysAgo(7)) / 60)} h {studioMinutes(songs, daysAgo(7)) % 60} m</b></span>
        <span><small>Next release</small><b>{upcoming[0] ? new Date(`${upcoming[0].releaseDate}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" }) : "Not set"}</b></span>
      </div>
      <div className="ms-seg" role="group" aria-label="Time range">
        {([["7", "7 days"], ["30", "30 days"], ["all", "All time"]] as [Range, string][]).map(([id, label]) =>
          <button key={id} type="button" aria-pressed={range === id} onClick={() => setRange(id)}>{label}</button>)}
      </div>
    </div>

    <div className="ms-platforms">
      {PLATFORMS.map(p => { const total = platformTotal(songs, p, now); const before = platformTotal(songs, p, start);
        const points = days.map(d => platformTotal(songs, p, d)); const top = Math.max(1, ...points);
        return <section key={p} className="ms-card ms-platform">
          <header><strong>{p}</strong><button type="button" className={`ms-chip ms-chip--${status(p) === "Live" ? "live" : "manual"}`} onClick={onConnections}>{status(p)}</button></header>
          <b className="ms-big">{fmt(total)}</b><small className="ms-muted">{MAIN_METRIC[p].toLowerCase()} · {change(total, before)} in range</small>
          <div className="ms-bars" aria-hidden="true">{points.map((v, i) => <i key={i} style={{ height: `${Math.max(4, v / top * 100)}%`, background: PLATFORM_COLOR[p] }}/>)}</div>
        </section>; })}
    </div>

    <div className="ms-split">
      <section className="ms-card">
        <header className="ms-row ms-row--between"><h3>Songs</h3><small className="ms-muted">by total {range === "all" ? "" : `· change over ${range} days`}</small></header>
        {ranked.length ? <table className="ms-table"><thead><tr><th>Song</th><th>Released</th><th>Total</th><th>Change</th><th>On</th></tr></thead>
          <tbody>{ranked.map(({ s, now: total, before }) => <tr key={s.id}>
            <td><button type="button" className="ms-song" onClick={() => onOpen(s.id!)}><i style={{ background: ART[s.art] ?? ART.amber }}/>{s.title}</button></td>
            <td>{s.releaseDate ? new Date(`${s.releaseDate}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" }) : s.stage}</td>
            <td className="ms-num">{fmt(total)}</td>
            <td className={total >= before ? "ms-up" : "ms-down"}>{change(total, before)}</td>
            <td className="ms-muted">{[...new Set([...s.releases.map(r => r.platform), ...s.stats.map(x => x.platform)])].join(", ") || "—"}</td></tr>)}</tbody></table>
          : <p className="ms-muted">No numbers yet. Log one on the right, or tell ZAE "Echoes has 1,240 plays on SoundCloud".</p>}
      </section>
      <div className="ms-stack">
        <section className="ms-card">
          <h3>Release calendar</h3>
          {upcoming.length ? upcoming.map(s => { const left = items.filter(i => !s.checklist[i]);
            return <button type="button" key={s.id} className="ms-release" onClick={() => onOpen(s.id!)}>
              <span className="ms-date"><small>{new Date(`${s.releaseDate}T12:00:00`).toLocaleDateString([], { month: "short" }).toUpperCase()}</small><b>{s.releaseDate.slice(8)}</b></span>
              <span><strong>{s.title}</strong><small>{s.stage}{left.length ? ` · ${left.length} checklist item${left.length > 1 ? "s" : ""} left` : " · ready"}</small></span></button>; })
            : <p className="ms-muted">No release dates set. Add one in a song's workspace.</p>}
        </section>
        <section className="ms-card">
          <h3>Log a number</h3>
          <form className="ms-log" onSubmit={e => { e.preventDefault(); const value = Number(log.value.replace(/,/g, ""));
            if (!logSong || !Number.isFinite(value) || value < 0) return;
            void onSave({ ...logSong, stats: [...logSong.stats, { platform: log.platform, metric: log.metric, date: today(), value: Math.trunc(value), source: "Logged on the Music dashboard", method: "manual" }] },
              `Logged ${fmt(Math.trunc(value))} ${log.metric.toLowerCase()} for ${logSong.title} on ${log.platform}.`).then(saved => saved && setLog({ ...log, value: "" })); }}>
            <label>Song<select value={logSong?.id ?? ""} onChange={e => setLog({ ...log, song: e.target.value })}>{songs.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
            <label>Platform<select value={log.platform} onChange={e => setLog({ ...log, platform: e.target.value, metric: MAIN_METRIC[e.target.value] })}>{PLATFORMS.map(p => <option key={p}>{p}</option>)}</select></label>
            <label>Metric<select value={log.metric} onChange={e => setLog({ ...log, metric: e.target.value })}>{METRICS.map(m => <option key={m}>{m}</option>)}</select></label>
            <label>Count<input inputMode="numeric" value={log.value} placeholder="1,240" onChange={e => setLog({ ...log, value: e.target.value })}/></label>
            <button type="submit" className="ms-primary" disabled={busy || !log.value.trim()}>Add</button>
          </form>
          <small className="ms-muted">Counts are the total shown on the platform today. Plays, views and listeners are different measures.</small>
        </section>
      </div>
    </div>
  </div>;
}

// ---- A: Studio board
function Studio({ songs, items, busy, onOpen, onSave }: { songs: Song[]; items: string[]; busy: boolean; onOpen: (id: string) => void; onSave: (song: Song, done?: string) => Promise<Song | null> }) {
  const [title, setTitle] = useState(""); const [query, setQuery] = useState(""); const [over, setOver] = useState("");
  const shown = songs.filter(s => !query.trim() || `${s.title} ${s.key} ${s.bpm ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  const drop = (stage: string) => (e: DragEvent) => { e.preventDefault(); setOver(""); const song = songs.find(s => s.id === e.dataTransfer.getData("text/plain"));
    if (song && song.stage !== stage) void onSave({ ...song, stage }, `${song.title} moved to ${stage}.`); };
  return <div className="ms-studio">
    <div className="ms-row ms-row--between">
      <input type="search" className="ms-search" value={query} placeholder="Search songs, keys, BPM" aria-label="Search songs" onChange={e => setQuery(e.target.value)}/>
      <form className="ms-row" onSubmit={e => { e.preventDefault(); if (title.trim()) void onSave(blank(title.trim()), `Added ${title.trim()}.`).then(saved => saved && setTitle("")); }}>
        <input value={title} maxLength={160} placeholder="New song title" aria-label="New song title" onChange={e => setTitle(e.target.value)}/>
        <button type="submit" className="ms-primary" disabled={busy || !title.trim()}>+ New song</button>
      </form>
    </div>
    <p className="ms-muted">Drag a card to another column to change its stage. Click a card to open its workspace.</p>
    <div className="ms-board">
      {STAGES.map(stage => { const cards = shown.filter(s => s.stage === stage);
        return <section key={stage} className={`ms-col${over === stage ? " ms-col--over" : ""}`} onDragOver={e => { e.preventDefault(); setOver(stage); }} onDragLeave={() => setOver("")} onDrop={drop(stage)}>
          <header><span>{stage}</span><small>{cards.length}</small></header>
          {cards.map(s => <button type="button" key={s.id} draggable className="ms-kcard" onDragStart={e => e.dataTransfer.setData("text/plain", s.id!)} onClick={() => onOpen(s.id!)}>
            <span className="ms-row"><i className="ms-art" style={{ background: ART[s.art] ?? ART.amber }}/><span className="ms-kcard__t"><strong>{s.title}</strong>
              <small>{s.bpm ? `${s.bpm} BPM` : "— BPM"}{s.key ? ` · ${s.key}` : ""}</small></span></span>
            <span className="ms-progress"><i style={{ width: `${progress(s, items.length)}%` }}/></span>
            <small>Next: {nextStep(s, items)}</small></button>)}
        </section>; })}
    </div>
  </div>;
}

// ---- C: Song workspace
function SongWorkspace({ songs, items, selected, onSelect, busy, onSave }: { songs: Song[]; items: string[]; selected: string; onSelect: (id: string) => void; busy: boolean;
  onSave: (song: Song, done?: string) => Promise<Song | null> }) {
  const current = songs.find(s => s.id === selected) ?? songs[0];
  const [draft, setDraft] = useState<Song | null>(current ?? null);
  const [view, setView] = useState<"lyrics" | "notes">("lyrics");
  const [session, setSession] = useState<Session>({ date: today(), minutes: 60, note: "" });
  const [release, setRelease] = useState<Release>({ platform: "Spotify", url: "" });
  useEffect(() => { setDraft(current ?? null); }, [current?.id, current?.revision]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = Boolean(draft && current && JSON.stringify(draft) !== JSON.stringify(current));
  const edit = (changes: Partial<Song>) => draft && setDraft({ ...draft, ...changes });

  if (!draft) return <div className="ms-empty"><h3>No songs yet</h3><p>Add one in the Studio first.</p></div>;
  const stageIndex = STAGES.indexOf(draft.stage as typeof STAGES[number]);
  return <div className="ms-song-ws">
    <aside className="ms-list" aria-label="Songs">
      {songs.map(s => <button type="button" key={s.id} aria-pressed={s.id === draft.id} disabled={dirty && s.id !== draft.id} onClick={() => onSelect(s.id!)}>
        <i className="ms-art" style={{ background: ART[s.art] ?? ART.amber }}/><span><strong>{s.title}</strong><small>{s.stage}</small></span></button>)}
      {dirty && <small className="ms-muted">Save or undo changes to switch songs.</small>}
    </aside>
    <div className="ms-ws">
      <DetailScreen id="music-song" name="Song" open itemId={draft.id ?? "new"} quiet={!selected} title={draft.title.trim() || "Untitled song"}
        onOpen={key => { const song = songs.find(item => detailKey(item.id ?? "") === key); if (song?.id && !dirty) onSelect(song.id); }} onClose={() => { /* the Song page always shows a song; Back moves to the previous one */ }}/>
      <div className="ms-row ms-ws__head">
        <label className="ms-art ms-art--big" style={{ background: ART[draft.art] ?? ART.amber }}><span className="sr-only">Card colour</span>
          <select value={draft.art} onChange={e => edit({ art: e.target.value })}>{Object.keys(ART).map(c => <option key={c}>{c}</option>)}</select></label>
        <div className="ms-ws__title">
          <input className="ms-title" value={draft.title} maxLength={160} aria-label="Song title" onChange={e => edit({ title: e.target.value })}/>
          <div className="ms-row ms-wrap">
            <label className="ms-pill">BPM<input inputMode="decimal" value={draft.bpm ?? ""} onChange={e => edit({ bpm: e.target.value ? Number(e.target.value) || null : null })}/></label>
            <label className="ms-pill">Key<input value={draft.key} maxLength={40} placeholder="D major" onChange={e => edit({ key: e.target.value })}/></label>
            <label className="ms-pill">Release<input type="date" value={draft.releaseDate} onChange={e => edit({ releaseDate: e.target.value })}/></label>
            <label className="ms-pill ms-pill--wide">GarageBand<input value={draft.projectFile} maxLength={2000} placeholder="Slow burn.band" onChange={e => edit({ projectFile: e.target.value })}/></label>
          </div>
        </div>
        <div className="ms-row">
          <button type="button" disabled={!dirty || busy} onClick={() => current && setDraft(current)}>Undo</button>
          <button type="button" className="ms-primary" disabled={!dirty || busy || !draft.title.trim()} onClick={() => void onSave(draft, "Saved.")}>Save</button>
        </div>
      </div>

      <ol className="ms-stages" aria-label="Stage">
        {STAGES.map((stage, i) => <li key={stage}><button type="button" aria-pressed={draft.stage === stage} className={i <= stageIndex ? "ms-stage ms-stage--on" : "ms-stage"} onClick={() => edit({ stage })}><i/>{stage}</button></li>)}
      </ol>

      <div className="ms-ws__grid">
        <section className="ms-card ms-editor">
          <PageNavigator id="song-text" name="Song text" items={SONG_TEXT} current={view} onChoose={next => setView(next as "lyrics" | "notes")}/>
          {view === "lyrics"
            ? <textarea value={draft.lyrics} maxLength={30000} aria-label="Lyrics" placeholder={"[Verse 1]\nYour lines here\n\n[Chorus]\n…"} onChange={e => edit({ lyrics: e.target.value })}/>
            : <textarea value={draft.body} maxLength={30000} aria-label="Session notes" placeholder="Ideas, arrangement, mix notes, what to try next…" onChange={e => edit({ body: e.target.value })}/>}
        </section>
        <div className="ms-stack">
          <section className="ms-card">
            <h3>Release checklist <small className="ms-muted">{items.filter(i => draft.checklist[i]).length}/{items.length}</small></h3>
            {items.map(item => <label key={item} className="ms-check"><input type="checkbox" checked={Boolean(draft.checklist[item])}
              onChange={e => edit({ checklist: { ...draft.checklist, [item]: e.target.checked } })}/>{item}</label>)}
          </section>
          <section className="ms-card">
            <h3>Studio sessions <small className="ms-muted">{Math.round(draft.sessions.reduce((a, s) => a + s.minutes, 0) / 6) / 10} h total</small></h3>
            <div className="ms-row ms-wrap">
              <input type="date" aria-label="Session date" value={session.date} onChange={e => setSession({ ...session, date: e.target.value })}/>
              <input inputMode="numeric" aria-label="Minutes" className="ms-short" value={session.minutes} onChange={e => setSession({ ...session, minutes: Math.max(0, Math.min(1440, Number(e.target.value) || 0)) })}/>
              <input aria-label="What you did" placeholder="What you did" maxLength={300} value={session.note} onChange={e => setSession({ ...session, note: e.target.value })}/>
              <button type="button" disabled={!session.date} onClick={() => { edit({ sessions: [session, ...draft.sessions] }); setSession({ ...session, note: "" }); }}>Add</button>
            </div>
            <ul className="ms-lines">{draft.sessions.slice(0, 8).map((s, i) => <li key={i}><span>{s.note || "Session"} · {s.minutes} min</span><small>{s.date}</small>
              <button type="button" aria-label="Remove session" onClick={() => edit({ sessions: draft.sessions.filter((_, j) => j !== i) })}>✕</button></li>)}</ul>
          </section>
        </div>
      </div>

      <div className="ms-ws__grid">
        <section className="ms-card">
          <h3>Releases</h3>
          <ul className="ms-lines">{draft.releases.map((r, i) => <li key={i}><span>{r.platform}</span><a href={r.url} target="_blank" rel="noreferrer">Open</a>
            <button type="button" aria-label={`Remove ${r.platform} link`} onClick={() => edit({ releases: draft.releases.filter((_, j) => j !== i) })}>✕</button></li>)}</ul>
          <div className="ms-row ms-wrap">
            <select aria-label="Release platform" value={release.platform} onChange={e => setRelease({ ...release, platform: e.target.value })}>{PLATFORMS.map(p => <option key={p}>{p}</option>)}</select>
            <input type="url" aria-label="Release link" placeholder="https://…" value={release.url} onChange={e => setRelease({ ...release, url: e.target.value })}/>
            <button type="button" disabled={!release.url.startsWith("https://") || draft.releases.length >= 12} onClick={() => { edit({ releases: [...draft.releases, release] }); setRelease({ ...release, url: "" }); }}>Add link</button>
          </div>
        </section>
        <section className="ms-card">
          <h3>Numbers for this song</h3>
          {draft.stats.length ? <div className="ms-scroll"><table className="ms-table"><thead><tr><th>Date</th><th>Platform</th><th>Metric</th><th>Count</th><th></th></tr></thead>
            <tbody>{[...draft.stats].map((s, i) => ({ s, i })).sort((a, b) => b.s.date.localeCompare(a.s.date)).map(({ s, i }) => <tr key={i}>
              <td>{s.date}</td><td>{s.platform}</td><td>{s.metric}</td><td className="ms-num">{fmt(s.value)}</td>
              <td><button type="button" aria-label="Remove number" onClick={() => edit({ stats: draft.stats.filter((_, j) => j !== i) })}>✕</button></td></tr>)}</tbody></table></div>
            : <p className="ms-muted">Log numbers on the Dashboard or tell ZAE.</p>}
        </section>
      </div>
      <div className="ms-row">
        <button type="button" disabled={busy || dirty} onClick={() => void onSave({ ...draft, archived: true }, `${draft.title} archived.`)}>Archive song</button>
        <small className="ms-muted">{dirty ? "Unsaved changes" : "Saved on your PC"}</small>
      </div>
    </div>
  </div>;
}

// ---- Connections: room for live analytics
function Connections({ connections }: { connections: Connection[] }) {
  return <div className="ms-conn">
    <p className="ms-muted">Live analytics will fill the Dashboard automatically once a platform is connected. Until then, numbers you log (or tell ZAE) are used, marked "Manual".</p>
    <div className="ms-platforms">
      {connections.map(c => <section key={c.platform} className="ms-card ms-conn__card">
        <header><strong>{c.platform}</strong><span className={`ms-chip ms-chip--${c.status === "connected" ? "live" : "off"}`}>{c.status === "connected" ? "Connected" : "Not connected"}</span></header>
        <small className="ms-muted">Main measure: {c.metric}</small>
        <p>{c.needs}</p>
        <button type="button" disabled title="Not built yet: tell Claude which platform to connect first">Connect</button>
      </section>)}
    </div>
  </div>;
}
