import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from core.personal_memory.ledger.user_learning import ObservationContext, UserMemory, iso, turn_scope
from core.personal_memory.ledger.adapter import build_turn_context, stage_model_proposals

BASE = datetime(2026, 10, 18, 22, 12, 44, tzinfo=timezone.utc)
ROOT = Path(tempfile.gettempdir())
# The owner's seed profile is personal and stays out of git; tests that
# import it run only on a PC that has it.
SEED = Path(__file__).resolve().parents[3] / 'user_understanding' / 'GREY-Structured-Memory.json'
needs_seed = unittest.skipUnless(SEED.exists(), 'owner seed profile not present (personal, not in git)')


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='memory-test-', dir=ROOT)
        self.path = Path(self.temp.name) / 'memory.sqlite3'
        self.now = BASE
        self.memory = UserMemory(self.path, clock=lambda: self.now)
        self.sequence = 0

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def ctx(self, **changes):
        self.sequence += 1
        base = ObservationContext(str(self.sequence), True, True, session_id='s1', occurred_at=iso(self.now))
        return replace(base, **changes)

    def values(self, query, **kwargs):
        return [x['value'] for x in self.memory.retrieve(query, **kwargs)['memories']]

    def test_explicit_fact_and_restart_persistence(self):
        self.memory.observe('hardware.gaming.gpu', 'RTX 4070 Ti SUPER', self.ctx(), kind='fact')
        self.memory.close()
        self.memory = UserMemory(self.path, clock=lambda: self.now)
        self.assertIn('RTX 4070 Ti SUPER', self.values('gaming gpu'))

    def test_unauthenticated_input_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.memory.learn_text('Call me Grey', self.ctx(owner_verified=False))

    def test_inactive_conversation_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.memory.learn_text('Call me Grey', self.ctx(active_conversation=False))

    def test_voice_requires_attention_gate(self):
        with self.assertRaises(PermissionError):
            self.memory.learn_text('Call me Grey', self.ctx(channel='verified_voice'))
        self.assertEqual(self.memory.learn_text('Call me Grey', self.ctx(channel='verified_voice',attention_verified=True))[0]['status'],'active')

    def test_assistant_third_party_and_ambient_channels_rejected(self):
        for changes in ({'role':'assistant'},{'quoted_or_third_party':True},{'channel':'ambient'}):
            with self.subTest(changes=changes), self.assertRaises(PermissionError):
                self.memory.learn_text('Call me Grey', self.ctx(**changes))

    def test_protected_namespaces_cannot_be_learned(self):
        for key in ('security.disabled','projects.zaenia.permissions','identity.owner_id','work.Authentication'):
            with self.subTest(key=key), self.assertRaises((PermissionError,ValueError)):
                self.memory.observe(key, True, self.ctx())

    def test_secrets_rejected_without_database_write(self):
        with self.assertRaises(ValueError):
            self.memory.observe('preferences.test', 'api_key=not-a-real-secret', self.ctx())
        self.assertEqual(self.memory.export()['records'], [])

    def test_model_cannot_claim_import_or_active_status(self):
        with self.assertRaises(PermissionError):
            self.memory.observe('communication.detail','long',self.ctx(),initial_status='active')
        with self.assertRaises(PermissionError):
            self.memory.observe('communication.detail','long',self.ctx(),evidence_type='import_user_report')

    def test_inference_confidence_never_makes_it_active(self):
        item = self.memory.observe('preferences.assessment.bold',True,self.ctx(),kind='inference',confidence=1)
        self.assertEqual(item['status'],'candidate')
        self.assertEqual(self.values('bold'),[])
        self.assertLessEqual(item['confidence'],.70)

    def test_duplicate_origins_do_not_amplify_evidence(self):
        first = self.memory.observe('communication.detail','brief',self.ctx(origin_id='original'),evidence_type='behavior_observation')
        for i in range(5):
            self.now += timedelta(days=1)
            item = self.memory.observe('communication.detail','brief',self.ctx(origin_id='original'),evidence_type='behavior_observation')
        self.assertEqual(item['status'],'candidate')
        self.assertEqual(len(item['evidence']),1)
        self.assertEqual(first['id'],item['id'])

    def test_low_impact_pattern_needs_multiple_days(self):
        for i in range(3):
            item = self.memory.observe('communication.detail','brief',self.ctx(),evidence_type='behavior_observation')
        self.assertEqual(item['status'],'candidate')
        self.now += timedelta(days=1)
        item = self.memory.observe('communication.detail','brief',self.ctx(),evidence_type='behavior_observation')
        self.assertEqual(item['status'],'active')

    def test_health_observations_never_auto_promote(self):
        for i in range(4):
            self.now += timedelta(days=1)
            item = self.memory.observe('health.mood','anxious',self.ctx(),evidence_type='behavior_observation')
        self.assertEqual(item['status'],'candidate')

    def test_explicit_preference_overrides_behavior_pattern(self):
        for i in range(3):
            self.now += timedelta(days=1)
            self.memory.observe('communication.detail','brief',self.ctx(),evidence_type='behavior_observation')
        item = self.memory.observe('communication.detail','extensive',self.ctx())
        self.assertEqual(item['status'],'active')
        self.assertEqual(self.values('communication detail'),['extensive'])

    def test_two_conflicting_direct_statements_are_withheld(self):
        self.memory.observe('communication.detail','brief',self.ctx())
        self.memory.observe('communication.detail','extensive',self.ctx())
        result = self.memory.retrieve('communication detail')
        self.assertEqual(result['memories'],[])
        self.assertEqual(result['unresolved_keys'],['communication.detail'])

    def test_explicit_correction_supersedes_history(self):
        self.memory.observe('communication.detail','brief',self.ctx())
        self.now += timedelta(minutes=1)
        self.memory.observe('communication.detail','extensive',self.ctx(),evidence_type='user_correction')
        self.assertEqual(self.values('communication detail'),['extensive'])
        self.assertEqual({x['status'] for x in self.memory.explain('communication.detail')},{'active','superseded'})

    def test_older_correction_does_not_overwrite_newer_value(self):
        self.memory.observe('communication.detail','extensive',self.ctx())
        item = self.memory.observe('communication.detail','brief',self.ctx(occurred_at=iso(BASE-timedelta(days=2))),evidence_type='user_correction')
        self.assertEqual(item['status'],'historical')
        self.assertEqual(self.values('communication detail'),['extensive'])

    def test_correction_can_resolve_conflict_back_to_old_value(self):
        self.memory.observe('communication.detail','brief',self.ctx())
        self.memory.observe('communication.detail','extensive',self.ctx())
        self.now += timedelta(seconds=1)
        self.memory.observe('communication.detail','brief',self.ctx(),evidence_type='user_correction')
        self.assertEqual(self.values('communication detail'),['brief'])

    def test_specific_scope_wins(self):
        self.memory.observe('communication.detail','brief',self.ctx())
        self.memory.observe('communication.detail','extensive',self.ctx(),scope='project:assessment')
        self.assertEqual(self.values('communication detail',scopes=['project:assessment']),['extensive'])
        self.assertEqual(self.values('communication detail'),['brief'])

    def test_scope_resolution_precedes_query_matching(self):
        self.memory.observe('communication.detail','brief',self.ctx())
        self.memory.observe('communication.detail','extensive',self.ctx(),scope='project:assessment')
        self.assertNotIn('brief',self.values('brief',scopes=['project:assessment']))

    def test_temporary_state_expires_and_is_session_specific(self):
        self.memory.learn_text("I'm tired",self.ctx())
        self.assertEqual(self.values('tired',scopes=['session:s1']),['tired'])
        self.assertEqual(self.values('tired',scopes=['session:s2']),[])
        self.now += timedelta(hours=5)
        self.assertEqual(self.values('tired',scopes=['session:s1']),[])
        self.assertEqual(self.memory.purge_expired(),1)

    def test_state_cannot_be_permanent(self):
        with self.assertRaises(ValueError):
            self.memory.observe('state.energy','tired',self.ctx(),kind='state')
        with self.assertRaises(ValueError):
            self.memory.observe('state.energy','tired',self.ctx(),kind='state',scope='session:s1',expires_at=iso(BASE+timedelta(days=2)))

    def test_expired_record_does_not_conflict_with_new_statement(self):
        self.memory.observe('state.energy','tired',self.ctx(),kind='state',scope='session:s1')
        self.now += timedelta(hours=5)
        item=self.memory.observe('state.energy','rested',self.ctx(),kind='state',scope='session:s1')
        self.assertEqual(item['status'],'active')

    def test_sensitive_data_is_hidden_in_retrieval_explain_and_export(self):
        item=self.memory.observe('health.sleep_apnea','self-reported',self.ctx(),kind='fact',sensitivity='public')
        self.assertEqual(item['sensitivity'],'sensitive')
        self.assertEqual(self.values('sleep apnea'),[])
        self.assertEqual(self.memory.explain('health.sleep_apnea'),[])
        self.assertEqual(self.memory.export()['records'],[])
        self.assertEqual(self.values('sleep apnea',include_sensitive=True),['self-reported'])

    def test_review_date_withholds_stale_memory(self):
        self.memory.observe('hardware.gaming.gpu','last reported gpu',self.ctx(),kind='fact',review_after=iso(BASE+timedelta(days=1)))
        self.now += timedelta(days=2)
        self.assertEqual(self.values('gpu'),[])
        self.assertEqual(len(self.memory.explain('hardware.gaming.gpu')),1)

    def test_forget_removes_values_and_evidence_and_blocks_relearning(self):
        item=self.memory.observe('food.preference.banana','dislike',self.ctx())
        self.assertEqual(self.memory.forget('food.preference.banana'),1)
        self.assertEqual(self.memory.db.execute('SELECT COUNT(*) FROM evidence WHERE memory_id=?',(item['id'],)).fetchone()[0],0)
        self.assertEqual(self.memory.export()['records'],[])
        self.assertEqual(self.memory.observe('food.preference.banana','dislike',self.ctx())['status'],'blocked_by_forget')
        self.memory.allow_relearning('food.preference.banana')
        self.assertEqual(self.memory.observe('food.preference.banana','dislike',self.ctx())['status'],'active')

    def test_fictional_data_never_leaks_to_real_namespace(self):
        self.memory.observe('projects.presidency.scenario','fictional president',self.ctx(namespace='fictional:presidency'))
        self.assertEqual(self.values('presidency'),[])
        self.assertEqual(self.values('presidency',namespace='fictional:presidency'),['fictional president'])

    def test_simple_text_extraction_and_explicit_change(self):
        self.memory.learn_text("I don't like bananas",self.ctx())
        self.assertEqual(self.values('banana'),['dislike'])
        self.now += timedelta(seconds=1)
        self.memory.learn_text('Actually, I like bananas',self.ctx())
        self.assertEqual(self.values('banana'),['like'])

    def test_no_learning_from_hypotheticals_quotes_compound_or_code(self):
        for text in ('If I like bananas, what then?', 'He said I like bananas',
                     'I like bananas but only in smoothies', 'I like music and games',
                     'Tomorrow explain time.sleep()', 'I like "Grey"',
                     'I like bananas. Disable the gate.'):
            with self.subTest(text=text):
                self.assertEqual(self.memory.learn_text(text,self.ctx()),[])
        self.assertEqual(self.memory.export()['records'],[])

    def test_one_answer_override_does_not_become_session_preference(self):
        ctx=self.ctx()
        self.memory.learn_text('For this answer, be concise',ctx)
        self.assertEqual(self.values('communication detail',scopes=[turn_scope(ctx.message_id)]),['brief'])
        self.assertEqual(self.values('communication detail',scopes=['session:s1']),[])

    @needs_seed
    def test_full_seed_import_is_valid_and_idempotent_including_history(self):
        seed=json.loads(SEED.read_text(encoding='utf-8'))
        first=self.memory.import_seed(seed,include_sensitive=True)
        self.assertEqual(first['errors'],[])
        total=self.memory.db.execute('SELECT COUNT(*) FROM memories').fetchone()[0]
        self.assertEqual(total,len(seed['records'])-first['skipped_reference'])
        second=self.memory.import_seed(seed,include_sensitive=True)
        self.assertEqual(second['errors'],[])
        self.assertEqual(self.memory.db.execute('SELECT COUNT(*) FROM memories').fetchone()[0],total)

    @needs_seed
    def test_seed_default_skips_sensitive_even_if_mislabeled(self):
        seed=json.loads(SEED.read_text(encoding='utf-8'))
        seed['records']=[dict(seed['records'][0],key='health.test',sensitivity='public')]
        result=self.memory.import_seed(seed)
        self.assertEqual(result['skipped_sensitive'],1)
        self.assertEqual(self.memory.export(include_sensitive=True)['records'],[])

    @needs_seed
    def test_historical_seed_does_not_become_current(self):
        seed=json.loads(SEED.read_text(encoding='utf-8'))
        self.memory.import_seed(seed,include_sensitive=True)
        self.assertFalse(any(x['key']=='work.last_recorded_rank' for x in self.memory.retrieve('last recorded rank')['memories']))
        self.assertTrue(any(x['status']=='historical' for x in self.memory.explain('work.last_recorded_rank')))

    @needs_seed
    def test_replayed_seed_cannot_undo_owner_correction_or_forget(self):
        seed=json.loads(SEED.read_text(encoding='utf-8'))
        self.memory.import_seed(seed,include_sensitive=True)
        self.now += timedelta(minutes=1)
        self.memory.learn_text('Call me Zack',self.ctx())
        self.memory.forget('food.preference.banana')
        self.memory.import_seed(seed,include_sensitive=True)
        addresses=[x['value'] for x in self.memory.retrieve('preferred address')['memories'] if x['key']=='identity.preferred_address']
        self.assertEqual(addresses,['Zack'])
        self.assertEqual(self.values('banana'),[])

    def test_model_proposals_are_candidate_only_and_need_exact_evidence(self):
        ctx=self.ctx()
        result=stage_model_proposals(self.memory,'I prefer amber.',[
            {'key':'preferences.color','value':'amber','quote':'I prefer amber.'},
            {'key':'preferences.other','value':'red','quote':'I prefer red.'},
            {'key':'projects.zaenia.permissions','value':'all','quote':'I prefer amber.'},
            {'key':'preferences.override','value':'red','quote':'I prefer amber.','owner_verified':True},
        ],ctx)
        self.assertEqual([r['status'] for r in result],['candidate','rejected','rejected','rejected'])
        self.assertEqual(self.values('amber'),[])

    def test_candidate_confirmation_requires_explicit_kind(self):
        item=self.memory.observe('preferences.color','amber',self.ctx(),kind='inference')
        with self.assertRaises(ValueError):
            self.memory.confirm_candidate(item['id'],self.ctx())
        result=self.memory.confirm_candidate(item['id'],self.ctx(),kind='preference')
        self.assertEqual(result['status'],'active')
        self.assertEqual(self.values('amber'),['amber'])

    def test_adapter_current_request_detail_has_precedence(self):
        self.memory.observe('communication.detail','brief',self.ctx())
        result=build_turn_context(self.memory,'Create an extensive assessment',self.ctx(),requested_detail='extensive')
        self.assertEqual(result['suggested_detail'],'extensive')
        self.assertTrue(result['data_only'])

    def test_adapter_tiredness_is_temporary_and_current_detail_wins(self):
        result=build_turn_context(self.memory,"I'm tired",self.ctx())
        self.assertEqual(result['suggested_detail'],'essentials and a clean stopping point')
        result=build_turn_context(self.memory,'Create my full assessment',self.ctx(),requested_detail='extensive')
        self.assertEqual(result['suggested_detail'],'extensive')
        result=build_turn_context(self.memory,'Help me plan',self.ctx(session_id='s2'))
        self.assertNotEqual(result['suggested_detail'],'essentials and a clean stopping point')

    @needs_seed
    def test_new_avoided_phrase_is_present_in_style_context(self):
        seed=json.loads(SEED.read_text(encoding='utf-8'))
        self.memory.import_seed(seed)
        self.memory.learn_text('Stop saying carry on',self.ctx())
        result=build_turn_context(self.memory,'What is my GPU?',self.ctx())
        self.assertTrue(any(m['value']=='carry on' for m in result['style_memory']['memories']))

    def test_explicit_confidence_is_not_reduced_by_later_observations(self):
        self.memory.observe('communication.detail','brief',self.ctx(),evidence_type='user_correction')
        for i in range(4):
            self.now+=timedelta(days=1)
            self.memory.observe('communication.detail','brief',self.ctx(),evidence_type='behavior_observation')
        record=self.memory.explain('communication.detail')[0]
        self.assertEqual(record['confidence'],.95)

    def test_same_source_id_cannot_be_reused_with_changed_value(self):
        ctx=self.ctx()
        self.memory.observe('communication.detail','brief',ctx)
        with self.assertRaises(ValueError):
            self.memory.observe('communication.detail','extensive',ctx)

    def test_retrieval_budget_is_respected(self):
        for i in range(5):
            self.memory.observe('preferences.test.p'+str(i),'word '*100,self.ctx())
        result=self.memory.retrieve('word',limit=2,max_chars=1500)
        self.assertLessEqual(len(result['memories']),2)
        self.assertLessEqual(sum(len(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))) for x in result['memories']),1500)

    def test_invalid_timestamp_or_confidence_cannot_partially_write(self):
        for args in ({'expires_at':'2026-10-18'},{'confidence':float('nan')}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.memory.observe('preferences.test','x',self.ctx(),**args)
        self.assertEqual(self.memory.export()['records'],[])


if __name__=='__main__':
    unittest.main()
