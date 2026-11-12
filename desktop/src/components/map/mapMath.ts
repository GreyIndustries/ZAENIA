// Web Mercator and small formatting helpers for LIFE > Map & traffic.
export const TILE = 256;
export type LatLon = { lat: number; lon: number };

export const world = (z: number) => TILE * 2 ** z;
export function project(lat: number, lon: number, z: number) {
  const sin = Math.sin(Math.min(85.05112878, Math.max(-85.05112878, lat)) * Math.PI / 180);
  return { x: (lon + 180) / 360 * world(z), y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * world(z) };
}
export function unproject(x: number, y: number, z: number): LatLon {
  const n = Math.PI - 2 * Math.PI * y / world(z);
  return { lat: 180 / Math.PI * Math.atan(Math.sinh(n)), lon: x / world(z) * 360 - 180 };
}
export function km(a: LatLon, b: LatLon) {
  const r = Math.PI / 180, dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}
export const ago = (iso: string | null | undefined) => {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};
export const road = (name: string) => {
  const n = name.replace(/^0+/, "");
  return /^\d+$/.test(n) ? (["5", "90", "82", "182", "205", "405", "705"].includes(n) ? `I-${n}` : `SR ${n}`) : name;
};
export const miles = (kilometres: number) => `${(kilometres * 0.621371).toFixed(kilometres < 16 ? 1 : 0)} mi`;
export const duration = (seconds: number) => {
  const minutes = Math.max(1, Math.round(seconds / 60));
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60 ? `${minutes % 60} min` : ""}`.trim();
};
export const clock = (date: Date) => date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
export const capital = (text: string) => text ? text[0].toUpperCase() + text.slice(1) : text;
/** Point-to-segment distance at city scale; sparse routes still match incidents between vertices. */
export function kmToLine(point: LatLon, line: number[][]) {
  if (!line.length) return Infinity;
  if (line.length === 1) return km(point, { lat: line[0][0], lon: line[0][1] });
  const wrap = (degrees: number) => ((degrees + 540) % 360) - 180;
  let best = Infinity;
  for (let i = 1; i < line.length; i++) {
    const [aLat, aLon] = line[i - 1], [bLat, bLon] = line[i];
    const scale = Math.max(0.00001, Math.cos((aLat + bLat) * Math.PI / 360));
    const x = wrap(bLon - aLon) * scale, y = bLat - aLat;
    const px = wrap(point.lon - aLon) * scale, py = point.lat - aLat;
    const length = x * x + y * y;
    const t = length ? Math.max(0, Math.min(1, (px * x + py * y) / length)) : 0;
    best = Math.min(best, km(point, { lat: aLat + t * y, lon: wrap(aLon + t * wrap(bLon - aLon)) }));
  }
  return best;
}
