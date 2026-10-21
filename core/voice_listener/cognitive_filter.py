from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from core.voice_listener.attention import find_attention_call, strip_attention

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "core"
    / "voice_listener"
    / "voice_listener_config.yaml"
)

CONTEXT_LOG_PATH = PROJECT_ROOT / "data" / "voice_context_log.jsonl"
CONTEXT_STATE_PATH = PROJECT_ROOT / "data" / "voice_context_state.json"

LOCAL_TIMEZONE = ZoneInfo("America/Los_Angeles")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing voice listener config: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_context_state() -> dict[str, Any]:
    default_state = {
        "conversation_active": False,
        "last_attention_time": None,
        "last_background_time": None,
        "signals": {},
    }

    if not CONTEXT_STATE_PATH.exists():
        return default_state

    try:
        return json.loads(
            CONTEXT_STATE_PATH.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return default_state


def save_context_state(state: dict[str, Any]) -> None:
    CONTEXT_STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    CONTEXT_STATE_PATH.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def log_derived_context(
    event_type: str,
    derived_data: dict[str, Any],
) -> None:
    """
    Save derived context only.
    Raw microphone transcripts are not stored here.
    """
    CONTEXT_LOG_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record = {
        "timestamp": get_now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "derived": derived_data,
    }

    with CONTEXT_LOG_PATH.open(
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


def get_attention_names() -> list[str]:
    config = load_config()

    names = (
        config
        .get("attention", {})
        .get("names", [])
        or []
    )

    return [
        normalize_text(str(name))
        for name in names
        if str(name).strip()
    ]


def contains_attention_call(text: str) -> bool:
    return attention_call(text) is not None


def attention_call(text: str):
    config = load_config().get("attention", {}) or {}
    return find_attention_call(text, config.get("names", []) or [], config.get("calls", []) or [])


def strip_attention_call(text: str) -> str:
    return strip_attention(text, attention_call(text))


def derive_behavior_signals(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)

    groups = {
        "fatigue": [
            "tired",
            "exhausted",
            "sleepy",
            "going to bed",
            "need sleep",
            "wrap this up",
            "done for tonight",
        ],
        "frustration": [
            "annoying",
            "frustrated",
            "keeps failing",
            "not working",
            "why does it keep",
        ],
        "urgency": [
            "hurry",
            "urgent",
            "right now",
            "asap",
            "need this now",
            "running late",
        ],
        "time_pressure": [
            "running late",
            "need to leave",
            "almost time",
            "don't have much time",
            "quick",
        ],
        "debugging": [
            "error",
            "failed",
            "broken",
            "fix",
            "not working",
            "issue",
            "problem",
        ],
        "wrap_up": [
            "going to bed",
            "done for tonight",
            "that's enough",
            "we're good",
            "leave this here",
            "go background",
            "sleep for now",
        ],
    }

    signals: dict[str, Any] = {}

    for group_name, markers in groups.items():
        score = sum(
            1
            for marker in markers
            if normalize_text(marker) in normalized
        )

        if score:
            signals[group_name] = {
                "active": True,
                "score": score,
            }

    return signals


def detect_background_intent(
    text: str,
    signals: dict[str, Any] | None = None,
) -> bool:
    normalized = normalize_text(text)
    # Fatigue or a mention of a bed/restaurant is not a request to end the
    # conversation. Only a directed, complete wrap-up statement backgrounds it.
    normalized = normalize_text(strip_attention_call(text))
    normalized = re.sub(r"^(?:(?:okay|ok|well|so|thanks|thank you)\s+)+", "", normalized)
    return bool(re.fullmatch(
        r"(?:(?:please|you can)\s+)?(?:go background|stand by|standby|stop responding|"
        r"go quiet|be quiet|stop|sleep for now|we are good|we're good|that's enough|"
        r"that is enough|i'm going to bed|i am going to bed|going to bed|"
        r"we can leave this here|leave this here|that's all for now|that is all for now|"
        r"done for tonight|that's it for now)(?:\s+(?:please|now|thanks))?",
        normalized,
    ))


def update_context_state(
    *,
    attention_called: bool = False,
    background_requested: bool = False,
    signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_context_state()
    now = get_now().isoformat(timespec="seconds")

    if attention_called:
        state["conversation_active"] = True
        state["last_attention_time"] = now

    if background_requested:
        state["conversation_active"] = False
        state["last_background_time"] = now

    if signals:
        stored_signals = state.get("signals", {})

        for name, value in signals.items():
            stored_signals[name] = {
                "last_seen": now,
                "score": value.get("score", 1),
            }

        state["signals"] = stored_signals

    save_context_state(state)
    return state


def should_learn_from_utterance(
    text: str,
    approved_voice: bool,
    signals: dict[str, Any],
) -> bool:
    if not approved_voice:
        return False

    normalized = normalize_text(text)

    if not normalized:
        return False

    ignored = {
        "yeah",
        "yes",
        "no",
        "okay",
        "ok",
        "uh",
        "um",
        "hey",
    }

    if normalized in ignored:
        return False

    return bool(signals)


def filter_utterance(
    text: str,
    *,
    approved_voice: bool = False,
) -> dict[str, Any]:
    """
    Cognitive gate.

    ignored:
        Do nothing.

    passive_context:
        Learn behavioral context only.
        Never execute a command.

    attention:
        ZÆNIA was explicitly addressed.
        Command may proceed to the rule engine.

    background:
        Stop conversational interaction while approved
        scheduled/background tasks continue.
    """
    normalized = normalize_text(text)

    if not normalized:
        return {
            "decision": "ignored",
            "authorized": False,
            "command_text": "",
            "signals": {},
        }

    if not approved_voice:
        return {
            "decision": "ignored",
            "authorized": False,
            "command_text": "",
            "signals": {},
            "reason": "unapproved_voice",
        }

    signals = derive_behavior_signals(normalized)
    attention_called = contains_attention_call(text)

    background_requested = detect_background_intent(
        normalized,
        signals,
    )

    state = update_context_state(
        attention_called=attention_called,
        background_requested=background_requested,
        signals=signals,
    )

    if background_requested:
        log_derived_context(
            "conversation_backgrounded",
            {
                "signals": list(signals.keys()),
                "conversation_active": False,
            },
        )

        return {
            "decision": "background",
            "authorized": False,
            "command_text": "",
            "signals": signals,
            "conversation_active": False,
        }

    if attention_called:
        command_text = strip_attention_call(text)

        log_derived_context(
            "attention_call",
            {
                "has_command": bool(command_text),
                "signals": list(signals.keys()),
                "conversation_active": True,
            },
        )

        return {
            "decision": "attention",
            "authorized": True,
            "command_text": command_text,
            "signals": signals,
            "conversation_active": True,
        }

    if should_learn_from_utterance(
        normalized,
        approved_voice,
        signals,
    ):
        log_derived_context(
            "passive_context",
            {
                "signals": list(signals.keys()),
                "conversation_active": state.get(
                    "conversation_active",
                    False,
                ),
            },
        )

        return {
            "decision": "passive_context",
            "authorized": False,
            "command_text": "",
            "signals": signals,
            "conversation_active": state.get(
                "conversation_active",
                False,
            ),
        }

    return {
        "decision": "ignored",
        "authorized": False,
        "command_text": "",
        "signals": signals,
        "conversation_active": state.get(
            "conversation_active",
            False,
        ),
    }
