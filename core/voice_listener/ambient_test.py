"""Ambient awareness tests: no microphone, no model, no disk."""
from __future__ import annotations

import unittest
from unittest import mock

from core.voice_listener.ambient import AmbientContext, AmbientJudge, AmbientSettings, might_need_help


def judge_with(verdict, now, **settings):
    calls = []
    def classify(text, context, activity=None):
        calls.append(text)
        return verdict
    settings.setdefault("require_name", True)
    return AmbientJudge(AmbientSettings(**settings), classify=classify, clock=lambda: now[0]), calls


class AmbientTest(unittest.TestCase):
    def setUp(self):
        # Hermetic: a real game in front of the PC turns on game mode (name required).
        patcher = mock.patch("core.assistant_platform.game_mode.active", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_help_cues_are_self_talk_not_others_or_chatter(self):
        for text in ["where did I put my keys", "ugh why won't this build", "I can't remember the wifi password",
                     "I need to call the dentist tomorrow", "is it going to rain later"]:
            with self.subTest(text=text):
                self.assertTrue(might_need_help(text))
        for text in ["nice", "she said where did I put my keys", "the tv is loud tonight", "dinner was good", ""]:
            with self.subTest(text=text):
                self.assertFalse(might_need_help(text))

    def test_chatter_is_noted_without_asking_the_brain(self):
        now = [100.0]
        judge, calls = judge_with({"respond": True, "confidence": 1.0, "need": "x"}, now)
        self.assertEqual(judge.decide("dinner was good tonight", [])["action"], "note")
        self.assertEqual(calls, [])

    def test_brain_decides_and_offers_are_rate_limited(self):
        now = [100.0]
        judge, _ = judge_with({"respond": True, "confidence": 0.9, "need": "finding keys"}, now)
        self.assertEqual(judge.decide("where did I put my keys", [])["action"], "respond")
        # Cooldown: a second offer right away becomes a quiet note instead.
        decision = judge.decide("where did I put my wallet", [])
        self.assertEqual(decision["action"], "note")
        self.assertTrue(decision["need"])
        now[0] += 91
        self.assertEqual(judge.decide("where did I put my phone", [])["action"], "respond")

    def test_low_confidence_or_no_model_stays_quiet(self):
        now = [0.0]
        judge, _ = judge_with({"respond": True, "confidence": 0.5, "need": ""}, now)
        self.assertEqual(judge.decide("why won't this build", [])["action"], "note")
        judge, _ = judge_with(None, now)
        self.assertEqual(judge.decide("why won't this build", [])["action"], "note")

    def test_without_a_wake_word_the_brain_decides_what_is_for_zae(self):
        now = [0.0]
        judge, calls = judge_with({"respond": False, "confidence": 0.0, "to_zae": 0.95, "need": ""}, now, require_name=False)
        for _ in range(10):  # direct requests are never rate-limited
            self.assertEqual(judge.decide("what's on my calendar today", [])["action"], "direct")
        judge, _ = judge_with({"respond": False, "confidence": 0.1, "to_zae": 0.1, "need": ""}, now, require_name=False)
        self.assertEqual(judge.decide("what should I make for dinner babe", [])["action"], "note")
        judge, calls = judge_with({"respond": True, "confidence": 1, "to_zae": 1, "need": ""}, now, require_name=False)
        for text in ["thanks", "cool", "ok"]:
            with self.subTest(text=text):
                self.assertEqual(judge.decide(text, [])["action"], "note")
        self.assertEqual(calls, [])

    def test_with_no_limits_configured_the_brain_alone_decides_when_to_speak(self):
        now = [0.0]
        judge, calls = judge_with({"respond": True, "confidence": 0.9, "to_zae": 0.1, "need": "x"}, now,
                                  require_name=False, cooldown_seconds=0, max_per_window=0)
        for _ in range(20):
            self.assertEqual(judge.decide("ugh why won't this build", [])["action"], "respond")
        # Even "she said ..." reaches the brain instead of a fixed rule.
        judge.decide("she said what time is it", [])
        self.assertEqual(calls[-1], "she said what time is it")

    def test_a_plain_greeting_always_gets_an_answer_without_a_name(self):
        now = [0.0]
        judge, calls = judge_with({"respond": False, "confidence": 0.1, "to_zae": 0.1, "need": ""}, now, require_name=False)
        for text in ["hello", "Hello!", "hi", "hey how are you", "good morning", "are you there"]:
            with self.subTest(text=text):
                self.assertEqual(judge.decide(text, [])["action"], "direct")
        self.assertEqual(calls, [])

    def test_without_a_model_plain_requests_still_get_answered(self):
        now = [0.0]
        judge, _ = judge_with(None, now, require_name=False)
        self.assertEqual(judge.decide("what time is it", [])["action"], "direct")
        self.assertEqual(judge.decide("dinner was good tonight", [])["action"], "note")
        judge, _ = judge_with(None, now, require_name=True)
        self.assertEqual(judge.decide("what time is it", [])["action"], "note")

    def test_disabled_ignores_everything(self):
        judge = AmbientJudge(AmbientSettings(enabled=False), classify=lambda *a: {"respond": True, "confidence": 1, "need": ""})
        self.assertEqual(judge.decide("where did I put my keys", [])["action"], "ignore")

    def test_context_expires_and_offer_is_consumed_once(self):
        now = [1000.0]
        context = AmbientContext(settings=AmbientSettings(context_minutes=10), clock=lambda: now[0])
        context.observe("working on the inspection report")
        context.note_need("I need to call the dentist", "dentist call")
        context.offer_for = "where did I put my keys"
        first = context.describe()
        self.assertIn("AMBIENT OFFER", first)
        self.assertIn("inspection report", first)
        self.assertIn("dentist call", first)
        self.assertNotIn("AMBIENT OFFER", context.describe())
        now[0] += 601
        self.assertIsNone(context.describe())

    def test_settings_are_bounded(self):
        settings = AmbientSettings.from_config({"respond_threshold": 0.1, "cooldown_seconds": "x", "enabled": False})
        self.assertEqual(settings.respond_threshold, 0.5)
        self.assertEqual(settings.cooldown_seconds, 90.0)
        self.assertFalse(settings.enabled)


if __name__ == "__main__":
    unittest.main()
