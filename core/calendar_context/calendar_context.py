from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import (
    date,
    datetime,
)
from pathlib import Path
from typing import Any, Iterable, Iterator
from zoneinfo import ZoneInfo

import yaml

from core.calendar_context.work_context import (
    build_work_context,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

CALENDAR_PATH = (
    PROJECT_ROOT
    / "core"
    / "calendar_context"
    / "zaenia_calendar.yaml"
)


# Fresh Google events supplied by a running CarPlay brief. Read-only: they
# are merged into what this request sees and are never written to the
# calendar file, so the brief needs no owner passkey. A ContextVar keeps the
# overlay private to the request that set it.
_GOOGLE_OVERLAY: ContextVar[tuple[frozenset[str], str, tuple[dict[str, Any], ...]] | None] = ContextVar(
    "zaenia_google_calendar_overlay",
    default=None,
)


@contextmanager
def google_events_overlay(
    events: Iterable[dict[str, Any]],
    target_dates: Iterable[str],
    source: str,
) -> Iterator[None]:
    """Show fresh Google events for target_dates to calendar reads in this request."""
    token = _GOOGLE_OVERLAY.set(
        (frozenset(target_dates), source, tuple(dict(event) for event in events))
    )
    try:
        yield
    finally:
        _GOOGLE_OVERLAY.reset(token)


def _apply_google_overlay(
    config: dict[str, Any],
) -> dict[str, Any]:
    overlay = _GOOGLE_OVERLAY.get()
    if overlay is None:
        return config
    dates, source, fresh = overlay
    kept = [
        event
        for event in (config.get("events") or [])
        if not (event.get("date") in dates and event.get("source") == source)
    ]
    merged = kept + [dict(event) for event in fresh]
    merged.sort(
        key=lambda item: (
            str(item.get("date") or ""),
            str(item.get("time") or ""),
            str(item.get("title") or ""),
        )
    )
    return {**config, "events": merged}


def load_calendar_config(
) -> dict[str, Any]:
    if not CALENDAR_PATH.exists():
        raise FileNotFoundError(
            f"ZÆNIA calendar file not found: "
            f"{CALENDAR_PATH}"
        )

    with CALENDAR_PATH.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        config = (
            yaml.safe_load(
                file
            )
            or {}
        )

    from core.calendar_context.duty_status import apply_overrides
    return _apply_google_overlay(apply_overrides(config))


def get_calendar_timezone(
    config: dict[str, Any],
) -> ZoneInfo:
    calendar_config = (
        config.get(
            "calendar_context",
            {},
        )
        or {}
    )

    timezone_name = (
        calendar_config.get(
            "timezone",
            "America/Los_Angeles",
        )
    )

    return ZoneInfo(
        timezone_name
    )


def get_today(
    config: dict[str, Any] | None = None,
) -> date:
    config = (
        config
        or load_calendar_config()
    )

    tz = (
        get_calendar_timezone(
            config
        )
    )

    return datetime.now(
        tz
    ).date()


def get_weekday_name(
    target_date: date,
) -> str:
    return target_date.strftime(
        "%A"
    )


def get_status_for_date(
    config: dict[str, Any],
    target_date: date,
) -> dict[str, Any]:
    """
    Resolve the baseline schedule before calendar-event
    intelligence is applied.
    """

    target_key = (
        target_date.isoformat()
    )

    weekday_name = (
        get_weekday_name(
            target_date
        )
    )

    from core.calendar_context.duty_status import LABELS
    chosen=(config.get('_owner_duty_days') or {}).get(target_key)
    if chosen in LABELS:
        return {'status':chosen,'status_label':LABELS[chosen],'note':None,
                'weekday':weekday_name,'date':target_key,'source':'owner_override'}

    special_dates = (
        config.get(
            "special_dates",
            {},
        )
        or {}
    )

    default_schedule = (
        config.get(
            "default_schedule",
            {},
        )
        or {}
    )

    status_phrases = (
        config.get(
            "status_phrases",
            {},
        )
        or {}
    )

    if target_key in special_dates:
        special = (
            special_dates[
                target_key
            ]
            or {}
        )

        status = (
            special.get(
                "status",
                "unknown",
            )
        )

        note = (
            special.get(
                "note"
            )
        )

        source = (
            "special_date"
        )

    else:
        status = (
            default_schedule.get(
                weekday_name,
                "unknown",
            )
        )

        note = None
        source = (
            "default_schedule"
        )

    return {
        "status": status,
        "status_label": (
            status_phrases.get(
                status,
                status.replace(
                    "_",
                    " ",
                ),
            )
        ),
        "note": note,
        "weekday": weekday_name,
        "date": target_key,
        "source": source,
    }


def normalize_event(
    event: dict[str, Any],
    fallback_source: str,
) -> dict[str, Any]:
    """
    Preserve useful metadata instead of flattening calendar
    events down to title/time only.
    """

    return {
        "date": (
            event.get(
                "date"
            )
        ),
        "day": (
            event.get(
                "day"
            )
        ),
        "time": (
            event.get(
                "time",
                "",
            )
        ),
        "end_time": (
            event.get(
                "end_time"
            )
        ),
        "all_day": bool(
            event.get(
                "all_day",
                False,
            )
        ),
        "title": (
            event.get(
                "title",
                "Untitled event",
            )
        ),
        "description": (
            event.get(
                "description"
            )
        ),
        "location": (
            event.get(
                "location"
            )
        ),
        "reminder": (
            event.get(
                "reminder"
            )
        ),
        "source": (
            event.get(
                "source"
            )
            or fallback_source
        ),
        "google_uid": (
            event.get(
                "google_uid"
            )
        ),
    }


def get_events_for_date(
    config: dict[str, Any],
    target_date: date,
) -> list[dict[str, Any]]:
    """
    Return one-time and recurring events for the date.
    """

    target_key = (
        target_date.isoformat()
    )

    weekday_name = (
        get_weekday_name(
            target_date
        )
    )

    matched_events: list[
        dict[str, Any]
    ] = []

    for event in (
        config.get(
            "events",
            []
        )
        or []
    ):
        if (
            event.get(
                "date"
            )
            == target_key
        ):
            matched_events.append(
                normalize_event(
                    event,
                    "one_time",
                )
            )

    for event in (
        config.get(
            "recurring_events",
            []
        )
        or []
    ):
        if (
            event.get(
                "day"
            )
            == weekday_name
        ):
            matched_events.append(
                normalize_event(
                    event,
                    "recurring",
                )
            )

    matched_events.sort(
        key=lambda item: (
            "00:00"
            if item.get(
                "all_day"
            )
            else (
                item.get(
                    "time"
                )
                or "99:99"
            )
        )
    )

    # Merge new local service events while leaving Google/YAML data intact.
    from core.scheduling.service import Store, TZ, UTC
    from datetime import time, timedelta
    database = PROJECT_ROOT / "data" / "scheduling" / "calendar.sqlite3"
    if database.exists():
        store = Store(database)
        lower = datetime.combine(target_date, time.min, tzinfo=TZ).astimezone(UTC)
        upper = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=TZ).astimezone(UTC)
        for event in store.events():
            for occurrence in store.occurrences(event, lower, upper):
                local = occurrence.astimezone(TZ)
                if local.date() == target_date:
                    matched_events.append({"id": event["id"], "date":target_key,
                        "time":local.strftime("%H:%M"), "title":event["title"],
                        "source":"local_service", "all_day":False})
        matched_events.sort(key=lambda item: item.get("time") or "00:00")
    return matched_events


