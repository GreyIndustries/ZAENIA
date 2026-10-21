"""Read-only live answers. Missing/denied sources never fall through to guesses."""
from __future__ import annotations

from datetime import datetime, timedelta
import re
import threading
import time
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")
_CACHE = {"at": 0., "value": None}
_LOCK = threading.Lock()


def weather_snapshot():
    with _LOCK:
        if _CACHE["value"] is not None and time.monotonic()-_CACHE["at"] < 300:
            return _CACHE["value"]
    from core.weather.weather_client import get_weather_for_location
    from core.weather.weather_selector import select_weather_location
    value = get_weather_for_location(select_weather_location(), forecast_days=7)
    value["checkedAt"] = datetime.now(PACIFIC).isoformat()
    with _LOCK:
        _CACHE.update(at=time.monotonic(), value=value)
    return value


def topic_for(question):
    text = " ".join(question.casefold().split()).strip(" .!?")
    if re.search(r"\b(?:explain|define|meaning|code|implement|fiction|pretend|write a|what is weather|how does)\b", text):
        return None
    if not re.search(r'\b(?:set|change|mark|update|schedule|add)\b',text) and (re.search(r"\b(?:am i|will i be) (?:on duty|off duty|on leave|in (?:school|class))\b",text) or re.search(r"\b(?:my duty status|my work status)\b",text)):
        return 'calendar'
    if re.search(r"\b(?:weather|forecast|rain|raining|temperature|snow|sunny)\b", text) and re.search(r"\b(?:what|how|is|will|today|tomorrow|later|current|now|check|tell|show|going)\b", text):
        return "weather"
    if re.search(r"\b(?:calendar|agenda|appointments?|meetings?|schedule)\b", text) and re.search(r"\b(?:what|show|read|check|do i|am i|have i|today|tomorrow|this week|next week)\b", text) and not re.search(r"\b(?:add|create|schedule .+ at|delete|remove|move|reschedule)\b", text):
        return "calendar"
    if re.search(r"\b(?:my tasks|task list|to.?do list|todos|to.?dos)\b", text) and re.search(r"\b(?:what|show|read|list|check|pending|left|due)\b", text) and not re.search(r"\b(?:add|create|delete|remove|complete)\b", text):
        return "tasks"
    if re.search(r"\b(?:system status|system health|cpu usage|memory usage|ram usage|are you running|are you online)\b", text):
        return "system"
    return None


