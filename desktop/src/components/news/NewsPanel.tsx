import { useCallback, useEffect, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import "./NewsPanel.css";

type Story = { title: string; link: string; summary?: string; published?: string | null; sources: string[]; links: Record<string, string>; coverage: number };
type SourceStatus = { name: string; focus: string[]; why: string; ok?: boolean; error?: string; checkedAt?: string };
type News = { updatedAt: string | null; stories: Story[]; sources: SourceStatus[] };

const TOPICS = [
  { id: "", label: "All" }, { id: "ai", label: "AI" }, { id: "hardware", label: "Hardware" },
  { id: "security", label: "Security" }, { id: "gaming", label: "Gaming" }, { id: "science", label: "Science" },
];

function ago(iso?: string | null): string {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`;
}

/** Tech headlines from ZAE's ten tracked sources; stories several sources report are marked. */
export function NewsPanel() {
  const [topic, setTopic] = useState("");
  const [query, setQuery] = useState("");
  const [news, setNews] = useState<News | null>(null);
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

  if (!LIVE_API) return <div className="section-content news-panel"><p>Tech news is available in the live app.</p></div>;
  return <div className="section-content news-panel">
    <div className="news-panel__bar">
      <div className="news-panel__topics" role="tablist" aria-label="Topic">
        {TOPICS.map(item => <button key={item.id} type="button" role="tab" aria-selected={topic === item.id}
          className={topic === item.id ? "choice choice--active" : "choice"} onClick={() => setTopic(item.id)}>{item.label}</button>)}
      </div>
      <form className="news-panel__search" onSubmit={event => { event.preventDefault(); void load(); }}>
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search headlines…" aria-label="Search headlines" maxLength={200}/>
        <button type="submit" className="choice" disabled={busy}>Search</button>
        <button type="button" className="choice" disabled={busy} onClick={() => void load(true)}>{busy ? "Checking…" : "Check now"}</button>
      </form>
    </div>
    <p className="news-panel__meta">
      {news?.updatedAt ? `Checked ${ago(news.updatedAt)} · ` : ""}{news ? `${news.sources.filter(s => s.ok !== false).length} of ${news.sources.length} sources reachable · ` : ""}
      <button type="button" className="news-panel__link" onClick={() => setShowSources(v => !v)}>{showSources ? "Hide sources" : "Sources"}</button>
    </p>
    {showSources && news && <ul className="news-panel__sources">{news.sources.map(source => <li key={source.name}>
      <strong>{source.name}</strong> {source.ok === false ? <em>unreachable</em> : null}<small>{source.why}</small></li>)}</ul>}
    {error && <p role="alert">{error}</p>}
    {news && !news.stories.length && !busy && <p>No headlines yet. Tap “Check now” when you're online.</p>}
    <ol className="news-panel__list">
      {news?.stories.map(story => <li key={story.link} className="news-panel__story">
        <a href={story.link} onClick={event => { event.preventDefault(); openLink(story.link); }}>{story.title}</a>
        {story.summary && <p>{story.summary}</p>}
        <small>
          {story.sources.map((name, index) => <span key={name}>{index > 0 && " · "}<a href={story.links[name]} onClick={event => { event.preventDefault(); openLink(story.links[name]); }}>{name}</a></span>)}
          {story.coverage > 1 && <span className="news-panel__badge">{story.coverage} sources</span>}
          {story.published && <span> · {ago(story.published)}</span>}
        </small>
      </li>)}
    </ol>
  </div>;
}
