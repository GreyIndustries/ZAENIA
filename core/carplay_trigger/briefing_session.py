from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from core.briefing.drive_briefing import build_drive_briefing
from core.carplay_audio.carplay_audio import generate_piper_audio
from core.calendar_context.calendar_context import google_events_overlay
from core.google_calendar_sync.google_calendar_ics import GOOGLE_SYNC_SOURCE, get_google_events_between


ROOT = Path(__file__).resolve().parents[2]
PACIFIC = ZoneInfo("America/Los_Angeles")
_LOCK = threading.RLock()


def with_completion_context(raw, day):
    from core.calendar_context.calendar_context import build_calendar_context
    today = raw.get('calendar_context') or {}
    previous = build_calendar_context(day - timedelta(days=1))
    raw['completion_context'] = {**today, 'events':[
        *[{**event,'date':event.get('date') or previous.get('date')} for event in previous.get('events',[]) if previous.get('enabled') is not False],
        *[{**event,'date':event.get('date') or today.get('date') or day.isoformat()} for event in today.get('events',[])],
    ]}
    return raw


def build_fresh_briefing(day) -> tuple[dict, dict]:
    """Build the drive briefing with Google Calendar read live.

    The car can request this while Zack is away from the PC, so nothing here
    asks for the owner passkey: today's and tomorrow's Google events are read
    from the private iCal feed and used for this brief only. Nothing is
    written to the local calendar file (that protected write still needs the
    passkey at the PC). If Google cannot be reached, the brief uses the
    calendar already saved locally. Only the error type is reported, so the
    private iCal URL never leaves this machine.
    """
    try:
        events = get_google_events_between(start_date=day-timedelta(days=1), days=3)
    except Exception as error:
        print("CarPlay calendar refresh skipped:", type(error).__name__)
        sync = {"success": False, "reason": f"Google Calendar refresh skipped ({type(error).__name__}); using saved calendar."}
        return sync, with_completion_context(build_drive_briefing(include_traffic_force=True, calendar_date=day),day)
    dates = [(day + timedelta(days=offset)).isoformat() for offset in range(-1,2)]
    sync = {"success": True, "reason": f"Google Calendar read live with {len(events)} event(s)."}
    with google_events_overlay(events, dates, GOOGLE_SYNC_SOURCE):
        raw = with_completion_context(build_drive_briefing(include_traffic_force=True, calendar_date=day),day)
    return sync, raw


class SessionNotFound(LookupError):
    pass


class SessionConflict(ValueError):
    pass


def clean_speech(text: str) -> str:
    text = re.sub(r"[\u2012-\u2015]", ", ", str(text))
    text = re.sub(r"\s+-\s+", ", ", text)
    return re.sub(r"\s+", " ", text).strip()


def answer_value(text: str) -> str:
    words = set(re.findall(r"[a-z]+", text.lower()))
    yes = bool(words & {"yes", "yeah", "yep", "completed", "done", "finished"})
    no = bool(words & {"no", "nope", "nah", "not", "unfinished", "incomplete"})
    if no:
        return "no"
    return "yes" if yes and not no else "no" if no and not yes else "unknown"


def slots_for(now: datetime, state: dict, answer: str = "unknown") -> tuple[list[str], bool]:
    minute = now.hour * 60 + now.minute
    slots = []
    if not state.get("first"):
        slots.append("first")
    if 690 <= minute <= 780 and not state.get("lunch"):
        slots.append("lunch")
    if not state.get("evening") and (minute >= 1020 or (minute >= 990 and answer == "yes")):
        slots.append("evening")
    ask = 990 <= minute < 1020 and not state.get("evening") and answer == "unknown"
    return slots, ask


def condition_family(code) -> str | None:
    try:
        code = int(code)
    except (TypeError, ValueError):
        return None
    if code == 0:
        return "clear"
    if code in {1, 2, 3}:
        return "cloudy"
    if code in {45, 48}:
        return "fog"
    if code in {56, 57, 66, 67}:
        return "freezing rain"
    if code in {51, 53, 55, 61, 63, 65, 80, 81, 82}:
        return "rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {95, 96, 99}:
        return "thunderstorms"
    return None


