"""The status bar along the bottom of the app: what ZAE is running on, at a glance.

Read-only and cheap: everything comes from local files, psutil, and two quick
local queries (Ollama's loaded models, nvidia-smi), each cached for a few seconds.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CACHE: dict[str, tuple[float, Any]] = {}
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}


def _cached(key: str, seconds: float, compute: Callable[[], Any]) -> Any:
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < seconds:
        return hit[1]
    try:
        value = compute()
    except Exception:
        value = None
    _CACHE[key] = (now, value)
    return value


def _json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _fresh(stamp: Any, seconds: float) -> bool:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(str(stamp))).total_seconds() <= seconds
    except (TypeError, ValueError):
        return False


def _gpu() -> dict[str, Any] | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    out = subprocess.run([exe, "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=4, **NO_WINDOW).stdout.strip().splitlines()
    if not out:
        return None
    use, used, total, temp = [part.strip() for part in out[0].split(",")]
    return {"use": int(float(use)), "memoryUsedGb": round(float(used) / 1024, 1), "memoryTotalGb": round(float(total) / 1024, 1),
            "temperature": int(float(temp))}


def _loaded_models() -> list[str]:
    import requests
    models = requests.get("http://127.0.0.1:11434/api/ps", timeout=2).json().get("models") or []
    return [str(item.get("name") or item.get("model")) for item in models]


def _brain_chips(loaded: list[str]) -> list[dict[str, Any]]:
    try:
        from core.brain.roster import FOUR, brains
        rows = {b["id"]: b for b in brains()}
        return [{"name": name, "model": rows[i]["model"], "job": job, "loaded": rows[i]["model"] in loaded} for i, name, job in FOUR]
    except Exception:
        return []


def status_bar(mode: str = "") -> dict[str, Any]:
    import psutil
    from core.api.status_feed import _configured_model
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(str(PROJECT_ROOT.anchor or "C:\\"))
    voice = _json(PROJECT_ROOT / "data" / "ui" / "voice_service.json")
    game = _json(PROJECT_ROOT / "data" / "ui" / "game_mode.json")
    backup = _json(PROJECT_ROOT / "data" / "backups" / "last.json")
    try:
        from core.voice_output.neural_voice import settings as kokoro
        speaking = kokoro()
        voice_name = f"Kokoro {speaking['voice']}" if speaking.get("active") else "Piper"
    except Exception:
        voice_name = "unknown"
    try:
        from core.telephony.settings import load, ready
        phone = "on" if ready(load()) else "off"
    except Exception:
        phone = "off"
    return {
        "model": _configured_model(),
        # The four brains for the bottom bar: name, model, job and whether it's in memory now.
        "brains": _brain_chips(_cached("loaded", 10, _loaded_models) or []),
        "loaded": _cached("loaded", 10, _loaded_models) or [],
        "voice": voice_name,
        "pcVoice": voice.get("state", "off") if _fresh(voice.get("updatedAt"), 15) else "off",
        "mode": mode,
        "cpu": round(psutil.cpu_percent(interval=None)),
        "ramUsedGb": round((memory.total - memory.available) / 2**30, 1),
        "ramTotalGb": round(memory.total / 2**30, 1),
        "gpu": _cached("gpu", 10, _gpu),
        "diskFreeGb": round(disk.free / 2**30),
        "gameMode": game.get("app") if game.get("active") and _fresh(game.get("updatedAt"), 30) else None,
        "phone": phone,
        "backup": backup.get("at"),
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def top_processes(limit: int = 6) -> list[dict[str, Any]]:
    """What's using this PC: the biggest programs by memory, with a short CPU sample (names only, nothing else)."""
    import time
    import psutil
    procs = []
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            proc.cpu_percent(None)
            procs.append(proc)
        except (psutil.Error, OSError):
            continue
    time.sleep(0.4)
    grouped: dict[str, dict[str, float]] = {}
    cores = psutil.cpu_count() or 1
    for proc in procs:
        try:
            name = (proc.info.get("name") or "?").removesuffix(".exe")
            mem = (proc.info.get("memory_info").rss if proc.info.get("memory_info") else 0) / 1e9
            cpu = proc.cpu_percent(None) / cores
        except (psutil.Error, OSError, AttributeError):
            continue
        entry = grouped.setdefault(name, {"cpu": 0.0, "memGb": 0.0})
        entry["cpu"] += cpu
        entry["memGb"] += mem
    labels = {"ollama": "Ollama (ZAE's brain)", "python": "Python (ZAENIA server)", "ZAENIA": "ZAENIA app", "msedge": "Edge", "chrome": "Chrome"}
    rows = sorted(grouped.items(), key=lambda kv: -kv[1]["memGb"])[:limit]
    return [{"name": labels.get(name, name), "cpu": round(v["cpu"], 1), "memGb": round(v["memGb"], 2)} for name, v in rows]
