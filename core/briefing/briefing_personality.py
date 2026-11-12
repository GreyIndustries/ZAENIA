import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STYLE_PATH = PROJECT_ROOT / "core" / "briefing" / "briefing_style.yaml"
HISTORY_PATH = PROJECT_ROOT / "data" / "briefing_history.json"


def load_style_config() -> dict[str, Any]:
    if not STYLE_PATH.exists():
        raise FileNotFoundError(f"Briefing style file not found: {STYLE_PATH}")

    with STYLE_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_now() -> datetime:
    return datetime.now(ZoneInfo("America/Los_Angeles"))


def get_time_block(now: datetime | None = None) -> str:
    now = now or get_now()
    hour = now.hour

    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    return "night"


def load_history() -> dict[str, Any]:
    if not HISTORY_PATH.exists():
        return {}

    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_history(history: dict[str, Any]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def choose_rotating(
    options: list[str],
    key: str,
    avoid_last: bool = True,
) -> str:
    """
    Pick a line while trying not to repeat the last used option.
    """
    if not options:
        return ""

    history = load_history()
    last_used = history.get(key)

    choices = options[:]

    if avoid_last and len(choices) > 1 and last_used in choices:
        choices.remove(last_used)

    selected = random.choice(choices)

    history[key] = selected
    save_history(history)

    return selected


def build_personality_lines(
    calendar_context: dict[str, Any],
    traffic_included: bool,
) -> dict[str, str]:
    """
    Build opener, duty/event sentence, traffic sentence, inspiration, weekday line, and closer.
    """
    style = load_style_config()
    now = get_now()
    time_block = get_time_block(now)
    weekday = calendar_context.get("weekday") or now.strftime("%A")

    openers = style.get("openers", {}).get(time_block, [])
    opener = choose_rotating(openers, f"opener_{time_block}")

    event_phrasing = style.get("event_phrasing", {})
    status = calendar_context.get("status", "unknown")
    event_count = calendar_context.get("event_count", 0)
    first_event = calendar_context.get("first_event")

    if status == "on_duty":
        duty_sentence = choose_rotating(event_phrasing.get("on_duty", []), "duty_on")
    elif status == "off_duty":
        duty_sentence = choose_rotating(event_phrasing.get("off_duty", []), "duty_off")
    else:
        duty_sentence = f"Today is marked as {calendar_context.get('status_label', status)}."

    if event_count and first_event:
        event_templates = event_phrasing.get("events_found", [])
        event_template = choose_rotating(event_templates, "events_found")
        event_sentence = event_template.format(
            count=event_count,
            first_event=first_event.get("title", "your first event"),
        )
    else:
        event_sentence = choose_rotating(event_phrasing.get("no_events", []), "no_events")

    reminders = calendar_context.get("reminders", [])
    reminder_sentence = ""
    if reminders:
        reminder_sentence = f"Reminder: {reminders[0]}"

    traffic_options = style.get("traffic_phrasing", {})
    if traffic_included:
        traffic_sentence = choose_rotating(traffic_options.get("included", []), "traffic_included")
    else:
        traffic_sentence = choose_rotating(traffic_options.get("skipped", []), "traffic_skipped")

    weekday_options = style.get("weekday_lines", {}).get(weekday, [])
    weekday_sentence = choose_rotating(weekday_options, f"weekday_{weekday}")

    inspiration_options = style.get("inspiration_lines", [])
    inspiration_sentence = choose_rotating(inspiration_options, "inspiration")

    closers = style.get("closers", [])
    closer = choose_rotating(closers, "closer")

    return {
        "opener": opener,
        "duty_sentence": duty_sentence,
        "event_sentence": event_sentence,
        "reminder_sentence": reminder_sentence,
        "traffic_sentence": traffic_sentence,
        "weekday_sentence": weekday_sentence,
        "inspiration_sentence": inspiration_sentence,
        "closer": closer,
    }


def trim_words(text: str, max_words: int = 85) -> str:
    words = text.split()

    if len(words) <= max_words:
        return text

    return " ".join(words[:max_words]).rstrip(".,;") + "."