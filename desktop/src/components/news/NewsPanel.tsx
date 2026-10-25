import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { AddToNotebook, AnalysisResult, useAnalysis } from "../research/researchShared";
import "../research/Research.css";
import { openLink } from "../../core/openLink";
import "./NewsPanel.css";
import previewArtA from "../../assets/jarvis-hologram.webp";
import previewArtB from "../../assets/core/warehouse-clean.webp";
import previewArtC from "../../assets/neural-core-sphere.webp";

type Story = { title: string; link: string; summary?: string; image?: string | null; published?: string | null; sources: string[]; links: Record<string, string>; coverage: number };
type SourceStatus = { name: string; focus: string[]; why: string; ok?: boolean; error?: string; checkedAt?: string };
type News = { updatedAt: string | null; stories: Story[]; sources: SourceStatus[] };

const TOPICS = [
  { id: "", label: "Everything" }, { id: "world", label: "World" }, { id: "us", label: "US" }, { id: "science", label: "Science" },
  { id: "ai", label: "AI" }, { id: "hardware", label: "Hardware" }, { id: "security", label: "Security" }, { id: "gaming", label: "Gaming" },
];
type WorldStory = { title: string; link: string; source: string; country: string; published: string };

// Preview-only sample stories (never shown in the live app).
const PREVIEW: News = {
  updatedAt: new Date().toISOString(),
  sources: [],
  stories: [
    ["A new generation of graphics cards arrives with a focus on efficiency", "Tom's Hardware", "The Verge"],
    ["Researchers release a compact open model that runs on a laptop", "MIT Technology Review"],
    ["Emergency patch issued for a widely used web framework", "BleepingComputer", "The Register"],
    ["Inside the race to build quieter, cooler data centres", "IEEE Spectrum"],
    ["Regulators publish new rules for consumer AI assistants", "BBC News Technology"],
    ["The best budget mechanical keyboards, tested", "Wired"],
    ["Why satellite internet is getting faster in rural areas", "NPR Technology"],
  ].map(([title, ...sources], index) => ({
    title, sources, links: {}, coverage: sources.length, link: `https://example.com/${index}`,
    summary: "Preview text: the live window shows each story's own summary from its newsroom.",
    published: new Date(Date.now() - (index + 1) * 47 * 60000).toISOString(), image: [previewArtA, null, previewArtB, null, previewArtC, null, null][index] ?? null,
  })),
};

