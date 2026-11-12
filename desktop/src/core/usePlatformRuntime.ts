import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "./bridge";
import { parsePlatformSummary } from "./platformModel";
import { skipWhileAway } from "./appBackground";
import type { PlatformSummary } from "./platformModel";

export function usePlatformRuntime() {
  const [summary, setSummary] = useState<PlatformSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const mounted = useRef(true);
  const refresh = useCallback(async () => {
    if (!LIVE_API || busy.current || document.hidden) return;
    busy.current = true;
    try {
      const parsed = parsePlatformSummary(await api("GET", "/api/platform/summary"));
      if (!parsed) throw new Error("The assistant capability response couldn't be read.");
      if (mounted.current) { setSummary(parsed); setError(null); }
    } catch (failure) { if (mounted.current) setError(errorText(failure)); }
    finally { busy.current = false; }
  }, []);
  useEffect(() => {
    mounted.current = true;
    // Every 2.5 s in use; every 15 s while the window is in the background.
    const away = { n: 0 };
    void refresh(); const timer = window.setInterval(() => { if (!skipWhileAway(away, 6)) void refresh(); }, 2500);
    const visible = () => { if (!document.hidden) void refresh(); };
    document.addEventListener("visibilitychange", visible);
    return () => { mounted.current = false; window.clearInterval(timer); document.removeEventListener("visibilitychange", visible); };
  }, [refresh]);
  return { summary, error, refresh };
}
