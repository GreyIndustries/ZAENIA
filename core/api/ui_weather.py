"""Current weather for the top bar, from ZAE's existing weather module (cached)."""
from __future__ import annotations

import re
import threading
import time
from typing import Any

_CACHE: dict[str, Any] = {"at": 0.0, "data": None}
_LOCK = threading.Lock()
CACHE_SECONDS = 15 * 60


def current_weather() -> dict[str, Any]:
    with _LOCK:
        if _CACHE["data"] is not None and time.monotonic() - _CACHE["at"] < CACHE_SECONDS:
            return _CACHE["data"]
    from core.weather.weather_client import get_weather_for_location, weather_code_text
    from core.weather.weather_selector import select_weather_location
    location = select_weather_location()
    result = get_weather_for_location(location)
    current = (result.get("forecast") or {}).get("current") or {}
    daily = (result.get("forecast") or {}).get("daily") or {}
    def first(key: str):
        values = daily.get(key) or []
        return values[0] if values else None
    data = {
        "place": re.sub(r"^in\s+", "", str(location.get("display_label") or location.get("name") or "")),
        "temperature": current.get("temperature_2m"),
        "feelsLike": current.get("apparent_temperature"),
        "condition": weather_code_text(current.get("weather_code")),
        "high": first("temperature_2m_max"),
        "low": first("temperature_2m_min"),
        "unit": "°F",
    }
    with _LOCK:
        _CACHE.update(at=time.monotonic(), data=data)
    return data
