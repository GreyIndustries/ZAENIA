from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.brain.grounded_answer import (
    answer_grounded_question,
)
from core.brain.local_llm import (
    chat_local,
)


@dataclass
class BrainRoute:
    """
    Describes how ZÆNIA decided to process one question.

    route:
        normal
        grounded_system

    The routing decision happens outside the language model.

    That prevents Qwen from deciding for itself that it does
    not need local evidence for a question about ZÆNIA's real
    system.
    """

    route: str
    reason: str
    confidence: float


SYSTEM_IDENTITY_TERMS = {
    "zaenia",
    "zænia",
    "zae",
    "your",
    "you",
    "we",
    "our",
}


SYSTEM_COMPONENT_TERMS = {
    "audio",
    "authentication",
    "brain",
    "calendar",
    "carplay",
    "command",
    "config",
    "configuration",
    "conversation",
    "elevenlabs",
    "file",
    "files",
    "folder",
    "folders",
    "listener",
    "memory",
    "microphone",
    "ollama",
    "piper",
    "provider",
    "qwen",
    "rule",
    "rules",
    "script",
    "speaker",
    "speech",
    "system",
    "tts",
    "voice",
    "vosk",
    "weather",
}


CURRENT_STATE_TERMS = {
    "active",
    "actually",
    "configured",
    "currently",
    "current",
    "disabled",
    "enabled",
    "installed",
    "running",
    "still",
    "using",
    "use",
    "uses",
    "provider",
    "where",
    "which",
    "what",
}


FILESYSTEM_TERMS = {
    "file",
    "files",
    "folder",
    "folders",
    "directory",
    "directories",
    "path",
    "paths",
    "project",
}


def normalize_words(
    text: str,
) -> set[str]:
    """
    Convert natural language into a small deterministic word
    set used only for brain routing.
    """

    cleaned = (
        text.lower()
        .replace("?", " ")
        .replace(".", " ")
        .replace(",", " ")
        .replace("!", " ")
        .replace(":", " ")
        .replace(";", " ")
        .replace("/", " ")
        .replace("\\", " ")
        .replace("-", " ")
    )

    return {
        word.strip()
        for word in cleaned.split()
        if word.strip()
    }


def mentions_zaenia_identity(
    words: set[str],
) -> bool:
    """
    Detect references to ZÆNIA herself.
    """

    return bool(
        words.intersection(
            SYSTEM_IDENTITY_TERMS
        )
    )


def mentions_system_component(
    words: set[str],
) -> bool:
    """
    Detect known ZÆNIA implementation concepts.
    """

    return bool(
        words.intersection(
            SYSTEM_COMPONENT_TERMS
        )
    )


def asks_about_current_state(
    words: set[str],
) -> bool:
    """
    Detect questions about current/configured/runtime state.
    """

    return bool(
        words.intersection(
            CURRENT_STATE_TERMS
        )
    )


def asks_about_filesystem(
    words: set[str],
) -> bool:
    """
    Detect questions concerning ZÆNIA's real local files.
    """

    return bool(
        words.intersection(
            FILESYSTEM_TERMS
        )
    )


def classify_question(
    question: str,
) -> BrainRoute:
    """
    Decide whether the question requires grounded local
    evidence.

    This decision is deterministic Python logic.

    Qwen is deliberately not given authority to bypass this
    boundary.
    """

    words = normalize_words(
        question
    )

    if not words:
        return BrainRoute(
            route="normal",
            reason=(
                "empty or non-specific input"
            ),
            confidence=0.0,
        )

    identity = (
        mentions_zaenia_identity(
            words
        )
    )

    component = (
        mentions_system_component(
            words
        )
    )

    current_state = (
        asks_about_current_state(
            words
        )
    )

    filesystem = (
        asks_about_filesystem(
            words
        )
    )

    if identity and component:
        return BrainRoute(
            route="grounded_system",
            reason=(
                "question refers to ZÆNIA and "
                "a local system component"
            ),
            confidence=0.98,
        )

    if component and current_state:
        return BrainRoute(
            route="grounded_system",
            reason=(
                "question asks about the current "
                "state of a known ZÆNIA component"
            ),
            confidence=0.95,
        )

    if filesystem and identity:
        return BrainRoute(
            route="grounded_system",
            reason=(
                "question asks about ZÆNIA's "
                "local filesystem"
            ),
            confidence=0.98,
        )

    return BrainRoute(
        route="normal",
        reason=(
            "question does not require verification "
            "against ZÆNIA's local system state"
        ),
        confidence=0.90,
    )


def answer_normal_question(
    question: str,
    *,
    recent_messages: list[dict[str, str]] | None = None,
    behavior_context: str | None = None,
    conversation_context: str | None = None,
) -> str:
    """
    Normal local reasoning through Qwen.

    This function performs no system command execution.
    """

    return chat_local(
        question,
        recent_messages=recent_messages,
        behavior_context=behavior_context,
        conversation_context=conversation_context,
    )


def answer_question(
    question: str,
    *,
    recent_messages: list[dict[str, str]] | None = None,
    behavior_context: str | None = None,
    conversation_context: str | None = None,
) -> dict[str, Any]:
    """
    Route one question through the correct local brain path.

    Grounded route:
        local evidence
        + hybrid retrieval
        + registry knowledge
        + evidence verification

    Normal route:
        recent memory
        + behavior context
        + conversation context
        + local Qwen

    Neither route has command-execution authority.
    """

    question = (
        question.strip()
    )

    if not question:
        return {
            "answer": "",
            "route": "normal",
            "route_reason": (
                "empty question"
            ),
            "route_confidence": 0.0,
            "evidence": [],
            "freshness": {},
            "verification": {},
            "execution_authorized": False,
        }

    route = classify_question(
        question
    )

    if route.route == "grounded_system":
        grounded = (
            answer_grounded_question(
                question,
                recent_messages=recent_messages,
                conversation_context=conversation_context,
            )
        )

        return {
            "answer": grounded.get(
                "answer",
                "",
            ),
            "draft_answer": grounded.get(
                "draft_answer",
                "",
            ),
            "route": (
                route.route
            ),
            "route_reason": (
                route.reason
            ),
            "route_confidence": (
                route.confidence
            ),
            "evidence": grounded.get(
                "evidence",
                [],
            ),
            "freshness": grounded.get(
                "freshness",
                {},
            ),
            "verification": grounded.get(
                "verification",
                {},
            ),
            "execution_authorized": False,
        }

    answer = answer_normal_question(
        question,
        recent_messages=(
            recent_messages
        ),
        behavior_context=(
            behavior_context
        ),
        conversation_context=(
            conversation_context
        ),
    )

    return {
        "answer": (
            answer.strip()
        ),
        "route": (
            route.route
        ),
        "route_reason": (
            route.reason
        ),
        "route_confidence": (
            route.confidence
        ),
        "evidence": [],
        "freshness": {},
        "verification": {},
        "execution_authorized": False,
    }
