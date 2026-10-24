import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { api, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import "./NewsPanel.css";
import previewArtA from "../../assets/jarvis-hologram.png";
import previewArtB from "../../assets/core/warehouse-clean.png";
import previewArtC from "../../assets/neural-core-sphere.png";

type Story = { title: string; link: string; summary?: string; image?: string | null; published?: string | null; sources: string[]; links: Record<string, string>; coverage: number };
type SourceStatus = { name: string; focus: string[]; why: string; ok?: boolean; error?: string; checkedAt?: string };
type News = { updatedAt: string | null; stories: Story[]; sources: SourceStatus[] };

const TOPICS = [
  { id: "", label: "Everything" }, { id: "ai", label: "AI" }, { id: "hardware", label: "Hardware" },
  { id: "security", label: "Security" }, { id: "gaming", label: "Gaming" }, { id: "science", label: "Science" },
];

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

/** Tech headlines from ZAE's tracked newsrooms, laid out as a glass magazine. */
export function NewsPanel() {
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
      const params = new URLSearchParams({ limit: "30", topic, q: query.trim() });
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
    return [lead, others.slice(0, 13), others.slice(13)];
  }, [news]);
  const reachable = news?.sources.filter(source => source.ok !== false).length ?? 0;
  const today = new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

  return <div className="section-content news">
    <header className="news__masthead">
      <div>
        <span className="news__kicker">{today}</span>
        <h2 className="news__title">The tech brief</h2>
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

    {hero && <article className="news__hero" onClick={() => openLink(hero.link)} role="link" tabIndex={0}
      onKeyDown={event => { if (event.key === "Enter") openLink(hero.link); }}>
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
        onClick={() => openLink(story.link)} role="link" tabIndex={0} onKeyDown={event => { if (event.key === "Enter") openLink(story.link); }}>
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
      <ol>{quick.map(story => <li key={story.link}><button type="button" onClick={() => openLink(story.link)}>{story.title}</button><Sources story={story}/></li>)}</ol>
    </section>}
  </div>;
}
