"""Briefing completion uses isolated state and fake audio; no owner services."""
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from zoneinfo import ZoneInfo

from core.calendar_context.completion import CalendarCompletion,occurrence
from core.assistant_platform.store import PlatformStore
from core.carplay_trigger.briefing_session import BriefingSessions


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix='zae-platform-test-',dir=Path(__file__).resolve().parents[2]);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.now=datetime(2026,10,24,12,tzinfo=ZoneInfo('America/Los_Angeles'))
        self.event={'title':'Fixture appointment','google_uid':'fixture-recurring','date':'2026-10-24','time':'09:00','end_time':'10:00','source':'google'}
        self.context={'date':'2026-10-24','events':[self.event]}
        self.patch=patch('core.assistant_platform.store.protect_storage');self.patch.start();self.addCleanup(self.patch.stop)
        self.completion=CalendarCompletion(PlatformStore(self.root/'state.sqlite3'))

    def service(self):return BriefingSessions(self.root/'brief',clock=lambda:self.now,completion=self.completion)

    def brief(self,callback):
        raw={'calendar_context':self.context,'weather_summary':'Fixture weather','traffic_result':{'success':True},'traffic_summary':'Fixture traffic'}
        with patch('core.carplay_trigger.briefing_session.build_fresh_briefing',return_value=({'success':True},raw)),patch('core.carplay_trigger.briefing_session.generate_piper_audio',side_effect=lambda text,path:path.write_bytes(b'fixture')):return callback()

    def test_completed_occurrence_stays_quiet_across_restarts_but_next_recurrence_does_not(self):
        service=self.service();first=self.brief(lambda:service.start('first',force_full=True))
        self.assertTrue(first['needs_answer']);self.assertEqual(first['question_type'],'calendar_completion')
        self.assertIn('Has Fixture appointment been completed?',first['briefing_text'])
        answer=self.brief(lambda:service.start(parent_id=first['session_id'],answer='I finished it'))
        self.assertIn('Marked complete.',answer['briefing_text']);self.assertFalse(answer['needs_answer'])
        # Playback can arrive after the completion answer.
        service.played(first['session_id'])
        repeated=self.brief(lambda:self.service().start('again',force_full=True))
        self.assertNotIn('Fixture appointment',repeated['briefing_text']);self.assertFalse(repeated['needs_answer'])
        self.now+=timedelta(days=7);self.event['date']=self.now.date().isoformat();self.context['date']=self.event['date']
        recurring=self.brief(lambda:self.service().start('next-week',force_full=True))
        self.assertTrue(recurring['needs_answer'])

    def test_waits_for_end_skips_unknown_times_all_day_and_future(self):
        for changes in ({'end_time':'14:00'},{'time':'unknown'},{'all_day':True},{'time':'14:00','end_time':'15:00'}):
            with self.subTest(changes=changes):self.assertIsNone(self.completion.due({'events':[{**self.event,**changes}]},self.now))
        self.assertIsNotNone(self.completion.due(self.context,self.now))

    def test_unplayed_audio_does_not_consume_question_and_not_yet_has_cooldown(self):
        service=self.service();first=self.brief(lambda:service.start('first',force_full=True))
        again=self.brief(lambda:service.start('unplayed',force_full=True));self.assertTrue(again['needs_answer'])
        service.played(first['session_id'])
        answer=self.brief(lambda:service.start(parent_id=first['session_id'],answer='not completed yet'))
        self.assertIn("leave it unfinished",answer['briefing_text'])
        self.assertFalse(self.brief(lambda:service.start('quiet',force_full=True))['needs_answer'])
        key=occurrence(self.event,'2026-10-24')[0];self.assertFalse(self.completion.store.get('calendar_completion',key)['completed'])

    def test_answer_retries_are_idempotent_and_unknown_never_means_complete(self):
        service=self.service();first=self.brief(lambda:service.start('first',force_full=True))
        answer=self.brief(lambda:service.start(parent_id=first['session_id'],answer='perhaps'))
        repeated=self.brief(lambda:service.start(parent_id=first['session_id'],answer='yes'))
        self.assertEqual(answer,repeated)
        key=occurrence(self.event,'2026-10-24')[0]
        self.assertIsNone(self.completion.store.get('calendar_completion',key))

    def test_off_duty_and_evening_departure_logic_do_not_interpret_event_answer(self):
        self.now=self.now.replace(hour=16,minute=40)
        service=self.service();first=self.brief(lambda:service.start('first',force_full=True))
        self.brief(lambda:service.start(parent_id=first['session_id'],answer='yes'))
        with service.connect() as db:
            import json
            row=db.execute('SELECT payload FROM sessions ORDER BY rowid DESC LIMIT 1').fetchone()
            self.assertNotIn('evening',json.loads(row[0])['slots'])

    def test_overnight_and_previous_day_occurrences_are_checked_after_their_end(self):
        event={**self.event,'date':'2026-10-23','time':'23:00','end_time':'01:00'}
        self.now=self.now.replace(hour=0,minute=30)
        self.assertIsNone(self.completion.due({'events':[event]},self.now))
        self.now=self.now.replace(hour=2)
        self.assertIsNotNone(self.completion.due({'events':[event]},self.now))

    def test_live_brief_fetch_includes_yesterday_without_putting_it_in_upcoming_schedule(self):
        from contextlib import nullcontext
        from core.carplay_trigger.briefing_session import build_fresh_briefing
        previous={'date':'2026-10-23','events':[{**self.event,'date':'2026-10-23'}]}
        raw={'calendar_context':self.context}
        with patch('core.carplay_trigger.briefing_session.get_google_events_between',return_value=[]) as fetch,patch('core.carplay_trigger.briefing_session.google_events_overlay',return_value=nullcontext()),patch('core.carplay_trigger.briefing_session.build_drive_briefing',return_value=raw),patch('core.calendar_context.calendar_context.build_calendar_context',return_value=previous):
            _,result=build_fresh_briefing(self.now.date())
        self.assertEqual(fetch.call_args.kwargs,{'start_date':self.now.date()-timedelta(days=1),'days':3})
        self.assertEqual(len(result['calendar_context']['events']),1)
        self.assertEqual(len(result['completion_context']['events']),2)


if __name__=='__main__':unittest.main()
