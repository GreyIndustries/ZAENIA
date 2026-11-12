import { BUILT_VERSIONS, useUpdates } from "./UpdatesPanel";
import type { VersionItem } from "./UpdatesPanel";
import "./SettingsHub.css";

/** Settings > About (like Windows' About): every version number, one place. */
function Table({ title, items, extra }: { title: string; items?: Record<string, VersionItem>; extra?: (item: VersionItem) => string }) {
  if (!items) return null;
  return <section className="zu-card">
    <p className="zu-kicker">{title}</p>
    <table className="zu-table"><thead><tr><th>Part</th><th>Version</th><th>{extra ? "Details" : ""}</th></tr></thead>
      <tbody>{Object.entries(items).map(([id, item]) => <tr key={id}><td>{item.name}</td><td>{item.version}</td><td className="zu-muted">{extra ? extra(item) : item.note ?? ""}</td></tr>)}</tbody>
    </table>
  </section>;
}

export function AboutPanel() {
  const { data } = useUpdates();
  const running = data?.running;
  const system = running?.system?.version ?? BUILT_VERSIONS.system?.version;
  const nodes = running?.nodes ?? BUILT_VERSIONS.nodes;
  const behind = running?.system?.version && running.system.version !== BUILT_VERSIONS.system?.version;
  return <div className="zu">
    <section className="zu-card">
      <div className="zu-about-head"><strong>ZÆNIA</strong><div>
        <p className="zu-muted">Zack's Ædaptive Neural Intelligence Assystem</p>
        <p className="zu-muted">Beta · offline-first personal assistant system for Windows</p></div></div>
      <div className="zu-versions" style={{ marginTop: 12 }}>
        <div><small>System</small><b>{system}</b><small>capabilities and security</small></div>
        <div><small>Interface</small><b>{BUILT_VERSIONS.ui?.version}</b><small>this app</small></div>
        <div><small>Server reports</small><b>{running?.system?.version ?? "—"}</b><small>{data ? "live" : "not reached"}</small></div>
      </div>
      {behind && <p className="zu-muted">The server and this app list different system versions; install the waiting update or restart the server.</p>}
      {BUILT_VERSIONS.scheme && <p className="zu-muted">{BUILT_VERSIONS.scheme}</p>}
    </section>
    <Table title="Tabs" items={BUILT_VERSIONS.tabs}/>
    <Table title="Modules" items={running?.modules ?? BUILT_VERSIONS.modules}/>
    <Table title="Brains (nodes)" items={nodes} extra={item => [item.job, item.model].filter(Boolean).join(" · ")}/>
  </div>;
}