function ago(iso?: string | null): string {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`;
}

// A colour per newsroom, used for the glass tint when a story has no picture.
const HUES: Record<string, number> = { "Ars Technica": 18, "MIT Technology Review": 350, "IEEE Spectrum": 205, "BBC News Technology": 0,
  "NPR Technology": 222, "The Verge": 285, "Wired": 45, "The Register": 0, "Tom's Hardware": 195, "BleepingComputer": 165 };
const hue = (story: Story) => HUES[story.sources[0]] ?? 210;

/** Bento layout: the first story is the hero; then a repeating rhythm of wide, tall and regular glass panels. */
const RHYTHM = ["wide", "tall", "", "", "wide", "", "tall", "", "", "wide", "", ""] as const;
function sizeFor(story: Story, index: number): string {
  if (story.coverage > 1 && index < 6) return "wide";
  const size = RHYTHM[index % RHYTHM.length];
  return size === "tall" && !story.image ? "" : size;
}

function Picture({ story }: { story: Story }) {
  const [failed, setFailed] = useState(false);
  if (!story.image || failed) return <div className="news__art" aria-hidden="true" style={{ "--hue": hue(story) } as CSSProperties}><span>{story.sources[0]?.slice(0, 2)}</span></div>;
  return <img className="news__img" src={story.image} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)}/>;
}

function Sources({ story }: { story: Story }) {
  return <span className="news__sources">
    {story.sources.slice(0, 3).map((name, index) => <span key={name}>{index > 0 && " · "}
      <a href={story.links[name] ?? story.link} onClick={event => { event.preventDefault(); event.stopPropagation(); openLink(story.links[name] ?? story.link); }}>{name}</a>
    </span>)}
    {story.coverage > 1 && <em className="news__badge">{story.coverage} sources</em>}
    {story.published && <span className="news__age">{ago(story.published)}</span>}
  </span>;
}

/** One story opened in the reader: its text without ads, and ZAE's summary or facts-vs-opinion. */
function Reader({ story, onClose }: { story: { title: string; link: string; source: string }; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const analysis = useAnalysis();
  const material = text ? { text, title: story.title } : { url: story.link, kind: "article" as const, title: story.title };
  const read = async () => {
    setBusy(true); setError(null);
    try { setText((await api<{ text: string }>("GET", `/api/research/article?url=${encodeURIComponent(story.link)}`, undefined, { timeoutMs: 60_000 })).text || "This page has no readable article text."); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  };
  return <aside className="news__reader research" aria-label="Story reader">
    <div className="news__reader-head"><strong>{story.title}</strong><button type="button" onClick={onClose} aria-label="Close reader">✕</button></div>
    <p className="research__meta">{story.source} · Web text is untrusted: ZAE reads it, never follows it.</p>
    <div className="research__actions">
      <button type="button" className="research__primary" disabled={busy} onClick={() => void read()}>{busy ? "Reading…" : "Read article"}</button>
      <button type="button" disabled={!!analysis.busy} onClick={() => void analysis.run("summarising", "summary", material)}>Summarise</button>
      <button type="button" disabled={!!analysis.busy} onClick={() => void analysis.run("separating facts and opinion", "facts_opinion", material)}>Facts vs opinion</button>
      <button type="button" onClick={() => openLink(story.link)}>Open in browser</button>
      <AddToNotebook source={{ title: story.title, kind: "news", url: story.link, text: text ?? "", meta: story.source, fetch: !text }}/>
    </div>
    <form className="research__bar" onSubmit={event => { event.preventDefault(); if (question.trim()) void analysis.run("answering", "ask", material, question.trim()); }}>
      <input value={question} maxLength={500} placeholder="Ask ZAE about this story…" aria-label="Ask ZAE about this story" onChange={event => setQuestion(event.target.value)}/>
      <button type="submit" disabled={!question.trim() || !!analysis.busy}>Ask</button>
    </form>
    <AnalysisResult {...analysis}/>
    {error && <p className="research__error" role="alert">{error}</p>}
    {text && <div className="news__reader-text">{text.split("\n\n").map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>}
  </aside>;
}

/** World search: articles from news sites everywhere that mention a keyword (GDELT). */
function WorldSearch({ onOpen }: { onOpen: (story: { title: string; link: string; source: string }) => void }) {
  const [keyword, setKeyword] = useState("");
  const [days, setDays] = useState(7);
  const [stories, setStories] = useState<WorldStory[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const search = async () => {
    setBusy(true); setError(null);
    try { setStories((await api<{ stories: WorldStory[] }>("GET", `/api/research/worldnews?q=${encodeURIComponent(keyword.trim())}&days=${days}`, undefined, { timeoutMs: 90_000 })).stories); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  };
  return <section className="news__world research" aria-label="Search world news">
    <form className="research__bar" onSubmit={event => { event.preventDefault(); if (keyword.trim()) void search(); }}>
      <input value={keyword} maxLength={80} placeholder="Search world news sites for a keyword…" aria-label="World news keyword" onChange={event => setKeyword(event.target.value)}/>
      <select value={days} aria-label="How far back" onChange={event => setDays(Number(event.target.value))}>{[1, 3, 7, 14, 30].map(value => <option key={value} value={value}>{value} day{value > 1 ? "s" : ""}</option>)}</select>
      <button type="submit" className="research__primary" disabled={busy || !keyword.trim()}>{busy ? "Searching…" : "Search world news"}</button>
    </form>
    {error && <p className="research__error" role="alert">{error}</p>}
    {stories && (stories.length ? <ol className="news__world-list">{stories.map(story => <li key={story.link}>
      <button type="button" onClick={() => onOpen({ title: story.title, link: story.link, source: story.source })}>{story.title}</button>
      <small>{story.source}{story.country ? ` · ${story.country}` : ""}{story.published ? ` · ${story.published.slice(0, 4)}-${story.published.slice(4, 6)}-${story.published.slice(6, 8)}` : ""}</small>
    </li>)}</ol> : <p className="research__empty">No articles found for that keyword.</p>)}
  </section>;
}

/** News: tech and world headlines from ZAE's tracked newsrooms, laid out as a glass magazine, with a reader. */
export function NewsPanel() {
  const [reading, setReading] = useState<{ title: string; link: string; source: string } | null>(null);
  const open = (story: Story) => setReading({ title: story.title, link: story.link, source: story.sources.join(", ") });
  const [topic, setTopic] = useState("");
  const [query, setQuery] = useState("");
  const [news, setNews] = useState<News | null>(LIVE_API ? null : PREVIEW);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSources, setShowSources] = useState(false);

  const load = useCallback(async (refresh = false) => {
    if (!LIVE_API) return;
    setBusy(true); setError(null);
    try {
      const params = new URLSearchParams({ limit: "50", topic, q: query.trim() });
      setNews(refresh ? await api<News>("POST", "/api/news/tech/refresh", undefined, { timeoutMs: 60000 })
        : await api<News>("GET", `/api/news/tech?${params}`));
    } catch (failure) { setError(failure instanceof Error ? failure.message : "News couldn't load."); }
    finally { setBusy(false); }
  }, [topic, query]);
  useEffect(() => { void load(); }, [topic]); // eslint-disable-line react-hooks/exhaustive-deps

  const [hero, rest, quick] = useMemo(() => {
    const stories = news?.stories ?? [];
    const lead = stories.find(story => story.image) ?? stories[0];
    const others = stories.filter(story => story !== lead);
    return [lead, others.slice(0, 21), others.slice(21)];
  }, [news]);
  const reachable = news?.sources.filter(source => source.ok !== false).length ?? 0;
  const today = new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

  return <div className={`section-content news${reading ? " news--reading" : ""}`}>
    <header className="news__masthead">
      <div>
        <span className="news__kicker">{today}</span>
        <h2 className="news__title">The brief</h2>
        <span className="news__meta">{news?.updatedAt ? `Checked ${ago(news.updatedAt)}` : "Not checked yet"}{news?.sources.length ? ` · ${reachable} of ${news.sources.length} newsrooms` : ""}
          {" · "}<button type="button" className="news__textbtn" onClick={() => setShowSources(value => !value)}>{showSources ? "hide sources" : "sources"}</button></span>
      </div>
      <form className="news__search" onSubmit={event => { event.preventDefault(); void load(); }}>
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search headlines" aria-label="Search headlines" maxLength={200}/>
        <button type="button" className="news__refresh" disabled={busy || !LIVE_API} onClick={() => void load(true)} title="Check every newsroom now">{busy ? "…" : "↻"}</button>
      </form>
    </header>

    <nav className="news__topics" aria-label="Topics">
      {TOPICS.map(item => <button key={item.id} type="button" aria-pressed={topic === item.id}
        className={`news__pill${topic === item.id ? " news__pill--on" : ""}`} onClick={() => setTopic(item.id)}>{item.label}</button>)}
    </nav>

    {showSources && news && <ul className="news__sourcelist">{news.sources.map(source => <li key={source.name} className={source.ok === false ? "news__source--down" : undefined}>
      <strong>{source.name}</strong><small>{source.ok === false ? "unreachable · " : ""}{source.why}</small></li>)}</ul>}
    {error && <p className="news__note" role="alert">{error}</p>}
    {news && !news.stories.length && !busy && <p className="news__note">No headlines yet. Tap ↻ when you're online.</p>}

    {LIVE_API && <WorldSearch onOpen={setReading}/>}
    {reading && <Reader key={reading.link} story={reading} onClose={() => setReading(null)}/>}

    {hero && <article className="news__hero" onClick={() => open(hero)} role="link" tabIndex={0}
      onKeyDown={event => { if (event.key === "Enter") open(hero); }}>
      <Picture story={hero}/>
      <div className="news__hero-copy">
        <span className="news__label">{hero.coverage > 1 ? "Top story" : "Latest"}</span>
        <h3>{hero.title}</h3>
        {hero.summary && <p>{hero.summary}</p>}
        <Sources story={hero}/>
      </div>
    </article>}

    <div className="news__grid">
      {rest.map((story, index) => <article key={story.link} className={`news__card news__card--${sizeFor(story, index) || "std"}`}
        onClick={() => open(story)} role="link" tabIndex={0} onKeyDown={event => { if (event.key === "Enter") open(story); }}>
        <Picture story={story}/>
        <div className="news__card-copy">
          <h4>{story.title}</h4>
          {sizeFor(story, index) && story.summary && <p>{story.summary}</p>}
          <Sources story={story}/>
        </div>
      </article>)}
    </div>

    {quick.length > 0 && <section className="news__quick" aria-label="More headlines">
      <h3>More headlines</h3>
      <ol>{quick.map(story => <li key={story.link}><button type="button" onClick={() => open(story)}>{story.title}</button><Sources story={story}/></li>)}</ol>
    </section>}
  </div>;
}
