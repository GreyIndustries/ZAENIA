import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.assistant_platform import code_doctor
from core.assistant_platform.arena import Arena
from core.assistant_platform.suggestions import Suggestions


class CodeDoctorTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        (self.root / "app.py").write_text("import os\nimport json\n\ndef add(x, items=[]):\n    try:\n        return json.dumps(x)\n    except:\n        pass\n    if x is 'a':\n        pass\n# TODO tidy\nAPI_KEY = 'abcd1234abcd1234abcd'\n", encoding="utf-8")
        (self.root / "broken.py").write_text("def oops(:\n", encoding="utf-8")
        (self.root / "bad.json").write_text("{nope}", encoding="utf-8")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "skip.py").write_text("def x(:\n", encoding="utf-8")
        self.patch = mock.patch.object(code_doctor, "allowed_roots", return_value=[self.root])
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.folder.cleanup()

    def test_scan_finds_real_problems_without_running_code(self):
        found = code_doctor.scan(str(self.root))
        messages = {(f["file"], f["message"].split(":")[0]) for f in found["findings"]}
        self.assertIn(("broken.py", "Syntax error"), messages)
        self.assertIn(("bad.json", "JSON won't load"), messages)
        text = " ".join(f["message"] for f in found["findings"] if f["file"] == "app.py")
        for expected in ("Bare except", "shared between calls", "'is' compares identity", "'os' is imported but never used", "Leftover note", "secret"):
            self.assertIn(expected, text)
        self.assertNotIn("node_modules/skip.py", {f["file"] for f in found["findings"]})

    def test_projects_outside_allowed_roots_are_refused(self):
        with self.assertRaises(ValueError):
            code_doctor.scan("C:/Windows")
        with self.assertRaises(ValueError):
            code_doctor.read_file(str(self.root), "../outside.py")

    def test_fix_applies_with_backup_and_refuses_stale_or_protected(self):
        target, old = code_doctor.read_file(str(self.root), "app.py")
        digest = hashlib.sha256(old.encode()).hexdigest()
        with mock.patch.object(code_doctor, "PROJECT_ROOT", self.root):
            with self.assertRaises(ValueError):
                code_doctor.apply_fix(str(self.root), "app.py", "x = 1\n", "0" * 64)
            result = code_doctor.apply_fix(str(self.root), "app.py", "x = 1\n", digest)
            self.assertEqual((self.root / "app.py").read_text(), "x = 1\n")
            self.assertEqual(Path(result["backup"]).read_text(), old)
            (self.root / "core" / "foundation").mkdir(parents=True)
            (self.root / "core" / "foundation" / "auth.py").write_text("a = 1\n")
            with self.assertRaises(PermissionError):
                code_doctor.apply_fix(str(self.root), "core/foundation/auth.py", "a = 2\n", hashlib.sha256(b"a = 1\n").hexdigest())

    def test_extract_and_diff(self):
        self.assertEqual(code_doctor.extract_code("Here:\n```python\nx = 2\n```"), "x = 2\n")
        self.assertIn("+x = 2", code_doctor.unified("x = 1\n", "x = 2\n", "a.py"))


