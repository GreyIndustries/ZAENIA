import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.brain.reply_shape import is_follow_up_for_more, reply_guide, wants_depth
from core.personal_memory import speech_style as style_module
from core.personal_memory.speech_style import SpeechStyle


class ReplyShapeTest(unittest.TestCase):
    def test_brief_by_default(self):
        for text in ("what time is my meeting", "is the server up?", "hey zae", "add milk to my list",
                     "whats the difference between ram and vram"):
            self.assertFalse(wants_depth(text), text)
            self.assertIn("brief", reply_guide(text))

    def test_depth_when_asked(self):
        for text in ("why?", "explain that", "tell me more", "go deeper", "walk me through the setup",
                     "how does it work", "ok why", "what do you mean?", "pros and cons of 64gb"):
            self.assertTrue(wants_depth(text), text)
            self.assertNotIn("REPLY SHAPE: brief", reply_guide(text, has_previous_answer=True))

    def test_bare_follow_up_expands_the_last_answer(self):
        self.assertTrue(is_follow_up_for_more("tell me more"))
        self.assertFalse(is_follow_up_for_more("explain how docker networking works"))
        self.assertIn("last answer", reply_guide("why?", has_previous_answer=True))
        self.assertNotIn("last answer", reply_guide("why?", has_previous_answer=False))

    def test_guide_is_the_last_system_message_before_the_question(self):
        from core.brain import local_llm
        with mock.patch("core.foundation.moral_code.vault.default_charter"), \
                mock.patch("core.foundation.moral_code.engine.guidance_for_generation", return_value="guidance"):
            messages = local_llm.build_messages("why?", recent_messages=[
                {"role": "user", "content": "is it safe"}, {"role": "assistant", "content": "Yes."}])
        self.assertEqual(messages[-1], {"role": "user", "content": "why?"})
        self.assertEqual(messages[-2]["role"], "system")
        self.assertIn("last answer", messages[-2]["content"])

    def test_brief_turns_carry_a_cue_for_the_model(self):
        from core.brain import local_llm
        with mock.patch("core.foundation.moral_code.vault.default_charter"), \
                mock.patch("core.foundation.moral_code.engine.guidance_for_generation", return_value="guidance"):
            brief = local_llm.build_messages("how far is the moon")
            deep = local_llm.build_messages("explain how tides work")
        # His words always go last, unchanged; the cue is a system line just before them.
        self.assertEqual(brief[-1], {"role": "user", "content": "how far is the moon"})
        self.assertEqual(brief[-2], {"role": "system", "content": "Reply to his next message in one or two short sentences."})
        self.assertEqual(deep[-1], {"role": "user", "content": "explain how tides work"})
        self.assertNotIn("one or two short sentences", deep[-2]["content"])


class SpeechStyleTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "speech_style.json"
        self.style = SpeechStyle(self.path)
        style_module._SPOKEN.clear()

    def tearDown(self):
        self.folder.cleanup()

    def test_no_hint_until_enough_turns(self):
        self.style.observe_text("hey whats up")
        self.assertIsNone(self.style.hint())

    def test_learns_short_casual_writing_and_his_words(self):
        for text in ("yeah lets do it", "u there", "ok lets go", "yeah sounds good", "lets fix the colors", "yeah do it"):
            self.style.observe_text(text)
        hint = self.style.hint()
        self.assertIn("short messages", hint)
        self.assertIn("casually", hint)
        self.assertIn("yeah", hint)
        self.assertIn("lets", hint)
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertNotIn("lets fix the colors", json.dumps(stored))  # no message text is kept

    def test_transcribed_speech_is_not_read_as_casual_typing(self):
        for text in ("open the calendar for tomorrow", "what is on my list today", "turn the lights down",
                     "read my latest email", "start the voice service"):
            style_module.mark_spoken(text)
            self.style.observe_text(text)
        data = self.style.load()
        self.assertEqual((data["lowercase"], data["spokenTurns"]), (0.0, 5))

    def test_voice_pace_follows_his_speaking_rate_within_limits(self):
        self.assertEqual(self.style.voice_speed(), 1.0)
        for _ in range(6):
            self.style.observe_speech(words=24, seconds=6.0)  # 240 words a minute: fast
        self.assertEqual(self.style.voice_speed(), 1.12)
        slow = SpeechStyle(Path(self.folder.name) / "slow.json")
        for _ in range(6):
            slow.observe_speech(words=10, seconds=6.0)  # 100 words a minute
        self.assertLess(slow.voice_speed(), 1.0)
        self.assertGreaterEqual(slow.voice_speed(), 0.92)


class VoiceStatusTest(unittest.TestCase):
    def test_reports_kokoro_not_piper(self):
        from core.api import status_feed
        with tempfile.TemporaryDirectory() as folder:
            model, voices = Path(folder) / "m.onnx", Path(folder) / "v.bin"
            model.write_bytes(b"x"); voices.write_bytes(b"x")
            config = {"active": True, "voice": "af_heart", "model_path": model, "voices_path": voices}
            with mock.patch("core.voice_output.neural_voice.settings", return_value=config), \
                    mock.patch("core.carplay_audio.carplay_audio.get_piper_settings"):
                result = status_feed._voice()
        self.assertEqual(result["phase"], "ready")
        self.assertIn("Kokoro voice ready (af_heart)", result["detail"])


if __name__ == "__main__":
    unittest.main()
