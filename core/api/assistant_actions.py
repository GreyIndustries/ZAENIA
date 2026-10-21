"""Conservative, local chat-to-action proposals. This module never executes actions.

Only explicit creation requests are recognized. A proposal contains the exact
body of an existing UI endpoint; the caller must obtain confirmation and use
that endpoint's normal authorization before creating anything. Unrecognized
conversation returns ``None`` so the ordinary assistant can answer it.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")

_NAME = r"(?:zay|zae|zænia|zaenia)"
_ADDRESS = re.compile(rf"^(?:hey\s+)?{_NAME}(?:\s*[,!:]\s*|\s+)", re.IGNORECASE)
_POLITE = re.compile(r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?", re.IGNORECASE)
_TASK = re.compile(r"^(?:add|create)\s+(?:a\s+)?task(?:\s+to\s+|\s*:\s*|\s+|$)(?P<title>.*)$", re.IGNORECASE)
_TASK_LIST = re.compile(r"^add\s+(?P<title>.+?)\s+to\s+(?:my|the)\s+tasks(?:\s+list)?$", re.IGNORECASE)
_SCHEDULE = re.compile(r"^schedule(?:\s+|$)(?P<body>.*)$", re.IGNORECASE)
_CALENDAR_ADD = re.compile(
    r"^add\s+(?P<title>.+?)\s+to\s+(?:my|the)\s+calendar(?:\s+(?P<when>.*))?$", re.IGNORECASE
)
_EVENT = re.compile(r"^(?:add|create)\s+(?:a\s+|an\s+)?(?:calendar\s+)?event(?:\s+for\s+|\s*:\s*|\s+|$)(?P<body>.*)$", re.IGNORECASE)
_REMINDER_REQUEST = re.compile(r"^(?:remind\s+me|set\s+(?:a\s+)?reminder|add\s+(?:a\s+)?reminder)(?:\s|$)", re.IGNORECASE)
_REMINDER = re.compile(r"\b(?:remind(?:er|ers)?|notify|notification|notifications|alert|alerts)\b|\b(?:ping|text|email)\s+me\b", re.IGNORECASE)
_RECURRENCE = re.compile(r"\b(?:every|each|hourly|daily|weekly|biweekly|fortnightly|monthly|quarterly|yearly|annual(?:ly)?|weekdays?|weekends?|recurr(?:ing|ence)|repeat(?:s|ing)?)\b|\b(?:once|twice)\s+(?:a|per)\b", re.IGNORECASE)
_NON_REQUEST = re.compile(
    r"\b(?:don't|don’t|do\s+not|not|never|if|unless|whether|instead\s+of|pretend|hypothetically|for\s+example|what\s+if)\b"
    r"|\b(?:or|but)\s+(?:should|can|could|would)\b", re.IGNORECASE
)
_EXTRA_COMMAND = re.compile(
    r"\b(?:and|then|also)\s+(?:please\s+)?(?:add|create|schedule|delete|remove|send|email|ignore|execute|run|cancel|set|update)\b"
    r"|\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b", re.IGNORECASE
)
_DATE_TEXT = r"(?:today|tomorrow|\d{4}-\d{2}-\d{2})"
_DATE = re.compile(rf"\b{_DATE_TEXT}\b", re.IGNORECASE)
_TIME_TEXT = r"(?:\d{1,2}(?::\d{2})?\s*[ap]m|\d{1,2}:\d{2})"
_TIME = re.compile(rf"\bat\s+{_TIME_TEXT}\b", re.IGNORECASE)
_WHEN = re.compile(
    rf"^(?P<title>.+?)\s+(?:on\s+)?(?P<date>{_DATE_TEXT})\s+at\s+"
    rf"(?P<time>{_TIME_TEXT})(?:\s+(?:pacific(?:\s+time)?|america/los_angeles))?$", re.IGNORECASE
)
_NUMBER_WORD = (
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)"
)
_DURATION_TEXT = (
    rf"\b(?:\d+(?:[./]\d+)?|an?|{_NUMBER_WORD}|half|quarter|couple|few|several)"
    rf"(?:[ -]+(?:{_NUMBER_WORD}|and|an?|of|half|quarter))*[ -]+"
    r"(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:h|hr|hrs|min|mins|m)\b"
)
_TEMPORAL_DETAIL = re.compile(
    _DURATION_TEXT
    + rf"|\b(?:at|by|around|about|before|after|until|till)\s+(?:the\s+)?(?:{_NUMBER_WORD}|half|quarter|"
    r"breakfast|brunch|lunch|lunchtime|dinner|dinnertime|bedtime|sunrise|sunset|dawn|dusk|closing)\b"
    r"|\b\d{1,2}(?::\d{2})?\s*[ap]m\b|\b\d{1,2}\s+o['’]clock\b"
    r"|\b(?:in|within)\s+(?:the\s+)?(?:hour|minute|day|week|month|year|moment|while)\b",
    re.IGNORECASE,
)
_CALENDAR_DETAIL = re.compile(
    # These clauses need fields the current calendar-create endpoint lacks.
    # Keeping them in the display title would not preserve their behavior.
    r"\b(?:with|at|in|inside|outside|near|via|over|on|for|from|between|until|till|through|"
    r"duration|lasting|lasts|ends?|ending|location|attendees?|invite|inviting|participants?|"
    r"UTC|GMT|EST|EDT|CST|CDT|MST|MDT|PST|PDT|timezone)\b"
    rf"|\b(?:\d{{1,2}}(?::\d{{2}})?|{_NUMBER_WORD})\s*(?:-|to)\s*(?:\d{{1,2}}|{_NUMBER_WORD})\b",
    re.IGNORECASE,
)
_TASK_CONSTRAINT = re.compile(
    r"\b(?:today|tomorrow|tonight|later|next|yesterday|noon|midnight|morning|afternoon|evening|deadline|due|before|after|priority|urgent|asap|when|whenever|soon|sometime|someday)\b"
    r"|\b(?:at|by|in|on|within)\s+(?:the\s+)?\d|\b\d{1,2}:\d{2}\b|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b"
    r"|\b(?:on|by)\s+(?:jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)\b"
    r"|\b(?:in|within)\s+(?:an?|one|two|three|four|five|six|seven|eight|nine|ten|half)\s+(?:hour|minute|day|week|month|year)"
    r"|\b(?:by|this)\s+(?:the\s+)?(?:end|week|month|year)\b", re.IGNORECASE
)


def _clarify(reply: str) -> dict[str, Any]:
    return {"reply": reply}


def _wall(day: date, at: time) -> datetime | None:
    """Return a unique Pacific instant; reject DST gaps and repeated times."""
    naive = datetime.combine(day, at)
    candidates = [naive.replace(tzinfo=PACIFIC, fold=fold) for fold in (0, 1)]
    valid = [candidate for candidate in candidates
             if candidate.astimezone(timezone.utc).astimezone(PACIFIC).replace(tzinfo=None) == naive]
    if not valid or len({candidate.utcoffset() for candidate in valid}) != 1:
        return None
    return valid[0]


def _clock(value: str) -> time | None:
    value = re.sub(r"\s+", "", value.lower())
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?([ap]m)?", value)
    if match is None:
        return None
    hour, minute = int(match[1]), int(match[2] or 0)
    if match[3]:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if match[3] == "pm" else 0)
    elif match[2] is None:
        return None
    try:
        return time(hour, minute)
    except ValueError:
        return None


def _calendar(body: str, now: datetime) -> dict[str, Any]:
    match = _WHEN.fullmatch(body)
    if match is None:
        if _DATE.search(body) is None:
            return _clarify("What date should I use? Give today, tomorrow, or a date like 2026-10-20, and a time such as 3 pm or 15:00 Pacific.")
        if _TIME.search(body) is None:
            return _clarify("What time should I use? Give an explicit time such as 3 pm or 15:00 Pacific.")
        return _clarify("Please give one event title, date, and time in Pacific time. I need clarification on the extra details before preparing it.")
    title = match["title"].strip()
    if not title or len(title) > 200:
        return _clarify("Give the event a title of 1 to 200 characters.")
    if _DATE.search(title) or _TIME.search(title):
        return _clarify("Which single date and time should I use for this event?")
    if _TEMPORAL_DETAIL.search(title) or _TASK_CONSTRAINT.search(title) or _CALENDAR_DETAIL.search(title):
        return _clarify("This request includes extra scheduling details, such as a duration, location, attendee, or another time. Chat can currently prepare an event title, date, and start time only. Please clarify those details before I prepare it.")
    date_text = match["date"].lower()
    try:
        day = now.date() + timedelta(days=1 if date_text == "tomorrow" else 0) if date_text in ("today", "tomorrow") else date.fromisoformat(date_text)
    except (ValueError, OverflowError):
        return _clarify("That date is not valid. Give a date like 2026-10-20.")
    at = _clock(match["time"])
    if at is None:
        return _clarify("That time is not valid. Give a time such as 3 pm or 15:00 Pacific.")
    start = _wall(day, at)
    if start is None:
        return _clarify("That Pacific time is skipped or occurs twice because of daylight saving time. Choose a different, unambiguous time.")
    if start.astimezone(timezone.utc) <= now.astimezone(timezone.utc):
        return _clarify("That date and time is in the past. What future date and time should I use?")
    return {
        "reply": f"Ready to add {title} on {day.isoformat()} at {at.strftime('%H:%M')} Pacific. Review and confirm to create it.",
        "proposal": {
            "kind": "calendar.create", "title": f"Schedule: {title}",
            "parameters": {"title": title, "date": day.isoformat(), "time": at.strftime("%H:%M"), "recurrence": "none"},
        },
    }


def propose_action(message: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    """Prepare an explicit task/event request, or ask about unsupported details.

    ``now`` defaults to the Pacific clock. An injected naive datetime is treated
    as Pacific wall time. There is no persistent state and no follow-up inference:
    each proposal must be a complete request in its own message.
    """
    if not isinstance(message, str) or len(message) > 8000:
        return None
    # Single-line, plain requests only. Quoted/injected conversation is not an
    # instruction, and two commands must never become one partial proposal.
    if any(not character.isprintable() for character in message) or any(token in message for token in ('"', '“', '”', '`', ';', '&&', '||', '<', '>')):
        return None
    text = message.strip()
    if not text or re.search(r"(?:^|\s)['‘]|['’](?:\s|$)", text) or _NON_REQUEST.search(text) or _EXTRA_COMMAND.search(text):
        return None
    text = _ADDRESS.sub("", text, count=1)
    polite = _POLITE.match(text)
    question_request = bool(re.match(r"^(?:can|could|would)\s+you\b", text, re.IGNORECASE))
    text = text[polite.end():].strip() if polite else text
    # A terminal question mark is allowed only on a polite creation request.
    if text.endswith("?"):
        if not question_request:
            return None
        text = text[:-1].rstrip()
    if "?" in text:
        return None
    text = re.sub(r"(?:,\s+please)?[.!]?$", "", text, flags=re.IGNORECASE).strip()
    task = _TASK.fullmatch(text) or _TASK_LIST.fullmatch(text)
    schedule = _SCHEDULE.fullmatch(text) or _EVENT.fullmatch(text)
    calendar_add = _CALENDAR_ADD.fullmatch(text)
    reminder = _REMINDER_REQUEST.match(text)
    if task is None and schedule is None and calendar_add is None and reminder is None:
        return None
    if reminder or _REMINDER.search(text):
        return _clarify("I can't prepare a notification or reminder from chat yet. Would you like a plain task, or a calendar event with an explicit date and time?")
    if _RECURRENCE.search(text):
        return _clarify("Recurring actions need more setup. I can prepare one task or one calendar event; what single occurrence should I use?")
    if task is not None:
        title = task["title"].strip()
        if not title or len(title) > 180:
            return _clarify("Give the task a title of 1 to 180 characters.")
        if _TASK_CONSTRAINT.search(title) or _TEMPORAL_DETAIL.search(title):
            return _clarify("This request includes timing or priority details. I can prepare a plain task with Normal priority and no deadline, or a calendar event with an explicit date and time. Which should I use?")
        return {
            "reply": f"Ready to add the task: {title}. Review and confirm to create it.",
            "proposal": {"kind": "task.create", "title": f"Add task: {title}",
                         "parameters": {"title": title, "priority": "Normal", "deadline": None}},
        }
    body = schedule["body"] if schedule is not None else f"{calendar_add['title']} {calendar_add['when'] or ''}".strip()
    current = datetime.now(PACIFIC) if now is None else now
    current = current.replace(tzinfo=PACIFIC) if current.tzinfo is None else current.astimezone(PACIFIC)
    return _calendar(body, current)
