from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STATE_PATH = (
    PROJECT_ROOT
    / "data"
    / "conversation_state.json"
)

LOCAL_TIMEZONE = ZoneInfo("America/Los_Angeles")

DEFAULT_ACTIVE_TIMEOUT_SECONDS = 180


def get_now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def default_state() -> dict[str, Any]:
    return {
        "mode": "background",
        "conversation_active": False,
        "waiting_for_follow_up": False,

        "conversation_started_at": None,
        "last_attention_at": None,
        "last_user_speech_at": None,
        "last_reply_at": None,

        "background_since": None,
        "background_reason": None,

        "current_topic": None,
        "current_task": None,

        "recent_signals": [],
    }


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        state = default_state()
        save_state(state)
        return state

    try:
        saved = json.loads(
            STATE_PATH.read_text(
                encoding="utf-8"
            )
        )
    except (json.JSONDecodeError, OSError):
        state = default_state()
        save_state(state)
        return state

    state = default_state()
    state.update(saved)

    return state


def save_state(
    state: dict[str, Any],
) -> None:
    STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATE_PATH.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def activate_conversation(
    *,
    topic: str | None = None,
    task: str | None = None,
) -> dict[str, Any]:
    state = load_state()
    now = get_now().isoformat(timespec="seconds")

    if not state.get("conversation_active"):
        state["conversation_started_at"] = now

    state["mode"] = "active"
    state["conversation_active"] = True
    state["waiting_for_follow_up"] = True

    state["last_attention_at"] = now
    state["last_user_speech_at"] = now

    state["background_since"] = None
    state["background_reason"] = None

    if topic:
        state["current_topic"] = topic

    if task:
        state["current_task"] = task

    save_state(state)
    return state


def record_user_speech(
    *,
    signals: list[str] | None = None,
) -> dict[str, Any]:
    state = load_state()

    state["last_user_speech_at"] = (
        get_now()
        .isoformat(timespec="seconds")
    )

    if signals is not None:
        state["recent_signals"] = list(
            dict.fromkeys(signals)
        )

    save_state(state)
    return state


def record_reply() -> dict[str, Any]:
    state = load_state()

    state["last_reply_at"] = (
        get_now()
        .isoformat(timespec="seconds")
    )

    if state.get("conversation_active"):
        state["waiting_for_follow_up"] = True

    save_state(state)
    return state


def set_waiting_for_follow_up(
    waiting: bool,
) -> dict[str, Any]:
    state = load_state()
    state["waiting_for_follow_up"] = waiting

    save_state(state)
    return state


def set_current_context(
    *,
    topic: str | None = None,
    task: str | None = None,
) -> dict[str, Any]:
    state = load_state()

    if topic is not None:
        state["current_topic"] = topic

    if task is not None:
        state["current_task"] = task

    save_state(state)
    return state


def background_conversation(
    reason: str = "context_complete",
) -> dict[str, Any]:
    state = load_state()

    state["mode"] = "background"
    state["conversation_active"] = False
    state["waiting_for_follow_up"] = False

    state["background_since"] = (
        get_now()
        .isoformat(timespec="seconds")
    )

    state["background_reason"] = reason

    state["current_topic"] = None
    state["current_task"] = None
    state["recent_signals"] = []

    save_state(state)
    return state


def parse_state_time(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=LOCAL_TIMEZONE
            )

        return parsed.astimezone(
            LOCAL_TIMEZONE
        )

    except ValueError:
        return None


def active_conversation_expired(
    timeout_seconds: int = DEFAULT_ACTIVE_TIMEOUT_SECONDS,
) -> bool:
    state = load_state()

    if not state.get("conversation_active"):
        return False

    last_user_speech = parse_state_time(
        state.get("last_user_speech_at")
    )

    if last_user_speech is None:
        return False

    expires_at = (
        last_user_speech
        + timedelta(
            seconds=timeout_seconds
        )
    )

    return get_now() >= expires_at


def refresh_conversation_state(
    timeout_seconds: int = DEFAULT_ACTIVE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """
    Quietly return to background after inactivity.

    This is only a fallback.

    Context-based wrap-up detection from the cognitive
    filter remains the preferred way to end a conversation.
    """
    if active_conversation_expired(
        timeout_seconds
    ):
        return background_conversation(
            reason="inactive_timeout"
        )

    return load_state()


def is_conversation_active() -> bool:
    state = refresh_conversation_state()

    return bool(
        state.get("conversation_active")
    )


def get_conversation_summary() -> dict[str, Any]:
    state = refresh_conversation_state()

    return {
        "mode": state.get("mode"),
        "conversation_active": state.get(
            "conversation_active"
        ),
        "waiting_for_follow_up": state.get(
            "waiting_for_follow_up"
        ),
        "current_topic": state.get(
            "current_topic"
        ),
        "current_task": state.get(
            "current_task"
        ),
        "recent_signals": state.get(
            "recent_signals",
            [],
        ),
        "last_attention_at": state.get(
            "last_attention_at"
        ),
        "last_user_speech_at": state.get(
            "last_user_speech_at"
        ),
        "last_reply_at": state.get(
            "last_reply_at"
        ),
        "background_reason": state.get(
            "background_reason"
        ),
    }