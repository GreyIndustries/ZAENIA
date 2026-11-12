import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { CATEGORIES } from "../../core/categories";
import { CATEGORY_META, CATEGORY_MODULES, PAGE_CATALOG } from "../../core/pageCatalog";
import { searchPages, type PageRoute } from "../../core/voiceUi";
import "./Bento.css";

/**
 * Grey's preview 05 (desktop) and M5 (phone) building blocks (Claude, 2026-11-11). Every page uses these, so the
 * category sheet, module homes, screens with children and leaf screens look exactly like the preview.
 */
export const ICONS: Record<string, string> = {
  cal: '<rect x="3.5" y="5" width="17" height="15" rx="3"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  note: '<path d="M6 3.5h9l4 4v13H6z"/><path d="M15 3.5v4h4M9 12h7M9 16h5"/>',
  heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5"/>',
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  music: '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
  tool: '<path d="M14.5 6.5a4 4 0 0 0-5 5L4 17l3 3 5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-3-3z"/>',
  code: '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>',
  trophy: '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8.5 20h7"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"/>',
  pulse: '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
  shield: '<path d="M12 3l7.5 3v5.5c0 4.5-3.2 8-7.5 9.5-4.3-1.5-7.5-5-7.5-9.5V6z"/>',
  page: '<rect x="5" y="3.5" width="14" height="17" rx="2.5"/><path d="M9 9h6M9 13h6M9 17h3"/>',
  folder: '<path d="M3.5 7a2 2 0 0 1 2-2H10l2 2.5h6.5a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  back: '<path d="M14.5 6l-6 6 6 6"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
};
export const Ico = ({ name }: { name: string }) => <svg className="bx-ico" viewBox="0 0 24 24" aria-hidden="true" dangerouslySetInnerHTML={{ __html: ICONS[name] ?? ICONS.page }}/>;
const CAT_ICON: Record<string, string> = { plan: "cal", health: "heart", know: "book", create: "music", build: "code", system: "gear" };

/** Open a page anywhere in ZAE through the shared router (search, voice and tiles all use it). */
export const openRoute = (route: PageRoute, pane?: string) => window.dispatchEvent(new CustomEvent("zae:open-route", { detail: { ...route, pane } }));
/** Open a page in a new tab (Ctrl/Cmd+click, middle-click, "Open in new tab", or voice). */
export const openTab = (route: PageRoute) => window.dispatchEvent(new CustomEvent("zae:open-tab", { detail: route }));
const wantsTab = (event: { ctrlKey: boolean; metaKey: boolean; button: number }) => event.ctrlKey || event.metaKey || event.button === 1;
/** Open a category page. */
export const openCategory = (id: string) => window.dispatchEvent(new CustomEvent("zae:workspace", { detail: id }));

/** Preview 05 top-row category control: plain text buttons, no icons. */
export function CategorySeg({ current, onPick = openCategory }: { current: string | null; onPick?: (id: string) => void }) {
  return <div className="bx-seg" role="tablist" aria-label="Categories">
    {CATEGORIES.map(item => <button type="button" role="tab" key={item.id} aria-selected={item.id === current} className={item.id === current ? "on" : undefined}
      style={{ "--a": CATEGORY_META[item.id]?.accent } as CSSProperties} onClick={() => onPick(item.id)}>{CATEGORY_META[item.id]?.name ?? item.name}</button>)}
  </div>;
}
/** Phone M5 category chips: icon + label, horizontal scroll. */
export function CategoryChips({ current, onPick = openCategory }: { current: string | null; onPick?: (id: string) => void }) {
  return <div className="bx-pseg" role="tablist" aria-label="Categories">
    {CATEGORIES.map(item => <button type="button" role="tab" key={item.id} aria-selected={item.id === current} className={item.id === current ? "on" : undefined}
      style={{ "--a": CATEGORY_META[item.id]?.accent } as CSSProperties} onClick={() => onPick(item.id)}><Ico name={CAT_ICON[item.id] ?? "page"}/>{CATEGORY_META[item.id]?.name ?? item.name}</button>)}
  </div>;
}

