from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from core.behavior.behavior_engine import (
    get_behavior_guidance,
    log_behavior_event,
)
from core.conversation.conversation_state import (
    activate_conversation,
    background_conversation,
    get_conversation_summary,
    is_conversation_active,
    record_reply,
    record_user_speech,
)
from core.voice_output.speaker import speak

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RULES_PATH = (
    PROJECT_ROOT
    / "core"
    / "conversation"
    / "reply_rules.yaml"
)

REPLY_LOG_PATH = (
    PROJECT_ROOT
    / "data"
    / "conversation_reply_log.jsonl"
)


def load_reply_rules() -> dict[str, Any]:
    if not RULES_PATH.exists():
        raise FileNotFoundError(
            f"Missing reply rules: {RULES_PATH}"
        )

    with RULES_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        return yaml.safe_load(f) or {}


def log_reply_event(
    event_type: str,
    data: dict[str, Any],
) -> None:
    REPLY_LOG_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        **data,
    }

    with REPLY_LOG_PATH.open(
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


def detect_reply_situation(
    text: str,
    signals: dict[str, Any] | None = None,
) -> str:
    lowered = text.lower().strip()
    signals = signals or {}

    if "wrap_up" in signals:
        return "wrap_up"

    if "frustration" in signals:
        return "frustration"

    if "fatigue" in signals:
        return "fatigue"

    gratitude_terms = [
        "thank you",
        "thanks",
        "appreciate it",
        "appreciate that",
    ]

    if any(term in lowered for term in gratitude_terms):
        return "gratitude"

    confirmation_terms = [
        "got it",
        "okay",
        "alright",
        "that works",
        "sounds good",
        "perfect",
    ]

    if any(term in lowered for term in confirmation_terms):
        return "confirmation"

    uncertainty_terms = [
        "not sure",
        "i don't know",
        "i dont know",
        "maybe",
        "what do you think",
        "unsure",
    ]

    if any(term in lowered for term in uncertainty_terms):
        return "uncertainty"

    accomplishment_terms = [
        "it works",
        "fixed it",
        "finished",
        "got it working",
    ]

    if any(term in lowered for term in accomplishment_terms):
        return "accomplishment"

    planning_terms = [
        "i need to",
        "next i",
        "tomorrow",
        "later i",
        "plan",
        "need to figure out",
    ]

    if any(term in lowered for term in planning_terms):
        return "planning"

    return "normal"


def get_situation_rules(
    situation: str,
) -> dict[str, Any]:
    rules = load_reply_rules()

    return (
        rules
        .get("situations", {})
        .get(situation, {})
        or {}
    )


def situation_is_enabled(
    situation: str,
) -> bool:
    return bool(
        get_situation_rules(
            situation
        ).get(
            "enabled",
            False,
        )
    )


def situation_requires_active_conversation(
    situation: str,
) -> bool:
    return bool(
        get_situation_rules(
            situation
        ).get(
            "requires_active_conversation",
            True,
        )
    )


def get_reply_probability(
    situation: str,
) -> float:
    return float(
        get_situation_rules(
            situation
        ).get(
            "automatic_reply_probability",
            1.0,
        )
    )


def should_reply(
    situation: str,
    *,
    attention_called: bool = False,
) -> bool:
    """
    Directly addressing ZÆNIA overrides normal reply probability.

    If Zack explicitly calls ZÆNIA and the situation has a valid
    conversational response rule, she answers.

    Follow-up conversation still uses usefulness/probability rules.
    """
    if not situation_is_enabled(
        situation
    ):
        return False

    if attention_called:
        return True

    active = is_conversation_active()

    if (
        situation_requires_active_conversation(
            situation
        )
        and not active
    ):
        return False

    probability = get_reply_probability(
        situation
    )

    return random.random() <= probability


def build_contextual_reply(
    situation: str,
    text: str,
    signals: dict[str, Any] | None = None,
) -> str:
    signals = signals or {}

    guidance = get_behavior_guidance(
        text,
        is_error="frustration" in signals,
    )

    time_context = guidance.get(
        "time_context",
        "normal",
    )

    if situation == "gratitude":
        return random.choice(
            [
                "Of course, Sir.",
                "Anytime, Zack.",
                "You got it, Grey.",
            ]
        )

    if situation == "confirmation":
        return random.choice(
            [
                "Good.",
                "Understood.",
                "That works.",
            ]
        )

    if situation == "fatigue":
        if time_context in {
            "late_night",
            "early_morning",
        }:
            return random.choice(
                [
                    "I’ll keep the next part short.",
                    "I’ll cut the extra detail for now.",
                    "We can keep this simple.",
                ]
            )

        return random.choice(
            [
                "I’ll keep things concise.",
                "We can simplify what comes next.",
                "I’ll keep the next steps lighter.",
            ]
        )

    if situation == "frustration":
        return random.choice(
            [
                "I see what’s happening. I’ll keep the next fix direct.",
                "Understood. We’ll change one thing and test it.",
                "Got it. I won’t pile extra changes onto the problem.",
            ]
        )

    if situation == "uncertainty":
        return random.choice(
            [
                "Tell me which part feels uncertain and I’ll narrow it down.",
                "I can help sort through that.",
                "We can isolate the unclear part first.",
            ]
        )

    if situation == "accomplishment":
        return random.choice(
            [
                "Good. That part is working.",
                "Nice. That piece is in place.",
                "Good, that moved us forward.",
            ]
        )

    if situation == "planning":
        return random.choice(
            [
                "I can help organize the next move.",
                "Let’s sequence that before we start changing things.",
                "I can help turn that into the next practical steps.",
            ]
        )

    if situation == "wrap_up":
        return random.choice(
            [
                "Understood. I’ll stay in the background.",
                "Got it. I’ll leave the conversation here.",
                "Understood, Sir. Background tasks can continue.",
            ]
        )

    return ""


def handle_conversation_input(
    text: str,
    *,
    signals: dict[str, Any] | None = None,
    attention_called: bool = False,
    speak_reply: bool = True,
) -> dict[str, Any]:
    """
    Conversational response engine.

    This function does NOT authorize or execute commands.
    """
    signals = signals or {}

    record_user_speech(
        signals=list(signals.keys())
    )

    if attention_called:
        activate_conversation()

    situation = detect_reply_situation(
        text,
        signals,
    )

    if situation == "wrap_up":
        reply = build_contextual_reply(
            situation,
            text,
            signals,
        )

        background_conversation(
            reason="contextual_wrap_up"
        )

        log_behavior_event(
            "conversation_wrap_up",
            "Conversation returned to background.",
            {
                "situation": situation,
            },
        )

        if reply and speak_reply:
            speak(reply)

        if reply:
            record_reply()

        return {
            "replied": bool(reply),
            "reply": reply,
            "situation": situation,
            "backgrounded": True,
        }

    if not should_reply(
        situation,
        attention_called=attention_called,
    ):
        return {
            "replied": False,
            "reply": "",
            "situation": situation,
            "backgrounded": False,
        }

    reply = build_contextual_reply(
        situation,
        text,
        signals,
    )

    if not reply:
        return {
            "replied": False,
            "reply": "",
            "situation": situation,
            "backgrounded": False,
        }

    if speak_reply:
        speak(reply)

    record_reply()

    log_reply_event(
        "conversation_reply",
        {
            "situation": situation,
            "reply": reply,
            "attention_called": attention_called,
            "conversation": get_conversation_summary(),
        },
    )

    return {
        "replied": True,
        "reply": reply,
        "situation": situation,
        "backgrounded": False,
    }