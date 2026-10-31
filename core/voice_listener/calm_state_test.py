import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.voice_listener import calm_state


class CalmStateTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.stack = [patch.object(calm_state, "CALM_FILE", root / "calm.json"), patch.object(calm_state, "EVENT_FILE", root / "event.json")]
        for item in self.stack:
            item.start()

    def tearDown(self):
        for item in self.stack:
            item.stop()
        self.folder.cleanup()

    def test_while_calm_only_a_wake_up_call_gets_through_and_is_handed_to_the_app(self):
        calm_state.report(True, now=100)
        self.assertTrue(calm_state.calm_turn("what's the weather tomorrow", now=105))   # ignored while calm
        self.assertIsNone(calm_state.take_event(now=105))
        self.assertTrue(calm_state.calm_turn("Zae, wake up sleepy, we have work to do", now=106))
        self.assertEqual(calm_state.take_event(now=107)["kind"], "wake")
        self.assertIsNone(calm_state.take_event(now=107))                              # handed over once

    def test_not_calm_passes_normal_speech_and_catches_sleep_phrases(self):
        calm_state.report(False, now=100)
        self.assertFalse(calm_state.calm_turn("wake up sleepy", now=101))               # already awake: normal turn
        self.assertFalse(calm_state.calm_turn("remind me to call mom at five", now=101))
        self.assertTrue(calm_state.calm_turn("I'm going to sleep", now=102))
        self.assertEqual(calm_state.take_event(now=103), {"kind": "sleep", "id": 2, "phrase": "i'm going to sleep"})

    def test_a_stale_calm_report_never_leaves_the_pc_voice_deaf(self):
        calm_state.report(True, now=100)
        self.assertFalse(calm_state.calm_turn("what's on today", now=100 + calm_state.FRESH_SECONDS + 1))

    def test_long_sentences_that_contain_the_words_do_not_match(self):
        self.assertIsNone(calm_state.match("I was going to sleep early but the game went late and then we talked for hours"))

    def test_phrase_lists_match_the_app(self):
        source = (Path(__file__).resolve().parents[2] / "desktop" / "src" / "core" / "calmPhrases.ts").read_text(encoding="utf-8")
        for name, table in (("WAKE_CALLS", calm_state.WAKE_CALLS), ("SLEEP_PHRASES", calm_state.SLEEP_PHRASES)):
            block = re.search(rf"export const {name} = \[(.*?)\] as const;", source, re.S).group(1)
            rows = [re.findall(r'"([^"]+)"', row) for row in re.findall(r"\[([^\]]*)\]", block)]
            self.assertEqual(rows, table)


if __name__ == "__main__":
    unittest.main()
