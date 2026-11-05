import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, LIVE_API } from "../../core/bridge";
import { BRAIN_COLOR, BRAIN_IDS, PARTS, constellationScene, type ConstellationFeed, type PartReading } from "./se3d/constellation";
import { css } from "./se3d/engine";
import { SE3DCanvas } from "./se3d/SE3DCanvas";
import { readBrain, trackUse, type BrainId, type Seen } from "./seActivity";
import "./SEBrainMap.css";

/**
 * The Synergized Encephalon (SE) as a 3D "Neural Constellation" (Grey's pick, 2026-11-04): each of ZAE's four models is a
 * cluster of cells around the conductor's hub. It is live from Ollama: a cluster glows while its model is loaded and
 * fires fast while that model is answering; a model that isn't installed goes dark.
 */
export type Brain = { id: string; name: string; model: string; where: string; role: string; installed: boolean; loaded: unknown };
const JOB: Record<BrainId, string> = { talk: "The only one that speaks", seek: "Reads files and searches the web", study: "Deep thinking: research, code, ideas", keep: "Small summaries, on the processor" };
const SEFusionCanvas = lazy(() => import("./se3d/SEFusionCanvas").then(module => ({ default: module.SEFusionCanvas })));

const POLL_MS = 4000;
const PART_TEXT: Record<string, string> = {
  reasoning: "ZAE's replaceable reasoning interface: it works out answers and checks them against evidence before Talk says them. What it proposes has no authority of its own.",
  memory: "Local personal memory that you confirm, plus the recent conversation. It stays on this PC.",
  index: "The search index and topic tracker (nomic-embed-text) find related past conversation and files, and keep track of which topic you are on.",
  senses: "The listener hears you; Talk is the only voice that answers.",
};
const cap = (text: string) => text.replace(/^./, ch => ch.toUpperCase());

/**
 * The picture and its words, from the rows /api/brains gave (and what we've seen of each model answering).
 * `waiting` says why there are no rows yet ("checking…" or "not connected"), so a brain isn't called "not installed" by mistake.
 */
