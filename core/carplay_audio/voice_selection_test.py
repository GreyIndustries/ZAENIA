"""Briefing voice selection, fallback, and WAV processing without real models."""
from __future__ import annotations

import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import wave

from core.carplay_audio import carplay_audio


def sample_wav(rate=24000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b"\x10\x10\xf0\xef" * 2400)
    return buffer.getvalue()


class BriefingVoiceTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="zae-brief-voice-", dir=carplay_audio.PROJECT_ROOT)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.destination = self.root / "brief.wav"
        for target, value in [
            ("get_onedrive_folder", self.root),
            ("load_voice_config", {"voice_output": {"enabled": True}, "piper": {"enabled": False}}),
        ]:
            item = patch.object(carplay_audio, target, return_value=value)
            item.start()
            self.addCleanup(item.stop)

    def test_briefing_uses_configured_neural_voice_without_piper_settings(self):
        with patch("core.voice_output.neural_voice.synthesize_wav", return_value=sample_wav()) as voice, \
                patch.object(carplay_audio, "get_piper_settings", side_effect=AssertionError("Piper was requested")), \
                patch.object(carplay_audio.subprocess, "run") as process:
            result = carplay_audio.generate_piper_audio("Nothing on schedule.", self.destination)
        voice.assert_called_once_with("Nothing on schedule.")
        process.assert_not_called()
        self.assertEqual(result, self.destination)
        with wave.open(str(result), "rb") as output:
            self.assertEqual((output.getnchannels(), output.getsampwidth(), output.getframerate()), (1, 2, 24000))
            self.assertEqual(output.getnframes(), 4800 + int(24000 * .95))
        self.assertEqual(list(self.root.iterdir()), [self.destination])

    def test_piper_fallback_is_kept_when_neural_voice_is_unavailable(self):
        settings = {"model_path": "fallback.onnx", "config_path": "fallback.json", "length_scale": 1.1, "noise_scale": .667, "noise_w": .8}
        def render(command, **kwargs):
            Path(command[command.index("--output_file") + 1]).write_bytes(sample_wav(22050))
            return SimpleNamespace(returncode=0)
        with patch("core.voice_output.neural_voice.synthesize_wav", return_value=None), \
                patch.object(carplay_audio, "get_piper_settings", return_value=settings), \
                patch.object(carplay_audio.subprocess, "run", side_effect=render) as process:
            carplay_audio.generate_piper_audio("Fallback briefing.", self.destination)
        self.assertEqual(process.call_args.kwargs["input"], "Fallback briefing.")
        with wave.open(str(self.destination), "rb") as output:
            self.assertEqual(output.getframerate(), 22050)

    def test_disabled_voice_output_does_not_synthesize(self):
        with patch.object(carplay_audio, "load_voice_config", return_value={"voice_output": {"enabled": False}}), \
                patch("core.voice_output.neural_voice.synthesize_wav") as voice:
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                carplay_audio.generate_piper_audio("Briefing.", self.destination)
        voice.assert_not_called()
        self.assertFalse(self.destination.exists())

    def test_bad_generated_audio_keeps_previous_file_and_cleans_temporary_files(self):
        original = sample_wav()
        self.destination.write_bytes(original)
        with patch("core.voice_output.neural_voice.synthesize_wav", return_value=b"invalid-wave"):
            with self.assertRaises((wave.Error, EOFError)):
                carplay_audio.generate_piper_audio("Briefing.", self.destination)
        self.assertEqual(self.destination.read_bytes(), original)
        self.assertEqual(list(self.root.iterdir()), [self.destination])


if __name__ == "__main__":
    unittest.main()