def weather_snapshot(raw: dict, now: datetime) -> dict | None:
    result = raw.get("weather_result") or {}
    forecast = result.get("forecast") or {}
    current = forecast.get("current") or {}
    units = forecast.get("current_units") or {}
    family = condition_family(current.get("weather_code"))
    try:
        temperature = float(current["temperature_2m"])
    except (KeyError, TypeError, ValueError):
        return None
    hourly = forecast.get("hourly") or {}
    wet_soon = None
    codes = hourly.get("weather_code") or []
    for index, stamp in enumerate(hourly.get("time") or []):
        try:
            moment = datetime.fromisoformat(str(stamp))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=PACIFIC)
        except ValueError:
            continue
        if now <= moment <= now + timedelta(hours=2) and index < len(codes):
            group = condition_family(codes[index])
            if group in {"rain", "freezing rain", "snow", "thunderstorms"}:
                wet_soon = group
                break
    return {"family": family, "temperature": temperature,
            "unit": str(units.get("temperature_2m", "")), "wet_soon": wet_soon,
            "hourly_available": bool(codes and hourly.get("time")),
            "location": raw.get("weather_location"),
            "summary": raw.get("weather_summary", "")}


def weather_updates(current: dict | None, old: dict | None) -> list[str]:
    if current is None:
        return ["I could not check the latest weather."]
    if old is None or current["location"] != old.get("location"):
        return [current["summary"]]
    lines = []
    new_family, old_family = current["family"], old.get("family")
    if new_family and new_family != old_family:
        if old_family in {"rain", "freezing rain", "snow"} and new_family in {"clear", "cloudy"}:
            lines.append(f"The {old_family} has stopped, and conditions are now {new_family}.")
        else:
            lines.append(f"Conditions have changed to {new_family}.")
    if current["hourly_available"] and current["wet_soon"] != old.get("wet_soon"):
        if current["wet_soon"] and current["wet_soon"] != new_family:
            lines.append(f"{current['wet_soon'].capitalize()} is now forecast within the next two hours.")
        elif old.get("wet_soon") and not current["wet_soon"]:
            lines.append(f"{old['wet_soon'].capitalize()} is no longer forecast within the next two hours.")
    threshold = 6 if "F" in current["unit"] else 3
    if current["unit"] == old.get("unit") and abs(current["temperature"] - old["temperature"]) >= threshold:
        direction = "warmer" if current["temperature"] > old["temperature"] else "cooler"
        lines.append(f"It is noticeably {direction}, now {round(current['temperature'])} degrees.")
    return lines


def calendar_lines(context: dict, now: datetime, full: bool, announced: dict) -> tuple[list[str], dict]:
    lines, updates = [], {}
    if context.get("enabled") is False:
        return lines, updates
    for event in context.get("events") or []:
        title = str(event.get("title") or "Untitled event")
        if event.get("all_day"):
            if full:
                lines.append(f"On your calendar today, {title}, all day.")
            continue
        clock = str(event.get("time") or "").strip()
        try:
            if re.fullmatch(r"\d{3,4}", clock):
                clock = clock.zfill(4)
                clock = clock[:2] + ":" + clock[2:]
            event_date = str(event.get("date") or context.get("date") or now.date().isoformat())
            start = datetime.fromisoformat(event_date + "T" + clock)
            if start.tzinfo is None:
                start = start.replace(tzinfo=PACIFIC)
        except ValueError:
            continue  # Unknown times cannot safely be called upcoming.
        if start <= now or (not full and start > now + timedelta(hours=2)):
            continue
        identity = str(event.get("google_uid") or title) + "|" + start.isoformat() + "|" + str(event.get("location") or "")
        key = hashlib.sha256(identity.encode()).hexdigest()
        minutes = (start - now).total_seconds() / 60
        urgency = "soon" if minutes <= 15 else "hour" if minutes <= 60 else "upcoming"
        if not full and announced.get(key) == urgency:
            continue
        spoken_time = start.strftime("%H:%M")
        lines.append(f"On your calendar, {title} at {spoken_time}.")
        updates[key] = urgency
    if full and not lines:
        lines.append("Nothing on schedule.")
    return lines, updates


