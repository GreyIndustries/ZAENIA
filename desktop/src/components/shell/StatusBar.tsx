import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { skipWhileAway } from "../../core/appBackground";
import "./StatusBar.css";

type Bar = {
  model: string; loaded: string[]; brains?: { name: string; model: string; job: string; loaded: boolean }[]; voice: string; pcVoice: string; mode: string; cpu: number; ramUsedGb: number; ramTotalGb: number;
  gpu: { use: number; memoryUsedGb: number; memoryTotalGb: number; temperature: number } | null; diskFreeGb: number;
  gameMode: string | null; phone: string; backup: string | null;
};
type Level = { level: string; score: number };
type Checks = { running: boolean; retryAfter: number; latest: { status: string; at?: string; counts?: Record<string, number> } | null; error?: string | null };

const dot = (state: "good" | "warn" | "bad" | "off") => <i className={`zae-status__dot zae-status__dot--${state}`} aria-hidden="true"/>;
const ago = (iso: string | null | undefined) => {
  if (!iso) return "never";
  const hours = (Date.now() - Date.parse(iso)) / 3_600_000;
  return hours < 1 ? "just now" : hours < 24 ? `${Math.round(hours)}h ago` : `${Math.round(hours / 24)}d ago`;
};

/** Along the bottom: model, voice, mic, security, CPU/RAM/GPU, disk, backup, phone and game mode. */
export function StatusBar({ micListening }: { micListening: boolean }) {
  const [bar, setBar] = useState<Bar | null>(null);
  const [security, setSecurity] = useState<Level | null>(null);
  useEffect(() => {
    if (!LIVE_API) return;
    let alive = true;
    const away = { n: 0 };
    const load = () => {
      void api<Bar>("GET", "/api/status/bar").then(next => { if (alive) setBar(next); }, () => undefined);
      void api<Level>("GET", "/api/security/summary").then(next => { if (alive) setSecurity(next); }, () => undefined);
    };
    load();
    const id = window.setInterval(() => { if (!skipWhileAway(away, 4)) load(); }, 15_000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);
  if (!LIVE_API) return <div className="zae-status">{dot("off")}Preview: live status shows in the desktop and phone apps.</div>;
  if (!bar) return <div className="zae-status">{dot("off")}Checking ZAE…</div>;
  const ram = bar.ramUsedGb / Math.max(1, bar.ramTotalGb);
  const backupAge = bar.backup ? (Date.now() - Date.parse(bar.backup)) / 3_600_000 : Infinity;
  return <div className="zae-status" role="status" aria-label="ZAE status">
    {/* Her four brains: a lit dot means it's in memory now; hover for its model and job. */}
    {bar.brains?.length ? bar.brains.map(brain => <span key={brain.name} title={`${brain.name}: ${brain.model}. ${brain.job}. ${brain.loaded ? "Loaded now." : "Not loaded; it loads when needed."}`}>
      {dot(brain.loaded ? "good" : "off")}{brain.name} <small className="zae-status__model">{brain.model}</small></span>)
      : <span title={bar.loaded.length ? `Loaded now: ${bar.loaded.join(", ")}` : "SE unloaded (loads when you talk to her)"}>{dot(bar.loaded.length ? "good" : "off")}Model {bar.model}</span>}
    <span>{dot("good")}Voice {bar.voice}</span>
    <span>{dot(micListening ? "good" : "off")}Mic {micListening ? "listening" : "off"}</span>
    <span>{dot(bar.pcVoice !== "off" ? "good" : "off")}PC voice {bar.pcVoice}</span>
    {security && <span>{dot(security.level === "strong" ? "good" : security.level === "fair" ? "warn" : "bad")}Security {security.level} ({security.score})</span>}
    <span>{dot(bar.mode === "unattended" ? "warn" : "good")}{bar.mode === "unattended" ? "Token mode" : bar.mode === "full" || bar.mode === "ready" ? "Passkey mode" : `Mode ${bar.mode}`}</span>
    <span>{dot(bar.cpu > 85 ? "warn" : "good")}CPU {bar.cpu}%</span>
    <span>{dot(ram > 0.9 ? "bad" : ram > 0.8 ? "warn" : "good")}RAM {bar.ramUsedGb}/{bar.ramTotalGb} GB</span>
    {bar.gpu && <span title={`GPU ${bar.gpu.temperature}°C`}>{dot(bar.gpu.use > 90 ? "warn" : "good")}GPU {bar.gpu.use}% · {bar.gpu.memoryUsedGb}/{bar.gpu.memoryTotalGb} GB</span>}
    <span>{dot(bar.diskFreeGb < 20 ? "bad" : bar.diskFreeGb < 60 ? "warn" : "good")}Disk {bar.diskFreeGb} GB free</span>
    <span>{dot(backupAge < 30 ? "good" : bar.backup ? "warn" : "bad")}Backup {bar.backup ? ago(bar.backup) : "not set up"}</span>
    {bar.phone === "on" && <span>{dot("good")}Phone line</span>}
    {bar.gameMode && <span>{dot("warn")}Game mode ({bar.gameMode.replace(/\.exe$/i, "")})</span>}
  </div>;
}

/** The sidebar's one-click health check: her security self-check, with the last result. */
export function SidebarCheck() {
  const [state, setState] = useState<Checks | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const load = useCallback(() => api<Checks>("GET", "/api/security/checks").then(setState, () => undefined), []);
  useEffect(() => {
    if (!LIVE_API) return;
    void load();
    const id = window.setInterval(() => void load(), 30_000);
    return () => window.clearInterval(id);
  }, [load]);
  const run = async () => {
    setNote(null);
    try { await api("POST", "/api/security/checks", {}, { timeoutMs: 30_000 }); setNote("Checking…"); window.setTimeout(() => void load(), 4000); }
    catch (failure) { setNote(errorText(failure)); }
  };
  if (!LIVE_API) return null;
  const latest = state?.latest;
  const label = state?.running ? "Check running" : !latest ? "No check yet" : latest.status === "pass" ? "All checks passed" : latest.status === "warn" ? "Passed with warnings" : "A check failed";
  const tone = state?.running ? "warn" : !latest ? "off" : latest.status === "pass" ? "good" : latest.status === "warn" ? "warn" : "bad";
  return <div className="sidebar-check">
    <span className="sidebar-check__state">{dot(tone)}{label}</span>
    {latest && !state?.running && <small>{ago(latest.at)}</small>}
    <button type="button" disabled={state?.running || (state?.retryAfter ?? 0) > 0} onClick={() => void run()}
      title={(state?.retryAfter ?? 0) > 0 ? `Again in ${Math.ceil((state?.retryAfter ?? 0) / 60)} min` : "Run ZAE's security self-check"}>
      {(state?.retryAfter ?? 0) > 0 ? `Again in ${Math.ceil((state?.retryAfter ?? 0) / 60)} min` : "Run check"}</button>
    {note && <small>{note}</small>}
  </div>;
}
