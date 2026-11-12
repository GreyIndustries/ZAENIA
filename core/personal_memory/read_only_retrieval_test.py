"""Reading memory never creates, changes or deletes it, and never learns.

Learning happens only in BrainService.remember_exchange, after a reply is
saved and with memory.write. Every store here is a temporary folder; no
personal file is read or written.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.personal_memory import MemoryStore, memory_context
from core.personal_memory import insights, store
from core.personal_memory.insights import InsightLearner, InsightStore
from core.personal_memory.ledger.user_learning import ObservationContext, UserMemory
from core.personal_memory.owner_profile import OwnerProfile

ENABLED = lambda: {"enabled": True, "every_turns": 6}  # noqa: E731


def snapshot(folder: Path) -> dict[str, bytes]:
    """Every file under the folder and its exact bytes (lock files aside)."""
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and p.suffix != ".lock"}


def never(*args, **kwargs):
    raise AssertionError("retrieval must not call the learner")


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)


class ExplicitMemoryReadTest(TempFolder):
    def test_reading_with_no_store_creates_nothing(self):
        path = self.dir / "personal_memory" / "memory.sqlite3"
        with mock.patch.object(store, "DEFAULT_PATH", path), \
                mock.patch.object(store, "protect_storage") as protect:
            self.assertIsNone(memory_context("what is my favorite color"))
        self.assertFalse(path.parent.exists())
        protect.assert_not_called()

    def test_reading_an_existing_store_changes_nothing(self):
        path = self.dir / "personal_memory" / "memory.sqlite3"
        MemoryStore(path).upsert("my favorite color", "green", "preference")
        before = snapshot(self.dir)
        with mock.patch.object(store, "DEFAULT_PATH", path), mock.patch.object(store, "protect_storage"):
            for _ in range(3):
                self.assertIn("green", memory_context("what is my favorite color"))
        self.assertEqual(snapshot(self.dir), before)

    def test_explicit_remember_still_saves(self):
        memories = MemoryStore(self.dir / "memory.sqlite3")
        memories.upsert("my favorite color", "green", "preference")
        self.assertEqual(memories.get("favorite color")["value"], "green")


class InsightReadTest(TempFolder):
    def test_reading_with_no_store_creates_nothing(self):
        path = self.dir / "personal_memory" / "insights.json"
        learner = InsightLearner(extract=never, settings=ENABLED, run=never)
        with mock.patch.object(insights, "DEFAULT_PATH", path):
            self.assertIsNone(learner.context("how do I like answers"))
        self.assertFalse(path.parent.exists())

    def test_reading_existing_insights_changes_nothing_and_learns_nothing(self):
        saved = InsightStore(self.dir / "insights.json")
        saved.merge([{"text": "Zack prefers short spoken answers from his assistant", "kind": "preference",
                      "evidence": "I prefer short spoken answers"}])
        before = snapshot(self.dir)
        learner = InsightLearner(saved, extract=never, settings=ENABLED, run=never)
        for _ in range(3):
            self.assertIn("short spoken answers", learner.context("short spoken answers please"))
        self.assertEqual(snapshot(self.dir), before)
        self.assertEqual(list(learner.pending), [])


class OwnerProfileReadTest(TempFolder):
    def owner_turn(self, message_id):
        return ObservationContext(message_id=message_id, owner_verified=True, active_conversation=True)

    def test_reading_with_no_profile_creates_nothing(self):
        path = self.dir / "user_understanding" / "user_memory.sqlite3"
        profile = OwnerProfile(path, extract=never, run=never)
        self.assertIsNone(profile.context("what GPU do I have"))
        self.assertEqual(profile.records(), [])
        with self.assertRaises(KeyError):
            profile.explain("0" * 32)
        self.assertFalse(path.parent.exists())

    def test_reading_an_existing_profile_changes_nothing_and_learns_nothing(self):
        path = self.dir / "user_memory.sqlite3"
        with UserMemory(path) as memory:
            item = memory.observe("hardware.gpu", "RTX 4070 Ti SUPER", self.owner_turn("seed-1"),
                                  kind="fact", quote="my GPU is an RTX 4070 Ti SUPER")
        before = snapshot(self.dir)
        profile = OwnerProfile(path, extract=never, run=never)
        for _ in range(2):
            self.assertIn("RTX 4070 Ti SUPER", profile.context("what gpu hardware do I have"))
            self.assertTrue(profile.records(query="gpu"))
            self.assertTrue(profile.explain(item["id"])["evidence"])
        self.assertEqual(snapshot(self.dir), before)
        self.assertEqual(list(profile.pending), [])

    def test_explicit_owner_statement_still_learns(self):
        path = self.dir / "user_memory.sqlite3"
        with UserMemory(path):
            pass
        profile = OwnerProfile(path, extract=never, run=never)
        changes = profile.observe("Call me Grey", channel="typed")
        self.assertEqual([(c["key"], c["status"]) for c in changes], [("identity.preferred_address", "active")])
        self.assertIn("preferred address: Grey", profile.context("hello"))


class LearningCoordinatorTest(TempFolder):
    """remember_exchange is the one place learning starts, and it needs memory.write."""

    def remember(self, allowed):
        from core.brain import brain_service
        record, observe, profile = mock.Mock(), mock.Mock(), mock.Mock()
        log = self.dir / "conversation_memory.jsonl"
        service = brain_service.BrainService(memory_authorizer=lambda operation: operation in allowed)
        with mock.patch.object(brain_service, "MEMORY_PATH", log), \
                mock.patch("core.brain.conversation_threads.tracker", return_value=mock.Mock(record=record)), \
                mock.patch("core.personal_memory.insights.learner", return_value=mock.Mock(observe=observe)), \
                mock.patch("core.personal_memory.owner_profile.owner_profile", return_value=mock.Mock(observe=profile)):
            service.remember_exchange(question="I like working late at night", answer="Noted.", route="normal")
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        return rows, record, observe, profile

    def test_without_memory_write_nothing_is_learned(self):
        rows, record, observe, profile = self.remember({"memory.read"})
        self.assertEqual([row["role"] for row in rows], ["user", "assistant"])  # the conversation log is unchanged
        record.assert_not_called()
        observe.assert_not_called()
        profile.assert_not_called()

    def test_with_memory_write_every_learner_runs_once(self):
        _, record, observe, profile = self.remember({"memory.read", "memory.write"})
        record.assert_called_once()
        observe.assert_called_once_with("I like working late at night")
        profile.assert_called_once_with("I like working late at night", channel="typed")


if __name__ == "__main__":
    unittest.main()
