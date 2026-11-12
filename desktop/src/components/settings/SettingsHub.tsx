import { usePaneNav } from "../shell/PaneNav";
import { Suspense, useEffect, useState } from "react";
import type { ReactNode } from "react";
import "./SettingsHub.css";

/**
 * Settings, Status and Security in one window (Grey, 2026-11-09), with a side menu like the
 * Fitness & Health food rail. Each page keeps its own top tabs and stays mounted once opened.
 * "Open status" / "open security" land here through the window aliases in App.tsx.
 */
export function SettingsHub({ pages }: { pages: { id: string; label: string; render: () => ReactNode }[] }) {
  const key = "zaenia.pageTab.settingshub";
  const [page, setPage] = useState(() => {
    try { const saved = localStorage.getItem(key); return pages.some(item => item.id === saved) ? saved! : pages[0].id; }
    catch { return pages[0].id; }
  });
  const [opened, setOpened] = useState<string[]>([page]);
  const choose = (next: string) => {
    setPage(next); setOpened(current => current.includes(next) ? current : [...current, next]);
    try { localStorage.setItem(key, next); } catch { /* optional */ }
  };
  const paneScope = usePaneNav();
  useEffect(() => {
    const jump = (event: Event) => {
      const detail = (event as CustomEvent<{ page: string; tab: string }>).detail; if ((detail as { pane?: string })?.pane && paneScope && (detail as { pane?: string }).pane !== paneScope.paneId) return;
      if (detail?.page === "settingshub" && pages.some(item => item.id === detail.tab)) choose(detail.tab);
    };
    window.addEventListener("zae:page-tab", jump); return () => window.removeEventListener("zae:page-tab", jump);
  });
  return <div className="settings-hub">
    <nav className="settings-hub__rail" aria-label="Settings sections">
      {pages.map(item => <button key={item.id} type="button" aria-pressed={page === item.id} onClick={() => choose(item.id)}>{item.label}</button>)}
    </nav>
    <div className="settings-hub__main">
      {pages.filter(item => opened.includes(item.id)).map(item => <div key={item.id} hidden={page !== item.id}>
        <Suspense fallback={<p className="hint">Loading…</p>}>{item.render()}</Suspense></div>)}
    </div>
  </div>;
}
