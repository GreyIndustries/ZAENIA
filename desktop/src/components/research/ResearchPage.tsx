import { lazy, Suspense, useState } from "react";
import "./Research.css";

const HistoryPanel = lazy(() => import("./HistoryPanel").then(module => ({ default: module.HistoryPanel })));
const NotebookPanel = lazy(() => import("./NotebookPanel").then(module => ({ default: module.NotebookPanel })));
const NewsPanel = lazy(() => import("../news/NewsPanel").then(module => ({ default: module.NewsPanel })));
const LibraryPanel = lazy(() => import("./LibraryPanel").then(module => ({ default: module.LibraryPanel })));

export type ResearchTab = "history" | "notebook" | "news" | "library";
const TABS: { id: ResearchTab; label: string }[] = [
  { id: "history", label: "Historical Connections" }, { id: "notebook", label: "Notebook" },
  { id: "news", label: "News" }, { id: "library", label: "The Library" },
];
const KEY = "zaenia.researchTab";

function saved(): ResearchTab {
  try { const value = localStorage.getItem(KEY); return TABS.some(tab => tab.id === value) ? value as ResearchTab : "history"; }
  catch { return "history"; }
}

/** Research: one page, its parts as tabs along the top (like Quantum's Research page). */
export function ResearchPage({ initial }: { initial?: ResearchTab }) {
  const [tab, setTab] = useState<ResearchTab>(initial ?? saved);
  const choose = (next: ResearchTab) => { setTab(next); try { localStorage.setItem(KEY, next); } catch { /* optional */ } };
  return <div className="research-page">
    <nav className="research-page__tabs" role="tablist" aria-label="Research">
      {TABS.map(item => <button key={item.id} type="button" role="tab" aria-selected={tab === item.id}
        className={tab === item.id ? "research-page__tab research-page__tab--on" : "research-page__tab"} onClick={() => choose(item.id)}>{item.label}</button>)}
    </nav>
    {/* Each tab stays mounted once opened, so switching back keeps your search, notes and timeline. */}
    {TABS.map(item => <OpenedTab key={item.id} active={tab === item.id} id={item.id}/>)}
  </div>;
}

function OpenedTab({ active, id }: { active: boolean; id: ResearchTab }) {
  const [opened, setOpened] = useState(active);
  if (active && !opened) setOpened(true);
  if (!opened) return null;
  return <div role="tabpanel" hidden={!active}>
    <Suspense fallback={<p className="research__empty">Loading…</p>}>
      {id === "history" ? <HistoryPanel/> : id === "notebook" ? <NotebookPanel/> : id === "news" ? <NewsPanel/> : <LibraryPanel/>}
    </Suspense>
  </div>;
}
