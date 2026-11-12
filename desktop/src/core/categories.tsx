import type { ReactNode } from "react";

/**
 * The six icons on the core are categories that every tab fits in (Grey, 2026-10-30). Listed in the core's slot order:
 * top left, top right, middle left, middle right, bottom left, bottom right. Default grouping: "by what you're doing"
 * (option 1 on Grey's card); change the names, tabs or icons here and the core, tab list and zoom follow.
 */
export type Category = { id: string; name: string; description: string; tabs: string[]; icon: ReactNode };

export const CATEGORIES: readonly Category[] = [
  { id: "plan", name: "Life", description: "Schedule, fitness & health, mail and notes", tabs: ["tasks", "notes"],
    icon: <><rect x="5" y="8" width="22" height="19" rx="3"/><path d="M10.5 5v6M21.5 5v6M5 14h22"/><path d="m11 20 3 3 7-7"/></> },
  { id: "warroom", name: "War Room", description: "Defense, cameras and business planning", tabs: ["warroom"],
    icon: <><path d="M16 3 27 8v8c0 7-11 13-11 13S5 23 5 16V8Z"/><path d="m11 16 3 3 7-7"/></> },
  { id: "know", name: "Know", description: "Research, news, assistant", tabs: ["research", "assistant"],
    icon: <><path d="M5 7.5c3.5-1.5 7.5-1.5 11 .8v18c-3.5-2.3-7.5-2.3-11-.8Z"/><path d="M27 7.5c-3.5-1.5-7.5-1.5-11 .8v18c3.5-2.3 7.5-2.3 11-.8Z"/></> },
  { id: "create", name: "Create", description: "Music", tabs: ["music"],
    icon: <><path d="M12 24V8l14-3v16"/><circle cx="8.5" cy="24" r="3.5"/><circle cx="22.5" cy="21" r="3.5"/></> },
  { id: "build", name: "Build", description: "Workbench, Code Doctor and LLM Training", tabs: ["workbench", "codedoctor", "arena"],
    icon: <><path d="M19 3H9a2.5 2.5 0 0 0-2.5 2.5v21A2.5 2.5 0 0 0 9 29h14a2.5 2.5 0 0 0 2.5-2.5V9.5Z"/><path d="M19 3v6.5h6.5"/><path d="m13.5 16-3 3 3 3M18.5 16l3 3-3 3"/></> },
  { id: "system", name: "Settings", description: "Settings, status, security, updates", tabs: ["system"],
    icon: <><circle cx="16" cy="16" r="4"/><path d="M14.4 3.5h3.2l.7 3.2 2.3 1 2.8-1.8 2.3 2.3-1.8 2.8 1 2.3 3.2.7v3.2l-3.2.7-1 2.3 1.8 2.8-2.3 2.3-2.8-1.8-2.3 1-.7 3.2h-3.2l-.7-3.2-2.3-1-2.8 1.8-2.3-2.3 1.8-2.8-1-2.3-3.2-.7v-3.2l3.2-.7 1-2.3-1.8-2.8 2.3-2.3 2.8 1.8 2.3-1Z"/></> },
];

/** The category a tab belongs to (for the tab list's grouping). */
export const categoryOf = (tab: string) => CATEGORIES.find(category => category.tabs.includes(tab)) ?? null;
