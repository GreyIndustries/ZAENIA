from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "core"
    / "conversation_runtime"
    / "runtime_config.yaml"
)


def load_runtime_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing runtime config: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        return yaml.safe_load(f) or {}


class TurnManager:
    """
    Determines when Zack has actually finished a conversational turn.

    VAD tells us when speech stops.

    TurnManager decides whether that silence means:
        - brief pause
        - thinking pause
        - completed turn
    """

    def __init__(self) -> None:
        config = load_runtime_config()

        timing = (
            config.get("turn_timing", {})
            or {}
        )

        behavior = (
            config.get("behavior", {})
            or {}
        )

        self.normal_end_pause_ms = int(
            timing.get(
                "normal_end_pause_ms",
                650,
            )
        )

        self.thinking_pause_ms = int(
            timing.get(
                "thinking_pause_ms",
                1000,
            )
        )

        self.max_utterance_seconds = float(
            timing.get(
                "max_utterance_seconds",
                30,
            )
        )

        self.wait_longer_after = {
            str(word).lower().strip()
            for word in behavior.get(
                "wait_longer_after",
                [],
            )
        }

        self.speech_active = False

        self.turn_started_at: float | None = None

        self.pending_finalize_at: float | None = None

        self.final_segments: list[str] = []

        self.current_partial = ""

    def reset(self) -> None:
        self.speech_active = False

        self.turn_started_at = None

        self.pending_finalize_at = None

        self.final_segments = []

        self.current_partial = ""

    def speech_started(self) -> None:
        now = time.monotonic()

        if self.turn_started_at is None:
            self.turn_started_at = now

        self.speech_active = True

        # Zack resumed speaking before we finalized.
        self.pending_finalize_at = None

    def update_partial(
        self,
        text: str,
    ) -> None:
        text = text.strip()

        if text:
            self.current_partial = text

    def add_final_segment(
        self,
        text: str,
    ) -> None:
        text = text.strip()

        if not text:
            return

        if (
            not self.final_segments
            or self.final_segments[-1] != text
        ):
            self.final_segments.append(
                text
            )

        self.current_partial = ""

    def get_current_text(self) -> str:
        parts = list(
            self.final_segments
        )

        if self.current_partial:
            parts.append(
                self.current_partial
            )

        return " ".join(
            part.strip()
            for part in parts
            if part.strip()
        ).strip()

    def _last_word(self) -> str:
        text = self.get_current_text()

        if not text:
            return ""

        cleaned = (
            text
            .lower()
            .replace(",", "")
            .replace(".", "")
            .replace("?", "")
            .replace("!", "")
        )

        words = cleaned.split()

        if not words:
            return ""

        return words[-1]

    def _looks_unfinished(self) -> bool:
        last_word = self._last_word()

        if not last_word:
            return False

        if last_word in self.wait_longer_after:
            return True

        unfinished_phrases = (
            "i think",
            "i mean",
            "what if",
            "maybe we",
            "the thing is",
            "it feels like",
            "i was thinking",
        )

        text = self.get_current_text().lower()

        for phrase in unfinished_phrases:
            if text.endswith(phrase):
                return True

        return False

    def speech_ended(self) -> None:
        self.speech_active = False

        if self._looks_unfinished():
            wait_ms = self.thinking_pause_ms

        else:
            wait_ms = self.normal_end_pause_ms

        self.pending_finalize_at = (
            time.monotonic()
            + (wait_ms / 1000.0)
        )

    def force_due_to_max_length(self) -> bool:
        if self.turn_started_at is None:
            return False

        elapsed = (
            time.monotonic()
            - self.turn_started_at
        )

        return (
            elapsed
            >= self.max_utterance_seconds
        )

    def should_finalize(self) -> bool:
        if self.speech_active:
            return False

        if self.force_due_to_max_length():
            return True

        if self.pending_finalize_at is None:
            return False

        return (
            time.monotonic()
            >= self.pending_finalize_at
        )

    def consume_turn(self) -> str:
        text = self.get_current_text()

        self.reset()

        return text