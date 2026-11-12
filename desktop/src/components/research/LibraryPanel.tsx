import { useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import { AddToNotebook, AnalysisResult, NeedsServer, UNTRUSTED_NOTE, useAnalysis } from "./researchShared";
import "./Research.css";
import { DetailScreen, detailKey } from "../shell/PageNavigator";

type Book = { id: string; title: string; author: string; year: number | string | null; source: string; access: string; url: string; readUrl: string | null };
type Found = { query: string; results: Book[]; readable: number; skipped: string[]; overview: { title: string; summary: string; url: string } | null };

const ELSEWHERE = (q: string) => [
  ["Wikipedia", `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(q)}`],
  ["HathiTrust full text", `https://babel.hathitrust.org/cgi/ls?q1=${encodeURIComponent(q)};anyall1=phrase;lmt=ft`],
  ["Library of Congress", `https://www.loc.gov/search/?q=${encodeURIComponent(q)}`],
  ["WorldCat (libraries near you)", `https://search.worldcat.org/search?q=${encodeURIComponent(q)}`],
  ["Google Books (free full view)", `https://www.google.com/search?tbm=bks&tbs=bkv:f&q=${encodeURIComponent(q)}`],
  ["Wikisource", `https://en.wikisource.org/w/index.php?search=${encodeURIComponent(q)}`],
];

/** Library: free books from Project Gutenberg, Open Library and the Internet Archive, read and scanned by ZAE. */
export function LibraryPanel() {
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<Found | null>(null);
  const [selected, setSelected] = useState<Book | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const analysis = useAnalysis();

  const search = async () => {
    if (!query.trim()) return;
    setBusy(true); setError(null); setSelected(null); analysis.clear();
    try { setFound(await api<Found>("GET", `/api/research/library?q=${encodeURIComponent(query.trim())}`, undefined, { timeoutMs: 60_000 })); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  };
  if (!LIVE_API) return <div className="research"><NeedsServer what="The Library"/></div>;

  return <div className="research research--library">
    <p className="research__note">{UNTRUSTED_NOTE}</p>
    <form className="research__bar" onSubmit={event => { event.preventDefault(); void search(); }}>
      <input value={query} maxLength={200} placeholder="Title, author or subject…" aria-label="Search books" onChange={event => setQuery(event.target.value)}/>
      <button type="submit" className="research__primary" disabled={busy || !query.trim()}>{busy ? "Searching…" : "Find books"}</button>
      {found && <small>{found.results.length} books found, {found.readable} readable here{found.skipped.length ? `. Skipped: ${found.skipped.join(", ")}` : ""}</small>}
    </form>
    {error && <p className="research__error" role="alert">{error}</p>}
    <div className="research__split">
      <div className="research__table-wrap">
        <table className="research__table">
          <thead><tr><th>Title</th><th>Author</th><th>Year</th><th>Source</th><th>Access</th></tr></thead>
          <tbody>{(found?.results ?? []).map(book => <tr key={book.id} className={`${selected?.id === book.id ? "research__row--on" : ""}${book.readUrl ? " research__row--free" : ""}`}
            onClick={() => { setSelected(book); analysis.clear(); }} tabIndex={0} onKeyDown={event => { if (event.key === "Enter") setSelected(book); }}>
            <td>{book.title}</td><td>{book.author}</td><td>{book.year ?? ""}</td><td>{book.source}</td><td>{book.access}</td>
          </tr>)}</tbody>
        </table>
        {!found && <p className="research__empty">Search for a title, author or subject. Free-to-read books are highlighted.</p>}
      </div>
      <aside className="research__side">
        <DetailScreen id="library-book" name="The Library" open={!!selected} itemId={selected?.id} title={selected?.title || "Book"}
          onOpen={key => { const book = found?.results.find(item => detailKey(item.id) === key); if (book) { setSelected(book); analysis.clear(); } }} onClose={() => setSelected(null)}/>
        {selected ? <>
          <h3>{selected.title}</h3>
          <p className="research__meta">{[selected.author, selected.year, selected.source].filter(Boolean).join(" · ")} · {selected.access}</p>
          <div className="research__actions">
            <button type="button" className="research__primary" disabled={!selected.readUrl || !!analysis.busy}
              onClick={() => void analysis.run("reading the book", "book", { url: selected.readUrl ?? "", kind: "book", title: selected.title })}>Read &amp; scan here</button>
            <button type="button" onClick={() => openLink(selected.url)}>Open in browser</button>
            <AddToNotebook source={{ title: selected.title, kind: "book", url: selected.readUrl ?? selected.url, meta: `${selected.author} ${selected.year ?? ""}`.trim(), fetch: Boolean(selected.readUrl) }}/>
          </div>
          {!selected.readUrl && <p className="research__meta">Not free to read here. {selected.access}.</p>}
          <AnalysisResult {...analysis}/>
        </> : found?.overview ? <>
          <h3>“{found.query}”</h3>
          <p className="research__meta">{found.overview.title} (Wikipedia)</p>
          <p>{found.overview.summary}</p>
        </> : <p className="research__empty">Pick a book to read it here, or see an overview of your search.</p>}
        {found && <div className="research__elsewhere"><span>Also look in (opens your browser):</span>
          {ELSEWHERE(found.query).map(([label, url]) => <button type="button" key={label} className="research__link" onClick={() => openLink(url)}>{label}</button>)}
        </div>}
      </aside>
    </div>
  </div>;
}
