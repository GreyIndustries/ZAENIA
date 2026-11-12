import math
import struct
import unittest
from unittest import mock

from core.voice_security.app_mic import AppMicGate, SESSION_SECONDS


def tone(seconds: float, amplitude: float = 0.2) -> bytes:
    count = int(16000 * seconds)
    return b"".join(struct.pack("<h", int(amplitude * 32767 * math.sin(2 * math.pi * 220 * i / 16000))) for i in range(count))


class AppMicGateTest(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.audited = []
        self.answer = True
        self.gate = AppMicGate(verify=lambda pcm: self.answer, score=lambda pcm: 0.71 if self.answer else 0.32,
                               configured=lambda: True, audit=self.audited.append, clock=lambda: self.now)

    def test_recognised_voice_passes_and_other_voice_is_rejected_and_audited(self):
        self.assertEqual(self.gate.check(tone(2.5))["reason"], "recognised")
        self.answer = False
        result = self.gate.check(tone(2.5))
        self.assertEqual((result["accepted"], result["reason"]), (False, "not_recognised"))
        self.assertEqual(self.audited, ["app_mic_speaker_rejected"])

    def test_short_reply_only_counts_right_after_a_recognised_turn(self):
        self.assertEqual(self.gate.check(tone(0.6))["reason"], "too_short")
        self.gate.check(tone(2.5))
        self.now += 10
        self.assertTrue(self.gate.check(tone(0.6))["accepted"])
        self.now += SESSION_SECONDS + 1
        self.assertFalse(self.gate.check(tone(0.6))["accepted"])

    def test_silence_and_unconfigured_are_rejected(self):
        self.assertEqual(self.gate.check(b"\x00\x00" * 40000)["reason"], "too_short")
        unconfigured = AppMicGate(verify=lambda pcm: True, configured=lambda: False, audit=self.audited.append)
        self.assertEqual(unconfigured.check(tone(2.5))["reason"], "not_set_up")

    def test_errors_fail_closed(self):
        broken = AppMicGate(verify=lambda pcm: (_ for _ in ()).throw(RuntimeError("model")), configured=lambda: True,
                            audit=self.audited.append)
        self.assertEqual(broken.check(tone(2.5)), {"accepted": False, "reason": "check_failed"})

    def test_stats_suggest_training_when_recognition_is_poor(self):
        self.answer = False
        for _ in range(6):
            self.gate.check(tone(2.5))
        stats = self.gate.stats()
        self.assertEqual((stats["recognisedRate"], stats["needsTraining"], stats["averageScore"]), (0.0, True, 0.32))


class TranscribeGateTest(unittest.TestCase):
    def test_rejected_turn_is_never_transcribed(self):
        import base64
        from core.api import ui_voice
        gate = AppMicGate(verify=lambda pcm: False, configured=lambda: True, audit=lambda reason: None)
        with mock.patch("core.voice_security.app_mic.app_mic_gate", return_value=gate), \
                mock.patch.object(ui_voice, "app_mic_requires_voice", return_value=True), \
                mock.patch.object(ui_voice, "recognize", side_effect=AssertionError("must not transcribe")):
            result = ui_voice.transcribe(base64.b64encode(tone(2.5)).decode())
        self.assertEqual((result["text"], result["forZae"], result["rejected"]), ("", False, "not_recognised"))


if __name__ == "__main__":
    unittest.main()
