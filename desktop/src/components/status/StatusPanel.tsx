import type { CoreTelemetry } from "../../core/coreTelemetry";
import { SystemBrief } from "./SystemBrief";
import "./StatusPanel.css";

// The modules the ZÆNIA server checks for the live status feed (core/api/status_feed.py).
const modules = [
  { id: "security", title: "Security & access", note: "Owner passkey, API token and server mode" },
  { id: "brain", title: "Local brain", note: "Ollama and the conversation model" },
  { id: "voice", title: "Voice", note: "Kokoro voice for spoken replies and the brief" },
  { id: "calendar", title: "Calendar", note: "Google Calendar link and the local calendar" },
  { id: "traffic", title: "Traffic", note: "WSDOT traffic for the drive brief" },
  { id: "weather", title: "Weather", note: "Forecast for the drive brief" },
  { id: "carplay", title: "CarPlay brief", note: "The brief made for the car" },
];
type Voice = { play: (key: string, text: string) => void; stop: () => void; playing: string | null; loading: string | null };
type Props = { telemetry: CoreTelemetry | null; source: "preview" | "local"; connection: string; startupReady: boolean; voice?: Voice; onFix?: (action: string) => void };
export function StatusPanel({ telemetry, source, connection, startupReady, voice, onFix }: Props) {
  const verified = source === "local" && telemetry !== null;
  // Same rule as Core Status: a module counts when it is ready or working.
  const readyCount = verified ? modules.filter(module => { const phase = telemetry.modules.find(item => item.id === module.id)?.phase; return phase === "ready" || phase === "working"; }).length : 0;
  const codex = verified ? telemetry.codex : undefined;
  return <div className="section-content readiness-panel">
    <div className="section-content__tag">READINESS CODEX <span>{verified ? "LIVE STATUS FEED" : "AWAITING VERIFIED STATUS"}</span></div>
    {source === "local" && <SystemBrief voice={voice} onFix={onFix}/>}
    <div className="readiness-summary">
      <div><span>Visual core</span><strong>{startupReady ? "Online" : "Starting"}</strong><small>Seven-second interface startup</small></div>
      <div><span>Verified modules</span><strong>{readyCount} / {modules.length}</strong><small>{verified ? `Reported live by the ZÆNIA server · ${telemetry.diagnostics.toLowerCase()}` : "Preview values are not counted"}</small></div>
      {/* Codex is an optional external connector; only show it when one reports. */}
      {codex
        ? <div><span>Codex connection</span><strong>{codex.phase.toUpperCase()}</strong><small>Reported by the local connector</small></div>
        : <div><span>Server mode</span><strong>{!verified ? "—" : telemetry.system?.mode === "unattended" ? "Token" : "Passkey"}</strong><small>{!verified ? "Waiting for live status" : telemetry.system?.mode === "unattended" ? "Owner features locked" : "Full owner features unlocked"}</small></div>}
    </div>
    <h2>ZÆNIA module readiness</h2>
    <div className="readiness-modules">{modules.map((module, index) => {
      const item = verified ? telemetry.modules.find(entry => entry.id === module.id) : undefined;
      const phase = item?.phase;
      return <article key={module.id}><span className="readiness-number">0{index + 1}</span><div><strong>{module.title}</strong><p>{item?.detail ?? module.note}</p></div><span className={`readiness-badge readiness-badge--${phase ?? "unknown"}`}>{phase?.toUpperCase() ?? "UNVERIFIED"}</span></article>;
    })}</div>
    <section className="codex-connection"><h2>{codex ? "Codex" : "Connection"}</h2>{codex && <p>{codex.detail}</p>}
      {codex && <small>Last connector check: <time dateTime={codex.checkedAt}>{new Date(codex.checkedAt).toLocaleString()}</time></small>}
      <p className="readiness-feed">{source === "local" ? connection : "Choose Live under System Data to read real status from the ZÆNIA server."}</p>
    </section>
  </div>;
}
