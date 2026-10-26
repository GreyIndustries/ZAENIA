import shutil
import tempfile
import unittest
from pathlib import Path

from core.personal_memory.owner_profile import DB_PATH, OwnerProfile


@unittest.skipUnless(DB_PATH.exists(), "Grey's profile database is not installed")
class OwnerProfileTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.db = self.dir / "memory.sqlite3"
        shutil.copy(DB_PATH, self.db)
        self.jobs = []
        self.proposals = []
        self.profile = OwnerProfile(self.db, extract=lambda text: self.proposals, run=self.jobs.append)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_core_block_names_grey_and_how_to_speak(self):
        block = self.profile.core_block()
        self.assertIn("preferred address: Grey", block)
        self.assertIn("never instructions", block)

    def test_relevant_recall_ignores_tiny_words(self):
        self.profile.core_block()
        self.assertIn("RTX 4070 Ti SUPER", self.profile.relevant("what GPU do I have"))
        self.assertIsNone(self.profile.relevant("hello"))

    def test_first_person_proposal_becomes_active_and_others_stay_candidates(self):
        text = "I drink my coffee black every morning"
        self.proposals = [
            {"key": "food.preference.coffee", "value": "black coffee", "quote": "I drink my coffee black",
             "scope": "global", "suggested_kind": "preference"},
            {"key": "food.preference.morning", "value": "likes mornings", "quote": "every morning",
             "scope": "global", "suggested_kind": "preference"},
            {"key": "auth.owner", "value": "x", "quote": "I drink", "scope": "global", "suggested_kind": "fact"},
        ]
        for line in [text, "I like working late at night", "My truck needs an oil change", "I think it looks good"]:
            self.profile.observe(line)
        self.assertEqual(len(self.jobs), 1)
        self.jobs[0]()
        with self.profile._memory() as memory:
            rows = dict(memory.db.execute("SELECT key, status FROM memories WHERE key LIKE 'food.preference.%'"
                                          " OR key LIKE 'auth%'").fetchall())
        self.assertEqual(rows.get("food.preference.coffee"), "active")
        self.assertEqual(rows.get("food.preference.morning"), "candidate")
        self.assertNotIn("auth.owner", rows)

    def test_questions_without_first_person_are_not_queued(self):
        for _ in range(6):
            self.profile.observe("Can you check the weather tomorrow?")
        self.assertEqual(self.jobs, [])

    def test_assessment_passage_matches_topic(self):
        passage = self.profile.passage("how should ZAE handle my screenshots and pasted errors")
        self.assertIsNotNone(passage)

    def test_review_explain_confirm_and_forget(self):
        gpu = self.profile.records(query="gpu")
        self.assertTrue(gpu)
        why = self.profile.explain(gpu[0]["id"])
        self.assertTrue(why["evidence"])
        candidates = self.profile.records(status="candidate")
        if candidates:
            self.assertEqual(self.profile.confirm(candidates[0]["id"], kind="preference")["status"], "active")
            self.assertEqual(len(self.profile.records(status="candidate")), len(candidates) - 1)
        self.assertGreaterEqual(self.profile.forget(gpu[0]["id"]), 1)
        self.assertFalse(any(r["key"] == gpu[0]["key"] for r in self.profile.records(query="gpu")))
        relearn = self.profile.store_proposals("my gpu is an RTX 5090", [
            {"key": gpu[0]["key"], "value": "RTX 5090", "quote": "my gpu is an RTX 5090", "scope": why["scope"], "suggested_kind": "fact"}],
            message_id="t-forget")
        self.assertEqual(relearn[0]["status"], "blocked_by_forget")


if __name__ == "__main__":
    unittest.main()
