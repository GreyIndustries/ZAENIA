"""Map tiles, landmarks and live traffic for LIFE > Map & traffic.

Local first (Grey, 2026-11-09: "less cloud work"):
- Map tiles (OpenStreetMap streets; USGS labelled imagery) come from the internet the first time an area is viewed, then from data/maps/tiles on this PC. Viewed areas
  keep working with no internet. Nothing is bulk-downloaded (OpenStreetMap's tile policy forbids it).
- Landmarks come from OpenStreetMap's Overpass API once per ~10 km square, then from data/maps/landmarks.
- Live traffic needs the internet: it uses the free WSDOT key ZAE already has (WSDOT_API_KEY) for highway alerts and
  traffic-flow sensors. The last good reading is saved, so offline the map shows it with its age.
No Google service and no paid key is used.
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "maps"
TILE_DIR = DATA_DIR / "tiles"
LANDMARK_DIR = DATA_DIR / "landmarks"
TRAFFIC_FILE = DATA_DIR / "traffic_last.json"
HOME_FILE = DATA_DIR / "home.json"

# Keyless public basemaps. Dark mode styles only the street imagery in the client;
# traffic, routes and markers retain their original colours. CARTO requires a key.
TILE_STYLES = {
    "clear": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "satellite": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/{z}/{y}/{x}",
    "labels": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",  # legacy request compatibility, not a satellite overlay
    "dark": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "standard": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
}
STYLE_MAX_ZOOM = {"satellite": 16}
TILE_CACHE_VERSION = "public-basemaps-v2"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
ALERTS_URL = "https://wsdot.wa.gov/Traffic/api/HighwayAlerts/HighwayAlertsREST.svc/GetAlertsAsJson"
FLOWS_URL = "https://wsdot.wa.gov/Traffic/api/TrafficFlow/TrafficFlowREST.svc/GetTrafficFlowsAsJson"
USER_AGENT = "ZAENIA/1.0 (single-user personal desktop assistant; tiles cached locally)"

MIN_ZOOM, MAX_ZOOM = 3, 18
TILE_REFRESH_SECONDS = 30 * 24 * 3600   # re-check a viewed tile at most monthly
LANDMARK_REFRESH_SECONDS = 90 * 24 * 3600
LANDMARK_CELL_ZOOM = 12                 # one cell is a z12 tile, about 10 km across here
MAX_LANDMARK_CELLS = 16
LANDMARK_FETCHES_PER_CALL = 3          # the page asks again for the rest, so no call runs long
TRAFFIC_CACHE_SECONDS = 180
DEFAULT_HOME = {"lat": 47.0343, "lon": -122.8232, "zoom": 12, "place": "Lacey"}

FLOW_LEVELS = {1: "clear", 2: "moderate", 3: "heavy", 4: "stop-and-go"}

_tile_slots = threading.BoundedSemaphore(2)   # OpenStreetMap asks clients to keep connections few
_landmark_lock = threading.Lock()
_traffic_lock = threading.Lock()
_traffic_cache: dict[str, Any] = {"at": 0.0, "data": None}


class MapUnavailable(Exception):
    """Nothing saved for this request and it couldn't be fetched (offline, or the source refused)."""


_map_http = threading.local()


