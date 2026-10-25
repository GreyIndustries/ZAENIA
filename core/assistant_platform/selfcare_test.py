import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from core.assistant_platform import protocols as protocol_module, reminders as reminder_module, selfcare
from core.assistant_platform.protocols import Protocols, run
from core.assistant_platform.reminders import Reminders, parse_request


class ReminderTest(unittest.TestCase):
    NOW = datetime(2026, 10, 25, 14, 0).astimezone()

    def test_parse_requests(self):
        when, what = parse_request("remind me in 20 minutes to check the oven", self.NOW)
        self.assertEqual((when - self.NOW, what), (timedelta(minutes=20), "check the oven"))
        when, what = parse_request("Zae, remind me at 5pm tomorrow to call mum", self.NOW)
        self.assertEqual((when.hour, when.day, what), (17, 26, "call mum"))
        when, _ = parse_request("remind me at 9 to stretch", self.NOW)  # 9:00 already passed today
        self.assertEqual((when.day, when.hour), (26, 9))
        when, _ = parse_request("remind me tonight to lock up", self.NOW)
        self.assertEqual(when.hour, 20)
        self.assertIsNone(parse_request("what should I do tonight", self.NOW))

    def test_fire_once_and_repeat(self):
        now = [datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)]
        with tempfile.TemporaryDirectory() as folder:
            items = Reminders(Path(folder) / "r.json", clock=lambda: now[0])
            items.add("once", now[0] + timedelta(minutes=5))
            items.add("daily", now[0] + timedelta(minutes=5), repeat="daily")
            self.assertEqual(items.due(), [])
            now[0] += timedelta(minutes=6)
            self.assertEqual(sorted(r["text"] for r in items.due()), ["daily", "once"])
            self.assertEqual([r["text"] for r in items.list()], ["daily"])
            self.assertEqual(items.due(), [])
            now[0] += timedelta(days=1)
            self.assertEqual([r["text"] for r in items.due()], ["daily"])


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.book = Protocols(Path(self.folder.name) / "p.json")

    def tearDown(self):
        self.folder.cleanup()

    def test_save_match_and_run(self):
        self.book.save({"name": "Goodnight", "phrases": ["Goodnight", "good night ZAE"],
                        "steps": [{"kind": "open", "value": "tasks"}, {"kind": "remind", "value": "7am tomorrow|gym"},
                                  {"kind": "ask", "value": "tomorrow?"}, {"kind": "say", "value": "Good night, sir."}]})
        found = self.book.match("Hey Zae, goodnight!")
        self.assertEqual(found["name"], "Goodnight")
        self.assertIsNone(self.book.match("goodnight moon is a book"))
        calls = []
        result = run(found, ask=lambda q: "Clear tomorrow.", set_reminder=lambda when, text: calls.append((when, text)) or "Reminder set.",
                     headlines=lambda: [], coach=lambda on: None, stop_watch=lambda: None)
        self.assertEqual(result, {"reply": "Reminder set. Clear tomorrow. Good night, sir.", "open": ["tasks"]})
        self.assertEqual(calls, [("7am tomorrow", "gym")])

    def test_steps_are_limited_to_safe_kinds(self):
        for steps in ([{"kind": "shell", "value": "del *"}], [{"kind": "open", "value": "C:/"}], [{"kind": "watch", "value": "on"}]):
            with self.assertRaises(ValueError):
                self.book.save({"name": "x", "phrases": ["x"], "steps": steps})

    def test_phrases_are_unique(self):
        self.book.save({"name": "a", "phrases": ["game time"], "steps": [{"kind": "say", "value": "hi"}]})
        with self.assertRaises(ValueError):
            self.book.save({"name": "b", "phrases": ["game time"], "steps": [{"kind": "say", "value": "hi"}]})

    def test_a_failed_step_is_reported_not_fatal(self):
        result = run({"steps": [{"kind": "coach", "value": "on"}, {"kind": "say", "value": "Done."}]}, ask=str, set_reminder=lambda a, b: "",
                     headlines=list, coach=lambda on: (_ for _ in ()).throw(PermissionError("not allowed")), stop_watch=lambda: None)
        self.assertIn("Couldn't do the coach step", result["reply"])


class BackupTest(unittest.TestCase):
    def test_backup_skips_models_and_keeps_fourteen(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "data"
            (data / "personal_memory").mkdir(parents=True)
            (data / "personal_memory" / "profile.json").write_text("{}")
            (data / "models").mkdir()
            (data / "models" / "big.onnx").write_bytes(b"x" * 10)
            (data / "voices").mkdir()
            (data / "voices" / "v.txt").write_text("skip")
            dest = root / "out"
            with mock.patch.object(selfcare, "LAST_FILE", data / "backups" / "last.json"):
                for index in range(16):
                    (dest).mkdir(exist_ok=True)
                    (dest / f"ZAENIA-data-2026010{index:02d}-000000.zip").write_bytes(b"old")
                record = selfcare.backup_now(dest, data)
            names = zipfile.ZipFile(record["path"]).namelist()
            self.assertEqual(names, ["data/personal_memory/profile.json"])
            self.assertEqual(len(list(dest.glob("ZAENIA-data-*.zip"))), 14)


if __name__ == "__main__":
    unittest.main()
