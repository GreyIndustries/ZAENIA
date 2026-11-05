import { useEffect, useRef, useState } from "react";
import { ACTION_LABEL, BONES, GestureActions } from "../../core/gestureActions";
import type { GestureAction } from "../../core/gestureActions";
import { DEFAULT_HAND_SETTINGS, HandMotionController, normalizeHandSettings, type HandDetection, type HandFrame, type HandSettings } from "../../core/handGestures";
import { HAND_ACTIVITY_EVENT, HandTargetSession, type VisualHandMotion } from "../../core/handTargets";
import "./HandControls.css";

const SETTINGS_KEY = "zaenia.handControls";
const EMPTY: HandFrame = { cursor: null, target: null, phase: "idle", progress: 0, motion: null, stop: false };
const readSettings = () => { try { return normalizeHandSettings(JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "null")); } catch { return normalizeHandSettings(null); } };
type Calibration = { step: "upper-left" | "lower-right"; began: number; samples: { x: number; y: number }[]; first?: { x: number; y: number } };

/** Camera frames stay in RAM. Only explicit presentation targets can be grabbed. */
export function HandControls({ enabled, suspended = false, speaking, onDisable, onAction, onWindowMotion }: {
  enabled: boolean; suspended?: boolean; speaking: boolean; onDisable: (reason?: string) => void;
  onAction: (action: GestureAction) => string | void; onWindowMotion: (id: string, motion: VisualHandMotion) => boolean;
}) {
  const latest = useRef({ onDisable, onAction, onWindowMotion, speaking }); latest.current = { onDisable, onAction, onWindowMotion, speaking };
  const [settings, setSettings] = useState<HandSettings>(readSettings);
  const settingsRef = useRef(settings); settingsRef.current = settings;
  const [camera, setCamera] = useState("");
  const [cameras, setCameras] = useState<MediaDeviceInfo[]>([]);
  const [mode, setMode] = useState<"move" | "shortcuts">("move");
  const modeRef = useRef(mode); modeRef.current = mode;
  const [state, setState] = useState("Off"), [frame, setFrame] = useState<HandFrame>(EMPTY), [target, setTarget] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null), [configOpen, setConfigOpen] = useState(false), [calibrating, setCalibrating] = useState(false);
  const calibration = useRef<Calibration | null>(null);
  const previewRef = useRef<HTMLDivElement>(null), skeletonRef = useRef<HTMLCanvasElement>(null), cursorRef = useRef<HTMLDivElement>(null);
  useEffect(() => { try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch { /* Optional preferences only. */ } }, [settings]);
  useEffect(() => { if (enabled && suspended) latest.current.onDisable("Hand controls paused. Enable them again when the dashboard is available."); }, [enabled, suspended]);
  useEffect(() => {
    if (!enabled || suspended) { setFrame(EMPTY); setTarget(null); setState("Off"); return; }
    let closed = false, ready = false, inFlight = false, timer = 0, sentAt = 0, lastVideoTime = -1, lastReply = -Infinity, lastActive = 0;
    let stream: MediaStream | null = null, activeSettings = settingsRef.current, activeMode = modeRef.current;
    let engine = new HandMotionController(activeSettings);
    const shortcuts = new GestureActions();
    const session = new HandTargetSession((id, motion) => latest.current.onWindowMotion(id, motion), action => runAction(action));
    const video = document.createElement("video"); video.muted = true; video.playsInline = true; video.className = "air-hud__video";
    let worker: Worker;
    const cancel = () => { session.clear(); engine.reset(); shortcuts.reset(); setFrame(EMPTY); setTarget(null); if (cursorRef.current) cursorRef.current.hidden = true; };
    try { worker = new Worker(`${import.meta.env.BASE_URL}handtracking/worker.js`); }
    catch { latest.current.onDisable("This browser couldn't start local hand tracking."); return; }
    const startupTimeout = window.setTimeout(() => { if (!ready) fail("Local hand tracking didn't become ready. Camera turned off."); }, 20_000);
    const stop = () => {
      if (closed) return; closed = true; cancel(); calibration.current = null; setCalibrating(false);
      window.clearTimeout(timer); window.clearTimeout(startupTimeout);
      stream?.getTracks().forEach(track => track.stop()); video.pause(); video.srcObject = null; video.remove(); worker.terminate();
    };
    const fail = (reason: string) => { if (closed) return; stop(); setState("Off"); latest.current.onDisable(reason); };
    function runAction(action: GestureAction) { const said = latest.current.onAction(action); setNotice(said || ACTION_LABEL[action.kind]); window.dispatchEvent(new Event(HAND_ACTIVITY_EVENT)); }
    const capture = async () => {
      if (closed) return;
      if (inFlight && performance.now() - sentAt > 500) cancel();
      if (inFlight && performance.now() - sentAt > 5000) { fail("Hand tracking stopped responding. Camera turned off."); return; }
      if (ready && !inFlight && video.readyState >= 2 && video.currentTime !== lastVideoTime) {
        inFlight = true; sentAt = performance.now(); lastVideoTime = video.currentTime;
        try {
          const ratio = Math.min(640 / video.videoWidth, 480 / video.videoHeight);
          const bitmap = await createImageBitmap(video, { resizeWidth: Math.max(1, Math.round(video.videoWidth * ratio)), resizeHeight: Math.max(1, Math.round(video.videoHeight * ratio)), resizeQuality: "low" });
          if (closed) { bitmap.close(); return; }
          worker.postMessage({ type: "frame", frame: bitmap, at: sentAt }, [bitmap]);
        } catch { inFlight = false; fail("The camera frame couldn't be processed."); return; }
      }
      timer = window.setTimeout(() => void capture(), 40);
    };
    const draw = (hands: HandDetection[]) => {
      const canvas = skeletonRef.current, ctx = canvas?.getContext("2d"); if (!canvas || !ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const ratio = video.videoWidth / video.videoHeight || 4 / 3, w = Math.min(canvas.width, canvas.height * ratio), h = w / ratio;
      const ox = (canvas.width - w) / 2, oy = (canvas.height - h) / 2;
      hands.forEach((hand, index) => {
        const points = hand.points; if (points.length !== 21 || points.some(p => !Number.isFinite(p.x) || !Number.isFinite(p.y))) return;
        const at = (i: number) => [ox + (1 - points[i].x) * w, oy + points[i].y * h];
        ctx.strokeStyle = index ? "#6de6ce" : "#ffcf81"; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = 2; ctx.beginPath();
        for (const [a, b] of BONES) { const [ax, ay] = at(a), [bx, by] = at(b); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); } ctx.stroke();
        points.forEach((_, i) => { const [x, y] = at(i); ctx.beginPath(); ctx.arc(x, y, 2, 0, Math.PI * 2); ctx.fill(); });
      });
    };
    const calibrate = (hands: HandDetection[], at: number): boolean => {
      const step = calibration.current; if (!step) return false;
      cancel();
      const hand = hands.find(item => activeSettings.hand === "auto" || item.handedness === activeSettings.hand), p = hand?.points[8];
      if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) { step.began = at; step.samples = []; setNotice(`Calibration: show your pointing hand at the ${step.step} of your comfortable reach.`); return true; }
      if (at - step.began < 1500) { setNotice(`Calibration: point to the ${step.step} of your comfortable reach, then hold still.`); return true; }
      step.samples.push({ x: 1 - p.x, y: p.y });
      if (at - step.began < 3000 || step.samples.length < 15) return true;
      const xs = step.samples.map(p => p.x), ys = step.samples.map(p => p.y);
      if (Math.max(...xs) - Math.min(...xs) > .09 || Math.max(...ys) - Math.min(...ys) > .09) { step.began = at; step.samples = []; setNotice("Hold your pointing finger steady to set this corner."); return true; }
      const corner = { x: xs.reduce((a, b) => a + b) / xs.length, y: ys.reduce((a, b) => a + b) / ys.length };
      if (step.step === "upper-left") { calibration.current = { step: "lower-right", began: at, samples: [], first: corner }; return true; }
      calibration.current = null; setCalibrating(false);
      if (!step.first || corner.x - step.first.x < .25 || corner.y - step.first.y < .25) { setNotice("Reach area was too small or the corners were reversed. Try calibration again."); return true; }
      setSettings(normalizeHandSettings({ ...settingsRef.current, range: { left: step.first.x, right: corner.x, top: step.first.y, bottom: corner.y } }));
      setNotice("Comfortable reach saved. Point at a title bar or the SE model, then pinch."); return true;
    };
    worker.onmessage = event => {
      if (closed) return;
      if (event.data.type === "ready") { ready = true; window.clearTimeout(startupTimeout); setState("Local · up to two hands"); }
      else if (event.data.type === "error") fail("Local hand tracking couldn't start. Check camera permission and the bundled model.");
      else if (event.data.type === "landmarks") {
        inFlight = false; const at = event.data.at;
        if (!Number.isFinite(at) || at <= lastReply || performance.now() - at > 500) { cancel(); return; } lastReply = at;
        if (settingsRef.current !== activeSettings || modeRef.current !== activeMode) { cancel(); activeSettings = settingsRef.current; activeMode = modeRef.current; engine = new HandMotionController(activeSettings); }
        const hands = (Array.isArray(event.data.hands) ? event.data.hands : []).filter((h: HandDetection) => h && Array.isArray(h.points)).slice(0, 2) as HandDetection[];
        draw(hands); if (calibrate(hands, at)) return;
        const out = engine.update(hands, at, activeMode === "move" ? session.resolve : () => null);
        if (!session.consume(out)) { cancel(); return; }
        if (activeMode === "shortcuts") { const result = shortcuts.update(hands.length === 1 ? hands[0].points : null, at, latest.current.speaking); if (result.action) runAction(result.action); }
        else if (out.stop) runAction({ kind: "stop" });
        if (out.cursor && out.target && at - lastActive > 750) { window.dispatchEvent(new Event(HAND_ACTIVITY_EVENT)); lastActive = at; }
        if (cursorRef.current) { cursorRef.current.hidden = !out.cursor || activeMode !== "move"; if (out.cursor) { cursorRef.current.style.left = `${out.cursor.x * 100}%`; cursorRef.current.style.top = `${out.cursor.y * 100}%`; cursorRef.current.dataset.phase = out.phase; } }
        setFrame(out); setTarget(session.name);
      }
    };
    worker.onerror = () => fail("Local hand tracking worker stopped.");
    setState("Starting the camera…"); setNotice("Point at a window title bar or the SE model, pause, then pinch to grab.");
    const listCameras = () => void navigator.mediaDevices.enumerateDevices().then(devices => { if (!closed) setCameras(devices.filter(device => device.kind === "videoinput")); }).catch(() => undefined);
    void (async () => {
      try {
        const selected = await navigator.mediaDevices.getUserMedia({ video: { ...(camera ? { deviceId: { exact: camera } } : {}), width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30, max: 30 } }, audio: false });
        if (closed) { selected.getTracks().forEach(track => track.stop()); return; }
        stream = selected; selected.getVideoTracks().forEach(track => track.addEventListener("ended", () => { if (!closed) fail("The selected camera disconnected. Enable hand controls and choose another camera."); }));
        video.srcObject = selected; await video.play(); if (closed) return;
        previewRef.current?.prepend(video); listCameras(); worker.postMessage({ type: "init" }); void capture();
      } catch { if (closed) return; if (camera) setCamera(""); fail(camera ? "The selected camera isn't available. Enable hand controls again to use the default camera." : "Camera access wasn't granted or a camera isn't available."); }
    })();
    const hidden = () => { if (document.hidden) fail("Hand controls paused when the app became hidden. Enable them again when ready."); };
    const blurred = () => fail("Hand controls paused when the app lost focus. Enable them again when ready.");
    document.addEventListener("visibilitychange", hidden); window.addEventListener("blur", blurred); window.addEventListener("resize", cancel);
    navigator.mediaDevices.addEventListener("devicechange", listCameras);
    return () => { stop(); document.removeEventListener("visibilitychange", hidden); window.removeEventListener("blur", blurred); window.removeEventListener("resize", cancel); navigator.mediaDevices.removeEventListener("devicechange", listCameras); };
  }, [enabled, suspended, camera]);
  if (!enabled || suspended) return null;
  const updateSettings = (patch: Partial<HandSettings>) => setSettings(normalizeHandSettings({ ...settings, ...patch }));
  return <>
    <div ref={cursorRef} className="hand-cursor" hidden aria-hidden="true"><span/></div>
    <aside className="air-hud" aria-label="Hand controls">
      <div className="air-hud__preview" ref={previewRef} data-hand-blocked><canvas ref={skeletonRef} width={192} height={144} aria-hidden="true"/></div>
      <div className="air-hud__info"><b>{calibrating ? "Calibrating reach" : frame.phase === "two-hand" ? "Two-hand control" : frame.phase === "grab" ? "Holding" : frame.phase === "arming" ? "Grabbing…" : target ? "Ready to grab" : "Point to target"}</b>
        <small>Camera on · {state}</small><span>{target ?? "Title bar or SE model"}</span>{frame.phase === "arming" && <progress aria-label="Grab progress" value={frame.progress} max={1}/>}
        <div className="air-hud__actions"><button type="button" aria-expanded={configOpen} onClick={() => setConfigOpen(open => !open)}>Adjust</button><button type="button" onClick={() => latest.current.onDisable()}>Turn off</button></div>
      </div>
      <p className="air-hud__note" role="status">{notice}</p>
      <div className="air-hud__palette" aria-label="Hand action menu">{([['previous','Previous'],['next','Next'],['home','Home'],['minimize','Minimize'],['close','Close']] as const).map(([kind, name]) => <button key={kind} data-hand-action={kind} type="button" onClick={() => latest.current.onAction({ kind })}>{name}</button>)}</div>
      {configOpen && <div className="air-hud__settings" data-hand-blocked>
        <label>Camera<select value={camera} onChange={event => setCamera(event.target.value)}><option value="">Default camera</option>{cameras.map((device, i) => <option key={device.deviceId} value={device.deviceId}>{device.label || `Camera ${i + 1}`}</option>)}</select></label>
        <label>Control mode<select value={mode} onChange={event => setMode(event.target.value as typeof mode)}><option value="move">Grab and manipulate</option><option value="shortcuts">Shortcut gestures</option></select></label>
        <label>Pointing hand<select value={settings.hand} onChange={event => updateSettings({ hand: event.target.value as HandSettings["hand"] })}><option value="auto">Automatic</option><option value="Right">Right hand</option><option value="Left">Left hand</option></select></label>
        <label>Sensitivity <output>{settings.sensitivity.toFixed(1)}×</output><input type="range" min="0.4" max="2" step="0.1" value={settings.sensitivity} onChange={event => updateSettings({ sensitivity: Number(event.target.value) })}/></label>
        <div className="air-hud__actions"><button type="button" disabled={calibrating} onClick={() => { calibration.current = { step: "upper-left", began: performance.now(), samples: [] }; setCalibrating(true); setNotice("Point to the upper-left of your comfortable reach and hold still."); }}>Calibrate reach</button>
          <button type="button" onClick={() => { calibration.current = null; setCalibrating(false); updateSettings({ range: { ...DEFAULT_HAND_SETTINGS.range } }); setNotice("Default reach restored."); }}>Reset reach</button></div>
      </div>}
      <p className="air-hud__help">{mode === "move" ? "Point, pause, pinch. Move one hand to drag or turn. Pinch both hands to resize; turn them to rotate the model. Release to let go. Open palm stops speech." : "One hand: hold 1–4 fingers for Plan/Health/Know/Create; rock sign for System; fist for Calm; peace sign for mic; thumbs up/down for supported cards. Open palm stops speech. Pinch never closes a tab."}</p>
    </aside>
  </>;
}
