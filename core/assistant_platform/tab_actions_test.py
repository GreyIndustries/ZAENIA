import tempfile
import unittest
from pathlib import Path

from core.assistant_platform import tab_actions
from core.assistant_platform.store import PlatformStore

PLAN = """Sir, here's your program.

* Monday (Chest and Triceps):
\t+ Barbell bench press (3 sets of 8-12 reps)
\t+ Tricep dips: 3 sets of 12-15 reps
* Tuesday (Rest day)

Cool-down: 5-10 minutes of stretching"""


class TabActionsTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(tab_actions.parse("add it to my fitness tab as a training plan"), "plans")
        self.assertEqual(tab_actions.parse("save that to my workbench"), "workbench")
        self.assertEqual(tab_actions.parse("put this in my notes"), "notes")
        self.assertEqual(tab_actions.parse("save it as a training plan"), "plans")
        self.assertEqual(tab_actions.parse("Add the plan to my Fitness & Health tab."), "plans")
        self.assertIsNone(tab_actions.parse("add milk to my shopping list"))
        self.assertIsNone(tab_actions.parse("what's in my fitness tab"))

    def test_steps_are_parsed(self):
        steps = tab_actions.plan_steps(PLAN)
        self.assertEqual([s["exercise"] for s in steps], ["Monday (Chest and Triceps)", "Barbell bench press", "Tricep dips", "Tuesday (Rest day)"])
        self.assertEqual(steps[1]["prescription"], "3 sets of 8-12 reps")
        self.assertEqual(steps[2]["prescription"], "3 sets of 12-15 reps")

    def test_save_makes_a_real_record(self):
        with tempfile.TemporaryDirectory() as folder:
            store = PlatformStore(Path(folder) / "p.sqlite3")
            messages = [{"role": "user", "content": "make me a program from https://www.tiktok.com/@a/video/1"},
                        {"role": "assistant", "content": PLAN},
                        {"role": "user", "content": "add it to my fitness tab"}]
            result = tab_actions.save("plans", messages, store=store, ask=lambda prompt: "Spiderman Physique Plan")
            self.assertEqual(result["tab"], "fitness")
            self.assertIn('Saved to Fitness & Health › Training plans as "Spiderman Physique Plan" with 4 steps', result["reply"])
            saved = store.get("fitness_plan", result["id"])
            self.assertEqual(saved["sourceUrl"], "https://www.tiktok.com/@a/video/1")
            self.assertEqual(len(saved["steps"]), 4)
            note = tab_actions.save("notes", messages, store=store, ask=lambda prompt: (_ for _ in ()).throw(RuntimeError()))
            self.assertEqual(note["tab"], "notes")
            with self.assertRaises(ValueError):
                tab_actions.save("plans", [{"role": "user", "content": "hi"}], store=store)



class LastReplyTest(unittest.TestCase):
    def test_skips_short_claims_after_the_plan(self):
        messages = [{"role": "user", "content": "plan from https://x.com/a"}, {"role": "assistant", "content": PLAN},
                    {"role": "user", "content": "add it"}, {"role": "assistant", "content": "Training plan added to your fitness tab: Insomniac."},
                    {"role": "user", "content": "I dont see it"}, {"role": "assistant", "content": "I added it, but it's not synced yet. Done now."}]
        answer, asked = tab_actions.last_reply(messages)
        self.assertEqual(answer, PLAN.strip())
        self.assertEqual(asked, "plan from https://x.com/a")


if __name__ == "__main__":
    unittest.main()
