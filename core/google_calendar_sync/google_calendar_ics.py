from __future__ import annotations

from datetime import (
    date,
    datetime,
    time,
    timedelta,
)
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import recurring_ical_events
import requests
import yaml
from icalendar import Calendar

from core.calendar_context.calendar_context import (
    CALENDAR_PATH,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

GOOGLE_CALENDAR_DIR = (
    PROJECT_ROOT
    / "data"
    / "google_calendar"
)

ICS_URL_PATH = (
    GOOGLE_CALENDAR_DIR
    / "google_calendar_ics_url.txt"
)

LOCAL_TIMEZONE = (
    ZoneInfo(
        "America/Los_Angeles"
    )
)

GOOGLE_SYNC_SOURCE = (
    "google_ics"
)


def load_ics_url() -> str:
    """
    Read Zack's private Google Calendar iCal URL.

    Treat this URL like a credential.
    """

    if not ICS_URL_PATH.exists():
        raise FileNotFoundError(
            f"Missing iCal URL file: "
            f"{ICS_URL_PATH}"
        )

    url = (
        ICS_URL_PATH
        .read_text(
            encoding="utf-8"
        )
        .strip()
    )

    if not url:
        raise RuntimeError(
            f"iCal URL file is empty: "
            f"{ICS_URL_PATH}"
        )

    return url


def fetch_ics_calendar() -> Calendar:
    """
    Download the private Google Calendar iCal feed.
    """

    url = (
        load_ics_url()
    )

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    return Calendar.from_ical(
        response.content
    )


def load_local_calendar_config(
) -> dict[str, Any]:
    if not CALENDAR_PATH.exists():
        raise FileNotFoundError(
            f"Missing ZÆNIA local calendar file: "
            f"{CALENDAR_PATH}"
        )

    with CALENDAR_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return (
            yaml.safe_load(
                file
            )
            or {}
        )


def save_local_calendar_config(config: dict[str, Any]) -> None:
    # Shared protected writer also covers direct Google-sync CLI launches.
    from core.calendar_context.calendar_update_main import save_config
    save_config(config)


def as_local_datetime(
    value: Any,
) -> datetime:
    """
    Convert Google Calendar values into local Pacific time.
    """

    if isinstance(
        value,
        datetime,
    ):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=LOCAL_TIMEZONE
            )

        return value.astimezone(
            LOCAL_TIMEZONE
        )

    if isinstance(
        value,
        date,
    ):
        return datetime.combine(
            value,
            time.min,
            tzinfo=LOCAL_TIMEZONE,
        )

    raise TypeError(
        "Unsupported calendar time value: "
        f"{value!r}"
    )


def clean_text(
    value: Any,
    max_length: int = 180,
) -> str:
    if value is None:
        return ""

    text = (
        str(value)
        .replace(
            "\\n",
            " ",
        )
        .replace(
            "\n",
            " ",
        )
        .strip()
    )

    text = " ".join(
        text.split()
    )

    if len(
        text
    ) > max_length:
        return (
            text[
                : max_length - 3
            ]
            .rstrip()
            + "..."
        )

    return text


def build_reminder_from_fields(
    *,
    location: str,
    description: str,
) -> str | None:
    if (
        location
        and description
    ):
        return (
            f"Location: {location}. "
            f"{description}"
        )

    if location:
        return (
            f"Location: {location}."
        )

    if description:
        return description

    return None


def get_event_end(
    event: Any,
    start_dt: datetime,
    is_all_day: bool,
) -> tuple[
    datetime | None,
    str | None,
]:
    """
    Preserve the end time when Google provides one.
    """

    dtend_raw = (
        event.get(
            "DTEND"
        )
    )

    if not dtend_raw:
        return (
            None,
            None,
        )

    end_dt = (
        as_local_datetime(
            dtend_raw.dt
        )
    )

    if is_all_day:
        return (
            end_dt,
            None,
        )

    return (
        end_dt,
        end_dt.strftime(
            "%H:%M"
        ),
    )


