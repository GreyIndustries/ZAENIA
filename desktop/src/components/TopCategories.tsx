import { useEffect, useRef, useState, type ReactNode } from "react";
import { CATEGORIES } from "../core/categories";
import "./TopCategories.css";

/**
 * The core's six categories in the top bar, next to Home (Grey, 2026-10-31): hover or click one for its tabs,
 * so any tab is two clicks from anywhere. A category with one tab opens it on click.
 */
export function TopCategories({ tabs, current, onOpen }: {
  tabs: { id: string; label: string; icon: ReactNode }[]; current: string; onOpen: (id: string) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const closeTimer = useRef(0);
  const bar = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => { if (!bar.current?.contains(event.target as Node)) setOpen(null); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(null); };
    window.addEventListener("pointerdown", away); window.addEventListener("keydown", escape);
    return () => { window.removeEventListener("pointerdown", away); window.removeEventListener("keydown", escape); };
  }, [open]);
  const go = (id: string) => { setOpen(null); onOpen(id); };
  return <nav className="top-cats" ref={bar} aria-label="Categories">
    {CATEGORIES.map(category => {
      const items = category.tabs.map(id => tabs.find(tab => tab.id === id)).filter(Boolean) as typeof tabs;
      if (!items.length) return null;
      const here = category.tabs.includes(current);
      return <div key={category.id} className="top-cats__cat"
        onMouseEnter={() => { window.clearTimeout(closeTimer.current); setOpen(category.id); }}
        onMouseLeave={() => { closeTimer.current = window.setTimeout(() => setOpen(o => o === category.id ? null : o), 180); }}>
        <button type="button" className="top-cats__btn" aria-expanded={open === category.id} aria-haspopup="menu" aria-current={here ? "true" : undefined}
          title={category.description}
          onClick={() => items.length === 1 ? go(items[0].id) : setOpen(o => o === category.id ? null : category.id)}>
          <svg viewBox="0 0 32 32" aria-hidden="true">{category.icon}</svg><span>{category.name}</span>
        </button>
        {open === category.id && <div className="top-cats__drop" role="menu" aria-label={category.name}>
          <small>{category.description}</small>
          {items.map(item => <button key={item.id} type="button" role="menuitem" className="top-cats__item" aria-current={item.id === current ? "page" : undefined}
            onClick={() => go(item.id)}>{item.icon}<span>{item.label}</span></button>)}
        </div>}
      </div>;
    })}
  </nav>;
}
