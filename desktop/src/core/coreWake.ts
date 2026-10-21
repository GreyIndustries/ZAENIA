export function wakeLevel(progress: number, start: number, duration: number) {
  const t = Math.min(1, Math.max(0, (progress - start) / duration));
  return t * t * (3 - 2 * t);
}
// The nucleus wakes first, then six subsystem junctions light in order.
// Percentages refer to the existing seven-second startup clock.
export function nodeWakeLevel(progress: number, index: number) {
  return wakeLevel(progress, 14 + index * 14, 14);
}