def convert_ical_event(
    event: Any,
) -> dict[str, Any] | None:
    """
    Convert one Google event into ZÆNIA's richer local format.
    """

    summary = clean_text(
        event.get(
            "SUMMARY"
        ),
        max_length=120,
    )

    if not summary:
        summary = (
            "Untitled calendar event"
        )

    dtstart_raw = (
        event.get(
            "DTSTART"
        )
    )

    if not dtstart_raw:
        return None

    start_value = (
        dtstart_raw.dt
    )

    start_dt = (
        as_local_datetime(
            start_value
        )
    )

    is_all_day = (
        isinstance(
            start_value,
            date,
        )
        and not isinstance(
            start_value,
            datetime,
        )
    )

    event_time = (
        "00:00"
        if is_all_day
        else start_dt.strftime(
            "%H:%M"
        )
    )

    end_dt, end_time = (
        get_event_end(
            event,
            start_dt,
            is_all_day,
        )
    )

    location = clean_text(
        event.get(
            "LOCATION"
        ),
        max_length=160,
    )

    description = clean_text(
        event.get(
            "DESCRIPTION"
        ),
        max_length=300,
    )

    uid = clean_text(
        event.get(
            "UID"
        ),
        max_length=200,
    )

    return {
        "date": (
            start_dt.date()
            .isoformat()
        ),
        "time": event_time,
        "end_time": end_time,
        "all_day": is_all_day,
        "title": summary,
        "description": (
            description
            or None
        ),
        "location": (
            location
            or None
        ),
        "reminder": (
            build_reminder_from_fields(
                location=location,
                description=description,
            )
        ),
        "source": (
            GOOGLE_SYNC_SOURCE
        ),
        "google_uid": uid,
    }


def get_google_events_between(
    start_date: date,
    days: int = 2,
) -> list[dict[str, Any]]:
    calendar = (
        fetch_ics_calendar()
    )

    start_dt = datetime.combine(
        start_date,
        time.min,
        tzinfo=LOCAL_TIMEZONE,
    )

    end_dt = (
        start_dt
        + timedelta(
            days=days
        )
    )

    raw_events = (
        recurring_ical_events
        .of(
            calendar
        )
        .between(
            start_dt,
            end_dt,
        )
    )

    converted_events: list[
        dict[str, Any]
    ] = []

    for raw_event in raw_events:
        converted = (
            convert_ical_event(
                raw_event
            )
        )

        if converted:
            converted_events.append(
                converted
            )

    converted_events.sort(
        key=lambda item: (
            item["date"],
            item["time"],
            item["title"],
        )
    )

    return converted_events


def remove_existing_google_events(
    config: dict[str, Any],
    target_dates: set[str],
) -> dict[str, Any]:
    existing_events = (
        config.get(
            "events"
        )
        or []
    )

    kept_events = []

    for event in existing_events:
        event_date = (
            event.get(
                "date"
            )
        )

        event_source = (
            event.get(
                "source"
            )
        )

        if (
            event_date
            in target_dates
            and event_source
            == GOOGLE_SYNC_SOURCE
        ):
            continue

        kept_events.append(
            event
        )

    config[
        "events"
    ] = kept_events

    return config


def sync_google_calendar_to_local(
    start_date: date | None = None,
    days: int = 2,
) -> dict[str, Any]:
    start_date = (
        start_date
        or datetime.now(
            LOCAL_TIMEZONE
        ).date()
    )

    google_events = (
        get_google_events_between(
            start_date=(
                start_date
            ),
            days=days,
        )
    )

    target_dates = {
        (
            start_date
            + timedelta(
                days=offset
            )
        ).isoformat()
        for offset in range(
            days
        )
    }

    config = (
        load_local_calendar_config()
    )

    config = (
        remove_existing_google_events(
            config,
            target_dates,
        )
    )

    local_events = (
        config.get(
            "events"
        )
        or []
    )

    local_events.extend(
        google_events
    )

    local_events.sort(
        key=lambda item: (
            item.get(
                "date",
                "",
            ),
            item.get(
                "time",
                "",
            ),
            item.get(
                "title",
                "",
            ),
        )
    )

    config[
        "events"
    ] = local_events

    save_local_calendar_config(
        config
    )

    return {
        "start_date": (
            start_date.isoformat()
        ),
        "days": days,
        "target_dates": sorted(
            target_dates
        ),
        "imported_count": len(
            google_events
        ),
        "events": google_events,
    }