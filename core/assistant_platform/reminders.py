"""Reminders: time-based nudges, separate from tasks.

Each reminder fires once (or daily / weekly) as an on-screen notice that ZAE
can read aloud, and optionally as a text to Grey's phone when the phone line
is set up. Kept in data/reminders.json. "Remind me in 20 minutes to check the
oven" and "remind me at 5pm tomorrow to call mum" work by voice or typing.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REMINDERS_FILE = PROJECT_ROOT / "data" / "reminders.json"
CHANNELS = ("screen", "speak", "phone")
REPEATS = ("none", "daily", "weekly")
MAX_REMINDERS = 500
_LOCK = threading.Lock()

_REMIND = re.compile(
    r"^(?:(?:hey )?(?:zae|zay|zaenia)[, ]+)?(?:please )?remind me\s+"
    r"(?:(?P<in>in\s+(?P<n>\d+|an?|one|two|five|ten|fifteen|twenty|thirty)\s*(?P<unit>minutes?|mins?|hours?|hrs?))"
    r"|(?:at\s+(?P<time>\d{1,2}(?::\d{2})?\s*(?:am|pm)?|noon|midnight))(?:\s+(?P<day>today|tomorrow|tonight))?"
    r"|(?P<day2>tomorrow|tonight)(?:\s+at\s+(?P<time2>\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?)"
    r"\s+(?:to\s+|that\s+|about\s+)?(?P<what>.+?)[.!?]*$", re.I)
_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30}


def _clock_time(text: str) -> tuple[int, int]:
    text = text.strip().lower()
    if text == "noon":
        return 12, 0
    if text == "midnight":
        return 0, 0
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    hour, minute, half = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    if half == "pm" and hour < 12:
        hour += 12
    if half == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        raise ValueError("That isn't a time of day.")
    return hour, minute


def parse_request(text: str, now: datetime | None = None) -> tuple[datetime, str] | None:
    """(when, what) for "remind me ..." sentences, in local time; None otherwise."""
    match = _REMIND.match(" ".join(str(text).split()))
    if not match:
        return None
    now = (now or datetime.now()).astimezone()
    what = match.group("what").strip()
    if match.group("in"):
        amount = _WORDS.get(match.group("n").lower(), None) or int(match.group("n"))
        unit = match.group("unit").lower()
        return now + (timedelta(hours=amount) if unit.startswith("h") else timedelta(minutes=amount)), what
    day = (match.group("day") or match.group("day2") or "").lower()
    clock = match.group("time") or match.group("time2") or ("20:00" if day == "tonight" else "9:00")
    hour, minute = _clock_time(clock)
    if day == "tonight" and hour < 12 and not re.search(r"am", clock, re.I):
        hour += 12
    when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if day == "tomorrow":
        when += timedelta(days=1)
    elif when <= now:
        when += timedelta(days=1)
    return when, what


class Reminders:
    def __init__(self, path: Path = REMINDERS_FILE, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.path, self.clock = Path(path), clock
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        from core.foundation.security.io import atomic_write
        atomic_write(self.path, json.dumps(items, indent=1).encode("utf-8"))

    def list(self, include_done: bool = False) -> list[dict[str, Any]]:
        return sorted((r for r in self._load() if include_done or not r.get("done")), key=lambda r: r["due"])

    def add(self, text: str, due: datetime | str, *, channels: list[str] | None = None, repeat: str = "none") -> dict[str, Any]:
        text = " ".join(str(text).split())[:300]
        if not text:
            raise ValueError("What should I remind you about?")
        when = datetime.fromisoformat(due) if isinstance(due, str) else due
        if when.tzinfo is None:
            when = when.astimezone()
        channels = [c for c in (channels or ["screen", "speak"]) if c in CHANNELS] or ["screen"]
        if repeat not in REPEATS:
            raise ValueError("Repeat is none, daily or weekly.")
        record = {"id": uuid.uuid4().hex, "text": text, "due": when.astimezone(timezone.utc).isoformat(timespec="seconds"),
                  "channels": channels, "repeat": repeat, "done": False, "created": self.clock().isoformat(timespec="seconds")}
        with _LOCK:
            items = self._load()
            if len([r for r in items if not r.get("done")]) >= MAX_REMINDERS:
                raise ValueError("Too many reminders; clear some old ones first.")
            self._save(items + [record])
        return record

    def delete(self, reminder_id: str) -> None:
        with _LOCK:
            self._save([r for r in self._load() if r["id"] != reminder_id])

    def due(self) -> list[dict[str, Any]]:
        """Reminders whose time has come; marks them done, or moves repeating ones to their next time."""
        now = self.clock()
        fired = []
        with _LOCK:
            items = self._load()
            for record in items:
                if record.get("done") or datetime.fromisoformat(record["due"]) > now:
                    continue
                fired.append(dict(record))
                if record["repeat"] == "none":
                    record["done"] = True
                else:
                    step = timedelta(days=1 if record["repeat"] == "daily" else 7)
                    nxt = datetime.fromisoformat(record["due"])
                    while nxt <= now:
                        nxt += step
                    record["due"] = nxt.isoformat(timespec="seconds")
            if fired:
                self._save(items)
        return fired

    def start(self, notify: Callable[[dict[str, Any]], None]) -> None:
        if self.thread is not None:
            return

        def run():
            while not self.stop_event.wait(20):
                try:
                    for record in self.due():
                        notify(record)
                except Exception:
                    pass
        self.thread = threading.Thread(target=run, name="zaenia-reminders", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()


_REMINDERS: Reminders | None = None


def reminders() -> Reminders:
    global _REMINDERS
    if _REMINDERS is None:
        _REMINDERS = Reminders()
    return _REMINDERS


def spoken_time(when: datetime) -> str:
    local = when.astimezone()
    today = datetime.now().astimezone().date()
    day = "today" if local.date() == today else "tomorrow" if local.date() == today + timedelta(days=1) else local.strftime("%A")
    return f"{local.strftime('%I:%M %p').lstrip('0')} {day}"
