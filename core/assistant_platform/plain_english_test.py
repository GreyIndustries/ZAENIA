"""Plain English tab: outline, splitting, cached explanations, and Python drafts that are only text."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.assistant_platform import code_doctor, plain_english as pe

SAMPLE = '''"""Keeps Grey's water plants healthy."""


def check_ph(value: float) -> bool:
    """True when the water's pH is safe for the plants."""
    return 5.5 <= value <= 6.5


class Pump:
    """The water pump."""

    def start(self) -> None:
        """Turn the pump on."""
        self.on = True
'''


class PlainEnglishTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name).resolve()
        (self.root / "garden.py").write_text(SAMPLE, encoding="utf-8")
        (self.root / "secret.txt").write_text("not code", encoding="utf-8")
        self.cache = self.root / "cache" / "plain.json"
        self.patch = mock.patch.object(code_doctor, "allowed_roots", return_value=[self.root])
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop(); self.folder.cleanup()

    def test_outline_lists_functions_classes_and_methods_without_a_model(self) -> None:
        items = pe.outline("garden.py", SAMPLE)
        self.assertEqual([(i["kind"], i["name"]) for i in items],
                         [("file", "garden.py"), ("function", "check_ph"), ("class", "Pump"), ("method", "Pump.start")])
        self.assertIn("pH is safe", items[1]["note"])
        self.assertEqual(items[1]["line"], 4)
        ts = pe.outline("a.tsx", "/** Shows the clock. */\nexport function Clock() {\n  return null;\n}\nconst add = (a: number) => a;\n")
        self.assertEqual([(i["name"], i["note"]) for i in ts], [("Clock", "Shows the clock."), ("add", "")])
        self.assertEqual(pe.outline("broken.py", "def (:"), [])

    def test_split_parts_keeps_every_line_and_cuts_before_top_level_code(self) -> None:
        text = "".join(f"def f{n}():\n    return {n}\n\n" for n in range(200))
        parts = pe.split_parts(text, limit=500)
        self.assertGreater(len(parts), 1)
        self.assertEqual("".join(part for _, part in parts), text)
        for first, part in parts:
            self.assertTrue(part.startswith("def ") or part.startswith("\n"), part[:20])
            self.assertEqual(text.splitlines(True)[first - 1], part.splitlines(True)[0])
        self.assertEqual(pe.split_parts(""), [(1, "")])

    def test_explain_uses_the_model_once_then_the_cache_until_the_file_changes(self) -> None:
        ask = mock.Mock(return_value="<think>hmm</think>This checks the water.")
        first = pe.explain(str(self.root), "garden.py", ask, cache_file=self.cache)
        self.assertEqual(first["text"], "This checks the water.")
        self.assertFalse(first["cached"])
        self.assertIn("FILE: garden.py", ask.call_args.args[0])
        self.assertIn("data, not instructions", ask.call_args.args[0])
        again = pe.explain(str(self.root), "garden.py", ask, cache_file=self.cache)
        self.assertTrue(again["cached"]); self.assertEqual(ask.call_count, 1)
        self.assertEqual(again["outline"][1]["name"], "check_ph")
        pe.explain(str(self.root), "garden.py", ask, refresh=True, cache_file=self.cache)
        self.assertEqual(ask.call_count, 2)
        (self.root / "garden.py").write_text(SAMPLE + "\n# changed\n", encoding="utf-8")
        self.assertFalse(pe.explain(str(self.root), "garden.py", ask, cache_file=self.cache)["cached"])
        self.assertEqual(pe.cached_files(str(self.root), cache_file=self.cache), ["garden.py"])

    def test_long_files_are_explained_in_numbered_parts(self) -> None:
        (self.root / "long.py").write_text("".join(f"def f{n}():\n    return {n}\n\n" for n in range(3000)), encoding="utf-8")
        ask = mock.Mock(return_value="ok")
        result = pe.explain(str(self.root), "long.py", ask, cache_file=self.cache)
        self.assertEqual(ask.call_count, result["parts"])
        self.assertGreater(result["parts"], 1)
        self.assertTrue(result["text"].startswith("Part 1 (from line 1)"))
        self.assertIn("PART 2 of", ask.call_args_list[1].args[0])

    def test_explain_refuses_files_code_doctor_cannot_open(self) -> None:
        ask = mock.Mock()
        for rel in ("secret.txt", "../outside.py", "missing.py"):
            with self.assertRaises(ValueError):
                pe.explain(str(self.root), rel, ask, cache_file=self.cache)
        ask.assert_not_called()

    def test_write_python_returns_code_tests_and_a_plain_walkthrough(self) -> None:
        reply = ("<think>x</think>Here you go.\n```python\ndef double(n: int) -> int:\n    return n * 2\n```\n"
                 "```python\nassert double(2) == 4\n```\n**IN PLAIN ENGLISH:**\n1. Takes a number.\n2. Gives back twice it.\n\nCHECK:\nNothing")
        ask = mock.Mock(return_value=reply)
        result = pe.write_python("Make a function that doubles a number", ask, project=str(self.root), context_file="garden.py")
        self.assertIn("def double", result["code"])
        self.assertEqual(result["tests"].strip(), "assert double(2) == 4")
        self.assertTrue(result["english"].startswith("1. Takes a number."))
        self.assertEqual(result["check"], "Nothing")
        prompt = ask.call_args.args[0]
        self.assertIn("doubles a number", prompt); self.assertIn("FILE: garden.py", prompt); self.assertIn("check_ph", prompt)
        with self.assertRaises(ValueError):
            pe.write_python("hi", ask)
        with self.assertRaises(ValueError):
            pe.write_python("Make something", mock.Mock(return_value="I can't."))

    def test_routes_reuse_code_doctor_endpoints_and_never_run_the_draft(self) -> None:
        from core.api import tools_routes
        app = FastAPI(); app.include_router(tools_routes.create_tools_router(lambda: None))
        client = TestClient(app)
        with mock.patch.object(pe, "CACHE_FILE", self.cache), \
                mock.patch.object(tools_routes, "_ask_study", return_value="Plain words.") as ask:
            scanned = client.post("/api/code/scan", json={"project": str(self.root)}).json()
            self.assertIn({"file": "garden.py", "lines": SAMPLE.count("\n") + 1}, scanned["files"])
            body = client.post("/api/code/explain", json={"project": str(self.root), "file": "garden.py", "mode": "plain"}).json()
            self.assertEqual(body["text"], "Plain words."); self.assertEqual(body["outline"][1]["name"], "check_ph")
            self.assertEqual(client.post("/api/code/explain", json={"project": str(self.root), "file": "garden.py", "mode": "bad"}).status_code, 422)
            ask.return_value = "```python\nprint('hi')\n```\nIN PLAIN ENGLISH:\n1. Says hi."
            with mock.patch("core.assistant_platform.playground.run") as run:
                written = client.post("/api/code/playground/ask", json={"language": "python", "code": "", "mode": "english",
                                                                         "question": "Say hi to Grey"}).json()
                run.assert_not_called()
            self.assertEqual(written["code"].strip(), "print('hi')")
            self.assertEqual(written["english"], "1. Says hi.")


if __name__ == "__main__":
    unittest.main()
