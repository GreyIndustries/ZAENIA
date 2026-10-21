from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = PROJECT_ROOT / "core" / "behavior" / "behavior_profile.yaml"
LOG_PATH = PROJECT_ROOT / "data" / "behavior_log.jsonl"

LOCAL_TIMEZONE = ZoneInfo("America/Los_Angeles")


def load_behavior_profile() -> dict[str, Any]:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(f"Missing behavior profile: {PROFILE_PATH}")

    with PROFILE_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_behavior_profile(profile: dict[str, Any]) -> None:
    from core.foundation.local_entry import owner_execute
    from core.foundation.security.io import atomic_write
    def validate(p):
        if set(p) != {"profile"} or not isinstance(p["profile"],dict):
            raise ValueError("Invalid behavior profile.")
        current=load_behavior_profile().get("behavior_profile",{})
        draft=p["profile"].get("behavior_profile",{})
        for key in ("owner_name","assistant_name"):
            if draft.get(key) != current.get(key):
                raise PermissionError("Behavior learning cannot change identity.")
        return p
    def commit(p):
        validate(p)
        atomic_write(PROFILE_PATH,yaml.safe_dump(p["profile"],sort_keys=False,allow_unicode=True).encode("utf-8"))
    owner_execute("behavior.write",{"profile":profile},commit,validate)


def get_now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def log_behavior_event(
    event_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": get_now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "message": message,
        "metadata": metadata or {},
    }

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_recent_behavior_events(limit: int = 20) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []

    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    recent_lines = lines[-limit:]

    events: list[dict[str, Any]] = []

    for line in recent_lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return events


def infer_time_context(now: datetime | None = None) -> str:
    now = now or get_now()
    hour = now.hour

    if hour >= 22 or hour < 4:
        return "late_night"

    if 4 <= hour < 7:
        return "early_morning"

    if 7 <= hour < 12:
        return "morning"

    if 12 <= hour < 18:
        return "afternoon"

    return "evening"


def command_suggests_debugging(command_text: str) -> bool:
    lowered = command_text.lower()

    markers = [
        "error",
        "failed",
        "fix",
        "broken",
        "debug",
        "screenshot",
        "why",
        "not working",
        "repair",
    ]

    return any(marker in lowered for marker in markers)


def command_suggests_wrap_up(command_text: str) -> bool:
    lowered = command_text.lower()

    markers = [
        "bed",
        "sleep",
        "wrap up",
        "tired",
        "quick",
        "essentials",
        "tomorrow",
    ]

    return any(marker in lowered for marker in markers)


def infer_situation(
    command_text: str = "",
    *,
    is_error: bool = False,
    repeated_error: bool = False,
    is_carplay: bool = False,
    is_danger: bool = False,
    event_count: int = 0,
) -> str:
    """
    Decide the communication situation.
    This controls how ZÆNIA should talk.
    """
    if is_danger:
        return "danger"

    if repeated_error:
        return "repeated_error"

    if is_error or command_suggests_debugging(command_text):
        return "debugging"

    if command_suggests_wrap_up(command_text):
        return "wrap_up"

    if is_carplay:
        if event_count >= 3:
            return "carplay_heavy_calendar"
        return "carplay_briefing"

    time_context = infer_time_context()

    if time_context == "late_night":
        return "late_night"

    if time_context == "early_morning":
        return "early_morning"

    return "normal"


def get_tone_mode_for_situation(situation: str) -> str:
    mapping = {
        "danger": "danger",
        "repeated_error": "debugging",
        "debugging": "debugging",
        "wrap_up": "tired",
        "late_night": "tired",
        "early_morning": "normal",
        "carplay_briefing": "normal",
        "carplay_heavy_calendar": "planning",
        "normal": "normal",
    }

    return mapping.get(situation, "normal")


def get_tone_settings(situation: str) -> dict[str, Any]:
    profile = load_behavior_profile()
    tone_modes = profile.get("behavior_profile", {}).get("tone_modes", {}) or {}

    tone_mode = get_tone_mode_for_situation(situation)
    settings = tone_modes.get(tone_mode, {}) or {}

    return {
        "tone_mode": tone_mode,
        "style": settings.get("style", "calm, direct, useful"),
        "max_lines": settings.get("max_lines", 5),
    }


def get_behavior_guidance(
    command_text: str = "",
    *,
    is_error: bool = False,
    repeated_error: bool = False,
    is_carplay: bool = False,
    is_danger: bool = False,
    event_count: int = 0,
) -> dict[str, Any]:
    situation = infer_situation(
        command_text,
        is_error=is_error,
        repeated_error=repeated_error,
        is_carplay=is_carplay,
        is_danger=is_danger,
        event_count=event_count,
    )

    tone = get_tone_settings(situation)

    return {
        "situation": situation,
        "tone_mode": tone["tone_mode"],
        "style": tone["style"],
        "max_lines": tone["max_lines"],
        "time_context": infer_time_context(),
        "use_generic_closer": False,
        "use_random_motivation": False,
        "danger_alert_allowed": situation == "danger",
    }


def build_situational_line(
    situation: str,
    *,
    event_count: int = 0,
    first_event_title: str | None = None,
    is_off_duty: bool = False,
) -> str:
    """
    Return a line only when the situation calls for one.
    No random closers.
    """
    profile = load_behavior_profile()
    phrase_rules = profile.get("behavior_profile", {}).get("phrase_rules", {}) or {}

    if situation == "danger":
        return phrase_rules.get("danger_only_alert_phrase", "Stay alert.")

    if situation == "late_night":
        return "Keep this short, then shut it down for the night."

    if situation == "wrap_up":
        return "We only need the safest stopping point."

    if situation == "repeated_error":
        return "Use a full file replacement instead of chasing tiny patches."

    if situation == "debugging":
        return "Change one thing, test one thing."

    if situation == "carplay_heavy_calendar":
        if first_event_title:
            return f"First priority is {first_event_title}."
        return "Prioritize the first required event."

    if situation == "carplay_briefing":
        if event_count > 0 and first_event_title:
            return f"First up: {first_event_title}."
        if is_off_duty:
            return "Use the open time deliberately."

    return ""


def record_command(command: str) -> None:
    guidance = get_behavior_guidance(command)
    log_behavior_event(
        "command",
        command,
        {
            "situation": guidance["situation"],
            "tone_mode": guidance["tone_mode"],
            "time_context": guidance["time_context"],
        },
    )


def record_feedback(feedback: str) -> None:
    log_behavior_event("feedback", feedback)


def record_correction(correction: str) -> None:
    log_behavior_event("correction", correction)


def summarize_behavior_state(limit: int = 12) -> dict[str, Any]:
    events = read_recent_behavior_events(limit=limit)

    counts: dict[str, int] = {}

    for event in events:
        event_type = event.get("event_type", "unknown")
        counts[event_type] = counts.get(event_type, 0) + 1

    return {
        "recent_event_count": len(events),
        "event_type_counts": counts,
        "time_context": infer_time_context(),
        "recent_events": events,
    }