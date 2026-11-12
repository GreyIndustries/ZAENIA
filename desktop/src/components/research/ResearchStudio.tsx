import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { AddToNotebook, AnalysisResult, NeedsServer, UNTRUSTED_NOTE, useAnalysis, type Topic } from "./researchShared";
import "./ResearchStudio.css";

/**
 * Research, reworked (Grey's picks, 2026-10-29): the Desk first (one search across everything), then the Reader
 * (one calm view for news, books, scripture and saved sources), then the Evidence board (a question, claims sorted
 * into Supports / Contradicts / Open, and a verdict built only from them). ZAE suggests; Grey decides what stays.
 */
export type ReadItem = { kind: string; title: string; meta?: string; url?: string; book?: boolean; topicId?: string; sourceId?: string; text?: string };
type DeskItem = { kind: string; title: string; meta?: string; url?: string; page?: string; readable?: boolean; text?: string; topicId?: string; sourceId?: string | null };
type DeskFound = { query: string; results: DeskItem[]; counts: Record<string, number>; failed: string[]; overview: { title: string; summary: string; url: string } | null };
type Claim = { id: string; text: string; column: Column; source: string };
type Column = "supports" | "contradicts" | "open";
type BoardTopic = { id: string; name: string; noteId?: string; question?: string; notes: string; claims?: Claim[];
  sources: { id: string; title: string; kind: string; url: string; meta: string; chars: number }[] };
type Mentions = { label: string; series: { term: string; points: { period: string; rate: number }[] }[] };

const SOURCES = [["library", "Library"], ["news", "News"], ["scripture", "Scripture"], ["notebook", "Notebook"]] as const;
const KIND_LABEL: Record<string, string> = { library: "Library", news: "News", scripture: "Scripture", notebook: "Notebook", web: "Web", book: "Library" };
const COLUMNS: [Column, string][] = [["supports", "Supports"], ["contradicts", "Contradicts"], ["open", "Open questions"]];
const remember = <T,>(key: string, fallback: T): T => { try { return JSON.parse(localStorage.getItem(key) ?? "") as T; } catch { return fallback; } };
const keep = (key: string, value: unknown) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* optional */ } };
const itemKey = (item: ReadItem) => item.sourceId ?? item.url ?? `${item.kind}:${item.title}`;

function useTopics() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const load = useCallback(() => { if (LIVE_API) api<{ topics: Topic[] }>("GET", "/api/research/notebook").then(reply => setTopics(reply.topics), () => undefined); }, []);
  useEffect(load, [load]);
  return { topics, reload: load };
}

// ------------------------------------------------------------------ Desk

