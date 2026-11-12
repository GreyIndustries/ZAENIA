import { createRoot } from "react-dom/client";
import { MapPanel } from "../components/map/MapPanel";
import type { api } from "../core/bridge";
import "../styles/look-styles.css";

const start = { lat: 47.6062, lon: -122.3321 };
const finish = { lat: 47.6162, lon: -122.3121 };
const stamp = new Date().toISOString();
const fixtureWindow = window as Window & { __MAP_TEST_CALLS__?: string[]; __MAP_TEST_ROUTE_DELAY__?: number };
fixtureWindow.__MAP_TEST_CALLS__ = [];
const place = { name: "Harbor Studio", detail: "Synthetic destination for this UI test", ...finish };
const tile = (dark: boolean) => `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="${dark ? "#18252d" : "#e9e9df"}"/><path d="M0 35H256M0 125H256M0 220H256M45 0V256M160 0V256" stroke="${dark ? "#344651" : "#fff"}" stroke-width="12"/><path d="M0 125H256M160 0V256" stroke="${dark ? "#556d77" : "#d3c7aa"}" stroke-width="3"/><rect x="66" y="51" width="75" height="54" rx="7" fill="${dark ? "#233d32" : "#cbdcb7"}"/><text x="17" y="116" font-family="sans-serif" font-size="9" fill="${dark ? "#9aaab1" : "#64716b"}">Sample streets</text></svg>`;

const previewAPI: typeof api = async <T,>(method: string, raw: string, body?: unknown): Promise<T> => {
  void method;
  const url = new URL(raw, "http://preview.invalid");
  const path = url.pathname;
  fixtureWindow.__MAP_TEST_CALLS__!.push(path);
  let data: unknown = {};
  if (path === "/api/map/home") data = { ...start, zoom: 14, features: location.search.includes("oldcore") ? undefined : { autocomplete: true, alternatives: true }, place: "Sample city", saved: { tiles: 48, megabytes: 2.4, landmarkAreas: 3 } };
  else if (path.includes("/tile/")) data = { png: btoa(tile(url.searchParams.get("style") === "dark")), mime: "image/svg+xml", source: "sample" };
  else if (path === "/api/map/traffic") data = { source: "saved", updatedAt: stamp, error: null,
    flows: [{ id: "a", ...start, level: 1, road: "5", direction: "N", label: "moving", place: "Sample street" }, { id: "b", lat: 47.61, lon: -122.32, level: 3, road: "5", direction: "N", label: "heavy", place: "Sample interchange" }],
    alerts: [{ id: "incident", lat: 47.6104, lon: -122.3221, endLat: null, endLon: null, headline: "Sample roadwork report", priority: "medium", road: "5", category: "Construction", start: stamp, updated: stamp }] };
  else if (path === "/api/map/traffic/segments") data = { pending: 0, segments: [{ id: "ab", from: "a", to: "b", line: [[47.6062, -122.3321], [47.61, -122.3321], [47.61, -122.32]] }] };
  else if (path === "/api/map/landmarks") data = { landmarks: [], missing: 0, pending: 0, tooWide: false };
  else if (path === "/api/map/search") data = { places: [place] };
  else if (path === "/api/map/route") {
    if (fixtureWindow.__MAP_TEST_ROUTE_DELAY__) await new Promise(resolve => setTimeout(resolve, fixtureWindow.__MAP_TEST_ROUTE_DELAY__));
    const stops = (body as { stops: { lat: number; lon: number }[] }).stops;
    const legs = stops.slice(1).map((point, i) => ({ distance: 1400, duration: 300, steps: [
      { text: "Continue along the selected road", distance: 600, duration: 120, ...stops[i] },
      { text: "Turn right toward the next stop", distance: 800, duration: 180, ...point },
    ] }));
    data = { distance: legs.length * 1400, duration: legs.length * 300,
      line: stops.flatMap((point, i) => i ? [[stops[i - 1].lat, point.lon], [point.lat, point.lon]] : [[point.lat, point.lon]]),
      legs, order: stops.map((_, i) => i), engine: "local", optimized: false };
  } else if (path === "/api/weather/now") data = { temperature: 52, condition: "Cloudy", high: 56, low: 45, place: "Sample city" };
  else if (path === "/api/map/weather/alerts") data = { source: "saved", updatedAt: stamp, alerts: [], error: null };
  else if (path === "/api/map/radar") data = { source: "sample", frames: [], maxZoom: 7 };
  else if (path === "/api/map/aircraft") data = { source: "saved", updatedAt: stamp, tooWide: false, error: null, planes: [{ id: "sample-plane", positionAt:location.search.includes("airLegacy")?undefined:new Date(Date.now()-Number(new URLSearchParams(location.search).get("airAge")??0)*1000).toISOString(), callsign: "SAMPLE", country: "Sample", lat: 47.612, lon: -122.32, onGround: false, altitudeFt: 9000, speedKt: 230, heading: 65, climbFpm: 0, squawk: null }] };
  else if (path === "/api/map/marine") data = { source: "saved", configured: true, updatedAt: stamp, tooWide: false, error: null, ships: [{ id: "000000001", name: "SAMPLE VESSEL", lat: 47.609, lon: -122.345, speedKt: 8, heading: 135, destination: "Sample harbor", updatedAt: stamp }] };
  return data as T;
};

const previewRoot=createRoot(document.getElementById("root")!);
const renderPreview=(visible=true)=>previewRoot.render(<div className="zaenia-app" style={{ minHeight: "100vh", background: "#070d14", color: "#e5edf5", padding: "24px", fontFamily: "Segoe UI, sans-serif" }}>
  <p style={{ margin: "0 0 16px", color: "#f4b653", fontSize: 12 }}>ZÆNIA · actual Map workspace component · synthetic UI test data, not live roads or vessel positions</p>
  {visible?<MapPanel request={previewAPI} live/>:<p>Other ZAE tab (synthetic lifecycle test)</p>}
</div>);

(window as Window & {__MAP_TEST_VISIBLE__?:(visible:boolean)=>void}).__MAP_TEST_VISIBLE__=renderPreview;renderPreview();
