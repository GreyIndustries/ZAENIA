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
        self.verdicts = []
        self.stack = [patch.object(calm_state, "CALM_FILE", root / "calm.json"), patch.object(calm_state, "EVENT_FILE", root / "event.json"),
                      patch.object(calm_state, "_ask_talk", side_effect=lambda system, text: self.verdicts.pop(0) if self.verdicts else None)]
        for item in self.stack:
            item.start()

    def tearDown(self):
        for item in self.stack:
            item.stop()
        self.folder.cleanup()

    def test_while_calm_anything_said_to_zae_wakes_her_and_is_handed_to_the_app(self):
        calm_state.report(True, now=100)
        self.verdicts = [{"other_person": True}]
        self.assertTrue(calm_state.calm_turn("hang on, I'm on the phone with mom", now=105))   # not for ZAE: ignored
        self.assertIsNone(calm_state.take_event(now=105))
        self.verdicts = [{"other_person": False}]
        self.assertTrue(calm_state.calm_turn("alright, let's get back to it", now=106))
        self.assertEqual(calm_state.take_event(now=106)["kind"], "wake")
        self.assertTrue(calm_state.calm_turn("Zae, wake up sleepy, we have work to do", now=106))
        self.assertEqual(calm_state.take_event(now=107)["kind"], "wake")
        self.assertIsNone(calm_state.take_event(now=107))                              # handed over once

    def test_not_calm_passes_normal_speech_and_catches_sleep_phrases(self):
        calm_state.report(False, now=100)
        self.assertFalse(calm_state.calm_turn("wake up sleepy", now=101))               # already awake: normal turn
        self.assertFalse(calm_state.calm_turn("remind me to call mom at five", now=101))
        self.assertTrue(calm_state.calm_turn("I'm going to sleep", now=102))
        self.assertEqual(calm_state.take_event(now=103), {"kind": "sleep", "id": 2, "phrase": "i'm going to sleep"})
        self.verdicts = [{"rest": True}]
        self.assertTrue(calm_state.calm_turn("alright that's it for tonight, catch you tomorrow", now=104))
        self.assertEqual(calm_state.take_event(now=104)["kind"], "sleep")
        self.verdicts = [{"rest": False}]
        self.assertFalse(calm_state.calm_turn("how much sleep should I get before a race", now=105))
        self.assertFalse(calm_state.calm_turn("rest of the week looks busy, plan it?", now=106))  # no model verdict: not a sleep request

    def test_while_calm_his_voice_is_enough_when_talk_cannot_be_asked(self):
        self.assertEqual(calm_state.intent("good morning", True, ask=lambda s, t: None)["kind"], "wake")
        self.assertEqual(calm_state.intent("you there zae", True, ask=lambda s, t: {"other_person": True})["kind"], "wake")  # her name

    def test_requests_go_to_the_app_only_while_it_is_open_and_are_taken_once(self):
        self.stack.append(patch.object(calm_state, "HANDOFF_FILE", Path(self.folder.name) / "handoff.json"))
        self.stack[-1].start()
        self.assertFalse(calm_state.hand_to_app("log two eggs", now=100))                  # app never reported
        calm_state.report(False, now=100)
        self.assertTrue(calm_state.hand_to_app("log two eggs", now=105))
        self.assertTrue(calm_state.hand_to_app("and a coffee", now=106))
        self.assertEqual(calm_state.take_voice_turns(now=107), ["log two eggs", "and a coffee"])
        self.assertEqual(calm_state.take_voice_turns(now=107), [])
        self.assertFalse(calm_state.hand_to_app("log a walk", now=100 + calm_state.APP_ONLINE_SECONDS + 1))  # app closed
        calm_state.hand_to_app("old", now=105)
        self.assertEqual(calm_state.take_voice_turns(now=200), [])                           # stale requests are dropped

    def test_a_stale_calm_report_never_leaves_the_pc_voice_deaf(self):
        calm_state.report(True, now=100)
        self.assertFalse(calm_state.calm_turn("what's on today", now=100 + calm_state.FRESH_SECONDS + 1))

    def test_long_sentences_that_contain_the_words_do_not_match(self):
        self.assertIsNone(calm_state.match("I was going to sleep early but the game went late and then we talked for hours"))

    def test_phrase_lists_match_the_app(self):
        source = (Path(__file__).resolve().parents[2] / "desktop" / "src" / "core" / "calmPhrases.ts").read_text(encoding="utf-8")
        cue = re.search(r"export const SLEEP_CUE = /(.*)/i;", source).group(1)
        self.assertEqual(cue, calm_state.SLEEP_CUE.pattern)
        for name, table in (("WAKE_CALLS", calm_state.WAKE_CALLS), ("SLEEP_PHRASES", calm_state.SLEEP_PHRASES)):
            block = re.search(rf"export const {name} = \[(.*?)\] as const;", source, re.S).group(1)
            rows = [re.findall(r'"([^"]+)"', row) for row in re.findall(r"\[([^\]]*)\]", block)]
            self.assertEqual(rows, table)


if __name__ == "__main__":
    unittest.main()
