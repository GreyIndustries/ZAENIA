import type { ReactNode } from "react";

/**
 * The six icons on the core are categories that every tab fits in (Grey, 2026-10-30). Listed in the core's slot order:
 * top left, top right, middle left, middle right, bottom left, bottom right. Default grouping: "by what you're doing"
 * (option 1 on Grey's card); change the names, tabs or icons here and the core, tab list and zoom follow.
 */
export type Category = { id: string; name: string; description: string; tabs: string[]; icon: ReactNode };

export const CATEGORIES: readonly Category[] = [
  { id: "plan", name: "Life", description: "Plan, fitness & health, notes", tabs: ["tasks", "notes"],
    icon: <><rect x="5" y="8" width="22" height="19" rx="3"/><path d="M10.5 5v6M21.5 5v6M5 14h22"/><path d="m11 20 3 3 7-7"/></> },
  { id: "health", name: "Health", description: "Fitness, food, training", tabs: ["fitness"],
    icon: <>
      <path d="M16 28.2c-1.7-1.4-6.6-5.5-8.3-9.3-1.7-3.8-.3-7.8 2.8-8.8 2.3-.8 4.3.5 5.5 2.9 1.2-2.8 3.4-4.2 5.7-3.6 3.3.8 4.4 4.7 2.7 8.4-1.8 3.9-6.6 8.7-8.4 10.4Z"/>
      <path d="M14.2 12.7V8.3c0-2 1-3.2 2.5-3.2s2.5 1.2 2.5 3.2v2.1M18.8 9.5V6.2c0-1.8 1-2.9 2.4-2.9s2.4 1.2 2.4 2.9v2.5M13.8 8.4c-1.5-1.3-1.7-3.1-.5-4.1 1.3-1.1 3-.4 3.5.9"/>
      <path d="M16 14.2c-.2 3.2-.3 7.7 0 13.3M10.5 13.6c2.3.4 3.8 1.7 4.5 3.8m6.1-4.6c-2.1.7-3.7 2.1-4.5 4.2"/>
    </> },
  { id: "know", name: "Know", description: "Research, news, assistant", tabs: ["research", "assistant"],
    icon: <><path d="M5 7.5c3.5-1.5 7.5-1.5 11 .8v18c-3.5-2.3-7.5-2.3-11-.8Z"/><path d="M27 7.5c-3.5-1.5-7.5-1.5-11 .8v18c3.5-2.3 7.5-2.3 11-.8Z"/></> },
  { id: "create", name: "Create", description: "Music, workbench", tabs: ["music", "workbench"],
    icon: <><path d="M12 24V8l14-3v16"/><circle cx="8.5" cy="24" r="3.5"/><circle cx="22.5" cy="21" r="3.5"/></> },
  { id: "build", name: "Build", description: "Code Doctor & files, arena", tabs: ["codedoctor", "arena"],
    icon: <><path d="M19 3H9a2.5 2.5 0 0 0-2.5 2.5v21A2.5 2.5 0 0 0 9 29h14a2.5 2.5 0 0 0 2.5-2.5V9.5Z"/><path d="M19 3v6.5h6.5"/><path d="m13.5 16-3 3 3 3M18.5 16l3 3-3 3"/></> },
  { id: "system", name: "Settings", description: "Settings, status, security, updates", tabs: ["system"],
    icon: <><circle cx="16" cy="16" r="4"/><path d="M14.4 3.5h3.2l.7 3.2 2.3 1 2.8-1.8 2.3 2.3-1.8 2.8 1 2.3 3.2.7v3.2l-3.2.7-1 2.3 1.8 2.8-2.3 2.3-2.8-1.8-2.3 1-.7 3.2h-3.2l-.7-3.2-2.3-1-2.8 1.8-2.3-2.3 1.8-2.8-1-2.3-3.2-.7v-3.2l3.2-.7 1-2.3-1.8-2.8 2.3-2.3 2.8 1.8 2.3-1Z"/></> },
];

/** The category a tab belongs to (for the tab list's grouping). */
export const categoryOf = (tab: string) => CATEGORIES.find(category => category.tabs.includes(tab)) ?? null;
