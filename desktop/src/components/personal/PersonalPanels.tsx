import { useEffect, useRef, useState } from 'react';
import type { PointerEvent, ReactNode } from 'react';
import { api, errorText, LIVE_API } from '../../core/bridge';
import '../assistant/PlatformPanel.css';
import './PersonalPanels.css';

type Base = { title: string; archived: boolean; id?: string; revision?: number; updatedAt?: string; createdAt?: string };
type Summary = Base & { category?: string; tags?: string[]; color?: string; size?: string; status?: string; stage?: string; date?: string; calories?: number; protein?: number; fiber?: number; minutes?: number; proteinTarget?: number | null; fiberTarget?: number | null; baselineCalories?: number | null };
type Listing = { items: Summary[]; total: number; nextOffset: number | null };
export type PersonalDraftCache = Record<string, { value: unknown; dirty: boolean }>;
type Props = { drafts: PersonalDraftCache };
const PATH = '/api/platform/personal';
const categories = ['Science', 'Biology', 'Tech', 'Bio tech', 'Bio chem', 'Nuclear physics', 'Nano technology', 'AI'];
const platforms = ['YouTube', 'SoundCloud', 'Spotify', 'Apple Music'];
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };

function useRecords<T extends Base>(collection: string, drafts: PersonalDraftCache, day = '') {
  const [value, setValue] = useState<T | null>((drafts[collection]?.value as T | null) ?? null);
  const [dirty, setDirty] = useState(drafts[collection]?.dirty ?? false);
  const [listing, setListing] = useState<Listing>({ items: [], total: 0, nextOffset: null });
  const [archived, setArchived] = useState(false); const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('');
  const locked = useRef(false); const ticket = useRef(0);
  function remember(next: T | null, changed: boolean) { setValue(next); setDirty(changed); drafts[collection] = { value: next, dirty: changed }; }
  async function load() {
    if (!LIVE_API) return;
    const current = ++ticket.current;
    const result = await api<Listing>('GET', `${PATH}/${collection}?day=${day}&archived=${archived}&offset=${offset}`);
    if (current === ticket.current) setListing(result);
  }
  useEffect(() => { void load().catch(e => setError(errorText(e))); return () => { ticket.current++; }; }, [collection, day, archived, offset]);
  async function perform(action: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError(''); setMessage('');
    try { await action(); await load(); } catch (e) { setError(errorText(e)); }
    finally { locked.current = false; setBusy(false); }
  }
  function edit(changes: Partial<T>) { if (value) remember({ ...value, ...changes }, true); }
  function create(next: T) { if (!dirty) { remember(next, true); setMessage(''); } }
  function open(id: string) { if (!dirty) void perform(async () => remember(await api<T>('GET', `${PATH}/${collection}/${id}`), false)); }
  async function save(changes: Partial<T> = {}) {
    if (!value) return;
    const { id, revision, updatedAt: _updated, createdAt: _created, ...record } = { ...value, ...changes };
    const saved = await api<T>(id ? 'PUT' : 'POST', `${PATH}/${collection}${id ? `/${id}` : ''}`, { record, ...(id ? { revision } : {}) });
    remember(saved, false); setMessage('Saved on your PC.');
  }
  const disabled = !LIVE_API || busy;
  const notice = <>{!LIVE_API && <p>Connect to ZAE to load and save your records.</p>}{error && <p role="alert" className="platform-error">{error}</p>}{message && <p role="status">{message}</p>}</>;
  const controls = <div className="platform-inline personal-controls"><label className="platform-check"><input type="checkbox" checked={archived} disabled={disabled} onChange={e => { setArchived(e.target.checked); setOffset(0); }}/>Archived</label><button disabled={disabled} onClick={() => void perform(async () => {})}>Refresh</button><small>{listing.total} records</small>{offset > 0 && <button disabled={disabled} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous</button>}{listing.nextOffset != null && <button disabled={disabled} onClick={() => setOffset(listing.nextOffset!)}>More</button>}</div>;
  const actions = <div className="platform-inline personal-actions"><button disabled={disabled || !value?.title.trim() || !dirty} onClick={() => void perform(() => save())}>Save</button><button disabled={disabled || !value} onClick={() => { remember(null, false); setMessage('Editor closed. Unsaved changes discarded.'); }}>Close / discard</button>{value?.id && <button disabled={disabled || dirty} onClick={() => void perform(() => save({ archived: !value.archived } as Partial<T>))}>{value.archived ? 'Restore' : 'Archive'}</button>}<small>{dirty ? 'Unsaved · draft stays while switching tabs' : 'Saved'}</small></div>;
  return { value, dirty, listing, disabled, busy, notice, controls, actions, create, edit, open, perform, setMessage };
}

