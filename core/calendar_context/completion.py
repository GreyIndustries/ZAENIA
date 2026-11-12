"""Occurrence-specific completion, separate from the provider's calendar.

No event is marked complete because time passed or because audio played.
Only an explicit answer or owner edit changes completion.
"""
from datetime import datetime, timedelta
import hashlib
import json
import re
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def occurrence(event, day):
    if event.get("all_day"):
        return None
    clock = str(event.get("time") or "").strip()
    if re.fullmatch(r"\d{3,4}", clock):
        clock = clock.zfill(4)
        clock = clock[:2] + ":" + clock[2:]
    try:
        start = datetime.fromisoformat(str(event.get("date") or day) + "T" + clock)
        if start.tzinfo is None:
            start = start.replace(tzinfo=PACIFIC)
        end = start
        end_clock = str(event.get("end_time") or "").strip()
        if end_clock:
            if re.fullmatch(r"\d{3,4}", end_clock):
                end_clock = end_clock.zfill(4)
                end_clock = end_clock[:2] + ":" + end_clock[2:]
            end = datetime.fromisoformat(start.date().isoformat() + "T" + end_clock)
            if end.tzinfo is None:
                end = end.replace(tzinfo=PACIFIC)
            if end < start:
                end += timedelta(days=1)
        identity = [str(event.get("source") or ""), str(event.get("google_uid") or event.get("id") or event.get("title") or ""), start.isoformat(), str(event.get("end_time") or ""), str(event.get("location") or "")]
        return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest(), start, end
    except (ValueError, TypeError):
        return None


class CalendarCompletion:
    def __init__(self, store):
        self.store = store

    def due(self, context, now):
        if context.get("enabled") is False:
            return None
        candidates = []
        for event in context.get("events") or []:
            item = occurrence(event, context.get("date") or now.date().isoformat())
            if item is None:
                continue
            key, start, end = item
            if end > now or end < now - timedelta(hours=24) or start > now:
                continue
            old = self.store.get("calendar_completion", key)
            if old and (old.get("completed") or (old.get("askedAt") and now - datetime.fromisoformat(old["askedAt"]) < timedelta(hours=12))):
                continue
            candidates.append((end, {"key": key, "title": str(event.get("title") or "Untitled event")[:200], "date": start.date().isoformat()}))
        return max(candidates, key=lambda item: item[0])[1] if candidates else None

    def asked(self, question, now):
        old = self.store.get("calendar_completion", question["key"])
        # A late playback acknowledgement must never undo a completed answer.
        if old:
            self.store.patch("calendar_completion", question["key"], {"askedAt": now.isoformat()}, preserve_true=("completed",))
        else:
            self.store.put("calendar_completion", {**question, "askedAt": now.isoformat(), "completed": False}, question["key"], revision=0)

    def answer(self, question, value, now):
        old = self.store.get("calendar_completion", question["key"])
        payload = {**question, "askedAt": now.isoformat(), "completed": value == "yes", "answeredAt": now.isoformat()}
        if old:
            self.store.patch("calendar_completion", question["key"], payload, preserve_true=("completed",))
        else:
            self.store.put("calendar_completion", payload, question["key"], revision=0)
