from __future__ import annotations

import re
import uuid
from datetime import (
    date,
    datetime,
    time,
    timedelta,
)
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

REMINDER_DIR = (
    PROJECT_ROOT
    / "data"
    / "reminders"
)

REMINDER_PATH = (
    REMINDER_DIR
    / "reminders.yaml"
)

LOCAL_TIMEZONE = (
    ZoneInfo(
        "America/Los_Angeles"
    )
)


REMINDER_PATTERNS = (
    r"\bremind me\b",
    r"\bi need to remember\b",
    r"\bi have to remember\b",
    r"\bdon't let me forget\b",
    r"\bdo not let me forget\b",
    r"\bmake sure i remember\b",
)


NON_REMINDER_PATTERNS = (
    r"\bi remember\b",
    r"\bdo you remember\b",
    r"\bremember when\b",
    r"\bremember that time\b",
)


REFERENCE_PATTERNS = (
    "do that",
    "do it",
    "remember that",
    "remember it",
    "take care of that",
    "handle that",
    "get that done",
)


def now_local() -> datetime:
    return datetime.now(
        LOCAL_TIMEZONE
    )


def clean_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .strip()
        .split()
    )


def normalize_for_matching(
    value: Any,
) -> str:
    return (
        clean_text(
            value
        )
        .lower()
    )


def is_reminder_intent(
    utterance: str,
) -> bool:
    """
    Determine whether the sentence expresses an actual
    reminder request or intention.
    """

    text = (
        normalize_for_matching(
            utterance
        )
    )

    if not text:
        return False

    for pattern in NON_REMINDER_PATTERNS:
        if re.search(
            pattern,
            text,
        ):
            return False

    return any(
        re.search(
            pattern,
            text,
        )
        for pattern
        in REMINDER_PATTERNS
    )


def remove_reminder_language(
    utterance: str,
) -> str:
    """
    Remove reminder-request framing from the beginning
    of the sentence.
    """

    text = (
        clean_text(
            utterance
        )
    )

    patterns = (
        r"^\s*remind me(?:\s+to)?\s+",
        r"^\s*i need to remember(?:\s+to)?\s+",
        r"^\s*i have to remember(?:\s+to)?\s+",
        r"^\s*don't let me forget(?:\s+to)?\s+",
        r"^\s*do not let me forget(?:\s+to)?\s+",
        r"^\s*make sure i remember(?:\s+to)?\s+",
    )

    for pattern in patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        )

    return (
        text.strip(
            " .,"
        )
    )


def contains_reference_phrase(
    text: str,
) -> bool:
    normalized = (
        normalize_for_matching(
            text
        )
    )

    return any(
        phrase
        in normalized
        for phrase
        in REFERENCE_PATTERNS
    )


def find_previous_action(
    conversation_context: list[str],
) -> str | None:
    """
    Search recent conversation backwards for a useful
    action statement.
    """

    for utterance in reversed(
        conversation_context
    ):
        text = clean_text(
            utterance
        )

        if not text:
            continue

        if is_reminder_intent(
            text
        ):
            continue

        action_patterns = (
            r"\bi need to\s+(.+)",
            r"\bi have to\s+(.+)",
            r"\bi gotta\s+(.+)",
            r"\bi should\s+(.+)",
            r"\bneed to\s+(.+)",
            r"\bhave to\s+(.+)",
        )

        for pattern in action_patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                action = (
                    match.group(1)
                    .strip(
                        " .,"
                    )
                )

                if action:
                    return action

    return None


def resolve_reminder_title(
    utterance: str,
    conversation_context: list[str] | None = None,
) -> tuple[
    str,
    bool,
]:
    """
    Return:

        reminder title
        whether surrounding conversation was used
    """

    context = (
        conversation_context
        or []
    )

    stripped = (
        remove_reminder_language(
            utterance
        )
    )

    if contains_reference_phrase(
        stripped
    ):
        previous_action = (
            find_previous_action(
                context
            )
        )

        if previous_action:
            return (
                previous_action,
                True,
            )

    return (
        stripped,
        False,
    )


def extract_clock_time(
    text: str,
) -> time | None:
    """
    Understand:

        7 pm
        7:30 pm
        19:30
        1930
    """

    normalized = (
        normalize_for_matching(
            text
        )
    )

    twelve_hour = re.search(
        r"\b("
        r"1[0-2]|0?[1-9]"
        r")"
        r"(?::([0-5]\d))?"
        r"\s*"
        r"(am|pm)"
        r"\b",
        normalized,
    )

    if twelve_hour:
        hour = int(
            twelve_hour.group(
                1
            )
        )

        minute = int(
            twelve_hour.group(
                2
            )
            or 0
        )

        meridiem = (
            twelve_hour.group(
                3
            )
        )

        if (
            meridiem == "pm"
            and hour != 12
        ):
            hour += 12

        if (
            meridiem == "am"
            and hour == 12
        ):
            hour = 0

        return time(
            hour=hour,
            minute=minute,
        )

    twenty_four_colon = re.search(
        r"\b("
        r"[01]?\d|2[0-3]"
        r"):([0-5]\d)\b",
        normalized,
    )

    if twenty_four_colon:
        return time(
            hour=int(
                twenty_four_colon.group(
                    1
                )
            ),
            minute=int(
                twenty_four_colon.group(
                    2
                )
            ),
        )

    military = re.search(
        r"\b("
        r"[01]\d|2[0-3]"
        r")([0-5]\d)\b",
        normalized,
    )

    if military:
        return time(
            hour=int(
                military.group(
                    1
                )
            ),
            minute=int(
                military.group(
                    2
                )
            ),
        )

    return None


