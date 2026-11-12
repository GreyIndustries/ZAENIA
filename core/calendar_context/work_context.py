from __future__ import annotations

import re
from typing import Any


OFF_KEYWORDS = (
    "donsa",
    "day off",
    "off day",
    "off work",
    "off duty",
    "pass day",
    "training holiday",
    "holiday",
)

LEAVE_KEYWORDS = (
    "leave",
    "pto",
    "vacation",
)

LATE_CALL_KEYWORDS = (
    "late call",
    "late work call",
    "late report",
    "report late",
)

CLASS_KEYWORDS = (
    "class",
    "course",
    "school",
    "training",
    "certification",
    "academy",
)

DUTY_KEYWORDS = (
    "staff duty",
    "cq",
    "charge of quarters",
    "sdo",
    "duty shift",
    "duty desk",
    "runner duty",
)

FIELD_KEYWORDS = (
    "field",
    "ftx",
    "field exercise",
    "field training",
    "deployment exercise",
)

RANGE_KEYWORDS = (
    "range",
    "weapons qual",
    "weapons qualification",
    "qualification range",
    "live fire",
)

ASSIGNMENT_KEYWORDS = (
    "detail",
    "assigned to",
    "assignment",
    "tasking",
    "support mission",
    "mission support",
)

APPOINTMENT_KEYWORDS = (
    "appointment",
    "medical",
    "dental",
    "clinic",
    "winder",
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .lower()
        .strip()
        .split()
    )


def event_search_text(
    event: dict[str, Any],
) -> str:
    """
    Combine calendar fields that may contain useful work context.
    """

    parts = [
        event.get("title"),
        event.get("description"),
        event.get("location"),
        event.get("reminder"),
    ]

    return " ".join(
        normalize_text(part)
        for part in parts
        if part
    )


def contains_any(
    text: str,
    keywords: tuple[str, ...],
) -> bool:
    return any(
        keyword in text
        for keyword in keywords
    )


def normalize_clock_value(
    raw: str,
) -> str | None:
    """
    Convert strings such as:

        0930
        9:30
        09:30

    into HH:MM.
    """

    value = raw.strip()

    match = re.fullmatch(
        r"(\d{1,2}):?(\d{2})",
        value,
    )

    if not match:
        return None

    hour = int(
        match.group(1)
    )

    minute = int(
        match.group(2)
    )

    if not (
        0 <= hour <= 23
        and 0 <= minute <= 59
    ):
        return None

    return f"{hour:02d}:{minute:02d}"


def extract_time_from_text(
    text: str,
) -> str | None:
    """
    Find likely military or normal clock times embedded in event text.
    """

    patterns = (
        r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
        r"\b([01]\d|2[0-3])([0-5]\d)\b",
        r"\b(\d)([0-5]\d)\b",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
        )

        if not match:
            continue

        candidate = (
            f"{match.group(1)}"
            f"{match.group(2)}"
        )

        normalized = (
            normalize_clock_value(
                candidate
            )
        )

        if normalized:
            return normalized

    return None


def classify_event(
    event: dict[str, Any],
) -> dict[str, Any]:
    """
    Classify one calendar event into work-context signals.

    This classification is descriptive. It does not modify the calendar.
    """

    text = (
        event_search_text(
            event
        )
    )

    all_day = bool(
        event.get(
            "all_day",
            False,
        )
    )

    result = {
        "event_title": (
            event.get(
                "title",
                "Untitled event",
            )
        ),
        "all_day": all_day,
        "is_off": False,
        "is_leave": False,
        "is_late_call": False,
        "is_all_day_class": False,
        "is_class": False,
        "is_duty": False,
        "is_field": False,
        "is_range": False,
        "is_assignment": False,
        "is_appointment": False,
        "report_time": None,
    }

    if contains_any(
        text,
        OFF_KEYWORDS,
    ):
        result["is_off"] = True

    if contains_any(
        text,
        LEAVE_KEYWORDS,
    ):
        result["is_leave"] = True

    if contains_any(
        text,
        LATE_CALL_KEYWORDS,
    ):
        result["is_late_call"] = True

        result["report_time"] = (
            extract_time_from_text(
                text
            )
            or event.get(
                "time"
            )
        )

    if contains_any(
        text,
        CLASS_KEYWORDS,
    ):
        result["is_class"] = True

        if all_day:
            result[
                "is_all_day_class"
            ] = True

    if contains_any(
        text,
        DUTY_KEYWORDS,
    ):
        result["is_duty"] = True

    if contains_any(
        text,
        FIELD_KEYWORDS,
    ):
        result["is_field"] = True

    if contains_any(
        text,
        RANGE_KEYWORDS,
    ):
        result["is_range"] = True

    if contains_any(
        text,
        ASSIGNMENT_KEYWORDS,
    ):
        result["is_assignment"] = True

    if contains_any(
        text,
        APPOINTMENT_KEYWORDS,
    ):
        result["is_appointment"] = True

    return result


def determine_primary_context(
    *,
    base_status: str,
    classifications: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Determine the day's primary work context.

    Calendar events may override the normal weekday schedule.
    """

    context_type = (
        "normal_work"
        if base_status == "on_duty"
        else base_status
    )

    reason = (
        "default_schedule"
    )

    report_time = None

    if base_status in {
        "off_duty",
        "leave",
    }:
        context_type = (
            base_status
        )

    for item in classifications:
        if item.get(
            "is_off"
        ):
            context_type = "off"
            reason = "calendar_event"

        if item.get(
            "is_leave"
        ):
            context_type = "leave"
            reason = "calendar_event"

    for item in classifications:
        if item.get(
            "is_duty"
        ):
            context_type = "duty"
            reason = "calendar_event"

    for item in classifications:
        if item.get(
            "is_field"
        ):
            context_type = "field"
            reason = "calendar_event"

        elif item.get(
            "is_range"
        ):
            context_type = "range"
            reason = "calendar_event"

        elif item.get(
            "is_assignment"
        ):
            context_type = "assignment"
            reason = "calendar_event"

    for item in classifications:
        if item.get(
            "is_all_day_class"
        ):
            context_type = "all_day_class"
            reason = "calendar_event"

    for item in classifications:
        if item.get(
            "is_late_call"
        ):
            context_type = "late_call"
            reason = "calendar_event"
            report_time = (
                item.get(
                    "report_time"
                )
            )

    appointments = [
        item
        for item in classifications
        if item.get(
            "is_appointment"
        )
    ]

    return {
        "type": context_type,
        "reason": reason,
        "report_time": report_time,
        "normal_work_schedule_suppressed": (
            context_type
            in {
                "off",
                "off_duty",
                "leave",
                "late_call",
                "all_day_class",
                "duty",
                "field",
                "range",
                "assignment",
            }
        ),
        "has_appointment": bool(
            appointments
        ),
        "signals": classifications,
    }


def build_work_context(
    *,
    base_status: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    classifications = [
        classify_event(
            event
        )
        for event in events
    ]

    return determine_primary_context(
        base_status=base_status,
        classifications=classifications,
    )