class SuggestionsTest(unittest.TestCase):
    def test_think_dedupes_and_approval_sets_reminder(self):
        with tempfile.TemporaryDirectory() as folder:
            box = Suggestions(Path(folder) / "s.json")
            reply = json.dumps({"suggestions": [{"for": "day", "title": "Pack gym bag", "why": "Gym at 7.", "remind": "9pm|pack gym bag"},
                                                {"for": "zae", "title": "Read weather aloud", "why": "You ask daily."},
                                                {"for": "day", "title": "pack gym bag", "why": "dup"}]})
            fresh = box.think(lambda prompt: "Sure: " + reply, context=lambda: "calendar: gym 7am")
            self.assertEqual([s["title"] for s in fresh], ["Pack gym bag", "Read weather aloud"])
            self.assertEqual(box.think(lambda prompt: reply, context=str), [])
            done = box.decide(fresh[0]["id"], True, set_reminder=lambda when, text: f"set {when} {text}")
            self.assertEqual(done["outcome"], "set 9pm pack gym bag")
            self.assertEqual(box.decide(fresh[1]["id"], False)["status"], "dismissed")

    def test_upgrades_and_features(self):
        from core.assistant_platform import suggestions as module
        with tempfile.TemporaryDirectory() as folder:
            box = Suggestions(Path(folder) / "s.json")
            prompts = []
            reply = json.dumps({"suggestions": [
                {"for": "upgrade", "title": "Update torch", "why": "2.6 is out.", "how": "Run zae.ps1 update.", "effort": "Medium"},
                {"for": "feature", "title": "Morning briefing", "why": "You ask daily.", "effort": "huge"},
                {"for": "day", "title": "Gym", "why": "x", "remind": "6pm|gym"}]})
            fresh = box.think(lambda prompt: prompts.append(prompt) or reply, context=lambda: "torch 2.5 (latest 2.6)", focus="system")
            self.assertEqual([(s["for"], s["effort"]) for s in fresh], [("upgrade", "medium"), ("feature", "")])
            self.assertIn("UPGRADE", prompts[0]); self.assertNotIn("DAY (", prompts[0])
            box.decide(fresh[0]["id"], True)
            self.assertEqual(box.list()[0]["outcome"], "Added to ZAE's upgrade plan.")
            plan = module.upgrade_plan(box.list())
            self.assertIn("Upgrade [medium]: Update torch. 2.6 is out. How: Run zae.ps1 update.", plan)
            box.think(lambda prompt: prompts.append(prompt) or "{}", context=str, focus="all")
            self.assertIn("Don't repeat these earlier ideas: Morning briefing; Update torch", prompts[1])
            with self.assertRaises(ValueError):
                box.think(lambda prompt: "{}", context=str, focus="weird")

    def test_system_context_reports_versions_and_existing_features(self):
        from core.assistant_platform import suggestions as module
        versions = lambda: {"python": "3.13.15", "packages": [{"name": "torch", "installed": "2.5", "latest": "2.6"},
                                                               {"name": "fastapi", "installed": "1.0", "latest": "1.0"}],
                            "ollama": {"installed": "0.12.0", "latest": "0.13.1"}}
        text = module.gather_system_context(versions)
        self.assertIn("Packages with newer releases: torch 2.5 (latest 2.6)", text)
        self.assertIn("Packages up to date: fastapi", text)
        self.assertIn("Ollama 0.12.0 (latest 0.13.1)", text)
        self.assertIn("WHAT THE APP ALREADY HAS", text)


class ArenaTest(unittest.TestCase):
    def test_rounds_votes_board_and_brain_override(self):
        with tempfile.TemporaryDirectory() as folder:
            ring = Arena(Path(folder) / "a.json", Path(folder) / "brain.json")
            fake = lambda model, question: {"model": model, "answer": f"{model} says hi", "seconds": 2.0 if model == "a" else 4.0}
            round_ = ring.run("hello?", ["a", "b", "a"], ask=fake)
            self.assertEqual([a["model"] for a in round_["answers"]], ["a", "b"])
            with mock.patch("core.brain.local_llm.get_brain_settings", return_value={"model": "a"}):
                board = ring.vote(round_["id"], "b")
            self.assertEqual(board["board"][0]["model"], "b")
            with self.assertRaises(ValueError):
                ring.run("x", ["only-one"], ask=fake)
            with mock.patch("core.assistant_platform.arena.local_models", return_value=[{"name": "b"}]), \
                    mock.patch("core.brain.local_llm.get_brain_settings", return_value={"model": "b"}):
                self.assertEqual(ring.use_as_brain("b")["override"], "b")
                with self.assertRaises(ValueError):
                    ring.use_as_brain("not-downloaded")


if __name__ == "__main__":
    unittest.main()
