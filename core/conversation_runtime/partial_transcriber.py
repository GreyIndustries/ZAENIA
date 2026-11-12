from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vosk import KaldiRecognizer, Model


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL_PATH = (
    PROJECT_ROOT
    / "data"
    / "models"
    / "vosk-model-small-en-us-0.15"
)


class PartialTranscriber:
    """
    Streaming local transcription using Vosk.

    Partial results are informational only.

    Only finalized text should ever be forwarded to
    ZÆNIA's conversation or command systems.
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        model_path: Path | None = None,
    ) -> None:
        self.sample_rate = sample_rate

        self.model_path = (
            model_path
            if model_path is not None
            else DEFAULT_MODEL_PATH
        )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Vosk model not found: {self.model_path}"
            )

        self.model = Model(
            str(self.model_path)
        )

        self.recognizer = KaldiRecognizer(
            self.model,
            self.sample_rate,
        )

        self.last_partial = ""

    def reset(self) -> None:
        self.recognizer = KaldiRecognizer(
            self.model,
            self.sample_rate,
        )

        self.last_partial = ""

    def feed(
        self,
        pcm_bytes: bytes,
    ) -> dict[str, Any]:
        """
        Returns one of:

        {
            "type": "partial",
            "text": "I think we should"
        }

        {
            "type": "final",
            "text": "I think we should change it"
        }

        {
            "type": "none",
            "text": ""
        }
        """

        if not pcm_bytes:
            return {
                "type": "none",
                "text": "",
            }

        if self.recognizer.AcceptWaveform(
            pcm_bytes
        ):
            result = json.loads(
                self.recognizer.Result()
            )

            text = (
                result
                .get("text", "")
                .strip()
            )

            self.last_partial = ""

            if text:
                return {
                    "type": "final",
                    "text": text,
                }

            return {
                "type": "none",
                "text": "",
            }

        partial_result = json.loads(
            self.recognizer.PartialResult()
        )

        partial = (
            partial_result
            .get("partial", "")
            .strip()
        )

        if (
            partial
            and partial != self.last_partial
        ):
            self.last_partial = partial

            return {
                "type": "partial",
                "text": partial,
            }

        return {
            "type": "none",
            "text": "",
        }

    def finalize(self) -> str:
        """
        Force Vosk to return any remaining recognized speech.
        """

        result = json.loads(
            self.recognizer.FinalResult()
        )

        text = (
            result
            .get("text", "")
            .strip()
        )

        self.last_partial = ""

        return text