export function ResearchDesk({ onRead, onBoard }: { onRead: (item: ReadItem) => void; onBoard: (topicId: string) => void }) {
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<string[]>(() => remember("zaenia.research.deskSources", SOURCES.map(([id]) => id)));
  const [found, setFound] = useState<DeskFound | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>(() => remember("zaenia.research.recent", []));
  const [mentions, setMentions] = useState<Mentions | null>(null);
  const [mentionsBusy, setMentionsBusy] = useState(false);
  const summary = useAnalysis();
  const { topics } = useTopics();

  const toggle = (id: string) => setChosen(current => {
    const next = current.includes(id) ? current.filter(x => x !== id) : [...current, id];
    const safe = next.length ? next : current;
    keep("zaenia.research.deskSources", safe); return safe;
  });
  const search = async (text = query) => {
    const q = text.trim();
    if (!q) return;
    setQuery(q); setBusy(true); setError(null); setFound(null); setMentions(null); summary.clear();
    const nextRecent = [q, ...recent.filter(item => item.toLowerCase() !== q.toLowerCase())].slice(0, 8);
    setRecent(nextRecent); keep("zaenia.research.recent", nextRecent);
    try { setFound(await api<DeskFound>("GET", `/api/research/desk?q=${encodeURIComponent(q)}&sources=${chosen.join(",")}`, undefined, { timeoutMs: 90_000 })); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  };
  const material = useMemo(() => !found ? "" : [
    found.overview ? `[Encyclopedia] ${found.overview.title}: ${found.overview.summary}` : "",
    ...found.results.map(item => `[${KIND_LABEL[item.kind] ?? item.kind}] ${item.title} (${item.meta ?? ""}) ${item.text ?? ""}`.trim()),
  ].filter(Boolean).join("\n"), [found]);
  const showMentions = async () => {
    if (!found) return;
    setMentionsBusy(true);
    try { setMentions(await api<Mentions>("GET", `/api/research/history?terms=${encodeURIComponent(found.query.slice(0, 60))}&source=newspapers`, undefined, { timeoutMs: 150_000 })); }
    catch (failure) { setError(errorText(failure)); }
    finally { setMentionsBusy(false); }
  };
  const read = (item: DeskItem) => onRead(item.kind === "notebook" ? { kind: "notebook", title: item.title, meta: item.meta, topicId: item.topicId, sourceId: item.sourceId ?? undefined, url: item.url }
    : { kind: item.kind, title: item.title, meta: item.meta, url: item.url, book: item.kind === "library", text: item.text });

  if (!LIVE_API) return <NeedsServer what="The research desk"/>;
  const points = mentions?.series[0]?.points ?? [];
  const peak = Math.max(1e-9, ...points.map(point => point.rate));
  return <div className="rs">
    <form className="rs-desk-search" onSubmit={(event: FormEvent) => { event.preventDefault(); void search(); }}>
      <span className="rs-kicker">One search across everything</span>
      <label className="rs-searchbox zx-inset">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input value={query} maxLength={200} placeholder="Research anything…" aria-label="Research anything" onChange={event => setQuery(event.target.value)}/>
        <button type="submit" className="rs-primary" disabled={busy || !query.trim()}>{busy ? "Searching…" : "Research"}</button>
      </label>
      <div className="rs-chips" role="group" aria-label="Sources to search">
        {SOURCES.map(([id, label]) => <button key={id} type="button" aria-pressed={chosen.includes(id)} onClick={() => toggle(id)}>{label}{found?.counts[id] !== undefined ? ` · ${found.counts[id]}` : ""}</button>)}
      </div>
      {!found && recent.length > 0 && <div className="rs-chips rs-chips--recent"><small>Recent:</small>{recent.map(item => <button key={item} type="button" onClick={() => void search(item)}>{item}</button>)}</div>}
    </form>
    {error && <p className="rs-error" role="alert">{error}</p>}
    {found && found.failed.length > 0 && <p className="rs-muted">{found.failed.map(name => KIND_LABEL[name] ?? name).join(", ")} didn't answer this time; the rest are below.</p>}
    <div className="rs-desk-grid">
      <section className="zx-card">
        <h2 className="zx-title">ZAE's summary</h2>
        {!found && <p className="rs-muted">Search above. ZAE checks the Library, world news, scripture and your notebook at once, then can sum up what they say.</p>}
        {found?.overview && <div className="zx-inset rs-overview"><b>{found.overview.title}</b><p>{found.overview.summary}</p>
          {found.overview.url && <a href={found.overview.url} target="_blank" rel="noreferrer">Encyclopedia article</a>}</div>}
        {found && <button type="button" className="rs-primary" disabled={!material || Boolean(summary.busy)}
          onClick={() => void summary.run("summing up", "ask", { text: material }, `What do these sources say about "${found.query}"? Answer in 3-5 sentences and name which source each point comes from.`)}>Sum up with ZAE</button>}
        <AnalysisResult busy={summary.busy} result={summary.result} error={summary.error}/>
        {summary.result && <AddToNotebook source={{ title: `Desk summary: ${found?.query ?? ""}`, kind: "pasted", text: summary.result }}/>}
        <small className="rs-muted">{UNTRUSTED_NOTE}</small>
      </section>
      <section className="zx-card">
        <h2 className="zx-title">Sources {found ? <small>{found.results.length}</small> : null}</h2>
        {busy && <p className="rs-muted" role="status">Checking every source…</p>}
        {found && found.results.length === 0 && <p className="rs-muted">Nothing found. Try fewer or different words.</p>}
        <ul className="rs-list">
          {found?.results.map((item, index) => <li key={`${item.kind}-${index}`} className="zx-inset rs-result">
            <span className={`rs-kind rs-kind--${item.kind}`}>{KIND_LABEL[item.kind] ?? item.kind}</span>
            <b>{item.title}</b>
            {item.meta && <small>{item.meta}</small>}
            {item.text && <p>{item.text}</p>}
            <span className="rs-row">
              {(item.readable || item.text) && <button type="button" onClick={() => read(item)}>Read</button>}
              {item.kind === "notebook" && item.topicId && <button type="button" onClick={() => onBoard(item.topicId!)}>Open board</button>}
              {(item.page || item.url) && item.kind !== "notebook" && <a href={item.page || item.url} target="_blank" rel="noreferrer">Open site</a>}
              {item.kind !== "notebook" && <AddToNotebook source={{ title: item.title, kind: item.kind === "library" ? "book" : item.kind === "news" ? "news" : "web",
                url: item.url, text: item.text, meta: item.meta, fetch: Boolean(item.url) }}/>}
            </span>
          </li>)}
        </ul>
      </section>
      <section className="zx-card">
        <h2 className="zx-title">Mentions over time</h2>
        {!mentions && <button type="button" disabled={!found || mentionsBusy} onClick={() => void showMentions()}>{mentionsBusy ? "Counting old newspapers…" : "Show mentions over time"}</button>}
        {mentions && points.length > 0 && <figure className="rs-bars" aria-label={`How often "${mentions.series[0].term}" appears in ${mentions.label}`}>
          <div>{points.map(point => <span key={point.period} title={`${point.period}: ${point.rate.toFixed(2)}`} style={{ height: `${Math.max(2, point.rate / peak * 100)}%` }}/>)}</div>
          <figcaption><span>{points[0].period}</span><span>{mentions.label}</span><span>{points[points.length - 1].period}</span></figcaption>
        </figure>}
        {mentions && points.length === 0 && <p className="rs-muted">No mentions found.</p>}
        <h2 className="zx-title">Your investigations</h2>
        {topics.length === 0 && <p className="rs-muted">None yet. Add a source to the notebook or start one on the Evidence board.</p>}
        <ul className="rs-list rs-list--plain">{topics.slice(0, 6).map(topic => <li key={topic.id}>
          <button type="button" className="rs-linkrow" onClick={() => onBoard(topic.id)}><b>{topic.name}</b><small>{topic.sources} sources</small></button></li>)}</ul>
      </section>
    </div>
  </div>;
}

// ------------------------------------------------------------------ Reader

type Highlight = { quote: string; at: string };

export function ResearchReader({ item, onRead }: { item: ReadItem | null; onRead: (item: ReadItem) => void }) {
  const [shelf, setShelf] = useState<ReadItem[]>(() => remember("zaenia.research.shelf", []));
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [selection, setSelection] = useState("");
  const [side, setSide] = useState<"zae" | "highlights" | "translate">("zae");
  const [question, setQuestion] = useState("");
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [topicId, setTopicId] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [language, setLanguage] = useState(() => remember("zaenia.research.readerLanguage", "English"));
  const [languages, setLanguages] = useState<string[]>(["English", "Spanish", "French", "German", "Hebrew", "Greek", "Latin"]);
  const [translation, setTranslation] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);
  const analysis = useAnalysis();
  const { topics } = useTopics();
  const page = useRef<HTMLDivElement>(null);
  const key = item ? itemKey(item) : "";

  useEffect(() => { if (LIVE_API) api<{ languages: string[] }>("GET", "/api/research/translate/languages").then(reply => setLanguages(reply.languages), () => undefined); }, []);
  useEffect(() => {
    if (!item || !LIVE_API) return;
    let live = true;
    setText(""); setError(null); setSelection(""); setTranslation(null); analysis.clear(); setBusy(true);
    setTopicId(item.topicId ?? "");
    setHighlights(remember<Record<string, Highlight[]>>("zaenia.research.highlights", {})[itemKey(item)] ?? []);
    const nextShelf = [{ ...item, text: item.kind === "scripture" ? item.text : undefined }, ...shelf.filter(other => itemKey(other) !== itemKey(item))].slice(0, 12);
    setShelf(nextShelf); keep("zaenia.research.shelf", nextShelf);
    const load = async (): Promise<string> => {
      if (item.text) return item.text;
      if (item.topicId && item.sourceId) {
        const source = await api<{ text: string; url: string }>("GET", `/api/research/notebook/${item.topicId}/sources/${item.sourceId}`);
        if (source.text) return source.text;
        if (!source.url) return "This saved source has no text kept, only its title.";
        return (await api<{ text: string }>("GET", `/api/research/article?url=${encodeURIComponent(source.url)}`, undefined, { timeoutMs: 60_000 })).text;
      }
      if (item.url && item.book) return (await api<{ excerpt: string }>("POST", "/api/research/library/read", { url: item.url }, { timeoutMs: 60_000 })).excerpt;
      if (item.url) return (await api<{ text: string }>("GET", `/api/research/article?url=${encodeURIComponent(item.url)}`, undefined, { timeoutMs: 60_000 })).text;
      return "";
    };
    load().then(value => { if (live) setText(value || "This page has no readable text. Open the site instead."); },
      failure => { if (live) setError(errorText(failure)); }).finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reading position: remembered per item and restored when it opens again.
  useEffect(() => {
    if (!text || !page.current) return;
    const saved = remember<Record<string, number>>("zaenia.research.positions", {})[key] ?? 0;
    const box = page.current;
    requestAnimationFrame(() => { box.scrollTop = saved * Math.max(0, box.scrollHeight - box.clientHeight); setProgress(saved); });
  }, [text, key]);
  const scrolled = () => {
    const box = page.current;
    if (!box) return;
    const value = box.scrollHeight > box.clientHeight ? box.scrollTop / (box.scrollHeight - box.clientHeight) : 1;
    setProgress(value);
    const all = remember<Record<string, number>>("zaenia.research.positions", {});
    all[key] = Math.round(value * 1000) / 1000; keep("zaenia.research.positions", all);
  };
  const select = () => setSelection((window.getSelection()?.toString() ?? "").trim().slice(0, 1000));

  const saveHighlight = async () => {
    if (!item || !selection) return;
    const next = [{ quote: selection, at: new Date().toISOString() }, ...highlights].slice(0, 100);
    setHighlights(next);
    const all = remember<Record<string, Highlight[]>>("zaenia.research.highlights", {}); all[key] = next; keep("zaenia.research.highlights", all);
    const topic = topics.find(t => t.id === topicId);
    if (!topic?.noteId) { setNote("Highlight kept here. Pick a notebook topic to save highlights to its notes too."); return; }
    try {
      await api("POST", `/api/platform/notes/${topic.noteId}/append`, { text: `> "${selection}"\n> ${item.title}${item.url ? ` (${item.url})` : ""}` });
      setNote(`Saved to "${topic.name}" notes.`);
    } catch (failure) { setNote(errorText(failure)); }
  };
  const compare = async () => {
    const topic = topics.find(t => t.id === topicId);
    if (!topic) { setNote("Pick a notebook topic to compare with."); return; }
    try {
      const detail = await api<BoardTopic>("GET", `/api/research/notebook/${topic.id}`);
      const mine = `MY NOTES:\n${detail.notes.slice(0, 4000)}\n\nMY SOURCES:\n${detail.sources.map(s => `- ${s.title} ${s.meta}`).join("\n")}`;
      void analysis.run("comparing", "ask", { text: `READING: ${item?.title}\n${text.slice(0, 9000)}\n\n${mine}` },
        "How does this reading compare with my notes and sources? What is new, what agrees and what conflicts?");
    } catch (failure) { setNote(errorText(failure)); }
  };
  const translate = async () => {
    setTranslating(true); setTranslation(null);
    try { setTranslation((await api<{ translation: string }>("POST", "/api/research/translate", { text: (selection || text).slice(0, 6000), target: language }, { timeoutMs: 600_000 })).translation); }
    catch (failure) { setNote(errorText(failure)); }
    finally { setTranslating(false); }
  };

  if (!LIVE_API) return <NeedsServer what="The reader"/>;
  const minutesLeft = Math.max(1, Math.round(text.split(/\s+/).length * (1 - progress) / 230));
  return <div className="rs rs-reader">
    <aside className="zx-card rs-shelf">
      <span className="rs-kicker">Reading</span>
      {shelf.length === 0 && <p className="rs-muted">Open anything with "Read" on the Desk, or a source on the Evidence board, and it lands here.</p>}
      {shelf.map(entry => <button key={itemKey(entry)} type="button" aria-pressed={itemKey(entry) === key} onClick={() => onRead(entry)}>
        <b>{entry.title}</b><small>{KIND_LABEL[entry.kind] ?? entry.kind}{entry.meta ? ` · ${entry.meta}` : ""}</small></button>)}
      {shelf.length > 0 && <button type="button" className="rs-quiet" onClick={() => { setShelf([]); keep("zaenia.research.shelf", []); }}>Clear the shelf</button>}
    </aside>
    <main className="zx-card rs-page">
      {!item && <p className="rs-muted">Nothing open yet.</p>}
      {item && <>
        <div className="rs-row rs-muted"><span className={`rs-kind rs-kind--${item.kind}`}>{KIND_LABEL[item.kind] ?? item.kind}</span>
          <span>{item.meta}{text ? ` · about ${minutesLeft} min left` : ""}</span>
          {item.url && <a href={item.url} target="_blank" rel="noreferrer">Open site</a>}</div>
        <h1 className="rs-page__title">{item.title}</h1>
        {busy && <p className="rs-muted" role="status">Opening…</p>}
        {error && <p className="rs-error" role="alert">{error}</p>}
        <div ref={page} className="rs-page__text" onScroll={scrolled} onMouseUp={select} onKeyUp={select} tabIndex={0} aria-label="Reading text">
          {text.split(/\n{2,}|\n(?=\s*\n)/).map((para, index) => para.trim() && <p key={index}>{para.trim()}</p>)}
        </div>
        {selection && <div className="rs-selbar zx-inset" role="toolbar" aria-label="Selected text">
          <span>“{selection.slice(0, 90)}{selection.length > 90 ? "…" : ""}”</span>
          <button type="button" className="rs-primary" onClick={() => void saveHighlight()}>Save highlight</button>
          <button type="button" onClick={() => { setSide("zae"); void analysis.run("explaining", "ask", { text: text.slice(0, 12000) }, `Explain this part plainly: "${selection.slice(0, 400)}"`); }}>Explain</button>
          <button type="button" onClick={() => { setSide("translate"); void translate(); }}>Translate</button>
        </div>}
        <div className="rs-progress"><span><span style={{ width: `${Math.round(progress * 100)}%` }}/></span><small>{Math.round(progress * 100)}%</small></div>
      </>}
    </main>
    <aside className="zx-card rs-side">
      <div className="rs-seg" role="tablist" aria-label="Reader tools">
        {(["zae", "highlights", "translate"] as const).map(id => <button key={id} type="button" role="tab" aria-selected={side === id} onClick={() => setSide(id)}>
          {id === "zae" ? "ZAE" : id === "highlights" ? `Highlights${highlights.length ? ` · ${highlights.length}` : ""}` : "Translate"}</button>)}
      </div>
      <label className="rs-field"><small>Notebook topic</small>
        <select value={topicId} onChange={event => setTopicId(event.target.value)}><option value="">None</option>{topics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
      {note && <p className="rs-muted" role="status">{note}</p>}
      {side === "zae" && <>
        <button type="button" disabled={!text || Boolean(analysis.busy)} onClick={() => void analysis.run("summing up", item?.book ? "book" : "summary", { text: text.slice(0, 40000) })}>Summarise this</button>
        <button type="button" disabled={!text || !selection || Boolean(analysis.busy)} onClick={() => void analysis.run("explaining", "ask", { text: text.slice(0, 12000) }, `Explain this part plainly: "${selection.slice(0, 400)}"`)}>Explain the highlighted part</button>
        <button type="button" disabled={!text || Boolean(analysis.busy)} onClick={() => void analysis.run("sorting", "facts_opinion", { text: text.slice(0, 40000) })}>Facts vs opinion</button>
        <button type="button" disabled={!text || !topicId || Boolean(analysis.busy)} onClick={() => void compare()}>Compare with my notebook</button>
        <AnalysisResult busy={analysis.busy} result={analysis.result} error={analysis.error}/>
        <form className="rs-ask zx-inset" onSubmit={event => { event.preventDefault(); if (question.trim()) { void analysis.run("answering", "ask", { text: text.slice(0, 40000) }, question.trim()); setQuestion(""); } }}>
          <input value={question} maxLength={400} placeholder="Ask about this page…" aria-label="Ask about this page" disabled={!text} onChange={event => setQuestion(event.target.value)}/>
          <button type="submit" disabled={!text || !question.trim()}>Ask</button>
        </form>
      </>}
      {side === "highlights" && <ul className="rs-list rs-list--plain">
        {highlights.length === 0 && <li className="rs-muted">Select text on the page, then "Save highlight".</li>}
        {highlights.map((mark, index) => <li key={index} className="zx-inset rs-mark"><q>{mark.quote}</q><small>{new Date(mark.at).toLocaleDateString()}</small></li>)}
      </ul>}
      {side === "translate" && <>
        <label className="rs-field"><small>Into</small><select value={language} onChange={event => { setLanguage(event.target.value); keep("zaenia.research.readerLanguage", event.target.value); }}>
          {languages.map(name => <option key={name}>{name}</option>)}</select></label>
        <button type="button" className="rs-primary" disabled={!text || translating} onClick={() => void translate()}>{translating ? "Translating…" : selection ? "Translate the selection" : "Translate the start of the page"}</button>
        {translation && <div className="zx-inset rs-translation">{translation.split("\n").map((line, index) => <p key={index}>{line}</p>)}</div>}
      </>}
    </aside>
  </div>;
}

// ------------------------------------------------------------------ Evidence board

export function EvidenceBoard({ topicId, onTopic, onRead }: { topicId: string | null; onTopic: (id: string) => void; onRead: (item: ReadItem) => void }) {
  const { topics, reload } = useTopics();
  const [topic, setTopic] = useState<BoardTopic | null>(null);
  const [question, setQuestion] = useState("");
  const [newName, setNewName] = useState("");
  const [drafts, setDrafts] = useState<Record<Column, string>>({ supports: "", contradicts: "", open: "" });
  const [suggestions, setSuggestions] = useState<{ column: Column; text: string; source: string }[]>([]);
  const [suggesting, setSuggesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const verdict = useAnalysis();
  const current = topicId ?? topics[0]?.id ?? null;

  const open = useCallback(async (id: string) => {
    try { const next = await api<BoardTopic>("GET", `/api/research/notebook/${id}`); setTopic(next); setQuestion(next.question ?? ""); setSuggestions([]); setError(null); }
    catch (failure) { setError(errorText(failure)); }
  }, []);
  useEffect(() => { if (current && LIVE_API) { void open(current); verdict.clear(); } }, [current, open]); // eslint-disable-line react-hooks/exhaustive-deps

  const change = async (request: Promise<BoardTopic>) => {
    try { const next = await request; setTopic(next); setError(null); reload(); } catch (failure) { setError(errorText(failure)); }
  };
  const create = async (event: FormEvent) => {
    event.preventDefault();
    if (!newName.trim()) return;
    try { const made = await api<BoardTopic>("POST", "/api/research/notebook", { name: newName.trim() }); setNewName(""); reload(); onTopic(made.id); }
    catch (failure) { setError(errorText(failure)); }
  };
  const addClaim = (column: Column, text: string, source = "") => topic && change(api<BoardTopic>("POST", `/api/research/notebook/${topic.id}/claims`, { text, column, source }));
  const suggest = async () => {
    if (!topic) return;
    setSuggesting(true); setError(null);
    try { setSuggestions((await api<{ suggestions: typeof suggestions }>("POST", `/api/research/notebook/${topic.id}/claims/suggest`, {}, { timeoutMs: 300_000 })).suggestions); }
    catch (failure) { setError(errorText(failure)); }
    finally { setSuggesting(false); }
  };
  const claims = topic?.claims ?? [];
  const askVerdict = () => {
    const cards = COLUMNS.map(([id, label]) => `${label.toUpperCase()}:\n${claims.filter(c => c.column === id).map(c => `- ${c.text}${c.source ? ` (${c.source})` : ""}`).join("\n") || "- none"}`).join("\n\n");
    void verdict.run("weighing the cards", "ask", { text: cards },
      `Using only these cards, answer in one or two sentences: ${(question || topic?.name || "").slice(0, 280)}. Then say how sure you are (low, medium or high) and why.`);
  };

  if (!LIVE_API) return <NeedsServer what="The evidence board"/>;
  return <div className="rs rs-board">
    <aside className="zx-card rs-shelf">
      <span className="rs-kicker">Investigations</span>
      {topics.map(t => <button key={t.id} type="button" aria-pressed={t.id === topic?.id} onClick={() => onTopic(t.id)}>
        <b>{t.name}</b><small>{t.sources} sources{t.updatedAt ? ` · ${new Date(t.updatedAt).toLocaleDateString([], { month: "short", day: "numeric" })}` : ""}</small></button>)}
      <form className="rs-ask zx-inset" onSubmit={event => void create(event)}>
        <input value={newName} maxLength={120} placeholder="New investigation…" aria-label="New investigation name" onChange={event => setNewName(event.target.value)}/>
        <button type="submit" disabled={!newName.trim()}>Add</button>
      </form>
    </aside>
    <main className="rs-board__main">
      {error && <p className="rs-error" role="alert">{error}</p>}
      {!topic && <p className="rs-muted">Start an investigation on the left, or add sources from the Desk to a notebook topic.</p>}
      {topic && <>
        <div className="rs-row rs-row--between">
          <div className="rs-board__head">
            <input className="rs-question zx-title" value={question} maxLength={300} placeholder={`What are you trying to find out about ${topic.name}?`}
              aria-label="The question" onChange={event => setQuestion(event.target.value)}
              onBlur={() => { if (question !== (topic.question ?? "")) void change(api<BoardTopic>("PUT", `/api/research/notebook/${topic.id}/question`, { question })); }}/>
            <small className="rs-muted">{topic.name} · {topic.sources.length} sources · {claims.length} claims</small>
          </div>
          <button type="button" className="rs-primary" disabled={suggesting || topic.sources.length === 0} onClick={() => void suggest()}
            title={topic.sources.length === 0 ? "Add sources to this topic first" : undefined}>{suggesting ? "ZAE is reading the sources…" : "Ask ZAE to suggest claims"}</button>
        </div>
        {suggestions.length > 0 && <section className="zx-card rs-suggest" aria-label="Suggested claims">
          <div className="rs-row rs-row--between"><b>ZAE suggests these. Keep the ones you agree with.</b><button type="button" className="rs-quiet" onClick={() => setSuggestions([])}>Dismiss all</button></div>
          {suggestions.map((s, index) => <div key={index} className="zx-inset rs-row rs-suggest__row">
            <span className={`rs-col-tag rs-col-tag--${s.column}`}>{COLUMNS.find(([id]) => id === s.column)?.[1]}</span>
            <span className="rs-grow">{s.text}{s.source && <small> · {s.source}</small>}</span>
            <button type="button" onClick={() => { void addClaim(s.column, s.text, s.source); setSuggestions(list => list.filter((_, i) => i !== index)); }}>Keep</button>
            <button type="button" className="rs-quiet" aria-label="Drop this suggestion" onClick={() => setSuggestions(list => list.filter((_, i) => i !== index))}>✕</button>
          </div>)}
        </section>}
        <div className="rs-columns">
          {COLUMNS.map(([id, label]) => <section key={id} className={`zx-card rs-column rs-column--${id}`}>
            <div className="rs-row rs-row--between"><b>{label}</b><small>{claims.filter(c => c.column === id).length}</small></div>
            {claims.filter(c => c.column === id).map(claim => <article key={claim.id} className="zx-inset rs-claim">
              <span>{claim.text}</span>
              <small>{claim.source || (id === "open" ? "Needs a source" : "No source given")}</small>
              <span className="rs-row">
                <select value={claim.column} aria-label="Move this claim" onChange={event => void change(api<BoardTopic>("PUT", `/api/research/notebook/${topic.id}/claims/${claim.id}`, { column: event.target.value }))}>
                  {COLUMNS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select>
                <button type="button" className="rs-quiet" aria-label="Delete this claim" onClick={() => void change(api<BoardTopic>("DELETE", `/api/research/notebook/${topic.id}/claims/${claim.id}`))}>✕</button>
              </span>
            </article>)}
            <form className="rs-ask zx-inset" onSubmit={event => { event.preventDefault(); if (drafts[id].trim()) { void addClaim(id, drafts[id].trim()); setDrafts(d => ({ ...d, [id]: "" })); } }}>
              <input value={drafts[id]} maxLength={500} placeholder="Add a claim…" aria-label={`Add a claim to ${label}`} onChange={event => setDrafts(d => ({ ...d, [id]: event.target.value }))}/>
              <button type="submit" disabled={!drafts[id].trim()}>Add</button>
            </form>
          </section>)}
        </div>
        <section className="zx-card rs-verdict">
          <div className="rs-row rs-row--between"><b className="rs-accent">Verdict so far</b>
            <button type="button" disabled={claims.length === 0 || Boolean(verdict.busy)} onClick={askVerdict}>Weigh the cards</button></div>
          {!verdict.result && !verdict.busy && !verdict.error && <p className="rs-muted">ZAE's one-line answer and how sure she is, built only from the cards above. You decide what to keep.</p>}
          <AnalysisResult busy={verdict.busy} result={verdict.result} error={verdict.error}/>
        </section>
        {topic.sources.length > 0 && <section className="zx-card">
          <b>Sources in this investigation</b>
          <ul className="rs-list rs-list--plain">{topic.sources.map(source => <li key={source.id} className="rs-row">
            <span className={`rs-kind rs-kind--${source.kind === "book" ? "library" : source.kind}`}>{KIND_LABEL[source.kind] ?? source.kind}</span>
            <span className="rs-grow">{source.title}</span>
            <button type="button" onClick={() => onRead({ kind: "notebook", title: source.title, meta: `In ${topic.name}`, topicId: topic.id, sourceId: source.id, url: source.url })}>Read</button>
          </li>)}</ul>
        </section>}
      </>}
    </main>
  </div>;
}
