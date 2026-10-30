/**
 * Food barcodes (EAN-13, UPC-A, EAN-8, UPC-E) read from camera frames or photos, on the device.
 * iPhone Safari has no BarcodeDetector, so ZAE carries her own reader: sample rows and columns of the picture,
 * turn each into bar/space widths, match the digit patterns and keep only codes whose check digit is right.
 * Where the browser has BarcodeDetector (Android Chrome), it is tried first.
 */
export type Gray = { width: number; height: number; data: Uint8ClampedArray | Uint8Array };

// Widths (in modules) of each digit's four runs, left-hand odd parity (L). G = reversed; R = same as L, starting with a bar.
const L_RUNS = [[3, 2, 1, 1], [2, 2, 2, 1], [2, 1, 2, 2], [1, 4, 1, 1], [1, 1, 3, 2], [1, 2, 3, 1], [1, 1, 1, 4], [1, 3, 1, 2], [1, 2, 1, 3], [3, 1, 1, 2]];
const EAN13_FIRST = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"];
const UPCE_PARITY = ["GGGLLL", "GGLGLL", "GGLLGL", "GGLLLG", "GLGGLL", "GLLGGL", "GLLLGG", "GLGLGL", "GLGLLG", "GLLGLG"]; // number system 0

export function checkDigitOk(code: string): boolean {
  if (!/^\d{8}$|^\d{12,13}$/.test(code)) return false;
  const digits = code.split("").map(Number);
  const check = digits.pop()!;
  const sum = digits.reverse().reduce((total, d, i) => total + d * (i % 2 === 0 ? 3 : 1), 0);
  return (10 - (sum % 10)) % 10 === check;
}

export function expandUpcE(six: string, system: number, check: number): string {
  const [a, b, c, d, e, last] = six.split("");
  const body = last <= "2" ? `${a}${b}${last}0000${c}${d}${e}` : last === "3" ? `${a}${b}${c}00000${d}${e}`
    : last === "4" ? `${a}${b}${c}${d}00000${e}` : `${a}${b}${c}${d}${e}0000${last}`;
  return `${system}${body}${check}`;
}

/** Best digit for four run widths, and whether it matched the reversed (G) pattern. */
function matchDigit(runs: number[], allowG: boolean): { digit: number; g: boolean; error: number } {
  const total = runs[0] + runs[1] + runs[2] + runs[3];
  const scaled = runs.map(r => r * 7 / total);
  let best = { digit: -1, g: false, error: Infinity };
  for (let digit = 0; digit < 10; digit++) {
    for (const g of allowG ? [false, true] : [false]) {
      const pattern = g ? [...L_RUNS[digit]].reverse() : L_RUNS[digit];
      const error = scaled.reduce((sum, value, i) => sum + Math.abs(value - pattern[i]), 0);
      if (error < best.error) best = { digit, g, error };
    }
  }
  return best;
}

function guardOk(runs: number[], start: number, count: number, module: number): boolean {
  for (let i = start; i < start + count; i++) if (runs[i] < module * 0.45 || runs[i] > module * 1.8) return false;
  return true;
}

/** Try to read a code from run widths starting at a bar run (index i), left to right. */
function decodeAt(runs: number[], i: number): string | null {
  const quiet = runs[i - 1] ?? Infinity;
  const module = (runs[i] + runs[i + 1] + runs[i + 2]) / 3;
  if (quiet < module * 3 || !guardOk(runs, i, 3, module)) return null;
  const MAX = 1.6; // total pattern error allowed per digit

  // EAN-13 / UPC-A: 3 + 24 + 5 + 24 + 3 runs
  if (i + 59 <= runs.length && guardOk(runs, i + 27, 5, module) && guardOk(runs, i + 56, 3, module)) {
    const left = [], right = [];
    let parity = "";
    for (let k = 0; k < 6; k++) { const m = matchDigit(runs.slice(i + 3 + k * 4, i + 7 + k * 4), true); if (m.error > MAX) { left.length = 0; break; } left.push(m.digit); parity += m.g ? "G" : "L"; }
    if (left.length === 6) {
      for (let k = 0; k < 6; k++) { const m = matchDigit(runs.slice(i + 32 + k * 4, i + 36 + k * 4), false); if (m.error > MAX) { right.length = 0; break; } right.push(m.digit); }
      const first = EAN13_FIRST.indexOf(parity);
      if (right.length === 6 && first >= 0) { const code = `${first}${left.join("")}${right.join("")}`; if (checkDigitOk(code)) return code; }
    }
  }
  // EAN-8: 3 + 16 + 5 + 16 + 3 runs
  if (i + 43 <= runs.length && guardOk(runs, i + 19, 5, module) && guardOk(runs, i + 40, 3, module)) {
    const digits: number[] = [];
    for (let k = 0; k < 8; k++) { const start = k < 4 ? i + 3 + k * 4 : i + 24 + (k - 4) * 4; const m = matchDigit(runs.slice(start, start + 4), false); if (m.error > MAX) break; digits.push(m.digit); }
    if (digits.length === 8) { const code = digits.join(""); if (checkDigitOk(code)) return code; }
  }
  // UPC-E: 3 + 24 + 6 runs, parity gives the number system and check digit; returned as the full 12-digit UPC-A
  if (i + 33 <= runs.length && guardOk(runs, i + 27, 6, module) && (runs[i + 33] ?? Infinity) >= module * 3) {
    const digits: number[] = [];
    let parity = "";
    for (let k = 0; k < 6; k++) { const m = matchDigit(runs.slice(i + 3 + k * 4, i + 7 + k * 4), true); if (m.error > MAX) break; digits.push(m.digit); parity += m.g ? "G" : "L"; }
    if (digits.length === 6) {
      for (const system of [0, 1]) {
        const table = system === 0 ? UPCE_PARITY : UPCE_PARITY.map(p => p.replace(/[LG]/g, c => c === "L" ? "G" : "L"));
        const check = table.indexOf(parity);
        if (check >= 0) { const code = expandUpcE(digits.join(""), system, check); if (checkDigitOk(code)) return code; }
      }
    }
  }
  return null;
}

