from __future__ import annotations

import re

from datetime import (
    date,
    datetime,
    time,
)
from typing import Any
from zoneinfo import ZoneInfo

from core.briefing.briefing_personality import (
    trim_words,
)

from core.calendar_context.calendar_context import (
    build_calendar_context,
    get_calendar_timezone,
    load_calendar_config,
)

from core.traffic.traffic_client import (
    get_i5_traffic_summary,
)

from core.traffic.traffic_main import (
    get_active_window,
    load_traffic_config,
)

from core.weather.weather_client import (
    get_weather_for_location,
    weather_code_text,
)

from core.weather.weather_selector import (
    select_weather_location,
)


WORKDAY_START = time(
    hour=5,
    minute=30,
)

WORKDAY_END = time(
    hour=18,
    minute=0,
)

WORK_NAMES = (
    "Zack",
    "Zackariah",
    "Grey",
)

OFF_CONTEXT_TYPES = {
    "off",
    "off_duty",
    "leave",
    "holiday",
}

WORK_CONTEXT_TYPES = {
    "normal_work",
    "on_duty",
    "late_call",
    "all_day_class",
    "class",
    "duty",
    "field",
    "range",
    "assignment",
}


def normalize_spoken_punctuation(
    text: str,
) -> str:
    """
    Hard ZÆNIA speech rule.

    Dash-style punctuation must never be sent to text-to-speech.
    Spoken dash pauses are converted into commas.

    Normal hyphens inside words are preserved.
    """

    text = str(
        text
        or ""
    ).strip()

    if not text:
        return ""

    replacements = {
        "â€”": ", ",
        "â€“": ", ",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    text = re.sub(
        r"\s*[—–―−]\s*",
        ", ",
        text,
    )

    text = re.sub(
        r"\s+--+\s+",
        ", ",
        text,
    )

    text = re.sub(
        r"\s+-\s+",
        ", ",
        text,
    )

    text = re.sub(
        r",\s*,+",
        ", ",
        text,
    )

    text = re.sub(
        r",\s*\.",
        ".",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def format_number(
    value: Any,
    fallback: str = "unknown",
) -> str:
    if value is None:
        return fallback

    try:
        return str(
            round(
                float(value)
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return str(value)


def get_local_now() -> datetime:
    """
    Use ZÆNIA's configured calendar timezone.
    """

    try:
        config = (
            load_calendar_config()
        )

        timezone = (
            get_calendar_timezone(
                config
            )
        )

    except Exception:
        timezone = ZoneInfo(
            "America/Los_Angeles"
        )

    return datetime.now(
        timezone
    )


def parse_clock_value(
    value: Any,
) -> time | None:
    if value is None:
        return None

    text_value = str(
        value
    ).strip()

    for clock_format in (
        "%H:%M",
        "%H%M",
        "%I:%M %p",
        "%I %p",
    ):
        try:
            parsed = datetime.strptime(
                text_value,
                clock_format,
            )

            return parsed.time()

        except ValueError:
            continue

    return None


def format_clock_for_speech(
    value: Any,
) -> str:
    parsed = (
        parse_clock_value(
            value
        )
    )

    if parsed is None:
        return str(
            value
            or ""
        ).strip()

    suffix = (
        "AM"
        if parsed.hour < 12
        else "PM"
    )

    spoken_hour = (
        parsed.hour % 12
        or 12
    )

    if parsed.minute == 0:
        return (
            f"{spoken_hour} {suffix}"
        )

    return (
        f"{spoken_hour}:"
        f"{parsed.minute:02d} "
        f"{suffix}"
    )


def get_daypart(
    now: datetime,
) -> str:
    if now.hour < 12:
        return "morning"

    if now.hour < 17:
        return "afternoon"

    return "evening"


def is_currently_work_time(
    calendar_context: dict[str, Any],
    now: datetime,
) -> bool:
    """
    Sir is used on off days and after work hours.

    Zack, Zackariah, or Grey is used during active work hours.
    """

    work_context = (
        calendar_context.get(
            "work_context",
            {},
        )
        or {}
    )

    context_type = str(
        work_context.get(
            "type",
            "",
        )
        or ""
    ).strip().lower()

    base_status = str(
        calendar_context.get(
            "status",
            "",
        )
        or ""
    ).strip().lower()

    if (
        context_type
        in OFF_CONTEXT_TYPES
    ):
        return False

    if (
        base_status
        in {
            "off_duty",
            "leave",
        }
    ):
        return False

    current_time = (
        now.time()
    )

    if (
        current_time < WORKDAY_START
        or current_time >= WORKDAY_END
    ):
        return False

    if (
        context_type
        == "late_call"
    ):
        report_time = (
            parse_clock_value(
                work_context.get(
                    "report_time"
                )
            )
        )

        if (
            report_time is not None
            and current_time < report_time
        ):
            return False

    if (
        context_type
        in WORK_CONTEXT_TYPES
    ):
        return True

    return (
        base_status
        == "on_duty"
    )


def choose_work_name(
    now: datetime,
) -> str:
    rotation_value = (
        now.date().toordinal()
        + now.hour
    )

    index = (
        rotation_value
        % len(
            WORK_NAMES
        )
    )

    return WORK_NAMES[
        index
    ]


def choose_address_name(
    calendar_context: dict[str, Any],
    now: datetime,
) -> str:
    if not is_currently_work_time(
        calendar_context,
        now,
    ):
        return "Sir"

    return choose_work_name(
        now
    )


def build_greeting(
    calendar_context: dict[str, Any],
    now: datetime,
) -> str:
    return (
        f"Good {get_daypart(now)}, "
        f"{choose_address_name(calendar_context, now)}."
    )


def format_event_for_speech(
    event: dict[str, Any],
) -> str:
    title = str(
        event.get(
            "title",
            "event",
        )
        or "event"
    ).strip()

    title = (
        normalize_spoken_punctuation(
            title
        )
    )

    if event.get(
        "all_day"
    ):
        return (
            f"{title} all day"
        )

    event_time = str(
        event.get(
            "time",
            "",
        )
        or ""
    ).strip()

    if event_time:
        return (
            f"{title} at "
            f"{format_clock_for_speech(event_time)}"
        )

    return title


def build_clear_schedule_sentence(
    now: datetime,
) -> str:
    return "Nothing on schedule."


def build_calendar_sentence(
    calendar_context: dict[str, Any],
    now: datetime,
) -> str:
    if not calendar_context.get(
        "enabled",
        True,
    ):
        return (
            "Calendar information is unavailable."
        )

    events = (
        calendar_context.get(
            "events",
            [],
        )
        or []
    )

    reminders = (
        calendar_context.get(
            "reminders",
            [],
        )
        or []
    )

    clean_reminders: list[str] = []

    for reminder in reminders:
        reminder_text = (
            normalize_spoken_punctuation(
                str(
                    reminder
                    or ""
                ).strip()
            )
        )

        if (
            reminder_text
            and reminder_text
            not in clean_reminders
        ):
            clean_reminders.append(
                reminder_text
            )

    if (
        not events
        and not clean_reminders
    ):
        return (
            build_clear_schedule_sentence(
                now
            )
        )

    sentence_parts: list[str] = []

    if events:
        max_spoken_events = 4

        spoken_events = [
            format_event_for_speech(
                event
            )
            for event in events[
                :max_spoken_events
            ]
        ]

        if len(
            spoken_events
        ) == 1:
            sentence_parts.append(
                "On your schedule, "
                f"{spoken_events[0]}."
            )

        else:
            sentence_parts.append(
                "On your schedule: "
                + "; ".join(
                    spoken_events[:-1]
                )
                + "; and "
                + spoken_events[-1]
                + "."
            )

        remaining_events = (
            len(events)
            - max_spoken_events
        )

        if remaining_events > 0:
            item_word = (
                "item"
                if remaining_events == 1
                else "items"
            )

            sentence_parts.append(
                f"You also have "
                f"{remaining_events} more "
                f"{item_word} today."
            )

    if clean_reminders:
        spoken_reminders = (
            clean_reminders[:2]
        )

        if len(
            spoken_reminders
        ) == 1:
            sentence_parts.append(
                "Reminder: "
                f"{spoken_reminders[0]}."
            )

        else:
            sentence_parts.append(
                "Reminders: "
                f"{spoken_reminders[0]}; "
                f"and {spoken_reminders[1]}."
            )

    if not sentence_parts:
        return (
            build_clear_schedule_sentence(
                now
            )
        )

    return (
        normalize_spoken_punctuation(
            " ".join(
                sentence_parts
            )
        )
    )


def build_weather_sentence(
    weather_result: dict[str, Any],
) -> str:
    forecast = (
        weather_result.get(
            "forecast",
            {},
        )
        or {}
    )

    current = (
        forecast.get(
            "current",
            {},
        )
        or {}
    )

    daily = (
        forecast.get(
            "daily",
            {},
        )
        or {}
    )

    temperature = (
        current.get(
            "temperature_2m"
        )
    )

    weather_code = (
        current.get(
            "weather_code"
        )
    )

    highs = (
        daily.get(
            "temperature_2m_max"
        )
        or []
    )

    if temperature is None:
        return (
            "Weather is unavailable right now."
        )

    temp = (
        format_number(
            temperature
        )
    )

    condition = (
        weather_code_text(
            weather_code
        )
        if weather_code is not None
        else ""
    )

    condition_clean = str(
        condition
        or ""
    ).strip().lower()

    high_value = (
        highs[0]
        if highs
        else None
    )

    high = (
        format_number(
            high_value
        )
        if high_value is not None
        else None
    )

    if condition_clean:
        sentence = (
            f"Outside, it's {temp} "
            f"and {condition_clean}"
        )

    else:
        sentence = (
            f"Outside, it's {temp} degrees"
        )

    if high is not None:
        try:
            if (
                float(high_value)
                > float(temperature)
            ):
                sentence += (
                    f", warming to around {high}"
                )

            else:
                sentence += (
                    f", with a high around {high}"
                )

        except (
            TypeError,
            ValueError,
        ):
            sentence += (
                f", with a high around {high}"
            )

    sentence += "."

    return (
        normalize_spoken_punctuation(
            sentence
        )
    )


def simplify_traffic_message(
    traffic_result: dict[str, Any] | None,
    summary: str | None,
    *,
    traffic_checked: bool,
) -> str:
    if not traffic_checked:
        return ""

    if not traffic_result:
        return (
            "Traffic data is unavailable right now."
        )

    raw_summary = (
        normalize_spoken_punctuation(
            str(
                summary
                or traffic_result.get(
                    "summary",
                    "",
                )
                or ""
            ).strip()
        )
    )

    lower = (
        raw_summary.lower()
    )

    unavailable_markers = [
        "request failed",
        "connection failed",
        "network error",
        "timed out",
        "timeout",
        "service unavailable",
        "api unavailable",
    ]

    if any(
        marker in lower
        for marker in unavailable_markers
    ):
        return (
            "Traffic data is unavailable right now."
        )

    clear_markers = [
        "no matching",
        "no incident",
        "no incidents",
        "no delay",
        "no delays",
        "no traffic news",
        "unclear traffic",
        "unknown traffic",
        "sensor points",
        "no useful traffic update",
        "traffic is clear",
    ]

    if (
        not raw_summary
        or any(
            marker in lower
            for marker in clear_markers
        )
    ):
        return (
            "Traffic is moving normally, "
            "with no notable delays."
        )

    return raw_summary


def build_drive_briefing(
    include_traffic_force: bool = False,
    calendar_date: date | None = None,
) -> dict[str, Any]:
    """
    Build Zack's concise CarPlay briefing.

    Spoken order:

        greeting
        calendar and tasks
        weather
        traffic

    Dash-style punctuation is removed before speech output.
    """

    now = (
        get_local_now()
    )

    location = (
        select_weather_location()
    )

    weather_result = (
        get_weather_for_location(
            location
        )
    )

    weather_sentence = (
        build_weather_sentence(
            weather_result
        )
    )

    calendar_context = (
        build_calendar_context(
            calendar_date
        )
    )

    greeting = (
        build_greeting(
            calendar_context,
            now,
        )
    )

    calendar_sentence = (
        build_calendar_sentence(
            calendar_context,
            now,
        )
    )

    traffic_config = (
        load_traffic_config()
    )

    active_traffic_window = (
        get_active_window(
            traffic_config
        )
    )

    traffic_included = False
    traffic_result = None
    traffic_summary = None

    if (
        active_traffic_window
        or include_traffic_force
    ):
        try:
            traffic_result = (
                get_i5_traffic_summary()
            )

            traffic_summary = str(
                traffic_result.get(
                    "summary",
                    "",
                )
                or ""
            )

        except Exception as error:
            traffic_result = {
                "success": False,
                "summary": (
                    "Traffic service unavailable: "
                    f"{error}"
                ),
            }

            traffic_summary = (
                traffic_result[
                    "summary"
                ]
            )

        traffic_included = True

    traffic_sentence = (
        simplify_traffic_message(
            traffic_result,
            traffic_summary,
            traffic_checked=(
                traffic_included
            ),
        )
    )

    parts = [
        greeting,
        calendar_sentence,
        weather_sentence,
        traffic_sentence,
    ]

    spoken_briefing = " ".join(
        part.strip()
        for part in parts
        if part
        and part.strip()
    )

    spoken_briefing = (
        trim_words(
            spoken_briefing,
            max_words=110,
        )
    )

    spoken_briefing = (
        normalize_spoken_punctuation(
            spoken_briefing
        )
    )

    address_name = (
        choose_address_name(
            calendar_context,
            now,
        )
    )

    return {
        "weather_location": (
            location
        ),
        "weather_result": (
            weather_result
        ),
        "weather_summary": (
            weather_sentence
        ),
        "calendar_context": (
            calendar_context
        ),
        "calendar_summary": (
            calendar_sentence
        ),
        "traffic_included": (
            traffic_included
        ),
        "traffic_window": (
            active_traffic_window
        ),
        "traffic_summary": (
            traffic_sentence
        ),
        "traffic_result": (
            traffic_result
        ),
        "address_name": (
            address_name
        ),
        "work_address_mode": (
            address_name
            != "Sir"
        ),
        "local_time": (
            now.isoformat()
        ),
        "spoken_briefing": (
            spoken_briefing
        ),
    }