type Stroke = { color: '#f2b95f' | '#75cfff' | '#a5eeaa' | '#f49cb8' | '#eeeeee'; width: number; points: number[][] };
type Project = Base & { category: string; tags?: string[]; color: string; size: string; status: string; body: string; blueprint: string; scenarios: string; unit: string; boardWidth: number; strokes: Stroke[]; referenceImage: string };
const emptyProject = (): Project => ({ title: '', archived: false, category: 'Tech', tags: [], color: 'amber', size: 'medium', status: 'Idea', body: '', blueprint: '', scenarios: '', unit: 'mm', boardWidth: 100, strokes: [], referenceImage: '' });

function Sketch({ value, onChange, disabled }: { value: Project; onChange: (strokes: Stroke[]) => void; disabled: boolean }) {
  const svg = useRef<SVGSVGElement>(null); const active = useRef<Stroke | null>(null); const pointer = useRef<number | null>(null);
  const [preview, setPreview] = useState<Stroke | null>(null); const [color, setColor] = useState<Stroke['color']>('#f2b95f'); const [line, setLine] = useState(false);
  function point(e: PointerEvent<SVGSVGElement>) { const rect = e.currentTarget.getBoundingClientRect(); return [Math.round(Math.max(0, Math.min(1000, (e.clientX - rect.left) / rect.width * 1000))), Math.round(Math.max(0, Math.min(600, (e.clientY - rect.top) / rect.height * 600)))]; }
  const count = value.strokes.reduce((sum, stroke) => sum + stroke.points.length, 0);
  function end(e: PointerEvent<SVGSVGElement>, cancel = false) {
    if (pointer.current !== e.pointerId) return;
    const stroke = active.current; active.current = null; pointer.current = null; setPreview(null);
    if (stroke && !cancel) onChange([...value.strokes, stroke]);
  }
  function exportDrawing() {
    if (!svg.current) return;
    const clone = svg.current.cloneNode(true) as SVGSVGElement;
    const millimeters: Record<string, number> = { mm: 1, cm: 10, m: 1000, in: 25.4, ft: 304.8 };
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', `${value.boardWidth * millimeters[value.unit]}mm`); clone.setAttribute('height', `${value.boardWidth * .6 * millimeters[value.unit]}mm`);
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: 'image/svg+xml' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${value.title.replace(/[^a-z0-9-]/gi, '_') || 'sketch'}.svg`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const last = preview ?? value.strokes[value.strokes.length - 1];
  const length = last ? last.points.slice(1).reduce((sum, p, i) => sum + Math.hypot(p[0] - last.points[i][0], p[1] - last.points[i][1]) * value.boardWidth / 1000, 0) : 0;
  const shown = [...value.strokes, ...(preview ? [preview] : [])];
  return <div className="personal-sketch">
    <div className="platform-inline"><label>Ink<select value={color} disabled={disabled} onChange={e => setColor(e.target.value as Stroke['color'])}><option value="#f2b95f">Amber</option><option value="#75cfff">Blue</option><option value="#a5eeaa">Green</option><option value="#f49cb8">Rose</option><option value="#eeeeee">White</option></select></label><label className="platform-check"><input type="checkbox" checked={line} onChange={e => setLine(e.target.checked)}/>Straight line</label><button type="button" disabled={disabled || !value.strokes.length} onClick={() => onChange(value.strokes.slice(0, -1))}>Undo stroke</button><button type="button" disabled={!value.strokes.length} onClick={exportDrawing}>Export SVG</button></div>
    <svg ref={svg} viewBox="0 0 1000 600" role="img" aria-label="Project sketch. Draw with a mouse, finger or stylus. Grid spacing is one tenth of the board width."
      onPointerDown={e => { if (disabled || value.strokes.length >= 300 || count >= 20000 || pointer.current !== null || e.button !== 0) return; e.currentTarget.setPointerCapture(e.pointerId); pointer.current = e.pointerId; active.current = { color, width: 2, points: [point(e)] }; setPreview(active.current); }}
      onPointerMove={e => { if (!active.current || pointer.current !== e.pointerId) return; const points = active.current.points; if (!line && (points.length >= 5000 || points.length + count >= 20000)) return; active.current = { ...active.current, points: line ? [points[0], point(e)] : [...points, point(e)] }; setPreview(active.current); }}
      onPointerUp={e => end(e)} onPointerCancel={e => end(e, true)}>
      <rect width="1000" height="600" fill="#101b24"/>{Array.from({ length: 11 }, (_, i) => <line key={`v${i}`} x1={i * 100} x2={i * 100} y1="0" y2="600" stroke="#34505c" strokeWidth="1"/>)}{Array.from({ length: 7 }, (_, i) => <line key={`h${i}`} x1="0" x2="1000" y1={i * 100} y2={i * 100} stroke="#34505c" strokeWidth="1"/>)}
      {shown.map((stroke, i) => <polyline key={i} points={stroke.points.map(p => p.join(',')).join(' ')} fill="none" stroke={stroke.color} strokeWidth={stroke.width} strokeLinecap="round" strokeLinejoin="round"/>)}
    </svg><small>Board: {value.boardWidth} × {+(value.boardWidth * .6).toFixed(4)} {value.unit}. Last stroke: {length.toFixed(2)} {value.unit}. Concept measurements; confirm tolerances in CAD.</small>
  </div>;
}

export function WorkbenchPanel({ drafts }: Props) {
  const r = useRecords<Project>('workbench', drafts); const [category, setCategory] = useState('All'); const [query, setQuery] = useState(''); const p = r.value;
  return <section className="platform-panel personal-panel" aria-label="Workbench" aria-busy={r.busy}>
    <div className="platform-panel__heading"><div><span className="subheading">IDEAS INTO PROJECTS</span><h2>Workbench</h2></div><button disabled={r.disabled || r.dirty} onClick={() => r.create(emptyProject())}>New project</button></div>{r.notice}
    <div className="personal-tabs" aria-label="Project subjects">{['All', ...categories].map(name => <button key={name} aria-pressed={category === name} onClick={() => setCategory(name)}>{name}</button>)}</div>
    <label>Find project<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Project title…"/></label>{r.controls}
    <div className="personal-forum">{r.listing.items.filter(item => (category === 'All' || item.category === category || (item.tags ?? []).includes(category)) && item.title.toLowerCase().includes(query.toLowerCase())).map(item => <button key={item.id} disabled={r.disabled || r.dirty} className={`personal-project personal-project--${item.size} personal-project--${item.color}`} aria-pressed={item.id === p?.id} onClick={() => r.open(item.id!)}><small>{[item.category, ...(item.tags ?? []).filter(tag => tag !== item.category)].join(' · ')} · {item.status}</small><strong>{item.title}</strong><span>Updated {new Date(item.updatedAt!).toLocaleDateString()}</span></button>)}</div>
    {!r.listing.total && <p>Start a project to keep its notes, sketches, blueprint references and experiments together.</p>}
    {p && <div className="personal-editor"><h3>{p.id ? 'Project details' : 'New project'}</h3><fieldset disabled={r.disabled}>
      <label>Project title<input required maxLength={160} value={p.title} onChange={e => r.edit({ title: e.target.value })}/></label>
      <div className="personal-fields"><Select label="Subject" value={p.category} options={categories} change={category => r.edit({ category })}/><Select label="Stage" value={p.status} options={['Idea', 'Research', 'Prototype', 'Testing', 'Complete']} change={status => r.edit({ status })}/><Select label="Card color" value={p.color} options={['amber', 'blue', 'green', 'rose', 'violet']} change={color => r.edit({ color })}/><Select label="Card size" value={p.size} options={['small', 'medium', 'large']} change={size => r.edit({ size })}/></div>
      <fieldset className="personal-crosstags"><legend>Also tag as</legend>
        {categories.filter(name => name !== p.category).map(name => { const on = (p.tags ?? []).includes(name);
          return <button type="button" key={name} aria-pressed={on} className={on ? 'personal-crosstag personal-crosstag--on' : 'personal-crosstag'}
            onClick={() => r.edit({ tags: on ? (p.tags ?? []).filter(tag => tag !== name) : [...(p.tags ?? []), name] })}>{on ? '✓ ' : '+ '}{name}</button>; })}
        <small>The project shows under every subject it's tagged with.</small>
      </fieldset>
      <label>Project notes<textarea rows={7} maxLength={30000} value={p.body} onChange={e => r.edit({ body: e.target.value })}/></label>
      <label>Blueprint file or link<input maxLength={2000} value={p.blueprint} onChange={e => r.edit({ blueprint: e.target.value })} placeholder="Reference to your CAD file, drawing or shared export"/></label>
      <label>Import sketch / blueprint image<input type="file" accept="image/png,image/jpeg" onChange={event => { const file=event.target.files?.[0]; event.target.value=''; if (!file) return; void r.perform(async () => { if(file.size>600000) throw new Error('Export a PNG or JPEG reference under 600 KB.'); const image=await new Promise<string>((resolve,reject) => { const reader=new FileReader(); reader.onload=()=>resolve(String(reader.result)); reader.onerror=()=>reject(new Error('Image could not be read.')); reader.readAsDataURL(file); }); r.edit({ referenceImage:image }); }); }}/></label>
      {p.referenceImage && <figure className="personal-reference"><img src={p.referenceImage} alt={`Sketch or blueprint reference for ${p.title}`}/><figcaption>Imported reference · kept on your PC</figcaption><button type="button" onClick={() => r.edit({ referenceImage:'' })}>Remove image from draft</button></figure>}
      <div className="personal-fields"><NumberField label="Sketch board width" value={p.boardWidth} min={.001} change={boardWidth => r.edit({ boardWidth })}/><Select label="Units" value={p.unit} options={['mm', 'cm', 'm', 'in', 'ft']} change={unit => r.edit({ unit })}/></div>
      <Sketch key={p.id ?? 'new'} value={p} disabled={r.disabled} onChange={strokes => r.edit({ strokes })}/>
      <label>Hypotheses, test conditions and results<textarea rows={5} maxLength={10000} value={p.scenarios} onChange={e => r.edit({ scenarios: e.target.value })} placeholder="Record the question, dimensions, materials, loads, assumptions and actual CAD / simulation results."/></label>
      <small>Scenario notes do not run a physics solver. Use the tools below for engineering analysis.</small>
    </fieldset>{r.actions}</div>}
    <details className="personal-resources"><summary>Sketching and blueprint tools · checked October 24, 2026</summary><p><a href="https://www.adobe.com/products/fresco.html" target="_blank" rel="noreferrer">Adobe Fresco</a> — free drawing on iPad and supported Windows devices. <a href="https://www.concepts.app/en/pricing-explained/" target="_blank" rel="noreferrer">Concepts</a> — free basics; optional one-time Essentials per platform. <a href="https://www.sketchbook.com/" target="_blank" rel="noreferrer">Sketchbook</a> — iPad basics free; Windows Pro is a separate one-time purchase.</p><p><a href="https://www.freecad.org/features.php" target="_blank" rel="noreferrer">FreeCAD</a> — free Windows CAD with real units, dimensioned drawings and FEM analysis; no native iPad app. <a href="https://support.shapr3d.com/hc/en-us/articles/7872024839452-Shapr3D-Basic" target="_blank" rel="noreferrer">Shapr3D Basic</a> — free iPad/Windows CAD, two projects and limited export; advanced drawings are paid. <a href="https://www.onshape.com/en/pricing" target="_blank" rel="noreferrer">Onshape Free</a> — iPad/browser CAD for noncommercial, public projects. Keep private inventions in a private tool.</p></details>
  </section>;
}

type Release = { platform: string; url: string };
type Stat = { platform: string; date: string; metric: string; value: number; source: string; method: 'manual' };
type Music = Base & { stage: string; projectFile: string; bpm: number | null; key: string; body: string; releases: Release[]; stats: Stat[] };
const emptyMusic = (): Music => ({ title: '', archived: false, stage: 'Idea', projectFile: '', bpm: null, key: '', body: '', releases: [], stats: [] });

export function MusicPanel({ drafts }: Props) {
  const r = useRecords<Music>('music', drafts); const m = r.value;
  const [release, setRelease] = useState<Release>({ platform: 'YouTube', url: '' });
  const [stat, setStat] = useState<Stat>({ platform: 'YouTube', date: today(), metric: 'Views', value: 0, source: '', method: 'manual' });
  return <section className="platform-panel personal-panel" aria-label="Music projects" aria-busy={r.busy}>
    <div className="platform-panel__heading"><div><span className="subheading">WRITE · RECORD · RELEASE</span><h2>Music</h2></div><button disabled={r.disabled || r.dirty} onClick={() => r.create(emptyMusic())}>New song</button></div>{r.notice}{r.controls}
    <div className="personal-forum">{r.listing.items.map(item => <button className="personal-project" disabled={r.disabled || r.dirty} key={item.id} onClick={() => r.open(item.id!)}><small>{item.stage}</small><strong>{item.title}</strong></button>)}</div>
    {!r.listing.total && <p>Track your GarageBand sessions, release links and each song's progress here.</p>}
    {m && <div className="personal-editor"><fieldset disabled={r.disabled}><label>Song title<input maxLength={160} value={m.title} onChange={e => r.edit({ title: e.target.value })}/></label><div className="personal-fields"><Select label="Production stage" value={m.stage} options={['Idea', 'Writing', 'Recording', 'Mixing', 'Mastering', 'Released']} change={stage => r.edit({ stage })}/><NumberField label="BPM (optional)" value={m.bpm} optional change={bpm => r.edit({ bpm })}/><label>Key<input maxLength={40} value={m.key} onChange={e => r.edit({ key: e.target.value })}/></label></div>
      <label>GarageBand project reference<input maxLength={2000} value={m.projectFile} onChange={e => r.edit({ projectFile: e.target.value })} placeholder="File location or iCloud reference; reference only"/></label><label>Session notes<textarea rows={5} maxLength={30000} value={m.body} onChange={e => r.edit({ body: e.target.value })}/></label>
      <h3>Releases</h3>{m.releases.map((item, i) => <div className="platform-inline" key={i}><span>{item.platform}</span><a href={item.url} target="_blank" rel="noreferrer">Open release</a><button onClick={() => r.edit({ releases: m.releases.filter((_, index) => index !== i) })}>Remove link</button></div>)}
      <div className="personal-fields"><Select label="Release platform" value={release.platform} options={platforms} change={platform => setRelease({ ...release, platform })}/><label>Release URL<input type="url" maxLength={2000} value={release.url} onChange={e => setRelease({ ...release, url: e.target.value })}/></label><button disabled={!release.url.startsWith('https://') || m.releases.length >= 12} onClick={() => { r.edit({ releases: [...m.releases, release] }); setRelease({ ...release, url: '' }); }}>Add release</button></div>
      <h3>Song statistics</h3><p>Manual observations from YouTube, SoundCloud, Spotify and Apple Music. Automatic connections are not configured yet. Compare the same platform and metric; plays, views and listeners are different measures.</p>
      <div className="personal-fields"><Select label="Statistics platform" value={stat.platform} options={platforms} change={platform => setStat({ ...stat, platform })}/><Select label="Metric" value={stat.metric} options={['Views', 'Plays', 'Listeners', 'Likes', 'Saves']} change={metric => setStat({ ...stat, metric })}/><label>Observed date<input type="date" value={stat.date} onChange={e => setStat({ ...stat, date: e.target.value })}/></label><NumberField label="Observed count" value={stat.value} change={value => setStat({ ...stat, value })}/><label>Source / reporting period<input maxLength={500} placeholder="e.g. Artist dashboard, lifetime count" value={stat.source} onChange={e => setStat({ ...stat, source: e.target.value })}/></label></div>
      <button disabled={!stat.date || !stat.source.trim() || m.stats.length >= 300} onClick={() => r.edit({ stats: [...m.stats, { ...stat, value: Math.trunc(stat.value) }] })}>Add dated statistic</button>
      <div className="personal-table-wrap"><table><thead><tr><th>Date</th><th>Platform</th><th>Metric</th><th>Count</th><th>Source / period</th><th></th></tr></thead><tbody>{m.stats.map((item, i) => <tr key={i}><td>{item.date}</td><td>{item.platform}</td><td>{item.metric}</td><td>{item.value.toLocaleString()}</td><td>{item.source} · manual</td><td><button onClick={() => r.edit({ stats: m.stats.filter((_, index) => index !== i) })}>Remove</button></td></tr>)}</tbody></table></div>
    </fieldset>{r.actions}</div>}
  </section>;
}

type Food = Base & { date: string; calories: number; protein: number; fiber: number; source: string };
type Exercise = Base & { date: string; minutes: number; calories: number; source: string; notes: string };
type Step = { exercise: string; prescription: string; done: boolean };
type Plan = Base & { sourceUrl: string; sourceText: string; sourceName: string; schedule: string; steps: Step[]; sessions: { date: string; steps: Step[] }[] };
type Settings = Base & { proteinTarget: number | null; fiberTarget: number | null; baselineCalories: number | null };
type TrainingSource = { sourceUrl: string; sourceText: string; sourceName: string; steps: Step[]; note: string };

export function FitnessPanel({ drafts }: Props) {
  const [day, setDay] = useState(today()); const [page, setPage] = useState('Log');
  const food = useRecords<Food>('food', drafts, day); const exercise = useRecords<Exercise>('exercise', drafts, day); const plans = useRecords<Plan>('plans', drafts); const settings = useRecords<Settings>('fitness-settings', drafts);
  const [totals, setTotals] = useState<{ calories: number; protein: number; fiber: number; burned: number; baseline: number | null; proteinTarget: number | null; fiberTarget: number | null } | null>(null);
  const [sourceText, setSourceText] = useState(''); const [sourceUrl, setSourceUrl] = useState('');
  const f = food.value; const e = exercise.value; const p = plans.value; const s = settings.value;
  const dirty = food.dirty || exercise.dirty || plans.dirty || settings.dirty;
  useEffect(() => { let active = true; if (LIVE_API) void api<typeof totals>('GET', `${PATH}/fitness-summary?day=${day}`).then(value => { if (active) setTotals(value); }).catch(() => { if (active) setTotals(null); }); return () => { active = false; }; }, [day, food.listing, exercise.listing, settings.listing]);
  async function source(body: { text?: string; url?: string; name?: string; data?: string }) {
    await plans.perform(async () => { const result = await api<TrainingSource>('POST', `${PATH}/training-source`, body, { timeoutMs: 60000 }); plans.create({ title: (result.sourceName === 'Pasted text' ? 'Training plan' : result.sourceName).slice(0, 160), archived: false, sourceUrl: result.sourceUrl, sourceText: result.sourceText, sourceName: result.sourceName, schedule: '', steps: result.steps, sessions: [] }); plans.setMessage(result.note); });
  }
  return <section className="platform-panel personal-panel" aria-label="Fitness and health">
    <div className="platform-panel__heading"><div><span className="subheading">NUTRITION · MOVEMENT · TRAINING</span><h2>Fitness &amp; Health</h2></div><label>Log date<input type="date" disabled={dirty} value={day} onChange={event => setDay(event.target.value)}/></label></div>
    <div className="personal-tabs">{['Log', 'Training plans', 'Targets'].map(name => <button key={name} aria-pressed={page === name} onClick={() => setPage(name)}>{name}</button>)}</div>
    {totals ? <><div className="personal-metrics"><Metric title="Food energy" value={`${totals.calories.toFixed(0)} kcal`}/><Metric title="Protein" value={`${totals.protein.toFixed(1)} g${totals.proteinTarget != null ? ` / ${totals.proteinTarget} g` : ''}`}/><Metric title="Fiber" value={`${totals.fiber.toFixed(1)} g${totals.fiberTarget != null ? ` / ${totals.fiberTarget} g` : ''}`}/><Metric title="Logged exercise burn" value={`${totals.burned.toFixed(0)} kcal`}/><Metric title="Intake minus exercise" value={`${(totals.calories - totals.burned).toFixed(0)} kcal`}/>{totals.baseline != null && <Metric title="Estimated energy balance" value={`${(totals.calories - totals.burned - totals.baseline).toFixed(0)} kcal`}/>}</div><small>Intake minus exercise excludes resting energy and other activity. Estimated energy balance uses your optional non-exercise baseline plus logged exercise. All burn figures are estimates.</small></> : <p>Daily totals unavailable. Connect or refresh the logs to retry.</p>}
    {page === 'Log' && <>
      <div className="personal-two"><div><h3>Food intake</h3>{food.notice}<button disabled={food.disabled || food.dirty} onClick={() => food.create({ title: '', archived: false, date: day, calories: 0, protein: 0, fiber: 0, source: 'Food label / manual entry' })}>Log food</button>{food.controls}<EntryList records={food.listing.items} disabled={food.disabled || food.dirty} open={food.open}/>
      {f && <div className="personal-editor"><fieldset disabled={food.disabled}><label>Food / serving<input maxLength={160} value={f.title} onChange={event => food.edit({ title: event.target.value })}/></label><small>Enter values for the full serving you consumed.</small><NumberField label="Calories (kcal)" value={f.calories} change={calories => food.edit({ calories })}/><NumberField label="Protein (g)" value={f.protein} change={protein => food.edit({ protein })}/><NumberField label="Fiber (g)" value={f.fiber} change={fiber => food.edit({ fiber })}/><label>Nutrition source<input maxLength={300} value={f.source} onChange={event => food.edit({ source: event.target.value })}/></label><label>Food date<input type="date" value={f.date} onChange={event => food.edit({ date: event.target.value })}/></label></fieldset>{food.actions}</div>}</div>
      <div><h3>Exercise log</h3>{exercise.notice}<button disabled={exercise.disabled || exercise.dirty} onClick={() => exercise.create({ title: '', archived: false, date: day, minutes: 30, calories: 0, source: 'Manual estimate', notes: '' })}>Log exercise</button>{exercise.controls}<EntryList records={exercise.listing.items} disabled={exercise.disabled || exercise.dirty} open={exercise.open}/>
      {e && <div className="personal-editor"><fieldset disabled={exercise.disabled}><label>Exercise<input maxLength={160} value={e.title} onChange={event => exercise.edit({ title: event.target.value })}/></label><NumberField label="Minutes" min={.1} value={e.minutes} change={minutes => exercise.edit({ minutes })}/><NumberField label="Active calories burned (estimate)" value={e.calories} change={calories => exercise.edit({ calories })}/><Select label="Burn source" value={e.source} options={['Manual estimate', 'Device estimate']} change={source => exercise.edit({ source })}/><label>Exercise date<input type="date" value={e.date} onChange={event => exercise.edit({ date: event.target.value })}/></label><label>Exercise notes<textarea maxLength={2000} value={e.notes} onChange={event => exercise.edit({ notes: event.target.value })}/></label></fieldset>{exercise.actions}</div>}</div></div>
    </>}
    {page === 'Training plans' && <>{plans.notice}<div className="personal-source"><h3>Create from a source</h3><label>Printed text or video transcript<textarea rows={5} maxLength={30000} value={sourceText} onChange={event => setSourceText(event.target.value)} placeholder="Squats: 3 × 10 reps&#10;Walk: 20 minutes"/></label><button disabled={plans.disabled || plans.dirty || !sourceText.trim()} onClick={() => void source({ text: sourceText })}>Extract text into a draft</button><label>Training article / video URL<input type="url" maxLength={2000} value={sourceUrl} onChange={event => setSourceUrl(event.target.value)}/></label><button disabled={plans.disabled || plans.dirty || !sourceUrl.startsWith('https://')} onClick={() => void source({ url: sourceUrl })}>Read article / keep video reference</button><label>Import training document<input type="file" accept=".txt,.md,.pdf,.docx,.srt,.vtt" disabled={plans.disabled || plans.dirty} onChange={async event => { const file = event.target.files?.[0]; if (!file) return; await plans.perform(async () => { if (file.size > 1000000) throw new Error('Choose a training document under 1 MB.'); const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ''; bytes.forEach(byte => { binary += String.fromCharCode(byte); }); const result = await api<TrainingSource>('POST', `${PATH}/training-source`, { name: file.name, data: btoa(binary) }); plans.create({ title: file.name.slice(0, 160), archived: false, sourceUrl: result.sourceUrl, sourceText: result.sourceText, sourceName: result.sourceName, schedule: '', steps: result.steps, sessions: [] }); plans.setMessage(result.note); }); event.target.value = ''; }}/></label><small>Text PDFs and Word documents are read locally. Scans need OCR or pasted text. Video links need captions / a transcript; a link alone does not mean ZAE watched it.</small></div>
      <button disabled={plans.disabled || plans.dirty} onClick={() => plans.create({ title: '', archived: false, sourceUrl: '', sourceName: 'Owner-created plan', sourceText: '', schedule: '', steps: [], sessions: [] })}>Blank training plan</button>{plans.controls}<EntryList records={plans.listing.items} disabled={plans.disabled || plans.dirty} open={plans.open}/>
      {p && <div className="personal-editor"><fieldset disabled={plans.disabled}><label>Plan title<input maxLength={160} value={p.title} onChange={event => plans.edit({ title: event.target.value })}/></label><label>Schedule / current cycle<input maxLength={500} value={p.schedule} onChange={event => plans.edit({ schedule: event.target.value })} placeholder="e.g. Monday / Wednesday / Friday, week 1"/></label><label>Source URL<input type="url" maxLength={2000} value={p.sourceUrl} onChange={event => plans.edit({ sourceUrl: event.target.value })}/></label><details><summary>Source text · {p.sourceName}</summary><label>Source / transcript<textarea rows={8} maxLength={30000} value={p.sourceText} onChange={event => plans.edit({ sourceText: event.target.value })}/></label><button disabled={!p.sourceText.trim()} onClick={() => void plans.perform(async () => { const result = await api<TrainingSource>('POST', `${PATH}/training-source`, { text: p.sourceText }); plans.edit({ steps: result.steps }); plans.setMessage(result.note); })}>Re-extract steps from text</button></details>
      {p.steps.map((step, index) => <div className="personal-step" key={index}><label className="platform-check"><input type="checkbox" checked={step.done} onChange={event => plans.edit({ steps: p.steps.map((item, i) => i === index ? { ...item, done: event.target.checked } : item) })}/>Done</label><label>Movement<input maxLength={300} value={step.exercise} onChange={event => plans.edit({ steps: p.steps.map((item, i) => i === index ? { ...item, exercise: event.target.value } : item) })}/></label><label>Sets / reps / duration<input maxLength={500} value={step.prescription} onChange={event => plans.edit({ steps: p.steps.map((item, i) => i === index ? { ...item, prescription: event.target.value } : item) })}/></label><button onClick={() => plans.edit({ steps: p.steps.filter((_, i) => i !== index) })}>Remove step</button></div>)}
      <div className="platform-inline"><button disabled={p.steps.length >= 100} onClick={() => plans.edit({ steps: [...p.steps, { exercise: 'Exercise', prescription: '', done: false }] })}>Add step</button><button disabled={!p.steps.length || p.sessions.length >= 200} onClick={() => plans.edit({ sessions: [...p.sessions, { date: day, steps: p.steps.map(step => ({ ...step })) }], steps: p.steps.map(step => ({ ...step, done: false })) })}>Record session / reset checklist</button><small>{p.steps.filter(step => step.done).length} / {p.steps.length} complete. Log the session above to record exercise and calories.</small></div><details><summary>Session history ({p.sessions.length})</summary>{p.sessions.map((session, index) => <p key={index}>{session.date}: {session.steps.filter(step => step.done).length} / {session.steps.length} steps complete — {session.steps.filter(step => step.done).map(step => step.exercise).join(', ') || 'No completed steps'}</p>)}</details></fieldset>{plans.actions}</div>}
    </>}
    {page === 'Targets' && <>{settings.notice}<p>Set your own nutrition targets. Optional baseline is your daily energy expenditure excluding exercise entered here. Do not enter a wearable's total expenditure and then add that same exercise again.</p>{settings.controls}<EntryList records={settings.listing.items} disabled={settings.disabled || settings.dirty} open={settings.open}/><button disabled={settings.disabled || settings.dirty || settings.listing.total > 0} onClick={() => settings.create({ title: 'My targets', archived: false, proteinTarget: null, fiberTarget: null, baselineCalories: null })}>Set targets</button>{s && <div className="personal-editor"><fieldset disabled={settings.disabled}><NumberField optional label="Protein target (g)" value={s.proteinTarget} change={proteinTarget => settings.edit({ proteinTarget })}/><NumberField optional label="Fiber target (g)" value={s.fiberTarget} change={fiberTarget => settings.edit({ fiberTarget })}/><NumberField optional label="Non-exercise baseline (kcal/day)" value={s.baselineCalories} change={baselineCalories => settings.edit({ baselineCalories })}/></fieldset>{settings.actions}</div>}</>}
  </section>;
}

function Select({ label, value, options, change }: { label: string; value: string; options: string[]; change: (value: string) => void }) { return <label>{label}<select value={value} onChange={e => change(e.target.value)}>{options.map(option => <option key={option}>{option}</option>)}</select></label>; }
function NumberField({ label, value, change, optional = false, min = 0 }: { label: string; value: number | null; change: (value: number) => void; optional?: boolean; min?: number }) {
  return <label>{label}<input type="number" min={min} step="any" value={value ?? ''} onChange={e => change((optional && e.target.value === '' ? null : Number(e.target.value)) as number)}/></label>;
}
function EntryList({ records, disabled, open }: { records: Summary[]; disabled: boolean; open: (id: string) => void }) { return <div className="personal-entries">{records.map(row => <button key={row.id} disabled={disabled} onClick={() => open(row.id!)}><strong>{row.title}</strong><small>{row.date}{row.calories != null ? ` · ${row.calories} kcal` : ''}{row.protein != null ? ` · ${row.protein} g protein · ${row.fiber} g fiber` : ''}</small></button>)}</div>; }
function Metric({ title, value }: { title: string; value: ReactNode }) { return <div><small>{title}</small><strong>{value}</strong></div>; }
