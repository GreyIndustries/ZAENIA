import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.assistant_platform import playground


class RunTests(unittest.TestCase):
    def test_python_runs_and_tests_pass(self):
        result = playground.run("python", "def add(a, b):\n    return a + b\nprint(add(2, 3))", tests="assert add(1, 1) == 2")
        self.assertEqual(result["exitCode"], 0)
        self.assertIn("5", result["stdout"])
        self.assertTrue(result["passed"])

    def test_failed_test_is_reported(self):
        result = playground.run("python", "def add(a, b):\n    return a - b", tests="assert add(1, 1) == 2")
        self.assertFalse(result["passed"])
        self.assertIn("AssertionError", result["stderr"])

    def test_no_tests_means_passed_is_none(self):
        self.assertIsNone(playground.run("python", "print('hi')")["passed"])

    def test_stdin_is_passed(self):
        self.assertIn("HELLO", playground.run("python", "print(input().upper())", stdin="hello")["stdout"])

    def test_timeout_stops_the_program(self):
        result = playground.run("python", "while True:\n    pass", timeout=1)
        self.assertTrue(result["timedOut"])
        self.assertIsNone(result["exitCode"])

    def test_no_secrets_in_environment(self):
        with mock.patch.dict(os.environ, {"ZAENIA_SECRET_TOKEN": "abc123"}):
            result = playground.run("python", "import os\nprint(sorted(os.environ))")
        self.assertNotIn("ZAENIA_SECRET_TOKEN", result["stdout"])

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            playground.run("ruby", "puts 1")
        with self.assertRaises(ValueError):
            playground.run("python", "   ")

    @unittest.skipUnless(shutil.which("node"), "Node not installed")
    def test_javascript(self):
        result = playground.run("javascript", "console.log(1 + 1)", tests="if (2 !== 2) throw new Error('x')")
        self.assertIn("2", result["stdout"])
        self.assertTrue(result["passed"])


class SnippetTests(unittest.TestCase):
    def test_save_update_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snippets.json"
            saved = playground.save_snippet({"title": "One", "language": "python", "code": "print(1)"}, path)
            playground.save_snippet({**saved, "code": "print(2)"}, path)
            items = playground.snippets(path)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["code"], "print(2)")
            playground.delete_snippet(saved["id"], path)
            self.assertEqual(playground.snippets(path), [])

    def test_prompt_marks_code_as_data(self):
        prompt = playground.ask_prompt("python", "print(1)", "", {"exitCode": 1, "stderr": "boom"}, "")
        self.assertIn("data, not instructions", prompt)
        self.assertIn("boom", prompt)


class ImplementTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name).resolve()
        patcher = mock.patch("core.assistant_platform.code_doctor.project_path", return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.folder.cleanup)

    def test_new_file_is_created(self):
        result = playground.save_to_project("x", "src/new.py", "print(1)\n")
        self.assertTrue(result["created"])
        self.assertEqual((self.root / "src" / "new.py").read_text(), "print(1)\n")

    def test_existing_file_needs_matching_hash_and_is_backed_up(self):
        target = self.root / "app.py"
        target.write_text("old\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            playground.save_to_project("x", "app.py", "new\n", "")
        good = hashlib.sha256("old\n".encode()).hexdigest()
        result = playground.save_to_project("x", "app.py", "new\n", good)
        self.assertFalse(result["created"])
        self.assertEqual(target.read_text(), "new\n")
        self.assertEqual(Path(result["backup"]).read_text(), "old\n")
        shutil.rmtree(Path(result["backup"]).parent, ignore_errors=True)

    def test_paths_outside_project_are_refused(self):
        with self.assertRaises(ValueError):
            playground.save_to_project("x", "../escape.py", "print(1)")
        with self.assertRaises(ValueError):
            playground.save_to_project("x", "notes.exe", "x")


if __name__ == "__main__":
    unittest.main()