export function SEBrainView({ rows, seen, waiting }: { rows: Brain[]; seen: Seen; waiting?: string }) {
  const latest = useRef({ rows, seen, waiting });
  latest.current = { rows, seen, waiting };
  const [visual, setVisual] = useState<"fusion" | "constellation">(() => {
    try { return localStorage.getItem("zaenia.se.visual") === "fusion" ? "fusion" : "constellation"; }
    catch { return "constellation"; }
  });
  const chooseVisual = (next: "fusion" | "constellation") => {
    setVisual(next);
    try { localStorage.setItem("zaenia.se.visual", next); } catch { /* optional preference */ }
  };
  const [pick, setPick] = useState<BrainId | "conductor" | `part:${string}` | null>(null);
  const read = (id: BrainId, row: Brain | undefined, marks: Seen, now: number) => waiting
    ? { level: 0.3, installed: true, state: "ready" as const, words: waiting } : readBrain(id, row, marks, now);

  const partReadings = (): PartReading[] => {
    const marks = latest.current;
    const busy = BRAIN_IDS.reduce((sum, id) => sum + (marks.waiting ? 0 : readBrain(id, marks.rows.find(b => b.id === id), marks.seen, Date.now()).level), 0) / 4;
    const topics = marks.rows.find(b => b.id === "topics");
    const embedder = marks.waiting ? { words: marks.waiting, level: 0.3 } : !topics?.installed ? { words: "not installed", level: 0 }
      : topics.loaded ? { words: "loaded, tracking your topic", level: 0.6 } : { words: "ready, loads when needed", level: 0.2 };
    const builtIn = { words: marks.waiting ?? "built in, always on", level: 0.3 + 0.5 * busy };
    return [builtIn, builtIn, embedder, builtIn];
  };
  const feed = useMemo<ConstellationFeed>(() => {
    const row = (id: BrainId) => latest.current.rows.find(b => b.id === id);
    const reading = (id: BrainId) => latest.current.waiting
      ? { level: 0.3, installed: true, state: "ready" as const, words: latest.current.waiting }
      : readBrain(id, row(id), latest.current.seen, Date.now());
    const text = (id: BrainId) => ({ name: row(id)?.name ?? cap(id), model: row(id)?.model ?? "", job: JOB[id], state: reading(id).words });
    return {
      signals: () => BRAIN_IDS.map(id => { const r = reading(id); return { level: r.level, installed: r.installed }; }),
      text,
      tip: id => {
        const t = text(id), r = reading(id);
        return { key: `brain:${id}:${r.state}:${t.model}`, title: t.name, color: css(BRAIN_COLOR[id]), sub: t.model, lines: [row(id)?.role ?? JOB[id]], note: `${r.words}${row(id)?.where ? ` · ${row(id)?.where}` : ""}` };
      },
      parts: partReadings,
      partTip: k => ({ key: `part:${PARTS[k].id}:${partReadings()[k].words}`, title: PARTS[k].name, color: css(PARTS[k].colour), lines: [PART_TEXT[PARTS[k].id]], note: partReadings()[k].words }),
      hubTip: () => ({ key: "hub", title: "Conductor", color: "#fff2cf", lines: ["Decides which brain does each kind of work and which line is said first, so two things are never said at once."], note: "never acts on its own" }),
    };
  }, []);
  const scene = useMemo(() => constellationScene(feed), [feed]);

  const by = (id: BrainId) => rows.find(b => b.id === id);
  const now = Date.now();
  const part = typeof pick === "string" && pick.startsWith("part:") ? PARTS.findIndex(x => `part:${x.id}` === pick) : -1;
  const detail = pick && pick !== "conductor" && part < 0 ? by(pick as BrainId) : undefined;
  const constellation = <SE3DCanvas scene={scene} label="The SE as a 3D network: four clusters of cells for Talk, Seek, Study and Keep around the conductor's hub, with signals firing" hint="Drag to turn · hover a cluster"/>;
  return <><div className="se-map__views" role="group" aria-label="SE model appearance">
    <button type="button" aria-pressed={visual === "constellation"} onClick={() => chooseVisual("constellation")}>Constellation</button>
    <button type="button" aria-pressed={visual === "fusion"} onClick={() => chooseVisual("fusion")}>Fusion model</button>
  </div><div className="se-map__body">
    {visual === "fusion" ? <Suspense fallback={constellation}><SEFusionCanvas feed={feed} onSelect={setPick} onFallback={() => chooseVisual("constellation")}/></Suspense> : constellation}
    <aside className="se-legend" aria-live="polite">
      {pick === "conductor" ? <div><b style={{ color: "#fff2cf" }}>Conductor</b><p>Decides which brain does each kind of work, and which line is said first, so two things are never said at once. It never acts on its own and can't change a permission.</p></div>
        : part >= 0 ? <div><b style={{ color: css(PARTS[part].colour) }}>{PARTS[part].name}</b><p>{PART_TEXT[PARTS[part].id]}</p><small>{partReadings()[part].words}</small></div>
        : detail && pick ? <div><b style={{ color: css(BRAIN_COLOR[pick as BrainId]) }}>{detail.name} · {detail.model}</b><p>{detail.role}</p><small>{detail.where} · {read(pick as BrainId, detail, seen, now).words}</small></div>
        : <p>Drag the picture to turn it and hover a cluster. A bright cluster that fires fast is working right now; a dim one is resting or not loaded. Talk is the only one that speaks; the others think and hand their findings to the conductor.</p>}
      <ul>
        {BRAIN_IDS.map(id => <li key={id}><button type="button" aria-pressed={pick === id} onClick={() => setPick(id)}>
          <i style={{ background: css(BRAIN_COLOR[id]) }}/><b>{by(id)?.name ?? cap(id)}</b><span>{by(id)?.model ?? ""}</span><em>{read(id, by(id), seen, now).words}</em></button></li>)}
        {PARTS.map((x, k) => <li key={x.id}><button type="button" aria-pressed={pick === `part:${x.id}`} onClick={() => setPick(`part:${x.id}`)}>
          <i style={{ background: css(x.colour) }}/><b>{x.name}</b><span>built in</span><em>{partReadings()[k].words}</em></button></li>)}
        <li><button type="button" aria-pressed={pick === "conductor"} onClick={() => setPick("conductor")}><i style={{ background: "#fff2cf" }}/><b>Conductor</b><span>the hub</span><em>decides who does what</em></button></li>
      </ul>
    </aside>
  </div></>;
}

export function SEBrainMap({ compact = false }: { compact?: boolean }) {
  const [rows, setRows] = useState<Brain[]>([]);
  const [seen, setSeen] = useState<Seen>({});
  const seenRef = useRef<Seen>({});
  const busy = useRef(false);
  const load = useCallback(() => {
    if (!LIVE_API || busy.current || document.hidden) return;
    busy.current = true;
    void api<{ brains: Brain[] }>("GET", "/api/brains", undefined, { timeoutMs: 60_000 })
      .then(reply => { seenRef.current = trackUse(seenRef.current, reply.brains, Date.now()); setSeen(seenRef.current); setRows(reply.brains); }, () => undefined)
      .finally(() => { busy.current = false; });
  }, []);
  useEffect(() => {
    load();
    const timer = window.setInterval(load, POLL_MS);
    const visible = () => { if (!document.hidden) load(); };
    document.addEventListener("visibilitychange", visible);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", visible); };
  }, [load]);

  return <section className={`se-map${compact ? " se-map--compact" : ""}`} aria-label="The Synergized Encephalon">
    <header className="se-map__head">
      <div><span className="se-kicker">Synergized Encephalon · SE</span><h3>Where each brain works</h3></div>
    </header>
    <SEBrainView rows={rows} seen={seen} waiting={rows.length ? undefined : LIVE_API ? "checking…" : "not connected"}/>
  </section>;
}
