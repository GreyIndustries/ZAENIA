/**
 * Light up what ZAE just did (Grey, 2026-10-31): after a spoken or typed request opens a tab, the item it made or
 * changed glows for a few seconds and scrolls into view. The tab's list may still be loading, so it keeps looking
 * for a few seconds. Chat lines are skipped (the request itself always contains the words).
 */
const CARD = "li, tr, article, [class*='card'], [class*='row'], [class*='item'], [class*='tile'], button, section";

function find(wanted: string): HTMLElement | null {
  const root = document.querySelector(".zaenia-app") ?? document.body;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    if (!(node.nodeValue ?? "").toLowerCase().includes(wanted)) continue;
    const element = node.parentElement;
    if (!element || element.closest(".home-chat, .message, [role=log], .calm, .ov-cat, .zae-toast")) continue;
    if (!element.getClientRects().length) continue; // hidden (another tab, a closed window)
    return element;
  }
  return null;
}

export function glowItem(text: string, { tries = 16, delay = 350 }: { tries?: number; delay?: number } = {}): void {
  const full = text.trim().toLowerCase().replace(/\s+/g, " ");
  if (full.length < 2) return;
  // A saved title can differ a little from the words used ("3 eggs and toast" → "Eggs and toast"): later tries
  // fall back to the longest word.
  const longest = full.split(" ").filter(word => word.length >= 4).sort((a, b) => b.length - a.length)[0] ?? full;
  let attempt = 0;
  const look = () => {
    const found = find(full) ?? (attempt >= tries / 2 ? find(longest) : null);
    if (!found) { if (++attempt < tries) window.setTimeout(look, delay); return; }
    const card = found.closest<HTMLElement>(CARD) ?? found;
    card.classList.remove("zae-glow");
    void card.offsetWidth; // restart the animation
    card.classList.add("zae-glow");
    card.scrollIntoView({ block: "center", behavior: "smooth" });
    window.setTimeout(() => card.classList.remove("zae-glow"), 5200);
  };
  window.setTimeout(look, 450);
}
