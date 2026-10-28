import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from core.assistant_platform import training
from core.assistant_platform.store import PlatformStore

STEPS = [{"exercise": "*Insomniac Spiderman Physique Training Program", "prescription": "Updated", "done": False},
         {"exercise": "*Note", "prescription": "This program is based on a video game physique", "done": False},
         {"exercise": "*Day 1", "prescription": "Chest and Triceps (Gym)", "done": False},
         {"exercise": "Barbell Bench Press", "prescription": "3 sets of 8-12 reps", "done": False},
         {"exercise": "Tricep Dips", "prescription": "3 sets of 12-15 reps", "done": False},
         {"exercise": "Day 2: Shoulders (Home/Outdoor)", "prescription": "", "done": False},
         {"exercise": "Push-ups", "prescription": "3 sets of 10-12 reps", "done": False}]


class TrainingTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "program.json"
        self.tracker = training.Training(self.path)

    def tearDown(self):
        self.folder.cleanup()

    def test_plan_days_and_weekdays(self):
        days = training.plan_days(STEPS)
        self.assertEqual([d["label"] for d in days], ["Day 1 Chest and Triceps (Gym)", "Day 2 Shoulders (Home/Outdoor)"])
        self.assertEqual([e["exercise"] for e in days[0]["exercises"]], ["Barbell Bench Press", "Tricep Dips"])
        self.assertEqual(training.default_weekdays(days, [], []), {"Monday": days[0]["label"], "Tuesday": days[1]["label"]})
        self.assertEqual(training.default_weekdays(days, ["Tuesday"], ["Saturday"]), {"Tuesday": days[0]["label"], "Saturday": days[1]["label"]})

    def test_targets_need_inputs_then_compute(self):
        self.assertEqual(training.targets(self.tracker.load()["profile"])["missing"], ["sex", "height", "weight"])
        profile = self.tracker.set_profile({"age": 30, "sex": "male", "heightIn": 70, "weightLb": 195.8, "goalWeightLb": 167, "rateLbPerWeek": 1})
        found = training.targets(profile)
        self.assertEqual((found["bmr"], found["maintenance"], found["dailyDeficit"], found["eat"], found["burn"], found["protein"]),
                         (1854, 2550, 500, 2300, 250, 167))
        self.assertAlmostEqual(found["weeksToGoal"], 28.8)
        for bad in ({"age": 5}, {"sex": "x"}, {"activity": "lazy"}, {"gymDays": ["Funday"]}, {"reminders": {"workout": "6am"}}, {"nope": 1}):
            with self.assertRaises(ValueError):
                self.tracker.set_profile(bad)

    def test_daily_log_burn_and_muscles(self):
        today = date.today().isoformat()
        self.tracker.log_day(today, {"weightLb": 195, "steps": 8000, "cardio": [{"type": "run", "miles": 2, "minutes": 20}],
                                     "done": {"Barbell Bench Press": True}, "sets": [{"exercise": "Leg Curl", "reps": 10, "weightLb": 90}]})
        data = self.tracker.load()
        self.assertEqual(data["profile"]["weightLb"], 195)
        burn = training.burned(data["days"][today], 195, 70)
        self.assertEqual((burn["cardio"], burn["cardioMiles"]), (round(0.63 * 195 * 2), 2.0))
        self.assertGreater(burn["steps"], 150)
        muscles = training.muscle_sets(data["days"], today)
        self.assertEqual((muscles["Hamstrings"], muscles["Biceps"]), (1, 0))  # leg curls are hamstrings, not biceps
        with self.assertRaises(ValueError):
            self.tracker.log_day(today, {"steps": -1})

    def test_overview_calendar_with_a_saved_plan(self):
        store = PlatformStore(Path(self.folder.name) / "p.sqlite3")
        from core.assistant_platform.personal_tools import PersonalTools
        plan = PersonalTools(store).save("plans", {"title": "Spider plan", "steps": STEPS, "sessions": []})
        today = date.today()
        self.tracker.log_day(today.isoformat(), {"done": {"Barbell Bench Press": True}, "weightLb": 194})
        self.tracker.set_program(plan["id"], {training.WEEKDAYS[today.weekday()]: "Day 1 Chest and Triceps (Gym)"})
        info = training.overview(store, self.path)
        cell = next(c for c in info["calendar"] if c["date"] == today.isoformat())
        self.assertEqual((cell["workout"], cell["planned"], cell["done"], cell["weighed"]), ("Day 1 Chest and Triceps (Gym)", 2, 1, True))
        self.assertTrue(info["habits"]["workouts"][-1])
        view = training.day_view(today.isoformat(), store, self.path)
        self.assertEqual(view["workout"]["label"], "Day 1 Chest and Triceps (Gym)")

    def test_sources_suggest_targets(self):
        reader = lambda url: {"title": "Spidey", "kind": "TikTok video", "text": "He is 5ft 10 and weighs 167."}
        ask = lambda prompt: json.dumps({"heightIn": 70, "weightLb": 167, "bodyFat": None, "advice": ["Train every muscle group"]})
        source = self.tracker.add_source("https://www.tiktok.com/@a/video/1", reader=reader, ask=ask)
        self.assertEqual(source["suggested"], {"heightIn": 70.0, "weightLb": 167.0, "advice": ["Train every muscle group"]})
        self.tracker.remove_source("https://www.tiktok.com/@a/video/1")
        self.assertEqual(self.tracker.load()["sources"], [])


