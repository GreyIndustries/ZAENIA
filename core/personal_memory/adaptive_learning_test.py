"""Evidence, corrections, rejection races, relevance and permission regression tests."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from core.personal_memory.insights import InsightStore, InsightLearner, grounded_candidates, render_insights, clean_insight


class AdaptiveLearningTests(unittest.TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory(dir=Path(__file__).resolve().parents[2]); self.addCleanup(self.directory.cleanup)
        self.store=InsightStore(Path(self.directory.name)/'insights.json')

    def candidate(self,**changes):
        return {'text':'Zack prefers concise practical answers','kind':'working_style','evidence':'I prefer concise practical answers',**changes}

    def test_evidence_must_be_literal_owner_words(self):
        self.assertEqual(len(grounded_candidates([self.candidate()],['I prefer concise practical answers'])),1)
        for evidence in ['I secretly own a yacht','', 'Hypothetically I prefer concise practical answers', 'He said I prefer concise practical answers']:
            self.assertEqual(grounded_candidates([self.candidate(evidence=evidence)],['Hypothetically I prefer concise practical answers','He said I prefer concise practical answers']),[])
        self.assertEqual(grounded_candidates([self.candidate()],['If I prefer concise practical answers, what would happen?']),[])
        self.assertEqual(grounded_candidates([self.candidate()],['He said I prefer concise practical answers']),[])

    def test_sensitive_identity_and_credentials_are_not_inferred(self):
        for claim in ['Zack is Christian','Zack has depression','Zack is a military veteran','Zack uses sk-proj-123456789abcdefghijk','Zack is a Democrat']:
            self.assertIsNone(clean_insight(claim,'pattern'))

    def test_same_batch_cannot_inflate_evidence(self):
        self.store.merge([self.candidate(),self.candidate()],batch_id='one')
        self.store.merge([self.candidate()],batch_id='one')
        self.assertEqual(self.store.list()[0]['count'],1)
        self.assertEqual(self.store.list()[0]['confidence'],'tentative')
        for identifier in ['two','three']: self.store.merge([self.candidate()],batch_id=identifier)
        item=self.store.list()[0]
        self.assertEqual(item['confidence'],'supported');self.assertEqual(item['source'],'inferred')

    def test_confirmation_cannot_be_overwritten_by_model(self):
        item=self.store.merge([self.candidate()])[0]
        confirmed=self.store.review(item['id'],revision=item['revision'])
        self.assertEqual(confirmed['source'],'user_confirmed')
        self.store.merge([self.candidate(text='Zack prefers concise practical answers always')])
        current=self.store.list()[0]
        self.assertEqual(current['text'],confirmed['text']);self.assertEqual(current['count'],1)

    def test_correction_replaces_text_and_suppresses_old_guess(self):
        item=self.store.merge([self.candidate()])[0]
        self.store.review(item['id'],text='Zack prefers detailed explanations for technical work',revision=item['revision'])
        self.assertEqual(self.store.merge([self.candidate()]),[])
        self.assertEqual(len(self.store.list()),1)
        self.assertIn('detailed',self.store.list()[0]['text'])
        from core.assistant_platform.store import Conflict
        with self.assertRaises(Conflict):self.store.review(item['id'],revision=item['revision'])

    def test_rejection_survives_store_restart_without_plaintext(self):
        item=self.store.merge([self.candidate()])[0]
        self.assertTrue(self.store.delete(item['id']))
        reopened=InsightStore(self.store.path)
        self.assertEqual(reopened.merge([self.candidate()]),[])
        self.assertEqual(reopened.list(),[])
        self.assertNotIn('concise',reopened.feedback_path.read_text())
        self.assertNotIn('I prefer',reopened.path.read_text())

    def test_clear_and_inflight_extraction_cannot_restore_removed_points(self):
        self.store.merge([self.candidate()])
        revision=self.store.revision();self.store.clear()
        self.assertEqual(self.store.merge([self.candidate(text='Zack enjoys science')],expected_revision=revision),[])

    def test_long_point_is_rejected_instead_of_silently_truncated(self):
        self.assertIsNone(clean_insight('x'*241,'interest'))

    def test_context_is_relevant_and_stale_inferences_are_not_used(self):
        self.store.merge([self.candidate(),self.candidate(text='Zack enjoys Star Wars stories',kind='interest')])
        text=render_insights(self.store.list(),question='Explain sorting algorithms')
        self.assertIn('concise',text);self.assertNotIn('Star Wars',text)
        with patch('core.personal_memory.insights._now',return_value=(datetime.now(timezone.utc)-timedelta(days=100)).isoformat()):
            old=self.store.merge([self.candidate(text='Zack likes ancient history',kind='interest')])[0]
        self.assertTrue(old['stale'])
        self.assertIsNone(render_insights([old],question='ancient history'))

    def test_old_plain_list_format_is_still_readable(self):
        legacy={'id':'legacy','text':'Zack likes astronomy','kind':'interest','count':2,'source':'inferred','last_seen':datetime.now(timezone.utc).isoformat()}
        self.store.path.write_text(json.dumps([legacy]))
        self.assertEqual(self.store.list()[0]['revision'],1)
        self.assertEqual(self.store.list()[0]['confidence'],'tentative')

    def test_ambient_activity_and_sensitive_input_do_not_enter_extractor(self):
        calls=[]
        worker=InsightLearner(self.store,extract=lambda *args:calls.append(args) or [],settings=lambda:{'enabled':True,'every_turns':2},run=lambda job:job())
        worker.observe('I prefer concise answers',source='ambient')
        worker.observe('My password is secret')
        self.assertEqual(list(worker.pending),[]);self.assertEqual(calls,[])

    def test_feedback_during_extraction_discards_the_whole_stale_batch(self):
        item=self.store.merge([self.candidate()])[0]
        def extract(*args):
            self.store.delete(item['id']);return [self.candidate()]
        worker=InsightLearner(self.store,extract=extract,settings=lambda:{'enabled':True,'every_turns':2},run=lambda job:job())
        worker.observe('I prefer concise practical answers');worker.observe('I enjoy learning science')
        self.assertEqual(self.store.list(),[])

    def test_brain_never_retrieves_inferences_without_read_permission(self):
        from core.brain.brain_service import BrainService
        with patch('core.personal_memory.insights.learner') as learner:
            learner.return_value.context.return_value='Relevant learning reference'
            BrainService(memory_authorizer=lambda _:False).load_behavior_context('science')
            learner.assert_not_called()
            BrainService(memory_authorizer=lambda _:None).load_behavior_context('science')
            learner.return_value.context.assert_called_once_with('science')


if __name__=='__main__':unittest.main()
