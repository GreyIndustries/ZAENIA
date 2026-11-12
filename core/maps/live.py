"""Live layers and directions for LIFE > Map & traffic (Grey, 2026-11-09).

All free, no paid key:
- Directions with several stops: the local GraphHopper engine on this PC first (127.0.0.1:8989, Washington roads,
  started by scripts/start_routing.ps1), so routes work offline and never leave the PC. If it isn't running, the
  public OSRM demo server (router.project-osrm.org, fair use) answers instead and the reply says "online".
- Place search: explicit submitted queries only, saved landmarks first, then a configurable Nominatim provider
  (max one request a second); location-scoped answers are saved. No autocomplete requests.
- Weather: National Weather Service alerts (api.weather.gov) and RainViewer radar frames.
- Air traffic: OpenSky Network, anonymous (rate limited, so replies are cached for 20 seconds).
Weather alerts can use their last saved reply. Radar and aircraft use bounded short-lived memory caches;
unavailable live sources return an explicit unavailable state rather than fabricated data.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
import ipaddress
import os
import threading
import time
from collections import OrderedDict
from typing import Any
from urllib.parse import urlsplit

from core.maps.service import DATA_DIR, LANDMARK_DIR, _http_get, _now_iso, _write_atomic

ROUTING_URL = os.getenv("ZAE_ROUTING_URL", "https://router.project-osrm.org").rstrip("/")
LOCAL_ROUTING_URL = os.getenv("ZAE_LOCAL_ROUTING_URL", "http://127.0.0.1:8989").rstrip("/")
# Public Nominatim is only for explicit submitted searches, never autocomplete.
# Its endpoint can be replaced without changing code (including a local instance).
NOMINATIM_URL = os.getenv("ZAE_GEOCODING_URL", "https://nominatim.openstreetmap.org/search").strip()
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
RAINVIEWER_URL = "https://api.rainviewer.com/public/weather-maps.json"
OPENSKY_URL = "https://opensky-network.org/api/states/all"
PLACES_FILE = DATA_DIR / "places.json"
MAX_STOPS = 12
RADAR_MAX_ZOOM = 7
RADAR_TILE_HOST = "https://tilecache.rainviewer.com"
CACHE_MAX_ENTRIES = 192
CACHE_MAX_BYTES = 32 * 1024 * 1024
ROUTE_BUDGET_SECONDS = 35.0
OPTIMIZATION_BUDGET_SECONDS = 8.0

_cache: OrderedDict[str, tuple[float, Any, int]] = OrderedDict()
_cache_lock = threading.Lock()
_nominatim_lock = threading.Lock()
_nominatim_last = [0.0]


def _cached(key: str, seconds: float, load: Any) -> Any:
    with _cache_lock:
        now = time.monotonic()
        for expired in [entry for entry, hit in _cache.items() if hit[0] <= now]:
            _cache.pop(expired, None)
        hit = _cache.get(key)
        if hit:
            _cache.move_to_end(key)
            return hit[1]
    value = load()
    # Byte payloads dominate radar memory. Serialized JSON is a conservative
    # estimate for these small dictionary/list replies, not a process RAM meter.
    size = len(value) if isinstance(value, bytes) else len(json.dumps(value).encode("utf-8")) * 2 + 64
    with _cache_lock:
        now = time.monotonic()
        for expired in [entry for entry, hit in _cache.items() if hit[0] <= now]:
            _cache.pop(expired, None)
        if size <= CACHE_MAX_BYTES:
            _cache[key] = (now + seconds, value, size)
            _cache.move_to_end(key)
            while len(_cache) > CACHE_MAX_ENTRIES or sum(hit[2] for hit in _cache.values()) > CACHE_MAX_BYTES:
                _cache.popitem(last=False)
    return value


def _saved(name: str) -> Any:
    try:
        return json.loads((DATA_DIR / "live" / f"{name}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(name: str, value: Any) -> None:
    try:
        _write_atomic(DATA_DIR / "live" / f"{name}.json", json.dumps(value).encode("utf-8"))
    except OSError:
        pass


# ---- directions

class RoutingBudgetExceeded(TimeoutError):
    """Stop allocating more routing requests when this attempt's budget expires."""


def _remaining_timeout(deadline: float | None, maximum: float) -> float:
    if deadline is None:
        return maximum
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RoutingBudgetExceeded("The route calculation exceeded its time budget.")
    return min(maximum, remaining)


