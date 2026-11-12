import { useEffect, useMemo, useRef, useState } from "react";
import { openLink } from "../../core/openLink";
import { calculate, CONSTANTS, convert, ELEMENTS, formatNumber, molarMass, UNITS } from "../../core/science";
import type { Element } from "../../core/science";
import { AnalysisResult, useAnalysis } from "../research/researchShared";
import "../research/Research.css";
import "./WorkbenchTools.css";

function Card({ title, children, wide }: { title: string; children: React.ReactNode; wide?: boolean }) {
  return <section className={`wb-card${wide ? " wb-card--wide" : ""}`}><h3>{title}</h3>{children}</section>;
}

function Calculator() {
  const [input, setInput] = useState("");
  const [degrees, setDegrees] = useState(true);
  const [history, setHistory] = useState<string[]>([]);
  const result = useMemo(() => { try { return input.trim() ? formatNumber(calculate(input, degrees), 12) : ""; } catch (error) { return error instanceof Error ? error.message : ""; } }, [input, degrees]);
  return <Card title="Scientific calculator">
    <form className="research__bar" onSubmit={event => { event.preventDefault(); if (result) setHistory(list => [`${input} = ${result}`, ...list].slice(0, 8)); }}>
      <input value={input} onChange={event => setInput(event.target.value)} placeholder="e.g. 2pi*sqrt(9.81/1.5) or 5!" aria-label="Expression"/>
      <button type="button" onClick={() => setDegrees(value => !value)}>{degrees ? "DEG" : "RAD"}</button>
    </form>
    <p className="wb-result">{result || "—"}</p>
    <p className="research__meta">sin cos tan asin acos atan sinh cosh tanh sqrt cbrt abs ln log log2 exp floor ceil round · pi e tau phi · ^ % !</p>
    {history.map(line => <p className="research__meta" key={line}>{line}</p>)}
  </Card>;
}

