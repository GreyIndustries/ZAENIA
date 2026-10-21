import { useEffect, useRef } from "react";
import orbitSprite from "../assets/image_403ddf_orbits.png";

/** Source photograph: image_403e20.jpg, in native image pixels. */
const BACKGROUND = { width: 1672, height: 941 } as const;

/**
 * Registration in BACKGROUND image coordinates, not viewport coordinates.
 * The atomic-image light traces stay aligned with the photographed planet
 * even when the window is resized or cropped by object-fit: cover.
 *
 * To adjust the effect later, change these four values only.
 */
const ORBIT = {
  x: 325,
  y: 40,
  width: 1020,
  height: 680,
} as const;

const MAX_DPR = 2;

export function OrbitOverlay() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d", { alpha: true });
    if (!context) return;

    const sprite = new Image();
    sprite.decoding = "async";
    let disposed = false;
    let loaded = false;

    const draw = () => {
      if (disposed || !loaded) return;

      const bounds = canvas.getBoundingClientRect();
      const width = bounds.width;
      const height = bounds.height;
      if (width <= 0 || height <= 0) return;

      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      const pixelWidth = Math.round(width * dpr);
      const pixelHeight = Math.round(height * dpr);
      if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
      if (canvas.height !== pixelHeight) canvas.height = pixelHeight;

      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);

      // Match the photograph's object-fit: cover behavior exactly.
      const scale = Math.max(
        width / BACKGROUND.width,
        height / BACKGROUND.height,
      );
      const offsetX = (width - BACKGROUND.width * scale) / 2;
      const offsetY = (height - BACKGROUND.height * scale) / 2;

      const x = offsetX + ORBIT.x * scale;
      const y = offsetY + ORBIT.y * scale;
      const w = ORBIT.width * scale;
      const h = ORBIT.height * scale;

      // A separate soft light pass makes thin original rings feel luminous.
      context.save();
      context.globalAlpha = 0.34;
      context.filter = `blur(${Math.max(2, 5 * scale)}px)`;
      context.drawImage(sprite, x, y, w, h);
      context.restore();

      // Crisp orbit lines: transparency comes from extracted original pixels.
      context.save();
      context.globalAlpha = 0.91;
      context.drawImage(sprite, x, y, w, h);
      context.restore();
    };

    const onLoad = () => {
      loaded = true;
      draw();
    };

    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    window.addEventListener("resize", draw);
    sprite.addEventListener("load", onLoad);
    sprite.src = orbitSprite;

    if (sprite.complete && sprite.naturalWidth > 0) onLoad();

    return () => {
      disposed = true;
      observer.disconnect();
      window.removeEventListener("resize", draw);
      sprite.removeEventListener("load", onLoad);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="zaenia-home__atomic-orbits"
      aria-hidden="true"
    />
  );
}
