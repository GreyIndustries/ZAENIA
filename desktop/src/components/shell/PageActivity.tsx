import { useEffect, useRef, useState } from "react";
import { activityLine, clearPageActivities, readPageActivities, recordPageActivity, type PageActivity } from "../../core/pageActivity";

export function visiblePageNavigators(root: ParentNode = document) {
  return [...root.querySelectorAll<HTMLElement>("[data-page-navigator]")].filter(node => !node.closest("[hidden],[inert]") && node.getClientRects().length > 0);
}
/** One capture observer, independent of the size or number of app pages. */
export function PageActivityObserver({ section, enabled }: { section: string; enabled: boolean }) {
  const recentWrites = useRef(new Map<string, number>());
  useEffect(() => {
    if (!enabled) return;
    const record = (event: Event) => {
      const target = event.target instanceof HTMLElement ? event.target : null;
      if (!target || target.closest(".page-nav,.navhub,.query-console,.chat-composer,[hidden],[inert]")) return;
      const nav = visiblePageNavigators().filter(node => node.parentElement?.contains(target)).slice(-1)[0];
      if (!nav) return;
      const control = target.closest<HTMLElement>("button,input,textarea,select");
      if (!control || control.matches(":disabled") || control.getAttribute("type") === "password"
        || /passkey|password|token|secret|private.key|credit.card/i.test(`${control.id} ${control.getAttribute("name")} ${control.getAttribute("aria-label")}`)) return;
      const app = nav.closest<HTMLElement>("[data-window-id]")?.dataset.windowId ?? section;
      const navigator = nav.dataset.pageNavigator!, page = nav.dataset.pageCurrent!, label = nav.dataset.pageLabel!;
      if (!app || !navigator || !page || !label) return;
      const edited = ["input", "change"].includes(event.type);
      if (event.type === "click" && !target.closest("button")) return;
      const key = `${app}/${navigator}/${page}`, now = Date.now();
      if (now - (recentWrites.current.get(key) ?? 0) < 2000) return;
      recentWrites.current.set(key, now); if (recentWrites.current.size > 100) recentWrites.current.delete(recentWrites.current.keys().next().value!);
      const title = control.closest<HTMLElement>("[data-work-title]")?.dataset.workTitle?.trim().replace(/[\r\n]+/g, " ").slice(0, 100);
      recordPageActivity({ key, app, navigator, page, label, subject: title || `your ${label} work`, action: edited ? "edited" : "used", at: now });
    };
    document.addEventListener("input", record, true); document.addEventListener("change", record, true); document.addEventListener("click", record, true);
    return () => { document.removeEventListener("input", record, true); document.removeEventListener("change", record, true); document.removeEventListener("click", record, true); };
  }, [enabled, section]);
  return null;
}
export function RecentPageWork({ navigator, page }: { navigator: string; page: string }) {
  const [recent, setRecent] = useState<PageActivity | null>(() => readPageActivities().find(item => item.navigator === navigator && item.page === page) ?? null);
  useEffect(() => {
    const load = () => setRecent(readPageActivities().find(item => item.navigator === navigator && item.page === page) ?? null);
    load(); window.addEventListener("zae:page-activity-cleared", load); window.addEventListener("storage", load);
    return () => { window.removeEventListener("zae:page-activity-cleared", load); window.removeEventListener("storage", load); };
  }, [navigator, page]);
  return <aside className="mission-recent" aria-label="Recently worked on this page">
    <div className="mission-recent__mark" aria-hidden="true">↶</div><div><small>Recently on this page</small>
      <p>{recent ? activityLine(recent) : "No recent work recorded for this page yet, sir."}</p>
      {recent && <span>{recent.action === "edited" ? "Edited a field" : "Used a page control"} · {new Date(recent.at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>}
    </div>
  </aside>;
}
export function ClearPageWorkButton() { return <button type="button" onClick={clearPageActivities}>Clear recent page work</button>; }
