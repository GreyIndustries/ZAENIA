import { useEffect, useState } from "react";

/** The window is hidden or another app has focus. */
export function windowAway(): boolean {
  return document.hidden || !document.hasFocus();
}

/**
 * For polling timers: true on the ticks to skip while the window is away, so
 * a check that runs every few seconds in use runs `every` times less often in
 * the background. Each timer keeps its own counter.
 */
export function skipWhileAway(counter: { n: number }, every: number): boolean {
  if (!windowAway()) { counter.n = 0; return false; }
  counter.n += 1;
  return counter.n % every !== 1;
}

/**
 * True while ZAE's window is in the background (hidden or not focused) and
 * she isn't busy hearing, thinking or speaking. The core then holds still and
 * animations pause, so an idle ZAE in the background barely uses the GPU or
 * CPU. Clicking back into the app, or her starting to respond, wakes it.
 */
export function useAppInBackground(busy: boolean): boolean {
  const [away, setAway] = useState(windowAway);
  useEffect(() => {
    const update = () => setAway(windowAway());
    window.addEventListener("focus", update);
    window.addEventListener("blur", update);
    document.addEventListener("visibilitychange", update);
    update();
    return () => {
      window.removeEventListener("focus", update);
      window.removeEventListener("blur", update);
      document.removeEventListener("visibilitychange", update);
    };
  }, []);
  return away && !busy;
}
