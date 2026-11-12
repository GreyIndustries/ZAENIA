import { ResearchWorkshop, ResearchReference, ResearchCards } from "./ResearchWorkshop";
import { usePaneNav } from "../shell/PaneNav";
import { PageNavigator } from "../shell/PageNavigator";
import { lazy, Suspense, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { ReadItem } from "./ResearchStudio";
import "./Research.css";

const ResearchDesk = lazy(() => import("./ResearchStudio").then(module => ({ default: module.ResearchDesk })));
const ResearchReader = lazy(() => import("./ResearchStudio").then(module => ({ default: module.ResearchReader })));
const EvidenceBoard = lazy(() => import("./ResearchStudio").then(module => ({ default: module.EvidenceBoard })));
const HistoryPanel = lazy(() => import("./HistoryPanel").then(module => ({ default: module.HistoryPanel })));
const NotebookPanel = lazy(() => import("./NotebookPanel").then(module => ({ default: module.NotebookPanel })));
const NewsPanel = lazy(() => import("../news/NewsPanel").then(module => ({ default: module.NewsPanel })));
const LibraryPanel = lazy(() => import("./LibraryPanel").then(module => ({ default: module.LibraryPanel })));
const WebAgentPanel = lazy(() => import("./WebAgentPanel").then(module => ({ default: module.WebAgentPanel })));
const TranslatePanel = lazy(() => import("./TranslatePanel").then(module => ({ default: module.TranslatePanel })));
const ScripturePanel = lazy(() => import("./ScripturePanel").then(module => ({ default: module.ScripturePanel })));

export type ResearchTab = "workshop" | "reference" | "cards" | "desk" | "reader" | "board" | "history" | "notebook" | "news" | "library" | "scripture" | "translate" | "agent";
// Grey's order (2026-10-29): Desk, Reader, Evidence board, then every tool the page already had.
const TABS: { id: ResearchTab; label: string }[] = [
  { id: "desk", label: "Desk" }, { id: "workshop", label: "Analysis workshop" }, { id: "reference", label: "Learning explorer" }, { id: "cards", label: "Study cards" }, { id: "reader", label: "Reader" }, { id: "board", label: "Evidence board" },
  { id: "agent", label: "Web agent" }, { id: "history", label: "Historical Connections" }, { id: "notebook", label: "Notebook" },
  { id: "news", label: "News" }, { id: "library", label: "The Library" }, { id: "scripture", label: "Scripture & ancient" },
  { id: "translate", label: "Translate" },
];
const KEY = "zaenia.researchTab";

function saved(): ResearchTab {
  try { const value = localStorage.getItem(KEY); return TABS.some(tab => tab.id === value) ? value as ResearchTab : "desk"; }
  catch { return "desk"; }
}

/** Research: one page, its parts as tabs along the top. The Desk opens things in the Reader and topics on the Evidence board. */
export function ResearchPage({ initial }: { initial?: ResearchTab }) {
  const [tab, setTab] = useState<ResearchTab>(initial ?? saved);
  const [reading, setReading] = useState<ReadItem | null>(null);
  const [boardTopic, setBoardTopic] = useState<string | null>(null);
  const choose = (next: ResearchTab) => { setTab(next); try { localStorage.setItem(KEY, next); } catch { /* optional */ } };
  const read = (item: ReadItem) => { setReading(item); choose("reader"); };
  const board = (topicId: string) => { setBoardTopic(topicId); choose("board"); };
  const paneScope = usePaneNav();
  useEffect(() => {
    const jump = (event: Event) => { const detail = (event as CustomEvent<{ page: string; tab: ResearchTab }>).detail; if ((detail as { pane?: string })?.pane && paneScope && (detail as { pane?: string }).pane !== paneScope.paneId) return; if (detail?.page === "research" && TABS.some(item => item.id === detail.tab)) choose(detail.tab); };
    window.addEventListener("zae:page-tab", jump); return () => window.removeEventListener("zae:page-tab", jump);
  });
  const panel = (id: ResearchTab) => id === "workshop" ? <ResearchWorkshop/> : id === "reference" ? <ResearchReference/> : id === "cards" ? <ResearchCards/> : id === "desk" ? <ResearchDesk onRead={read} onBoard={board}/>
    : id === "reader" ? <ResearchReader item={reading} onRead={read}/>
    : id === "board" ? <EvidenceBoard topicId={boardTopic} onTopic={setBoardTopic} onRead={read}/>
    : id === "history" ? <HistoryPanel/> : id === "notebook" ? <NotebookPanel/> : id === "news" ? <NewsPanel/> : id === "scripture" ? <ScripturePanel/>
    : id === "translate" ? <TranslatePanel/> : id === "agent" ? <WebAgentPanel/> : <LibraryPanel/>;
  return <div className="research-page">
    <PageNavigator id={"research"} name={"Research"} items={TABS} current={tab} onChoose={next => choose(next as ResearchTab)}/>
    {/* Each tab stays mounted once opened, so switching back keeps your search, notes and timeline. */}
    {TABS.map(item => <OpenedTab key={item.id} label={item.label} active={tab === item.id}>{panel(item.id)}</OpenedTab>)}
  </div>;
}

function OpenedTab({ active, children, label }: { active: boolean; children: ReactNode; label: string }) {
  const [opened, setOpened] = useState(active);
  if (active && !opened) setOpened(true);
  if (!opened) return null;
  return <div role="region" aria-label={label} data-page-panel={label} hidden={!active}>
    <Suspense fallback={<p className="research__empty">Loading…</p>}>{children}</Suspense>
  </div>;
}
