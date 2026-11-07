"""Build requests: the copy, the locked-path check, retries, approve/reject/undo, and the chat phrase."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.assistant_platform import build_helper as bh


def sh(*args, cwd):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root, self.helper = base / "live", base / "helper"
        self.root.mkdir()
        sh("init", "-q", "-b", "main", cwd=self.root)
        sh("config", "user.email", "t@t", cwd=self.root)
        sh("config", "user.name", "t", cwd=self.root)
        (self.root / "core").mkdir()
        (self.root / "core" / "colour.py").write_text("RING = 'gold'\n", encoding="utf-8")
        sh("add", "-A", cwd=self.root)
        sh("commit", "-qm", "start", cwd=self.root)
        self.applied, self.notices, self.tool_calls = [], [], []
        self.review_calls = []
        self.edit = lambda folder: (folder / "core" / "colour.py").write_text("RING = 'blue'\n", encoding="utf-8")
        self.results = [(True, "Python tests: OK")]

    def tearDown(self):
        bh.remove_copy(root=self.root, helper=self.helper)
        self.temp.cleanup()

    def tool(self, tool, folder, prompt, files):
        self.tool_calls.append(prompt)
        self.edit(folder)
        return True, "Made the rings blue."

    def checks(self, folder, changed):
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]

    def review(self, title, brief, diff):
        self.review_calls.append((title, brief, diff))
        return {"status": "reviewed", "model": "test-reviewer", "text": "No findings", "at": "now", "advisory": True}

    def requests(self):
        return bh.BuildRequests(Path(self.temp.name) / "state.json", root=self.root, helper=self.helper,
                                tool_runner=self.tool, checks=self.checks, reviewer=self.review, choose=lambda size, wanted=None: "claude",
                                gaming=lambda: False, notify=lambda *a: self.notices.append(a[1]))

    def draft(self, store):
        ask = lambda prompt: json.dumps({"title": "Blue rings", "brief": "Make the core rings blue.", "size": "small", "check": "rings are blue"})
        return store.create("build blue rings when I'm tired", ask)


class FlowTest(RepoCase):
    def test_draft_waits_for_start_then_tested_change_is_ready_and_live_is_untouched(self):
        store = self.requests()
        item = self.draft(store)
        self.assertEqual((item["status"], item["title"], item["size"]), ("draft", "Blue rings", "small"))
        self.assertIn("Done when: rings are blue", item["brief"])
        store._update(item["id"], status="queued")
        done = store.process(item["id"])
        self.assertEqual(done["status"], "ready", done.get("step"))
        self.assertEqual(done["changed"], ["core/colour.py"])
        self.assertIn("+RING = 'blue'", done["diff"])
        self.assertEqual((self.root / "core" / "colour.py").read_text(), "RING = 'gold'\n")   # live code unchanged
        self.assertFalse(self.helper.exists())                                                 # the copy is cleaned up
        self.assertTrue(any("Ready to review" in n for n in self.notices))
        self.assertEqual(done["review"]["status"], "reviewed")
        self.assertIn("+RING = 'blue'", self.review_calls[0][2])

    def test_approve_merges_and_undo_reverts(self):
        store = self.requests()
        item = self.draft(store)
        store._update(item["id"], status="queued")
        store.process(item["id"])
        approved = store.approve(item["id"])
        self.assertEqual((self.root / "core" / "colour.py").read_text(), "RING = 'blue'\n")
        self.assertEqual(approved["needs"], {"app": False, "server": True})
        store.undo(item["id"])
        self.assertEqual((self.root / "core" / "colour.py").read_text(), "RING = 'gold'\n")
        self.assertEqual(store.get(item["id"])["status"], "undone")

    def test_only_ready_changes_can_be_approved(self):
        store = self.requests()
        item = self.draft(store)
        with self.assertRaises(ValueError):
            store.approve(item["id"])

    def test_failed_tests_go_back_to_the_tool_then_stop(self):
        self.results = [(False, "FAIL: test_ring"), (False, "FAIL: test_ring"), (False, "FAIL: test_ring")]
        store = self.requests()
        item = self.draft(store)
        store._update(item["id"], status="queued")
        done = store.process(item["id"])
        self.assertEqual(done["status"], "failed")
        self.assertEqual(len(self.tool_calls), bh.RETRIES + 1)
        self.assertIn("FAIL: test_ring", self.tool_calls[1])
        self.assertNotIn("zae/", subprocess.run(["git", "-C", str(self.root), "branch"], capture_output=True, text=True).stdout)

    def test_a_retry_that_passes_is_ready(self):
        self.results = [(False, "FAIL: x"), (True, "OK")]
        store = self.requests()
        item = self.draft(store)
        store._update(item["id"], status="queued")
        self.assertEqual(store.process(item["id"])["status"], "ready")

    def test_touching_a_locked_path_throws_the_work_away(self):
        def sneaky(folder):
            (folder / "core" / "foundation").mkdir(parents=True)
            (folder / "core" / "foundation" / "rules.py").write_text("ALLOW_ALL = True\n", encoding="utf-8")
        self.edit = sneaky
        store = self.requests()
        item = self.draft(store)
        store._update(item["id"], status="queued")
        done = store.process(item["id"])
        self.assertEqual(done["status"], "failed")
        self.assertIn("locked files", done["step"])
        self.assertFalse((self.root / "core" / "foundation").exists())

    def test_a_tools_own_files_are_not_part_of_the_change(self):
        real_edit = self.edit

        def messy(folder):
            real_edit(folder)
            (folder / ".aider.chat.history.md").write_text("# chat\n", encoding="utf-8")
            (folder / ".aider.tags.cache.v4").mkdir()
            (folder / ".aider.tags.cache.v4" / "x.val").write_text("cache", encoding="utf-8")
        self.edit = messy
        store = self.requests()
        item = self.draft(store)
        store._update(item["id"], status="queued")
        done = store.process(item["id"])
        self.assertEqual(done["status"], "ready", done.get("step"))
        self.assertEqual(done["changed"], ["core/colour.py"])
        self.assertNotIn(".aider", done["diff"])

    def test_a_run_that_only_leaves_tool_files_changed_nothing(self):
        def junk_only(folder):
            (folder / ".aider.input.history").write_text("x", encoding="utf-8")
        self.edit = junk_only
        store = self.requests()
        item = self.draft(store)
        store._update(item["id"], status="queued")
        done = store.process(item["id"])
        self.assertEqual(done["status"], "failed")
        self.assertIn("didn't change anything", done["step"])

    def test_reject_deletes_the_branch(self):
        store = self.requests()
        item = self.draft(store)
        store._update(item["id"], status="queued")
        store.process(item["id"])
        store.reject(item["id"])
        self.assertEqual(store.get(item["id"])["status"], "rejected")
        self.assertNotIn("zae/", subprocess.run(["git", "-C", str(self.root), "branch"], capture_output=True, text=True).stdout)


class RulesTest(unittest.TestCase):
    def test_second_pass_review_is_local_bounded_and_redacts_secrets(self):
        from unittest.mock import patch
        with patch("core.brain.local_llm.get_brain_settings", return_value={"endpoint": "http://127.0.0.1:11434/api/chat"}), \
             patch("core.brain.local_llm.chat_local", return_value="No findings") as chat:
            result = bh.review_change_locally("Title", "Brief", "API_KEY='super-secret-value'\n" + "x" * 31_000)
        self.assertEqual(result["status"], "reviewed")
        self.assertEqual(result["model"], "qwen3.5:9b")
        prompt = chat.call_args.args[0]
        self.assertIn("[REDACTED]", prompt)
        self.assertNotIn("super-secret-value", prompt)
        self.assertLess(len(prompt), 32_000)

    def test_second_pass_review_refuses_remote_model_endpoint(self):
        from unittest.mock import patch
        with patch("core.brain.local_llm.get_brain_settings", return_value={"endpoint": "https://example.com/api/chat"}), \
             patch("core.brain.local_llm.chat_local") as chat:
            with self.assertRaises(PermissionError):
                bh.review_change_locally("Title", "Brief", "diff")
        chat.assert_not_called()

    def test_locked_paths(self):
        for path in ("core/foundation/x.py", "core/voice_security/runtime.py", "core/api/auth.py", "scripts/zae.ps1",
                     ".github/workflows/ci.yml", ".claude/settings.json", "core/assistant_platform/build_helper.py",
                     "core/api/build_routes.py", "core/api/client_gate.py", "desktop/src-tauri/tauri.conf.json",
                     "desktop/package.json", "AGENTS.md", "data/secure/x.json", "Core/Foundation/x.py", "core/api/ui_routes.py"):
            self.assertTrue(bh.locked(path), path)
        for path in ("core/assistant_platform/nutrition.py", "desktop/src/components/core/neuralField.ts", "docs/notes.md"):
            self.assertFalse(bh.locked(path), path)

    def test_tool_choice(self):
        both = {"claude": True, "aider": True}
        self.assertEqual(bh.choose_tool("small", available=both, is_online=lambda: True), "aider")
        self.assertEqual(bh.choose_tool("large", available=both, is_online=lambda: True), "claude")
        self.assertEqual(bh.choose_tool("large", available=both, is_online=lambda: False), "aider")
        self.assertEqual(bh.choose_tool("small", "claude", available=both), "claude")
        self.assertEqual(bh.choose_tool("small", available={"claude": True, "aider": False}, is_online=lambda: True), "claude")
        with self.assertRaises(RuntimeError):
            bh.choose_tool("small", available={"claude": False, "aider": False})

    def test_secrets_stay_out_of_the_tools(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"TWILIO_AUTH_TOKEN": "x", "ZAENIA_DESKTOP_KEY": "y", "PATH": "p"}):
            env = bh._clean_env()
        self.assertEqual(("TWILIO_AUTH_TOKEN" in env, "ZAENIA_DESKTOP_KEY" in env, env.get("PATH")), (False, False, "p"))

    def test_chat_phrase(self):
        self.assertEqual(bh.parse_build("ZAE, build a water tracker on the health tab"), "a water tracker on the health tab")
        self.assertEqual(bh.parse_build("change your code so the rings turn blue at night"), "the rings turn blue at night")
        for text in ("build the app", "make a note about lunch", "what should I build next", "build muscle"):
            self.assertIsNone(bh.parse_build(text), text)


if __name__ == "__main__":
    unittest.main()