const categoryName = (route: PageRoute) => {
  const id = Object.entries(CATEGORY_MODULES).find(([, list]) => list.some(module => module.app === route.app && (!module.path || module.path.every((part, at) => route.path[at] === part))))?.[0];
  return id ? CATEGORY_META[id]?.name ?? "" : "";
};
function highlight(label: string, query: string): ReactNode {
  const word = query.trim().toLowerCase().replace(/^(open|go to|show|take me to)\s+/, "").replace(/\bthe\b/g, "").trim();
  const at = word ? label.toLowerCase().indexOf(word) : -1;
  return at < 0 ? label : <>{label.slice(0, at)}<mark>{label.slice(at, at + word.length)}</mark>{label.slice(at + word.length)}</>;
}
export function SearchResults({ query, onPick }: { query: string; onPick: (route: PageRoute) => void }) {
  const results = searchPages(query, 9);
  if (!results.length) return <div className="bx-nores">No page called “{query.trim()}”. Try “cookbook”, “library” or “vault”.</div>;
  return <>{results.map((route, at) => { const parts = route.label.split(" / ");
    return <button type="button" key={`${route.app}/${route.path.join("/")}`} className={`bx-res${at === 0 ? " first" : ""}`} onClick={() => onPick(route)}>
      <span className="bx-tile bx-tile--s"><Ico name="page"/></span>
      <span className="bx-res__t">{highlight(parts[parts.length - 1], query)}<span className="bx-res__p">{[categoryName(route), ...parts.slice(0, -1)].filter(Boolean).join(" › ")}</span></span>
      {at === 0 && <span className="bx-res__en">Enter</span>}</button>; })}</>;
}
/**
 * Search box. Desktop (preview 06): compact 42px box in the top row, results drop down beneath, Ctrl K hint and mic.
 * Phone (M5): 56px "Say or type a page" bar with a 42px mic; results replace the body below (onQuery reports the text).
 */
export function PageSearch({ phone = false, voice, onQuery, focusKey }: { phone?: boolean; voice?: { available: boolean; start: () => void }; onQuery?: (query: string) => void; focusKey?: number }) {
  const [query, setQuery] = useState(""); const [note, setNote] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (focusKey) input.current?.focus(); }, [focusKey]);
  const set = (value: string) => { setQuery(value); onQuery?.(value); };
  const pick = (route: PageRoute) => { set(""); openRoute(route); };
  const mic = () => { if (!voice?.available) { setNote("Voice input isn't available here. Check that the microphone is allowed and ZAE is connected, or type the page."); return; } setNote("Listening… say a page, like “open cookbook”."); voice.start(); };
  return <div className={phone ? "bx-psearch" : "bx-sbox"}>
    <label className={phone ? "bx-vbar" : "bx-cmd"}>
      <Ico name="search"/>
      <input ref={input} type="search" value={query} maxLength={100} aria-label="Search pages" data-page-search
        placeholder={phone ? "Say or type a page" : "Go to any page… try “cookbook”, “library” or “vault”"}
        onChange={event => set(event.target.value)}
        onKeyDown={event => { if (event.key === "Enter") { const first = searchPages(query, 1)[0]; if (first) { event.preventDefault(); pick(first); } } if (event.key === "Escape") set(""); }}/>
      {!phone && <kbd>Ctrl K</kbd>}
      <button type="button" className="bx-mic" aria-label="Say a page" onClick={mic}><Ico name="mic"/></button>
    </label>
    {note && <p className="bx-note" role="status">{note}</p>}
    {query.trim() && <div className={phone ? "bx-results bx-results--inline" : "bx-results"} role="list" aria-label="Matching pages"><SearchResults query={query} onPick={pick}/></div>}
  </div>;
}

