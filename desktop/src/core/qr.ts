import jsQR from "jsqr";

/** Reads a QR code from a camera frame (Phone confirms at the PC). jsQR runs on the phone; nothing is sent anywhere. */
export async function readQr(canvas: HTMLCanvasElement): Promise<string | null> {
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context || !canvas.width || !canvas.height) return null;
  const image = context.getImageData(0, 0, canvas.width, canvas.height);
  return jsQR(image.data, image.width, image.height, { inversionAttempts: "attemptBoth" })?.data ?? null;
}
