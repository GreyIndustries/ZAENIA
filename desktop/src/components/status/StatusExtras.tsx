import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "../research/Research.css";

type Step = { kind: string; value: string };
type Protocol = { id: string; name: string; phrases: string[]; steps: Step[]; enabled: boolean };
type ProtocolState = { protocols: Protocol[]; kinds: string[]; tabs: string[]; examples: Omit<Protocol, "id" | "enabled">[] };

const KIND_HELP: Record<string, string> = {
  say: "ZAE says…", open: "Open tab", remind: "Reminder (30|stretch or 7am tomorrow|gym)", ask: "Ask her and say the answer",
  headlines: "Read top 3 headlines", coach: "Game coach on/off", watch: "Stop screen watching",
};
const blank = (): Omit<Protocol, "id"> => ({ name: "", phrases: [""], steps: [{ kind: "say", value: "" }], enabled: true });

/** Protocols: routines started by a phrase ("goodnight"). */
type Gpu = { name: string; vramGb: number | null; driver: string | null; integrated: boolean; display: string | null };
type Specs = { cpu: { name: string; cores: number; threads: number; maxGhz: number }; ram: { totalGb: number; sticks: number; speedMts: number; kind: string; model: string };
  gpus: Gpu[]; board: string; bios: string | null; drives: { name: string; type: string; sizeGb: number }[];
  volumes: { letter: string; label: string; sizeGb: number; freeGb: number }[]; os: string; at: number };

/** This PC: the parts ZAE knows about, read from Windows. */
export function PcSpecsPanel() {
  const [data, setData] = useState<Specs | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async (refresh = false) => {
    setBusy(true); setError(null);
    try { setData(await api<Specs>("GET", `/api/pc/specs${refresh ? "?refresh=true" : ""}`, undefined, { timeoutMs: 90_000 })); }
    catch (failure) { setError(errorText(failure)); } finally { setBusy(false); }
  }, []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  if (!LIVE_API) return <div className="research"><p className="research__note">This PC's specs show in the desktop app.</p></div>;
  const row = (label: string, value: string) => <div className="pc-spec"><span>{label}</span><strong>{value}</strong></div>;
  return <div className="research">
    <p className="research__note">What ZAE knows about your PC, read from Windows on this PC (no serial numbers, nothing sent anywhere). She uses it to answer questions like “can my PC run this?” and for upgrade suggestions.</p>
    <div className="research__actions"><button type="button" disabled={busy} onClick={() => void load(true)}>{busy ? "Reading…" : "Read again"}</button>
      {data && <span className="research__meta">Read {new Date(data.at * 1000).toLocaleString()}</span>}</div>
    {error && <p className="research__error" role="alert">{error}</p>}
    {data && <div className="wb-cards">
      <div className="research__side"><h3>Processor</h3>{row("CPU", data.cpu.name)}{row("Cores / threads", `${data.cpu.cores} / ${data.cpu.threads}`)}{row("Max clock", `${data.cpu.maxGhz} GHz`)}</div>
      <div className="research__side"><h3>Memory</h3>{row("RAM", `${data.ram.totalGb} GB ${data.ram.kind}`)}{row("Speed", `${data.ram.speedMts} MT/s`)}{row("Sticks", `${data.ram.sticks} × ${data.ram.model}`)}</div>
      {data.gpus.map(gpu => <div className="research__side" key={gpu.name}><h3>{gpu.integrated ? "Integrated graphics" : "Graphics card"}</h3>{row("GPU", gpu.name)}
        {gpu.vramGb ? row("VRAM", `${gpu.vramGb} GB`) : null}{gpu.driver ? row("Driver", gpu.driver) : null}{gpu.display ? row("Display", gpu.display) : null}</div>)}
      <div className="research__side"><h3>System</h3>{row("Motherboard", data.board)}{data.bios ? row("BIOS", data.bios) : null}{row("Windows", data.os)}</div>
      <div className="research__side"><h3>Storage</h3>{data.drives.map(d => <div key={d.name}>{row(d.name, `${d.type} · ${d.sizeGb} GB`)}</div>)}
        {data.volumes.map(v => <div key={v.letter}>{row(`${v.letter}: ${v.label}`, `${v.freeGb} of ${v.sizeGb} GB free`)}</div>)}</div>
    </div>}
  </div>;
}

