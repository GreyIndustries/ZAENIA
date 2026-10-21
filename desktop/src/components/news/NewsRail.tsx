import { useEffect, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import "./NewsRail.css";

type Story = { title: string; link: string; sources: string[]; links: Record<string, string>; coverage: number; published?: string | null };
type News = { updatedAt: string | null; stories: Story[] };

const OPEN_KEY = "zaenia.newsRail.open";
const REFRESH_MS = 10 * 60 * 1000;

// Sample headlines for the visual preview only (never shown in the live app).
const PREVIEW: News = { updatedAt: new Date().toISOString(), stories: [
  { title: "Preview: a chip maker announces a new GPU line", link: "https://example.com/1", sources: ["Tom's Hardware", "The Verge"], links: {}, coverage: 2, published: new Date(Date.now() - 50 * 60000).toISOString() },
  { title: "Preview: researchers publish a smaller open AI model", link: "https://example.com/2", sources: ["MIT Technology Review"], links: {}, coverage: 1, published: new Date(Date.now() - 3 * 3600000).toISOString() },
  { title: "Preview: emergency patch for a widely used web framework", link: "https://example.com/3", sources: ["BleepingComputer"], links: {}, coverage: 1, published: new Date(Date.now() - 5 * 3600000).toISOString() },
] };

function readOpen(): boolean { try { return localStorage.getItem(OPEN_KEY) !== "0"; } catch { return true; } }
function ago(iso?: string | null): string {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return minutes < 60 ? `${minutes}m` : minutes < 2880 ? `${Math.round(minutes / 60)}h` : `${Math.round(minutes / 1440)}d`;
}

/** Right-side tech headlines on the desktop: the top stories, newest and most-covered first. */
export function NewsRail({ onOpenAll }: { onOpenAll: () => void }) {
  const [open, setOpen] = useState(readOpen);
  const [news, setNews] = useState<News | null>(LIVE_API ? null : PREVIEW);
  const [error, setError] = useState(false);
  useEffect(() => { try { localStorage.setItem(OPEN_KEY, open ? "1" : "0"); } catch { /* storage unavailable */ } }, [open]);
  useEffect(() => {
    if (!LIVE_API || !open) return;
    let cancelled = false;
    const load = () => api<News>("GET", "/api/news/tech?limit=8")
      .then(next => { if (!cancelled) { setNews(next); setError(false); } }, () => { if (!cancelled) setError(true); });
    void load();
    const id = window.setInterval(() => { if (!document.hidden) void load(); }, REFRESH_MS);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [open]);

  if (!open) return <button type="button" className="news-rail__tab" onClick={() => setOpen(true)} title="Show tech news" aria-label="Show tech news">
    <span>TECH NEWS</span>
  </button>;

  return <aside className="news-rail" aria-label="Tech news">
    <header className="news-rail__head">
      <span className="news-rail__title">TECH NEWS</span>
      <span className="news-rail__age">{news?.updatedAt ? `checked ${ago(news.updatedAt)} ago` : ""}</span>
      <button type="button" className="news-rail__close" onClick={() => setOpen(false)} aria-label="Hide tech news" title="Hide">›</button>
    </header>
    {error && !news && <p className="news-rail__note">News isn't reachable right now.</p>}
    {news && !news.stories.length && <p className="news-rail__note">No headlines yet.</p>}
    <ol className="news-rail__list">
      {news?.stories.slice(0, 8).map(story => <li key={story.link}>
        <button type="button" className="news-rail__story" onClick={() => openLink(story.link)} title={`Open in your browser: ${story.title}`}>
          <strong>{story.title}</strong>
          <small>{story.sources.slice(0, 2).join(" · ")}{story.sources.length > 2 ? ` +${story.sources.length - 2}` : ""}
            {story.coverage > 1 && <em>{story.coverage} sources</em>}{story.published ? ` · ${ago(story.published)}` : ""}</small>
        </button>
      </li>)}
    </ol>
    <button type="button" className="news-rail__all" onClick={onOpenAll}>All tech news</button>
  </aside>;
}