class BriefingSessions:
    """Persistent delivery state. Audio generation alone never consumes a slot."""

    def __init__(self, directory: Path | None = None, clock=None, handoff_loader=None, completion=None):
        from core.calendar_context.completion import CalendarCompletion
        from core.assistant_platform.store import PlatformStore
        self.completion = completion or CalendarCompletion(PlatformStore(Path(directory) / "completion.sqlite3" if directory is not None else None))
        self.directory = directory or ROOT / "data" / "carplay_sessions"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(PACIFIC))
        self.handoff_loader = handoff_loader
        self.database = self.directory / "sessions.sqlite3"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS days (day TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, payload TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=180)
        try:
            with connection:
                yield connection
        finally:
            # SQLite's transaction context commits/rolls back but does not close.
            connection.close()

    def get(self, session_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise SessionNotFound("Briefing session not found.")
        return json.loads(row[0])

    def require_recent(self, session: dict):
        age = self.clock() - datetime.fromisoformat(session["generated_at"])
        if age > timedelta(minutes=30) or age < timedelta(minutes=-1):
            raise SessionConflict("Briefing session expired. Request a fresh briefing.")

    def start(self, request_id: str | None = None, parent_id: str | None = None, answer: str = "", *, force_full: bool = False) -> dict:
        with _LOCK:
            return self._start(request_id, parent_id, answer, force_full=force_full)

    def _start(self, request_id, parent_id, answer, *, force_full=False):
        now = self.clock().astimezone(PACIFIC)
        parent = None
        if parent_id:
            parent = self.get(parent_id)
            self.require_recent(parent)
            if parent["briefing_type"] != "question":
                raise SessionConflict("This session is not waiting for an answer.")
            request_id = "answer:" + parent_id
        elif request_id and request_id.startswith("answer:"):
            raise SessionConflict("Reserved request ID.")
        with self.connect() as db:
            if request_id:
                existing = db.execute("SELECT payload FROM sessions WHERE request_id=?", (request_id,)).fetchone()
                if existing:
                    session = json.loads(existing[0])
                    self.require_recent(session)
                    return session["response"]
            row = db.execute("SELECT payload FROM days WHERE day=?", (now.date().isoformat(),)).fetchone()
        state = json.loads(row[0]) if row else {}
        value = answer_value(answer) if parent else "unknown"
        event_answer = bool(parent and parent.get("completionQuestion"))
        if event_answer and value != "unknown":
            self.completion.answer(parent["completionQuestion"], value, now)
        force_full = force_full or bool(parent and parent.get("forceFull"))
        slots, ask = slots_for(now, state, "unknown" if event_answer else value)
        sync, raw = {"success": True, "reason": "Departure confirmation."}, {}
        started = time.monotonic()
        if not parent:
            sync, raw = build_fresh_briefing(now.date())
            context = raw.get("calendar_context") or {}
            off = str(context.get("status", "")).lower() in {"off", "leave", "off_day"}
            ask = ask and now.weekday() < 5 and not off
        else:
            # Calendar and weather are refreshed again after dictation so the final brief is current.
            sync, raw = build_fresh_briefing(now.date())
            ask = False  # An unclear answer falls back, it never causes a prompt loop.
            if not event_answer and value != "yes" and now.hour * 60 + now.minute < 1020:
                slots = []
        kind = "full" if force_full else "question" if ask else "full" if slots else "short"
        snapshot, event_updates = {}, {}
        if kind == "question":
            text = "Grey, are you finished at work for today?"
            slots = []
        else:
            weather = weather_snapshot(raw, now)
            old = state.get("snapshot") or {}
            traffic_result = raw.get("traffic_result") or {}
            traffic_ok = bool(traffic_result) and traffic_result.get("success") is not False
            traffic = clean_speech(raw.get("traffic_summary") or "") if traffic_ok else None
            events, event_updates = calendar_lines(raw.get("calendar_context") or {}, now, kind == "full", state.get("events") or {})
            if kind == "full":
                opener = str((raw.get("personality") or {}).get("opener") or "")
                parts = [opener, *events, raw.get("weather_summary") or "Weather is unavailable."]
                if weather and weather["wet_soon"] and weather["wet_soon"] != weather["family"]:
                    parts.append(f"{weather['wet_soon'].capitalize()} is forecast within the next two hours.")
                parts.append(traffic or "I could not check the latest traffic.")
                try:
                    from core.research.agent import watch
                    parts.append(watch().briefing_line())
                except Exception:
                    pass
            else:
                weather_lines = weather_updates(weather, old.get("weather"))
                parts = list(weather_lines)
                if traffic is None:
                    parts.append("I could not check the latest traffic.")
                elif traffic != old.get("traffic"):
                    parts.append(traffic)
                parts.extend(events)
            text = clean_speech(" ".join(str(p) for p in parts if p)) or "No new updates."
            snapshot = {"weather": weather or old.get("weather"), "traffic": traffic if traffic is not None else old.get("traffic")}
            if kind == "short" and weather and old.get("weather"):
                # Carry the spoken temperature baseline forward until a change is announced.
                baseline = old["weather"]
                if weather["unit"] == baseline.get("unit") and not any("degrees" in line for line in weather_lines):
                    snapshot["weather"] = dict(weather, temperature=baseline["temperature"])
                if not weather["hourly_available"]:
                    snapshot["weather"]["wet_soon"] = baseline.get("wet_soon")
        completion_question = None
        if kind != "question" and not parent:
            completion_question = self.completion.due(raw.get('completion_context') or raw.get("calendar_context") or {}, now)
            if completion_question:
                text = clean_speech(text + " Has " + completion_question["title"] + " been completed?")
                kind = "question"
        if event_answer:
            acknowledgement = "Marked complete. " if value == "yes" else "I'll leave it unfinished. " if value == "no" else "I couldn't tell whether it was completed, so I left it unchanged. "
            text = acknowledgement + text
        if kind != 'question' and self.handoff_loader is not None:
            try: handoff=self.handoff_loader()
            except Exception: handoff=None # Optional task context cannot break a driving briefing.
            old_handoff=(state.get('snapshot') or {}).get('handoffRevision')
            if handoff and handoff.get('device')=='car':
                revision=handoff.get('revision')
                if revision != old_handoff:
                    text=clean_speech(text+' Your active task: '+str(handoff.get('summary',''))[:240]+'. Next: '+str(handoff.get('nextStep',''))[:180]+'. Work remains on your PC.')
                snapshot['handoffRevision']=revision
        session_id = str(uuid.uuid4())
        audio_path = self.directory / (session_id + ".wav")
        generate_piper_audio(clean_speech(text), audio_path)
        if not audio_path.is_file() or audio_path.stat().st_size == 0:
            raise RuntimeError("Piper did not create briefing audio.")
        response = {"success": True, "generated_at": now.isoformat(),
                    "duration_seconds": round(time.monotonic() - started, 2),
                    "calendar_sync": sync, "briefing_text": clean_speech(text), "audio_ready": True,
                    "audio_endpoint": "/api/carplay/audio?session_id=" + session_id,
                    "traffic_included": bool(raw.get("traffic_included", False)),
                    "traffic_window": str(raw["traffic_window"]) if raw.get("traffic_window") else None,
                    "session_id": session_id, "briefing_type": kind, "needs_answer": kind == "question",
                    "question_type": "calendar_completion" if completion_question else "departure" if kind == "question" else None}
        session = {"generated_at": now.isoformat(), "day": now.date().isoformat(), "briefing_type": kind,
                   "slots": slots, "snapshot": snapshot, "events": event_updates,
                   "audio_path": str(audio_path), "response": response, "played": False,
                   "completionQuestion": completion_question, "forceFull": force_full}
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (session_id, request_id, json.dumps(session)))
        return response

    def played(self, session_id: str) -> dict:
        with _LOCK, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise SessionNotFound("Briefing session not found.")
            session = json.loads(row[0])
            if session["played"]:
                return {"success": True, "already_recorded": True}
            self.require_recent(session)
            if session.get("completionQuestion"):
                self.completion.asked(session["completionQuestion"], self.clock())
            if session["briefing_type"] != "question" or session.get("completionQuestion"):
                row = db.execute("SELECT payload FROM days WHERE day=?", (session["day"],)).fetchone()
                state = json.loads(row[0]) if row else {}
                for slot in session["slots"]:
                    state[slot] = True
                # An older delayed acknowledgment must not overwrite newer delivered facts.
                if session["generated_at"] >= state.get("last_generated_at", ""):
                    state["snapshot"] = session["snapshot"]
                    state.setdefault("events", {}).update(session["events"])
                    state["last_generated_at"] = session["generated_at"]
                db.execute("INSERT OR REPLACE INTO days VALUES (?,?)", (session["day"], json.dumps(state)))
            session["played"] = True
            db.execute("UPDATE sessions SET payload=? WHERE id=?", (json.dumps(session), session_id))
        return {"success": True, "already_recorded": False}
