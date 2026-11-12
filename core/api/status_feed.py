"""Read-only live status for the ZÆNIA UI.

Feeds Core Status, Module Status, System Status and the orb labels with what
is actually true on this PC. It performs no actions and never returns
secrets: no tokens, no iCal link, no file contents. Results are cached for a
few seconds so the UI can poll freely.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
PACIFIC = ZoneInfo("America/Los_Angeles")
CACHE_SECONDS = 4.0
OLLAMA_TAGS = "http://127.0.0.1:11434/api/tags"

_STARTED = time.time()
_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"at": 0.0, "mode": None, "value": None}
_CPU_PREVIOUS: list[int] = []


def _clip(text: str, limit: int = 100) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _module(module_id: str, name: str, phase: str, detail: str) -> dict[str, str]:
    return {"id": module_id, "name": name, "phase": phase, "detail": _clip(detail)}


def _when(moment: datetime) -> str:
    local = moment.astimezone(PACIFIC)
    today = datetime.now(PACIFIC).date()
    clock = local.strftime("%I:%M %p").lstrip("0")
    if local.date() == today:
        return clock
    return local.strftime("%b %d, ") + clock


# ---------------------------------------------------------------- modules

def _security(mode: str) -> dict[str, str]:
    from core.foundation.auth.passkey import passkey_exists
    from core.api.auth import api_token_exists
    if not passkey_exists():
        return _module("security", "Security", "error", "Owner passkey is not set up")
    if not api_token_exists():
        return _module("security", "Security", "error", "API token is not set up")
    if mode == "unattended":
        return _module("security", "Security", "ready", "Token mode: owner features locked until passkey")
    if mode == "voice_only":
        return _module("security", "Security", "ready", "Windows-protected startup; voice requests verify the enrolled speaker")
    return _module("security", "Security", "ready", "Unlocked with the owner passkey")


def _configured_model(key: str = "model") -> str:
    try:
        text = (ROOT / "core" / "brain" / "brain_config.yaml").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(rf"^\s*{key}:\s*[\"']?([^\"'\n#]+)", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _brain() -> dict[str, str]:
    import requests
    model = _configured_model()
    try:
        reply = requests.get(OLLAMA_TAGS, timeout=1.5)
    except requests.RequestException:
        return _module("brain", "SE engine (Ollama)", "error", "Ollama is not running")
    if reply.status_code != 200:
        return _module("brain", "SE engine (Ollama)", "error", f"Ollama answered HTTP {reply.status_code}")
    try:
        names = {str(item.get("name", "")) for item in (reply.json().get("models") or [])}
    except ValueError:
        names = set()
    if model and model not in names:
        fallback = _configured_model("fallback_model")
        if fallback and fallback in names:
            return _module("brain", "SE engine (Ollama)", "working",
                           f"Ollama running {fallback}; {model} is not downloaded yet (ollama pull {model})")
        return _module("brain", "SE engine (Ollama)", "working", f"Ollama running; {model} is not downloaded")
    return _module("brain", "SE engine (Ollama)", "ready", "Ollama running; the Synergized Encephalon's brains are below")


def _brains() -> list[dict[str, str]]:
    """Her four brains (Talk, Seek, Study, Keep), each with its job, from Ollama's downloaded and loaded models."""
    import requests
    from core.brain.roster import FOUR, brain_modules
    try:
        installed = {str(m.get("name", "")) for m in requests.get(OLLAMA_TAGS, timeout=1.5).json().get("models") or []}
        loaded = {str(m.get("name", "")) for m in requests.get(OLLAMA_TAGS.replace("/tags", "/ps"), timeout=1.5).json().get("models") or []}
    except Exception:
        installed, loaded = None, set()
    try:
        return [_module(m["id"], m["name"], m["phase"], m["detail"]) for m in brain_modules(installed, loaded)]
    except Exception:
        return [_module(f"brain_{brain_id}", name, "error", "Couldn't read this brain's state") for brain_id, name, _ in FOUR]