export function ProtocolsPanel() {
  const [state, setState] = useState<ProtocolState | null>(null);
  const [draft, setDraft] = useState<(Omit<Protocol, "id"> & { id?: string }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<ProtocolState>("GET", "/api/protocols").then(setState, failure => setError(errorText(failure))), []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  const save = async () => {
    if (!draft) return;
    setError(null);
    const body = { name: draft.name, phrases: draft.phrases.filter(p => p.trim()), steps: draft.steps.filter(s => s.kind === "headlines" || s.value.trim()), enabled: draft.enabled };
    try { await api(draft.id ? "PUT" : "POST", draft.id ? `/api/protocols/${draft.id}` : "/api/protocols", body); setDraft(null); await load(); }
    catch (failure) { setError(errorText(failure)); }
  };
  const remove = async (id: string) => { await api("DELETE", `/api/protocols/${id}`).catch(failure => setError(errorText(failure))); await load(); };
  if (!LIVE_API) return <p className="research__note">Protocols need the ZÆNIA server.</p>;
  return <div className="research">
    <p className="research__note">A protocol is a routine you start with a phrase, by voice or typing: say “goodnight” and she runs every step. Steps only use things ZAE already does; they never run programs or change security.</p>
    {error && <p className="research__error" role="alert">{error}</p>}
    <div className="research__actions">
      <button type="button" className="research__primary" onClick={() => setDraft(blank())}>New protocol</button>
      {state?.examples.filter(example => !state.protocols.some(p => p.name === example.name)).map(example =>
        <button type="button" key={example.name} onClick={() => setDraft({ ...example, enabled: true })}>Start from “{example.name}”</button>)}
    </div>
    {draft && <div className="research__side">
      <input aria-label="Protocol name" placeholder="Name (e.g. Goodnight)" value={draft.name} maxLength={80} onChange={event => setDraft({ ...draft, name: event.target.value })}/>
      <label className="research__meta">Phrases that start it (one per line)</label>
      <textarea aria-label="Phrases" value={draft.phrases.join("\n")} onChange={event => setDraft({ ...draft, phrases: event.target.value.split("\n") })} style={{ minHeight: 60 }}/>
      <label className="research__meta">Steps, in order</label>
      {draft.steps.map((step, index) => <div className="research__bar" key={index}>
        <select aria-label={`Step ${index + 1} kind`} value={step.kind} onChange={event => setDraft({ ...draft, steps: draft.steps.map((s, i) => i === index ? { kind: event.target.value, value: "" } : s) })}>
          {(state?.kinds ?? Object.keys(KIND_HELP)).map(kind => <option key={kind} value={kind}>{KIND_HELP[kind] ?? kind}</option>)}
        </select>
        {step.kind === "open" ? <select aria-label="Tab" value={step.value} onChange={event => setDraft({ ...draft, steps: draft.steps.map((s, i) => i === index ? { ...s, value: event.target.value } : s) })}>
          <option value="">Pick a tab…</option>{state?.tabs.map(tab => <option key={tab} value={tab}>{tab}</option>)}</select>
          : step.kind === "coach" ? <select aria-label="On or off" value={step.value} onChange={event => setDraft({ ...draft, steps: draft.steps.map((s, i) => i === index ? { ...s, value: event.target.value } : s) })}>
            <option value="">On or off…</option><option value="on">on</option><option value="off">off</option></select>
          : step.kind === "headlines" ? null
          : <input aria-label={`Step ${index + 1}`} value={step.value} maxLength={300} placeholder={KIND_HELP[step.kind]}
              onChange={event => setDraft({ ...draft, steps: draft.steps.map((s, i) => i === index ? { ...s, value: step.kind === "watch" ? "off" : event.target.value } : s) })}/>}
        <button type="button" aria-label="Remove step" onClick={() => setDraft({ ...draft, steps: draft.steps.filter((_, i) => i !== index) })}>✕</button>
      </div>)}
      <div className="research__actions">
        <button type="button" disabled={draft.steps.length >= 12} onClick={() => setDraft({ ...draft, steps: [...draft.steps, { kind: "say", value: "" }] })}>+ Step</button>
        <button type="button" className="research__primary" onClick={() => void save()}>Save</button>
        <button type="button" onClick={() => setDraft(null)}>Cancel</button>
      </div>
    </div>}
    {state && !state.protocols.length && !draft && <p className="research__empty">No protocols yet. Start from an example above.</p>}
    {state?.protocols.map(protocol => <div className="research__side" key={protocol.id}>
      <h3>{protocol.name} <small>say: {protocol.phrases.map(p => `“${p}”`).join(" or ")}</small></h3>
      <ol className="research__meta">{protocol.steps.map((step, index) => <li key={index}>{KIND_HELP[step.kind] ?? step.kind}{step.value ? `: ${step.value}` : ""}</li>)}</ol>
      <div className="research__actions">
        <button type="button" onClick={() => setDraft({ ...protocol })}>Edit</button>
        <button type="button" className="research__danger" onClick={() => void remove(protocol.id)}>Delete</button>
      </div>
    </div>)}
  </div>;
}

type Health = { memoryPercent: number; diskFreeGb: number; cpuPercent: number; backup: { at?: string; path?: string; files?: number; bytes?: number };
  destination: string; watchdog: boolean; issues: string[] };

/** Self-Sustain: backups, auto-restart and health. */
export function SelfSustainPanel() {
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<Health>("GET", "/api/selfcare").then(setHealth, failure => setError(errorText(failure))), []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  const act = async (label: string, path: string, body: unknown) => {
    setBusy(label); setError(null);
    try { await api("POST", path, body, { timeoutMs: 300_000 }); await load(); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(null); }
  };
  if (!LIVE_API) return <p className="research__note">Self-Sustain needs the ZÆNIA server.</p>;
  if (!health) return <p className="research__empty">Checking…</p>;
  const backupAt = health.backup?.at ? new Date(health.backup.at).toLocaleString() : "never";
  return <div className="research">
    <p className="research__note">ZAE looks after herself: a backup of her memory and settings every night, an optional watchdog that restarts her server if it stops, and a watch on memory and disk.</p>
    {error && <p className="research__error" role="alert">{error}</p>}
    {health.issues.length > 0 ? <div className="research__side">{health.issues.map(issue => <p key={issue}>⚠ {issue}</p>)}</div>
      : <p className="research__meta">✓ All good.</p>}
    <div className="research__split research__split--even">
      <div className="research__side">
        <h3>Backups</h3>
        <p>Last backup: {backupAt}{health.backup?.files ? ` · ${health.backup.files} files · ${Math.round((health.backup.bytes ?? 0) / 2 ** 20)} MB` : ""}</p>
        <p className="research__meta">Saved to {health.destination}. The newest 14 are kept. Models and voices are left out because they can be downloaded again.</p>
        <div className="research__actions"><button type="button" className="research__primary" disabled={!!busy} onClick={() => void act("backing up", "/api/selfcare/backup", {})}>{busy === "backing up" ? "Backing up…" : "Back up now"}</button></div>
        <p className="research__meta">Restoring is a console step with your passkey: python -m core.assistant_platform.selfcare restore &lt;zip&gt;</p>
      </div>
      <div className="research__side">
        <h3>Auto-restart</h3>
        <p>{health.watchdog ? "On: Windows checks her server every 5 minutes and restarts it (token mode) if it stops answering twice." : "Off. Turn it on and Windows will restart her server if it crashes."}</p>
        <div className="research__actions"><button type="button" disabled={!!busy} onClick={() => void act("watchdog", "/api/selfcare/watchdog", { on: !health.watchdog })}>{health.watchdog ? "Turn auto-restart off" : "Turn auto-restart on"}</button></div>
        <h3>Health</h3>
        <p>Memory {health.memoryPercent.toFixed(0)}% used · CPU {health.cpuPercent.toFixed(0)}% · {health.diskFreeGb} GB free</p>
      </div>
    </div>
  </div>;
}

type Reminder = { id: string; text: string; due: string; channels: string[]; repeat: string };

/** Reminders: time-based nudges (on screen, spoken, or a text to your phone). */
export function RemindersPanel() {
  const [items, setItems] = useState<Reminder[]>([]);
  const [text, setText] = useState("");
  const [when, setWhen] = useState("");
  const [repeat, setRepeat] = useState("none");
  const [phone, setPhone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<{ reminders: Reminder[] }>("GET", "/api/reminders").then(reply => setItems(reply.reminders), failure => setError(errorText(failure))), []);
  useEffect(() => { if (LIVE_API) void load(); }, [load]);
  const add = async () => {
    setError(null);
    try {
      await api("POST", "/api/reminders", { text, due: new Date(when).toISOString(), repeat, channels: phone ? ["screen", "speak", "phone"] : ["screen", "speak"] });
      setText(""); setWhen(""); setRepeat("none"); await load();
    } catch (failure) { setError(errorText(failure)); }
  };
  if (!LIVE_API) return <p className="research__note">Reminders need the ZÆNIA server.</p>;
  return <div className="research">
    <p className="research__note">Or just say “remind me in 20 minutes to check the oven” or “remind me at 5pm tomorrow to call mum”.</p>
    {error && <p className="research__error" role="alert">{error}</p>}
    <form className="research__bar" onSubmit={event => { event.preventDefault(); if (text.trim() && when) void add(); }}>
      <input value={text} maxLength={300} placeholder="Remind me to…" aria-label="Reminder" onChange={event => setText(event.target.value)}/>
      <input type="datetime-local" value={when} aria-label="When" onChange={event => setWhen(event.target.value)} style={{ flex: "0 1 210px", colorScheme: "dark" }}/>
      <select value={repeat} aria-label="Repeat" onChange={event => setRepeat(event.target.value)}><option value="none">Once</option><option value="daily">Daily</option><option value="weekly">Weekly</option></select>
      <label className="research__meta"><input type="checkbox" checked={phone} onChange={event => setPhone(event.target.checked)}/> also text my phone</label>
      <button type="submit" className="research__primary" disabled={!text.trim() || !when}>Add</button>
    </form>
    {!items.length && <p className="research__empty">No reminders coming up.</p>}
    <ul className="research__list">{items.map(item => <li key={item.id} className="research__bar">
      <span style={{ flex: 1 }}>{item.text}<small className="research__meta"> · {new Date(item.due).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}{item.repeat !== "none" ? ` · ${item.repeat}` : ""}{item.channels.includes("phone") ? " · text" : ""}</small></span>
      <button type="button" className="research__danger" onClick={() => void api("DELETE", `/api/reminders/${item.id}`).then(load, failure => setError(errorText(failure)))}>Delete</button>
    </li>)}</ul>
  </div>;
}
