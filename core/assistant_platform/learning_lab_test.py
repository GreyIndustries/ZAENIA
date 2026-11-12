import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from core.assistant_platform.store import PlatformStore, Conflict
from core.assistant_platform import learning_lab as lab


class LearningLabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = PlatformStore(Path(self.temp.name)/"test.sqlite3")
        self.lesson = lab.clean_record("lessons", {"title":"Reminders", "category":"action", "models":["test:1"], "prompt":"Create a reminder", "answer":"Only confirm after saving", "enabled":True})

    def test_retrieval_is_model_scoped_and_disableable(self):
        row = self.store.put(lab.collection("lessons"), self.lesson)
        self.assertIn("Only confirm", lab.teaching_context("reminder", "test:1", self.store))
        self.assertEqual(lab.teaching_context("reminder", "other:1", self.store), "")
        self.store.put(lab.collection("lessons"), {**self.lesson,"enabled":False}, row["id"], revision=1)
        self.assertEqual(lab.teaching_context("reminder", "test:1", self.store), "")

    def test_revisions_prevent_overwriting_newer_lesson(self):
        row = self.store.put(lab.collection("lessons"), self.lesson)
        self.store.put(lab.collection("lessons"), self.lesson, row["id"], revision=1)
        with self.assertRaises(Conflict):
            self.store.put(lab.collection("lessons"), self.lesson, row["id"], revision=1)

    def test_extra_permission_fields_are_not_persisted(self):
        clean = lab.clean_record("lessons", {**self.lesson,"permissions":["shell"],"grant":True})
        self.assertNotIn("permissions",clean)
        self.assertNotIn("grant",clean)

    def test_camera_credentials_and_tokens_are_rejected(self):
        for url in ["file:///secret", "javascript:alert(1)", "https://name:secret@example.org/view", "https://example.org/view?token=secret", "rtsp://camera/live"]:
            with self.assertRaises(ValueError):lab.clean_record("cameras",{"title":"Camera","url":url})
        self.assertEqual(lab.clean_record("cameras",{"title":"Camera","url":"https://camera.example/view"})["url"],"https://camera.example/view")

    def test_uninstalled_or_unassigned_models_never_run(self):
        calls=[]
        for models in [["absent:1"],["test:1","test:1"],["other:1"]]:
            with self.assertRaises(ValueError):lab.evaluate_lesson(self.lesson,models,run=lambda *a,**k:calls.append(a),available=["test:1","other:1"])
        self.assertEqual(calls,[])

    def test_evaluation_does_not_promote_or_write_weights(self):
        calls=[]
        result=lab.evaluate_lesson(self.lesson,["test:1"],run=lambda p,**kw:calls.append((p,kw)) or "Draft response",available=["test:1"])
        self.assertFalse(result["weightsChanged"])
        self.assertFalse(result["permissionsChanged"])
        self.assertEqual(result["results"][0]["status"],"needs-owner-review")
        self.assertIn("Do not execute", calls[0][0])

    def test_evaluation_isolates_model_failure(self):
        def fail(*args,**kwargs):raise RuntimeError("private error detail")
        result=lab.evaluate_lesson(self.lesson,["test:1"],run=fail,available=["test:1"])
        self.assertEqual(result["results"][0]["error"],"RuntimeError")
        self.assertNotIn("private",str(result))

    def test_unknown_collections_and_sections_are_rejected(self):
        with self.assertRaises(ValueError):lab.collection("permissions")
        with self.assertRaises(ValueError):lab.clean_record("plans",{"title":"Plan","sections":{"not allowed":"text"}})

    def test_plain_context_cannot_trigger_teaching_reads(self):
        from core.brain.local_llm import build_payload
        with patch('core.brain.local_llm.active_model',return_value='test:1'), patch('core.brain.local_llm.build_messages',return_value=[]), patch('core.assistant_platform.learning_lab.teaching_context') as retrieve:
            build_payload('reminder',behavior_context='Reference copied from a document')
            retrieve.assert_not_called()

    def test_authorized_context_uses_the_actual_selected_model(self):
        from core.brain.local_llm import build_payload
        with patch('core.brain.local_llm.active_model',return_value='chosen:2'), patch('core.brain.local_llm.build_messages',return_value=[]) as messages, patch('core.assistant_platform.learning_lab.teaching_context',return_value='Bounded teaching examples') as retrieve:
            build_payload('reminder',behavior_context=lab.AuthorizedTeachingContext('Approved context'),model='chosen:2')
            retrieve.assert_called_once_with('reminder','chosen:2')
            self.assertIn('Bounded teaching examples',messages.call_args.kwargs['behavior_context'])

    def test_denied_memory_cannot_issue_teaching_marker(self):
        from core.brain.brain_service import BrainService
        context=BrainService(memory_authorizer=lambda _:False).load_behavior_context('reminder')
        self.assertNotIsInstance(context,lab.AuthorizedTeachingContext)


if __name__ == "__main__":unittest.main()