def _http_get(url: str, *, params: dict[str, Any] | None = None, timeout: float = 15) -> Any:
    import requests
    session = getattr(_map_http, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        _map_http.session = session
    reply = session.get(url, params=params, timeout=timeout)
    reply.raise_for_status()
    return reply


def _http_post(url: str, *, data: dict[str, Any], timeout: float = 40) -> Any:
    import requests
    reply = requests.post(url, data=data, timeout=timeout, headers={"User-Agent": USER_AGENT})
    reply.raise_for_status()
    return reply


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.part")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


# ---- tiles

def valid_tile(z: int, x: int, y: int) -> bool:
    return MIN_ZOOM <= z <= MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z


def tile_mime(body: bytes) -> str:
    return "image/jpeg" if body.startswith(b"\xff\xd8") else "image/png"


def tile(z: int, x: int, y: int, style: str = "clear") -> tuple[bytes, str]:
    """PNG bytes and where they came from: "saved", "online" or "saved-old" (online refresh failed)."""
    if not valid_tile(z, x, y):
        raise ValueError("That map tile is outside the map.")
    if style not in TILE_STYLES or z > STYLE_MAX_ZOOM.get(style, MAX_ZOOM):
        raise ValueError("That map style isn't available at this zoom.")
    # Source-specific namespace: never reuse old CARTO warning images, including
    # offline fallback. Street/dark/legacy styles share the same OSM bytes/cache.
    cache_style = "standard" if style in {"clear", "dark", "standard", "labels"} else style
    path = TILE_DIR / TILE_CACHE_VERSION / cache_style / str(z) / str(x) / f"{y}.png"
    saved = path.read_bytes() if path.is_file() else None
    if saved is not None and time.time() - path.stat().st_mtime < TILE_REFRESH_SECONDS:
        return saved, "saved"
    try:
        with _tile_slots:
            reply = _http_get(TILE_STYLES[style].format(s="abcd"[(x + y) % 4], z=z, x=x, y=y), timeout=12)
        body = reply.content
        if not body.startswith((b"\x89PNG", b"\xff\xd8")):
            raise ValueError("not an image")
        _write_atomic(path, body)
        return body, "online"
    except Exception as error:
        if saved is not None:
            return saved, "saved-old"
        raise MapUnavailable("This part of the map hasn't been saved yet and the map server can't be reached.") from error


# ---- landmarks

def _lon_to_tile(lon: float, z: int) -> int:
    return max(0, min(2 ** z - 1, int((lon + 180.0) / 360.0 * 2 ** z)))


def _lat_to_tile(lat: float, z: int) -> int:
    lat = max(min(lat, 85.0511), -85.0511)
    rad = math.radians(lat)
    return max(0, min(2 ** z - 1, int((1.0 - math.asinh(math.tan(rad)) / math.pi) / 2.0 * 2 ** z)))


def _tile_bounds(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    """south, west, north, east of a tile."""
    def lat(row: int) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * row / 2 ** z))))
    return lat(y + 1), x / 2 ** z * 360.0 - 180.0, lat(y), (x + 1) / 2 ** z * 360.0 - 180.0


def _landmark_ranges(south: float, west: float, north: float, east: float) -> tuple[range, range]:
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("That map area isn't valid.")
    z = LANDMARK_CELL_ZOOM
    xs = range(_lon_to_tile(west, z), _lon_to_tile(east, z) + 1)
    ys = range(_lat_to_tile(north, z), _lat_to_tile(south, z) + 1)
    return xs, ys


def landmark_cells(south: float, west: float, north: float, east: float) -> list[tuple[int, int]]:
    xs, ys = _landmark_ranges(south, west, north, east)
    # Count before allocating: a world view contains millions of z12 cells.
    if len(xs) * len(ys) > MAX_LANDMARK_CELLS:
        raise ValueError("Zoom in to show landmarks in this area.")
    return [(x, y) for x in xs for y in ys]


def _overpass_query(south: float, west: float, north: float, east: float) -> str:
    box = f"({south:.5f},{west:.5f},{north:.5f},{east:.5f})"
    parts = [
        f'nwr["tourism"~"^(attraction|museum|viewpoint|zoo|aquarium|theme_park|gallery)$"]["name"]{box};',
        f'nwr["historic"~"^(monument|memorial|castle|ruins|lighthouse|fort|ship)$"]["name"]{box};',
        f'nwr["leisure"~"^(park|stadium|nature_reserve|marina)$"]["name"]{box};',
        f'nwr["amenity"~"^(hospital|university|college|library|townhall|courthouse|police|fire_station|ferry_terminal)$"]["name"]{box};',
        f'nwr["aeroway"="aerodrome"]["name"]{box};',
        f'node["natural"~"^(peak|volcano)$"]["name"]{box};',
        f'nwr["shop"="mall"]["name"]{box};',
    ]
    return "[out:json][timeout:25];(" + "".join(parts) + ");out center tags 400;"


