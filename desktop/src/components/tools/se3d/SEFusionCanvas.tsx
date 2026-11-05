import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import type { BrainId } from "../seActivity";
import type { ConstellationFeed } from "./constellation";
import { createFusionModel, FUSION_BRAINS } from "./fusionModel";
import "./SEFusionCanvas.css";
import { HAND_MODEL_EVENT, type VisualHandMotion } from "../../../core/handTargets";

type Pick = BrainId | "conductor" | "gate";
type Props = { feed: ConstellationFeed; onSelect?: (id: BrainId | "conductor") => void; onFallback?: () => void };
const ORDER: BrainId[] = ["talk", "seek", "study", "keep"];
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

/** Real mesh geometry. This view only consumes the existing roster; it never loads models or grants actions. */
export function SEFusionCanvas({ feed, onSelect, onFallback }: Props) {
  const stage = useRef<HTMLDivElement>(null);
  const labels = useRef<Partial<Record<BrainId, HTMLButtonElement | null>>>({});
  const leaders = useRef<Partial<Record<BrainId, SVGLineElement | null>>>({});
  const actions = useRef<{ reset(): void; zoom(amount: number): void } | null>(null);
  const latest = useRef({ feed, onSelect });
  latest.current = { feed, onSelect };
  const [failed, setFailed] = useState(false);
  const [hover, setHover] = useState<Pick | null>(null);
  const [words, setWords] = useState<Record<string, string>>({});

  useEffect(() => {
    const host = stage.current;
    if (!host) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    } catch { setFailed(true); return; }
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.setClearColor(0x04070d, 0);
    renderer.domElement.className = "se-fusion__canvas";
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.setAttribute("aria-label", "ZÆNIA's three-dimensional fusion model. Four model clusters connect to the Conductor, with a separate execution gate. Drag to rotate, use arrow keys to turn, plus or minus to zoom, or Home to reset.");
    renderer.domElement.tabIndex = 0;
    host.prepend(renderer.domElement);

    let model: ReturnType<typeof createFusionModel>;
    try { model = createFusionModel(); }
    catch {
      renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
      setFailed(true); return;
    }
    const scene = new THREE.Scene();
    scene.add(model.root);
    let environment: THREE.WebGLRenderTarget | undefined;
    let room: RoomEnvironment | undefined, generator: THREE.PMREMGenerator | undefined;
    try {
      room = new RoomEnvironment();
      generator = new THREE.PMREMGenerator(renderer);
      environment = generator.fromScene(room, 0.04, 0.1, 100, { size: 128 });
      scene.environment = environment.texture;
    } catch {
      // Environment reflections are optional; ordinary lights still render the model.
      environment?.dispose(); environment = undefined;
    } finally { room?.dispose(); generator?.dispose(); }
    scene.environmentIntensity = 0.55;
    scene.add(new THREE.HemisphereLight(0xffecd4, 0x172840, 1.1));
    const key = new THREE.DirectionalLight(0xffe6c0, 2.7);
    key.position.set(-3, 6, 7); scene.add(key);
    const rim = new THREE.DirectionalLight(0x8bbfe8, 2.2);
    rim.position.set(5, 1, -4); scene.add(rim);
    const fill = new THREE.PointLight(0xffa64a, 4.5, 14);
    fill.position.set(0, 1, 3); scene.add(fill);
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    const bounds = new THREE.Box3().setFromObject(model.root);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const point = new THREE.Vector3();
    const ray = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const app = host.closest(".zaenia-app");
    let visible = true, lost = false, disposed = false, frame = 0, lastFrame = 0, elapsed = 0;
    let zoom = 1, width = 1, height = 1;
    let drag: { id: number; x: number; y: number; startX: number; startY: number; moved: boolean } | null = null;
    let lastWords = "";

    const canDraw = () => !disposed && !lost && visible && !document.hidden;
    const canMove = () => canDraw() && !media.matches && app?.getAttribute("data-motion") !== "reduced" && !app?.classList.contains("zaenia-app--background");
    const fit = () => {
      width = Math.max(1, host.clientWidth); height = Math.max(1, host.clientHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5, 1400 / width));
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      const tangent = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      const distance = Math.max(size.y / (2 * tangent), size.x / (2 * tangent * camera.aspect)) * 1.08 + size.z * 0.40;
      camera.position.set(center.x, center.y + 0.25, center.z + distance / zoom);
      camera.lookAt(center); camera.updateProjectionMatrix();
    };
    const draw = (moving = false) => {
      if (!canDraw()) return;
      const signals = latest.current.feed.signals();
      const levels: Partial<Record<BrainId, number>> = {};
      ORDER.forEach((id, index) => {
        const signal = signals[index];
        levels[id] = signal?.installed && Number.isFinite(signal.level) ? clamp(signal.level, 0, 1) : 0;
      });
      model.update(elapsed, levels, moving);
      renderer.render(scene, camera);
      for (const spec of FUSION_BRAINS) {
        const label = labels.current[spec.id];
        if (!label) continue;
        model.clusters[spec.id].getWorldPosition(point); point.project(camera);
        const x = (point.x + 1) * width / 2, y = (1 - point.y) * height / 2;
        const labelWidth = width < 640 ? 112 : 140;
        const left = point.x < 0 ? 12 : width - labelWidth - 12;
        const top = clamp(y - 24, 12, Math.max(12, height - 60));
        label.style.width = `${labelWidth}px`;
        label.style.left = `${left}px`;
        label.style.top = `${top}px`;
        label.style.setProperty("--brain-color", spec.color);
        const leader = leaders.current[spec.id];
        if (leader) {
          leader.setAttribute("x1", String(x)); leader.setAttribute("y1", String(y));
          leader.setAttribute("x2", String(point.x < 0 ? left + labelWidth : left)); leader.setAttribute("y2", String(top + 24));
        }
      }
    };
    const refreshWords = () => {
      if (!canDraw()) return;
      const next = Object.fromEntries(ORDER.map(id => [id, latest.current.feed.text(id).state]));
      const key = JSON.stringify(next);
      if (key !== lastWords) { lastWords = key; setWords(next); }
      if (!canMove()) draw();
    };
    const loop = (now: number) => {
      frame = 0;
      if (!canMove()) return;
      if (!lastFrame || now - lastFrame >= 1000 / 30) {
        elapsed += lastFrame ? Math.min((now - lastFrame) / 1000, 0.1) : 0;
        lastFrame = now; draw(true);
      }
      frame = requestAnimationFrame(loop);
    };
    const sync = () => {
      cancelAnimationFrame(frame); frame = 0; lastFrame = 0;
      if (canDraw()) { draw(); refreshWords(); }
      if (canMove()) frame = requestAnimationFrame(loop);
    };
    const reset = () => { model.root.rotation.set(0.08, -0.12, 0); zoom = 1; fit(); draw(); };
    const zoomBy = (amount: number) => { zoom = clamp(zoom + amount, 0.7, 1.6); fit(); draw(); };
    actions.current = { reset, zoom: zoomBy };
    const pick = (event: PointerEvent): Pick | null => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
      ray.setFromCamera(pointer, camera);
      for (const hit of ray.intersectObjects(model.pickables, true)) {
        let object: THREE.Object3D | null = hit.object;
        while (object && object !== scene) {
          const id = object.userData.pick as Pick | undefined;
          if (id && ([...ORDER, "conductor", "gate"] as string[]).includes(id)) return id;
          object = object.parent;
        }
      }
      return null;
    };
    const down = (event: PointerEvent) => {
      if (event.button !== 0) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY, moved: false };
      renderer.domElement.setPointerCapture(event.pointerId);
    };
    const move = (event: PointerEvent) => {
      if (drag?.id === event.pointerId) {
        const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
        if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) > 4) drag.moved = true;
        model.root.rotation.y += dx * 0.007;
        if (event.pointerType !== "touch") model.root.rotation.x = clamp(model.root.rotation.x + dy * 0.005, -0.65, 0.65);
        drag.x = event.clientX; drag.y = event.clientY; draw();
      } else setHover(pick(event));
    };
    const up = (event: PointerEvent) => {
      if (drag?.id !== event.pointerId) return;
      if (!drag.moved) {
        const id = pick(event); setHover(id);
        if (id && id !== "gate") latest.current.onSelect?.(id);
      }
      if (renderer.domElement.hasPointerCapture(event.pointerId)) renderer.domElement.releasePointerCapture(event.pointerId);
      drag = null;
    };
    const cancel = () => { drag = null; };
    const leave = () => { if (!drag) setHover(null); };
    const keyboard = (event: KeyboardEvent) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "=", "-", "Home"].includes(event.key)) return;
      event.preventDefault();
      if (event.key === "Home") reset();
      else if (event.key === "+" || event.key === "=") zoomBy(0.1);
      else if (event.key === "-") zoomBy(-0.1);
      else {
        if (event.key === "ArrowLeft") model.root.rotation.y -= 0.12;
        if (event.key === "ArrowRight") model.root.rotation.y += 0.12;
        if (event.key === "ArrowUp") model.root.rotation.x = clamp(model.root.rotation.x - 0.1, -0.65, 0.65);
        if (event.key === "ArrowDown") model.root.rotation.x = clamp(model.root.rotation.x + 0.1, -0.65, 0.65);
        draw();
      }
    };
    const contextLost = (event: Event) => { event.preventDefault(); lost = true; sync(); setFailed(true); };
    const handMotion = (event: Event) => {
      if (!canDraw() || document.hidden || app?.classList.contains("zaenia-app--background")) return;
      const motion = (event as CustomEvent<VisualHandMotion>).detail;
      if (!motion || motion.kind !== "change" || ![motion.dx, motion.dy, motion.scale, motion.angle].every(Number.isFinite)) return;
      model.root.rotation.y += clamp(motion.dx, -.15, .15) * 5;
      model.root.rotation.x = clamp(model.root.rotation.x + clamp(motion.dy, -.15, .15) * 4, -.65, .65);
      model.root.rotation.z = clamp(model.root.rotation.z + clamp(motion.angle, -.2, .2), -Math.PI, Math.PI);
      zoom = clamp(zoom * clamp(motion.scale, .8, 1.25), .7, 1.6); fit(); draw();
    };
    const resize = new ResizeObserver(() => { fit(); draw(); }); resize.observe(host);
    const intersection = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? true; sync(); }); intersection.observe(host);
    const mutation = new MutationObserver(sync);
    if (app) mutation.observe(app, { attributes: true, attributeFilter: ["class", "data-motion"] });
    document.addEventListener("visibilitychange", sync); media.addEventListener("change", sync);
    const canvas = renderer.domElement;
    canvas.addEventListener("pointerdown", down); canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up); canvas.addEventListener("pointercancel", cancel);
    canvas.addEventListener("pointerleave", leave); canvas.addEventListener("keydown", keyboard);
    canvas.addEventListener("webglcontextlost", contextLost);
    host.addEventListener(HAND_MODEL_EVENT, handMotion);
    const timer = window.setInterval(refreshWords, 1000);
    reset(); sync();
    return () => {
      disposed = true; actions.current = null; cancelAnimationFrame(frame); window.clearInterval(timer);
      resize.disconnect(); intersection.disconnect(); mutation.disconnect();
      document.removeEventListener("visibilitychange", sync); media.removeEventListener("change", sync);
      canvas.removeEventListener("pointerdown", down); canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", up); canvas.removeEventListener("pointercancel", cancel);
      canvas.removeEventListener("pointerleave", leave); canvas.removeEventListener("keydown", keyboard);
      canvas.removeEventListener("webglcontextlost", contextLost);
      host.removeEventListener(HAND_MODEL_EVENT, handMotion);
      model.dispose(); environment?.dispose(); renderer.dispose(); renderer.forceContextLoss(); canvas.remove();
    };
  }, []);

  const tip = hover === "gate" ? { title: "Execution gate", note: "A visual reminder of Core's permission boundary. This model cannot approve or perform an action." }
    : hover === "conductor" ? feed.hubTip() : hover ? feed.tip(hover) : null;
  return <div className="se-fusion">
    <div ref={stage} className="se-fusion__stage" data-testid="se-fusion-stage" data-hand-model="">
      {!failed && <svg className="se-fusion__leaders" aria-hidden="true">{FUSION_BRAINS.map(spec => <line key={spec.id} ref={element => { leaders.current[spec.id] = element; }} stroke={spec.color}/>)}</svg>}
      {!failed && FUSION_BRAINS.map(spec => {
        const text = feed.text(spec.id);
        return <button key={spec.id} ref={element => { labels.current[spec.id] = element; }} className="se-fusion__label" type="button"
          onClick={() => { setHover(spec.id); onSelect?.(spec.id); }} onFocus={() => setHover(spec.id)}>
          <b>{text.name || spec.name}</b><span>{text.model || spec.model}</span><small>{words[spec.id] || text.state}</small>
        </button>;
      })}
      {failed && <div className="se-fusion__fallback" role="status"><p>3D rendering is unavailable on this device. The model details remain available beside the picture.</p>
        {onFallback && <button type="button" onClick={onFallback}>Use lightweight view</button>}</div>}
    </div>
    {!failed && <div className="se-fusion__compact-labels" aria-label="SE model clusters">{FUSION_BRAINS.map(spec => {
      const text = feed.text(spec.id);
      return <button key={spec.id} type="button" style={{ borderLeftColor: spec.color }} onClick={() => { setHover(spec.id); onSelect?.(spec.id); }}>
        <b>{text.name || spec.name}</b><span>{text.model || spec.model}</span><small>{words[spec.id] || text.state}</small>
      </button>;
    })}</div>}
    {tip && !failed && <div className="se-fusion__tip" role="status"><b>{tip.title}</b><span>{tip.note}</span></div>}
    {!failed && <div className="se-fusion__controls"><span>Drag to turn · arrow keys also work</span><div>
      <button type="button" aria-label="Zoom out of the SE model" onClick={() => actions.current?.zoom(-0.1)}>−</button>
      <button type="button" aria-label="Zoom into the SE model" onClick={() => actions.current?.zoom(0.1)}>+</button>
      <button type="button" onClick={() => actions.current?.reset()}>Reset view</button>
    </div></div>}
  </div>;
}
