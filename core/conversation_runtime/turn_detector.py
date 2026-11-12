from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from silero_vad import (
    VADIterator,
    load_silero_vad,
)


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


class TurnDetector:
    """
    Local speech start/end detector using Silero VAD.

    This class does NOT transcribe speech and does NOT
    authorize commands.

    Its job is only to determine:

        silence
        speech started
        speech continuing
        speech ended
    """

    def __init__(self) -> None:
        config = load_runtime_config()

        runtime = (
            config.get(
                "conversation_runtime",
                {},
            )
            or {}
        )

        vad_config = (
            config.get(
                "vad",
                {},
            )
            or {}
        )

        self.sample_rate = int(
            runtime.get(
                "sample_rate",
                16000,
            )
        )

        self.frame_samples = int(
            vad_config.get(
                "frame_samples",
                512,
            )
        )

        self.threshold = float(
            vad_config.get(
                "threshold",
                0.5,
            )
        )

        self.min_silence_ms = int(
            vad_config.get(
                "min_silence_duration_ms",
                650,
            )
        )

        self.speech_pad_ms = int(
            vad_config.get(
                "speech_pad_ms",
                120,
            )
        )

        self.model = load_silero_vad(
            onnx=True
        )

        self.iterator = VADIterator(
            self.model,
            threshold=self.threshold,
            sampling_rate=self.sample_rate,
            min_silence_duration_ms=self.min_silence_ms,
            speech_pad_ms=self.speech_pad_ms,
        )

        self.speech_active = False

        # Raw PCM may arrive in blocks larger than 512 samples.
        # We keep leftovers here until another full VAD frame exists.
        self._sample_buffer = np.array(
            [],
            dtype=np.int16,
        )

    def reset(self) -> None:
        self.iterator.reset_states()

        self.speech_active = False

        self._sample_buffer = np.array(
            [],
            dtype=np.int16,
        )

    def _pcm_to_float_tensor(
        self,
        samples: np.ndarray,
    ) -> torch.Tensor:
        audio = (
            samples
            .astype(np.float32)
            / 32768.0
        )

        return torch.from_numpy(
            audio
        )

    def _process_frame(
        self,
        frame: np.ndarray,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        tensor = self._pcm_to_float_tensor(
            frame
        )

        result = self.iterator(
            tensor,
            return_seconds=False,
        )

        if not result:
            return events

        if "start" in result:
            self.speech_active = True

            events.append(
                {
                    "type": "speech_start",
                    "sample": result["start"],
                }
            )

        if "end" in result:
            self.speech_active = False

            events.append(
                {
                    "type": "speech_end",
                    "sample": result["end"],
                }
            )

        return events

    def feed_pcm16(
        self,
        pcm_bytes: bytes,
    ) -> list[dict[str, Any]]:
        """
        Feed signed 16-bit mono PCM audio.

        The incoming block can be larger than Silero's
        preferred frame size. It will be divided internally.
        """

        if not pcm_bytes:
            return []

        new_samples = np.frombuffer(
            pcm_bytes,
            dtype=np.int16,
        )

        if self._sample_buffer.size:
            samples = np.concatenate(
                (
                    self._sample_buffer,
                    new_samples,
                )
            )
        else:
            samples = new_samples

        events: list[dict[str, Any]] = []

        offset = 0

        while (
            len(samples) - offset
            >= self.frame_samples
        ):
            frame = samples[
                offset:
                offset + self.frame_samples
            ]

            events.extend(
                self._process_frame(
                    frame
                )
            )

            offset += self.frame_samples

        self._sample_buffer = samples[
            offset:
        ].copy()

        return events

    def is_speaking(self) -> bool:
        return self.speech_active


def self_test() -> None:
    detector = TurnDetector()

    print(
        "ZÆNIA turn detector ready"
    )

    print(
        f"Sample rate: "
        f"{detector.sample_rate} Hz"
    )

    print(
        f"Frame size: "
        f"{detector.frame_samples} samples"
    )

    print(
        f"Silence threshold: "
        f"{detector.min_silence_ms} ms"
    )


if __name__ == "__main__":
    self_test()