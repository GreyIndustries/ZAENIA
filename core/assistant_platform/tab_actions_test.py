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



class NoteCommandTest(unittest.TestCase):
    def test_parse_and_save_notes_from_chat(self):
        from core.assistant_platform.notes import Notes
        self.assertEqual(tab_actions.parse_note("add this to my notes: buy creatine"), {"action": "new", "name": "", "text": "buy creatine"})
        self.assertEqual(tab_actions.parse_note("update my workout log note with this"), {"action": "update", "name": "workout log", "text": ""})
        self.assertEqual(tab_actions.parse_note("add this to my Arc Reactor note")["name"], "Arc Reactor")
        self.assertIsNone(tab_actions.parse_note("add milk to my shopping list"))
        with tempfile.TemporaryDirectory() as folder:
            store = PlatformStore(Path(folder) / "p.sqlite3")
            messages = [{"role": "user", "content": "plan?"}, {"role": "assistant", "content": PLAN}]
            made = tab_actions.save_note({"action": "new", "name": "", "text": ""}, messages, store=store, ask=lambda p: "Spider Plan")
            self.assertEqual(Notes(store).get(made["id"])["body"], PLAN.strip())
            gym = Notes(store).create("Gym log", "Mon: bench")
            done = tab_actions.save_note({"action": "update", "name": "gym", "text": "Tue: squat 225"}, messages, store=store)
            self.assertEqual(done["id"], gym["id"])
            self.assertTrue(Notes(store).get(gym["id"])["body"].endswith("Tue: squat 225"))
            fresh = tab_actions.save_note({"action": "update", "name": "reading list", "text": "Dune"}, messages, store=store)
            self.assertIn("started one", fresh["reply"])


class SpokenRequestTest(unittest.TestCase):
    def test_notes_said_naturally(self):
        self.assertEqual(tab_actions.parse_note("make a note that the mixer needs a new cable")["text"], "the mixer needs a new cable")
        self.assertEqual(tab_actions.parse_note("Zae, take a note: buy guitar strings")["text"], "buy guitar strings")
        self.assertEqual(tab_actions.parse_note("note to self call Jay back")["text"], "call Jay back")
        self.assertEqual(tab_actions.parse_note("write down the gate code is 4471")["text"], "the gate code is 4471")
        for not_a_note in ("note that", "notes are in the tab", "make a note", "what's in my notes"):
            self.assertIsNone(tab_actions.parse_note(not_a_note), not_a_note)

    def test_open_a_record_by_name(self):
        from core.assistant_platform.notes import Notes
        from core.assistant_platform.personal_tools import PersonalTools
        self.assertEqual(tab_actions.parse_open("open the song Midnight Drive"), {"kind": "music", "name": "Midnight Drive"})
        self.assertEqual(tab_actions.parse_open("open my research project on GPUs"), {"kind": "research", "name": "GPUs"})
        self.assertEqual(tab_actions.parse_open("pull up the Arc Reactor project"), {"kind": "project", "name": "Arc Reactor"})
        self.assertIsNone(tab_actions.parse_open("open fitness"))
        with tempfile.TemporaryDirectory() as folder:
            store = PlatformStore(Path(folder) / "p.sqlite3")
            PersonalTools(store).save("music", {"title": "Midnight Drive", "archived": False})
            PersonalTools(store).save("workbench", {"title": "Arc Reactor Mk II", "archived": False})
            Notes(store).create("Gym log", "Mon: bench")
            self.assertEqual(tab_actions.open_record({"kind": "music", "name": "midnight drive"}, store=store)["focus"], "Midnight Drive")
            found = tab_actions.open_record({"kind": "project", "name": "Arc Reactor"}, store=store)
            self.assertEqual((found["tab"], found["focus"]), ("workbench", "Arc Reactor Mk II"))
            self.assertEqual(tab_actions.open_record({"kind": "notes", "name": "gym"}, store=store)["tab"], "notes")
            with self.assertRaises(ValueError):
                tab_actions.open_record({"kind": "music", "name": "Nothing Like This"}, store=store)


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
