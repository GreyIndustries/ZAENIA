import { km, kmToLine } from "./mapMath";

export type TrafficStroke = { line: number[][]; level: number | null };
export const ROUTE_COLORS: Record<number, string> = { 1: "#4285f4", 2: "#f59a23", 3: "#e8352e", 4: "#b71c1c" };
type RoadSegment = { from: string; to: string; line: number[][] };
type Reading = { id: string; level: number };

/** Nearby parallel WSDOT road geometry is an approximation, never lane-level traffic. */
export function routeTraffic(line: number[][], segments: RoadSegment[], flows: Reading[], fresh: boolean): TrafficStroke[] {
  if (!fresh || !segments.length) return [{ line, level: null }];
  const levels = new Map(flows.map(flow => [flow.id, flow.level]));
  const cells = new Map<string, { a: number[]; b: number[]; level: number }[]>();
  const cell = (lat: number, lon: number) => `${Math.floor(lat * 100)},${Math.floor(lon * 100)}`;
  for (const segment of segments) {
    const readings = [levels.get(segment.from), levels.get(segment.to)].filter((x): x is number => x !== undefined && x >= 1 && x <= 4);
    if (!readings.length) continue;
    for (let i = 1; i < segment.line.length; i++) {
      const a = segment.line[i - 1], b = segment.line[i];
      const length = km({ lat: a[0], lon: a[1] }, { lat: b[0], lon: b[1] });
      if (length > 10) continue; // do not infer across large unobserved gaps
      const road = { a, b, level: Math.max(...readings) };
      for (let n = 0, count = Math.max(1, Math.ceil(length / .3)); n <= count; n++) {
        const key = cell(a[0] + (b[0] - a[0]) * n / count, a[1] + (b[1] - a[1]) * n / count);
        const bucket = cells.get(key) ?? [];
        if (bucket[bucket.length - 1] !== road) bucket.push(road);
        cells.set(key, bucket);
      }
    }
  }
  const result: TrafficStroke[] = [];
  for (let i = 1; i < line.length; i++) {
    const a = line[i - 1], b = line[i], mid = { lat: (a[0] + b[0]) / 2, lon: (a[1] + b[1]) / 2 };
    const x = Math.floor(mid.lat * 100), y = Math.floor(mid.lon * 100);
    let closest = .07, level: number | null = null;
    const scale = Math.cos(mid.lat * Math.PI / 180), dx = (b[1] - a[1]) * scale, dy = b[0] - a[0];
    for (let ox = -1; ox <= 1; ox++) for (let oy = -1; oy <= 1; oy++) {
      for (const road of cells.get(`${x + ox},${y + oy}`) ?? []) {
        const rx = (road.b[1] - road.a[1]) * scale, ry = road.b[0] - road.a[0];
        const parallel = Math.abs(dx * rx + dy * ry) / (Math.hypot(dx, dy) * Math.hypot(rx, ry));
        if (!(parallel > .8)) continue;
        const distance = Math.max(...[a, b].map(p => kmToLine({ lat: p[0], lon: p[1] }, [road.a, road.b])));
        if (distance < closest) { closest = distance; level = road.level; }
      }
    }
    const last = result[result.length - 1];
    if (last && last.level === level) last.line.push(b);
    else result.push({ line: [a, b], level });
  }
  return result;
}