export type Mini = { key: string; name: string; label: string; onOpen: () => void; route?: PageRoute };
export type Tile = { key: string; name: string; d?: string; icon: string; accent: string; onOpen: () => void; minis?: Mini[]; span?: "wide" | "third" | ""; route?: PageRoute };
/** Bento of the current level's children (preview 05): 6-column grid; tiles span 3, full width when alone or >6 inside. */
export function BentoGrid({ tiles }: { tiles: Tile[] }) {
  return <div className="bx-bento">{tiles.map(tile =>
    <div key={tile.key} className={`bx-bt${tile.span ? ` ${tile.span}` : ""}`} style={{ "--a": tile.accent } as CSSProperties} data-tile={tile.name}>
      <button type="button" className="bx-bh" onClick={event => tile.route && wantsTab(event) ? openTab(tile.route) : tile.onOpen()} onAuxClick={event => { if (event.button === 1 && tile.route) { event.preventDefault(); openTab(tile.route); } }}>
        <span className="bx-tile"><Ico name={tile.icon}/></span>
        <span className="bx-bh__t"><span className="bx-n">{tile.name}</span>{tile.d && <span className="bx-d">{tile.d}</span>}</span>
        <span className="bx-ar" aria-hidden="true">↗</span>
      </button>
      {tile.minis?.length ? <div className="bx-mini">{tile.minis.map(mini => <button type="button" key={mini.key} onClick={event => mini.route && wantsTab(event) ? openTab(mini.route) : mini.onOpen()}
        onAuxClick={event => { if (event.button === 1 && mini.route) { event.preventDefault(); openTab(mini.route); } }}>{mini.name}<small>{mini.label}</small></button>)}</div>
        : <div className="bx-bar bx-bar--m"/>}
    </div>)}</div>;
}
/** Phone M5 accordions: one open at a time (the first by default); a child without children is a plain tile. */
export function Accordion({ tiles }: { tiles: Tile[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const firstOpenable = tiles.findIndex(tile => tile.minis?.length);
  const current = open === null ? firstOpenable : open;
  return <>{tiles.map((tile, index) => { const hasKids = !!tile.minis?.length; const expanded = hasKids && current === index;
    return <div key={tile.key} className={`bx-acc${expanded ? " open" : ""}`} style={{ "--a": tile.accent } as CSSProperties} data-tile={tile.name}>
      <button type="button" className="bx-bh" aria-expanded={hasKids ? expanded : undefined} onClick={() => hasKids ? setOpen(expanded ? -1 : index) : tile.onOpen()}>
        <span className="bx-tile"><Ico name={tile.icon}/></span>
        <span className="bx-bh__t"><span className="bx-n">{tile.name}</span><span className="bx-d">{hasKids ? `${tile.minis!.length} screens` : tile.d || "Screen"}</span></span>
        <span className="bx-tw" aria-hidden="true">›</span>
      </button>
      {expanded && <div className="bx-rows">
        <button type="button" className="bx-rows__home" onClick={tile.onOpen}>Open {tile.name} home<small>↗</small></button>
        {tile.minis!.map(mini => <button type="button" key={mini.key} onClick={mini.onOpen}>{mini.name}<small>{mini.label === "Screen" ? "›" : `${mini.label} ›`}</small></button>)}
      </div>}
    </div>; })}</>;
}
/** Tiles for a catalogue level: each child, its screens as minis ("N inside" / "Screen"). */
export function catalogTiles(app: string, base: string[], items: { id: string; label: string; children?: { id: string; label: string; children?: unknown[] }[] }[], meta: (path: string[]) => { accent: string; icon: string; d?: string }, records: (path: string[]) => Mini[] = () => []): Tile[] {
  const label = PAGE_CATALOG.find(entry => entry.id === app)?.label ?? app;
  return items.map(item => {
    const path = [...base, item.id]; const m = meta(path);
    const minis: Mini[] = (item.children ?? []).map(child => ({ key: child.id, name: child.label, label: child.children?.length ? `${child.children.length} inside` : "Screen",
      onOpen: () => openRoute({ app, path: [...path, child.id], label: `${label} / ${child.label}` }) }));
    return { key: item.id, name: item.label, d: m.d, icon: m.icon, accent: m.accent, onOpen: () => openRoute({ app, path, label: `${label} / ${item.label}` }),
      minis: [...minis, ...records(path)], span: items.length === 1 || (item.children?.length ?? 0) > 6 ? "wide" : "" };
  });
}
/** "Recent work here" card (preview 05 / M5). Continue moves focus to the page's own content. */
export function RecentCard({ what, when, onContinue, label = "Recent work here", action = "Continue" }: { what: string; when: string; onContinue: () => void; label?: string; action?: string }) {
  return <div className="bx-recent" role="note" aria-label={label}>
    <div><div className="bx-recent__l">{label}</div><div className="bx-recent__w">{what}</div><div className="bx-recent__t">{when}</div></div>
    <button type="button" className="bx-recent__go" onClick={onContinue}>{action}</button>
  </div>;
}
