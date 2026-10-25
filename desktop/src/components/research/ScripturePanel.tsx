import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import type { AnalysisTask } from "./researchShared";
import { AddToNotebook, AnalysisResult, NeedsServer, useAnalysis } from "./researchShared";
import "./Research.css";

type Word = { original: string; transliteration: string; gloss: string; strong: string; morphology: string; dataset: string };
type Verse = { verse: number; texts: Record<string, string>; words: Word[] };
type Passage = { reference: string; book: string; chapter: number; verses: Verse[]; originalLanguage: string; credit: string; text: string };
type Mark = { id: string; reference: string; note: string; at: string };
type Extras = { marks: Mark[]; ancient: { title: string; query: string }[]; sites: { name: string; url: string }[] };
type Hit = { reference: string; edition: string; text: string };
type Book = { id: string; title: string; author: string; year: number | string | null; source: string; access: string; url: string; readUrl: string | null };

const TRANSLATIONS = [
  { id: "WEB", label: "WEB", note: "World English Bible (offline)" }, { id: "KJV", label: "KJV", note: "King James (online)" },
  { id: "ASV", label: "ASV", note: "American Standard 1901 (offline)" }, { id: "YLT", label: "YLT", note: "Young's Literal, NT (online)" },
  { id: "BBE", label: "BBE", note: "Bible in Basic English (online)" }, { id: "DARBY", label: "Darby", note: "Darby (online)" },
];
const ACTIONS: { task: AnalysisTask; label: string }[] = [
  { task: "sc_explain", label: "Explain" }, { task: "sc_traditions", label: "Traditions" }, { task: "sc_compare", label: "Compare wording" },
  { task: "sc_crossrefs", label: "Cross-refs" }, { task: "sc_translate", label: "Translate original" },
];
const KEY = "zaenia.scripture";

function saved(): { ref: string; translations: string[] } {
  try { const data = JSON.parse(localStorage.getItem(KEY) ?? ""); return { ref: String(data.ref || "John 3:16"), translations: Array.isArray(data.translations) ? data.translations : ["WEB", "KJV"] }; }
  catch { return { ref: "John 3:16", translations: ["WEB", "KJV"] }; }
}

