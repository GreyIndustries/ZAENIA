"""Daily status fixtures: no owner calendar, Google, model or microphone use."""
from contextlib import ExitStack
from datetime import date,datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.calendar_context import duty_status as duty
from core.calendar_context import calendar_context as calendar


class DutyTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(TemporaryDirectory(prefix='zae-duty-test-',dir=Path(__file__).resolve().parents[2])))
        self.path=self.root/'private/overrides.json'
        self.stack.enter_context(patch.object(duty,'DUTY_FILE',self.path))
        self.stack.enter_context(patch.object(duty,'protect_storage',side_effect=lambda path:path.mkdir(parents=True,exist_ok=True)))

    def test_all_four_choices_persist_and_reset_restores_calendar(self):
        for revision,status in enumerate(duty.LABELS):
            result=duty.set_day('2026-10-18',status,revision)
            self.assertEqual(duty.read_overrides()['days']['2026-10-18'],status)
            self.assertEqual(result['label'],duty.LABELS[status])
        duty.set_day('2026-10-18',None,4)
        self.assertEqual(duty.read_overrides()['days'],{})
        self.assertEqual(duty.read_overrides()['revision'],5)

    def test_stale_edit_is_refused_without_losing_saved_choice(self):
        duty.set_day('2026-10-18','leave',0)
        with self.assertRaises(duty.DutyStatusConflict):duty.set_day('2026-10-18','on_duty',0)
        self.assertEqual(duty.read_overrides()['days']['2026-10-18'],'leave')

    def test_invalid_dates_statuses_and_revision_do_not_write(self):
        for day,status,revision in [('2026-02-30','leave',0),('20261018','leave',0),('2026-10-18','deployment',0),('2026-10-18','leave',True)]:
            with self.subTest(day=day,status=status,revision=revision),self.assertRaises(duty.DutyStatusError):duty.set_day(day,status,revision)
        self.assertFalse(self.path.exists())

    def test_corrupt_data_never_silently_becomes_a_default_schedule(self):
        self.path.parent.mkdir();self.path.write_text('{broken')
        with self.assertRaises(duty.DutyStatusError):duty.read_overrides()

    def test_owner_selection_takes_precedence_over_special_dates_and_inferred_events(self):
        config={'calendar_context':{'enabled':True},'special_dates':{'2026-10-18':{'status':'on_duty'}},
                'default_schedule':{'Sunday':'on_duty'},'events':[{'date':'2026-10-18','title':'Staff duty','all_day':True}]}
        duty.set_day('2026-10-18','class',0)
        config=duty.apply_overrides(config)
        self.assertEqual(calendar.get_status_for_date(config,date(2026,10,18))['status'],'class')
        with patch.object(calendar,'load_calendar_config',return_value=config),patch.object(calendar,'get_events_for_date',return_value=config['events']):
            context=calendar.build_calendar_context(date(2026,10,18))
        self.assertEqual(context['work_context']['type'],'all_day_class')
        self.assertTrue(context['work_context']['normal_work_schedule_suppressed'])
        self.assertEqual(context['status_source'],'owner_override')
        self.assertEqual(len(context['events']),1)

    def test_calendar_context_uses_schedule_after_reset(self):
        config={'default_schedule':{'Sunday':'on_duty'}}
        duty.set_day('2026-10-18','off_duty',0);duty.set_day('2026-10-18',None,1)
        self.assertEqual(calendar.get_status_for_date(duty.apply_overrides(config),date(2026,10,18))['status'],'on_duty')

    def test_brain_context_reads_owner_status_only_with_calendar_permission(self):
        from core.brain.brain_service import BrainService
        day=datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
        duty.set_day(day,'leave',0)
        with patch.object(BrainService,'_read_json_file',return_value={}),patch('core.assistant_platform.service.existing_platform',return_value=None),patch('core.personal_memory.memory_context',return_value=None):
            allowed=BrainService(memory_authorizer=lambda operation:True).load_conversation_context('Help me plan today.')
            denied=BrainService(memory_authorizer=lambda operation:False).load_conversation_context('Help me plan today.')
        self.assertIn('On leave',allowed)
        self.assertIn(day,allowed)
        self.assertIsNone(denied)

    def client(self,allowed):
        from fastapi.testclient import TestClient
        from core.api.server import create_app
        class Gate:
            def authorize(self,operation):return operation in allowed
        client=self.stack.enter_context(TestClient(create_app(token_verifier=lambda token:token=='isolated-duty-token',client_gate=Gate(),include_carplay=False,include_phone_app=False)))
        client.headers['X-ZAENIA-API-TOKEN']='isolated-duty-token'
        self.stack.enter_context(patch('core.api.ui_routes.audit'))
        return client

    def test_edit_api_requires_token_and_calendar_write(self):
        client=self.client({'calendar.read'})
        body={'date':'2026-10-18','status':'off_duty','revision':0}
        self.assertEqual(client.put('/api/calendar/duty-status',json=body).status_code,403)
        self.assertEqual(client.put('/api/calendar/duty-status',json=body,headers={'X-ZAENIA-API-TOKEN':'wrong'}).status_code,401)
        self.assertFalse(self.path.exists())

    def test_edit_api_validates_and_conflicts(self):
        client=self.client({'ui.calendar.write'})
        body={'date':'2026-10-18','status':'leave','revision':0}
        response=client.put('/api/calendar/duty-status',json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['label'],'On leave')
        self.assertEqual(client.put('/api/calendar/duty-status',json=body).status_code,409)
        self.assertEqual(client.put('/api/calendar/duty-status',json={**body,'status':'unknown','revision':1}).status_code,422)
        self.assertEqual(client.put('/api/calendar/duty-status',json={**body,'revision':1,'extra':'not accepted'}).status_code,422)

    def test_calendar_reply_contains_editable_selection_and_effective_label(self):
        from core.api import ui_calendar
        duty.set_day('2026-10-18','off_duty',0)
        config=duty.apply_overrides({'default_schedule':{'Sunday':'on_duty'}})
        with patch.object(calendar,'load_calendar_config',return_value=config),patch.object(calendar,'get_events_for_date',return_value=[]),patch.object(ui_calendar,'_google_events',return_value=(None,'Fixture; Google disabled.')),patch.object(ui_calendar,'scheduling_db',return_value=self.root/'calendar.sqlite3'),patch('core.google_calendar_sync.google_calendar_api.status',return_value={'connected':False}):
            reply=ui_calendar.read_calendar(date(2026,10,18),1)
        self.assertEqual(reply['dutyOverrides'],{'2026-10-18':'off_duty'})
        self.assertEqual(reply['dutyRevision'],1)
        self.assertEqual(reply['dayStatus']['2026-10-18'],'Off duty / DONSA')

    def test_duty_question_uses_fresh_calendar_status(self):
        from core.assistant_platform.live_answers import resolve,topic_for
        answer=resolve('Am I on duty tomorrow?',lambda operation:True,now=datetime(2026,10,18,12,tzinfo=ZoneInfo('America/Los_Angeles')),
                       loaders={'calendar':lambda start,days:{'events':[],'dayStatus':{'2026-10-19':'School / class'}}})
        self.assertIn('School / class',answer['answer'])
        self.assertTrue(answer['verification']['available'])
        self.assertIsNone(topic_for('Change my duty status to on leave.'))


if __name__=='__main__':unittest.main()
