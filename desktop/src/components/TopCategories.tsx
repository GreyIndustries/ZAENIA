import { useEffect, useState, type ReactNode } from "react";
import { CATEGORIES } from "../core/categories";
import "./TopCategories.css";

/** Direct workspace destinations; no hover menus or app dropdowns. */
export function TopCategories({ tabs, current }: {
  tabs: { id: string; label: string; icon: ReactNode }[]; current: string;
}) {
  const [workspace, setWorkspace] = useState<string | null>(null);
  useEffect(() => {
    const update = (event: Event) => setWorkspace((event as CustomEvent<string | null>).detail);
    window.addEventListener("zae:navigation-view", update);
    return () => window.removeEventListener("zae:navigation-view", update);
  }, []);
  return <nav className="top-cats" aria-label="Category workspaces">
    {CATEGORIES.filter(category => category.tabs.some(id => tabs.some(tab => tab.id === id)) || category.id === "health").map(category =>
      <button key={category.id} type="button" className="top-cats__btn" title={`Open ${category.name} workspace`}
        aria-current={(workspace ? workspace === category.id : category.tabs.includes(current)) ? "page" : undefined}
        onClick={() => window.dispatchEvent(new CustomEvent("zae:workspace", { detail: category.id }))}>
        <svg viewBox="0 0 32 32" aria-hidden="true">{category.icon}</svg><span>{category.name}</span>
      </button>)}
  </nav>;
}
