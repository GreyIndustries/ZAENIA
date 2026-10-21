"""Bounded, RAM-only calendar clarification shared by chat and verified voice.

This layer only fills explicitly supplied date/time slots. The canonical strict
parser validates both the intact partial request and the completed request; it
continues to reject locations, durations, recurrence, and ambiguous commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
import time

from core.api import assistant_actions as calendar_parser
from core.assistant_service import prepare_action


_HOURS = {word: index for index, word in enumerate(
    ('one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'), 1)}
_HOUR_TEXT = '(?:' + '|'.join(_HOURS) + r'|1[0-2]|[1-9])'
_MINUTE_TEXT = r'(?:fifteen|thirty|forty(?:[ -]?five))'
_SPOKEN_TIME = rf'(?P<hour>{_HOUR_TEXT})(?:\s+(?P<minute>{_MINUTE_TEXT}))?\s+(?P<meridian>[ap]\s*m)\b'
_CLOCK_SLOT = re.compile(rf'(?P<prefix>\bat\s+){_SPOKEN_TIME}', re.IGNORECASE)
_BARE_CLOCK = re.compile(rf'(?P<prefix>){_SPOKEN_TIME}', re.IGNORECASE)
_DATE_TEXT = r'(?:today|tomorrow|\d{4}-\d{2}-\d{2})'
_TIME_TEXT = r'(?:\d{1,2}(?::\d{2})?\s*[ap]m|\d{1,2}:\d{2})'
_DAY_END = re.compile(rf'^(?P<title>.+?)\s+(?:on\s+)?(?P<day>{_DATE_TEXT})$', re.IGNORECASE)
_TIME_END = re.compile(rf'^(?P<title>.+?)\s+at\s+(?P<clock>{_TIME_TEXT})(?:\s+(?:pacific(?:\s+time)?|america/los_angeles))?$', re.IGNORECASE)
_TEMPORAL_REPLY = re.compile(rf'^(?:(?:on\s+)?(?P<day>{_DATE_TEXT})(?:\s+at\s+(?P<dayclock>{_TIME_TEXT}))?|(?:at\s+)?(?P<clock>{_TIME_TEXT}))$', re.IGNORECASE)
_CANCEL = re.compile(r'^(?:cancel(?:\s+that\s+action)?|never\s*mind)[.!]?$', re.IGNORECASE)


def _numeric_clock(match):
    raw_hour = match['hour'].lower()
    hour = _HOURS[raw_hour] if raw_hour in _HOURS else int(raw_hour)
    minute = re.sub(r'[ -]', '', (match['minute'] or '').lower())
    suffix = {'fifteen': ':15', 'thirty': ':30', 'fortyfive': ':45', '': ''}[minute]
    meridian = re.sub(r'\s+', '', match['meridian'].lower())
    return f"{match['prefix']}{hour}{suffix} {meridian}"


def normalize_spoken_clocks(message: str) -> str:
    """Normalize explicit ``at ... am/pm`` slots or an exact bare clock reply.

    Number words elsewhere, unsupported minute forms, and clocks without an
    explicit meridian remain untouched. Callers should apply this only to a
    scheduling request or a calendar clarification, never to memory values.
    """
    if not isinstance(message, str):
        return message
    bare = _BARE_CLOCK.fullmatch(message)
    return _numeric_clock(bare) if bare else _CLOCK_SLOT.sub(_numeric_clock, message)


def _request_body(message):
    # Reuse the canonical anchored request grammar rather than recognizing
    # creation intents differently across chat and voice.
    text = calendar_parser._ADDRESS.sub('', message.strip(), count=1)
    text = calendar_parser._POLITE.sub('', text, count=1).strip()
    text = re.sub(r'(?:,\s+please)?[.!?]?$', '', text, flags=re.IGNORECASE).strip()
    event = calendar_parser._SCHEDULE.fullmatch(text) or calendar_parser._EVENT.fullmatch(text)
    if event:
        return event['body'].strip()
    added = calendar_parser._CALENDAR_ADD.fullmatch(text)
    if added:
        return f"{added['title']} {added['when'] or ''}".strip()
    return None


@dataclass(frozen=True)
class _CalendarDraft:
    title: str
    day: str | None
    clock: str | None
    expires: float


class ActionDialogue:
    def __init__(self, ttl=300, clock=time.monotonic):
        if not isinstance(ttl, (int, float)) or isinstance(ttl, bool) or not math.isfinite(ttl) or not 0 < ttl <= 300:
            raise ValueError('Calendar clarification expires within 300 seconds.')
        self.ttl, self.clock = float(ttl), clock
        self._draft = None

    def clear(self):
        self._draft = None

    def has_draft(self):
        if self._draft is not None and self.clock() >= self._draft.expires:
            self.clear()
        return self._draft is not None

    @staticmethod
    def _complete(title, day, clock):
        return f'schedule {title} {day} at {clock}'

    @staticmethod
    def _question(draft):
        if draft.day is None and draft.clock is None:
            return {'reply': f'What date and time should I use for {draft.title}? Say tomorrow at 3 pm, for example.'}
        if draft.day is None:
            return {'reply': f'What date should I use for {draft.title}? Say today, tomorrow, or a date like 2026-10-20.'}
        return {'reply': f'What time should I use for {draft.title}? Say a time such as 3 pm or 15:00 Pacific.'}

    def _validate_partial(self, title, day, clock, now):
        # 23:59 is the latest supported start, so a valid 'today' draft is not
        # rejected simply because noon has already passed.
        probe = self._complete(title, day or 'tomorrow', clock or '23:59')
        return prepare_action(probe, now=now)

    def prepare(self, message, now: datetime | None = None):
        if not isinstance(message, str) or len(message) > 8000:
            self.clear()
            return None
        active = self._draft if self.has_draft() else None
        short = calendar_parser._ADDRESS.sub('', message.strip(), count=1)
        if active is not None and _CANCEL.fullmatch(short):
            self.clear()
            return {'reply': 'Cancelled the pending calendar request.'}

        if active is not None:
            # Only a complete temporal-only turn may fill slots. Preserve all
            # other wording by clearing the draft and parsing it as a new turn.
            short = re.sub(r'[.!]$', '', short).strip()
            temporal = _TEMPORAL_REPLY.fullmatch(normalize_spoken_clocks(short))
            if temporal:
                day = temporal['day'] or active.day
                clock = temporal['dayclock'] or temporal['clock'] or active.clock
                validated = self._validate_partial(active.title, day, clock, now)
                if validated is None or 'proposal' not in validated:
                    self.clear()
                    return validated
                if day is not None and clock is not None:
                    self.clear()
                    return prepare_action(self._complete(active.title, day, clock), now=now)
                self._draft = _CalendarDraft(active.title, day, clock, active.expires)
                return self._question(self._draft)

        self.clear()
        body = _request_body(message)
        normalized = normalize_spoken_clocks(message) if body is not None else message
        result = prepare_action(normalized, now=now)
        if result is None or 'proposal' in result or body is None:
            return result
        body = _request_body(normalized)
        title, day, clock = body, None, None
        # A trailing 'at' after an explicit date is just an empty clock slot.
        if body.lower().endswith(' at') and _DAY_END.fullmatch(body[:-3].rstrip()):
            title = body[:-3].rstrip()
        timed = _TIME_END.fullmatch(title)
        if timed:
            title, clock = timed['title'].strip(), timed['clock']
        dated = _DAY_END.fullmatch(title)
        if dated:
            title, day = dated['title'].strip(), dated['day']
        if not title or (day is not None and clock is not None):
            return result
        validated = self._validate_partial(title, day, clock, now)
        if validated is None or 'proposal' not in validated:
            return result
        self._draft = _CalendarDraft(title, day, clock, self.clock() + self.ttl)
        return self._question(self._draft)
