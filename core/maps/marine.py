"""Public AIS positions for the map: server-only, bounded and RAM-only.

Importing this module opens no network connection. A configured, explicit map
request leases a single worker for 90 seconds. AIS coverage is incomplete and
must not be presented as a complete military/naval picture or safe navigation.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

STREAM_URL = "wss://stream.aisstream.io/v0/stream"
MESSAGE_TYPES = ("PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport",
                 "ShipStaticData", "StaticDataReport")
TTL_SECONDS, LEASE_SECONDS, UPDATE_SECONDS, MAX_SHIPS = 300, 90, 15, 500
Bounds = tuple[float, float, float, float]


def _bounds(south: float, west: float, north: float, east: float) -> Bounds:
    values = (south, west, north, east)
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in values):
        raise ValueError("AIS map bounds must be finite coordinates.")
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("AIS map bounds must be ordered and cannot cross the date line.")
    return tuple(float(v) for v in values)


def _number(value: Any, low: float, high: float, *, exclusive_high: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value) if low <= value and (value < high if exclusive_high else value <= high) else None


def _text(value: Any, limit: int = 120) -> str:
    return "".join(c for c in str(value or "") if c.isprintable()).strip(" @")[:limit]


class MarineTracker:
    def __init__(self, *, key_provider: Callable[[], str | None] | None = None,
                 connector: Callable[..., Any] | None = None, clock: Callable[[], float] = time.monotonic,
                 utcnow: Callable[[], datetime] | None = None, start_workers: bool = True):
        self._key_provider = key_provider or (lambda: os.environ.get("AISSTREAM_API_KEY"))
        self._connector = connector
        self._clock = clock
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self._start_workers = start_workers
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket = None
        self._key = ""
        self._desired: Bounds | None = None
        self._sent: Bounds | None = None
        self._lease = 0.0
        self._connected = False
        self._error: str | None = None
        self._ships: dict[str, dict[str, Any]] = {}

    def snapshot(self, south: float, west: float, north: float, east: float) -> dict[str, Any]:
        bounds = _bounds(south, west, north, east)
        too_wide = north - south > 10 or east - west > 10
        key = str(self._key_provider() or "").strip()
        with self._lock:
            self._key = key
            self._desired = bounds if key and not too_wide else None
            self._lease = self._clock() + LEASE_SECONDS if self._desired else 0
            self._prune()
            if not key:
                self._error = "Set AISSTREAM_API_KEY on the Core server to enable public AIS positions."
            elif too_wide:
                self._error = "Zoom in to an area no more than 10 degrees wide and tall for AIS."
            elif self._start_workers and (self._thread is None or not self._thread.is_alive()):
                self._stop.clear()
                self._error = "Connecting to public AIS."
                self._thread = threading.Thread(target=self._run, name="zae-public-ais", daemon=True)
                self._thread.start()
            ships = []
            if not too_wide:
                for record in self._ships.values():
                    if self._clock() - record.get("positionSeen", -math.inf) > TTL_SECONDS:
                        continue
                    ship = record["ship"]
                    if south <= ship["lat"] <= north and west <= ship["lon"] <= east:
                        ships.append(dict(ship))
            ships.sort(key=lambda ship: (ship.get("updatedAt") or "", ship["id"]), reverse=True)
            error = self._error
            if key and not too_wide and self._connected and self._sent != bounds:
                error = "Updating the AIS viewport; area changes are coalesced to limit stream requests."
            return {"source": ("live" if self._connected and key else "saved") if ships else "none",
                    "configured": bool(key), "updatedAt": max((s["updatedAt"] for s in ships), default=None),
                    "ships": ships, "tooWide": too_wide, "error": error}

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self._lease = 0
            socket, thread = self._socket, self._thread
        if socket is not None:
            try:
                socket.close()
            except Exception:
                pass
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=4)

    def _prune(self) -> None:
        now = self._clock()
        for identifier in list(self._ships):
            if now - self._ships[identifier]["seen"] > TTL_SECONDS:
                del self._ships[identifier]
        while len(self._ships) > MAX_SHIPS:
            del self._ships[min(self._ships, key=lambda identifier: self._ships[identifier]["seen"])]

    def _ingest(self, frame: str | bytes) -> bool:
        if len(frame) > 131_072:
            return False
        try:
            packet = json.loads(frame)
        except (ValueError, UnicodeError, TypeError):
            return False
        if not isinstance(packet, dict):
            return False
        if packet.get("error") or packet.get("MessageType") == "Error":
            # Never echo provider text: it may contain credentials or subscription data.
            raise ConnectionError("Public AIS rejected the subscription.")
        kind = packet.get("MessageType")
        if kind == "SubscriptionConfirmation":
            if not packet.get("Message", {}).get("CompressionEnabled", False):
                raise ConnectionError("Public AIS compression was not negotiated.")
            return False
        if kind not in MESSAGE_TYPES:
            return False
        metadata, body = packet.get("MetaData"), packet.get("Message")
        if not isinstance(metadata, dict) or not isinstance(body, dict) or not isinstance(body.get(kind), dict):
            return False
        message = body[kind]
        identifier = str(metadata.get("MMSI", message.get("UserID", "")))
        if not re.fullmatch(r"[0-9]{9}", identifier) or identifier == "000000000":
            return False
        position = kind in MESSAGE_TYPES[:3]
        if position and message.get("Valid") is False:
            return False
        lat = _number(message.get("Latitude", metadata.get("Latitude", metadata.get("latitude"))), -90, 90)
        lon = _number(message.get("Longitude", metadata.get("Longitude", metadata.get("longitude"))), -180, 180)
        if position and (lat is None or lon is None):
            return False
        report_a = message.get("ReportA") if isinstance(message.get("ReportA"), dict) else {}
        name = _text(metadata.get("ShipName") or message.get("Name") or report_a.get("Name"))
        destination = _text(message.get("Destination"))
        now = self._clock()
        with self._lock:
            self._prune()
            record = self._ships.setdefault(identifier, {"ship": {"id": identifier}, "seen": now})
            record["seen"] = now
            ship = record["ship"]
            if name:
                ship["name"] = name
            if destination:
                ship["destination"] = destination
            if position:
                record["positionSeen"] = now
                heading = _number(message.get("TrueHeading"), 0, 360, exclusive_high=True)
                if heading is None:
                    heading = _number(message.get("Cog"), 0, 360, exclusive_high=True)
                ship.update(lat=lat, lon=lon, speedKt=_number(message.get("Sog"), 0, 102.3, exclusive_high=True),
                            heading=heading, updatedAt=self._utcnow().isoformat())
                ship.setdefault("name", identifier)
            self._prune()
        return position

    def _run(self) -> None:
        backoff = 1.0
        try:
            connector = self._connector
            if connector is None:
                try:
                    from websockets.sync.client import connect
                except ImportError:
                    with self._lock:
                        self._error = "Public AIS needs the optional websockets package on the Core server."
                    return
                connector = connect
            while not self._stop.is_set():
                with self._lock:
                    key, bounds = self._key, self._desired
                    if not key or bounds is None or self._clock() >= self._lease:
                        return
                try:
                    with connector(STREAM_URL, compression="deflate", open_timeout=8, close_timeout=2,
                                   max_size=131_072, max_queue=16) as socket:
                        self._send(socket, key, bounds)
                        last_subscription = self._clock()
                        with self._lock:
                            self._socket, self._connected, self._sent = socket, True, bounds
                            self._error = None
                        while not self._stop.is_set():
                            with self._lock:
                                desired = self._desired
                                if self._key != key or desired is None or self._clock() >= self._lease:
                                    break
                            if desired != bounds and self._clock() - last_subscription >= UPDATE_SECONDS:
                                self._send(socket, key, desired)
                                bounds, last_subscription = desired, self._clock()
                                with self._lock:
                                    self._sent = bounds
                            try:
                                frame = socket.recv(timeout=2)
                            except TimeoutError:
                                continue
                            if self._ingest(frame):
                                backoff = 1.0
                except Exception:
                    with self._lock:
                        self._error = "Public AIS is unavailable. Showing recent received positions, if any; retrying."
                finally:
                    with self._lock:
                        self._socket, self._connected = None, False
                with self._lock:
                    active = self._desired is not None and self._clock() < self._lease
                if not active:
                    return
                if self._stop.wait(backoff + random.uniform(0, backoff * 0.25)):
                    return
                backoff = min(30, backoff * 2)
        finally:
            with self._lock:
                self._socket, self._connected, self._sent = None, False, None
                if self._thread is threading.current_thread():
                    self._thread = None

    @staticmethod
    def _send(socket: Any, key: str, bounds: Bounds) -> None:
        south, west, north, east = bounds
        socket.send(json.dumps({"APIKey": key, "BoundingBoxes": [[[south, west], [north, east]]],
                                "FilterMessageTypes": list(MESSAGE_TYPES)}))


_tracker = MarineTracker()


def snapshot(south: float, west: float, north: float, east: float) -> dict[str, Any]:
    return _tracker.snapshot(south, west, north, east)


def stop() -> None:
    _tracker.stop()
