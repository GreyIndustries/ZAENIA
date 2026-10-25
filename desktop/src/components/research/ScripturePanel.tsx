import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import type { AnalysisTask } from "./researchShared";
import { AddToNotebook, AnalysisResult, NeedsServer, useAnalysis } from "./researchShared";
import "./Research.css";

type Word = { original: string; transliteration: string; gloss: string; strong: string; morphology: string; dataset: string };
type Verse = { verse: number; texts: Record<string, string>; words: Word[] };
type Passage = { reference: string; heReference?: string; meaning?: string; book: string; chapter: number; verses: Verse[];
  originalLanguage: string; credit: string; text: string; rtl?: string[] };
type Source = "bible" | "jewish" | "quran";
type Mark = { id: string; reference: string; note: string; at: string; source?: Source };
type Extras = { marks: Mark[]; ancient: { title: string; query: string }[]; sites: { name: string; url: string }[] };
type Hit = { reference: string; edition: string; text: string };
type Book = { id: string; title: string; author: string; year: number | string | null; source: string; access: string; url: string; readUrl: string | null };
type Choice = { id: string; label: string; note: string };

const SOURCES: Record<Source, { label: string; start: string; placeholder: string; defaults: string[]; choices: Choice[]; fixed?: boolean; note: string }> = {
  bible: {
    label: "Bible", start: "John 3:16", placeholder: "John 3:16, Psalm 23, Romans 8:28-39", defaults: ["WEB", "KJV"],
    note: "The interlinear Hebrew and Greek, WEB and ASV are on your PC; KJV, YLT, BBE and Darby come from bible-api.com; full Hebrew verses from Sefaria.",
    choices: [
      { id: "WEB", label: "WEB", note: "World English Bible (offline)" }, { id: "KJV", label: "KJV", note: "King James (online)" },
      { id: "ASV", label: "ASV", note: "American Standard 1901 (offline)" }, { id: "YLT", label: "YLT", note: "Young's Literal, NT (online)" },
      { id: "BBE", label: "BBE", note: "Bible in Basic English (online)" }, { id: "DARBY", label: "Darby", note: "Darby (online)" },
      { id: "HEB", label: "Hebrew", note: "Full Hebrew verses, Masoretic text (Old Testament, from Sefaria)" },
    ],
  },
  jewish: {
    label: "Jewish texts", start: "Pirkei Avot 1", placeholder: "Pirkei Avot 1, Mishnah Berakhot 1:1, Berakhot 2a, Genesis Rabbah 1:1", defaults: ["EN", "HE"], fixed: true,
    note: "Mishnah, Talmud, Midrash, Pirkei Avot and more from Sefaria's free library, in Hebrew or Aramaic beside English.",
    choices: [{ id: "EN", label: "English", note: "English translation (Sefaria)" }, { id: "HE", label: "Hebrew / Aramaic", note: "Original text (Sefaria)" }],
  },
  quran: {
    label: "Quran", start: "1", placeholder: "1, 2:255, 36:1-12 (surah:verses)", defaults: ["AR", "PICKTHALL"],
    note: "Arabic, transliteration and English translations from alquran.cloud.",
    choices: [
      { id: "AR", label: "Arabic", note: "Uthmani Arabic text" }, { id: "TR", label: "Transliteration", note: "Arabic in Latin letters" },
      { id: "PICKTHALL", label: "Pickthall", note: "Pickthall, 1930" }, { id: "YUSUFALI", label: "Yusuf Ali", note: "Yusuf Ali, 1934" },
      { id: "SAHIH", label: "Saheeh Intl", note: "Saheeh International, modern" },
    ],
  },
};
const SITES: Record<Source, (name: string) => boolean> = {
  bible: name => !name.startsWith("Quran"), jewish: name => name.startsWith("Sefaria"), quran: name => name.startsWith("Quran"),
};
const ACTIONS: { task: AnalysisTask; label: string }[] = [
  { task: "sc_explain", label: "Explain" }, { task: "sc_traditions", label: "Traditions" }, { task: "sc_compare", label: "Compare wording" },
  { task: "sc_crossrefs", label: "Cross-refs" }, { task: "sc_translate", label: "Translate original" },
];
const KEY = "zaenia.scripture";
type Saved = { source: Source; picks: Record<Source, { ref: string; translations: string[] }> };

