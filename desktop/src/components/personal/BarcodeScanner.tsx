import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { readCanvas } from "../../core/barcode";
import "./BarcodeScanner.css";

/**
 * Full-screen camera scanner for food barcodes (Fitness & Health). Uses the back camera, reads about 8 frames a second
 * inside the guide box with ZAE's own reader (so it works on iPhone), buzzes when it finds a code and closes.
 * Frames stay on the device; only the digits are sent on for the nutrition lookup.
 */
export function BarcodeScanner({ onCode, onClose, qr }: { onCode: (code: string) => void; onClose: () => void;
  /** Read a QR code (Phone confirms at the PC) instead of a food barcode: a square guide box and the QR reader. */
  qr?: (canvas: HTMLCanvasElement) => Promise<string | null> }) {
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [torch, setTorch] = useState<{ on: boolean; track: MediaStreamTrack } | null>(null);
  const [status, setStatus] = useState("Starting the camera…");
  const found = useRef(onCode);
  found.current = onCode;

  useEffect(() => {
    let stream: MediaStream | null = null;
    let stopped = false;
    let timer = 0;
    const canvas = document.createElement("canvas");
    const stop = () => { stopped = true; window.clearTimeout(timer); stream?.getTracks().forEach(track => track.stop()); };
    (async () => {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        setError("The camera needs ZAE's secure https address. Open ZAE from that address, or take a photo of the barcode instead."); return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } } });
      } catch (failure) {
        const name = (failure as { name?: string }).name;
        setError(name === "NotAllowedError" ? "Camera access was blocked. Allow the camera for ZAE in your browser settings, then try again." : "The camera couldn't start. Take a photo of the barcode instead.");
        return;
      }
      if (stopped) { stream.getTracks().forEach(track => track.stop()); return; }
      const element = video.current!;
      element.srcObject = stream;
      await element.play().catch(() => undefined);
      const track = stream.getVideoTracks()[0];
      const caps = (track.getCapabilities?.() ?? {}) as { torch?: boolean };
      if (caps.torch) setTorch({ on: false, track });
      setStatus(qr ? "Point the camera at the QR code on your PC" : "Line the barcode up inside the box");
      const scan = async () => {
        if (stopped) return;
        const width = element.videoWidth, height = element.videoHeight;
        if (width && height) {
          // The guide box: the middle 80% across and 40% down of the picture (a centred square for QR codes).
          const side = Math.min(width, height) * 0.8;
          const [sx, sy, sw, sh] = qr ? [(width - side) / 2, (height - side) / 2, side, side] : [width * 0.1, height * 0.3, width * 0.8, height * 0.4];
          const scale = Math.min(1, 900 / sw);
          canvas.width = Math.round(sw * scale); canvas.height = Math.round(sh * scale);
          canvas.getContext("2d", { willReadFrequently: true })!.drawImage(element, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
          const code = await (qr ?? readCanvas)(canvas).catch(() => null);
          if (code && !stopped) { navigator.vibrate?.(60); stop(); found.current(code); return; }
        }
        timer = window.setTimeout(() => void scan(), 120);
      };
      void scan();
    })();
    return stop;
  }, []);

  const toggleTorch = async () => {
    if (!torch) return;
    try { await torch.track.applyConstraints({ advanced: [{ torch: !torch.on } as MediaTrackConstraintSet] }); setTorch({ ...torch, on: !torch.on }); } catch { setTorch(null); }
  };

  // On top of everything (header, chat bar, tab bar), whatever panel opened it.
  return createPortal(<div className="barcode-scanner" role="dialog" aria-modal="true" aria-label={qr ? "Scan the QR code on your PC" : "Scan a food barcode"}>
    <video ref={video} playsInline muted autoPlay aria-hidden="true"/>
    <div className="barcode-scanner__shade" aria-hidden="true"><span className={`barcode-scanner__box ${qr ? "barcode-scanner__box--square" : ""}`}><i/></span></div>
    <div className="barcode-scanner__top">
      <button type="button" onClick={onClose}>Cancel</button>
      {torch && <button type="button" aria-pressed={torch.on} onClick={() => void toggleTorch()}>{torch.on ? "Light off" : "Light on"}</button>}
    </div>
    <p className="barcode-scanner__status" role="status">{error ?? status}</p>
  </div>, document.body);
}
