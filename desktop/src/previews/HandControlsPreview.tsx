import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AppWindow, type ShellWindow } from "../components/shell/WindowShell";
import { HandControls } from "../components/shell/HandControls";
import { SEFusionCanvas } from "../components/tools/se3d/SEFusionCanvas";
import type { ConstellationFeed } from "../components/tools/se3d/constellation";
import { FUSION_BRAINS } from "../components/tools/se3d/fusionModel";
import { DEFAULT_HAND_SETTINGS, HandMotionController, type HandDetection } from "../core/handGestures";
import { HandTargetSession, type VisualHandMotion } from "../core/handTargets";
import { handWindowRect } from "../core/windowLayout";
import "./HandControlsPreview.css";

/** Synthetic geometry/landmarks only. Core, owner data and inference providers are never accessed. */
function syntheticHand(x: number, y: number, pinch: boolean, side = "Right"): HandDetection {
  const range = DEFAULT_HAND_SETTINGS.range;
  const wx = 1 - (range.left + x * (range.right - range.left)) + .0525, wy = range.top + y * (range.bottom - range.top) + .3;
  const p = Array.from({ length: 21 }, () => ({ x: wx, y: wy })); p[0] = { x: wx, y: wy };
  [5, 9, 13, 17].forEach((base, finger) => {
    const bx = wx + (finger - 1.5) * .035, by = wy - .16;
    p[base] = { x: bx, y: by }; p[base + 1] = { x: bx, y: by - .035 };
    p[base + 2] = { x: bx, y: finger === 0 ? by - .08 : by + .01 }; p[base + 3] = { x: bx, y: finger === 0 ? by - .14 : by + .045 };
  });
  p[1] = { x: wx - .05, y: wy - .02 }; p[2] = { x: wx - .09, y: wy - .06 }; p[3] = { x: wx - .13, y: wy - .12 };
  p[4] = pinch ? { x: p[8].x - .013, y: p[8].y } : { x: wx - .21, y: wy - .15 };
  return { points: p, handedness: side, score: .98 };
}
function Preview() {
  const stage = useRef<HTMLDivElement>(null), pending = useRef<(() => void) | null>(null);
  const [win, setWin] = useState<ShellWindow>({ id: "practice", x: .08, y: .04, w: .82, h: .91, z: 1, minimized: false });
  const current = useRef(win); current.current = win;
  const [enabled, setEnabled] = useState(false), [running, setRunning] = useState(false), [status, setStatus] = useState("Ready · no camera in use");
  const [workerStatus, setWorkerStatus] = useState("Not checked"), workerRef = useRef<Worker | null>(null);
  const feed = useMemo<ConstellationFeed>(() => ({
    signals: () => FUSION_BRAINS.map(() => ({ installed: true, level: .35 })),
    text: id => { const brain = FUSION_BRAINS.find(item => item.id === id)!; return { name: brain.name, model: brain.model, job: id, state: "Sample: resting" }; },
    tip: id => ({ key: id, title: id, color: "#ffce83", lines: [], note: "Synthetic practice model" }),
    hubTip: () => ({ key: "conductor", title: "Conductor", color: "#fff0cb", lines: [], note: "Synthetic practice model" }),
  }), []);
  const moveWindow = (_id: string, motion: VisualHandMotion) => {
    const box = stage.current?.getBoundingClientRect(); if (!box) return false;
    if (motion.kind === "change") { const rect = handWindowRect(current.current, motion, { width: window.innerWidth, height: window.innerHeight }, box); current.current = { ...current.current, ...rect }; setWin(current.current); }
    return true;
  };
  useEffect(() => () => { pending.current?.(); workerRef.current?.terminate(); }, []);
  function replay(model: boolean) {
    pending.current?.(); setEnabled(false);
    const element = document.querySelector(model ? "[data-hand-model]" : ".os-window__bar");
    const rect = element?.getBoundingClientRect(); if (!rect) return;
    const x = (rect.x + rect.width * .5) / window.innerWidth, y = (rect.y + rect.height * .5) / window.innerHeight;
    const engine = new HandMotionController(), session = new HandTargetSession(moveWindow, () => undefined);
    let i = 0, begins = 0, changes = 0, pairs = 0;
    setRunning(true); setStatus("Replaying synthetic hands…");
    const timer = window.setInterval(() => {
      const pinched = i >= 8 && i < 67;
      const offset = i < 16 ? 0 : Math.min(1, (i - 16) / 20);
      let hands = [syntheticHand(x + offset * .055, y + offset * .018, pinched)];
      if (i >= 39 && i < 64) {
        const spread = Math.max(0, i - 44) * .002;
        hands = [syntheticHand(x + .055 - spread, y + .018, true), syntheticHand(x + .20 + spread, y + .018 + Math.max(0, i - 51) * .002, true, "Left")];
        if (i % 2) hands.reverse();
      }
      const frame = engine.update(hands, performance.now(), session.resolve); session.consume(frame);
      begins += Number(frame.motion?.kind === "begin"); changes += Number(frame.motion?.kind === "change"); pairs += Number(frame.phase === "two-hand");
      if (++i >= 76) { window.clearInterval(timer); session.clear(); pending.current = null; setRunning(false); setStatus(`${model ? "Model" : "Window"} replay complete · ${begins} grab · ${changes} movement frames · ${pairs} two-hand frames · released`); }
    }, 40);
    pending.current = () => { window.clearInterval(timer); session.clear(); setRunning(false); };
  }
  async function checkWorker() {
    workerRef.current?.terminate(); setWorkerStatus("Loading bundled tracker…");
    const worker = new Worker(`${import.meta.env.BASE_URL}handtracking/worker.js`); workerRef.current = worker;
    const timeout = window.setTimeout(() => finish("Tracker timed out"), 20_000);
    function finish(message: string) { window.clearTimeout(timeout); worker.terminate(); workerRef.current = null; setWorkerStatus(message); }
    worker.onerror = () => finish("Tracker failed to load");
    worker.onmessage = async event => {
      if (event.data.type === "error") finish("Tracker returned an error");
      else if (event.data.type === "ready") {
        const canvas = new OffscreenCanvas(640, 480); canvas.getContext("2d")?.fillRect(0, 0, 640, 480);
        const frame = await createImageBitmap(canvas); worker.postMessage({ type: "frame", frame, at: performance.now() }, [frame]);
      } else if (event.data.type === "landmarks") finish(Array.isArray(event.data.hands) && event.data.hands.length === 0 ? "Local worker passed · blank frame · no camera used" : "Unexpected blank-frame result");
    };
    worker.postMessage({ type: "init" });
  }
  return <main className="hands-preview zaenia-app" data-motion="reduced">
    <header><small>ZÆNIA · LOCAL HAND CONTROLS</small><h1>Point. Grab. Move.</h1><p>Practice with the same gesture engine, window controls and 3D model used in ZAE. Demonstrations use synthetic hands.</p></header>
    <nav><button disabled={running || enabled} onClick={() => replay(false)}>Demonstrate window control</button><button disabled={running || enabled} onClick={() => replay(true)}>Demonstrate model control</button><button disabled={running} onClick={() => { pending.current?.(); setWin({ id: "practice", x: .08, y: .04, w: .82, h: .91, z: 1, minimized: false }); }}>Reset window</button>
      <button disabled={running} onClick={() => setEnabled(value => !value)}>{enabled ? "Disable camera practice" : "Enable camera practice"}</button><button onClick={() => void checkWorker()}>Check local tracker</button></nav>
    <p role="status">{status}</p><p role="status">{workerStatus}</p>
    <div className="hands-preview__stage" ref={stage}><AppWindow win={win} title="SE practice window" label="POINT AT THIS TITLE BAR" active stage={() => stage.current?.getBoundingClientRect() ?? null} onFocus={() => undefined} onClose={() => setStatus("Close selected in practice")} onMinimize={() => setStatus("Minimize selected in practice")} onChange={rect => setWin(before => ({ ...before, ...rect }))}><SEFusionCanvas feed={feed}/></AppWindow></div>
    <p className="hands-preview__instructions">Highlight a title bar or model, then pinch. Hold a second pinch to resize and turn. Release to let go. Tracking loss releases immediately. Camera practice is optional and stays on this PC.</p>
    <HandControls enabled={enabled} speaking={false} onDisable={reason => { setEnabled(false); setStatus(reason || "Camera practice off"); }} onAction={action => { setStatus(`Practice action: ${action.kind}`); }} onWindowMotion={moveWindow}/>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Preview/>);
