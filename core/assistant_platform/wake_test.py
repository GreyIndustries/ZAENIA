import time
import unittest

from core.assistant_platform import wake


class WakeTest(unittest.TestCase):
    SITUATION = {"hour": 7, "minute": 40, "calmMinutes": 480, "next": {"title": "Physical Therapy", "when": "at 8:30", "hoursAway": 0.8},
                 "dueToday": 1, "overdue": 0, "kcalLeft": 2100, "news": 5, "security": 100, "finished": ["the backup"]}

    def test_written_line_uses_the_situation(self):
        reply = wake.compose("wake", 3, self.SITUATION)
        self.assertEqual((reply["focus"], reply["source"]), ("calendar", "written"))
        self.assertIn("Good morning, boss", reply["line"])
        self.assertIn("Physical Therapy is next at 8:30", reply["line"])
        self.assertIn("the backup", reply["line"])

    def test_focus_follows_what_matters_most(self):
        self.assertEqual(wake.focus_for("wake", {"overdue": 2, "next": {"hoursAway": 1}}), "tasks")
        self.assertEqual(wake.focus_for("wake", {"kcalLeft": 900, "hour": 13}), "fitness")
        self.assertEqual(wake.focus_for("wake", {"news": 3}), "news")
        self.assertEqual(wake.focus_for("sleep", {"overdue": 3}), "system")
        self.assertEqual(wake.focus_in("Affirmative. You have 300 calories remaining.", "wake", {"next": {"title": "PT", "hoursAway": 1}}), "fitness")

    def test_brain_line_is_used_when_quick_and_sensible(self):
        prompts = []
        reply = wake.compose("wake", 2, self.SITUATION, run=lambda p: prompts.append(p) or '"Never fully. Your PT session is at 8:30."')
        self.assertEqual((reply["line"], reply["source"]), ("Never fully. Your PT session is at 8:30.", "brain"))
        self.assertIn("Sleeping on the job?", prompts[0])
        self.assertIn("Never claim human feelings", prompts[0])
        self.assertIn("Next on the calendar: Physical Therapy at 8:30.", prompts[0])

    def test_slow_brain_falls_back_to_the_written_line(self):
        reply = wake.compose("wake", 1, self.SITUATION, run=lambda p: time.sleep(0.5) or "late", timeout=0.05)
        self.assertEqual(reply["source"], "written")
        self.assertTrue(reply["line"].startswith("Awake and ready."))

    def test_sleep_mentions_work_kept_running(self):
        self.assertNotIn("Finished while calm", wake.prompt("sleep", "I'm going to sleep", {"finished": ["the backup"]}))
        reply = wake.compose("sleep", 2, {"hour": 23, "running": ["the research on sleep"]})
        self.assertIn("Good night", reply["line"])
        self.assertIn("the research on sleep", reply["line"])
        with self.assertRaises(ValueError):
            wake.compose("nap", 1, {})


if __name__ == "__main__":
    unittest.main()
