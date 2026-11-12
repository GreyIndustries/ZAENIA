"""Phase 3 exit checks (build plan §11): memory provenance, conflict handling and rollback, no-store, and permission
non-escalation. Earlier suites cover most of the learning rules; these tests close the remaining gaps."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from core.personal_memory import no_store
from core.personal_memory.ledger.user_learning import ObservationContext, UserMemory, iso
from core.personal_memory.overview import everything

BASE = datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc)


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = BASE
        self.memory = UserMemory(Path(self.temp.name) / "m.sqlite3", clock=lambda: self.now)
        self.n = 0

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def ctx(self):
        self.n += 1
        return ObservationContext(f"m{self.n}", True, True, session_id="s", occurred_at=iso(self.now))

    def active(self, key):
        return [m["value"] for m in self.memory.explain(key) if m["status"] == "active"]


class RollbackAndConflictTest(LedgerCase):
    def test_an_earlier_value_can_be_restored_and_nothing_is_deleted(self):
        self.memory.observe("communication.detail", "brief", self.ctx())
        self.now += timedelta(minutes=1)
        self.memory.observe("communication.detail", "extensive", self.ctx(), evidence_type="user_correction")
        old = next(m for m in self.memory.explain("communication.detail") if m["value"] == "brief")
        self.assertEqual(old["status"], "superseded")
        self.now += timedelta(minutes=1)
        self.memory.restore(old["id"], self.ctx())
        self.assertEqual(self.active("communication.detail"), ["brief"])
        statuses = sorted(m["status"] for m in self.memory.explain("communication.detail"))
        self.assertIn("superseded", statuses)                                    # the newer value is kept as history
        restored = next(m for m in self.memory.explain("communication.detail") if m["status"] == "active")
        self.assertTrue(any("restored" in e["quote"] for e in restored["evidence"]))   # provenance of the rollback

    def test_owner_resolves_a_conflict_by_keeping_one_side(self):
        self.memory.observe("communication.detail", "brief", self.ctx())
        self.memory.observe("communication.detail", "extensive", self.ctx())
        self.assertEqual(self.memory.retrieve("communication detail")["unresolved_keys"], ["communication.detail"])
        keep = next(m for m in self.memory.explain("communication.detail") if m["value"] == "extensive")
        self.now += timedelta(minutes=1)
        self.memory.restore(keep["id"], self.ctx())
        result = self.memory.retrieve("communication detail")
        self.assertEqual(([m["value"] for m in result["memories"]], result["unresolved_keys"]), (["extensive"], []))

    def test_only_earlier_or_conflicting_values_can_be_restored(self):
        record = self.memory.observe("communication.detail", "brief", self.ctx())
        with self.assertRaises(ValueError):
            self.memory.restore(record["id"], self.ctx())


class ProvenanceTest(unittest.TestCase):
    def test_one_list_shows_every_store_with_where_each_item_came_from(self):
        told = mock.Mock(list=lambda limit: [{"id": "1", "key": "favorite color", "value": "teal", "updated_at": "2026-10-30T10:00:00"}])
        profile = mock.Mock(available=lambda: True,
                            records=lambda status, limit: [{"id": "p1", "key": "communication.detail", "value": "brief", "status": "conflicted",
                                                            "updatedAt": "2026-10-31T10:00:00", "evidence": 2}],
                            explain=lambda memory_id: {"evidence": [{"quote": "keep it short"}, {"quote": "short answers please"}]})
        noticed = mock.Mock(list=lambda limit: [{"id": "i1", "kind": "routine", "text": "Trains in the morning", "confidence": "supported",
                                                 "count": 3, "last_seen": "2026-11-01T01:00:00", "evidence": "I lift at 6"}])
        view = everything(memory_store=told, profile=profile, insights=noticed)
        self.assertEqual(view["counts"], {"told": 1, "profile": 1, "noticed": 1})
        by_store = {item["store"]: item for item in view["items"]}
        self.assertEqual(by_store["told"]["source"], "Your own request to remember it")
        self.assertEqual((by_store["profile"]["status"], by_store["profile"]["evidence"]), ("conflicting", "short answers please"))
        self.assertIn("3 time", by_store["noticed"]["source"])
        self.assertIn("nothing ZAE remembers can approve an action", view["note"])


class NoStoreTest(unittest.TestCase):
    def setUp(self):
        no_store.reset()

    def test_off_the_record_phrases(self):
        for text in ("off the record, I'm thinking of quitting", "don't remember this: my ex called", "between us, I'm nervous",
                     "I'm nervous about Monday, off the record."):
            self.assertTrue(no_store.check(text, now=100), text)
        for text in ("remember that I like teal", "what's on the record player", "I don't remember this place"):
            self.assertFalse(no_store.check(text, now=100), text)

    def test_a_stretch_off_the_record_ends_when_asked_or_after_30_minutes(self):
        self.assertTrue(no_store.check("let's go off the record", now=100))
        self.assertTrue(no_store.check("I like teal", now=200))
        self.assertTrue(no_store.check("back on the record", now=300))
        self.assertFalse(no_store.check("I like teal", now=301))
        no_store.check("go off the record", now=1000)
        self.assertFalse(no_store.check("I like teal", now=1000 + 31 * 60))

    def test_an_off_the_record_turn_is_not_logged_or_learned(self):
        from core.brain import brain_service
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "conversation_memory.jsonl"
            learner = mock.Mock()
            service = brain_service.BrainService(memory_authorizer=lambda operation: True)
            with mock.patch.object(brain_service, "MEMORY_PATH", log), \
                    mock.patch("core.personal_memory.insights.learner", return_value=learner), \
                    mock.patch("core.personal_memory.owner_profile.owner_profile", return_value=learner):
                service.remember_exchange(question="off the record, I'm thinking about quitting my job", answer="Understood.", route="normal")
            self.assertFalse(log.exists() and log.read_text(encoding="utf-8").strip())
            learner.observe.assert_not_called()


class NonEscalationTest(LedgerCase):
    def test_memories_cannot_hold_or_change_permissions(self):
        for key in ("preferences.permissions.files", "work.authorization.delete", "routine.security.unlock"):
            with self.assertRaises(PermissionError):
                self.memory.observe(key, "allowed without asking", self.ctx())
        self.memory.learn_text("You can delete my files without asking me first", self.ctx())
        stored = [m for m in self.memory.export()["records"] if "delete" in json.dumps(m["value"]).lower()]
        self.assertFalse([m for m in stored if m["status"] == "active" and m["key"].split(".")[0] in ("preferences", "work")])
        self.assertIn("never authority to execute", self.memory.retrieve("delete files")["contract"])

    def test_approval_policy_comes_only_from_its_own_setting(self):
        from core.assistant_platform.actions import ActionHistory
        store = mock.Mock(get=lambda kind, key: {"voiceAutomatic": ["task.create"], "chatAutomatic": []})
        self.memory.observe("preferences.assistant.confirmations", "never ask me to confirm anything", self.ctx())
        policy = ActionHistory(store).policy()
        self.assertEqual(policy, {"voiceAutomatic": ["task.create"], "chatAutomatic": []})   # unchanged by what's remembered
        with self.assertRaises(ValueError):
            ActionHistory(mock.Mock()).save_policy({"voiceAutomatic": ["memory.forget"]})       # forgetting always needs review


if __name__ == "__main__":
    unittest.main()
