import { useEffect, useRef, useState } from "react";
import { classifyHand, GestureInterpreter } from "../../core/handGestures";
import type { GestureCommand, Point } from "../../core/handGestures";

export function HandControls({ enabled, onDisable, onCommand }: { enabled: boolean; onDisable: (reason?: string) => void; onCommand: (command: GestureCommand) => void }) {
  const command = useRef(onCommand); command.current = onCommand;
  const disable = useRef(onDisable); disable.current = onDisable;
  const [state, setState] = useState("Off");
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);
  useEffect(() => {
    if (!enabled) { setState("Off"); setPointer(null); return; }
    let closed = false, ready = false, inFlight = false, timer = 0, sentAt = 0;
    let stream: MediaStream | null = null;
    const video = document.createElement("video"); video.muted = true; video.playsInline = true;
    let worker: Worker;
    try { worker = new Worker(`${import.meta.env.BASE_URL}handtracking/worker.js`); }
    catch { disable.current("This browser couldn't start local hand tracking."); return; }
    const startupTimeout = window.setTimeout(() => { if (!ready) fail("Local hand tracking didn't become ready. Camera turned off."); }, 20_000);
    const interpreter = new GestureInterpreter();
    const stop = () => {
      if (closed) return; closed = true;
      window.clearTimeout(timer); stream?.getTracks().forEach(track => track.stop()); video.pause(); video.srcObject = null;
      window.clearTimeout(startupTimeout);
      worker.terminate(); setPointer(null);
    };
    const fail = (reason: string) => { stop(); setState("Off"); disable.current(reason); };
    const frame = async () => {
      if (closed) return;
      if (inFlight && performance.now()-sentAt>5000) { fail("Hand tracking stopped responding. Camera turned off."); return; }
      if (ready && !inFlight && video.readyState >= 2) {
        inFlight = true;
        try {
          const bitmap = await createImageBitmap(video, { resizeWidth: 640, resizeHeight: 480, resizeQuality: "low" });
          if (closed) { bitmap.close(); return; }
          sentAt = performance.now(); worker.postMessage({ type: "frame", frame: bitmap, at: sentAt }, [bitmap]);
        } catch { inFlight = false; fail("The camera frame couldn't be processed."); return; }
      }
      timer = window.setTimeout(() => void frame(), 80);
    };
    worker.onmessage = event => {
      if (closed) return;
      if (event.data.type === "ready") { ready = true; setState("Hands only · local"); }
      else if (event.data.type === "error") fail("Local hand tracking couldn't start. Check camera permission and the bundled model.");
      else if (event.data.type === "landmarks") {
        inFlight = false;
        const points = event.data.points as Point[] | null;
        const pose = points ? classifyHand(points) : null;
        setPointer(pose ? { x: pose.x, y: pose.y } : null);
        for (const action of interpreter.update(pose, event.data.at)) command.current(action);
      }
    };
    worker.onerror = () => fail("Local hand tracking worker stopped.");
    setState("Starting local camera…");
    void (async () => {
      try {
        const selected = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15, max: 20 } }, audio: false });
        if (closed) { selected.getTracks().forEach(track => track.stop()); return; }
        stream = selected; video.srcObject = stream; await video.play();
        worker.postMessage({ type: "init" }); void frame();
      } catch { fail("Camera access wasn't granted or a camera isn't available."); }
    })();
    const visibility = () => { if (document.hidden) { stop(); disable.current("Hand controls paused when the app became hidden. Enable them again when ready."); } };
    document.addEventListener("visibilitychange", visibility);
    return () => { stop(); document.removeEventListener("visibilitychange", visibility); };
  }, [enabled]);
  if (!enabled) return null;
  return <><div className="hand-control-status" role="status"><span/>Camera on · {state}<button type="button" onClick={() => disable.current()}>Turn off</button></div>
    {pointer && <span className="hand-control-pointer" aria-hidden="true" style={{ left: `${pointer.x * 100}%`, top: `${pointer.y * 100}%` }}/>}</>;
}
