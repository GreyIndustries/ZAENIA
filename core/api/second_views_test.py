"""Backends for the 2nd/3rd tab designs: Status uptime, Arena test set, Workbench experiments."""
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


class UptimeTest(unittest.TestCase):
    def setUp(self):
        from core.api.uptime import Uptime
        self.dir = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".tmp" if (Path(__file__).resolve().parents[2] / ".tmp").exists() else None)
        self.addCleanup(self.dir.cleanup)
        self.now = datetime(2026, 10, 30, 12, 0)
        self.state = {"brain": True}
        self.up = Uptime(Path(self.dir.name) / "uptime.json", {"server": lambda: True, "brain": lambda: self.state["brain"]}, clock=lambda: self.now)

    def test_counts_changes_and_server_gaps(self):
        self.up.sample()
        self.now += timedelta(minutes=5); self.state["brain"] = False; self.up.sample()
        self.now += timedelta(minutes=5); self.state["brain"] = True; self.up.sample()
        self.now += timedelta(hours=1); self.up.sample()  # the server was off in between
        view = self.up.view()
        brain = next(r for r in view["rows"] if r["id"] == "brain")
        server = next(r for r in view["rows"] if r["id"] == "server")
        self.assertEqual(brain["percent"], 75.0)
        self.assertLess(server["percent"], 50)  # 4 good of 15 expected
        kinds = [e["kind"] for e in view["events"]]
        self.assertEqual(kinds, ["off", "back", "down"])
        self.assertEqual(len(view["days"]), 30)
        self.assertEqual(view["days"][-1], "2026-10-30")


class BenchTest(unittest.TestCase):
    def setUp(self):
        from core.assistant_platform.arena_bench import Bench
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        answers = {"good": "About 240 kcal, roughly 45 g protein.", "half": "Roughly 240 kcal.", "bad": "No idea."}
        self.bench = Bench(Path(self.dir.name) / "bench.json", ask=lambda model, question: {"answer": answers[model], "seconds": 1.5})

    def test_grading(self):
        from core.assistant_platform.arena_bench import grade
        self.assertEqual(grade("It is about 240 kcal and 45 g protein", "240 kcal, 45 g protein"), 1.0)
        self.assertEqual(grade("240 kcal", "240 kcal, 45 g protein"), 0.5)
        self.assertEqual(grade("unknown", "240 kcal"), 0.0)

    def test_run_scores_every_model(self):
        with self.assertRaises(ValueError):
            self.bench.start(["good"], wait=True)  # no questions yet
        self.bench.add("Kcal in 150 g chicken breast?", "240 kcal, 45 g protein")
        view = self.bench.start(["good", "half", "bad"], wait=True)
        self.assertEqual(view["run"]["totals"], {"good": 1.0, "half": 0.5, "bad": 0.0})
        self.assertIsNone(view["running"])
        qid = view["questions"][0]["id"]
        self.assertEqual(self.bench.remove(qid)["questions"], [])


class ExperimentRecordTest(unittest.TestCase):
    def test_experiment_validates(self):
        from core.assistant_platform.personal_tools import validate_record
        record = validate_record("experiments", {"title": "Basil under LEDs", "hypothesis": "6500 K grows taller", "groups": ["6500 K", "3000 K"],
                                                 "readings": [{"day": 3, "values": [1.2, 1.0], "note": "Sprouted"}]})
        self.assertEqual(record["groups"], ["6500 K", "3000 K"])
        with self.assertRaises(Exception):
            validate_record("experiments", {"title": "x", "groups": ["a", "b", "c", "d", "e"]})

    def test_routes(self):
        from core.api.ui_routes import operation_for
        self.assertEqual(operation_for("GET", "/api/status/uptime"), "status.read")
        self.assertEqual(operation_for("POST", "/api/arena/bench/run"), "chat.reply")


if __name__ == "__main__":
    unittest.main()
