import { km } from "./mapMath";
export type Fix = { lat: number; lon: number; accuracy: number; timestamp: number };
export type Progress = { along: number; fraction: number; offset: number; point: number[]; timestamp: number; arrived: boolean };
export type RouteIndex = { line: number[][]; cumulative: number[]; total: number };
export function indexRoute(line: number[][]): RouteIndex {
  const cumulative = [0];
  for (let i = 1; i < line.length; i++) cumulative.push(cumulative[i - 1] + km({lat: line[i-1][0], lon: line[i-1][1]}, {lat: line[i][0], lon: line[i][1]}) * 1000);
  return { line, cumulative, total: cumulative[cumulative.length - 1] ?? 0 };
}
const wrap = (n: number) => ((n + 540) % 360) - 180;
export function measureProgress(index: RouteIndex, fix: Fix, previous: Progress | null, now = Date.now()): { progress: Progress | null; status: string } {
  if (![fix.lat, fix.lon, fix.accuracy, fix.timestamp].every(Number.isFinite) || Math.abs(fix.lat) > 90 || Math.abs(fix.lon) > 180 || fix.accuracy < 0) return { progress: previous, status: "Invalid GPS reading" };
  if (now - fix.timestamp > 15000 || fix.timestamp > now + 5000 || (previous && fix.timestamp <= previous.timestamp)) return {progress: previous, status: "Waiting for a fresh GPS reading"};
  if (fix.accuracy > 80) return {progress: previous, status: "GPS accuracy is low; progress paused"};
  if (index.total < 1) return {progress: null, status: "Route is too short to track"};
  let best: { along: number; offset: number; point: number[] } | null = null;
  const allowance = previous ? (fix.timestamp - previous.timestamp) / 1000 * 65 + 100 : Infinity;
  for (let i = 1; i < index.line.length; i++) {
    const a = index.line[i-1], b = index.line[i], scale = Math.cos(fix.lat * Math.PI / 180);
    const x = wrap(b[1]-a[1])*scale, y = b[0]-a[0], px = wrap(fix.lon-a[1])*scale, py = fix.lat-a[0];
    const t = Math.max(0,Math.min(1,(px*x+py*y)/(x*x+y*y || 1)));
    const point = [a[0]+t*y, wrap(a[1]+t*wrap(b[1]-a[1]))];
    const along = index.cumulative[i-1]+t*(index.cumulative[i]-index.cumulative[i-1]);
    if (previous && (along < previous.along - 100 || along > previous.along + allowance)) continue;
    const offset = km(fix,{lat:point[0],lon:point[1]})*1000;
    if (!best || offset < best.offset - .5 || (Math.abs(offset-best.offset)<.5 && along<best.along)) best={along,offset,point};
  }
  if (!best || best.offset > Math.max(60,fix.accuracy*1.5)) return {progress: previous,status:"Off route or GPS jump; progress paused. Review your route."};
  const along = Math.max(previous?.along ?? 0, best.along);
  const end=index.line[index.line.length-1];
  const arrived=along/index.total >= .98 && km(fix,{lat:end[0],lon:end[1]})*1000 <= Math.max(30,fix.accuracy);
  return {progress:{along,fraction:arrived?1:Math.min(.999,along/index.total),offset:best.offset,point:previous && best.along<previous.along?previous.point:best.point,timestamp:fix.timestamp,arrived},status:arrived?"Destination reached":"Tracking your trip"};
}
export function completedLine(index: RouteIndex, progress: Progress | null): number[][] {
  if (!progress) return [];
  let i=0;while(i<index.cumulative.length && index.cumulative[i]<=progress.along)i++;
  return [...index.line.slice(0,i),progress.point];
}
