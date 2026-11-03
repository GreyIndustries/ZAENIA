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
from datetime import date, datetime, time, timedelta, timezone
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
_REMINDER_PREFIX = re.compile(
    r"^(?:(?:hey\s+)?(?:zae|zay|zaenia)[, ]+)?(?:(?:can|could|would)\s+you\s+)?"
    r"(?:please\s+)?(?:remind\s+me|(?:set|add|put|create|make)\s+(?:me\s+)?(?:a\s+)?reminder)(?:\s+|$)", re.I)
_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_MONTH_REF = rf"(?:{_MONTH}\.?|this\s+month|next\s+month)"
_DATE_TEXT = (rf"(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|{_MONTH}\.?\s+(?:the\s+)?{_DAY}(?:,?\s+\d{{4}})?"
              rf"|(?:the\s+)?{_DAY}(?:\s+(?:of\s+)?{_MONTH_REF})?(?:,?\s+\d{{4}})?)")
_DATE_ONLY = re.compile(rf"(?:on\s+)?{_DATE_TEXT}", re.I)
_CLOCK_TEXT = r"(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|noon|midnight)"
_DATE_FIRST = re.compile(
    rf"^(?:on|for)\s+(?P<date>{_DATE_TEXT})(?:\s+at\s+(?P<clock>{_CLOCK_TEXT}))?\s+(?:to|about|for|that)\s+(?P<what>.+?)[.!?]*$", re.I)
_DATE_LAST = re.compile(
    rf"^(?:to|about|for|that)\s+(?P<what>.+?)\s+(?:on|for)\s+(?P<date>{_DATE_TEXT})(?:\s+at\s+(?P<clock>{_CLOCK_TEXT}))?[.!?]*$", re.I)
_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30}
_MONTH_NUMBERS = {name: index for index, names in enumerate((
    ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"),
    ("jul", "july"), ("aug", "august"), ("sep", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december"),
), start=1) for name in names}


def is_reminder_request(text: str) -> bool:
    """Recognize reminder commands even when the date/time/details are incomplete."""
    return bool(_REMINDER_PREFIX.match(" ".join(str(text).split())))


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


def _reminder_date(text: str, today: date) -> tuple[date, str, bool] | None:
    """Return (date, roll-forward unit, pinned) for a month/day expression.

    Pinned dates (an explicit year, "this month" or "next month") never roll forward.
    """
    value = " ".join(text.strip().lower().replace(",", " ").split())
    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if iso:
        try:
            return date(int(iso[1]), int(iso[2]), int(iso[3])), "", True
        except ValueError:
            return None
    year_match = re.search(r"\b(\d{4})\b", value)
    year = int(year_match[1]) if year_match else today.year
    value = re.sub(r"\b\d{4}\b", " ", value)
    month_match = re.search(rf"\b({_MONTH})\b", value, re.I)
    month = _MONTH_NUMBERS.get(month_match[1][:3].lower()) if month_match else None
    day_match = re.search(rf"\b({_DAY})\b", value, re.I)
    if day_match is None:
        return None
    day = int(re.match(r"\d+", day_match[1])[0])
    anchor = re.search(r"\b(this|next) month\b", value)
    if anchor:
        month = today.month
        if anchor[1] == "next":
            month += 1
            if month > 12:
                month, year = 1, year + 1
        roll = ""
    elif month is None:
        month = today.month
        roll = "month"
    else:
        roll = "year"
    try:
        target = date(year, month, day)
    except ValueError:
        return None
    explicit_year = year_match is not None or anchor is not None
    if not explicit_year and target < today:
        if roll == "month":
            month += 1
            if month > 12:
                month, year = 1, year + 1
            try:
                target = date(year, month, day)
            except ValueError:
                # Keep looking for the next month that contains this day (e.g. the 31st).
                for _ in range(11):
                    month += 1
                    if month > 12:
                        month, year = 1, year + 1
                    try:
                        target = date(year, month, day)
                        break
                    except ValueError:
                        continue
                else:
                    return None
        else:
            try:
                target = date(year + 1, month, day)
            except ValueError:
                return None
    return target, roll, explicit_year


def parse_date(text: str, today: date | None = None) -> date | None:
    """Resolve a spoken date like "November 8", "8 Nov" or "the 8th of this month"."""
    value = " ".join(str(text).split())
    if not _DATE_ONLY.fullmatch(value):
        return None
    resolved = _reminder_date(re.sub(r"^on\s+", "", value, flags=re.I), today or date.today())
    return resolved[0] if resolved else None


def parse_request(text: str, now: datetime | None = None) -> tuple[datetime, str] | None:
    """(when, what) for direct reminder commands; None when required details are missing."""
    normalized = " ".join(str(text).split())
    prefix = _REMINDER_PREFIX.match(normalized)
    if prefix is None:
        return None
    body = normalized[prefix.end():].strip()
    now = (now or datetime.now()).astimezone()

    absolute = _DATE_FIRST.fullmatch(body) or _DATE_LAST.fullmatch(body)
    if absolute is not None:
        resolved = _reminder_date(absolute["date"], now.date())
        what = absolute["what"].strip()
        if resolved is None or not what:
            return None
        target_day, roll, explicit_year = resolved
        clock = absolute["clock"]
        try:
            hour, minute = _clock_time(clock) if clock else (9, 0)
        except ValueError:
            return None
        due = datetime.combine(target_day, time(hour, minute), tzinfo=now.tzinfo)
        if due <= now:
            if explicit_year:
                return None
            if roll == "month":
                year, month = due.year, due.month + 1
                if month > 12:
                    year, month = year + 1, 1
                for _ in range(12):
                    try:
                        due = due.replace(year=year, month=month)
                        break
                    except ValueError:
                        month += 1
                        if month > 12:
                            year, month = year + 1, 1
                else:
                    return None
            else:
                try:
                    due = due.replace(year=due.year + 1)
                except ValueError:
                    return None
        return due, what

    # Normalize "put/set/add a reminder ..." to the established deterministic parser.
    match = _REMIND.match(f"remind me {body}")
    if not match:
        return None
    what = match.group("what").strip()
    if match.group("in"):
        amount = _WORDS.get(match.group("n").lower(), None) or int(match.group("n"))
        unit = match.group("unit").lower()
        return now + (timedelta(hours=amount) if unit.startswith("h") else timedelta(minutes=amount)), what
    day = (match.group("day") or match.group("day2") or "").lower()
    clock = match.group("time") or match.group("time2") or ("20:00" if day == "tonight" else "9:00")
    try:
        hour, minute = _clock_time(clock)
    except ValueError:
        return None
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