def resolve_due_datetime(
    utterance: str,
    reference_time: datetime | None = None,
) -> datetime | None:
    """
    Resolve deterministic natural-language date/time phrases.
    """

    reference = (
        reference_time
        or now_local()
    )

    text = (
        normalize_for_matching(
            utterance
        )
    )

    target_date: date | None = None

    if "tomorrow" in text:
        target_date = (
            reference.date()
            + timedelta(
                days=1
            )
        )

    elif "today" in text:
        target_date = (
            reference.date()
        )

    elif "tonight" in text:
        target_date = (
            reference.date()
        )

    clock = (
        extract_clock_time(
            text
        )
    )

    if (
        "tonight" in text
        and clock is None
    ):
        clock = time(
            hour=19,
            minute=0,
        )

    if (
        target_date is None
        and clock is not None
    ):
        target_date = (
            reference.date()
        )

        candidate = datetime.combine(
            target_date,
            clock,
            tzinfo=LOCAL_TIMEZONE,
        )

        if candidate <= reference:
            target_date = (
                target_date
                + timedelta(
                    days=1
                )
            )

    if target_date is None:
        return None

    if clock is None:
        clock = time(
            hour=9,
            minute=0,
        )

    return datetime.combine(
        target_date,
        clock,
        tzinfo=LOCAL_TIMEZONE,
    )


def remove_time_language(
    title: str,
) -> str:
    """
    Remove scheduling language from a DIRECT reminder command.

    Example:

        tomorrow at 7 PM to bring the radio

    becomes:

        bring the radio

    This must not be used on context-derived reminder text,
    because words like "tomorrow" may be part of the actual
    action meaning.
    """

    text = (
        clean_text(
            title
        )
    )

    substitutions = (
        r"\btomorrow\b",
        r"\btoday\b",
        r"\btonight\b",
        r"\bat\s+("
        r"1[0-2]|0?[1-9]"
        r")"
        r"(?::[0-5]\d)?"
        r"\s*(?:am|pm)\b",
        r"\bat\s+("
        r"[01]?\d|2[0-3]"
        r"):[0-5]\d\b",
        r"\bat\s+("
        r"[01]\d|2[0-3]"
        r")[0-5]\d\b",
    )

    for pattern in substitutions:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        )

    text = " ".join(
        text.split()
    )

    text = re.sub(
        r"^\s*to\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return (
        text.strip(
            " .,;-"
        )
    )


def build_reminder_proposal(
    utterance: str,
    conversation_context: list[str] | None = None,
    reference_time: datetime | None = None,
) -> dict[str, Any]:
    """
    Parse conversational speech into a reminder proposal.

    Nothing is saved here.
    """

    intent = (
        is_reminder_intent(
            utterance
        )
    )

    if not intent:
        return {
            "is_reminder": False,
            "reason": (
                "No reminder intent detected."
            ),
            "proposal": None,
        }

    raw_title, used_context = (
        resolve_reminder_title(
            utterance,
            conversation_context,
        )
    )

    # [comment omitted from source review]
    # [comment omitted from source review]
    # [comment omitted from source review]
    # [comment omitted from source review]
    # [comment omitted from source review]
    if used_context:
        title = (
            clean_text(
                raw_title
            )
            .strip(
                " .,;-"
            )
        )

    else:
        title = (
            remove_time_language(
                raw_title
            )
        )

    if not title:
        return {
            "is_reminder": True,
            "reason": (
                "Reminder intent detected, "
                "but the action is unclear."
            ),
            "proposal": None,
        }

    due_at = (
        resolve_due_datetime(
            utterance,
            reference_time,
        )
    )

    confidence = (
        0.95
        if due_at is not None
        else 0.75
    )

    if used_context:
        confidence -= 0.05

    proposal = {
        "title": title,
        "due_at": (
            due_at.isoformat()
            if due_at
            else None
        ),
        "timezone": (
            str(
                LOCAL_TIMEZONE
            )
        ),
        "used_conversation_context": (
            used_context
        ),
        "confidence": round(
            confidence,
            2,
        ),
        "source": (
            "conversation"
        ),
        "original_utterance": (
            clean_text(
                utterance
            )
        ),
    }

    return {
        "is_reminder": True,
        "reason": (
            "Reminder proposal created."
        ),
        "proposal": proposal,
    }


def load_reminders(
) -> dict[str, Any]:
    if not REMINDER_PATH.exists():
        return {
            "version": 1,
            "reminders": [],
        }

    with REMINDER_PATH.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        data = (
            yaml.safe_load(
                file
            )
            or {}
        )

    data.setdefault(
        "version",
        1,
    )

    data.setdefault(
        "reminders",
        [],
    )

    return data


def save_reminders(data: dict[str, Any]) -> None:
    raise PermissionError("Legacy bulk reminder writes are disabled. Use core.scheduling.main.")


def execute_reminder_proposal(proposal: dict[str, Any], *, authorized: bool = False,
                              engine=None, grant=None) -> dict[str, Any]:
    """Boolean claims never authorize execution. Trusted host supplies its dispatcher."""
    if engine is None:
        raise PermissionError("An authenticated RuleEngine and exact action grant are required.")
    from core.foundation.rules.models import ActionRequest
    from core.scheduling.service import validate_event
    event = validate_event({"title": proposal.get("title"), "start": proposal.get("due_at"),
                            "recurrence": proposal.get("recurrence", "none"),
                            "channels": proposal.get("channels", ["console"]),
                            **({"id":proposal["id"]} if "id" in proposal else {})})
    return engine.execute(ActionRequest("calendar.write", event), grant=grant)
