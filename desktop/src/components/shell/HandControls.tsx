import { useEffect, useRef, useState } from "react";
import { ACTION_LABEL, BONES, GestureActions } from "../../core/gestureActions";
import type { GestureAction, HandShape, Point } from "../../core/gestureActions";
import "./HandControls.css";

const SHAPE_LABEL: Record<HandShape, string> = { one: "One finger", two: "Two fingers", peace: "Peace sign", three: "Three fingers", four: "Four fingers",
  five: "Open hand", rock: "Rock sign", fist: "Fist", thumbsUp: "Thumbs up", thumbsDown: "Thumbs down", pinch: "Pinch", other: "Hand" };

/**
 * Hand gestures for actions (Grey, 2026-10-31). Local MediaPipe hand landmarks only; camera frames stay in memory
 * and are never saved or sent. The gestures are in core/gestureActions.ts; App carries out each action.
 */
export function HandControls({ enabled, speaking, onDisable, onAction }: {
  enabled: boolean; speaking: boolean; onDisable: (reason?: string) => void; onAction: (action: GestureAction) => string | void;
}) {
  const act = useRef(onAction); act.current = onAction;
  const disable = useRef(onDisable); disable.current = onDisable;
  const talking = useRef(speaking); talking.current = speaking;
  const [state, setState] = useState("Off");
  const [shape, setShape] = useState<HandShape | null>(null);
  const [holding, setHolding] = useState<{ label: string; progress: number } | null>(null);
  const [toast, setToast] = useState<{ text: string; at: number } | null>(null);
  const [help, setHelp] = useState(false);
  const previewRef = useRef<HTMLDivElement>(null);
  const skeletonRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(current => current === toast ? null : current), 1600);
    return () => window.clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    if (!enabled) { setState("Off"); setShape(null); setHolding(null); return; }
    let closed = false, ready = false, inFlight = false, timer = 0, sentAt = 0;
    let stream: MediaStream | null = null;
    const video = document.createElement("video"); video.muted = true; video.playsInline = true; video.className = "air-hud__video";
    let worker: Worker;
    try { worker = new Worker(`${import.meta.env.BASE_URL}handtracking/worker.js`); }
    catch { disable.current("This browser couldn't start local hand tracking."); return; }
    const startupTimeout = window.setTimeout(() => { if (!ready) fail("Local hand tracking didn't become ready. Camera turned off."); }, 20_000);
    const engine = new GestureActions();
    const stop = () => {
      if (closed) return; closed = true;
      window.clearTimeout(timer); stream?.getTracks().forEach(track => track.stop()); video.pause(); video.srcObject = null; video.remove();
      window.clearTimeout(startupTimeout);
      worker.terminate();
    };
    const fail = (reason: string) => { stop(); setState("Off"); disable.current(reason); };
    const frame = async () => {
      if (closed) return;
      if (inFlight && performance.now() - sentAt > 5000) { fail("Hand tracking stopped responding. Camera turned off."); return; }
      if (ready && !inFlight && video.readyState >= 2) {
        inFlight = true;
        try {
          const bitmap = await createImageBitmap(video, { resizeWidth: 640, resizeHeight: 480, resizeQuality: "low" });
          if (closed) { bitmap.close(); return; }
          sentAt = performance.now(); worker.postMessage({ type: "frame", frame: bitmap, at: sentAt }, [bitmap]);
        } catch { inFlight = false; fail("The camera frame couldn't be processed."); return; }
      }
      timer = window.setTimeout(() => void frame(), 40);
    };
    const draw = (points: Point[] | null) => {
      const canvas = skeletonRef.current; const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!points) return;
      const w = canvas.width, h = canvas.height, at = (p: Point) => [(1 - p.x) * w, p.y * h] as const;
      ctx.strokeStyle = "rgba(255,207,129,.9)"; ctx.lineWidth = 2; ctx.beginPath();
      for (const [a, b] of BONES) { const [ax, ay] = at(points[a]); const [bx, by] = at(points[b]); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); }
      ctx.stroke(); ctx.fillStyle = "rgba(255,255,255,.85)";
      for (const p of points) { const [x, y] = at(p); ctx.beginPath(); ctx.arc(x, y, 2, 0, Math.PI * 2); ctx.fill(); }
    };
    worker.onmessage = event => {
      if (closed) return;
      if (event.data.type === "ready") { ready = true; setState("Local only"); }
      else if (event.data.type === "error") fail("Local hand tracking couldn't start. Check camera permission and the bundled model.");
      else if (event.data.type === "landmarks") {
        inFlight = false;
        const points = event.data.points as Point[] | null;
        const result = engine.update(points, event.data.at, talking.current);
        draw(points);
        setShape(previous => previous === result.shape ? previous : result.shape);
        setHolding(result.holding);
        if (result.action) {
          const said = act.current(result.action);
          setToast({ text: said || ACTION_LABEL[result.action.kind], at: Date.now() });
        }
      }
    };
    worker.onerror = () => fail("Local hand tracking worker stopped.");
    setState("Starting the camera…");
    void (async () => {
      try {
        const selected = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30, max: 30 } }, audio: false });
        if (closed) { selected.getTracks().forEach(track => track.stop()); return; }
        stream = selected; video.srcObject = stream; await video.play();
        previewRef.current?.prepend(video);
        worker.postMessage({ type: "init" }); void frame();
      } catch { fail("Camera access wasn't granted or a camera isn't available."); }
    })();
    const visibility = () => { if (document.hidden) { stop(); disable.current("Hand controls paused when the app became hidden. Turn them on again when ready."); } };
    document.addEventListener("visibilitychange", visibility);
    return () => { stop(); document.removeEventListener("visibilitychange", visibility); };
  }, [enabled]);
  if (!enabled) return null;
  return <>
    {(holding || toast) && <div className={`gesture-toast${toast ? " gesture-toast--done" : ""}`} role="status" aria-live="polite">
      {toast ? <b>{toast.text}</b> : holding && <><svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="15" className="gesture-toast__track"/>
        <circle cx="18" cy="18" r="15" className="gesture-toast__fill" pathLength="100" strokeDasharray={`${Math.round(holding.progress * 100)} 100`}/></svg><b>{holding.label}</b></>}
    </div>}
    <aside className="air-hud" aria-label="Hand controls">
      <div className="air-hud__preview" ref={previewRef}><canvas ref={skeletonRef} width={192} height={144} aria-hidden="true"/></div>
      <div className="air-hud__info">
        <b>{shape ? SHAPE_LABEL[shape] : "Show your hand"}</b>
        <small>Camera on · {state}</small>
        <span className="air-hud__actions">
          <button type="button" aria-expanded={help} onClick={() => setHelp(open => !open)}>Gestures</button>
          <button type="button" onClick={() => disable.current()}>Turn off</button>
        </span>
      </div>
      {help && <ul className="air-hud__help">
        <li><b>Swipe</b> open hand left / right: previous / next tab; up: Home; down: minimise</li>
        <li><b>Hold 1–5 fingers</b>: 1 Plan · 2 Health · 3 Know · 4 Create · 5 Build</li>
        <li><b>Rock sign</b>: System</li>
        <li><b>Open palm</b> while ZAE talks: stop her</li>
        <li><b>Fist</b>, hold: Calm view</li>
        <li><b>Peace sign</b> (fingers spread): mic on / off</li>
        <li><b>Thumbs up / down</b>: confirm / dismiss ZAE's card</li>
        <li><b>Pinch</b>, hold: close the tab</li>
      </ul>}
    </aside>
  </>;
}
