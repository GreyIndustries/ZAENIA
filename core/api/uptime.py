"""How ZAE has been running (Status tab, "Uptime"; Grey's pick C, 2026-10-30).

Every 5 minutes the server notes whether each part is working: the server itself, the local brain (Ollama answering),
the desktop app (it checked in for remote commands), and backups (one in the last 30 hours). Each day keeps a count of
good and total checks per part, for 30 days, plus a short list of what changed (a part going down or coming back, and
times the server itself was off). Nothing personal is stored: only part names, counts and times.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPTIME_FILE = PROJECT_ROOT / "data" / "ui" / "uptime.json"
EVERY = 300
KEEP_DAYS = 30
PARTS = {"server": "Server", "brain": "Local brain", "desktop": "Desktop app", "backup": "Backups"}
_LOCK = threading.Lock()


def _brain_ok() -> bool:
    import requests
    try:
        return requests.get("http://127.0.0.1:11434/api/tags", timeout=3).ok
    except Exception:
        return False


def _desktop_ok() -> bool:
    from core.api import remote_control
    return time.time() - remote_control.last_collect() < EVERY


def _backup_ok() -> bool:
    from core.assistant_platform.selfcare import last_backup
    at = last_backup().get("at")
    try:
        return bool(at) and time.time() - datetime.fromisoformat(at).timestamp() < 30 * 3600
    except ValueError:
        return False


PROBES: dict[str, Callable[[], bool]] = {"server": lambda: True, "brain": _brain_ok, "desktop": _desktop_ok, "backup": _backup_ok}


class Uptime:
    def __init__(self, path: Path = UPTIME_FILE, probes: dict[str, Callable[[], bool]] | None = None, clock: Callable[[], datetime] = datetime.now):
        self.path, self.probes, self.clock = Path(path), probes or PROBES, clock
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("days"), dict):
                return data
        except (OSError, ValueError):
            pass
        return {"days": {}, "events": [], "last": None, "state": {}}

    def _save(self, data: dict[str, Any]) -> None:
        from core.foundation.security.io import atomic_write
        keep = sorted(data["days"])[-KEEP_DAYS:]
        data["days"] = {day: data["days"][day] for day in keep}
        data["events"] = data["events"][-60:]
        atomic_write(self.path, json.dumps(data, indent=1).encode("utf-8"))

    def sample(self) -> dict[str, Any]:
        now = self.clock()
        results = {}
        for part, probe in self.probes.items():
            try:
                results[part] = bool(probe())
            except Exception:
                results[part] = False
        with _LOCK:
            data = self._load()
            last = datetime.fromisoformat(data["last"]) if data.get("last") else None
            if last and now - last > timedelta(seconds=EVERY * 2.5):
                # The server itself was off: count the missed checks as down, day by day.
                data["events"].append({"at": last.isoformat(timespec="minutes"), "until": now.isoformat(timespec="minutes"), "part": "server", "kind": "off"})
                missed, cursor = int((now - last).total_seconds() // EVERY) - 1, last
                for _ in range(min(missed, KEEP_DAYS * 288)):
                    cursor += timedelta(seconds=EVERY)
                    counts = data["days"].setdefault(cursor.date().isoformat(), {}).setdefault("server", [0, 0])
                    counts[1] += 1
            day = data["days"].setdefault(now.date().isoformat(), {})
            for part, ok in results.items():
                counts = day.setdefault(part, [0, 0])
                counts[0] += 1 if ok else 0
                counts[1] += 1
                before = data["state"].get(part)
                if before is not None and before != ok:
                    data["events"].append({"at": now.isoformat(timespec="minutes"), "part": part, "kind": "back" if ok else "down"})
                data["state"][part] = ok
            data["last"] = now.isoformat(timespec="seconds")
            self._save(data)
        return results

    def view(self) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
        today = self.clock().date()
        days = [(today - timedelta(days=KEEP_DAYS - 1 - i)).isoformat() for i in range(KEEP_DAYS)]
        rows = []
        for part, name in PARTS.items():
            share, good, total = [], 0, 0
            for day in days:
                counts = data["days"].get(day, {}).get(part)
                if counts and counts[1]:
                    share.append(round(counts[0] / counts[1], 3)); good += counts[0]; total += counts[1]
                else:
                    share.append(None)
            rows.append({"id": part, "name": name, "days": share, "percent": round(good / total * 100, 1) if total else None,
                         "now": data["state"].get(part)})
        events = [{**e, "name": PARTS.get(e["part"], e["part"])} for e in reversed(data["events"][-20:])]
        return {"days": days, "rows": rows, "events": events, "last": data.get("last"), "every": EVERY}

    def start(self) -> None:
        if self.thread is not None:
            return

        def run():
            while True:
                try:
                    self.sample()
                except Exception:
                    pass
                if self.stop_event.wait(EVERY):
                    return
        self.thread = threading.Thread(target=run, name="zaenia-uptime", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()


_instance: Uptime | None = None


def uptime() -> Uptime:
    global _instance
    if _instance is None:
        _instance = Uptime()
    return _instance
