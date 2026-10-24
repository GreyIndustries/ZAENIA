import { IN_TAURI } from "./bridge";

/** Open a web link in the default browser (the desktop app's webview can't open new tabs itself). */
export function openLink(url: string): void {
  if (!/^https?:\/\//i.test(url)) return;
  if (IN_TAURI) {
    void import("@tauri-apps/plugin-opener").then(({ openUrl }) => openUrl(url)).catch(() => undefined);
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