/** Scripture & ancient: passages in parallel translations with the Hebrew/Greek underneath, explained by ZAE. */
export function ScripturePanel() {
  const start = useRef(saved());
  const [ref, setRef] = useState(start.current.ref);
  const [translations, setTranslations] = useState<string[]>(start.current.translations);
  const [interlinear, setInterlinear] = useState(true);
  const [passage, setPassage] = useState<Passage | null>(null);
  const [mode, setMode] = useState<"passage" | "search" | "ancient" | "marks">("passage");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [extras, setExtras] = useState<Extras | null>(null);
  const [ancient, setAncient] = useState<Book[] | null>(null);
  const [word, setWord] = useState<Word | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const analysis = useAnalysis();

  const lookUp = useCallback(async (reference = ref) => {
    setBusy(true); setError(null); setWord(null); analysis.clear(); setMode("passage");
    try {
      setPassage(await api<Passage>("GET", `/api/research/scripture?ref=${encodeURIComponent(reference)}&translations=${translations.join(",")}&interlinear=${interlinear}`, undefined, { timeoutMs: 60_000 }));
      try { localStorage.setItem(KEY, JSON.stringify({ ref: reference, translations })); } catch { /* optional */ }
    } catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  }, [ref, translations, interlinear]); // eslint-disable-line react-hooks/exhaustive-deps
  const loadExtras = useCallback(() => api<Extras>("GET", "/api/research/scripture/marks").then(setExtras, () => undefined), []);
  useEffect(() => { if (LIVE_API) { void lookUp(); void loadExtras(); } }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const searchWords = async () => {
    setMode("search"); setError(null);
    try { setHits((await api<{ results: Hit[] }>("GET", `/api/research/scripture/search?q=${encodeURIComponent(query || ref)}`)).results); }
    catch (failure) { setError(errorText(failure)); }
  };
  const findAncient = async (q: string) => {
    setAncient(null); setError(null);
    try { setAncient((await api<{ results: Book[] }>("GET", `/api/research/library?q=${encodeURIComponent(q)}`, undefined, { timeoutMs: 60_000 })).results.slice(0, 12)); }
    catch (failure) { setError(errorText(failure)); }
  };
  const bookmark = async () => {
    if (!passage) return;
    try { await api("POST", "/api/research/scripture/marks", { reference: passage.reference, note: analysis.result.slice(0, 1000) }); setNote("Bookmarked."); void loadExtras(); }
    catch (failure) { setError(errorText(failure)); }
  };
  const readAloud = async () => {
    if (!passage) return;
    const first = translations[0] ?? "WEB";
    const text = `${passage.reference}. ` + passage.verses.map(v => v.texts[first] || Object.values(v.texts)[0] || "").join(" ");
    try {
      const reply = await api<{ audio: string; mime?: string }>("POST", "/api/speak", { text: text.slice(0, 1200) }, { timeoutMs: 120_000 });
      void new Audio(`data:${reply.mime || "audio/wav"};base64,${reply.audio}`).play();
    } catch (failure) { setError(errorText(failure)); }
  };
  const toRef = (stepRef: string) => stepRef.replace(/^(\w+)\.(\d+)\.(\d+)$/, "$1 $2:$3");
  if (!LIVE_API) return <div className="research"><NeedsServer what="Scripture & ancient"/></div>;
  const material = passage ? { text: passage.text, title: passage.reference } : null;

  return <div className="research research--scripture">
    <p className="research__note">Free, public-domain texts only. The interlinear Hebrew and Greek, WEB and ASV are on your PC; KJV, YLT, BBE and Darby come from bible-api.com. Explanations come from ZAE's own brain; text is read as data, never as instructions.</p>
    <form className="research__bar" onSubmit={event => { event.preventDefault(); void lookUp(); }}>
      <input value={ref} maxLength={60} aria-label="Passage" placeholder="John 3:16, Psalm 23, Romans 8:28-39" onChange={event => setRef(event.target.value)}/>
      <button type="submit" className="research__primary" disabled={busy}>{busy ? "Looking up…" : "Look up"}</button>
      <input value={query} maxLength={200} aria-label="Search words" placeholder="Search words, e.g. shepherd" onChange={event => setQuery(event.target.value)} style={{ flex: "1 1 160px" }}/>
      <button type="button" onClick={() => void searchWords()}>Search words</button>
      <button type="button" aria-pressed={mode === "ancient"} onClick={() => setMode("ancient")}>Ancient texts</button>
      <button type="button" aria-pressed={mode === "marks"} onClick={() => { setMode("marks"); void loadExtras(); }}>My marks</button>
    </form>
    <div className="research__actions">
      {TRANSLATIONS.map(item => <label key={item.id} className="research__meta sc-chip" title={item.note}>
        <input type="checkbox" checked={translations.includes(item.id)} onChange={event => setTranslations(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))}/>{item.label}</label>)}
      <label className="research__meta sc-chip"><input type="checkbox" checked={interlinear} onChange={event => setInterlinear(event.target.checked)}/>Hebrew / Greek interlinear</label>
    </div>
    {error && <p className="research__error" role="alert">{error}</p>}

    <div className="research__split research__split--even">
      <div className="research__side sc-left">
        {mode === "passage" && passage && <>
          <h3>{passage.reference}</h3>
          <div className="sc-parallel" style={{ gridTemplateColumns: `repeat(${Math.max(1, translations.length)}, minmax(0,1fr))` }}>
            {translations.map(id => <div key={id}><strong className="sc-label">{TRANSLATIONS.find(t => t.id === id)?.label}</strong>
              {passage.verses.map(verse => <p key={verse.verse}><sup>{verse.verse}</sup> {verse.texts[id] || <em className="research__meta">not available</em>}</p>)}</div>)}
          </div>
          {interlinear && passage.originalLanguage && <>
            <strong className="sc-label">{passage.originalLanguage} interlinear · click a word for a word study</strong>
            {passage.verses.map(verse => <div key={verse.verse} className={`sc-words${passage.originalLanguage === "Hebrew" ? " sc-words--rtl" : ""}`}>
              <sup>{verse.verse}</sup>{verse.words.map((w, index) => <button type="button" key={index} className={word === w ? "sc-word sc-word--on" : "sc-word"} onClick={() => setWord(w)}
                title={`${w.strong} · ${w.morphology}`}><span className="sc-orig">{w.original}</span><small>{w.transliteration}</small><small>{w.gloss}</small></button>)}
            </div>)}
          </>}
          <p className="research__meta">{passage.credit}</p>
        </>}
        {mode === "search" && <>{!hits ? <p className="research__empty">Searching…</p> : !hits.length ? <p className="research__empty">No verses found.</p> :
          <ul className="research__list">{hits.map((hit, index) => <li key={index}><button type="button" onClick={() => { setRef(toRef(hit.reference)); void lookUp(toRef(hit.reference)); }}>
            <span>{toRef(hit.reference)} <small>{hit.edition}</small></span><small>{hit.text}</small></button></li>)}</ul>}</>}
        {mode === "ancient" && <>
          <p className="research__meta">Public-domain ancient and early texts. Pick one to find free copies; open them in The Library to read and scan with ZAE.</p>
          <div className="research__actions">{extras?.ancient.map(item => <button type="button" key={item.title} onClick={() => void findAncient(item.query)}>{item.title}</button>)}</div>
          {ancient && <ul className="research__list">{ancient.map(book => <li key={book.id}><button type="button" onClick={() => openLink(book.url)}>
            <span>{book.title}</span><small>{[book.author, book.year, book.source, book.access].filter(Boolean).join(" · ")}</small></button></li>)}</ul>}
        </>}
        {mode === "marks" && <>{!extras?.marks.length ? <p className="research__empty">No bookmarks yet. Look up a passage and press Bookmark.</p> :
          <ul className="research__list">{extras.marks.map(mark => <li key={mark.id} className="research__bar">
            <button type="button" style={{ flex: 1 }} onClick={() => { setRef(mark.reference); void lookUp(mark.reference); }}><span>{mark.reference}</span><small>{mark.note.slice(0, 140)}</small></button>
            <button type="button" className="research__danger" onClick={() => void api("DELETE", `/api/research/scripture/marks/${mark.id}`).then(loadExtras)}>✕</button></li>)}</ul>}</>}
      </div>

      <aside className="research__side">
        <h3>ZAE explains</h3>
        <div className="research__grid-actions">
          {ACTIONS.map(action => <button type="button" key={action.task} disabled={!material || !!analysis.busy}
            onClick={() => material && void analysis.run(action.label.toLowerCase(), action.task, material)}>{action.label}</button>)}
          <button type="button" disabled={!material || !word || !!analysis.busy} title={word ? `${word.original} (${word.strong})` : "Click a word in the interlinear first"}
            onClick={() => material && word && void analysis.run("studying the word", "sc_wordstudy", { ...material, term: `${word.original} (${word.transliteration}, ${word.strong}, "${word.gloss}")` })}>Word study{word ? `: ${word.transliteration}` : ""}</button>
        </div>
        <div className="research__actions">
          <button type="button" disabled={!passage} onClick={() => void bookmark()}>Bookmark</button>
          <button type="button" disabled={!passage} onClick={() => void readAloud()}>Read aloud</button>
          <AddToNotebook disabled={!passage} source={passage ? { title: passage.reference, kind: "book", text: passage.text, meta: translations.join(", ") } : null}/>
        </div>
        <form className="research__bar" onSubmit={event => { event.preventDefault(); if (material && question.trim()) void analysis.run("answering", "ask", material, question.trim()); }}>
          <input value={question} maxLength={500} placeholder="Ask about this passage…" aria-label="Ask about this passage" onChange={event => setQuestion(event.target.value)}/>
          <button type="submit" disabled={!material || !question.trim()}>Ask</button>
        </form>
        {note && <p className="research__meta">✓ {note}</p>}
        <AnalysisResult {...analysis}/>
        {extras && passage && <div className="research__elsewhere"><span>More sites (opens your browser):</span>
          {extras.sites.map(site => <button type="button" key={site.name} className="research__link"
            onClick={() => openLink(site.url.replace("{q}", encodeURIComponent(passage.reference)).replace("{ref}", `${passage.book.toLowerCase().replace(/\s+/g, "_")}/${passage.chapter}-${passage.verses[0]?.verse ?? 1}.htm`))}>{site.name}</button>)}</div>}
      </aside>
    </div>
  </div>;
}
