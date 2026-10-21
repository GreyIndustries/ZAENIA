"""Shared calendar clarification checks; no model, hardware, or stored data."""
from datetime import datetime
from zoneinfo import ZoneInfo
import unittest

from core.assistant_dialogue import ActionDialogue, normalize_spoken_clocks

NOW = datetime(2026, 10, 16, 12, tzinfo=ZoneInfo("America/Los_Angeles"))


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.ticks = [0.0]
        self.dialogue = ActionDialogue(clock=lambda: self.ticks[0])

    def prepare(self, message):
        return self.dialogue.prepare(message, now=NOW)

    def test_missing_time_is_filled(self):
        self.assertNotIn("proposal", self.prepare("Schedule dentist tomorrow"))
        result = self.prepare("at three thirty pm")
        self.assertEqual(result["proposal"]["parameters"], {"title": "dentist", "date": "2026-10-17", "time": "15:30", "recurrence": "none"})
        self.assertFalse(self.dialogue.has_draft())

    def test_missing_date_is_filled(self):
        self.assertNotIn("proposal", self.prepare("Schedule dentist at 3 pm"))
        self.assertEqual(self.prepare("tomorrow")["proposal"]["parameters"]["time"], "15:00")

    def test_two_temporal_turns_complete_only_after_both_fields(self):
        self.assertNotIn("proposal", self.prepare("Schedule dentist"))
        self.assertNotIn("proposal", self.prepare("tomorrow"))
        self.assertEqual(self.prepare("nine a m")["proposal"]["parameters"]["time"], "09:00")

    def test_both_fields_in_one_followup(self):
        self.prepare("Add dentist to my calendar")
        self.assertEqual(self.prepare("tomorrow at three pm")["proposal"]["kind"], "calendar.create")

    def test_spoken_clock_in_full_request(self):
        for text, expected in (("three pm", "15:00"), ("nine a m", "09:00"), ("twelve fifteen pm", "12:15"), ("one forty-five pm", "13:45")):
            with self.subTest(text=text):
                self.assertEqual(self.prepare(f"Schedule dentist tomorrow at {text}")["proposal"]["parameters"]["time"], expected)

    def test_no_meridian_is_not_guessed(self):
        self.prepare("Schedule dentist tomorrow")
        self.assertIsNone(self.prepare("three"))
        self.assertFalse(self.dialogue.has_draft())

    def test_expiry_cancellation_and_unrelated_turn_clear_drafts(self):
        for turn in ("cancel", "never mind", "Explain gravity"):
            self.prepare("Schedule dentist tomorrow")
            self.prepare(turn)
            self.assertFalse(self.dialogue.has_draft())
            self.assertIsNone(self.prepare("3 pm"))
        self.prepare("Schedule dentist tomorrow")
        self.ticks[0] = 301
        self.assertIsNone(self.prepare("3 pm"))

    def test_drafts_do_not_cross_instances(self):
        self.prepare("Schedule dentist tomorrow")
        self.assertIsNone(ActionDialogue().prepare("3 pm", now=NOW))

    def test_unsupported_details_do_not_become_partial_requests(self):
        for message in ("Schedule dentist for two hours tomorrow", "Schedule dentist with Alex tomorrow", "Schedule dentist every day", "Schedule dentist at the office tomorrow", "Don't schedule dentist tomorrow", "Schedule dentist tomorrow and delete my files"):
            with self.subTest(message=message):
                result = self.prepare(message)
                self.assertTrue(result is None or "proposal" not in result)
                self.assertFalse(self.dialogue.has_draft())
                self.assertIsNone(self.prepare("3 pm"))

    def test_followup_cannot_smuggle_constraints_or_commands(self):
        for reply in ("3 pm for two hours", "3 pm and delete files", "3 pm at the office", "3 pm; run anything"):
            self.prepare("Schedule dentist tomorrow")
            self.assertIsNone(self.prepare(reply))
            self.assertFalse(self.dialogue.has_draft())

    def test_memory_values_are_preserved(self):
        result = self.prepare("Remember my favorite quote is at three pm")
        self.assertEqual(result["proposal"]["parameters"]["value"], "at three pm")

    def test_normalizer_preserves_non_clock_words(self):
        self.assertEqual(normalize_spoken_clocks("three reports at noon"), "three reports at noon")
        self.assertEqual(normalize_spoken_clocks("at three twenty pm"), "at three twenty pm")


if __name__ == "__main__":
    unittest.main()
