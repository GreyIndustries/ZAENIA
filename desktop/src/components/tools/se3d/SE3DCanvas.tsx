import { useEffect, useRef, useState } from "react";
import { clamp, mountStage, type Scene, type Tip } from "./engine";
import "./SE3D.css";

/**
 * One 3D SE picture: a canvas that a scene draws on, with hover details. Drag turns it. The details are also in text
 * beside every use of it, so the picture never holds anything that can only be seen.
 */
export function SE3DCanvas({ scene, label, hint, wide = false }: { scene: Scene; label: string; hint?: string; wide?: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const shown = useRef("");
  const [tip, setTip] = useState<Tip | null>(null);

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    return mountStage(element, scene.draw, (hit, bounds) => {
      const key = hit ? hit.tip.key : "";
      if (key !== shown.current) { shown.current = key; setTip(hit ? hit.tip : null); }
      const popup = box.current;
      if (hit && popup) {
        popup.style.left = `${clamp(hit.x + 16, 4, Math.max(4, bounds.w - popup.offsetWidth - 4))}px`;
        popup.style.top = `${Math.max(4, Math.min(hit.y - 10, bounds.h - popup.offsetHeight - 4))}px`;
      }
    }, scene.options);
  }, [scene]);

  return <div className={`se3d${wide ? " se3d--wide" : ""}`}>
    <div className="se3d__stage">
      <canvas ref={canvas} role="img" aria-label={label}/>
      <div ref={box} className="se3d__tip" hidden={!tip}>
        {tip && <>
          <b style={{ color: tip.color }}>{tip.title}</b>{tip.sub && <> <span>{tip.sub}</span></>}
          {tip.lines.map((line, index) => <p key={index}>{line}</p>)}
          {tip.note && <em>{tip.note}</em>}
        </>}
      </div>
    </div>
    {hint && <span className="se3d__hint">{hint}</span>}
  </div>;
}
