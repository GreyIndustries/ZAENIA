import { useEffect, useRef, useState } from 'react';
import { api, errorText, LIVE_API } from '../../core/bridge';
import './KnowledgePanel.css';

type Source = { id: string; title: string; url: string; kind: string; learned: string; characters: number; truncated: number };
type Match = { title: string; url: string; excerpt: string };
type Word = { original: string; transliteration: string; gloss: string; lexical?: string; morphology?: string; lexical_and_morphology?: string; raw_reference: string };
type Passage = { reference: string; book_name: string; words: Word[]; translations: Record<string,string>; source_credit: string; variant_warning: string };
type BibleStatus = { available: boolean; books: number; credit: string; source: string };

export function KnowledgePanel() {
  const [sources, setSources] = useState<Source[]>([]);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<Match[]>([]);
  const [reference, setReference] = useState('John 1:1');
  const [passage, setPassage] = useState<Passage | null>(null);
  const [bible, setBible] = useState<BibleStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!LIVE_API) return;
    let active = true;
    void Promise.allSettled([
      api<{sources:Source[]}>('GET','/api/platform/knowledge'),
      api<BibleStatus>('GET','/api/platform/scripture/status'),
    ]).then(([library, scripture]) => {
      if (!active) return;
      if (library.status === 'fulfilled') setSources(library.value.sources);
      else setError(errorText(library.reason));
      if (scripture.status === 'fulfilled') setBible(scripture.value);
    });
    return () => { active = false; };
  }, []);
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(null); setNotice(null);
    try { await action(); } catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  }
  const disabled = busy || !LIVE_API;
  return <>
    <section className="assistant-panel__section knowledge-panel" aria-labelledby="knowledge-heading" aria-busy={busy}>
      <header className="assistant-panel__heading"><h2 id="knowledge-heading">Learning library</h2><span>{sources.length} sources</span></header>
      <p className="assistant-panel__note">Give Zae a webpage or downloaded text to learn from. She saves searchable excerpts on this PC and uses relevant sources in future answers. This expands her reference library; it does not retrain her model.</p>
      {error && <p className="assistant-panel__error" role="alert">{error}</p>}
      {notice && <p className="assistant-panel__success" role="status">{notice}</p>}
      <form className="assistant-panel__form" onSubmit={event => { event.preventDefault(); void run(async () => {
        const source = await api<Source>('POST','/api/platform/knowledge',{url:url.trim()},{timeoutMs:90_000});
        setSources(previous => [source,...previous.filter(item => item.id !== source.id)]); setUrl('');
        setNotice(`Learned ${source.title}.${source.truncated ? ' Saved an excerpt; this page was shortened.' : ''}`);
      }); }}>
        <label>Webpage to learn from<input type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://…" required maxLength={2000} disabled={disabled}/></label>
        <button type="submit" disabled={disabled || !url.trim()}>{busy ? 'Working…' : 'Download and learn'}</button>
      </form>
      <details><summary>Learn from downloaded text</summary>
        <form className="assistant-panel__form" onSubmit={event => { event.preventDefault(); void run(async () => {
          const source=await api<Source>('POST','/api/platform/knowledge',{title,content});
          setSources(previous => [source,...previous.filter(item => item.id !== source.id)]); setTitle(''); setContent(''); setNotice('Text learned and saved for future questions.');
        }); }}>
          <input ref={file} type="file" accept=".txt,.md,text/plain,text/markdown" aria-label="Choose downloaded text" disabled={disabled} onChange={event => {
            const selected=event.target.files?.[0]; event.target.value=''; if (!selected) return;
            void run(async () => {
              if (selected.size>2_000_000) throw new Error('Choose a text file smaller than 2 MB.');
              const value=await selected.text(); if (value.length>1_000_000) throw new Error('Choose text under one million characters.');
              setTitle(selected.name.slice(0,250)); setContent(value); setNotice('Text loaded. Choose Learn this text to save it.');
            });
          }}/>
          <label>Source title<input value={title} onChange={event => setTitle(event.target.value)} maxLength={250} required disabled={disabled}/></label>
          <label>Source text<textarea value={content} onChange={event => setContent(event.target.value)} rows={4} minLength={20} maxLength={1_000_000} required disabled={disabled}/></label>
          <button type="submit" disabled={disabled || !title.trim() || content.trim().length<20}>Learn this text</button>
        </form>
      </details>
      <form className="assistant-panel__form" onSubmit={event => { event.preventDefault(); void run(async () => {
        const result=await api<{matches:Match[]}>('GET',`/api/platform/knowledge/search?q=${encodeURIComponent(query)}`); setMatches(result.matches);
        if (!result.matches.length) setNotice('No matching saved excerpts.');
      }); }}>
        <label>Search learned sources<input value={query} onChange={event => setQuery(event.target.value)} maxLength={1000} disabled={disabled}/></label>
        <button type="submit" disabled={disabled || !query.trim()}>Search library</button>
      </form>
      {matches.map((item,index) => <blockquote key={index}><strong>{item.title}</strong><p>{item.excerpt}</p>{item.url && <small>{item.url}</small>}</blockquote>)}
      <div className="knowledge-panel__sources">{sources.map(source => <article key={source.id}>
        <strong>{source.title}</strong><small>{source.url || 'Imported text'} · {source.characters.toLocaleString()} characters{source.truncated ? ' · Shortened excerpt' : ''} · Learned {new Date(source.learned).toLocaleDateString()}</small>
        <button type="button" disabled={disabled} aria-label={`Remove source ${source.title}`} onClick={() => void run(async () => {
          await api('DELETE',`/api/platform/knowledge/${source.id}`); setSources(previous => previous.filter(item => item.id !== source.id)); setMatches([]); setNotice('Removed the source and its searchable excerpts.');
        })}>Remove source</button>
      </article>)}</div>
      {!sources.length && <p className="assistant-panel__empty">No downloaded sources yet. You can also say “learn from” followed by a webpage address.</p>}
    </section>
    <section className="assistant-panel__section knowledge-panel" aria-labelledby="interlinear-heading">
      <header className="assistant-panel__heading"><h2 id="interlinear-heading">Interlinear Bible</h2><span>{bible ? `${bible.books} books · Offline` : 'Checking corpus…'}</span></header>
      <p className="assistant-panel__note">Hebrew and Greek words, transliteration, English glosses, Strong’s references and morphology. English translations: ASV 1901 and WEB Classic. You can also ask Zae about a specific verse in chat.</p>
      <form className="assistant-panel__form" onSubmit={event => { event.preventDefault(); void run(async () => {
        const result=await api<Passage>('GET',`/api/platform/scripture?reference=${encodeURIComponent(reference)}`); setPassage(result);
      }); }}>
        <label>Bible verse<input value={reference} onChange={event => setReference(event.target.value)} placeholder="Genesis 1:1" maxLength={80} disabled={disabled}/></label>
        <button type="submit" disabled={disabled || !reference.trim()}>Read interlinear</button>
      </form>
      {passage && <div className="knowledge-panel__passage"><h3>{passage.book_name} · {passage.reference}</h3>
        {Object.entries(passage.translations).map(([edition,translation]) => <p key={edition}><strong>{edition}</strong> {translation}</p>)}
        <div className="knowledge-panel__table"><table><thead><tr><th>Original</th><th>Transliteration</th><th>English gloss</th><th>Strong’s / morphology</th><th>Source / variant</th></tr></thead><tbody>{passage.words.map((word,index) => <tr key={index}><td lang={word.raw_reference.startsWith('Gen') ? 'he' : undefined} dir="auto">{word.original}</td><td>{word.transliteration}</td><td>{word.gloss}</td><td>{word.lexical_and_morphology || `${word.lexical} · ${word.morphology}`}</td><td>{word.raw_reference}</td></tr>)}</tbody></table></div>
        <p className="assistant-panel__note">{passage.variant_warning}</p><small>{passage.source_credit}</small>
      </div>}
      <p className="assistant-panel__note"><a href="https://github.com/STEPBible/STEPBible-Data" target="_blank" rel="noreferrer">STEP Bible / Tyndale House Cambridge · CC BY 4.0</a>. Glosses and textual variants are source evidence; interpretation should consider context.</p>
    </section>
  </>;
}
