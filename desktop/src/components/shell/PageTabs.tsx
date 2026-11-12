import { usePaneNav } from "./PaneNav";
import { PageNavigator } from "./PageNavigator";
import { Suspense, useEffect, useState } from "react";
import type { ReactNode } from "react";
import "../research/Research.css";

/** Tabs along the top of a page (Status, Settings, Workbench…). Each tab stays mounted once opened. */
export function PageTabs({ id, tabs }: { id: string; tabs: { id: string; label: string; render: () => ReactNode }[] }) {
  const key = `zaenia.pageTab.${id}`;
  const [tab, setTab] = useState(() => {
    try { const saved = localStorage.getItem(key); return tabs.some(item => item.id === saved) ? saved! : tabs[0].id; }
    catch { return tabs[0].id; }
  });
  const [opened, setOpened] = useState<string[]>([tab]);
  const choose = (next: string) => {
    setTab(next); setOpened(current => current.includes(next) ? current : [...current, next]);
    try { localStorage.setItem(key, next); } catch { /* optional */ }
  };
  // "Open Files" / "open news" jump straight to that sub-tab even when this page is already open.
  const paneScope = usePaneNav();
  useEffect(() => {
    const jump = (event: Event) => { const detail = (event as CustomEvent<{ page: string; tab: string }>).detail; if ((detail as { pane?: string })?.pane && paneScope && (detail as { pane?: string }).pane !== paneScope.paneId) return; if (detail?.page === id && tabs.some(item => item.id === detail.tab)) choose(detail.tab); };
    window.addEventListener("zae:page-tab", jump); return () => window.removeEventListener("zae:page-tab", jump);
  });
  return <div className="research-page">
    <PageNavigator id={id} name={id === "life" ? "LIFE" : id.charAt(0).toUpperCase() + id.slice(1)} items={tabs} current={tab} onChoose={choose}/>
    {tabs.filter(item => opened.includes(item.id)).map(item => <div key={item.id} role="region" data-page-panel={item.id} aria-label={item.label} hidden={tab !== item.id}><Suspense fallback={<p className="research__empty">Loading…</p>}>{item.render()}</Suspense></div>)}
  </div>;
}