def _voice() -> dict[str, str]:
    # Kokoro is ZAE's voice; Piper is only the fallback when Kokoro can't run.
    from core.carplay_audio.carplay_audio import get_piper_settings
    piper = None
    try:
        get_piper_settings()
    except FileNotFoundError:
        piper = "Piper voice files are missing"
    except RuntimeError as error:
        piper = str(error).split(":")[0] or "Piper voice is off"
    try:
        from core.voice_output.neural_voice import settings as kokoro_settings
        kokoro = kokoro_settings()
    except Exception:
        kokoro = {"active": False}
    if kokoro.get("active"):
        if kokoro["model_path"].exists() and kokoro["voices_path"].exists():
            backup = "Piper as backup" if piper is None else "no Piper backup"
            return _module("voice", "Voice", "ready", f"Kokoro voice ready ({kokoro['voice']}), {backup}")
        if piper is None:
            return _module("voice", "Voice", "working", "Kokoro voice files are missing; speaking with Piper for now")
        return _module("voice", "Voice", "error", "Kokoro and Piper voice files are missing")
    if piper is not None:
        return _module("voice", "Voice", "error" if "missing" in piper else "pending", piper)
    return _module("voice", "Voice", "ready", "Piper voice ready")


def _calendar() -> tuple[dict[str, str], str]:
    from core.calendar_context.calendar_context import CALENDAR_PATH
    from core.google_calendar_sync.google_calendar_ics import ICS_URL_PATH
    if not CALENDAR_PATH.is_file():
        return _module("calendar", "Calendar", "error", "Local calendar file is missing"), "Calendar missing"
    linked = ICS_URL_PATH.is_file() and ICS_URL_PATH.stat().st_size > 0
    saved = datetime.fromtimestamp(CALENDAR_PATH.stat().st_mtime, PACIFIC)
    if not linked:
        return (_module("calendar", "Calendar", "working", f"Google not linked; local calendar saved {_when(saved)}"),
                "Local only")
    return (_module("calendar", "Calendar", "ready", f"Google linked; briefs read it live. Saved {_when(saved)}"),
            "Google live")


def _traffic() -> dict[str, str]:
    if os.environ.get("WSDOT_API_KEY", "").strip():
        return _module("traffic", "Traffic", "ready", "WSDOT traffic key set")
    return _module("traffic", "Traffic", "pending", "WSDOT_API_KEY is not set for the server")


def _weather() -> dict[str, str]:
    import core.weather.weather_client  # noqa: F401  (import check only; no network call)
    return _module("weather", "Weather", "ready", "Open-Meteo, no key needed")


def _carplay() -> tuple[dict[str, str], str | None]:
    database = ROOT / "data" / "carplay_sessions" / "sessions.sqlite3"
    if not database.is_file():
        return _module("carplay", "CarPlay Brief", "pending", "No brief made yet"), None
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        row = connection.execute("SELECT payload FROM sessions ORDER BY rowid DESC LIMIT 1").fetchone()
    finally:
        connection.close()
    if row is None:
        return _module("carplay", "CarPlay Brief", "pending", "No brief made yet"), None
    generated = datetime.fromisoformat(json.loads(row[0])["generated_at"])
    age_hours = (datetime.now(PACIFIC) - generated).total_seconds() / 3600
    phase = "ready" if age_hours <= 36 else "working"
    return _module("carplay", "CarPlay Brief", phase, f"Last brief {_when(generated)}"), generated.isoformat()


def _guard(check: Callable[[], Any], fallback_id: str, fallback_name: str) -> Any:
    try:
        return check()
    except Exception as error:  # A failing check reports itself; it never breaks the feed.
        return _module(fallback_id, fallback_name, "error", f"Check failed: {type(error).__name__}")


# ------------------------------------------------------------ PC load

