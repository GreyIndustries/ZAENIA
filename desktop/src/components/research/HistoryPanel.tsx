import { useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { openLink } from "../../core/openLink";
import { AddToNotebook, AnalysisResult, NeedsServer, UNTRUSTED_NOTE, useAnalysis } from "./researchShared";
import "./Research.css";

type Point = { period: string; count: number | null; rate: number };
type Track = { source: string; label: string; unit: string; series: { term: string; points: Point[] }[] };
type Row = { when: string; what: string; where: string; url: string };

const SOURCES = [
  { id: "newspapers", label: "US newspapers 1770s–1960s (Library of Congress)" },
  { id: "books", label: "Books & documents 1700s–2020s (Internet Archive)" },
  { id: "news", label: "World online news since 2017 (GDELT)" },
];
const COLORS = ["var(--accent, #e0a353)", "#5fd6ff", "#c38bff"];
const LANGUAGES = [["", "All languages"], ["english", "English"], ["spanish", "Spanish"], ["german", "German"], ["french", "French"], ["italian", "Italian"], ["norwegian", "Norwegian"], ["polish", "Polish"]];

/** Totals, first appearance, peak, spikes and trend for one term. */
function summarise(points: Point[]) {
  const used = points.filter(point => point.rate > 0);
  if (!used.length) return null;
  const peak = used.reduce((best, point) => point.rate > best.rate ? point : best);
  const total = points.reduce((sum, point) => sum + (point.count ?? 0), 0);
  const spikes = points.filter((point, index) => {
    const around = [points[index - 1], points[index + 1]].filter(Boolean).map(item => item.rate);
    const base = around.length ? around.reduce((a, b) => a + b, 0) / around.length : 0;
    return point.rate > 0 && point.rate >= 2 * Math.max(base, 0.0001) && point !== peak;
  }).map(point => point.period);
  const third = Math.max(1, Math.floor(points.length / 3));
  const avg = (list: Point[]) => list.reduce((sum, point) => sum + point.rate, 0) / Math.max(1, list.length);
  const early = avg(points.slice(0, third)), late = avg(points.slice(-third));
  const trend = late > early * 1.25 ? "rising" : late < early * 0.8 ? "falling" : "steady";
  return { total, first: used[0].period, peak: peak.period, spikes, trend };
}

/** Bars per period, one colour per term; click a bar to see what was written then. */
function Timeline({ data, picked, onPick }: { data: Track; picked: { term: string; period: string } | null; onPick: (term: string, period: string) => void }) {
  const periods = data.series[0]?.points.map(point => point.period) ?? [];
  const max = Math.max(0.0001, ...data.series.flatMap(series => series.points.map(point => point.rate)));
  const groupWidth = 100 / Math.max(1, periods.length);
  const barWidth = groupWidth / (data.series.length + 1);
  return <figure className="research__chart">
    <svg viewBox="0 0 100 52" preserveAspectRatio="none" role="img" aria-label={`Timeline: ${data.series.map(s => s.term).join(", ")}`}>
      {periods.map((period, index) => data.series.map((series, s) => {
        const point = series.points[index];
        const height = (point.rate / max) * 46;
        const on = picked?.term === series.term && picked.period === period;
        return <rect key={`${period}-${series.term}`} x={index * groupWidth + (s + 0.5) * barWidth} y={48 - height} width={barWidth * 0.9} height={Math.max(height, 0.2)}
          fill={COLORS[s]} opacity={on ? 1 : 0.75} stroke={on ? "#fff" : "none"} strokeWidth={0.2} style={{ cursor: "pointer" }}
          onClick={() => onPick(series.term, period)}><title>{`${series.term}, ${period}: ${point.rate} ${data.unit}${point.count != null ? ` (${point.count} found)` : ""}`}</title></rect>;
      }))}
    </svg>
    <div className="research__axis">{periods.map((period, index) => <span key={period} style={{ width: `${groupWidth}%` }}>{periods.length > 16 && index % 2 ? "" : period}</span>)}</div>
    <figcaption>{data.series.map((series, s) => <span key={series.term}><i style={{ background: COLORS[s] }}/>{series.term}</span>)}<em>{data.unit}</em></figcaption>
  </figure>;
}

/** Historical connections: when people wrote about something most, and what was going on then. */
export function HistoryPanel() {
  const [terms, setTerms] = useState("");
  const [source, setSource] = useState("newspapers");
  const [data, setData] = useState<Track | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<{ term: string; period: string } | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [rowsBusy, setRowsBusy] = useState(false);
  const [language, setLanguage] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [suggesting, setSuggesting] = useState(false);
  const [translated, setTranslated] = useState<string[] | null>(null);
  const analysis = useAnalysis();

  const trackIt = async () => {
    if (!terms.trim()) return;
    setBusy(true); setError(null); setPicked(null); setRows([]); analysis.clear();
    try { setData(await api<Track>("GET", `/api/research/history?terms=${encodeURIComponent(terms)}&source=${source}&language=${language}`, undefined, { timeoutMs: 150_000 })); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  };
  const pick = async (term: string, period: string) => {
    setPicked({ term, period }); setRows([]); setRowsBusy(true); analysis.clear(); setTranslated(null);
    try { setRows((await api<{ rows: Row[] }>("GET", `/api/research/history/samples?term=${encodeURIComponent(term)}&source=${data?.source ?? source}&period=${period.slice(0, 4)}&language=${language}`, undefined, { timeoutMs: 90_000 })).rows); }
    catch (failure) { setError(errorText(failure)); }
    finally { setRowsBusy(false); }
  };
  const samplesText = rows.map(row => `${row.when} | ${row.where} | ${row.what}`).join("\n");
  const suggest = async () => {
    const first = terms.split(",")[0]?.trim();
    if (!first) return;
    setSuggesting(true);
    try {
      const reply = await api<{ result: string }>("POST", "/api/research/analyze", { task: "suggest", text: first, term: first }, { timeoutMs: 300_000 });
      setSuggestions(reply.result.split("\n").map(line => line.replace(/^[-*\d.)\s]+/, "").trim()).filter(Boolean).slice(0, 8));
    } catch (failure) { setError(errorText(failure)); }
    finally { setSuggesting(false); }
  };
  const translate = async () => {
    try {
      const reply = await api<{ result: string }>("POST", "/api/research/analyze", { task: "translate", text: rows.map(row => row.what).join("\n") }, { timeoutMs: 300_000 });
      setTranslated(reply.result.split("\n").filter(line => line.trim()));
    } catch (failure) { setError(errorText(failure)); }
  };
  if (!LIVE_API) return <div className="research"><NeedsServer what="Historical connections"/></div>;

  return <div className="research research--history">
    <p className="research__note">{UNTRUSTED_NOTE}</p>
    <form className="research__bar" onSubmit={event => { event.preventDefault(); void trackIt(); }}>
      <input value={terms} maxLength={200} placeholder="Up to 3, commas between: plague, influenza, cholera" aria-label="Words or phrases to track" onChange={event => setTerms(event.target.value)}/>
      <select value={source} aria-label="Where to look" onChange={event => setSource(event.target.value)}>{SOURCES.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
      {source === "newspapers" && <select value={language} aria-label="Newspaper language" onChange={event => setLanguage(event.target.value)}>{LANGUAGES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}
      <button type="button" disabled={suggesting || !terms.trim()} onClick={() => void suggest()}>{suggesting ? "Thinking…" : "Suggest keywords"}</button>
      <button type="submit" className="research__primary" disabled={busy || !terms.trim()}>{busy ? "Tracking…" : "Track through time"}</button>
    </form>
    {suggestions.length > 0 && <div className="research__actions" aria-label="Suggested keywords">{suggestions.map(word => <button type="button" key={word}
      onClick={() => setTerms(current => current.split(",").map(item => item.trim()).filter(Boolean).length >= 3 ? word : [current, word].filter(item => item.trim()).join(", "))}>+ {word}</button>)}</div>}
    {error && <p className="research__error" role="alert">{error}</p>}
    {data && <div className="research__summary">{data.series.map((series, s) => {
      const facts = summarise(series.points);
      return <div key={series.term}><strong style={{ color: COLORS[s] }}>{series.term}</strong>{facts ? <span>
        {facts.total ? `${facts.total.toLocaleString()} found · ` : ""}first seen {facts.first} · peak {facts.peak}{facts.spikes.length ? ` · spikes ${facts.spikes.join(", ")}` : ""} · {facts.trend}</span>
        : <span>not found</span>}</div>;
    })}</div>}
    {data ? <Timeline data={data} picked={picked} onPick={(term, period) => void pick(term, period)}/>
      : <div className="research__chart research__chart--empty">{busy ? "Counting pages decade by decade…" : "Your timeline appears here."}</div>}
    <div className="research__split research__split--even">
      <div className="research__side">
        <h3>Historical connections</h3>
        <p>Track a word or phrase through time and see when people wrote about it most. Rates are per million pages, so busy decades don't look bigger just because more was printed.</p>
        <p>Click a bar to see what was written then, and ask ZAE what was going on.</p>
        <AnalysisResult {...analysis}/>
      </div>
      <div className="research__side">
        <div className="research__table-wrap">
          <table className="research__table">
            <thead><tr><th>When</th><th>What was written</th><th>Where</th></tr></thead>
            <tbody>{rows.map((row, index) => <tr key={index} onDoubleClick={() => row.url && openLink(row.url)} title="Double-click to open">
              <td>{row.when}</td><td>{translated?.[index] ?? row.what}</td><td>{row.where}</td></tr>)}</tbody>
          </table>
          {rowsBusy && <p className="research__empty">Looking up {picked?.term} in the {picked?.period}…</p>}
          {!rowsBusy && picked && !rows.length && <p className="research__empty">Nothing to show for that period.</p>}
        </div>
        <div className="research__actions">
          <button type="button" disabled={!rows[0]?.url} onClick={() => openLink(rows[0].url)}>Open first</button>
          <button type="button" disabled={!rows.length} onClick={() => void translate()}>Translate titles</button>
          <AddToNotebook disabled={!rows.length} source={picked ? { title: `${picked.term} in the ${picked.period}`, kind: "history", text: samplesText, meta: data?.label ?? "" } : null}/>
          <button type="button" className="research__primary" disabled={!rows.length || !!analysis.busy}
            onClick={() => picked && void analysis.run("what was happening", "what_happened", { text: samplesText, term: picked.term, period: picked.period })}>What happened then?</button>
        </div>
      </div>
    </div>
  </div>;
}
