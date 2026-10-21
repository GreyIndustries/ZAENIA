"""Kokoro voice wrapper tests: a fake engine, no model download or audio device."""
from __future__ import annotations

import io
from pathlib import Path
import unittest
from unittest.mock import patch
import wave

import numpy as np

from core.voice_output import neural_voice


def config(**overrides):
    base = {"active": True, "model_path": Path("missing.onnx"), "voices_path": Path("missing.bin"),
            "voice": "af_heart", "speed": 1.0, "lang": "en-us"}
    base.update(overrides)
    return base


class FakeEngine:
    def __init__(self):
        self.calls = []

    def get_voice_style(self, name):
        return np.full(4, {"af_heart": 1.0, "af_bella": 3.0}[name])

    def create(self, text, voice, speed, lang):
        self.calls.append(voice)
        return np.array([0.0, 0.5, -0.5, 2.0], dtype=np.float32), 24000


class NeuralVoiceTest(unittest.TestCase):
    def test_missing_files_or_piper_provider_fall_back(self):
        with patch.object(neural_voice, "settings", return_value=config()):
            self.assertIsNone(neural_voice.synthesize_wav("hello"))
        with patch.object(neural_voice, "settings", return_value=config(active=False)):
            self.assertIsNone(neural_voice.synthesize_wav("hello"))

    def test_engine_output_becomes_a_clipped_16_bit_wav(self):
        engine = FakeEngine()
        with patch.object(neural_voice, "settings", return_value=config()), \
                patch.object(neural_voice, "_engine", return_value=engine):
            audio = neural_voice.synthesize_wav("Good evening, Sir.")
        with wave.open(io.BytesIO(audio), "rb") as clip:
            self.assertEqual((clip.getnchannels(), clip.getsampwidth(), clip.getframerate(), clip.getnframes()), (1, 2, 24000, 4))
            frames = np.frombuffer(clip.readframes(4), dtype="<i2")
        self.assertEqual(frames[-1], 32767)
        self.assertEqual(engine.calls, ["af_heart"])

    def test_voice_blends_are_weighted(self):
        style = neural_voice._style(FakeEngine(), "af_heart:0.5,af_bella:0.5")
        self.assertTrue(np.allclose(style, 2.0))

    def test_engine_errors_fall_back(self):
        class Broken(FakeEngine):
            def create(self, *args, **kwargs):
                raise RuntimeError("boom")
        with patch.object(neural_voice, "settings", return_value=config()), \
                patch.object(neural_voice, "_engine", return_value=Broken()):
            self.assertIsNone(neural_voice.synthesize_wav("hello"))


if __name__ == "__main__":
    unittest.main()
