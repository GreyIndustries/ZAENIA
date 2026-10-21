"""Calendar for the ZÆNIA UI.

Reads what ZÆNIA's briefs read: the calendar file, the scheduling service
store (core/scheduling) and live Google events. The owner allowed token
clients to add and delete scheduling-service events (ui.calendar.write and
ui.calendar.delete); the owner calendar file and Google stay read-only here.
"""
from __future__ import annotations

import hashlib
import threading
import time as clock
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACIFIC = ZoneInfo("America/Los_Angeles")
MAX_DAYS = 62
GOOGLE_CACHE_SECONDS = 300.0

_GOOGLE_LOCK = threading.Lock()
_GOOGLE_CACHE: dict[str, Any] = {"key": None, "at": 0.0, "events": None, "error": None}


class CalendarError(ValueError):
    """A request the calendar can't accept; the message is safe to show."""


class EventNotFound(LookupError):
    pass


def scheduling_db() -> Path:
    # Same file calendar_context reads for "local_service" events.
    return PROJECT_ROOT / "data" / "scheduling" / "calendar.sqlite3"


def _store():
    from core.scheduling.service import Store
    return Store(scheduling_db())


def _google_calendar() -> tuple[Any, str | None]:
    """The parsed Google calendar, fetched at most every few minutes."""
    with _GOOGLE_LOCK:
        if clock.monotonic() - _GOOGLE_CACHE["at"] < GOOGLE_CACHE_SECONDS and _GOOGLE_CACHE["at"]:
            return _GOOGLE_CACHE["events"], _GOOGLE_CACHE["error"]
    try:
        from core.google_calendar_sync.google_calendar_ics import fetch_ics_calendar
        calendar, error = fetch_ics_calendar(), None
    except Exception as failure:  # network, missing link, parse errors
        calendar, error = None, f"Google Calendar couldn't be read ({type(failure).__name__}); showing saved events."
    with _GOOGLE_LOCK:
        _GOOGLE_CACHE.update(at=clock.monotonic(), events=calendar, error=error)
    return calendar, error


