/**
 * Finger-snap detection (Grey, 2026-11-05) from two numbers per audio frame: bright (2.5 to 9 kHz) and low (0.1 to 1.5 kHz)
 * energy. A snap is a short, sharp burst that is mostly bright and far above the room's background, then falls away at
 * once; speech and music are low-heavy and rise and fall slowly. One snap and two snaps close together are different
 * events. Pure logic: no microphone, no DOM. Audio is never stored or sent anywhere.
 */
export type SnapEvent = "single" | "double";

export class SnapDetector {
  static BURST = 6;        // times the background in the bright band
  static FLOOR = 0.002;    // never fire below this absolute bright energy (a silent room has a tiny background)
  static BRIGHT = 0.9;     // bright share of the frame's energy: bright / (bright + low)
  static REFRACTORY = 130; // ms, one burst can't count twice
  static DOUBLE_MIN = 140; static DOUBLE_MAX = 650;
  private background = 0.0005;
  private prev: { bright: number; low: number; at: number } | null = null;
  private before = 0;   // the bright energy of the frame before prev
  private first = -Infinity;
  private last = -Infinity;

  reset() { this.prev = null; this.before = 0; this.first = -Infinity; this.last = -Infinity; }

  /** Feed one frame; returns an event once it is settled (a single snap is only reported after the double-snap window). */
  update(bright: number, low: number, at: number): SnapEvent | null {
    if (!Number.isFinite(bright) || !Number.isFinite(low) || !Number.isFinite(at) || bright < 0 || low < 0) return null;
    let event: SnapEvent | null = null;
    const p = this.prev;
    this.prev = { bright, low, at };
    const before = this.before; this.before = p ? p.bright : 0;
    if (p) {
      const burst = p.bright > Math.max(SnapDetector.FLOOR, this.background * SnapDetector.BURST);
      const sharp = bright < p.bright * 0.5 && before < p.bright * 0.5;       // it rose from quiet and is gone again by the next frame
      const bright_ = p.bright / (p.bright + p.low + 1e-12) >= SnapDetector.BRIGHT;
      if (burst && sharp && bright_ && p.at - this.last >= SnapDetector.REFRACTORY) {
        this.last = p.at;
        if (this.first > -Infinity && p.at - this.first >= SnapDetector.DOUBLE_MIN && p.at - this.first <= SnapDetector.DOUBLE_MAX) { this.first = -Infinity; event = "double"; }
        else this.first = p.at;
      }
    }
    // the background follows quiet frames only, so a loud sound can't teach it to ignore snaps
    if (bright < this.background * 3 + SnapDetector.FLOOR) this.background += (bright - this.background) * 0.02;
    if (event === null && this.first > -Infinity && at - this.first > SnapDetector.DOUBLE_MAX) { this.first = -Infinity; event = "single"; }
    return event;
  }
}
