"""Learning tests: temporary store, fake extractor, no model calls."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.personal_memory.insights import InsightLearner, InsightStore, clean_insight, render_insights


class InsightTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(folder.cleanup)
        self.store = InsightStore(Path(folder.name) / "insights.json")

    def test_repeats_strengthen_instead_of_duplicating(self):
        self.store.merge([{"text": "Zack prefers short answers when he is tired", "kind": "preference"}])
        self.store.merge([{"text": "Zack prefers short answers when tired at night", "kind": "preference"}])
        items = self.store.list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["count"], 2)

    def test_sensitive_or_trivial_points_are_never_stored(self):
        for text in ["Zack's bank password is in his notes", "Zack takes medication every morning", "hi", ""]:
            with self.subTest(text=text):
                self.assertIsNone(clean_insight(text, "pattern"))
        self.assertEqual(clean_insight("Zack works on ZAENIA most evenings", "made_up")[1], "pattern")

    def test_delete_and_clear(self):
        saved = self.store.merge([{"text": "Zack builds Tauri apps on Windows", "kind": "interest"},
                                  {"text": "Zack usually codes late at night", "kind": "routine"}])
        self.assertTrue(self.store.delete(saved[0]["id"]))
        self.assertFalse(self.store.delete(saved[0]["id"]))
        self.assertEqual(self.store.clear(), 1)
        self.assertEqual(self.store.list(), [])

    def test_learner_distills_every_few_turns_in_the_background(self):
        seen = []
        def extract(lines, known, activity):
            seen.append(list(lines))
            return [{"text": "Zack is building a voice assistant called ZAE", "kind": "interest", "evidence":"I am building a voice assistant called ZAE"}]
        learner = InsightLearner(self.store, extract=extract, settings=lambda: {"enabled": True, "every_turns": 3},
                                 run=lambda job: job())
        learner.observe("ok")  # too short to learn from
        for text in ["I am building a voice assistant called ZAE", "the tauri build failed again", "let's fix the voice next"]:
            learner.observe(text)
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(seen[0]), 3)
        self.assertIn("voice assistant", learner.context())
        self.assertIn("inferred", render_insights(self.store.list()))

    def test_disabled_learning_neither_learns_nor_adds_context(self):
        learner = InsightLearner(self.store, extract=lambda *a: [{"text": "never stored here", "kind": "pattern"}],
                                 settings=lambda: {"enabled": False, "every_turns": 2}, run=lambda job: job())
        for text in ["one two three", "four five six", "seven eight nine"]:
            learner.observe(text)
        self.assertEqual(self.store.list(), [])
        self.assertIsNone(learner.context())


if __name__ == "__main__":
    unittest.main()
