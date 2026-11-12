import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { SEBrainMap } from "./SEBrainMap";
import "./CodeStudio.css";

/** Arena > Brains & tools: her brains (Talk, Seek, Study, Keep, topic tracker), the coding tools and every local
 * model, checked live from Ollama. Reference only; choosing a brain stays in Rounds & brain. */
type Loaded = { vramGb: number; sizeGb: number; context: number | null; until: string | null } | null;
type Brain = { id: string; name: string; model: string; where: string; role: string; keepAlive: string; installed: boolean; loaded: Loaded };
type Tool = { id: string; name: string; installed: boolean; version: string | null; model: string | null; use: string };
type Model = { name: string; sizeGb: number; parameters: string; loaded: boolean; usedBy: string[] };
type Turns = { turns: number; firstTextP50Ms: number | null; firstTextP95Ms: number | null; fillerTurns: number; fallbackTurns: number; failedTurns: number; byRoute: Record<string, number>; byModel: Record<string, number>; claimsChecked: number; claimsUnsupported: number };
type Roster = { ollama: { running: boolean; version: string | null; address: string }; brains: Brain[]; tools: Tool[]; models: Model[]; turns?: Turns };
const seconds = (ms: number | null) => ms === null ? "—" : `${(ms / 1000).toFixed(2)} s`;

export function BrainsPanel() {
  const [roster, setRoster] = useState<Roster | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<Roster>("GET", "/api/brains", undefined, { timeoutMs: 60_000 }).then(r => { setRoster(r); setError(null); }, f => setError(errorText(f))), []);
  useEffect(() => {
    if (!LIVE_API) return;
    void load();
    const timer = window.setInterval(() => void load(), 15_000);
    return () => window.clearInterval(timer);
  }, [load]);
  if (!LIVE_API) return <p className="cs-muted">This needs the ZÆNIA server: open it in the desktop app.</p>;
  return <div className="cs">
    <div className="cs-head">
      <div><span className="cs-kicker">SE & tools</span><h2 className="zx-title">The Synergized Encephalon, live</h2></div>
      {roster && <span className={roster.ollama.running ? "cs-good" : "cs-bad"}>{roster.ollama.running ? `Ollama ${roster.ollama.version} running on this PC only` : "Ollama isn't running"}</span>}
    </div>
    {error && <p className="cs-error" role="alert">{error}</p>}
    {!roster && !error && <p className="cs-muted">Checking…</p>}
    <SEBrainMap/>
    {roster && <>
      <div className="wb-cards">{roster.brains.map(brain => <div className="zx-card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 6 }} key={brain.id}>
        <div className="cs-row cs-row--between"><b style={{ fontSize: 16 }}>{brain.name}</b>
          <span className={brain.loaded ? "cs-good" : brain.installed ? "cs-muted" : "cs-bad"}>{brain.loaded ? "● Loaded" : brain.installed ? "○ Ready" : "Not installed"}</span></div>
        <code>{brain.model}</code>
        <span className="cs-muted">{brain.role}</span>
        <small className="cs-muted">{brain.where} · stays loaded: {brain.keepAlive}{brain.loaded ? ` · using ${brain.loaded.vramGb} GB graphics memory` : ""}</small>
      </div>)}</div>
      {roster.turns && <>
        <h3 className="zx-title" style={{ marginTop: 8 }}>How recent turns went</h3>
        <div className="zx-card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 6 }}>
          {roster.turns.turns === 0 ? <small>No turns recorded yet.</small> : <>
            <b>Last {roster.turns.turns} turns · first words in {seconds(roster.turns.firstTextP50Ms)} (typical), {seconds(roster.turns.firstTextP95Ms)} (slowest 5%)</b>
            <small>{roster.turns.fillerTurns} needed the filler · {roster.turns.fallbackTurns} fell back to Seek · {roster.turns.failedTurns} failed</small>
            <small>Citations checked: {roster.turns.claimsChecked}, not supported: {roster.turns.claimsUnsupported}</small>
            <small>Routes: {Object.entries(roster.turns.byRoute).map(([name, count]) => `${name} ${count}`).join(" · ")}</small>
            <small>Models: {Object.entries(roster.turns.byModel).map(([name, count]) => `${name} ${count}`).join(" · ")}</small>
            <small>Only timings and routes are kept, never what was said.</small></>}
        </div></>}
      <h3 className="zx-title" style={{ marginTop: 8 }}>Coding tools</h3>
      <div className="wb-cards">{roster.tools.map(tool => <div className="zx-card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 6 }} key={tool.id}>
        <div className="cs-row cs-row--between"><b style={{ fontSize: 16 }}>{tool.name}</b>
          <span className={tool.installed ? "cs-good" : "cs-bad"}>{tool.installed ? `✓ ${tool.version ?? "installed"}` : "Not installed"}</span></div>
        {tool.model && <code>{tool.model}</code>}
        <span className="cs-muted">{tool.use}</span>
      </div>)}</div>
      <h3 className="zx-title" style={{ marginTop: 8 }}>All local models</h3>
      <ul className="cs-files">{roster.models.map(model => <li key={model.name} style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr) 80px" }}>
        <code>{model.loaded ? "● " : ""}{model.name}</code>
        <span style={{ textAlign: "left" }}>{model.usedBy.length ? model.usedBy.join(", ") : "Not used (Arena only)"}</span>
        <span>{model.sizeGb} GB</span>
      </li>)}</ul>
    </>}
  </div>;
}
