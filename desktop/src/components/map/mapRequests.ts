import type { LatLon } from "./mapMath";

export type MapStop = { key: number; label: string; query: string; lat: number | null; lon: number | null };
export type MapStep = LatLon & { text: string; distance: number; duration: number };
export type MapRoute = {
  distance: number; duration: number; line: number[][]; alternatives?: MapRoute[];
  legs: { distance: number; duration: number; steps: MapStep[] }[];
  order: number[]; engine: "local" | "online"; optimized?: boolean; optimizationNote?: string | null;
};

export function validPlace(lat: unknown, lon: unknown): boolean {
  return typeof lat === "number" && Number.isFinite(lat) && Math.abs(lat) <= 90
    && typeof lon === "number" && Number.isFinite(lon) && Math.abs(lon) <= 180;
}

export function completeStops(stops: MapStop[]): boolean {
  return stops.length >= 2 && stops.length <= 12 && stops.every(stop => validPlace(stop.lat, stop.lon));
}

export function stopFingerprint(stops: MapStop[], bestOrder: boolean): string {
  return JSON.stringify([bestOrder, stops.map(stop => [stop.key, stop.query, stop.lat, stop.lon])]);
}

/** Tickets are invalidated synchronously, before React commits an edited stop. */
export class RequestGate {
  private version = 0;
  issue(key: string) { return { version: ++this.version, key }; }
  invalidate() { ++this.version; }
  isCurrent(ticket: { version: number }) { return this.version === ticket.version; }
  accepts(ticket: { version: number; key: string }, key: string) {
    return this.isCurrent(ticket) && ticket.key === key;
  }
}

export function checkedRoute(value: MapRoute, stopCount: number): MapRoute {
  const nonnegative = (number: unknown) => typeof number === "number" && Number.isFinite(number) && number >= 0;
  if (!value || !nonnegative(value.distance) || !nonnegative(value.duration)
    || !Array.isArray(value.line) || value.line.length < 2 || value.line.length > 150_000
    || !value.line.every(point => Array.isArray(point) && validPlace(point[0], point[1]))
    || !Array.isArray(value.order) || value.order.length !== stopCount || new Set(value.order).size !== stopCount
    || value.order.some(index => !Number.isInteger(index) || index < 0 || index >= stopCount)
    || value.order[0] !== 0 || value.order[value.order.length - 1] !== stopCount - 1
    || !Array.isArray(value.legs) || value.legs.length !== stopCount - 1
    || value.legs.some(leg => !nonnegative(leg.distance) || !nonnegative(leg.duration) || !Array.isArray(leg.steps)
      || leg.steps.some(step => typeof step.text !== "string" || !validPlace(step.lat, step.lon)
        || !nonnegative(step.distance) || !nonnegative(step.duration)))
    || !["local", "online"].includes(value.engine)) {
    throw new Error("The routing service returned an incomplete route. Please try again.");
  }
  return value;
}
