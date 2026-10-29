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

    def test_creating_tasks_and_reminders_is_left_to_their_own_handlers(self):
        for text in ("Add a task to inspect the car", "create an event for Friday", "remind me to stretch", "Please add a reminder at 5"):
            self.assertFalse(chat_actions.maybe(text), text)
        self.assertTrue(chat_actions.maybe("mark the inspect the car task done"))

    def test_classify_only_picks_known_actions(self):
        self.assertEqual(chat_actions.classify("log 8000 steps", lambda p: '{"action": "body.log", "args": {"steps": 8000}}'),
                         {"action": "body.log", "args": {"steps": 8000}})
        self.assertIsNone(chat_actions.classify("x", lambda p: '{"action": "files.delete_everything", "args": {}}'))
        self.assertIsNone(chat_actions.classify("x", lambda p: '{"action": "none"}'))
        self.assertIsNone(chat_actions.classify("x", lambda p: "no json"))

    def test_stated_nutrition_logs_without_lookup(self):
        self.assertEqual(chat_actions.stated_nutrition("I ate 2,100 cal, 150g protein, 30g fiber and 220 carbs today"),
                         {"calories": 2100, "protein": 150, "fiber": 30, "carbs": 220})
        self.assertEqual(chat_actions.stated_nutrition("12g saturated fat, 20g fat, sodium 300"), {"saturatedFat": 12, "fat": 20, "sodiumMg": 300})
        self.assertEqual(chat_actions.stated_nutrition("I ate a chicken burrito"), {})
        reply = self.run_action("food.log", {"name": "protein", "text": "I ate 2,100 cal, 150g protein, 30g fiber and 220 carbs today"})
        self.assertIn("2100 kcal", reply["reply"])
        food = PersonalTools(self.store).listing("food", day=date.today().isoformat())["items"][-1]
        self.assertEqual((food["title"], food["calories"], food["protein"], food["fiber"], food["carbs"]), ("Logged in chat", 2100, 150, 30, 220))
        reply = self.run_action("food.log", {"name": "shake", "text": "shake with 40g protein, 10g carbs and 5g fat"})
        self.assertIn("worked out from your macros", reply["reply"])

    def test_fitness_quick_log_only_runs_fitness_actions(self):
        from unittest import mock
        with mock.patch.object(chat_actions, "run", return_value={"reply": "Logged.", "tab": "fitness"}) as ran:
            self.assertEqual(chat_actions.fitness_quick_log("weighed 195.4", lambda p: '{"action": "body.log", "args": {"weightLb": 195.4}}')["reply"], "Logged.")
            self.assertEqual(ran.call_args[0][0]["args"]["text"], "weighed 195.4")
            with self.assertRaisesRegex(ValueError, "couldn't tell"):
                chat_actions.fitness_quick_log("translate hello", lambda p: '{"action": "translate", "args": {"text": "hello", "to": "French"}}')
            with self.assertRaisesRegex(ValueError, "Log sub-tab"):
                chat_actions.fitness_quick_log("ate a burrito", lambda p: '{"action": "food.log", "args": {"name": "burrito"}}')
            self.assertEqual(ran.call_count, 1)

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
