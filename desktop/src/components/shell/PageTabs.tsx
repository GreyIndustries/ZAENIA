import { useState } from "react";
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
  return <div className="research-page">
    <nav className="research-page__tabs" role="tablist" aria-label={`${id} sections`}>
      {tabs.map(item => <button key={item.id} type="button" role="tab" aria-selected={tab === item.id}
        className={tab === item.id ? "research-page__tab research-page__tab--on" : "research-page__tab"} onClick={() => choose(item.id)}>{item.label}</button>)}
    </nav>
    {tabs.filter(item => opened.includes(item.id)).map(item => <div key={item.id} role="tabpanel" hidden={tab !== item.id}>{item.render()}</div>)}
  </div>;
}
