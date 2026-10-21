import { useEffect, useState } from "react";
export const STARTUP_DURATION = 7000;
export function startupPercent(elapsed: number) {
  return Math.min(100, Math.max(0, Math.floor(elapsed / STARTUP_DURATION * 100)));
}
export function useCoreStartup(replay: number) {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    setProgress(0);
    const started = performance.now();
    let frame = 0;
    const advance = (now: number) => {
      const next = startupPercent(now - started);
      setProgress(next);
      if (next < 100) frame = requestAnimationFrame(advance);
    };
    frame = requestAnimationFrame(advance);
    return () => cancelAnimationFrame(frame);
  }, [replay]);
  return { progress, ready: progress === 100 };
}