/** Bar/space widths along one line of brightness values, split at a threshold. Starts with a space run. */
export function runsOf(line: number[], threshold: number): number[] {
  const runs: number[] = [];
  let dark = false, length = 0;
  for (const value of line) {
    const isDark = value < threshold;
    if (isDark === dark) length++;
    else { runs.push(length); length = 1; dark = isDark; }
  }
  runs.push(length);
  return runs;
}

/** Read a code from one line of brightness values (either direction). */
export function decodeLine(line: number[]): string | null {
  let min = 255, max = 0;
  for (const v of line) { if (v < min) min = v; if (v > max) max = v; }
  if (max - min < 40) return null;
  for (const split of [0.5, 0.42, 0.58]) {
    for (const values of [line, [...line].reverse()]) {
      const runs = runsOf(values, min + (max - min) * split);
      for (let i = 1; i < runs.length - 30; i += 2) { const code = decodeAt(runs, i); if (code) return code; }
    }
  }
  return null;
}

/** Brightness (0–255) from RGBA image data. */
export function toGray(image: { width: number; height: number; data: Uint8ClampedArray }): Gray {
  const out = new Uint8Array(image.width * image.height);
  for (let p = 0, q = 0; p < out.length; p++, q += 4) out[p] = (image.data[q] * 299 + image.data[q + 1] * 587 + image.data[q + 2] * 114) / 1000;
  return { width: image.width, height: image.height, data: out };
}

/** Scan rows (and columns, for a barcode held sideways) across the middle of the picture. A code must be read twice to count. */
export function decodeGray(image: Gray, lines = 24): string | null {
  const seen = new Map<string, number>();
  const note = (code: string | null) => { if (!code) return null; const n = (seen.get(code) ?? 0) + 1; seen.set(code, n); return n >= 2 ? code : null; };
  const { width, height, data } = image;
  for (let k = 0; k < lines; k++) {
    const y = Math.round(height * (0.2 + 0.6 * (k + 0.5) / lines));
    const row = Array.from(data.subarray(y * width, (y + 1) * width));
    const found = note(decodeLine(row));
    if (found) return found;
  }
  for (let k = 0; k < lines; k++) {
    const x = Math.round(width * (0.2 + 0.6 * (k + 0.5) / lines));
    const column: number[] = [];
    for (let y = 0; y < height; y++) column.push(data[y * width + x]);
    const found = note(decodeLine(column));
    if (found) return found;
  }
  // A single clean read is still accepted when nothing disagrees with it.
  return seen.size === 1 ? [...seen.keys()][0] : null;
}

type Detector = { detect(source: CanvasImageSource): Promise<{ rawValue: string }[]> };
let detector: Detector | null | undefined;
function nativeDetector(): Detector | null {
  if (detector !== undefined) return detector;
  const Native = (globalThis as { BarcodeDetector?: new (options: { formats: string[] }) => Detector }).BarcodeDetector;
  try { detector = Native ? new Native({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] }) : null; } catch { detector = null; }
  return detector;
}

/** Read a barcode from a canvas: the browser's own detector when it has one, otherwise ZAE's reader. */
export async function readCanvas(canvas: HTMLCanvasElement): Promise<string | null> {
  const native = nativeDetector();
  if (native) {
    try { const found = await native.detect(canvas); const code = found.map(item => item.rawValue.replace(/\D/g, "")).find(value => value.length >= 8); if (code) return code; } catch { /* fall back */ }
  }
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  return decodeGray(toGray(context.getImageData(0, 0, canvas.width, canvas.height)));
}

/** Read a barcode from a photo file, trying a few sizes. */
export async function readPhoto(file: File): Promise<string | null> {
  const bitmap = await createImageBitmap(file);
  try {
    for (const target of [1000, 1600, 700]) {
      const scale = Math.min(1, target / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale);
      canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      const code = await readCanvas(canvas);
      if (code) return code;
    }
    return null;
  } finally { bitmap.close(); }
}
