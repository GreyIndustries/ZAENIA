import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from core.assistant_platform import chat_actions, training as training_module
from core.assistant_platform.personal_tools import PersonalTools
from core.assistant_platform.store import PlatformStore
from core.assistant_platform.training_test import STEPS


class ChatActionsTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = PlatformStore(Path(self.folder.name) / "p.sqlite3")
        self.path = Path(self.folder.name) / "program.json"
        self.tracker = training_module.Training(self.path)
        real_day_view = training_module.day_view
        self.patches = [mock.patch.object(training_module, "training", lambda: self.tracker),
                        mock.patch.object(training_module, "day_view", lambda day, store: real_day_view(day, store, self.path))]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.folder.cleanup()

    def run_action(self, action, args, ask=None):
        return chat_actions.run({"action": action, "args": args}, store=self.store, ask=ask)

    def test_prefilter(self):
        for text in ("I ate a chicken burrito", "log 8000 steps", "move arc reactor to prototype", "mark squats done", "ran 2 miles"):
            self.assertTrue(chat_actions.maybe(text), text)
        for text in ("what is the weather today", "hello", "how many calories should I eat?"):
            self.assertFalse(chat_actions.maybe(text), text)

    def test_classify_only_picks_known_actions(self):
        self.assertEqual(chat_actions.classify("log 8000 steps", lambda p: '{"action": "body.log", "args": {"steps": 8000}}'),
                         {"action": "body.log", "args": {"steps": 8000}})
        self.assertIsNone(chat_actions.classify("x", lambda p: '{"action": "files.delete_everything", "args": {}}'))
        self.assertIsNone(chat_actions.classify("x", lambda p: '{"action": "none"}'))
        self.assertIsNone(chat_actions.classify("x", lambda p: "no json"))

    def test_fitness_logging(self):
        with self.assertRaisesRegex(ValueError, "sourced values"):
            self.run_action("food.log", {"name": "chicken burrito"}, ask=lambda p: '{"calories": 650, "protein": 35, "fiber": 6}')
        self.assertEqual(self.store.list("fitness_food"), [])
        reply = self.run_action("food.log", {"name": "chicken burrito", "calories": 650, "protein": 35, "fiber": 6})
        self.assertIn("650 kcal", reply["reply"])
        food = PersonalTools(self.store).listing("food", day=date.today().isoformat())["items"][0]
        self.assertEqual((food["title"], food["calories"]), ("chicken burrito", 650))
        self.run_action("body.log", {"weightLb": 194.6, "steps": 8000})
        self.run_action("cardio.log", {"type": "run", "miles": 2.5, "minutes": 25})
        entry = self.tracker.load()["days"][date.today().isoformat()]
        self.assertEqual((entry["weightLb"], entry["steps"], entry["cardio"][0]["miles"]), (194.6, 8000, 2.5))
        plan = PersonalTools(self.store).save("plans", {"title": "Spider", "steps": STEPS, "sessions": []})
        self.tracker.set_program(plan["id"], {training_module.WEEKDAYS[date.today().weekday()]: "Day 1 Chest and Triceps (Gym)"})
        done = self.run_action("workout.done", {"exercises": ["bench"]})
        self.assertIn("Barbell Bench Press", done["reply"]); self.assertIn("Tricep Dips", done["reply"])
        self.run_action("set.log", {"exercise": "dips", "sets": 3, "reps": 12})
        entry = self.tracker.load()["days"][date.today().isoformat()]
        self.assertEqual(len(entry["sets"]), 3)
        self.assertTrue(entry["done"]["Tricep Dips"])

    def test_projects_and_tasks(self):
        self.assertIn("Arc Reactor", self.run_action("project.create", {"title": "Arc Reactor", "subject": "Nuclear physics"})["reply"])
        moved = self.run_action("project.stage", {"project": "arc reactor", "stage": "Prototype"})
        self.assertEqual(moved["reply"], 'Moved "Arc Reactor" to Prototype.')
        self.assertEqual(self.store.list("workbench")[0]["status"], "Prototype")
        self.run_action("music.create", {"title": "Midnight Drive"})
        self.assertEqual(self.store.list("music")[0]["title"], "Midnight Drive")
        tasks = [{"id": "t1", "title": "Go to the gym", "status": "Pending"}]
        with mock.patch("core.api.ui_tasks.list_tasks", return_value=tasks), mock.patch("core.api.ui_tasks.update_task") as update:
            self.assertEqual(self.run_action("task.complete", {"task": "gym task"})["reply"], 'Marked "Go to the gym" done.')
            update.assert_called_once_with("t1", {"status": "Completed"})
            with self.assertRaises(ValueError):
                self.run_action("task.complete", {"task": "laundry"})


if __name__ == "__main__":
    unittest.main()
