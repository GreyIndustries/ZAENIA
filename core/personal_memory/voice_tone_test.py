import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from core.personal_memory import voice_tone


def voice(pitch=120.0, loud=4000.0, seconds=3.0, wobble=1.0):
    """A voice-like clip: a buzzy tone whose pitch moves by `wobble` semitones, with short gaps between 'words'."""
    t = np.arange(int(16000 * seconds)) / 16000
    f = pitch * 2 ** (wobble * np.sin(2 * np.pi * 0.7 * t) / 12)
    phase = 2 * np.pi * np.cumsum(f) / 16000
    wave = sum(np.sin(k * phase) / k for k in (1, 2, 3))
    gate = (np.sin(2 * np.pi * 2.5 * t) > -0.6).astype(float)
    return (loud * wave * gate).clip(-32000, 32000).astype(np.int16).tobytes()


class VoiceToneTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.patches = [patch.object(voice_tone, "BASELINE_FILE", root / "base.json"), patch.object(voice_tone, "NOW_FILE", root / "now.json")]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.folder.cleanup()

    def test_measure_finds_pitch_loudness_and_pace(self):
        values = voice_tone.measure(voice(pitch=120), 8)
        self.assertAlmostEqual(values["pitch"], 120, delta=8)
        self.assertGreater(values["wps"], 2)
        self.assertGreater(voice_tone.measure(voice(loud=9000), 8)["db"], values["db"] + 5)
        self.assertIsNone(voice_tone.measure(b"\0\0" * 16000, 8))   # silence

    def test_nothing_is_judged_until_his_baseline_exists(self):
        for _ in range(voice_tone.MIN_SAMPLES - 1):
            self.assertIsNone(voice_tone.observe(voice(), 8, now=100))
        self.assertIsNone(voice_tone.hint(now=100))

    def test_rushed_turn_gives_a_brief_calm_hint_and_it_expires(self):
        for _ in range(voice_tone.MIN_SAMPLES):
            voice_tone.observe(voice(), 8, now=100)
        reading = voice_tone.observe(voice(pitch=150, loud=10000), 12, now=200)    # higher, louder, faster
        self.assertIn("louder", reading["cues"])
        self.assertEqual(reading["sense"], "rushed or under pressure")
        hint = voice_tone.hint(now=210)
        self.assertIn("be brief, calm and direct", hint)
        self.assertIn("never claim feelings yourself", hint)
        self.assertIsNone(voice_tone.hint(now=200 + voice_tone.FRESH_SECONDS + 1))

    def test_tired_turn_and_usual_turn(self):
        for _ in range(voice_tone.MIN_SAMPLES):
            voice_tone.observe(voice(), 8, now=100)
        self.assertEqual(voice_tone.observe(voice(loud=1500, wobble=0.3), 5, now=200)["sense"], "tired or low")
        self.assertIsNone(voice_tone.observe(voice(), 8, now=300))
        self.assertIsNone(voice_tone.hint(now=301))

    def test_only_numbers_are_kept(self):
        voice_tone.observe(voice(), 8, now=100)
        saved = (Path(self.folder.name) / "base.json").read_text()
        self.assertEqual(set(__import__("json").loads(saved)), {"db", "pitch", "spread", "wps", "samples"})


if __name__ == "__main__":
    unittest.main()
