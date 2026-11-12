"""The four brains in Settings diagnostics: every field fits what the app accepts (100 characters), or the whole
status feed is rejected as "invalid status schema" (2026-11-01)."""
import unittest
from unittest import mock

from core.brain import roster


class BrainModulesTest(unittest.TestCase):
    def test_every_state_fits_the_apps_limits(self):
        models = {b["model"] for b in roster.brains()}
        for installed, loaded in ((models, {"qwen3.5:4b"}), (set(), set()), (None, set())):
            rows = roster.brain_modules(installed, loaded)
            self.assertEqual([r["id"] for r in rows], ["brain_talk", "brain_seek", "brain_study", "brain_keep"])
            for row in rows:
                self.assertIn(row["phase"], ("ready", "working", "pending", "error"))
                for key in ("id", "name", "detail"):
                    self.assertLessEqual(len(row[key]), 100, row)

    def test_detail_says_the_job_and_whether_it_is_loaded(self):
        rows = {r["id"]: r for r in roster.brain_modules({b["model"] for b in roster.brains()}, {"qwen3.5:4b"})}
        self.assertEqual(rows["brain_talk"]["detail"], "Answers you. Loaded now on the graphics card.")
        self.assertIn("Loads when needed", rows["brain_keep"]["detail"])
        self.assertIn("processor", rows["brain_keep"]["detail"])

    def test_the_status_feed_keeps_them_within_limits(self):
        from core.api import status_feed
        with mock.patch("requests.get", side_effect=OSError("no ollama")):
            rows = status_feed._brains()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(len(r["detail"]) <= 100 and r["phase"] == "error" for r in rows))


if __name__ == "__main__":
    unittest.main()