class SetupAndContextTest(unittest.TestCase):
    def test_setup_command(self):
        for text in ("set up my training program", "Setup my fitness", "update my fitness stats", "start my training"):
            self.assertTrue(training.setup_command(text), text)
        self.assertFalse(training.setup_command("set up my calendar"))

    def test_context_only_for_fitness_talk(self):
        with tempfile.TemporaryDirectory() as folder:
            store = PlatformStore(Path(folder) / "p.sqlite3")
            path = Path(folder) / "program.json"
            from core.assistant_platform.personal_tools import PersonalTools
            plan = PersonalTools(store).save("plans", {"title": "Spider plan", "steps": STEPS, "sessions": []})
            tracker = training.Training(path)
            tracker.set_program(plan["id"], {})
            tracker.set_profile({"age": 30, "sex": "male", "heightIn": 70, "weightLb": 195.8, "goalWeightLb": 167})
            self.assertIsNone(training.training_context("what's the weather", store, path))
            text = training.training_context("how many calories should I eat today?", store, path)
            self.assertIn("Daily targets: eat 2300 kcal, burn 250 kcal", text)
            self.assertIn("Program: Spider plan", text)
            self.assertIn("5'10\"", text)
            self.assertEqual(training.setup_missing(path), [])


class PushTest(unittest.TestCase):
    def test_subscribe_send_and_drop_gone_phones(self):
        from core.api import web_push
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        self.assertEqual(len(web_push.public_key(pem)), 87)
        with tempfile.TemporaryDirectory() as folder:
            subs = Path(folder) / "s.json"
            import base64
            public = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
            keys = {"p256dh": base64.urlsafe_b64encode(public).rstrip(b"=").decode(), "auth": base64.urlsafe_b64encode(b"a" * 16).rstrip(b"=").decode()}
            web_push.subscribe({"endpoint": "https://web.push.apple.com/a", "keys": keys}, path=subs, origin="https://zae.example.test")
            web_push.subscribe({"endpoint": "https://web.push.apple.com/b", "keys": keys}, path=subs, origin="https://zae.example.test")
            with self.assertRaises(ValueError):
                web_push.subscribe({"endpoint": "http://x"}, path=subs)
            sent = []

            class Gone(Exception):
                response = type("R", (), {"status_code": 410})()

            def push(subscription_info, data, **kwargs):
                if subscription_info["endpoint"].endswith("b"):
                    raise Gone()
                sent.append(json.loads(data))
            self.assertEqual(web_push.send("Reminder", "Stretch", push=push, path=subs, pem=pem), 1)
            self.assertEqual(sent[0]["body"], "Stretch")
            self.assertEqual([s["endpoint"] for s in web_push.subscriptions(subs)], ["https://web.push.apple.com/a"])

    def test_training_reminders_fire_once_in_their_window(self):
        from datetime import datetime
        from core.api import web_push
        sent = []
        reminders = web_push.TrainingReminders(clock=lambda: datetime(2026, 10, 26, 7, 5), sender=lambda title, body: sent.append(title))
        fake = {"profile": {"reminders": {"workout": "", "weighIn": "07:00", "food": "20:00"}}, "days": {}}
        with mock.patch("core.assistant_platform.training.Training.load", return_value=fake):
            self.assertEqual(reminders.tick(), ["weighIn"])
            self.assertEqual(reminders.tick(), [])
        self.assertEqual(sent, ["Weigh-in"])


class ActualWorkoutTest(unittest.TestCase):
    def test_parse_uses_stated_miles_and_replaces_plan_burn(self):
        reply = json.dumps({"activities": [
            {"name": "Deadlift", "type": "strength", "detail": "3 reps", "minutes": 10, "met": 6},
            {"name": "Two-mile run", "type": "run", "detail": "2 miles", "minutes": 18, "miles": 3, "met": 9},
            {"name": "", "type": "core"}]})
        items = training.parse_actual("deadlift, then a 2-mile run", lambda prompt: reply)
        self.assertEqual([i["name"] for i in items], ["Deadlift", "Two-mile run"])
        self.assertEqual(items[1]["miles"], 2.0)
        with tempfile.TemporaryDirectory() as folder:
            tracker = training.Training(Path(folder) / "program.json")
            today = date.today().isoformat()
            tracker.log_day(today, {"done": {"Bench": True, "Rows": True}})
            plan_burn = training.burned(tracker.load()["days"][today], 200, 66)
            entry = tracker.log_day(today, {"actual": items})
            burn = training.burned(entry, 200, 66)
            self.assertEqual(burn["actual"][1]["kcal"], round(0.63 * 200 * 2))
            self.assertEqual(burn["lifting"], sum(a["kcal"] for a in burn["actual"]))
            self.assertNotEqual(plan_burn["lifting"], burn["lifting"])
            self.assertIsNone(tracker.log_day(today, {"actual": None})["actual"])

    def test_values_are_clamped(self):
        items = training.clean_actual([{"name": "x" * 300, "type": "weird", "minutes": 9999, "met": 50}])
        self.assertEqual((len(items[0]["name"]), items[0]["type"], items[0]["minutes"], items[0]["met"]), (120, "other", 300.0, 14.0))
        with self.assertRaises(ValueError):
            training.clean_actual([])


if __name__ == "__main__":
    unittest.main()
