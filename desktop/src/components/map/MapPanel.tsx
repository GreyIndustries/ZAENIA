import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { ago, capital, clock, duration, km, kmToLine, miles, project, road, TILE, unproject, world } from "./mapMath";
import { checkedRoute, completeStops, RequestGate, stopFingerprint, validPlace } from "./mapRequests";
import type { MapRoute as Route, MapStop as Stop } from "./mapRequests";
import { routeTraffic as buildRouteTraffic, ROUTE_COLORS } from "./routeTraffic";
import { indexRoute, completedLine } from "./tripProgress";
import type { Progress } from "./tripProgress";
import { beginTrip, pauseTrip, stopTrip, setAutoReroute, subscribeTrip, tripSnapshot } from "./tripSession";
import { DetailScreen, PageNavigator } from "../shell/PageNavigator";
/** GODSPEED's five screens (Claude 2026-11-11): each is a page with Back, not a tab row. */
const MAP_PAGES = [{ id: "directions", label: "Directions" }, { id: "traffic", label: "Traffic" }, { id: "weather", label: "Weather" }, { id: "air", label: "Air" }, { id: "sea", label: "Sea" }] as const;
/** A short name for whatever was picked on the map, for its screen title. */
const pickedName = (picked: { item: unknown } | null): string => { const item = (picked?.item ?? {}) as Record<string, unknown>;
  for (const key of ["headline", "name", "callsign", "label", "event", "category", "id"]) if (typeof item[key] === "string" && (item[key] as string).trim()) return (item[key] as string).trim();
  return "Map details"; };
import { trafficEta } from "./trafficEta";
import {AircraftLayer} from "./AircraftLayer";
import type {AircraftRecord} from "./aircraftMotion";
import "./MapPanel.css";

/**
 * LIFE > Map & traffic (Grey, 2026-11-09): a clear map with live traffic, directions with several stops, weather
 * (radar and alerts), air traffic and landmarks, with as little cloud as possible. Everything comes through the ZAE
 * server (core/maps): viewed map areas, landmarks and searches are saved on the PC, directions come from the
 * GraphHopper engine on the PC when it runs. Live feeds (WSDOT traffic, NWS weather, RainViewer radar, OpenSky planes)
 * need the internet; offline the last saved reading is shown with its age. No dependency: a small map in plain React.
 */

type View = { lat: number; lon: number; z: number };
type Home = View & { features?: { autocomplete?: boolean; alternatives?: boolean }; place: string; saved: { tiles: number; megabytes: number; landmarkAreas: number } };
type Flow = { id: string; lat: number; lon: number; level: 1 | 2 | 3 | 4; label: string; road: string; direction: string; place: string };
type Alert = { id: string; lat: number; lon: number; endLat: number | null; endLon: number | null; headline: string; category: string; priority: string; road: string; start: string | null; updated: string | null };
type Traffic = { source: "live" | "saved" | "none"; updatedAt: string | null; flows: Flow[]; alerts: Alert[]; error: string | null };
type Landmark = { id: string; name: string; kind: string; lat: number; lon: number };
type Place = { name: string; detail: string; lat: number; lon: number };
type WeatherAlert = { id: string; event: string; severity: string; headline: string; instruction: string; ends: string | null; area: string; polygon: number[][] | null };
type Weather = { source: string; updatedAt: string | null; alerts: WeatherAlert[]; error: string | null };
type Now = { place: string; temperature: number | null; condition: string; high: number | null; low: number | null; feelsLike?: number | null };
type Radar = { source: string; host: string; frames: { time: number; path: string }[]; maxZoom: number };
type Plane = AircraftRecord;
type Air = { source: string; updatedAt: string | null; planes: Plane[]; tooWide: boolean; error: string | null };
type Ship = { id: string; name: string; lat: number; lon: number; speedKt: number | null; heading: number | null; destination?: string | null; updatedAt: string };
type Marine = { source: "live" | "saved" | "none"; configured: boolean; updatedAt: string | null; ships: Ship[]; tooWide: boolean; error: string | null };
type Selected = { kind: "alert"; item: Alert } | { kind: "flow"; item: Flow } | { kind: "landmark"; item: Landmark } | { kind: "plane"; item: Plane } | { kind: "weather"; item: WeatherAlert } | { kind: "ship"; item: Ship } | null;
type Tab = "traffic" | "directions" | "weather" | "air" | "sea";
type Style = "map" | "satellite" | "dark";
type Segment = { id: string; from: string; to: string; line: number[][] };

const MIN_Z = 3, MAX_Z = 18, MAX_PARALLEL = 4, TILE_MEMORY = 900, MAX_STOPS = 12;
const TRAFFIC_EVERY_MS = 3 * 60_000, AIR_EVERY_MS = 30_000, WEATHER_EVERY_MS = 5 * 60_000, NEARBY_KM = 40;
const FALLBACK_HOME: Home = { lat: 47.0343, lon: -122.8232, z: 12, place: "Lacey", saved: { tiles: 0, megabytes: 0, landmarkAreas: 0 } };
// Traffic colours as in Grey's reference pictures: green moving, orange slowing, red heavy, dark red stop-and-go.
const FLOW_COLORS = ROUTE_COLORS;
const PRIORITY_RANK: Record<string, number> = { highest: 0, high: 1, medium: 2, low: 3, lowest: 4 };
const SEVERITY_COLOR: Record<string, string> = { Extreme: "#b0185b", Severe: "#e8344e", Moderate: "#ff8a3d", Minor: "#f2b84b" };
// Each look is one or more tile layers from the ZAE server: [server style, highest zoom it has].
const STYLE_LAYERS: Record<Style, [string, number][]> = { map: [["clear", 18]], satellite: [["satellite", 16]], dark: [["dark", 18]] };
const STYLE_NAMES: Record<Style, string> = { map: "Map", satellite: "Satellite", dark: "Dark" };
const LETTERS = "ABCDEFGHIJKL";

// Tiles live for the whole app session, so reopening the tab is instant.
const tiles = new Map<string, string>();
const missing = new Map<string, number>();
const loading = new Set<string>();
const tileSubscribers = new Set<() => void>();
const remember = (key: string, value: string) => { tiles.set(key, value); if (tiles.size > TILE_MEMORY) tiles.delete(tiles.keys().next().value!); };
const stored = <T,>(key: string, fallback: T): T => { try { const value = localStorage.getItem(key); return value ? JSON.parse(value) as T : fallback; } catch { return fallback; } };
const store = (key: string, value: unknown) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* optional */ } };
let stopKey = 0;
const blankStop = (label = "", lat: number | null = null, lon: number | null = null): Stop => ({ key: ++stopKey, label, query: label, lat, lon });

