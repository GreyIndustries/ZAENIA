from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.behavior.behavior_engine import (
    load_behavior_profile,
    summarize_behavior_state,
)
from core.brain.local_llm import chat_local
from core.brain.conversation_style import user_led_answer
from core.brain.recent_memory import recent_lines
from core.conversation.conversation_state import (
    activate_conversation,
    background_conversation,
    get_conversation_summary,
    record_reply,
    record_user_speech,
)
from core.voice_output.speaker import speak

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MEMORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "conversation_memory.jsonl"
)

LOCAL_TIMEZONE = ZoneInfo("America/Los_Angeles")

MAX_RECENT_TURNS = 12


def get_now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def append_memory(
    role: str,
    content: str,
) -> None:
    MEMORY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record = {
        "timestamp": get_now().isoformat(timespec="seconds"),
        "role": role,
        "content": content,
    }

    with MEMORY_PATH.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


def read_recent_memory(
    max_turns: int = MAX_RECENT_TURNS,
) -> list[dict[str, str]]:
    recent = recent_lines(MEMORY_PATH, limit=max(1, min(200, max_turns)))

    messages: list[dict[str, str]] = []

    for line in recent:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in {
            "user",
            "assistant",
        }:
            continue

        if not content:
            continue

        messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    return messages


def build_behavior_context() -> str:
    profile = load_behavior_profile()
    behavior = (
        profile
        .get("behavior_profile", {})
        or {}
    )

    state = summarize_behavior_state(
        limit=12
    )

    preferences = (
        behavior
        .get("current_user_preferences", {})
        or {}
    )

    correction_memory = (
        behavior
        .get("correction_memory", {})
        or {}
    )

    context = {
        "time_context": state.get(
            "time_context"
        ),
        "recent_behavior_event_counts": state.get(
            "event_type_counts"
        ),
        "user_preferences": preferences,
        "rejected_phrases": correction_memory.get(
            "rejected_phrases",
            [],
        ),
        "preferred_behavior": correction_memory.get(
            "preferred_behavior",
            [],
        ),
    }

    return json.dumps(
        context,
        indent=2,
        ensure_ascii=False,
    )


def build_conversation_context() -> str:
    state = get_conversation_summary()

    context = {
        "mode": state.get("mode"),
        "conversation_active": state.get(
            "conversation_active"
        ),
        "current_topic": state.get(
            "current_topic"
        ),
        "current_task": state.get(
            "current_task"
        ),
        "recent_signals": state.get(
            "recent_signals"
        ),
        "waiting_for_follow_up": state.get(
            "waiting_for_follow_up"
        ),
    }

    return json.dumps(
        context,
        indent=2,
        ensure_ascii=False,
    )


def clean_spoken_response(
    text: str,
) -> str:
    """
    Keep local speech natural.

    Removes common local-model artifacts that should not
    be spoken aloud.
    """
    cleaned = text.strip()

    unwanted_prefixes = [
        "assistant:",
        "zaenia:",
        "zænia:",
    ]

    lowered = cleaned.lower()

    for prefix in unwanted_prefixes:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    return cleaned


def converse(
    user_text: str,
    *,
    speak_response: bool = True,
    attention_called: bool = False,
    memory_authorizer=None,
) -> dict[str, Any]:
    """
    Main natural conversation path.

    This function NEVER executes commands.

    Command execution remains in the separate attention-call
    + command-router + rule-engine path.
    """
    user_text = user_text.strip()

    if not user_text:
        return {
            "reply": "",
            "spoken": False,
        }

    if attention_called:
        activate_conversation()

    record_user_speech()

    # Typed fallback, PC voice and streaming chat must use the same context
    # and fresh-source routing instead of maintaining separate prompt stacks.
    from core.brain.brain_service import BrainService, owner_words
    result=BrainService(memory_authorizer=memory_authorizer).ask(owner_words(user_text))
    reply=clean_spoken_response(str(result.get('answer') or ''))

    record_reply()

    if speak_response:
        speak(reply)

    return {
        "reply": reply,
        "spoken": speak_response,
    }


def return_to_background(
    reason: str = "conversation_complete",
) -> None:
    background_conversation(
        reason=reason
    )


def clear_recent_memory() -> None:
    """
    Clear only the rolling conversational transcript.

    This does not erase behavior profile or learned preferences.
    """
    MEMORY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MEMORY_PATH.write_text(
        "",
        encoding="utf-8",
    )