function Converter() {
  const categories = Object.keys(UNITS);
  const [category, setCategory] = useState("Length");
  const units = Object.keys(UNITS[category]);
  const [from, setFrom] = useState(units[0]);
  const [to, setTo] = useState(units[1]);
  const [value, setValue] = useState("1");
  useEffect(() => { const list = Object.keys(UNITS[category]); setFrom(list[0]); setTo(list[1] ?? list[0]); }, [category]);
  const out = Number.isFinite(Number(value)) && UNITS[category][from] !== undefined && UNITS[category][to] !== undefined ? formatNumber(convert(Number(value), category, from, to), 8) : "—";
  return <Card title="Unit converter">
    <div className="research__bar">
      <select value={category} aria-label="Quantity" onChange={event => setCategory(event.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select>
      <input value={value} inputMode="decimal" aria-label="Value" onChange={event => setValue(event.target.value)} style={{ flex: "0 1 120px" }}/>
      <select value={from} aria-label="From" onChange={event => setFrom(event.target.value)}>{units.map(unit => <option key={unit}>{unit}</option>)}</select>
      <span>→</span>
      <select value={to} aria-label="To" onChange={event => setTo(event.target.value)}>{units.map(unit => <option key={unit}>{unit}</option>)}</select>
    </div>
    <p className="wb-result">{out} {to}</p>
  </Card>;
}

function TimerTool() {
  const [mode, setMode] = useState<"stopwatch" | "timer">("timer");
  const [minutes, setMinutes] = useState("5");
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const start = useRef(0);
  useEffect(() => {
    if (!running) return;
    start.current = Date.now() - elapsed;
    const id = window.setInterval(() => setElapsed(Date.now() - start.current), 100);
    return () => window.clearInterval(id);
  }, [running]); // eslint-disable-line react-hooks/exhaustive-deps
  const total = Number(minutes) * 60000;
  const shown = mode === "timer" ? Math.max(0, total - elapsed) : elapsed;
  useEffect(() => { if (mode === "timer" && running && elapsed >= total) { setRunning(false); try { new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=").play().catch(() => undefined); } catch { /* optional */ } } }, [elapsed, mode, running, total]);
  const clock = `${String(Math.floor(shown / 60000)).padStart(2, "0")}:${String(Math.floor(shown / 1000) % 60).padStart(2, "0")}.${Math.floor((shown % 1000) / 100)}`;
  return <Card title="Timer & stopwatch">
    <div className="research__bar">
      <select value={mode} aria-label="Mode" onChange={event => { setMode(event.target.value as typeof mode); setRunning(false); setElapsed(0); }}><option value="timer">Timer</option><option value="stopwatch">Stopwatch</option></select>
      {mode === "timer" && <input value={minutes} inputMode="decimal" aria-label="Minutes" onChange={event => setMinutes(event.target.value)} style={{ flex: "0 1 80px" }}/>}
      <button type="button" className="research__primary" onClick={() => setRunning(value => !value)}>{running ? "Pause" : "Start"}</button>
      <button type="button" onClick={() => { setRunning(false); setElapsed(0); }}>Reset</button>
    </div>
    <p className="wb-result wb-result--big">{clock}{mode === "timer" && !running && elapsed >= total && total > 0 ? " · done" : ""}</p>
  </Card>;
}

function BaseConverter() {
  const [text, setText] = useState("255");
  const [base, setBase] = useState(10);
  const value = /^[0-9a-f]+$/i.test(text) ? parseInt(text, base) : NaN;
  return <Card title="Number bases">
    <div className="research__bar">
      <input value={text} aria-label="Number" onChange={event => setText(event.target.value.trim())}/>
      <select value={base} aria-label="Base" onChange={event => setBase(Number(event.target.value))}><option value={2}>binary</option><option value={8}>octal</option><option value={10}>decimal</option><option value={16}>hex</option></select>
    </div>
    {Number.isFinite(value) ? <p className="research__meta">dec {value} · hex {value.toString(16).toUpperCase()} · oct {value.toString(8)} · bin {value.toString(2)}</p> : <p className="research__meta">Not a number in that base.</p>}
  </Card>;
}

function Electronics() {
  const [v, setV] = useState(""); const [i, setI] = useState(""); const [r, setR] = useState("");
  const known = [v, i, r].filter(item => item.trim() !== "").length;
  let out = "Fill in any two.";
  if (known === 2) {
    const V = Number(v), I = Number(i), R = Number(r);
    out = !v ? `V = ${formatNumber(I * R)} V · P = ${formatNumber(I * I * R)} W` : !i ? `I = ${formatNumber(V / R)} A · P = ${formatNumber(V * V / R)} W` : `R = ${formatNumber(V / I)} Ω · P = ${formatNumber(V * I)} W`;
  }
  return <Card title="Ohm's law (V = I·R, P = V·I)">
    <div className="research__bar">
      <input placeholder="Volts" value={v} aria-label="Volts" onChange={event => setV(event.target.value)}/>
      <input placeholder="Amps" value={i} aria-label="Amps" onChange={event => setI(event.target.value)}/>
      <input placeholder="Ohms" value={r} aria-label="Ohms" onChange={event => setR(event.target.value)}/>
    </div>
    <p className="wb-result">{out}</p>
  </Card>;
}

const RESOURCES: [string, string, string][] = [
  ["arXiv", "https://arxiv.org", "Free physics, maths, CS and engineering papers"], ["NIST", "https://www.nist.gov/pml", "Constants, standards, reference data"],
  ["PubChem", "https://pubchem.ncbi.nlm.nih.gov", "Chemical compounds and safety data"], ["NASA ADS", "https://ui.adsabs.harvard.edu", "Astronomy and physics literature"],
  ["Wolfram Alpha", "https://www.wolframalpha.com", "Computational answers"], ["Desmos", "https://www.desmos.com/calculator", "Graphing calculator"],
  ["PhET simulations", "https://phet.colorado.edu", "Interactive physics and chemistry sims"], ["Engineering Toolbox", "https://www.engineeringtoolbox.com", "Engineering data tables"],
  ["Digi-Key", "https://www.digikey.com", "Electronic parts and datasheets"], ["Octopart", "https://octopart.com", "Part search across suppliers"],
  ["Falstad circuit sim", "https://www.falstad.com/circuit/circuitjs.html", "Run circuits in the browser"], ["MDN Web Docs", "https://developer.mozilla.org", "Web technology reference"],
  ["Python docs", "https://docs.python.org/3/", "Python reference"], ["Rust book", "https://doc.rust-lang.org/book/", "Learn Rust"],
  ["OpenStax", "https://openstax.org/subjects/science", "Free physics, chemistry, biology textbooks"], ["MIT OpenCourseWare", "https://ocw.mit.edu", "Free MIT courses"],
  ["Khan Academy", "https://www.khanacademy.org/science", "Lessons and practice"], ["NASA Open Data", "https://data.nasa.gov", "Space and Earth data"],
];

/** Workbench → Tools: calculators, converters, references and links for science and tech. */
export function ToolsPanel() {
  const [constFilter, setConstFilter] = useState("");
  return <div className="wb-grid">
    <Calculator/>
    <Converter/>
    <TimerTool/>
    <Electronics/>
    <BaseConverter/>
    <Card title="Physical constants" wide>
      <input className="wb-filter" placeholder="Filter…" value={constFilter} aria-label="Filter constants" onChange={event => setConstFilter(event.target.value)}/>
      <table className="research__table"><tbody>{CONSTANTS.filter(c => `${c.symbol} ${c.name}`.toLowerCase().includes(constFilter.toLowerCase())).map(c =>
        <tr key={c.symbol} title="Click to copy" onClick={() => void navigator.clipboard?.writeText(String(c.value))}><td><strong>{c.symbol}</strong></td><td>{c.name}</td><td>{formatNumber(c.value, 10)}</td><td>{c.unit}</td></tr>)}</tbody></table>
    </Card>
    <Card title="Science & tech resources" wide>
      <div className="wb-links">{RESOURCES.map(([name, url, why]) => <button type="button" key={name} onClick={() => openLink(url)}><strong>{name}</strong><small>{why}</small></button>)}</div>
    </Card>
  </div>;
}

// ---------------------------------------------------------------- Labs
function PeriodicTable({ onPick }: { onPick: (element: Element) => void }) {
  const [filter, setFilter] = useState("");
  const shown = ELEMENTS.filter(element => !filter || `${element.symbol} ${element.name} ${element.number}`.toLowerCase().includes(filter.toLowerCase()));
  return <Card title="Periodic table" wide>
    <input className="wb-filter" placeholder="Find an element…" value={filter} aria-label="Find element" onChange={event => setFilter(event.target.value)}/>
    <div className="wb-elements">{shown.map(element => <button type="button" key={element.number} className={`wb-element wb-element--${element.category}`} onClick={() => onPick(element)}
      title={`${element.name}, ${element.mass} u (${element.category})`}><small>{element.number}</small><strong>{element.symbol}</strong></button>)}</div>
  </Card>;
}

function Chemistry() {
  const [formula, setFormula] = useState("H2SO4");
  const [grams, setGrams] = useState("10");
  const molar = useMemo(() => { try { return molarMass(formula); } catch (error) { return error instanceof Error ? error.message : "?"; } }, [formula]);
  const [gas, setGas] = useState({ P: "101325", V: "0.0224", n: "", T: "273.15" });
  const R = 8.314462618;
  const gasOut = (() => {
    const missing = (Object.keys(gas) as (keyof typeof gas)[]).filter(key => gas[key].trim() === "");
    if (missing.length !== 1) return "Leave exactly one blank.";
    const [P, V, n, T] = [Number(gas.P), Number(gas.V), Number(gas.n), Number(gas.T)];
    const key = missing[0];
    const value = key === "P" ? n * R * T / V : key === "V" ? n * R * T / P : key === "n" ? P * V / (R * T) : P * V / (n * R);
    return `${key} = ${formatNumber(value)} ${({ P: "Pa", V: "m³", n: "mol", T: "K" })[key]}`;
  })();
  const [dil, setDil] = useState({ c1: "1", v1: "", c2: "0.1", v2: "100" });
  const dilOut = (() => {
    const blank = (Object.keys(dil) as (keyof typeof dil)[]).filter(key => dil[key].trim() === "");
    if (blank.length !== 1) return "Leave exactly one blank.";
    const [c1, v1, c2, v2] = [Number(dil.c1), Number(dil.v1), Number(dil.c2), Number(dil.v2)];
    const key = blank[0];
    return `${key.toUpperCase()} = ${formatNumber(key === "c1" ? c2 * v2 / v1 : key === "v1" ? c2 * v2 / c1 : key === "c2" ? c1 * v1 / v2 : c1 * v1 / c2)}`;
  })();
  const [ph, setPh] = useState("1e-7");
  return <>
    <Card title="Molar mass & moles">
      <div className="research__bar"><input value={formula} aria-label="Formula" placeholder="e.g. Ca(OH)2 or CuSO4·5H2O" onChange={event => setFormula(event.target.value)}/>
        <input value={grams} aria-label="Grams" inputMode="decimal" onChange={event => setGrams(event.target.value)} style={{ flex: "0 1 90px" }}/><span>g</span></div>
      {typeof molar === "string" ? <p className="research__error">{molar}</p> : <>
        <p className="wb-result">{formatNumber(molar.mass, 6)} g/mol · {formatNumber(Number(grams) / molar.mass, 5)} mol in {grams} g</p>
        <p className="research__meta">{molar.parts.map(part => `${part.symbol}×${part.count} (${(part.mass / molar.mass * 100).toFixed(1)}%)`).join(" · ")}</p></>}
    </Card>
    <Card title="Ideal gas law (PV = nRT)">
      <div className="research__bar">{(["P", "V", "n", "T"] as const).map(key => <input key={key} placeholder={`${key} (${({ P: "Pa", V: "m³", n: "mol", T: "K" })[key]})`} aria-label={key} value={gas[key]} onChange={event => setGas({ ...gas, [key]: event.target.value })}/>)}</div>
      <p className="wb-result">{gasOut}</p>
    </Card>
    <Card title="Dilution (C₁V₁ = C₂V₂)">
      <div className="research__bar">{(["c1", "v1", "c2", "v2"] as const).map(key => <input key={key} placeholder={key.toUpperCase()} aria-label={key} value={dil[key]} onChange={event => setDil({ ...dil, [key]: event.target.value })}/>)}</div>
      <p className="wb-result">{dilOut}</p>
    </Card>
    <Card title="pH">
      <div className="research__bar"><span>[H⁺] mol/L</span><input value={ph} aria-label="Hydrogen ion concentration" onChange={event => setPh(event.target.value)}/></div>
      <p className="wb-result">{Number(ph) > 0 ? `pH ${(-Math.log10(Number(ph))).toFixed(2)} · pOH ${(14 + Math.log10(Number(ph))).toFixed(2)}` : "—"}</p>
    </Card>
  </>;
}

function Projectile() {
  const [speed, setSpeed] = useState(20);
  const [angle, setAngle] = useState(45);
  const [gravity, setGravity] = useState(9.81);
  const [height, setHeight] = useState(0);
  const rad = angle * Math.PI / 180, vx = speed * Math.cos(rad), vy = speed * Math.sin(rad);
  const flight = (vy + Math.sqrt(vy * vy + 2 * gravity * height)) / gravity;
  const range = vx * flight, peak = height + vy * vy / (2 * gravity);
  const points = Array.from({ length: 41 }, (_, i) => { const t = flight * i / 40; return [vx * t, height + vy * t - gravity * t * t / 2]; });
  const maxX = Math.max(range, 1), maxY = Math.max(peak, 1);
  return <Card title="Projectile motion" wide>
    <div className="research__bar">
      <label className="research__meta">Speed {speed} m/s <input type="range" min={1} max={100} value={speed} onChange={event => setSpeed(Number(event.target.value))}/></label>
      <label className="research__meta">Angle {angle}° <input type="range" min={1} max={89} value={angle} onChange={event => setAngle(Number(event.target.value))}/></label>
      <label className="research__meta">Launch height {height} m <input type="range" min={0} max={100} value={height} onChange={event => setHeight(Number(event.target.value))}/></label>
      <select value={gravity} aria-label="Gravity" onChange={event => setGravity(Number(event.target.value))}><option value={9.81}>Earth</option><option value={1.62}>Moon</option><option value={3.71}>Mars</option><option value={24.79}>Jupiter</option></select>
    </div>
    <svg viewBox="0 0 100 50" className="wb-plot" preserveAspectRatio="none" aria-label="Trajectory">
      <polyline fill="none" stroke="var(--accent, #e0a353)" strokeWidth="0.6" points={points.map(([x, y]) => `${(x / maxX) * 98 + 1},${49 - (y / maxY) * 46}`).join(" ")}/>
      <line x1="0" y1="49" x2="100" y2="49" stroke="#5d6b7d" strokeWidth="0.3"/>
    </svg>
    <p className="wb-result">Range {formatNumber(range, 4)} m · peak {formatNumber(peak, 4)} m · flight {formatNumber(flight, 4)} s</p>
  </Card>;
}

function Physics() {
  const [length, setLength] = useState("1"); const [g, setG] = useState("9.81");
  const [mass, setMass] = useState("2"); const [vel, setVel] = useState("3"); const [h, setH] = useState("10");
  const [f, setF] = useState("440"); const [wl, setWl] = useState("");
  return <>
    <Projectile/>
    <Card title="Pendulum">
      <div className="research__bar"><input value={length} aria-label="Length (m)" placeholder="Length m" onChange={event => setLength(event.target.value)}/><input value={g} aria-label="g" placeholder="g" onChange={event => setG(event.target.value)}/></div>
      <p className="wb-result">T = {formatNumber(2 * Math.PI * Math.sqrt(Number(length) / Number(g)), 4)} s</p>
    </Card>
    <Card title="Energy">
      <div className="research__bar"><input value={mass} aria-label="Mass kg" placeholder="kg" onChange={event => setMass(event.target.value)}/><input value={vel} aria-label="Speed m/s" placeholder="m/s" onChange={event => setVel(event.target.value)}/><input value={h} aria-label="Height m" placeholder="m" onChange={event => setH(event.target.value)}/></div>
      <p className="wb-result">KE {formatNumber(0.5 * Number(mass) * Number(vel) ** 2)} J · PE {formatNumber(Number(mass) * 9.81 * Number(h))} J · p {formatNumber(Number(mass) * Number(vel))} kg·m/s</p>
    </Card>
    <Card title="Waves (v = f·λ)">
      <div className="research__bar"><input value={f} aria-label="Frequency Hz" placeholder="Hz" onChange={event => setF(event.target.value)}/><input value={wl} aria-label="Wavelength m" placeholder="λ m (blank = sound in air)" onChange={event => setWl(event.target.value)}/></div>
      <p className="wb-result">{wl ? `v = ${formatNumber(Number(f) * Number(wl))} m/s` : `λ in air = ${formatNumber(343 / Number(f))} m · λ for light = ${formatNumber(299792458 / Number(f))} m`}</p>
    </Card>
  </>;
}

/** Workbench → Labs: chemistry and physics calculators and simulations, with ZAE to explain. */
export function LabsPanel() {
  const [element, setElement] = useState<Element | null>(null);
  const [question, setQuestion] = useState("");
  const analysis = useAnalysis();
  return <div className="wb-grid">
    <PeriodicTable onPick={setElement}/>
    {element && <Card title={`${element.name} (${element.symbol})`}>
      <p className="wb-result">#{element.number} · {element.mass} u · {element.category}</p>
      <div className="research__actions"><button type="button" onClick={() => void analysis.run("explaining", "ask", { text: `${element.name}, element ${element.number}` }, `Tell me the key facts about ${element.name}: electron configuration, common compounds, uses and hazards.`)}>Ask ZAE about it</button></div>
    </Card>}
    <Chemistry/>
    <Physics/>
    <Card title="Ask ZAE (chemistry & physics)" wide>
      <form className="research__bar" onSubmit={event => { event.preventDefault(); if (question.trim()) void analysis.run("thinking", "ask", { text: "General chemistry and physics knowledge." }, question.trim()); }}>
        <input value={question} maxLength={500} placeholder="e.g. Why does salt lower the freezing point of water?" aria-label="Question" onChange={event => setQuestion(event.target.value)}/>
        <button type="submit" className="research__primary" disabled={!question.trim()}>Ask</button>
      </form>
      <AnalysisResult {...analysis}/>
    </Card>
  </div>;
}