def build_calendar_context(
    target_date: date | None = None,
) -> dict[str, Any]:
    """
    Build ZÆNIA's complete calendar context including inferred
    work context.
    """

    config = (
        load_calendar_config()
    )

    calendar_config = (
        config.get(
            "calendar_context",
            {},
        )
        or {}
    )

    enabled = bool(
        calendar_config.get(
            "enabled",
            True,
        )
    )

    target_date = (
        target_date
        or get_today(
            config
        )
    )

    status = (
        get_status_for_date(
            config,
            target_date,
        )
    )

    events = (
        get_events_for_date(
            config,
            target_date,
        )
    )

    first_event = (
        events[
            0
        ]
        if events
        else None
    )

    reminders = [
        event[
            "reminder"
        ]
        for event in events
        if event.get(
            "reminder"
        )
    ]

    work_context = (
        build_work_context(
            base_status=(
                status[
                    "status"
                ]
            ),
            events=events,
        )
    )
    if status['source']=='owner_override':
        work_context={**work_context,'type':{'on_duty':'normal_work','off_duty':'off_duty','class':'all_day_class','leave':'leave'}[status['status']],
                      'reason':'owner_override','report_time':None,'normal_work_schedule_suppressed':status['status']!='on_duty'}

    return {
        "enabled": enabled,
        "date": (
            target_date.isoformat()
        ),
        "weekday": (
            get_weekday_name(
                target_date
            )
        ),
        "status": (
            status[
                "status"
            ]
        ),
        "status_label": (
            status[
                "status_label"
            ]
        ),
        "status_note": (
            status[
                "note"
            ]
        ),
        "status_source": (
            status[
                "source"
            ]
        ),
        "events": events,
        "event_count": len(
            events
        ),
        "first_event": (
            first_event
        ),
        "reminders": reminders,
        "work_context": (
            work_context
        ),
    }


def build_simple_calendar_sentence(
    context: dict[str, Any],
) -> str:
    """
    Plain fallback sentence.

    Do not announce internal work-context labels unless they
    directly help the user.
    """

    if not context.get(
        "enabled",
        True,
    ):
        return (
            "Calendar context is disabled."
        )

    events = (
        context.get(
            "events",
            []
        )
        or []
    )

    if not events:
        return (
            "No upcoming events or tasks."
        )

    first_event = (
        events[
            0
        ]
    )

    title = str(
        first_event.get(
            "title",
            "calendar event",
        )
    )

    event_time = str(
        first_event.get(
            "time",
            "",
        )
    )

    if first_event.get(
        "all_day"
    ):
        return (
            f"You have {title} all day."
        )

    if event_time:
        return (
            f"Your next event is {title} "
            f"at {event_time}."
        )

    return (
        f"Your next event is {title}."
    )