def _cpu_percent() -> int | None:
    try:
        import psutil  # type: ignore
        return round(psutil.cpu_percent(interval=None))
    except Exception:
        pass
    if os.name != "nt":
        return _linux_cpu_percent()
    import ctypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

    idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None
    value = lambda item: (item.high << 32) | item.low  # noqa: E731
    sample = [value(idle), value(kernel) + value(user)]  # kernel time includes idle time
    previous = _CPU_PREVIOUS[:]
    _CPU_PREVIOUS[:] = sample
    if not previous or sample[1] <= previous[1]:
        return None
    busy = 1 - (sample[0] - previous[0]) / (sample[1] - previous[1])
    return max(0, min(100, round(busy * 100)))


def _memory_percent() -> int | None:
    try:
        import psutil  # type: ignore
        return round(psutil.virtual_memory().percent)
    except Exception:
        pass
    if os.name != "nt":
        return _linux_memory_percent()
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                    ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                    ("avail_extended", ctypes.c_ulonglong)]

    status = MEMORYSTATUSEX()
    status.length = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.load)


def _linux_cpu_percent() -> int | None:
    """Busy share of all cores since the previous call, from /proc/stat."""
    try:
        with open("/proc/stat", encoding="ascii") as handle:
            fields = [int(value) for value in handle.readline().split()[1:]]
    except (OSError, ValueError):
        try:
            return min(100, round(os.getloadavg()[0] / (os.cpu_count() or 1) * 100))
        except (AttributeError, OSError):
            return None
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle + iowait
    sample = [idle, sum(fields[:8])]  # guest time is already counted in user time
    previous = _CPU_PREVIOUS[:]
    _CPU_PREVIOUS[:] = sample
    if not previous or sample[1] <= previous[1]:
        return None
    busy = 1 - (sample[0] - previous[0]) / (sample[1] - previous[1])
    return max(0, min(100, round(busy * 100)))


def _linux_memory_percent() -> int | None:
    """Memory in use (total minus available), from /proc/meminfo."""
    values: dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="ascii") as handle:
            for line in handle:
                name, _, rest = line.partition(":")
                if name in ("MemTotal", "MemAvailable"):
                    values[name] = int(rest.split()[0])
    except (OSError, ValueError, IndexError):
        return None
    total, available = values.get("MemTotal"), values.get("MemAvailable")
    if not total or available is None:
        return None
    return max(0, min(100, round((total - available) / total * 100)))


try:  # Prime the processor sample so the first status call can report load.
    _cpu_percent()
except Exception:
    pass


# ------------------------------------------------------------- snapshot

def build_status(mode: str) -> dict[str, Any]:
    """Snapshot in the shape the desktop UI validates (see coreTelemetry.ts)."""
    with _LOCK:
        now = time.time()
        if _CACHE["value"] is not None and _CACHE["mode"] == mode and now - _CACHE["at"] < CACHE_SECONDS:
            return _CACHE["value"]
        calendar, synchronization = _guard(_calendar, "calendar", "Calendar"), "Unknown"
        if isinstance(calendar, tuple):
            calendar, synchronization = calendar
        carplay, last_brief = _guard(_carplay, "carplay", "CarPlay Brief"), None
        if isinstance(carplay, tuple):
            carplay, last_brief = carplay
        modules = [
            _guard(lambda: _security(mode), "security", "Security"),
            _guard(_brain, "brain", "SE engine (Ollama)"),
            *_brains(),
            _guard(_voice, "voice", "Voice"),
            calendar,
            _guard(_traffic, "traffic", "Traffic"),
            _guard(_weather, "weather", "Weather"),
            carplay,
        ]
        attention = sum(1 for item in modules if item["phase"] in ("error", "pending"))
        value = {
            "progress": 100,
            "phase": "ONLINE",
            "diagnostics": "ALL READY" if attention == 0 else f"{attention} NEED ATTENTION",
            "synchronization": synchronization,
            "modules": modules,
            "system": {
                "mode": mode,
                "cpu": _cpu_percent(),
                "memory": _memory_percent(),
                "uptime_seconds": int(now - _STARTED),
                "last_brief_at": last_brief,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        _CACHE.update(at=now, mode=mode, value=value)
        return value