def _routing_is_local(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False

def _maneuver_text(step: dict[str, Any]) -> str:
    maneuver = step.get("maneuver") or {}
    kind, modifier = maneuver.get("type", ""), maneuver.get("modifier") or ""
    road = step.get("name") or step.get("ref") or ""
    onto = f" onto {road}" if road else ""
    if kind == "depart":
        bearing = maneuver.get("bearing_after")
        return f"Head {_compass(bearing) if isinstance(bearing, (int, float)) else 'out'}{' on ' + road if road else ''}"
    if kind == "arrive":
        side = f" on the {modifier}" if modifier in ("left", "right") else ""
        return f"Arrive at your stop{side}"
    if kind in ("roundabout", "rotary"):
        exit_number = maneuver.get("exit")
        return f"At the roundabout, take the {_ordinal(exit_number)} exit{onto}" if exit_number else f"Go through the roundabout{onto}"
    if kind in ("on ramp", "off ramp"):
        return f"Take the {'ramp' if kind == 'on ramp' else 'exit'}{(' ' + modifier) if modifier else ''}{onto}"
    if kind == "merge":
        return f"Merge{(' ' + modifier) if modifier else ''}{onto}"
    if kind == "fork":
        return f"Keep {modifier or 'straight'} at the fork{onto}"
    if kind == "end of road":
        return f"At the end of the road, turn {modifier or 'ahead'}{onto}"
    if kind in ("continue", "new name"):
        return f"Continue{onto}" if road else "Continue straight"
    if modifier == "uturn":
        return f"Make a U-turn{onto}"
    if modifier == "straight":
        return f"Go straight{onto}"
    return f"Turn {modifier}{onto}" if modifier else f"Continue{onto}"


def _compass(bearing: float) -> str:
    return ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"][int((bearing + 22.5) % 360 // 45)]


def _ordinal(number: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(number, f"{number}th")


def _check_stops(stops: list[dict[str, float]]) -> str:
    if not 2 <= len(stops) <= MAX_STOPS:
        raise ValueError(f"A route needs between 2 and {MAX_STOPS} stops.")
    points = []
    for stop in stops:
        lat, lon = float(stop["lat"]), float(stop["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("One of the stops isn't a real place.")
        points.append(f"{lon:.6f},{lat:.6f}")
    return ";".join(points)


def _online_route(stops: list[dict[str, float]], best_order: bool = False, *, deadline: float | None = None, alternatives: bool = False) -> dict[str, Any]:
    """OSRM: driving route through the stops in order (or the quickest order, keeping the first and last stop)."""
    coordinates = _check_stops(stops)
    params: dict[str, Any] = {"overview": "full", "geometries": "geojson", "steps": "true"}
    if best_order and len(stops) > 2:
        url = f"{ROUTING_URL}/trip/v1/driving/{coordinates}"
        params.update(source="first", destination="last", roundtrip="false")
    else:
        url = f"{ROUTING_URL}/route/v1/driving/{coordinates}"
    if alternatives and len(stops) == 2:
        params["alternatives"] = "true"
    try:
        data = _http_get(url, params=params, timeout=_remaining_timeout(deadline, 25)).json()
    except Exception as error:
        raise ConnectionError("Directions can't be worked out right now: the routing server can't be reached.") from error
    if data.get("code") != "Ok":
        raise ValueError("No driving route connects those stops.")
    best = (data.get("trips") or data.get("routes") or [None])[0]
    if not best:
        raise ValueError("No driving route connects those stops.")
    order = list(range(len(stops)))
    if data.get("waypoints") and best_order:
        order = [index for index, _ in sorted(enumerate(data["waypoints"]), key=lambda pair: pair[1].get("waypoint_index", pair[0]))]
    result = _osrm_path(best, order)
    if alternatives:
        result["alternatives"] = [_osrm_path(path, order) for path in (data.get("routes") or [])[1:3]]
    return result


def _osrm_path(best: dict[str, Any], order: list[int]) -> dict[str, Any]:
    legs = []
    for leg in best.get("legs") or []:
        steps = [{"text": _maneuver_text(step), "distance": round(step.get("distance", 0)), "duration": round(step.get("duration", 0)),
                  "lat": (step.get("maneuver") or {}).get("location", [0, 0])[1], "lon": (step.get("maneuver") or {}).get("location", [0, 0])[0]}
                 for step in leg.get("steps") or []]
        legs.append({"distance": round(leg.get("distance", 0)), "duration": round(leg.get("duration", 0)), "steps": steps})
    line = [[round(lat, 6), round(lon, 6)] for lon, lat in (best.get("geometry") or {}).get("coordinates", [])]
    return {"distance": round(best.get("distance", 0)), "duration": round(best.get("duration", 0)), "line": line, "legs": legs,
            "order": order, "engine": "local" if _routing_is_local(ROUTING_URL) else "online"}


GH_TURNS = {-98: "Make a U-turn", -8: "Make a U-turn", -7: "Keep left", -3: "Turn sharp left", -2: "Turn left", -1: "Turn slightly left",
            0: "Continue", 1: "Turn slightly right", 2: "Turn right", 3: "Turn sharp right", 7: "Keep right", 8: "Make a U-turn"}


def _gh_path(stops: list[dict[str, float]], *, timeout: float = 20, alternatives: bool = False) -> dict[str, Any]:
    params = [("point", f"{float(s['lat']):.6f},{float(s['lon']):.6f}") for s in stops]
    params += [("profile", "car"), ("points_encoded", "false"), ("instructions", "true"), ("locale", "en")]
    if alternatives and len(stops) == 2:
        params += [("algorithm", "alternative_route")]
    data = _http_get(f"{LOCAL_ROUTING_URL}/route", params=params, timeout=timeout).json()   # type: ignore[arg-type]
    paths = data.get("paths") or []
    if not paths:
        raise ValueError(data.get("message") or "No driving route connects those stops.")
    return {**paths[0], "_alternatives": paths[1:3]} if alternatives else paths[0]


def _local_route(stops: list[dict[str, float]], *, deadline: float | None = None, alternatives: bool = False) -> dict[str, Any]:
    kwargs = {"alternatives": True} if alternatives else {}
    path = _gh_path(stops, timeout=_remaining_timeout(deadline, 20), **kwargs)
    result = _gh_result(path, len(stops))
    if alternatives:
        result["alternatives"] = [_gh_result(option, len(stops)) for option in path.get("_alternatives", [])]
    return result


def _gh_result(path: dict[str, Any], stop_count: int) -> dict[str, Any]:
    coordinates = (path.get("points") or {}).get("coordinates") or []
    legs: list[dict[str, Any]] = [{"distance": 0, "duration": 0, "steps": []}]
    for item in path.get("instructions") or []:
        start = coordinates[item.get("interval", [0])[0]] if coordinates else [0, 0]
        sign = item.get("sign", 0)
        text = str(item.get("text") or GH_TURNS.get(sign, "Continue"))
        if sign in (4, 5):
            text = "Arrive at your stop"
        leg = legs[-1]
        leg["steps"].append({"text": text, "distance": round(item.get("distance", 0)), "duration": round(item.get("time", 0) / 1000),
                             "lat": round(start[1], 6), "lon": round(start[0], 6)})
        leg["distance"] += round(item.get("distance", 0))
        leg["duration"] += round(item.get("time", 0) / 1000)
        if sign == 5:   # a stop along the way: the next leg starts here
            legs.append({"distance": 0, "duration": 0, "steps": []})
    return {"distance": round(path.get("distance", 0)), "duration": round(path.get("time", 0) / 1000),
            "line": [[round(lat, 6), round(lon, 6)] for lon, lat, *_ in coordinates], "legs": legs,
            "order": list(range(stop_count)), "engine": "local"}


def _local_best_order(stops: list[dict[str, float]], *, deadline: float | None = None) -> list[int]:
    """Quickest visiting order keeping the first and last stop, from local drive times between every pair of stops."""
    import itertools
    if deadline is None:
        deadline = time.monotonic() + OPTIMIZATION_BUDGET_SECONDS
    count = len(stops)
    cost = [[0.0] * count for _ in range(count)]
    for a in range(count):
        for b in range(count):
            if a != b and b != 0 and a != count - 1:
                timeout = _remaining_timeout(deadline, 4)
                # Pair times can be reused when the owner retries a plan. They
                # use the same bounded cache as other live replies.
                start, end = stops[a], stops[b]
                key = f"drive-time:{start['lat']:.6f},{start['lon']:.6f}:{end['lat']:.6f},{end['lon']:.6f}"
                cost[a][b] = float(_cached(key, 60, lambda: _gh_path([start, end], timeout=timeout).get("time", 0)))
    middle = list(range(1, count - 1))

    def total(order: list[int]) -> float:
        return sum(cost[order[i]][order[i + 1]] for i in range(len(order) - 1))
    if len(middle) <= 8:
        best = min(itertools.permutations(middle), key=lambda option: total([0, *option, count - 1]))
        _remaining_timeout(deadline, 1)
        return [0, *best, count - 1]
    order, left = [0], set(middle)   # nearest next stop, then swap pairs while it helps
    while left:
        nearest = min(left, key=lambda stop: cost[order[-1]][stop])
        order.append(nearest)
        left.remove(nearest)
    order.append(count - 1)
    improved = True
    while improved:
        _remaining_timeout(deadline, 1)
        improved = False
        for i in range(1, count - 2):
            for j in range(i + 1, count - 1):
                option = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if total(option) < total(order):
                    order, improved = option, True
    return order


def route(stops: list[dict[str, float]], best_order: bool = False, alternatives: bool = False) -> dict[str, Any]:
    """Driving route through the stops: on this PC when the local engine runs, otherwise online."""
    _check_stops(stops)
    started = time.monotonic()
    deadline = started + ROUTE_BUDGET_SECONDS
    note = None
    optimized = best_order and len(stops) > 2
    order = list(range(len(stops)))
    try:
        if optimized:
            try:
                order = _local_best_order(stops, deadline=min(deadline, started + OPTIMIZATION_BUDGET_SECONDS))
            except RoutingBudgetExceeded:
                optimized = False
                note = "Stop-order optimization reached its time budget. This route uses your entered stop order."
        options = {"alternatives": True} if alternatives and len(stops) == 2 else {}
        result = _local_route([stops[index] for index in order], deadline=deadline, **options)
        result["order"] = order
    except Exception:
        # A local extract may not contain the requested road. The existing
        # online fallback covers that case as well as an unavailable engine.
        options = {"alternatives": True} if alternatives and len(stops) == 2 else {}
        result = _online_route(stops, best_order=optimized, deadline=deadline, **options)
    result["optimized"] = optimized
    result["optimizationNote"] = note
    return result


# ---- place search

def _load_places() -> dict[str, Any]:
    try:
        value = json.loads(PLACES_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def search_places(query: str, near_lat: float, near_lon: float) -> dict[str, Any]:
    text = " ".join(query.split()).strip()
    if len(text) < 2:
        return {"places": [], "source": "none"}
    if not (-90 <= near_lat <= 90 and -180 <= near_lon <= 180) or len(text) > 120:
        raise ValueError("Use a valid map location and a search of at most 120 characters.")
    lowered = text.lower()
    # The same business name in a different town must not reuse the old town's
    # answer. Legacy query-only entries are deliberately not used as matches.
    cache_key = f"v2:{near_lat:.2f},{near_lon:.2f}:{lowered}"
    local: list[dict[str, Any]] = []
    if LANDMARK_DIR.is_dir():
        for path in LANDMARK_DIR.glob("*.json"):
            try:
                for item in json.loads(path.read_text(encoding="utf-8")).get("landmarks", []):
                    if lowered in item["name"].lower():
                        local.append({"name": item["name"], "detail": item["kind"], "lat": item["lat"], "lon": item["lon"]})
            except (OSError, ValueError, KeyError, TypeError):
                continue
    try:
        with _nominatim_lock:   # Explicit searches only; never typeahead/autocomplete.
            saved = _load_places()
            if isinstance(saved.get(cache_key), list):
                return {"places": (local + saved[cache_key])[:8], "source": "saved"}
            endpoint = urlsplit(NOMINATIM_URL)
            if not endpoint.hostname or endpoint.username or endpoint.password or endpoint.fragment:
                raise ValueError("No valid geocoding provider is configured.")
            if endpoint.scheme != "https" and not (endpoint.scheme == "http" and _routing_is_local(NOMINATIM_URL)):
                raise ValueError("Geocoding requires HTTPS or a local provider.")
            wait = 1.05 - (time.monotonic() - _nominatim_last[0])
            if wait > 0:
                time.sleep(wait)
            box = f"{max(-180, near_lon - 1.5)},{min(90, near_lat + 1)},{min(180, near_lon + 1.5)},{max(-90, near_lat - 1)}"
            # Failed requests count toward the start-rate limit too.
            _nominatim_last[0] = time.monotonic()
            reply = _http_get(NOMINATIM_URL, params={"q": text, "format": "jsonv2", "limit": 6, "viewbox": box,
                                                     "addressdetails": 0, "countrycodes": "us"}, timeout=12).json()
            found = []
            for item in reply if isinstance(reply, list) else []:
                try:
                    lat, lon = float(item["lat"]), float(item["lon"])
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                except (KeyError, TypeError, ValueError):
                    continue
                found.append({"name": str(item.get("name") or item.get("display_name", "")).strip()[:80],
                              "detail": str(item.get("display_name", ""))[:160], "lat": round(lat, 6), "lon": round(lon, 6)})
            saved[cache_key] = found
            while len(saved) > 2000:
                saved.pop(next(iter(saved)))
            _write_atomic(PLACES_FILE, json.dumps(saved).encode("utf-8"))
        return {"places": (local + found)[:8], "source": "online"}
    except Exception:
        return {"places": local[:8], "source": "saved" if local else "offline"}


# Search-as-you-type uses Photon, not public Nominatim (which forbids it).
# The public demo is for light personal use; configurable loopback hosting keeps
# this usable without depending on a public service. Never accept a URL from clients.
PHOTON_URL = os.getenv("ZAE_PHOTON_URL", "https://photon.komoot.io/api/").strip()
_photon_lock = threading.Lock()
_photon_last = [0.0]


def suggest_places(query: str, near_lat: float, near_lon: float) -> dict[str, Any]:
    text = " ".join(query.split())
    if not (-90 <= near_lat <= 90 and -180 <= near_lon <= 180) or len(text) > 120:
        raise ValueError("Use a valid location and a search of at most 120 characters.")
    if len(text) < 3:
        return {"places": [], "source": "none"}
    key = f"photon:{near_lat:.2f},{near_lon:.2f}:{text.casefold()}"

    def load() -> dict[str, Any]:
        try:
            endpoint = urlsplit(PHOTON_URL)
            if not endpoint.hostname or endpoint.username or endpoint.password or endpoint.fragment:
                raise ValueError("Invalid suggestion provider.")
            if endpoint.scheme != "https" and not (endpoint.scheme == "http" and _routing_is_local(PHOTON_URL)):
                raise ValueError("Suggestions require HTTPS or loopback.")
            # Do not queue obsolete keystrokes behind an in-flight provider call.
            if not _photon_lock.acquire(blocking=False):
                return {"places": [], "source": "busy"}
            try:
                if time.monotonic() - _photon_last[0] < 1.0:
                    return {"places": [], "source": "busy"}
                _photon_last[0] = time.monotonic()
                data = _http_get(PHOTON_URL, params={"q": text, "lat": round(near_lat, 2),
                                  "lon": round(near_lon, 2), "limit": 6}, timeout=5).json()
            finally:
                _photon_lock.release()
            places, seen = [], set()
            for item in (data.get("features") or [])[:12]:
                try:
                    lon, lat = map(float, item["geometry"]["coordinates"][:2])
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                    props = item.get("properties") or {}
                    name = str(props.get("name") or props.get("street") or props.get("city") or "Place")[:100]
                    detail = ", ".join(str(props[k]) for k in ("housenumber", "street", "city", "state", "postcode", "country") if props.get(k))[:220]
                    identity = (name, lat, lon)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    places.append({"name": name, "detail": detail, "lat": lat, "lon": lon})
                except (ValueError, TypeError, KeyError):
                    continue
            return {"places": places[:6], "source": "photon"}
        except Exception:
            return {"places": [], "source": "offline"}

    # Short-lived, bounded RAM only: no keystroke history saved to disk.
    with _cache_lock:
        previous = _cache.get(key)
        if previous and previous[0] > time.monotonic():
            return previous[1]
    result = load()
    if result["source"] == "photon":
        return _cached(key, 300, lambda: result)
    return result


# ---- weather

def weather_alerts(lat: float, lon: float) -> dict[str, Any]:
    key = f"{lat:.2f},{lon:.2f}"

    def load() -> dict[str, Any]:
        try:
            reply = _http_get(NWS_ALERTS_URL, params={"point": key}, timeout=15).json()
            alerts = []
            for feature in reply.get("features") or []:
                props = feature.get("properties") or {}
                geometry = feature.get("geometry") or {}
                rings = geometry.get("coordinates") if geometry.get("type") == "Polygon" else None
                alerts.append({"id": str(props.get("id") or feature.get("id")), "event": props.get("event", ""),
                               "severity": props.get("severity", ""), "headline": (props.get("headline") or "")[:300],
                               "instruction": (props.get("instruction") or "")[:600], "ends": props.get("ends") or props.get("expires"),
                               "area": (props.get("areaDesc") or "")[:200],
                               "polygon": [[round(p[1], 4), round(p[0], 4)] for p in rings[0]] if rings else None})
            data = {"source": "live", "updatedAt": _now_iso(), "alerts": alerts, "error": None}
            _save(f"weather_alerts_{key}", data)
            return data
        except Exception:
            saved = _saved(f"weather_alerts_{key}") or {"updatedAt": None, "alerts": []}
            return {**saved, "source": "saved" if saved.get("updatedAt") else "none", "error": "Weather alerts can't be reached right now."}
    return _cached(f"nws:{key}", 300, load)


def radar_frames() -> dict[str, Any]:
    """Latest RainViewer radar frames; the page draws them as a map layer (zoomed past 7, tiles are stretched)."""
    def load() -> dict[str, Any]:
        try:
            reply = _http_get(RAINVIEWER_URL, timeout=12).json()
            frames = [{"time": frame["time"], "path": frame["path"]} for frame in (reply.get("radar") or {}).get("past", [])[-6:]]
            data = {"source": "live", "host": RADAR_TILE_HOST, "frames": frames, "maxZoom": RADAR_MAX_ZOOM}
            return data
        except Exception:
            return {"source": "none", "host": "", "frames": [], "maxZoom": RADAR_MAX_ZOOM}
    return _cached("radar", 300, load)


def radar_tile(path: str, z: int, x: int, y: int) -> bytes:
    if not path.startswith("/v2/radar/") or ".." in path or not all(c.isalnum() or c in "/_-" for c in path):
        raise ValueError("That radar frame isn't valid.")
    if not 0 <= z <= RADAR_MAX_ZOOM or not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise ValueError("That radar tile is outside the map.")
    def load() -> bytes:
        # Manifest content is untrusted data, not permission to fetch arbitrary
        # hosts on the PC's network. The official tile endpoint is fixed here.
        body = _http_get(f"{RADAR_TILE_HOST}{path}/256/{z}/{x}/{y}/2/1_1.png", timeout=12).content
        if not body.startswith(b"\x89PNG"):
            raise ValueError("not a PNG")
        return body
    return _cached(f"radar:{path}:{z}:{x}:{y}", 600, load)


# ---- air traffic

def aircraft(south: float, west: float, north: float, east: float) -> dict[str, Any]:
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("That map area isn't valid.")
    if (north - south) * (east - west) > 25:   # about 400 x 300 km; wider views cost more of OpenSky's free credits
        return {"source": "none", "planes": [], "tooWide": True, "error": None}
    box = tuple(round(value * 4) / 4 for value in (south, west, north, east))   # quarter-degree boxes share a cache entry
    south, west, north, east = box[0] - 0.25, box[1] - 0.25, box[2] + 0.25, box[3] + 0.25

    def load() -> dict[str, Any]:
        try:
            reply = _http_get(OPENSKY_URL, params={"lamin": south, "lomin": west, "lamax": north, "lomax": east}, timeout=15).json()
            planes = []
            def number(value: Any, minimum: float, maximum: float) -> float | None:
                return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and minimum <= value <= maximum else None
            def stamp(value: Any) -> str | None:
                seconds = number(value, 1, time.time() + 5)
                return datetime.fromtimestamp(seconds, timezone.utc).isoformat() if seconds is not None else None
            for state in (reply.get("states") or [])[:2000]:
                if not isinstance(state, list) or len(state) < 17 or number(state[5], -180, 180) is None or number(state[6], -90, 90) is None:
                    continue
                altitude = number(state[13], -2000, 30000) if state[13] is not None else number(state[7], -2000, 30000)
                speed = number(state[9], 0, 600)
                heading = number(state[10], 0, 360)
                climb = number(state[11], -200, 200)
                planes.append({"id": str(state[0])[:32], "callsign": str(state[1] or "").strip()[:32], "country": str(state[2] or "")[:80],
                                 "positionAt": stamp(state[3]), "lastContactAt": stamp(state[4]),
                               "lat": round(state[6], 5), "lon": round(state[5], 5), "onGround": bool(state[8]),
                               "altitudeFt": round(altitude * 3.28084) if altitude is not None else None,
                               "speedKt": round(speed * 1.94384) if speed is not None else None,
                               "heading": round(heading) % 360 if heading is not None else None,
                               "climbFpm": round(climb * 196.85) if climb is not None else None, "squawk": state[14]})
            return {"source": "live", "updatedAt": stamp(reply.get("time")), "fetchedAt": _now_iso(), "planes": planes, "tooWide": False, "error": None}
        except Exception:
            return {"source": "none", "updatedAt": None, "planes": [], "tooWide": False,
                    "error": "OpenSky can't be reached right now (its free access is rate limited)."}
    return _cached(f"air:{box}", 20, load)