def resolve(question, authorize, *, now=None, loaders=None):
    topic = topic_for(question)
    if topic is None:
        return None
    moment = (now or datetime.now(PACIFIC)).astimezone(PACIFIC)
    operation = {"weather": "weather.read", "calendar": "calendar.read", "tasks": "tasks.read", "system": "status.read"}[topic]
    source = {"weather": "Open-Meteo via ZAE weather", "calendar": "ZAE calendar and connected calendar sources",
              "tasks": "ZAE saved task list", "system": "Local system telemetry"}[topic]
    metadata = {"source": source, "checkedAt": moment.isoformat(), "available": False}
    try:
        if authorize is None or authorize(operation) is False:
            raise PermissionError("Source is unavailable with current permissions.")
        supplied = loaders or {}
        if topic == "weather":
            data = supplied.get("weather", weather_snapshot)()
            metadata["checkedAt"] = data.get("checkedAt") or metadata["checkedAt"]
            forecast = data.get("forecast") or {}
            daily, current = forecast.get("daily") or {}, forecast.get("current") or {}
            from core.weather.weather_client import weather_code_text
            place = (data.get("location") or {}).get("display_label") or "your configured location"
            place = re.sub(r"^in\s+", "", place)
            tomorrow = bool(re.search(r"\btomorrow\b", question, re.I))
            target = (moment.date()+timedelta(days=int(tomorrow))).isoformat()
            if re.search(r"\b(?:next week|next month|yesterday|last week)\b", question, re.I):
                raise ValueError("That forecast range is not available here.")
            dates = daily.get("time") or []
            index = dates.index(target) if target in dates else None
            def day(key):
                values = daily.get(key) or []
                return values[index] if index is not None and index < len(values) else None
            if tomorrow:
                if index is None or day("temperature_2m_max") is None:
                    raise ValueError("Tomorrow's forecast is unavailable.")
                answer = f"Tomorrow in {place}: {weather_code_text(day('weather_code'))}, high {round(day('temperature_2m_max'))}°F, low {round(day('temperature_2m_min'))}°F."
            elif current.get("temperature_2m") is not None:
                answer = f"In {place}: {round(current['temperature_2m'])}°F, {weather_code_text(current.get('weather_code'))}."
                if day("temperature_2m_max") is not None and day("temperature_2m_min") is not None:
                    answer += f" Today's high is {round(day('temperature_2m_max'))}°F and low {round(day('temperature_2m_min'))}°F."
            else:
                raise ValueError("Current weather is unavailable.")
            if re.search(r"\brain|later|tomorrow\b", question, re.I):
                rain = day("precipitation_sum")
                answer += f" Forecast precipitation for {'tomorrow' if tomorrow else 'today'}: {rain} inches." if rain is not None else " A precipitation forecast isn't available."
                if not tomorrow and re.search(r"\blater|tonight\b", question, re.I):
                    answer += " This is a daily forecast; I don't have an hourly timing estimate."
        elif topic == "calendar":
            from core.api.ui_calendar import read_calendar
            start, days = moment.date(), 1
            lower = question.casefold()
            if "tomorrow" in lower: start += timedelta(days=1)
            if "this week" in lower: days = 7-start.weekday()
            if "next week" in lower: start += timedelta(days=7-start.weekday()); days = 7
            data = supplied.get("calendar", read_calendar)(start, days)
            events = data.get("events") or []
            rows = [f"{item['date']} {item.get('time') or 'all day'} — {item['title']}" for item in events[:12]]
            answer = "\n".join(rows) if rows else f"No saved events found for {start.isoformat()}" + (f" through {(start+timedelta(days=days-1)).isoformat()}." if days>1 else ".")
            statuses=data.get('dayStatus') or {}
            duty_rows=[f"{day}: {label}" for day,label in list(sorted(statuses.items()))[:7] if label]
            if duty_rows:answer='Duty status — '+'; '.join(duty_rows)+'.\n'+answer
            if len(events)>12: answer += f"\nPlus {len(events)-12} more; open Calendar for the full list."
            if data.get("notice"): answer += "\n" + str(data["notice"])[:300]
            metadata["sourceCacheSeconds"] = 300
        elif topic == "tasks":
            from core.api.ui_tasks import list_tasks
            tasks = supplied.get("tasks", list_tasks)()
            pending = [item for item in tasks if item.get("status") != "Completed" and not item.get("archived")]
            answer = "\n".join(f"{item['title']} — {item['status']}" + (f", due {item['deadline']}" if item.get('deadline') else "") for item in pending[:12]) if pending else "Your saved task list has no unfinished tasks."
            if len(pending)>12: answer += f"\nPlus {len(pending)-12} more; open Tasks for the full list."
        else:
            from core.api.status_feed import build_status
            data = supplied.get("system", lambda: build_status("authenticated"))()
            system = data.get("system") or {}
            metadata["checkedAt"] = system.get("checked_at") or metadata["checkedAt"]
            answer = f"System: {data.get('diagnostics') or 'status unavailable'}."
            if system.get("cpu") is not None: answer += f" CPU {system['cpu']}%."
            if system.get("memory") is not None: answer += f" Memory {system['memory']}%."
            issues = [item for item in data.get("modules", []) if item.get("phase") in {"pending", "error"}]
            if issues: answer += " Attention: " + ", ".join(str(item.get("label") or item.get("id")) for item in issues) + "."
        metadata["available"] = True
    except PermissionError:
        answer = f"I can't read {topic} data with the current permissions. I won't guess."
    except Exception:
        answer = f"I couldn't verify the requested {topic} information from its source right now. I won't guess."
    checked = datetime.fromisoformat(metadata["checkedAt"].replace("Z", "+00:00")).astimezone(PACIFIC)
    answer += f"\nSource: {source}; checked {checked.strftime('%b %d, %I:%M %p')} Pacific."
    return {"answer": answer, "route": "live_data", "route_reason": "Read-only source-backed answer",
            "route_confidence": 1., "evidence": [metadata], "freshness": metadata,
            "verification": {"applied": True, "available": metadata["available"]}, "execution_authorized": False}