export function MapPanel({ request = api, live = LIVE_API }: { request?: typeof api; live?: boolean } = {}) {
  const [home, setHome] = useState<Home>(FALLBACK_HOME);
  const [view, setView] = useState<View>({ lat: FALLBACK_HOME.lat, lon: FALLBACK_HOME.lon, z: FALLBACK_HOME.z });
  const [size, setSize] = useState({ w: 900, h: 560 });
  const [, setTileVersion] = useState(0);
  const [style, setStyle] = useState<Style>(() => { const saved = stored<string>("zaenia.map.style", "map"); return Object.prototype.hasOwnProperty.call(STYLE_LAYERS, saved) ? saved as Style : "map"; });
  const [segments, setSegments] = useState<Segment[]>([]);
  const [layers, setLayers] = useState(() => { const saved = stored("zaenia.map.layers", { traffic: true, landmarks: true, radar: false, planes: false, ships: false });
    return { traffic: saved?.traffic !== false, landmarks: saved?.landmarks !== false, radar: saved?.radar === true, planes: saved?.planes === true, ships: saved?.ships === true }; });
  const [tab, setTab] = useState<Tab>(() => { const saved = stored<string>("zaenia.map.tab", "directions"); return ["traffic", "directions", "weather", "air", "sea"].includes(saved) ? saved as Tab : "directions"; });
  const [traffic, setTraffic] = useState<Traffic | null>(null);
  const [trafficBusy, setTrafficBusy] = useState(false);
  const [landmarks, setLandmarks] = useState<Map<string, Landmark>>(() => new Map());
  const [landmarkNote, setLandmarkNote] = useState("");
  const [weather, setWeather] = useState<Weather | null>(null);
  const [now, setNow] = useState<Now | null>(null);
  const [radar, setRadar] = useState<Radar | null>(null);
  const [animateAircraft,setAnimateAircraft]=useState(()=>stored<boolean>("zaenia.map.animateAircraft",true)!==false);
  const [air, setAir] = useState<Air | null>(null);
  useEffect(()=>{if(air)setSelected(current=>{if(current?.kind!=="plane")return current;const report=air.planes.find(p=>p.id===current.item.id);return report?{kind:"plane",item:report}:current;});},[air]);
  const [marine, setMarine] = useState<Marine | null>(null);
  const [selected, setSelected] = useState<Selected>(null);
  const lastPicked = useRef<Selected>(null); if (selected) lastPicked.current = selected;
  const [error, setError] = useState("");
  const [commuteNotice,setCommuteNotice] = useState("");
  // Directions
  const [stops, setStops] = useState<Stop[]>(() => tripSnapshot().stops.length ? tripSnapshot().stops.map(p=>blankStop(p.label,p.lat,p.lon)) : [blankStop(),blankStop()]);
  const [bestOrder, setBestOrder] = useState(false);
  const [route, setRoute] = useState<Route | null>(()=>tripSnapshot().route);
  const [routeChoices, setRouteChoices] = useState<Route[]>([]);
  const [routeBusy, setRouteBusy] = useState(false);
  const [routeError, setRouteError] = useState("");
  const [picking, setPicking] = useState<number | null>(null);   // stop index waiting for a tap on the map
  const [suggest, setSuggest] = useState<{ index: number; places: Place[] } | null>(null);
  const [searchBusy, setSearchBusy] = useState<number | null>(null);
  const [searchError, setSearchError] = useState("");
  const [previewIndex, setPreviewIndex] = useState(0);
  const [activeSearch, setActiveSearch] = useState<number | null>(null);
  const [suggestIndex, setSuggestIndex] = useState(-1);
  const [recent, setRecent] = useState<Place[]>(() => { const saved = stored<unknown>("zaenia.map.recent", []); return Array.isArray(saved) ? saved.filter((p): p is Place => p && typeof p.name === "string" && validPlace(p.lat, p.lon)).slice(0, 8) : []; });
  const [tracking, setTracking] = useState(tripSnapshot().running);
  const [follow, setFollow] = useState(true);
  const [tripStatus, setTripStatus] = useState(tripSnapshot().status);
  const [sessionState,setSessionState]=useState(tripSnapshot());
  const [progress, setProgress] = useState<Progress | null>(()=>tripSnapshot().progress);
  const progressRef = useRef<Progress | null>(null);
  const [tripClock, setTripClock] = useState(Date.now());
  const [destinationWeather, setDestinationWeather] = useState<Weather | null>(null);
  const [position, setPosition] = useState<{ lat: number; lon: number; accuracy: number } | null>(null);
  const [locationState, setLocationState] = useState("");
  const locationGate = useRef(0);
  const alive = useRef(true);
  const routeGate = useRef(new RequestGate());
  const searchGate = useRef(new RequestGate());
  const stopsRef = useRef(stops); stopsRef.current = stops;
  const orderRef = useRef(bestOrder); orderRef.current = bestOrder;
  const frame = useRef<HTMLDivElement>(null);
  const drag = useRef<{ id: number; x: number; y: number; moved: boolean } | null>(null);
  const wheelAt = useRef(0);
  const wanted = useRef<string[]>([]);
  const touched = useRef(false);   // once Grey moves the map, the home reply doesn't move it back
  const invalidateRoute = () => { stopTrip(); setTracking(false); setProgress(null); progressRef.current = null; routeGate.current.invalidate(); setRoute(null); setRouteChoices([]); setRouteBusy(false); setRouteError(""); setPreviewIndex(0); };
  const changeStops = (update: (current: Stop[]) => Stop[]) => {
    searchGate.current.invalidate(); setSearchBusy(null); setSuggest(null); setSearchError(""); invalidateRoute(); setStops(update);
  };

  useEffect(() => store("zaenia.map.style", style), [style]);
  useEffect(() => store("zaenia.map.layers", layers), [layers]);
  useEffect(() => store("zaenia.map.tab", tab), [tab]);
  useEffect(()=>store("zaenia.map.animateAircraft",animateAircraft),[animateAircraft]);

  // Where the map opens and how much is saved on the PC.
  useEffect(() => {
    if (!live) return;
    request<Home & { zoom?: number }>("GET", "/api/map/home").then(reply => {
      const next = { ...FALLBACK_HOME, ...reply, z: Math.min(MAX_Z, Math.max(MIN_Z, Number(reply.zoom) || FALLBACK_HOME.z)) };
      setHome(next);
      // Home is a viewport fallback, never silently the current route origin.
      if (!touched.current) setView({ lat: next.lat, lon: next.lon, z: next.z });
    }).catch(() => { /* the fallback home still works */ });
  }, []);

  useEffect(() => {
    const element = frame.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setSize({ w: Math.max(200, entry.contentRect.width), h: Math.max(200, entry.contentRect.height) }));
    observer.observe(element);
    const stop = (event: WheelEvent) => event.preventDefault();   // React's wheel listener is passive
    element.addEventListener("wheel", stop, { passive: false });
    return () => { observer.disconnect(); element.removeEventListener("wheel", stop); };
  }, []);

  // ---- tiles: nearest to the centre first, a few at a time
  const center = project(view.lat, view.lon, view.z);
  const left = center.x - size.w / 2, top = center.y - size.h / 2, count = 2 ** view.z;
  const visible = useMemo(() => {
    const list: { x: number; y: number; wrapX: number; d: number }[] = [];
    for (let x = Math.floor(left / TILE); x <= Math.floor((left + size.w) / TILE); x++) {
      for (let y = Math.max(0, Math.floor(top / TILE)); y <= Math.min(count - 1, Math.floor((top + size.h) / TILE)); y++) {
        list.push({ x, y, wrapX: ((x % count) + count) % count, d: Math.hypot((x + 0.5) * TILE - center.x, (y + 0.5) * TILE - center.y) });
      }
    }
    return list.sort((a, b) => a.d - b.d);
  }, [left, top, size.w, size.h, count, center.x, center.y]);
  const radarFrame = radar && radar.frames.length ? radar.frames[radar.frames.length - 1] : null;
  const radarZ = Math.min(view.z, radar?.maxZoom ?? 7);

  const pump = useCallback(() => {
    if (!live) return;
    for (const key of wanted.current) {
      if (loading.size >= MAX_PARALLEL) return;
      if (tiles.has(key) || loading.has(key) || (missing.get(key) ?? 0) > Date.now()) continue;
      loading.add(key);
      const [kind, ...rest] = key.split("|");
      const path = kind === "radar" ? `/api/map/radar/tile/${rest[1]}?path=${encodeURIComponent(rest[0])}` : `/api/map/tile/${rest[0]}?style=${kind}`;
      request<{ png: string; mime?: string }>("GET", path, undefined, { timeoutMs: 25_000 })
        .then(reply => remember(key, `data:${reply.mime ?? "image/png"};base64,${reply.png}`))
        .catch(() => { missing.set(key, Date.now() + 60_000); })
        .finally(() => {
          loading.delete(key);
          if (missing.size > TILE_MEMORY) { for (const [key, expires] of missing) if (expires <= Date.now()) missing.delete(key); }
          if (missing.size > TILE_MEMORY) missing.delete(missing.keys().next().value!);
          for (const wake of tileSubscribers) wake();
        });
    }
  }, []);
  useEffect(() => {
    const wake = () => { setTileVersion(v => v + 1); pump(); };
    tileSubscribers.add(wake); pump();
    const retry = window.setInterval(() => { if (!document.hidden) wake(); }, 60_000);
    return () => { tileSubscribers.delete(wake); wanted.current = []; routeGate.current.invalidate(); searchGate.current.invalidate(); window.clearInterval(retry); };
  }, [pump]);
  useEffect(() => {
    const keysFor = (kind: string, z: number) => { const s = 2 ** (view.z - z); return [...new Set(visible.map(t => `${kind}|${z}/${Math.floor(t.wrapX / s)}/${Math.floor(t.y / s)}`))]; };
    const base = STYLE_LAYERS[style].flatMap(([kind, top]) => keysFor(kind, Math.min(view.z, top)));
    const scale = 2 ** (view.z - radarZ);
    const weatherKeys = layers.radar && radarFrame
      ? [...new Set(visible.map(t => `radar|${radarFrame.path}|${radarZ}/${Math.floor(t.wrapX / scale)}/${Math.floor(t.y / scale)}`))] : [];
    wanted.current = [...base, ...weatherKeys];
    pump();
  }, [visible, view.z, style, layers.radar, radarFrame, radarZ, pump]);

  // ---- live feeds
  const loadTraffic = useCallback((refresh = false) => {
    if (!live) return;
    setTrafficBusy(true);
    request<Traffic>("GET", `/api/map/traffic${refresh ? "?refresh=true" : ""}`, undefined, { timeoutMs: 60_000 })
      .then(reply => { setTraffic(reply); setError(""); })
      .catch(reason => setError(errorText(reason)))
      .finally(() => setTrafficBusy(false));
  }, []);
  // Road shapes for the traffic lines are worked out once on the PC; ask again while some are still being made.
  useEffect(() => {
    if (!live) return;
    let timer = 0, cancelled = false;
    const load = () => request<{ segments: Segment[]; pending: number }>("GET", "/api/map/traffic/segments", undefined, { timeoutMs: 60_000 })
      .then(reply => { if (cancelled) return; setSegments(reply.segments); if (reply.pending) timer = window.setTimeout(load, 15_000); })
      .catch(() => { if (!cancelled) timer = window.setTimeout(load, 60_000); });
    load();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, []);
  useEffect(() => {
    loadTraffic();
    const timer = window.setInterval(() => { if (!document.hidden) loadTraffic(); }, TRAFFIC_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [loadTraffic]);

  useEffect(() => {
    if (!live) return;
    const load = () => {
      request<Weather>("GET", `/api/map/weather/alerts?lat=${(position ? Math.round(position.lat*10)/10 : home.lat).toFixed(3)}&lon=${(position ? Math.round(position.lon*10)/10 : home.lon).toFixed(3)}`).then(setWeather).catch(() => { /* shown as unavailable */ });
      request<Now>("GET", "/api/weather/now", undefined, { timeoutMs: 30_000 }).then(setNow).catch(() => { /* optional */ });
      request<Radar>("GET", "/api/map/radar").then(setRadar).catch(() => { /* radar optional */ });
    };
    load();
    const timer = window.setInterval(() => { if (!document.hidden) load(); }, WEATHER_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [home.lat, home.lon, position ? Math.round(position.lat*10) : null, position ? Math.round(position.lon*10) : null]);

  const bounds = useMemo(() => {
    const nw = unproject(left, top, view.z), se = unproject(left + size.w, top + size.h, view.z);
    return { south: se.lat, west: nw.lon, north: nw.lat, east: se.lon };
  }, [left, top, size.w, size.h, view.z]);
  const area = `south=${bounds.south.toFixed(4)}&west=${bounds.west.toFixed(4)}&north=${bounds.north.toFixed(4)}&east=${bounds.east.toFixed(4)}`;

  useEffect(() => {
    if (!live || (!layers.planes && tab !== "air")) return;
    let cancelled = false;
    const load = () => request<Air>("GET", `/api/map/aircraft?${area}`).then(reply => { if (!cancelled) setAir(reply); }).catch(() => { if(!cancelled)setAir(current=>current?{...current,error:"Aircraft feed unavailable; last reports will freeze and expire."}:{source:"none",updatedAt:null,planes:[],tooWide:false,error:"Aircraft feed is unavailable."}); });
    const first = window.setTimeout(load, 500);
    const timer = window.setInterval(() => { if (!document.hidden) load(); }, AIR_EVERY_MS);
    return () => { cancelled = true; window.clearTimeout(first); window.clearInterval(timer); };
  }, [area, layers.planes || tab === "air"]);

  useEffect(() => {
    if (!live || (!layers.ships && tab !== "sea")) return;
    let cancelled = false;
    const load = () => request<Marine>("GET", `/api/map/marine?${area}`).then(reply => { if (!cancelled) setMarine(reply); })
      .catch(() => { if (!cancelled) setMarine({ source: "none", configured: false, updatedAt: null, ships: [], tooWide: false, error: "The ship feed is unavailable. Check the connection and local setup." }); });
    const first = window.setTimeout(load, 500);
    const timer = window.setInterval(() => { if (!document.hidden) load(); }, AIR_EVERY_MS);
    return () => { cancelled = true; window.clearTimeout(first); window.clearInterval(timer); };
  }, [area, layers.ships, tab]);

  useEffect(() => {
    if (!live || !layers.landmarks) return;
    if (view.z < 13) { setLandmarkNote(""); return; }
    let cancelled = false, timer = 0;
    const ask = (round: number) => {
      request<{ landmarks: Landmark[]; missing: number; pending: number; tooWide: boolean }>("GET", `/api/map/landmarks?${area}`, undefined, { timeoutMs: 120_000 })
        .then(reply => {
          if (cancelled) return;
          setLandmarks(current => { const next = new Map(current); reply.landmarks.forEach(item => next.set(item.id, item)); return next; });
          setLandmarkNote(reply.pending ? "Saving landmarks for this area…" : reply.missing ? "Some landmarks load once you're online." : "");
          if (reply.pending && round < 8) timer = window.setTimeout(() => ask(round + 1), 400);
        }).catch(() => { if (!cancelled) setLandmarkNote(""); });
    };
    timer = window.setTimeout(() => ask(0), 700);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [area, view.z, layers.landmarks]);

  // ---- moving the map
  const moveBy = (dx: number, dy: number) => setView(current => {
    const c = project(current.lat, current.lon, current.z);
    const next = unproject(c.x - dx, Math.min(Math.max(c.y - dy, 0), world(current.z)), current.z);
    return { ...current, lat: next.lat, lon: ((next.lon + 540) % 360) - 180 };
  });
  const zoomAt = (dz: number, px = size.w / 2, py = size.h / 2) => { touched.current = true; setView(current => {
    const z = Math.min(MAX_Z, Math.max(MIN_Z, current.z + dz));
    if (z === current.z) return current;
    const c = project(current.lat, current.lon, current.z);
    const point = { x: c.x - size.w / 2 + px, y: c.y - size.h / 2 + py };
    const scale = 2 ** (z - current.z);
    const next = unproject(point.x * scale - px + size.w / 2, point.y * scale - py + size.h / 2, z);
    return { lat: next.lat, lon: next.lon, z };
  }); };
  const goTo = (lat: number, lon: number, z = Math.max(view.z, 14)) => { touched.current = true; setView({ lat, lon, z: Math.min(MAX_Z, z) }); };
  const fitLine = (line: number[][]) => {
    if (!line.length) return;
    let south = 90, north = -90, west = 180, east = -180;
    for (const [lat, lon] of line) { south = Math.min(south, lat); north = Math.max(north, lat); west = Math.min(west, lon); east = Math.max(east, lon); }
    let z = MAX_Z;
    while (z > MIN_Z) {
      const a = project(north, west, z), b = project(south, east, z);
      if (b.x - a.x < size.w * 0.8 && b.y - a.y < size.h * 0.8) break;
      z--;
    }
    touched.current = true;
    setView({ lat: (south + north) / 2, lon: (west + east) / 2, z });
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest("button")) return;
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.id !== event.pointerId) return;
    const dx = event.clientX - d.x, dy = event.clientY - d.y;
    if (!d.moved && Math.hypot(dx, dy) < 3) return;
    setFollow(false); d.moved = true; d.x = event.clientX; d.y = event.clientY; touched.current = true;
    moveBy(dx, dy);
  };
  const onPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    drag.current = null;
    if (!d || d.moved || (event.target as HTMLElement).closest("button")) return;
    if (picking !== null) {
      const box = event.currentTarget.getBoundingClientRect();
      const point = unproject(left + event.clientX - box.left, top + event.clientY - box.top, view.z);
      setStop(picking, { label: `Pin ${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}`, lat: point.lat, lon: point.lon });
      setPicking(null);
      return;
    }
    setSelected(null);
  };
  const onWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    const time = Date.now();
    if (time - wheelAt.current < 220 || event.deltaY === 0) return;
    wheelAt.current = time;
    const box = event.currentTarget.getBoundingClientRect();
    zoomAt(event.deltaY < 0 ? 1 : -1, event.clientX - box.left, event.clientY - box.top);
  };

  // ---- directions
  const locate = () => {
    if (!navigator.geolocation) { setLocationState("Location is unavailable here. Enter your starting address."); return; }
    const generation = ++locationGate.current;
    const origin = stopsRef.current[0];
    setLocationState("Finding your location…");
    navigator.geolocation.getCurrentPosition(value => {
      if (!alive.current || generation !== locationGate.current || (stopsRef.current[0].key !== origin.key || stopsRef.current[0].query !== origin.query || stopsRef.current[0].lat !== origin.lat)) return;
      const point = { lat: value.coords.latitude, lon: value.coords.longitude, accuracy: value.coords.accuracy };
      if (!validPlace(point.lat, point.lon)) return;
      setPosition(point); setStop(0, { label: "Your location", ...point });
      setLocationState(`Location accuracy: about ${Math.round(point.accuracy)} m${point.accuracy > 250 ? ". Check the starting pin before routing." : ""}`);
      if (!touched.current) { touched.current = true; setView(current => ({ ...current, lat: point.lat, lon: point.lon, z: 14 })); }
    }, reason => {
      if (alive.current && generation === locationGate.current) setLocationState(reason.code === 1 ? "Location permission is off. Allow it in browser/Windows settings, or enter your start." : "Couldn't find your location. Retry or enter your start.");
    }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
  };
  useEffect(() => { alive.current = true; if (live && !tripSnapshot().route) locate(); return () => { alive.current = false; locationGate.current++; }; }, []);
  const setStop = (index: number, place: { label: string; lat: number; lon: number }) => {
    if (!validPlace(place.lat, place.lon)) return;
    setActiveSearch(null); setSuggestIndex(-1);
    if (index > 0) setRecent(current => { const next = [{ name: place.label, detail: "Recent destination", lat: place.lat, lon: place.lon }, ...current.filter(p => p.lat !== place.lat || p.lon !== place.lon)].slice(0, 8); store("zaenia.map.recent", next); return next; });
    changeStops(current => current.map((stop, i) => i === index ? { ...stop, label: place.label, query: place.label, lat: place.lat, lon: place.lon } : stop));
  };
  const addStop = (place: { label: string; lat: number; lon: number }) => {
    changeStops(current => {
      const at = current.findIndex(stop => stop.lat === null);
      if (at >= 0) return current.map((stop, i) => i === at ? { ...stop, label: place.label, query: place.label, lat: place.lat, lon: place.lon } : stop);
      return current.length >= MAX_STOPS ? current : [...current, { ...blankStop(place.label, place.lat, place.lon) }];
    });
    setTab("directions");
  };
  const typeStop = (index: number, query: string) => {
    setActiveSearch(index); setSuggestIndex(-1);
    changeStops(current => current.map((stop, i) => i === index ? { ...stop, label: "", query, lat: null, lon: null } : stop));
  };
  const searchStop = (index: number, autocomplete = false) => {
    const stop = stopsRef.current[index];
    if (!live || !stop || stop.query.trim().length < 3) return;
    const key = `${stop.key}:${stop.query}`;
    const ticket = searchGate.current.issue(key);
    setSearchBusy(index); setSearchError(""); setSuggest(null);
    request<{ places: Place[]; source?: string }>("GET", `/api/map/search?autocomplete=${autocomplete}&q=${encodeURIComponent(stop.query.trim())}&lat=${view.lat.toFixed(4)}&lon=${view.lon.toFixed(4)}`, undefined, { timeoutMs: 20_000 })
      .then(reply => {
        const current = stopsRef.current[index];
        if (!current || !searchGate.current.accepts(ticket, `${current.key}:${current.query}`)) return;
        setSuggestIndex(-1);
        setSuggest({ index, places: reply.places.filter(place => validPlace(place.lat, place.lon)) });
        if (reply.source === "offline") setSearchError("Online suggestions are unavailable. Press Enter for address search or choose a map pin.");
        if (reply.source === "busy") setSearchError("Suggestions are busy. Keep typing or press Enter to search.");
      })
      .catch(reason => { if (searchGate.current.isCurrent(ticket)) setSearchError(errorText(reason)); })
      .finally(() => { if (searchGate.current.isCurrent(ticket)) setSearchBusy(null); });
  };
  useEffect(() => {
    if (activeSearch === null || !home.features?.autocomplete) return;
    const current = stops[activeSearch];
    if (!current || current.lat !== null || current.query.trim().length < 3) return;
    const timer = window.setTimeout(() => searchStop(activeSearch, true), 1100);
    return () => window.clearTimeout(timer);
  }, [activeSearch, stops, home.features?.autocomplete]);
  const moveStop = (index: number, by: number) => {
    changeStops(current => { const next = [...current]; const [item] = next.splice(index, 1); next.splice(index + by, 0, item); return next; });
  };
  const ready = stops.filter(stop => stop.lat !== null && stop.lon !== null);
  const canRoute = completeStops(stops);
  const getDirections = () => {
    if (!live || !canRoute) return;
    const snapshot = stops.map(stop => ({ ...stop }));
    const optimize = bestOrder;
    const ticket = routeGate.current.issue(stopFingerprint(snapshot, optimize));
    setRouteBusy(true); setRouteError("");
    request<Route>("POST", "/api/map/route", { stops: snapshot.map(stop => ({ lat: stop.lat, lon: stop.lon })), bestOrder: optimize, ...(home.features?.alternatives ? { alternatives: snapshot.length === 2 } : {}) }, { timeoutMs: 90_000 })
      .then(value => {
        if (!routeGate.current.accepts(ticket, stopFingerprint(stopsRef.current, orderRef.current))) return;
        const reply = checkedRoute(value, snapshot.length);
        if (optimize) setStops(reply.order.map(i => snapshot[i]));
        const choices = [reply];
        for (const option of (reply.alternatives ?? []).slice(0, 2)) {
          try { choices.push(checkedRoute(option, snapshot.length)); } catch { /* skip malformed optional routes */ }
        }
        setRouteChoices(choices); setRoute(reply);
        setPreviewIndex(0); setSelected(null); setRouteBusy(false);
        fitLine(reply.line);
      })
      .catch(reason => { if (routeGate.current.isCurrent(ticket)) setRouteError(errorText(reason)); })
      .finally(() => { if (routeGate.current.isCurrent(ticket)) setRouteBusy(false); });
  };
  const routeAlerts = useMemo(() => route && traffic ? traffic.alerts.filter(alert => kmToLine(alert, route.line) < 0.6) : [], [route, traffic]);
  const routeSlow = useMemo(() => route && traffic ? traffic.flows.filter(flow => flow.level >= 3 && kmToLine(flow, route.line) < 0.3) : [], [route, traffic]);

  const tripIndex = useMemo(() => route ? indexRoute(route.line) : null, [route]);
  const toggleTrip=()=>{
    if(tracking){pauseTrip();return;}
    if(!route)return;
    if(progress?.arrived)stopTrip();
    setFollow(true);
    beginTrip(route,stops.map(stop=>({lat:stop.lat!,lon:stop.lon!,label:stop.label})),async remaining=>checkedRoute(await request<Route>("POST","/api/map/route",{stops:remaining.map(p=>({lat:p.lat,lon:p.lon})),bestOrder:false},{timeoutMs:45000}),remaining.length));
  };
  useEffect(()=>{
    const sync=()=>{const value=tripSnapshot();setSessionState(value);setTracking(value.running);setProgress(value.progress);progressRef.current=value.progress;setTripStatus(value.status);if(value.fix)setPosition(value.fix);if(value.route){setRoute(value.route);setStops(current=>current.length===value.stops.length && current.every((stop,i)=>stop.lat===value.stops[i].lat&&stop.lon===value.stops[i].lon)?current:value.stops.map(p=>blankStop(p.label,p.lat,p.lon)));}};
    sync();return subscribeTrip(sync);
  },[]);
  useEffect(()=>{if(route && tripSnapshot().route && route!==tripSnapshot().route)stopTrip();},[route]);
  useEffect(()=>{if(tracking && follow && progress){touched.current=true;setView(current=>({...current,lat:progress.point[0],lon:progress.point[1],z:Math.max(14,current.z)}));}},[tracking,follow,progress]);
  useEffect(()=>{const timer=window.setInterval(()=>setTripClock(Date.now()),15000);return()=>window.clearInterval(timer);},[]);
  const gpsStale = tracking && !!progress && tripClock-progress.timestamp>15000;
  const doneLine=useMemo(()=>tripIndex?completedLine(tripIndex,progress):[],[tripIndex,progress]);
  const destination=route?stops[stops.length-1]:null;
  useEffect(()=>{
    if(!live || !destination || destination.lat===null || destination.lon===null){setDestinationWeather(null);return;}
    let active=true;const load=()=>request<Weather>("GET",`/api/map/weather/alerts?lat=${destination.lat!.toFixed(3)}&lon=${destination.lon!.toFixed(3)}`).then(value=>{if(active)setDestinationWeather(value);}).catch(()=>{if(active)setDestinationWeather({source:"none",updatedAt:null,alerts:[],error:"Destination weather is unavailable."});});
    setDestinationWeather(null);void load();const timer=window.setInterval(()=>{if(!document.hidden)void load();},WEATHER_EVERY_MS);return()=>{active=false;window.clearInterval(timer);};
  },[live,destination?.lat,destination?.lon]);

  // ---- what to draw
  const screen = (lat: number, lon: number) => { const p = project(lat, lon, view.z); return { x: p.x - left, y: p.y - top }; };
  const onScreen = (p: { x: number; y: number }, pad = 40) => p.x > -pad && p.y > -pad && p.x < size.w + pad && p.y < size.h + pad;
  const flows = layers.traffic && traffic ? traffic.flows.map(item => ({ item, p: screen(item.lat, item.lon) })).filter(f => onScreen(f.p)) : [];
  const alerts = layers.traffic && traffic ? traffic.alerts.map(item => ({ item, p: screen(item.lat, item.lon), e: item.endLat != null && item.endLon != null ? screen(item.endLat, item.endLon) : null }))
    .filter(a => onScreen(a.p) || (a.e && onScreen(a.e))) : [];
  // Traffic along the roads: each line runs between two neighbouring sensors and takes the worse of their readings.
  const levels = useMemo(() => new Map((traffic?.flows ?? []).map(flow => [flow.id, flow.level])), [traffic]);
  const roadWidth = view.z <= 9 ? 2.5 : view.z <= 11 ? 3.5 : view.z <= 13 ? 5 : 7;
  const drawn = new Set<string>();
  const trafficLines = !layers.traffic ? [] : segments.flatMap(segment => {
    const a = levels.get(segment.from), b = levels.get(segment.to);
    if (a === undefined && b === undefined) return [];
    const points = segment.line.map(([lat, lon]) => screen(lat, lon));
    if (!points.some(p => onScreen(p, 0))) return [];
    drawn.add(segment.from); drawn.add(segment.to);
    return [{ id: segment.id, level: Math.max(a ?? 1, b ?? 1) as 1 | 2 | 3 | 4, points: points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ") }];
  });
  const marks = layers.landmarks && view.z >= 13 ? [...landmarks.values()].map(item => ({ item, p: screen(item.lat, item.lon) })).filter(m => onScreen(m.p, 10)) : [];

  const ships = layers.ships && marine ? marine.ships.map(item => ({ item, p: screen(item.lat, item.lon) })).filter(m => onScreen(m.p)) : [];
  const routeStrokes = useMemo(() => route ? buildRouteTraffic(route.line, segments, traffic?.flows ?? [],
    traffic?.source === "live" && !!traffic.updatedAt && Date.now() - Date.parse(traffic.updatedAt) < 10 * 60_000) : [], [route, segments, traffic, layers.traffic, Math.floor(tripClock/15000)]);
  const eta=useMemo(()=>trafficEta(route?.duration??0,routeStrokes,progress?.fraction??0),[route,routeStrokes,progress]);
  const routePath = route ? route.line.map(([lat, lon]) => { const p = screen(lat, lon); return `${p.x.toFixed(1)},${p.y.toFixed(1)}`; }).join(" ") : "";
  const weatherShapes = layers.radar && weather ? weather.alerts.filter(a => a.polygon) : [];

  const nearby = useMemo(() => {
    if (!traffic) return [];
    return traffic.alerts.map(item => ({ item, distance: km(home, item) })).filter(a => a.distance <= NEARBY_KM)
      .sort((a, b) => (PRIORITY_RANK[a.item.priority.toLowerCase()] ?? 5) - (PRIORITY_RANK[b.item.priority.toLowerCase()] ?? 5) || a.distance - b.distance).slice(0, 30);
  }, [traffic, home]);
  const slow = traffic ? traffic.flows.filter(f => f.level >= 3 && km(home, f) <= NEARBY_KM) : [];
  const planeList = useMemo(() => air ? [...air.planes].sort((a, b) => km(view, a) - km(view, b)).slice(0, 40) : [], [air, view]);

  const tileLayer = (kind: string, z: number, className: string) => visible.map(({ x, y, wrapX }) => {
    const px = x * TILE - left, py = y * TILE - top, scale = 2 ** (view.z - z);
    const exact = scale === 1 ? tiles.get(`${kind}|${z}/${wrapX}/${y}`) : undefined;
    if (exact) return <img key={`${x}/${y}`} className={`zmap__tile ${className}`} src={exact} alt="" draggable={false} style={{ left: px, top: py }}/>;
    // A zoomed-out tile stands in (radar always does past its top zoom) until this one arrives.
    for (let d = Math.max(1, view.z - z); d <= Math.max(4, view.z - z) && view.z - d >= 0; d++) {
      const s = 2 ** d, parent = tiles.get(`${kind}|${view.z - d}/${Math.floor(wrapX / s)}/${Math.floor(y / s)}`);
      if (!parent) continue;
      return <div key={`${x}/${y}`} className={`zmap__tile zmap__tile--stand-in ${className}`} style={{ left: px, top: py }}>
        <img src={parent} alt="" draggable={false} style={{ width: TILE * s, height: TILE * s, left: -(wrapX % s) * TILE, top: -(y % s) * TILE }}/>
      </div>;
    }
    return kind === STYLE_LAYERS[style][0][0] ? <div key={`${x}/${y}`} className="zmap__tile zmap__tile--empty" style={{ left: px, top: py }}/> : null;
  });

  const status = !live ? "Preview: the map and live feeds load from the ZAE server in the app."
    : !traffic ? (trafficBusy ? "Checking traffic…" : error || "Traffic not loaded yet.")
    : traffic.source === "live" ? `Traffic live from WSDOT · updated ${ago(traffic.updatedAt)}`
    : traffic.source === "saved" ? `Offline · traffic from ${ago(traffic.updatedAt)}`
    : traffic.error || "No traffic reading yet.";
  const toggle = (name: keyof typeof layers) => setLayers(current => ({ ...current, [name]: !current[name] }));
  const arrive = route ? clock(new Date((tracking && progress ? progress.timestamp : Date.now()) + eta.seconds * 1000)) : "";
  const steps = useMemo(() => route?.legs.flatMap((leg, legIndex) => leg.steps.map(step => ({ ...step, legIndex }))) ?? [], [route]);
  let instructionDistance=0;
  const liveStepIndex=steps.findIndex(step=>{instructionDistance+=step.distance;return instructionDistance>(route?.distance??0)*(progress?.fraction??0);});
  const effectiveStep=tracking?Math.max(0,liveStepIndex):previewIndex;
  const previewStep = steps[effectiveStep];
  const showStep = (index: number) => { const next = Math.min(steps.length - 1, Math.max(0, index)); setPreviewIndex(next); const step = steps[next]; if (step) goTo(step.lat, step.lon, 16); };
  const routeTraffic = !traffic || traffic.source === "none" ? "Traffic reports unavailable for this route."
    : `${routeAlerts.length} incident${routeAlerts.length === 1 ? "" : "s"} · ${routeSlow.length} slow report${routeSlow.length === 1 ? "" : "s"} near the route${traffic.source === "saved" ? " · saved data" : ""}. Coverage varies.`;

  return <div className={`zmap zmap--${style === "map" ? "light" : "dark"} zmap--${style}`}>
    <header className="zmap__head">
      <div>
        <span className="zmap__kicker">ZÆNIA · navigation workspace</span>
        <h3 className="zmap__title zmap__workspace-title">GODSPEED</h3>
        <span className="zmap__location">{home.place || "Map"}{now?.temperature != null && <small className="zmap__temp">{Math.round(now.temperature)}° {now.condition.toLowerCase()}</small>}</span>
        <span className={`zmap__status${traffic?.source === "live" ? " zmap__status--live" : ""}`}>{status}</span>
      </div>
      <div className="zmap__layers" role="group" aria-label="Map layers">
        {([["traffic", "Traffic"], ["landmarks", "Places"], ["radar", "Radar"], ["planes", "Aircraft"], ["ships", "Ships"]] as const).map(([name, label]) =>
          <button key={name} type="button" className={layers[name] ? "zmap__pill zmap__pill--on" : "zmap__pill"} aria-pressed={layers[name]} onClick={() => toggle(name)}>{label}</button>)}
        <span className="zmap__segment" role="group" aria-label="Map style">
          {(["map", "satellite", "dark"] as const).map(option => <button key={option} type="button" aria-pressed={style === option} className={style === option ? "zmap__seg zmap__seg--on" : "zmap__seg"} onClick={() => setStyle(option)}>{STYLE_NAMES[option]}</button>)}
        </span>
      </div>
    </header>

    <div className="zmap__body">
      <div className={`zmap__frame${picking !== null ? " zmap__frame--picking" : ""}`} ref={frame} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
        onPointerCancel={() => { drag.current = null; }} onWheel={onWheel}
        onDoubleClick={event => { const box = event.currentTarget.getBoundingClientRect(); zoomAt(1, event.clientX - box.left, event.clientY - box.top); }}
        role="application" tabIndex={0} aria-label="Map. Drag to move, scroll to zoom. Arrow keys move; plus and minus zoom."
        onKeyDown={event => {
          if (event.target !== event.currentTarget) return;
          const moves: Record<string, [number, number]> = { ArrowLeft: [80, 0], ArrowRight: [-80, 0], ArrowUp: [0, 80], ArrowDown: [0, -80] };
          if (moves[event.key]) { event.preventDefault(); touched.current = true; moveBy(...moves[event.key]); }
          else if (event.key === "+" || event.key === "=") { event.preventDefault(); zoomAt(1); }
          else if (event.key === "-") { event.preventDefault(); zoomAt(-1); }
          else if (event.key === "Escape") { setSelected(null); setPicking(null); }
        }}>
        {STYLE_LAYERS[style].map(([kind, topZoom]) => <div key={kind} className={`zmap__tiles zmap__tiles--${kind}`}>{tileLayer(kind, Math.min(view.z, topZoom), "")}</div>)}
        {layers.radar && radarFrame && <div className="zmap__radar">{tileLayer(`radar|${radarFrame.path}`, radarZ, "zmap__tile--radar")}</div>}
        <svg className="zmap__overlay" width={size.w} height={size.h} aria-hidden="true">
          {weatherShapes.map(alert => <polygon key={alert.id} points={alert.polygon!.map(([lat, lon]) => { const p = screen(lat, lon); return `${p.x},${p.y}`; }).join(" ")}
            className="zmap__wx-area" style={{ stroke: SEVERITY_COLOR[alert.severity] ?? "#f2b84b", fill: SEVERITY_COLOR[alert.severity] ?? "#f2b84b" }}/>)}

          {alerts.map(({ item, p, e }) => e && <line key={`l${item.id}`} x1={p.x} y1={p.y} x2={e.x} y2={e.y} className="zmap__alert-line"/>)}
          {trafficLines.map(({ id, points }) => <polyline key={`c${id}`} points={points} className="zmap__road-case" style={{ strokeWidth: roadWidth + 3 }}/>)}
          {trafficLines.map(({ id, level, points }) => <polyline key={id} points={points} className="zmap__road" style={{ stroke: FLOW_COLORS[level], strokeWidth: roadWidth }}/>)}
          {flows.filter(f => !drawn.has(f.item.id)).map(({ item, p }) => <circle key={item.id} cx={p.x} cy={p.y} r={item.level === 1 ? (view.z >= 13 ? 3.5 : 2.5) : (view.z >= 13 ? 6 : 4.5)}
            fill={FLOW_COLORS[item.level]} className={`zmap__flow zmap__flow--${item.level}`}/>)}
          {routePath && <polyline points={routePath} className="zmap__route-glow"/>}
          {routeStrokes.map((stroke, i) => <polyline key={`route${i}`} points={stroke.line.map(([lat, lon]) => { const p = screen(lat, lon); return `${p.x},${p.y}`; }).join(" ")} className="zmap__route" style={{ stroke: stroke.level === null || !layers.traffic ? "#7c899d" : ROUTE_COLORS[stroke.level], strokeDasharray: stroke.level === null || !layers.traffic ? "9 5" : undefined }}/>)}
          {doneLine.length>1 && <polyline points={doneLine.map(([lat,lon])=>{const p=screen(lat,lon);return `${p.x},${p.y}`;}).join(" ")} className="zmap__completed"/>}
          {position && <circle cx={screen(position.lat, position.lon).x} cy={screen(position.lat, position.lon).y} r={8} fill="#4285f4" stroke="white" strokeWidth={3}/>}
        </svg>
        {flows.filter(f => f.item.level >= 2).map(({ item, p }) => <button key={`f${item.id}`} type="button" className="zmap__mark zmap__mark--flow" style={{ left: p.x, top: p.y }}
          aria-label={`${road(item.road)} ${item.direction}: ${item.label}`} onClick={() => setSelected({ kind: "flow", item })}/>)}
        {marks.map(({ item, p }) => <button key={item.id} type="button" className="zmap__mark zmap__mark--place" style={{ left: p.x, top: p.y }} onClick={() => setSelected({ kind: "landmark", item })}>
          <i/>{view.z >= 15 && <span>{item.name}</span>}
        </button>)}
        {alerts.map(({ item, p }) => { const closed = /clos/i.test(`${item.category} ${item.headline}`);
          return onScreen(p) && <button key={`a${item.id}`} type="button" className={`zmap__mark zmap__mark--alert zmap__mark--${closed ? "closed" : (item.priority || "low").toLowerCase()}`}
          style={{ left: p.x, top: p.y }} aria-label={item.headline} onClick={() => setSelected({ kind: "alert", item })}>{closed ? <i/> : "!"}</button>; })}
        <AircraftLayer reports={air?.planes??[]} enabled={layers.planes} animate={animateAircraft} view={view} left={left} top={top} width={size.w} height={size.h} onSelect={item=>setSelected({kind:"plane",item})}/>
        {ships.map(({ item, p }) => <button key={`ship${item.id}`} type="button" className="zmap__mark zmap__mark--ship" style={{ left: p.x, top: p.y }}
          aria-label={`Vessel ${item.name || item.id}`} onClick={() => setSelected({ kind: "ship", item })}>
          <svg viewBox="0 0 24 24" style={{ transform: `rotate(${item.heading ?? 0}deg)` }}><path d="M12 2 18 9v10l-6 3-6-3V9Z"/></svg>
        </button>)}
        {route && ready.map((stop, index) => { const p = screen(stop.lat!, stop.lon!); return onScreen(p) &&
          <button key={stop.key} type="button" className="zmap__mark zmap__mark--stop" style={{ left: p.x, top: p.y }} aria-label={`Stop ${LETTERS[index]}: ${stop.label}`}
            onClick={() => { setTab("directions"); }}><span>{LETTERS[index]}</span></button>; })}

        <div className="zmap__zoom">
          <button type="button" onClick={() => zoomAt(1)} aria-label="Zoom in" disabled={view.z >= MAX_Z}>+</button>
          <button type="button" onClick={() => zoomAt(-1)} aria-label="Zoom out" disabled={view.z <= MIN_Z}>−</button>
          <button type="button" onClick={() => setView({ lat: home.lat, lon: home.lon, z: home.z })} aria-label="Back to home" title="Home">⌂</button>
          {route && <button type="button" className="zmap__overview-button" onClick={() => fitLine(route.line)} aria-label="Fit entire route" title="Fit route">⛶</button>}
        </div>
        {route && previewStep && !selected && picking === null && <div className="zmap__step-card" onPointerDown={event => event.stopPropagation()}>
          <div className="zmap__step-kicker"><span>{tracking?"Live trip":"Route preview"}</span><span>{effectiveStep + 1} / {steps.length}</span></div>
          <strong>{previewStep.text}</strong>
          <small>{previewStep.distance < 400 ? `${Math.round(previewStep.distance * 3.281 / 10) * 10} ft` : miles(previewStep.distance / 1000)} · leg {LETTERS[previewStep.legIndex]} → {LETTERS[previewStep.legIndex + 1]}</small>
          <div className="zmap__step-controls" hidden={tracking}><button type="button" disabled={previewIndex === 0} onClick={() => showStep(previewIndex - 1)}>← Previous</button>
            <button type="button" disabled={previewIndex >= steps.length - 1} onClick={() => showStep(previewIndex + 1)}>Next step →</button></div>
        </div>}
        {route && !selected && picking === null && <div className="zmap__route-card" onPointerDown={event => event.stopPropagation()}>
          <div className="zmap__route-card-head"><strong>{stops[stops.length - 1]?.label || "Your destination"}</strong><span>{stops.length} stops</span></div>
          <div className="zmap__route-stats">
            <div className="zmap__route-stat"><strong>{duration(eta.seconds)}</strong><span>{progress?"time remaining":"estimated time"}</span></div>
            <div className="zmap__route-stat"><strong>{miles(route.distance*(1-(progress?.fraction??0))/1000)}</strong><span>{progress?"remaining":"distance"}</span></div>
            <div className="zmap__route-stat"><strong>{arrive}</strong><span>estimated arrival</span></div>
          </div>
          <div className="zmap__route-state" role="status">{progress?`${Math.round(progress.fraction*100)}% completed · ${gpsStale?"GPS stale":tripStatus}`:route.engine==="local"?"Calculated on this PC · Route preview":"Calculated online · Route preview"}</div>
          {progress && <progress max={100} value={progress.fraction*100} aria-label="Route completed"/>}
          <div className="zmap__route-actions"><button type="button" onClick={toggleTrip}>{tracking?"Pause trip":progress?.arrived?"Restart trip":progress?"Resume trip":"Start trip"}</button><button type="button" onClick={() => { setFollow(false); fitLine(route.line); setTab("directions"); }}>Route overview</button>
            <button type="button" onClick={invalidateRoute}>Clear route</button></div>
        </div>}
        {layers.traffic && <div className="zmap__legend" aria-label="Traffic legend"><span><i style={{background:"#7c899d"}}/>Unknown / stale</span>
          {([1, 2, 3, 4] as const).map(level => <span key={level}><i style={{ background: FLOW_COLORS[level] }}/>{["Regular", "Slower", "Heavy", "Stop & go"][level - 1]}</span>)}
          {layers.radar && radarFrame && <span className="zmap__legend-radar">Radar {clock(new Date(radarFrame.time * 1000))}</span>}
        </div>}
        {picking !== null && <div className="zmap__note zmap__note--pick">Tap the map to set stop {LETTERS[picking]} <button type="button" onClick={() => setPicking(null)}>Cancel</button></div>}
        {picking === null && landmarkNote && layers.landmarks && <div className="zmap__note">{landmarkNote}</div>}
        {selected && <div className="zmap__card" role="dialog" aria-label="Details">
          <button type="button" className="zmap__close" aria-label="Close" onClick={() => setSelected(null)}>×</button>
          {selected.kind === "alert" && <><small>{[selected.item.category, road(selected.item.road), selected.item.priority && `${selected.item.priority} priority`].filter(Boolean).join(" · ")}</small>
            <p>{selected.item.headline}</p><small>{selected.item.updated ? `Updated ${ago(selected.item.updated)}` : selected.item.start ? `Since ${ago(selected.item.start)}` : ""}</small></>}
          {selected.kind === "flow" && <><small>{road(selected.item.road)} {selected.item.direction}</small><p>{capital(selected.item.label)} traffic</p><small>{selected.item.place}</small></>}
          {selected.kind === "landmark" && <><small>{capital(selected.item.kind)}</small><p>{selected.item.name}</p><small>{miles(km(home, selected.item))} from {home.place || "home"}</small>
            <button type="button" className="zmap__textbtn" onClick={() => addStop({ label: selected.item.name, lat: selected.item.lat, lon: selected.item.lon })}>Add as a stop</button></>}
          {selected.kind === "plane" && <><small>{[selected.item.country, selected.item.squawk && `squawk ${selected.item.squawk}`].filter(Boolean).join(" · ")}</small><p>{selected.item.callsign || selected.item.id.toUpperCase()}</p><small>Position observed {selected.item.positionAt?ago(selected.item.positionAt):"at an unknown time"}. Marker motion between reports is estimated.</small>
            <small>{selected.item.onGround ? "On the ground" : [selected.item.altitudeFt != null && `${selected.item.altitudeFt.toLocaleString()} ft`, selected.item.speedKt != null && `${selected.item.speedKt} kt`,
              selected.item.climbFpm ? `${selected.item.climbFpm > 0 ? "climbing" : "descending"} ${Math.abs(selected.item.climbFpm).toLocaleString()} ft/min` : ""].filter(Boolean).join(" · ")}</small></>}
          {selected.kind === "ship" && <><small>AIS vessel · {selected.item.id}</small><p>{selected.item.name || "Unnamed vessel"}</p>
            <small>{selected.item.speedKt != null ? `${selected.item.speedKt.toFixed(1)} kt · ` : ""}{selected.item.heading != null ? `${Math.round(selected.item.heading)}° · ` : ""}reported {ago(selected.item.updatedAt)}</small>
            {selected.item.destination && <small>Reported destination: {selected.item.destination}</small>}</>}
          {selected.kind === "weather" && <><small>{selected.item.severity} · until {selected.item.ends ? clock(new Date(selected.item.ends)) : "further notice"}</small><p>{selected.item.headline || selected.item.event}</p><small>{selected.item.instruction}</small></>}
        </div>}
        <div className="zmap__credit">{style === "satellite" ? "USGS The National Map · Orthoimagery and US Topo" : "© OpenStreetMap contributors"}{layers.traffic ? " · WSDOT" : ""}{layers.radar ? " · RainViewer · NWS" : ""}{layers.planes ? " · OpenSky" : ""}{layers.ships ? " · AISStream" : ""}</div>
      </div>

      <aside className="zmap__rail">
        <PageNavigator id="godspeed" name="GODSPEED" items={MAP_PAGES} current={tab} onChoose={next => setTab(next as Tab)}/>
        <DetailScreen id="map-detail" name="Map" open={!!selected} title={pickedName(selected)} onOpen={() => { if (lastPicked.current) setSelected(lastPicked.current); }} onClose={() => setSelected(null)}/>

        {tab === "traffic" && <>
          <div className="zmap__railhead">
            <h4>Near {home.place || "home"}</h4>
            <button type="button" className="zmap__textbtn" onClick={() => loadTraffic(true)} disabled={trafficBusy || !live}>{trafficBusy ? "Checking…" : "Refresh"}</button>
          </div>
          <p className="zmap__summary">{!traffic || traffic.source === "none" ? "Traffic reports unavailable." : slow.length ? `${slow.length} slow spot${slow.length === 1 ? "" : "s"} within ${Math.round(NEARBY_KM * 0.621)} mi` : "No slow reports matched nearby. Coverage varies."}</p>
          {traffic?.error && traffic.source !== "live" && <p className="zmap__warn">{traffic.error}</p>}
          <ul className="zmap__list">
            {nearby.map(({ item, distance }) => <li key={item.id}>
              <button type="button" onClick={() => { goTo(item.lat, item.lon); setSelected({ kind: "alert", item }); }}>
                <span className={`zmap__dot zmap__dot--${(item.priority || "low").toLowerCase()}`}/>
                <strong>{item.headline || item.category}</strong>
                <small>{[road(item.road), miles(distance), ago(item.updated || item.start)].filter(Boolean).join(" · ")}</small>
              </button>
            </li>)}
            {traffic && traffic.source !== "none" && !nearby.length && <li className="zmap__empty">No incidents or closures matched nearby. Coverage varies.</li>}
          </ul>
        </>}

        {tab === "directions" && <>
          <div className="zmap__panel-intro"><h4>Directions</h4><p>Driving · choose your destination</p></div>
          <div className="zmap__route-tools"><button type="button" onClick={()=>loadTraffic(true)}>Refresh traffic</button><button type="button" onClick={locate}>◎ Your location</button><button type="button" onClick={() => changeStops(current => [...current].reverse())} aria-label="Reverse route">⇅ Swap</button></div>
          {!home.features?.autocomplete && <small className="zmap__search-state">Typing suggestions require the updated Core. Restart the server after installing; Enter still searches.</small>}
          {locationState && <small className="zmap__search-state" role="status">{locationState}</small>}
          <ol className="zmap__stops">
            {stops.map((stop, index) => <li key={stop.key} className="zmap__stop">
              <span className={`zmap__letter${stop.lat !== null ? " zmap__letter--set" : ""}`}>{LETTERS[index]}</span>
              <input value={stop.query} placeholder={index === 0 ? "Your location or starting address" : index === stops.length - 1 ? "Destination" : "Stop"} aria-label={`Stop ${LETTERS[index]}`}
                maxLength={120} onChange={event => typeStop(index, event.target.value)} role="combobox" aria-autocomplete="list" aria-expanded={suggest?.index === index} aria-controls={`map-places-${stop.key}`} aria-activedescendant={suggest?.index === index && suggestIndex >= 0 ? `map-place-${stop.key}-${suggestIndex}` : undefined} onFocus={event => { event.target.select(); setActiveSearch(index); }}
                onKeyDown={event => {
                  const places = suggest?.index === index ? suggest.places : [];
                  if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setSuggestIndex(i => Math.max(0, Math.min(places.length - 1, i + (event.key === "ArrowDown" ? 1 : -1)))); }
                  else if (event.key === "Enter") { event.preventDefault(); const place = places[suggestIndex]; if (place) setStop(index, { label: place.name, lat: place.lat, lon: place.lon }); else { setActiveSearch(null); searchStop(index); } }
                  else if (event.key === "Escape") { setSuggest(null); setActiveSearch(null); }
                }}/>
              <span className="zmap__stopbtns">
                <button type="button" title="Pick on the map" aria-label="Pick on the map" onClick={() => setPicking(index)}>◎</button>
                <button type="button" title="Move up" aria-label="Move up" hidden={stops.length === 2} disabled={index === 0} onClick={() => moveStop(index, -1)}>↑</button>
                <button type="button" title="Move down" aria-label="Move down" hidden={stops.length === 2} disabled={index === stops.length - 1} onClick={() => moveStop(index, 1)}>↓</button>
                <button type="button" title="Remove" aria-label="Remove" hidden={stops.length === 2} disabled={stops.length <= 2} onClick={() => changeStops(current => current.filter((_, i) => i !== index))}>×</button>
              </span>
              {stop.lat === null && <button type="button" className="zmap__stop-search" disabled={!live || stop.query.trim().length < 3 || searchBusy === index} onClick={() => searchStop(index)}>
                {searchBusy === index ? "Searching…" : "Search this stop"}</button>}
              {suggest?.index === index && <ul className="zmap__suggest" id={`map-places-${stop.key}`} role="listbox">
                {suggest.places.map((place, i) => <li key={i} id={`map-place-${stop.key}-${i}`} role="option" aria-selected={suggestIndex === i}><button type="button" onClick={() => setStop(index, { label: place.name, lat: place.lat, lon: place.lon })}>
                  <strong>{place.name}</strong><small>{place.detail}</small></button></li>)}
                {!suggest.places.length && <li className="zmap__empty">No matches. Try a fuller address, or pick on the map.</li>}
              </ul>}
            </li>)}
          </ol>
          <small className="zmap__search-state">Typing sends your search and approximate map area to Photon for suggestions. Enter searches addresses. Map pins skip lookup. Routing uses this PC first, otherwise an online service.</small>
          {recent.length > 0 && !stops[stops.length - 1].query && <div className="zmap__recent"><strong>Recent destinations</strong>{recent.map((place, i) => <button type="button" key={i} onClick={() => setStop(stops.length - 1, { label: place.name, lat: place.lat, lon: place.lon })}>{place.name}</button>)}<button type="button" onClick={() => { setRecent([]); store("zaenia.map.recent", []); }}>Clear recents</button></div>}
          {searchError && <p className="zmap__warn" role="status">{searchError}</p>}
          <div className="zmap__routebar">
            <button type="button" className="zmap__textbtn" disabled={stops.length >= MAX_STOPS} onClick={() => changeStops(current => [...current, blankStop()])}>+ Add stop</button>
            <label className="zmap__check"><input type="checkbox" checked={bestOrder} onChange={event => { setBestOrder(event.target.checked); invalidateRoute(); }}/> Quickest order</label>
          </div>
          <button type="button" className="zmap__go" disabled={!canRoute || routeBusy || !live} onClick={getDirections}>{routeBusy ? "Working out the route…" : "Get directions"}</button>
          {!canRoute && <small className="zmap__search-state">Choose a search result or map pin for all {stops.length} stops.</small>}
          {routeError && <p className="zmap__warn">{routeError}</p>}
          {route && <section className="zmap__trip" aria-label="Trip progress">
            <div className="zmap__route-tools"><button type="button" onClick={toggleTrip}>{tracking?"Pause trip":progress?.arrived?"Restart trip":progress?"Resume trip":"Start trip"}</button><button type="button" onClick={()=>setFollow(value=>!value)} aria-pressed={follow}>{follow?"Following location":"Recenter / follow"}</button><button type="button" onClick={()=>{stopTrip();setTripStatus("Trip reset");}}>Reset trip</button></div>
            <label><input type="checkbox" checked={sessionState.autoReroute} onChange={event=>setAutoReroute(event.target.checked)}/> Automatically reroute after repeated off-route readings</label><small>{sessionState.wake}</small><progress max={100} value={(progress?.fraction??0)*100}/>
            <strong>{Math.round((progress?.fraction??0)*100)}% completed</strong><small>Traffic ETA coverage: {Math.round(eta.coverage*100)}% of remaining geometry · estimated delay {duration(eta.delaySeconds)}. Flow-category multipliers are approximate, not measured travel times.</small>
            <p>{miles(route.distance*(progress?.fraction??0)/1000)} traveled · {miles(route.distance*(1-(progress?.fraction??0))/1000)} remaining</p>
            <p role="status">{gpsStale?"GPS signal is stale; progress paused.":tripStatus||"Start trip to track progress across ZAE tabs while the app stays running."}</p>
            <small>Remaining time: {duration(eta.seconds)} · traffic-adjusted estimate where reports exist; unknown roads retain baseline time. GPS stays in memory across ZAE tabs. Closing/reloading ZAE ends the trip. Locked or suspended phones may pause GPS.</small>
            {tracking && progress && <strong>Current instruction: {steps.find((_,i)=>steps.slice(0,i+1).reduce((n,s)=>n+s.distance,0)>route.distance*progress.fraction)?.text??"Approach your destination"}</strong>}
          </section>}
          {routeChoices.length > 0 && <div className="zmap__choices" aria-label="Route options">{routeChoices.map((choice, i) => <button type="button" key={i} aria-pressed={route === choice} onClick={() => { stopTrip(); setTracking(false); setRoute(choice); setPreviewIndex(0); fitLine(choice.line); }}><strong>{duration(choice.duration)}</strong><span>{i === 0 ? "Suggested route" : `Alternative ${i}`} · {miles(choice.distance / 1000)}</span></button>)}</div>}
          {route && <div className="zmap__routeinfo">
            {commuteNotice && <p role="status">{commuteNotice}</p>}
            <button type="button" disabled={stops.length !== 2 || stops.some(p => p.lat == null || p.lon == null)} onClick={() => {
              void api("POST", "/api/map/commute", {stops:stops.map(p=>({lat:p.lat,lon:p.lon}))}).then(()=>setCommuteNotice("Work commute saved for conversation."),e=>setError(errorText(e)));
            }}>Save work commute</button>
            <p className="zmap__routesum"><strong>{duration(route.duration)}</strong> · {miles(route.distance / 1000)} · arrive {arrive}</p>
            <small>{route.engine === "local" ? "Calculated on this PC" : "Calculated online"}. {routeTraffic}</small>
            <small>Blue: reported regular traffic · orange: slower · red: heavy. Dashed grey: unknown or stale traffic. WSDOT matching is approximate; ETA uses categorical traffic estimates with partial coverage.</small>
            {route.optimizationNote && <p className="zmap__warn">{route.optimizationNote}</p>}
            {routeAlerts.map(alert => <button key={alert.id} type="button" className="zmap__routealert" onClick={() => { goTo(alert.lat, alert.lon); setSelected({ kind: "alert", item: alert }); }}>⚠ {alert.headline}</button>)}
            <ol className="zmap__legs">
              {route.legs.map((leg, legIndex) => <li key={legIndex}>
                <h5>{LETTERS[legIndex]} → {LETTERS[legIndex + 1]} <small>{duration(leg.duration)} · {miles(leg.distance / 1000)}</small></h5>
                <ol>{leg.steps.map((step, i) => <li key={i}><button type="button" aria-current={previewIndex === route.legs.slice(0, legIndex).reduce((sum, item) => sum + item.steps.length, 0) + i ? "step" : undefined}
                  onClick={() => showStep(route.legs.slice(0, legIndex).reduce((sum, item) => sum + item.steps.length, 0) + i)}>
                  <span>{step.text}</span>{step.distance > 0 && <small>{step.distance < 400 ? `${Math.round(step.distance * 3.281 / 10) * 10} ft` : miles(step.distance / 1000)}</small>}</button></li>)}</ol>
              </li>)}
            </ol>
          </div>}
        </>}

        {tab === "weather" && <>
          <p className="zmap__search-state">Current conditions below are for {home.place || "your saved home"}. Alerts are checked near {position?"your location":"home"}; destination alerts cover the destination point, not every road along the route.</p>
          {destination && <section className="zmap__trip"><strong>Destination weather alerts</strong><p>{destinationWeather?.error || (!destinationWeather?"Checking destination…":destinationWeather.alerts.length?`${destinationWeather.alerts.length} alert(s) near the destination`:destinationWeather.source==="none"?"Unavailable":"No active alerts reported near the destination.")}</p>{destinationWeather?.updatedAt&&<small>{destinationWeather.source} · checked {ago(destinationWeather.updatedAt)}</small>}{destinationWeather?.alerts.map(alert=><p key={alert.id}>{alert.event}: {alert.headline}</p>)}</section>}
          {radarFrame && <p className="zmap__search-state">Radar observation: {ago(new Date(radarFrame.time*1000).toISOString())}. Radar is observed precipitation, not a forecast.</p>}
          <div className="zmap__wxnow">
            {now?.temperature != null ? <><strong>{Math.round(now.temperature)}°</strong><span>{capital(now.condition)}<small>{now.high != null && now.low != null ? `High ${Math.round(now.high)}° · low ${Math.round(now.low)}°` : ""}{now.feelsLike != null ? ` · feels ${Math.round(now.feelsLike)}°` : ""}</small></span></>
              : <span className="zmap__empty">Current weather isn't available right now.</span>}
          </div>
          <div className="zmap__railhead"><h4>Weather alerts</h4>
            <button type="button" className="zmap__textbtn" onClick={() => toggle("radar")}>{layers.radar ? "Hide radar" : "Show radar"}</button></div>
          {weather?.error && <p className="zmap__warn">{weather.error}{weather.updatedAt ? ` Showing alerts from ${ago(weather.updatedAt)}.` : ""}</p>}
          <ul className="zmap__list">
            {weather?.alerts.map(alert => <li key={alert.id}><button type="button" onClick={() => setSelected({ kind: "weather", item: alert })}>
              <span className="zmap__dot" style={{ background: SEVERITY_COLOR[alert.severity] ?? "#f2b84b" }}/>
              <strong>{alert.event}</strong><small>{alert.ends ? `Until ${new Date(alert.ends).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}` : alert.severity}</small></button></li>)}
            {weather && weather.source !== "none" && !weather.alerts.length && <li className="zmap__empty">No weather alerts reported for {home.place || "home"}.</li>}
          </ul>
          <p className="zmap__saved">{radarFrame ? `Radar from ${clock(new Date(radarFrame.time * 1000))}, refreshed every 5 minutes.` : "Radar loads when the PC is online."} Alerts: National Weather Service.</p>
        </>}

        {tab === "air" && <>
          <label className="zmap__check"><input type="checkbox" aria-label="Animate aircraft" checked={animateAircraft&&layers.planes} onChange={event=>{setAnimateAircraft(event.target.checked);if(event.target.checked)setLayers(current=>({...current,planes:true}));}}/> Animate aircraft</label>
          <p className="zmap__search-state">Reports refresh every 30 seconds. Moving markers are estimates from reported speed and heading, not continuous radar. Estimation stops after 45 seconds; stale markers fade after 60 seconds and disappear after 120. Reduced-motion settings show reported positions only.</p>
          {air?.updatedAt&&<p className="zmap__search-state">Feed observation: {ago(air.updatedAt)}</p>}
          <div className="zmap__railhead"><h4>Flights in view</h4>
            <button type="button" className="zmap__textbtn" onClick={() => toggle("planes")}>{layers.planes ? "Hide on map" : "Show on map"}</button></div>
          {air?.tooWide && <p className="zmap__warn">Zoom in to see flights (the free feed limits how wide an area it shows).</p>}
          {air?.error && <p className="zmap__warn">{air.error}</p>}
          <ul className="zmap__list">
            {planeList.map(plane => <li key={plane.id}><button type="button" onClick={() => { goTo(plane.lat, plane.lon, Math.max(view.z, 11)); setSelected({ kind: "plane", item: plane }); }}>
              <span className="zmap__dot zmap__dot--plane"/><strong>{plane.callsign || plane.id.toUpperCase()}</strong>
              <small>{plane.onGround ? "On the ground" : [plane.altitudeFt != null && `${plane.altitudeFt.toLocaleString()} ft`, plane.speedKt != null && `${plane.speedKt} kt`].filter(Boolean).join(" · ")} · {miles(km(view, plane))} · report {plane.positionAt?ago(plane.positionAt):"time unknown"}</small></button></li>)}
            {air && air.source !== "none" && !air.tooWide && !air.error && !planeList.length && <li className="zmap__empty">No flights reported in this area.</li>}
          </ul>
          <p className="zmap__saved">Flights: OpenSky Network. Motion is estimated between reports; coverage and observation age vary. Aircraft without a valid position timestamp remain stationary.</p>
        </>}

        {tab === "sea" && <>
          <div className="zmap__railhead"><h4>Vessels in view</h4><button type="button" className="zmap__textbtn" onClick={() => toggle("ships")}>{layers.ships ? "Hide on map" : "Show on map"}</button></div>
          {marine?.tooWide && <p className="zmap__warn">Zoom in to load ship positions for this area.</p>}
          {marine?.error && <p className="zmap__warn">{marine.error}</p>}
          <ul className="zmap__list">
            {marine?.ships.map(ship => <li key={ship.id}><button type="button" onClick={() => { goTo(ship.lat, ship.lon, Math.max(view.z, 12)); setSelected({ kind: "ship", item: ship }); }}>
              <span className="zmap__dot zmap__dot--ship"/><strong>{ship.name || ship.id}</strong>
              <small>{ship.speedKt != null ? `${ship.speedKt.toFixed(1)} kt · ` : ""}{ago(ship.updatedAt)}</small></button></li>)}
            {marine?.configured && !marine.tooWide && !marine.ships.length && <li className="zmap__empty">{marine.source === "live" ? "Waiting for AIS reports in this area." : "No current vessel positions available."}</li>}
            {!marine && <li className="zmap__empty">Checking the ship feed…</li>}
          </ul>
          <div className="zmap__marine-info"><p>Public AIS reports · {marine?.updatedAt ? `updated ${ago(marine.updatedAt)}` : "coverage varies"}. Some vessels do not broadcast; positions can be delayed.</p>
            <p>Live ship positions use a free <a href="https://aisstream.io/" target="_blank" rel="noopener noreferrer">AISStream account</a> with its key configured on the PC. The key stays on the server.</p></div>
        </>}

        <p className="zmap__saved">Saved on this PC: {home.saved.tiles.toLocaleString()} map tiles ({home.saved.megabytes} MB), {home.saved.landmarkAreas} landmark areas. Viewed places open offline.</p>
      </aside>
    </div>
  </div>;
}

export default MapPanel;
