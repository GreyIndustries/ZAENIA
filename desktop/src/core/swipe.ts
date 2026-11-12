import { useEffect, useRef } from "react";

/**
 * App-style swiping for the phone (Grey, 2026-10-30): swipe left for the next sub-tab, right for the previous one;
 * past the first or last sub-tab it moves to the neighbouring tab in the bottom-bar order. Swipes that start on text
 * fields, sliders, maps, the chat box or anything that scrolls sideways are left alone.
 */
export type SwipeDirection = "next" | "previous";

/** A deliberate horizontal swipe: long enough, mostly sideways and quick. */
export function swipeDirection(dx: number, dy: number, ms: number): SwipeDirection | null {
  if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.6 || ms > 700) return null;
  return dx < 0 ? "next" : "previous";
}

/** Where a swipe goes: another sub-tab on this page, or the neighbouring page at the ends. */
export function swipeTarget(direction: SwipeDirection, subTab: number, subTabs: number, page: number, pages: number):
  { kind: "subtab"; index: number } | { kind: "page"; index: number } | null {
  const step = direction === "next" ? 1 : -1;
  if (subTabs > 1 && subTab + step >= 0 && subTab + step < subTabs) return { kind: "subtab", index: subTab + step };
  if (page + step >= 0 && page + step < pages) return { kind: "page", index: page + step };
  return null;
}

const NO_SWIPE = "input, textarea, select, [contenteditable=true], [data-no-swipe], .home-chat, .calm, .barcode-scanner, .ov-cat, .ov-sheet";

function scrollsSideways(element: Element | null, stop: Element): boolean {
  for (let node = element; node && node !== stop; node = node.parentElement) {
    const style = getComputedStyle(node);
    if ((style.overflowX === "auto" || style.overflowX === "scroll") && node.scrollWidth > node.clientWidth + 4) return true;
  }
  return false;
}

export function useSwipeNavigation({ enabled, root, pages, current, open }: {
  enabled: boolean; root: () => HTMLElement | null; pages: readonly string[]; current: string; open: (page: string) => void;
}) {
  const latest = useRef({ pages, current, open });
  latest.current = { pages, current, open };
  useEffect(() => {
    const host = root();
    if (!enabled || !host) return;
    let start: { x: number; y: number; at: number; target: Element | null } | null = null;
    const down = (event: TouchEvent) => {
      if (event.touches.length !== 1) { start = null; return; }
      const target = event.target as Element | null;
      if (target?.closest(NO_SWIPE) || scrollsSideways(target, host)) { start = null; return; }
      start = { x: event.touches[0].clientX, y: event.touches[0].clientY, at: Date.now(), target };
    };
    const up = (event: TouchEvent) => {
      if (!start) return;
      const touch = event.changedTouches[0];
      const direction = swipeDirection(touch.clientX - start.x, touch.clientY - start.y, Date.now() - start.at);
      start = null;
      if (!direction) return;
      const { pages: order, current: page, open: go } = latest.current;
      // The page's own sub-tab row: the first visible tab list in the main view.
      const pageNavigator = [...host.querySelectorAll<HTMLElement>("[data-page-navigator]")].find(node => node.offsetParent !== null && !node.closest("[hidden]"));
      if (pageNavigator) {
        const step = pageNavigator.querySelector<HTMLButtonElement>(direction === "next" ? "[data-page-next]" : "[data-page-previous]");
        if (step && !step.disabled) step.click();
        return; // Never switch apps accidentally at a subpage boundary.
      }
      const row = [...host.querySelectorAll<HTMLElement>('[role="tablist"]')].find(list => list.offsetParent !== null && !list.closest("[hidden]"));
      const tabs = row ? [...row.querySelectorAll<HTMLElement>('[role="tab"]')] : [];
      const selected = tabs.findIndex(tab => tab.getAttribute("aria-selected") === "true");
      const goal = swipeTarget(direction, Math.max(0, selected), tabs.length, Math.max(0, order.indexOf(page)), order.length);
      if (!goal) return;
      host.dataset.swipe = direction;
      window.setTimeout(() => { delete host.dataset.swipe; }, 320);
      if (goal.kind === "subtab") { tabs[goal.index].click(); tabs[goal.index].scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" }); }
      else go(order[goal.index]);
    };
    host.addEventListener("touchstart", down, { passive: true });
    host.addEventListener("touchend", up, { passive: true });
    return () => { host.removeEventListener("touchstart", down); host.removeEventListener("touchend", up); };
  }, [enabled, root]);
}