def _google_events(start: date, days: int) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Live Google events for the range. Never returns the iCal link."""
    calendar, error = _google_calendar()
    if calendar is None:
        return None, error
    try:
        import recurring_ical_events
        from core.google_calendar_sync.google_calendar_ics import LOCAL_TIMEZONE, convert_ical_event
        lower = datetime.combine(start, time.min, tzinfo=LOCAL_TIMEZONE)
        upper = lower + timedelta(days=days)
        events = [converted for raw in recurring_ical_events.of(calendar).between(lower, upper)
                  if (converted := convert_ical_event(raw))]
    except Exception as failure:
        return None, f"Google Calendar couldn't be read ({type(failure).__name__}); showing saved events."
    events.sort(key=lambda item: (item["date"], item["time"], item["title"]))
    return events, None


def _source_label(source: str | None) -> str:
    if source == "local_service":
        return "zaenia"
    if source and source.startswith("google"):
        return "google"
    if source == "recurring":
        return "recurring"
    return "calendar"


def _event_id(event: dict[str, Any]) -> str:
    if event.get("source") == "local_service" and isinstance(event.get("id"), str):
        return event["id"]
    basis = "|".join(str(event.get(key) or "") for key in ("source", "date", "time", "title", "google_uid"))
    return "cal-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _clip(value: Any, limit: int) -> str | None:
    if value in (None, ""):
        return None
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def read_calendar(start: date, days: int) -> dict[str, Any]:
    if not 1 <= days <= MAX_DAYS:
        raise CalendarError(f"Ask for 1 to {MAX_DAYS} days.")
    from core.calendar_context.calendar_context import (
        get_events_for_date,
        get_status_for_date,
        google_events_overlay,
        load_calendar_config,
    )
    from core.google_calendar_sync.google_calendar_ics import GOOGLE_SYNC_SOURCE

    dates = [start + timedelta(days=offset) for offset in range(days)]
    google, google_error = _google_events(start, days)
    if google is not None:
        with google_events_overlay(google, [day.isoformat() for day in dates], GOOGLE_SYNC_SOURCE):
            config = load_calendar_config()
    else:
        config = load_calendar_config()

    from core.google_calendar_sync.google_calendar_api import is_mirror, status as google_write_status
    try:
        local_ids = {str(event.get("id")) for event in _store().events()}
    except Exception:
        local_ids = set()
    events: list[dict[str, Any]] = []
    statuses: dict[str, str] = {}
    for day in dates:
        status = get_status_for_date(config, day)
        statuses[day.isoformat()] = str(status.get("status_label") or status.get("status") or "")
        for event in get_events_for_date(config, day):
            # Google's copy of a ZÆNIA event: show it once, as the ZÆNIA event.
            if is_mirror(event.get("description"), local_ids):
                continue
            source = _source_label(event.get("source"))
            events.append({
                "id": _event_id(event),
                "date": day.isoformat(),
                "time": _clip(event.get("time"), 8) or "",
                "endTime": _clip(event.get("end_time"), 8),
                "allDay": bool(event.get("all_day")),
                "title": _clip(event.get("title"), 200) or "Untitled event",
                "location": _clip(event.get("location"), 200),
                "reminder": _clip(event.get("reminder"), 300),
                "source": source,
                "deletable": source == "zaenia",
            })
    return {
        "start": start.isoformat(),
        "days": days,
        "events": events,
        "dayStatus": statuses,
        "dutyOverrides": {day.isoformat():config['_owner_duty_days'][day.isoformat()] for day in dates if day.isoformat() in config.get('_owner_duty_days',{})},
        "dutyRevision": config.get('_owner_duty_revision',0),
        "google": "live" if google is not None else "unavailable",
        "notice": google_error,
        "googleWrite": google_write_status()["connected"],
    }


def add_event(title: Any, day: Any, at: Any, recurrence: Any = "none") -> dict[str, Any]:
    from core.scheduling.service import validate_event, wall
    if not isinstance(title, str) or not title.strip():
        raise CalendarError("Give the event a title.")
    try:
        target = date.fromisoformat(str(day))
    except ValueError as error:
        raise CalendarError("Choose a date.") from error
    try:
        hour, minute = (int(part) for part in str(at).split(":", 1))
        start_time = time(hour, minute)
    except (ValueError, TypeError) as error:
        raise CalendarError("Choose a time, like 14:30.") from error
    if recurrence not in ("none", "daily", "weekly"):
        raise CalendarError("Repeat can be none, daily or weekly.")
    try:
        start = wall(target, start_time)
        params = validate_event({
            "id": "app-" + uuid.uuid4().hex[:20],
            "title": " ".join(title.split())[:200],
            "start": start.isoformat(),
            "recurrence": recurrence,
            "channels": ["console"],
        })
    except ValueError as error:
        raise CalendarError(str(error)) from error
    _store().put(params)
    # Two-way Google Calendar: also create it in Google when connected (best effort).
    from core.google_calendar_sync.google_calendar_api import push_in_background
    if scheduling_db() == PROJECT_ROOT / "data" / "scheduling" / "calendar.sqlite3":
        push_in_background(params)
    from core.assistant_platform.receipts import record
    record("calendar.create",f"Created calendar event: {params['title']}",source_path=scheduling_db(),target=params['id'],after=params)
    return params


def delete_event(event_id: str) -> None:
    store = _store()
    if not any(event.get("id") == event_id for event in store.events()):
        raise EventNotFound(event_id)
    store.delete({"id": event_id})
    from core.google_calendar_sync.google_calendar_api import remove_event
    import threading
    if scheduling_db() == PROJECT_ROOT / "data" / "scheduling" / "calendar.sqlite3":
        threading.Thread(target=remove_event, args=(event_id,), name="zaenia-google-delete", daemon=True).start()


def today() -> date:
    return datetime.now(PACIFIC).date()