def _kind(tags: dict[str, str]) -> str:
    for key in ("tourism", "historic", "aeroway", "natural", "amenity", "leisure", "shop"):
        if key in tags:
            value = tags[key]
            return {"aerodrome": "airport", "townhall": "city hall", "fire_station": "fire station",
                    "ferry_terminal": "ferry", "nature_reserve": "nature reserve", "theme_park": "theme park",
                    "college": "college", "mall": "mall"}.get(value, value.replace("_", " "))
    return "landmark"


def parse_overpass(data: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for element in data.get("elements") or []:
        tags = element.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        lat = element.get("lat", (element.get("center") or {}).get("lat"))
        lon = element.get("lon", (element.get("center") or {}).get("lon"))
        if not name or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        found.append({"id": f"{str(element.get('type', 'n'))[0]}{element.get('id')}", "name": name[:80],
                      "kind": _kind(tags), "lat": round(float(lat), 6), "lon": round(float(lon), 6)})
    return found


def _saved_cell(x: int, y: int) -> tuple[list[dict[str, Any]] | None, bool]:
    """Saved landmarks for a cell and whether they are still fresh."""
    path = LANDMARK_DIR / f"{LANDMARK_CELL_ZOOM}_{x}_{y}.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))["landmarks"]
        return saved, time.time() - path.stat().st_mtime < LANDMARK_REFRESH_SECONDS
    except (OSError, ValueError, KeyError, TypeError):
        return None, False


def _fetch_cell(x: int, y: int) -> list[dict[str, Any]]:
    reply = _http_post(OVERPASS_URL, data={"data": _overpass_query(*_tile_bounds(x, y, LANDMARK_CELL_ZOOM))})
    found = parse_overpass(reply.json())
    _write_atomic(LANDMARK_DIR / f"{LANDMARK_CELL_ZOOM}_{x}_{y}.json",
                  json.dumps({"savedAt": _now_iso(), "landmarks": found}).encode("utf-8"))
    return found


def landmarks(south: float, west: float, north: float, east: float) -> dict[str, Any]:
    """Named landmarks in the area. "pending": cells not fetched yet this call; "missing": cells unavailable offline."""
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("That map area isn't valid.")
    xs, ys = _landmark_ranges(south, west, north, east)
    if len(xs) * len(ys) > MAX_LANDMARK_CELLS:
        return {"landmarks": [], "missing": 0, "pending": 0, "tooWide": True}
    cells = landmark_cells(south, west, north, east)
    seen: dict[str, dict[str, Any]] = {}
    missing = pending = fetches = 0
    with _landmark_lock:   # one Overpass request at a time
        for x, y in cells:
            found, fresh = _saved_cell(x, y)
            if not fresh:
                if fetches < LANDMARK_FETCHES_PER_CALL:
                    fetches += 1
                    try:
                        found = _fetch_cell(x, y)
                    except Exception:
                        if found is None:
                            missing += 1
                elif found is None:
                    pending += 1
            for item in found or []:
                seen.setdefault(item["id"], item)
    inside = [item for item in seen.values() if south <= item["lat"] <= north and west <= item["lon"] <= east]
    return {"landmarks": inside, "missing": missing, "pending": pending, "tooWide": False}


# ---- traffic

_WSDOT_DATE = re.compile(r"/Date\((-?\d+)([+-]\d{4})?\)/")


def _wsdot_time(value: Any) -> str | None:
    match = _WSDOT_DATE.match(str(value or ""))
    if not match:
        return None
    return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc).isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _point(location: Any) -> tuple[float, float] | None:
    if not isinstance(location, dict):
        return None
    lat, lon = location.get("Latitude"), location.get("Longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or (lat == 0 and lon == 0):
        return None
    return round(float(lat), 6), round(float(lon), 6)


def parse_flows(raw: Any) -> list[dict[str, Any]]:
    flows = []
    for item in raw if isinstance(raw, list) else []:
        level = item.get("FlowReadingValue")
        location = item.get("FlowStationLocation") or {}
        point = _point(location)
        if level not in FLOW_LEVELS or point is None:
            continue
        flows.append({"id": str(item.get("FlowDataID")), "lat": point[0], "lon": point[1], "level": level,
                      "label": FLOW_LEVELS[level], "road": str(location.get("RoadName") or "").strip(),
                      "direction": str(location.get("Direction") or "").strip(),
                      "place": str(location.get("Description") or "").strip()[:120],
                      "milepost": location.get("MilePost") if isinstance(location.get("MilePost"), (int, float)) else None})
    return flows


def parse_alerts(raw: Any) -> list[dict[str, Any]]:
    alerts = []
    for item in raw if isinstance(raw, list) else []:
        start = item.get("StartRoadwayLocation") or {}
        point = _point(start)
        if point is None:
            continue
        end = _point(item.get("EndRoadwayLocation"))
        alerts.append({"id": str(item.get("AlertID")), "lat": point[0], "lon": point[1],
                       "endLat": end[0] if end else None, "endLon": end[1] if end else None,
                       "headline": str(item.get("HeadlineDescription") or "").strip()[:400],
                       "category": str(item.get("EventCategory") or "").strip(),
                       "priority": str(item.get("Priority") or "").strip(),
                       "road": str(start.get("RoadName") or "").strip(),
                       "start": _wsdot_time(item.get("StartTime")), "updated": _wsdot_time(item.get("LastUpdatedTime"))})
    return alerts


def _saved_traffic() -> dict[str, Any] | None:
    try:
        return json.loads(TRAFFIC_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def traffic(force: bool = False) -> dict[str, Any]:
    with _traffic_lock:
        cached = _traffic_cache["data"]
        if cached is not None and not force and time.monotonic() - _traffic_cache["at"] < TRAFFIC_CACHE_SECONDS:
            return cached
        key = os.getenv("WSDOT_API_KEY", "").strip()
        error = None
        if not key:
            error = "Live traffic needs the free WSDOT key (WSDOT_API_KEY) set for the ZAE server."
        else:
            try:
                flows = parse_flows(_http_get(FLOWS_URL, params={"AccessCode": key}, timeout=20).json())
                alerts = parse_alerts(_http_get(ALERTS_URL, params={"AccessCode": key}, timeout=20).json())
                data = {"source": "live", "updatedAt": _now_iso(), "flows": flows, "alerts": alerts, "error": None}
                _write_atomic(TRAFFIC_FILE, json.dumps(data).encode("utf-8"))
                _traffic_cache.update(at=time.monotonic(), data=data)
                return data
            except Exception:
                error = "WSDOT traffic can't be reached right now."
        saved = _saved_traffic() or {"updatedAt": None, "flows": [], "alerts": []}
        data = {**saved, "source": "saved" if saved.get("updatedAt") else "none", "error": error}
        # Retry a failed source sooner than a good one.
        _traffic_cache.update(at=time.monotonic() - TRAFFIC_CACHE_SECONDS + 60, data=data)
        return data


# ---- traffic drawn along the roads

SEGMENTS_FILE = DATA_DIR / "flow_segments.json"
SEGMENT_MAX_KM = 4.0
_segment_lock = threading.Lock()
_segment_state: dict[str, Any] = {"running": False, "data": None}


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = math.pi / 180
    h = math.sin((b[0] - a[0]) * r / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def segment_pairs(flows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Neighbouring sensors on the same road and direction, in the direction traffic moves."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for flow in flows:
        if flow.get("milepost") is not None and flow.get("road"):
            groups.setdefault((flow["road"], flow.get("direction", "")), []).append(flow)
    pairs = []
    for (_, direction), members in groups.items():
        members.sort(key=lambda flow: flow["milepost"], reverse=direction.upper().startswith(("S", "W")))
        for a, b in zip(members, members[1:]):
            if _km((a["lat"], a["lon"]), (b["lat"], b["lon"])) <= SEGMENT_MAX_KM:
                pairs.append((a, b))
    return pairs


def _load_segments() -> dict[str, Any]:
    if _segment_state["data"] is None:
        try:
            _segment_state["data"] = json.loads(SEGMENTS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _segment_state["data"] = {}
    return _segment_state["data"]


def _build_segments(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> None:
    """Road shapes between sensors from the PC's own routing engine; done once and saved."""
    from core.maps.live import _gh_path
    try:
        segments = _load_segments()
        for index, (a, b) in enumerate(pairs):
            key = f"{a['id']}>{b['id']}"
            if key in segments:
                continue
            try:
                path = _gh_path([{"lat": a["lat"], "lon": a["lon"]}, {"lat": b["lat"], "lon": b["lon"]}])
                line = [[round(lat, 5), round(lon, 5)] for lon, lat, *_ in (path.get("points") or {}).get("coordinates", [])]
                # A detour far longer than the straight gap means the sensors weren't on one carriageway: draw it straight.
                if not line or path.get("distance", 0) > 2.5 * 1000 * _km((a["lat"], a["lon"]), (b["lat"], b["lon"])) + 300:
                    line = [[a["lat"], a["lon"]], [b["lat"], b["lon"]]]
            except ValueError:
                line = [[a["lat"], a["lon"]], [b["lat"], b["lon"]]]
            segments[key] = line
            if index % 100 == 99:
                _write_atomic(SEGMENTS_FILE, json.dumps(segments).encode("utf-8"))
        _write_atomic(SEGMENTS_FILE, json.dumps(segments).encode("utf-8"))
    except Exception:
        pass   # the local engine is off: try again on a later request
    finally:
        _segment_state["running"] = False


def traffic_segments() -> dict[str, Any]:
    """Road-shaped lines between neighbouring WSDOT sensors, keyed "fromId>toId". The page colours them from /traffic."""
    flows = (traffic() or {}).get("flows") or []
    pairs = segment_pairs(flows)
    with _segment_lock:
        segments = _load_segments()
        missing = [pair for pair in pairs if f"{pair[0]['id']}>{pair[1]['id']}" not in segments]
        if missing and not _segment_state["running"]:
            _segment_state["running"] = True
            threading.Thread(target=_build_segments, args=(missing,), name="zae-traffic-segments", daemon=True).start()
    wanted = {f"{a['id']}>{b['id']}" for a, b in pairs}
    return {"segments": [{"id": key, "from": key.split(">")[0], "to": key.split(">")[1], "line": line}
                         for key, line in list(segments.items()) if key in wanted],
            "pending": len(missing)}


# ---- home and cache

def _folder_stats(folder: Path, pattern: str) -> tuple[int, int]:
    count = size = 0
    if folder.is_dir():
        for path in folder.rglob(pattern):
            count += 1
            try:
                size += path.stat().st_size
            except OSError:
                pass
    return count, size


def home() -> dict[str, Any]:
    """Where the map opens: data/maps/home.json if Grey set one, else the weather location, else Lacey."""
    place = dict(DEFAULT_HOME)
    try:
        saved = json.loads(HOME_FILE.read_text(encoding="utf-8"))
        if isinstance(saved.get("lat"), (int, float)) and isinstance(saved.get("lon"), (int, float)):
            place.update({k: saved[k] for k in ("lat", "lon", "zoom", "place") if k in saved})
    except (OSError, ValueError):
        try:
            from core.weather.weather_selector import select_weather_location
            location = select_weather_location()
            if isinstance(location.get("latitude"), (int, float)) and isinstance(location.get("longitude"), (int, float)):
                place.update(lat=location["latitude"], lon=location["longitude"],
                             place=re.sub(r"^in\s+", "", str(location.get("display_label") or location.get("name") or place["place"])))
        except Exception:
            pass
    tiles, tile_bytes = _folder_stats(TILE_DIR, "*.png")
    cells, _ = _folder_stats(LANDMARK_DIR, "*.json")
    return {**place, "saved": {"tiles": tiles, "megabytes": round(tile_bytes / 1_048_576, 1), "landmarkAreas": cells}}