function saved(): Saved {
  const fresh: Saved = { source: "bible", picks: { bible: { ref: "John 3:16", translations: ["WEB", "KJV"] }, jewish: { ref: "Pirkei Avot 1", translations: ["EN", "HE"] }, quran: { ref: "1", translations: ["AR", "PICKTHALL"] } } };
  try {
    const data = JSON.parse(localStorage.getItem(KEY) ?? "");
    if (data.ref) fresh.picks.bible = { ref: String(data.ref), translations: Array.isArray(data.translations) ? data.translations : ["WEB", "KJV"] }; // older saves
    if (data.picks) for (const id of Object.keys(SOURCES) as Source[]) if (data.picks[id]?.ref) fresh.picks[id] = data.picks[id];
    if (data.source in SOURCES) fresh.source = data.source;
  } catch { /* first visit */ }
  return fresh;
}

/** Scripture & ancient: the Bible (with the Hebrew/Greek underneath), Jewish texts and the Quran in parallel, explained by ZAE. */
export function ScripturePanel() {
  const start = useRef(saved());
  const picks = useRef(start.current.picks);
  const [source, setSource] = useState<Source>(start.current.source);
  const [ref, setRef] = useState(picks.current[start.current.source].ref);
  const [translations, setTranslations] = useState<string[]>(picks.current[start.current.source].translations);
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
  const info = SOURCES[source];
  const shown = info.fixed ? info.defaults : translations;

  const lookUp = useCallback(async (reference = ref, from: Source = source, wanted: string[] = translations) => {
    setBusy(true); setError(null); setWord(null); analysis.clear(); setMode("passage");
    const chosen = SOURCES[from].fixed ? SOURCES[from].defaults : wanted;
    try {
      setPassage(await api<Passage>("GET", `/api/research/scripture?source=${from}&ref=${encodeURIComponent(reference)}&translations=${chosen.join(",")}&interlinear=${from === "bible" && interlinear}`, undefined, { timeoutMs: 60_000 }));
      picks.current = { ...picks.current, [from]: { ref: reference, translations: wanted } };
      try { localStorage.setItem(KEY, JSON.stringify({ source: from, picks: picks.current })); } catch { /* optional */ }
    } catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  }, [ref, source, translations, interlinear]); // eslint-disable-line react-hooks/exhaustive-deps
  const loadExtras = useCallback(() => api<Extras>("GET", "/api/research/scripture/marks").then(setExtras, () => undefined), []);
  useEffect(() => { if (LIVE_API) { void lookUp(); void loadExtras(); } }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const switchTo = (next: Source, reference?: string) => {
    const pick = picks.current[next];
    setSource(next); setRef(reference ?? pick.ref); setTranslations(pick.translations); setPassage(null); setHits(null);
    void lookUp(reference ?? pick.ref, next, pick.translations);
  };
  const searchWords = async () => {
    setMode("search"); setError(null); setHits(null);
    try { setHits((await api<{ results: Hit[] }>("GET", `/api/research/scripture/search?source=${source}&q=${encodeURIComponent(query || ref)}`, undefined, { timeoutMs: 60_000 })).results); }
    catch (failure) { setError(errorText(failure)); }
  };
  const findAncient = async (q: string) => {
    setAncient(null); setError(null);
    try { setAncient((await api<{ results: Book[] }>("GET", `/api/research/library?q=${encodeURIComponent(q)}`, undefined, { timeoutMs: 60_000 })).results.slice(0, 12)); }
    catch (failure) { setError(errorText(failure)); }
  };
  const bookmark = async () => {
    if (!passage) return;
    try { await api("POST", "/api/research/scripture/marks", { reference: ref.trim(), note: analysis.result.slice(0, 1000), source }); setNote("Bookmarked."); void loadExtras(); }
    catch (failure) { setError(errorText(failure)); }
  };
  const readAloud = async () => {
    if (!passage) return;
    const english = shown.find(id => !(passage.rtl ?? []).includes(id) && id !== "TR") ?? shown[0];
    const text = `${passage.reference}. ` + passage.verses.map(v => v.texts[english] || "").join(" ");
    try {
      const reply = await api<{ audio: string; mime?: string }>("POST", "/api/speak", { text: text.slice(0, 1200) }, { timeoutMs: 120_000 });
      void new Audio(`data:${reply.mime || "audio/wav"};base64,${reply.audio}`).play();
    } catch (failure) { setError(errorText(failure)); }
  };
  const openHit = (reference: string) => {
    const target = source === "bible" ? reference.replace(/^(\w+)\.(\d+)\.(\d+)$/, "$1 $2:$3") : reference;
    setRef(target); void lookUp(target);
  };
  if (!LIVE_API) return <div className="research"><NeedsServer what="Scripture & ancient"/></div>;
  const material = passage ? { text: passage.text, title: passage.reference } : null;
  const label = (id: string) => info.choices.find(choice => choice.id === id)?.label ?? id;

  return <div className="research research--scripture">
    <p className="research__note">Free, public texts only. {info.note} Explanations come from ZAE's own brain; text is read as data, never as instructions.</p>
    <form className="research__bar" onSubmit={event => { event.preventDefault(); void lookUp(); }}>
      <select value={source} aria-label="Source" onChange={event => switchTo(event.target.value as Source)}>
        {(Object.keys(SOURCES) as Source[]).map(id => <option key={id} value={id}>{SOURCES[id].label}</option>)}
      </select>
      <input value={ref} maxLength={80} aria-label="Passage" placeholder={info.placeholder} onChange={event => setRef(event.target.value)}/>
      <button type="submit" className="research__primary" disabled={busy}>{busy ? "Looking up…" : "Look up"}</button>
      <input value={query} maxLength={200} aria-label="Search words" placeholder={`Search ${info.label.toLowerCase()}, e.g. ${source === "quran" ? "mercy" : source === "jewish" ? "repentance" : "shepherd"}`} onChange={event => setQuery(event.target.value)} style={{ flex: "1 1 160px" }}/>
      <button type="button" onClick={() => void searchWords()}>Search words</button>
      <button type="button" aria-pressed={mode === "ancient"} onClick={() => setMode("ancient")}>Ancient texts</button>
      <button type="button" aria-pressed={mode === "marks"} onClick={() => { setMode("marks"); void loadExtras(); }}>My marks</button>
    </form>
    <div className="research__actions">
      {!info.fixed && info.choices.map(item => <label key={item.id} className="research__meta sc-chip" title={item.note}>
        <input type="checkbox" checked={translations.includes(item.id)} onChange={event => setTranslations(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))}/>{item.label}</label>)}
      {source === "bible" && <label className="research__meta sc-chip"><input type="checkbox" checked={interlinear} onChange={event => setInterlinear(event.target.checked)}/>Hebrew / Greek interlinear</label>}
      {info.fixed && <span className="research__meta">Hebrew or Aramaic beside English. Talmud pages use daf numbers, like Berakhot 2a.</span>}
    </div>
    {error && <p className="research__error" role="alert">{error}</p>}

    <div className="research__split research__split--even">
      <div className="research__side sc-left">
        {mode === "passage" && passage && <>
          <h3>{passage.reference} {passage.heReference && <small dir="rtl">{passage.heReference}</small>} {passage.meaning && <small>“{passage.meaning}”</small>}</h3>
          <div className="sc-parallel" style={{ gridTemplateColumns: `repeat(${Math.max(1, shown.length)}, minmax(0,1fr))` }}>
            {shown.map(id => { const rtl = (passage.rtl ?? []).includes(id);
              return <div key={id} dir={rtl ? "rtl" : undefined} className={rtl ? "sc-rtl" : undefined}><strong className="sc-label">{label(id)}</strong>
                {passage.verses.map(verse => <p key={verse.verse}><sup>{verse.verse}</sup> {verse.texts[id] || <em className="research__meta">not available</em>}</p>)}</div>; })}
          </div>
          {source === "bible" && interlinear && passage.originalLanguage && <>
            <strong className="sc-label">{passage.originalLanguage} interlinear · click a word for a word study</strong>
            {passage.verses.map(verse => <div key={verse.verse} className={`sc-words${passage.originalLanguage === "Hebrew" ? " sc-words--rtl" : ""}`}>
              <sup>{verse.verse}</sup>{verse.words.map((w, index) => <button type="button" key={index} className={word === w ? "sc-word sc-word--on" : "sc-word"} onClick={() => setWord(w)}
                title={`${w.strong} · ${w.morphology}`}><span className="sc-orig">{w.original}</span><small>{w.transliteration}</small><small>{w.gloss}</small></button>)}
            </div>)}
          </>}
          <p className="research__meta">{passage.credit}</p>
        </>}
        {mode === "search" && <>{!hits ? <p className="research__empty">Searching…</p> : !hits.length ? <p className="research__empty">Nothing found.</p> :
          <ul className="research__list">{hits.map((hit, index) => <li key={index}><button type="button" onClick={() => openHit(hit.reference)}>
            <span>{source === "bible" ? hit.reference.replace(/^(\w+)\.(\d+)\.(\d+)$/, "$1 $2:$3") : hit.reference} <small>{hit.edition}</small></span><small>{hit.text}</small></button></li>)}</ul>}</>}
        {mode === "ancient" && <>
          <p className="research__meta">Public-domain ancient and early texts. Pick one to find free copies; open them in The Library to read and scan with ZAE.</p>
          <div className="research__actions">{extras?.ancient.map(item => <button type="button" key={item.title} onClick={() => void findAncient(item.query)}>{item.title}</button>)}</div>
          {ancient && <ul className="research__list">{ancient.map(book => <li key={book.id}><button type="button" onClick={() => openLink(book.url)}>
            <span>{book.title}</span><small>{[book.author, book.year, book.source, book.access].filter(Boolean).join(" · ")}</small></button></li>)}</ul>}
        </>}
        {mode === "marks" && <>{!extras?.marks.length ? <p className="research__empty">No bookmarks yet. Look up a passage and press Bookmark.</p> :
          <ul className="research__list">{extras.marks.map(mark => <li key={mark.id} className="research__bar">
            <button type="button" style={{ flex: 1 }} onClick={() => switchTo(mark.source ?? "bible", mark.reference)}>
              <span>{mark.reference} <small>{SOURCES[mark.source ?? "bible"].label}</small></span><small>{mark.note.slice(0, 140)}</small></button>
            <button type="button" className="research__danger" onClick={() => void api("DELETE", `/api/research/scripture/marks/${mark.id}`).then(loadExtras)}>✕</button></li>)}</ul>}</>}
      </div>

      <aside className="research__side">
        <h3>ZAE explains</h3>
        <div className="research__grid-actions">
          {ACTIONS.map(action => <button type="button" key={action.task} disabled={!material || !!analysis.busy}
            onClick={() => material && void analysis.run(action.label.toLowerCase(), action.task, material)}>{action.label}</button>)}
          {source === "bible" && <button type="button" disabled={!material || !word || !!analysis.busy} title={word ? `${word.original} (${word.strong})` : "Click a word in the interlinear first"}
            onClick={() => material && word && void analysis.run("studying the word", "sc_wordstudy", { ...material, term: `${word.original} (${word.transliteration}, ${word.strong}, "${word.gloss}")` })}>Word study{word ? `: ${word.transliteration}` : ""}</button>}
        </div>
        <div className="research__actions">
          <button type="button" disabled={!passage} onClick={() => void bookmark()}>Bookmark</button>
          <button type="button" disabled={!passage} onClick={() => void readAloud()}>Read aloud</button>
          <AddToNotebook disabled={!passage} source={passage ? { title: passage.reference, kind: "book", text: passage.text, meta: shown.map(label).join(", ") } : null}/>
        </div>
        <form className="research__bar" onSubmit={event => { event.preventDefault(); if (material && question.trim()) void analysis.run("answering", "ask", material, question.trim()); }}>
          <input value={question} maxLength={500} placeholder="Ask about this passage…" aria-label="Ask about this passage" onChange={event => setQuestion(event.target.value)}/>
          <button type="submit" disabled={!material || !question.trim()}>Ask</button>
        </form>
        {note && <p className="research__meta">✓ {note}</p>}
        <AnalysisResult {...analysis}/>
        {extras && passage && <div className="research__elsewhere"><span>More sites (opens your browser):</span>
          {extras.sites.filter(site => SITES[source](site.name)).map(site => <button type="button" key={site.name} className="research__link"
            onClick={() => openLink(site.url.replace("{q}", encodeURIComponent(source === "bible" ? passage.reference : ref.trim())).replace("{ref}", `${passage.book.toLowerCase().replace(/\s+/g, "_")}/${passage.chapter}-${passage.verses[0]?.verse ?? 1}.htm`))}>{site.name}</button>)}</div>}
      </aside>
    </div>
  </div>;
}
