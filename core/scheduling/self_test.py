"""Isolated confirmation suite. No live messages or owner files are touched."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def run():
    with tempfile.TemporaryDirectory(prefix='zaenia-module2-') as folder:
        env = dict(os.environ,ZAENIA_FOUNDATION_DATA_DIR=folder)
        subprocess.run([sys.executable,'-m','core.scheduling.self_test','--child',folder],env=env,check=True)

def child(folder):
    from datetime import datetime,timedelta,time,date
    from unittest.mock import patch
    from core.scheduling.service import Store,TZ,UTC,wall,validate_event,register
    from core.scheduling.parser import propose
    from core.foundation.auth.passkey import create_passkey
    from core.foundation.auth.session import AuthSession
    from core.foundation.rules.models import ActionRequest
    from core.foundation.rules.engine import RuleEngine
    from core.foundation.rules.vault import CANONICAL_HARD
    from core.foundation.storage.paths import VAULT_FILE,MORAL_VAULT_FILE
    checks = 0
    def check(value):
        nonlocal checks
        if not value: raise AssertionError('Module 2 assertion failed.')
        checks += 1
    def raises(kind,fn):
        try: fn()
        except kind: check(True)
        else: raise AssertionError('Expected '+kind.__name__)
    now = datetime(2026,10,12,12,tzinfo=TZ)
    result = propose('Remind me to bring the radio tomorrow at 7 PM',now)
    check(result['proposal']['title']=='bring the radio')
    check(result['proposal']['start'].startswith('2026-10-13T19:00'))
    check(propose('remind me to eat tomorrow at 7',now)['needs_clarification'])
    check(propose('remind me to eat today at 7 AM',now)['needs_clarification'])
    raises(ValueError,lambda:wall(date(2026,3,8),time(2,30)))
    raises(ValueError,lambda:wall(date(2026,11,1),time(1,30)))
    raises(ValueError,lambda:validate_event({'title':'test','start':'2026-10-13T19:00'}))
    raises(ValueError,lambda:validate_event({'title':'test','start':now.isoformat(),'channels':['unknown']}))
    db = Path(folder)/'calendar.sqlite3'
    store=Store(db)
    start=now+timedelta(hours=2)
    event=validate_event({'id':'radio','title':'Radio','start':start.isoformat()})
    store.put(event)
    check(Store(db).events()==[event])
    sent=[]
    check(store.tick(start-timedelta(hours=1),sent.append)==1)
    check(Store(db).tick(start-timedelta(hours=1),sent.append)==0)
    check(store.tick(start-timedelta(minutes=15),sent.append)==1)
    check(store.tick(start,sent.append)==1)
    check([b['minutes'] for b in sent]==[60,15,0])
    check(len({b['delivery_id'] for b in sent})==3)
    event['id']='retry';store.put(event)
    def fail(body): raise OSError('simulated offline')
    check(store.tick(start-timedelta(hours=1),fail)==0)
    check(Store(db).tick(start-timedelta(hours=1)+timedelta(seconds=31),sent.append)==1)
    event['id']='cancel';store.put(event);store.materialize(now)
    store.delete({'id':'cancel'})
    store.tick(start,sent.append)
    check(not any(b['event_id']=='cancel' for b in sent))
    event['id']='edit';store.put(event);store.materialize(now)
    event['start']=(start+timedelta(days=1)).isoformat();store.put(event)
    store.tick(start,sent.append)
    check(not any(b['event_id']=='edit' for b in sent))
    daily=validate_event({'id':'daily','title':'Daily','start':'2026-10-31T09:00:00-07:00','recurrence':'daily'})
    occurrences=list(store.occurrences(daily,datetime(2026,10,31,tzinfo=UTC),datetime(2026,11,3,tzinfo=UTC)))
    check(len(occurrences)==3)
    check(all(d.astimezone(TZ).hour==9 for d in occurrences))
    check((occurrences[1]-occurrences[0]).total_seconds()==25*3600)
    # Real passkey, session, and exact-action grants. Moral charter uses a test fixture;
    # installed Module 1's separate verification checks its protected real charter.
    password='isolated test password only 2026'
    create_passkey(password,password)
    VAULT_FILE.write_bytes(b'fixture rule generation')
    MORAL_VAULT_FILE.write_bytes(b'fixture moral generation')
    session=AuthSession();session.mark_authenticated(password)
    vault={'version':2,'rules':list(CANONICAL_HARD.values())}
    with patch('core.foundation.moral_code.vault.default_charter',return_value={}):
        engine=RuleEngine(session,vault,{'version':1,'charter':{},'notes':[]})
        register(engine,store)
        request=engine.prepare(ActionRequest('calendar.write',{'title':'Guarded','start':start.isoformat()}))
        raises(PermissionError,lambda:engine.execute(request))
        grant=session.reauthenticate(request.operation,request.params,password)
        changed=ActionRequest(request.operation,{**request.params,'title':'Changed'})
        raises(PermissionError,lambda:engine.execute(changed,grant=grant))
        check(engine.execute(request,grant=grant)['title']=='Guarded')
        raises(PermissionError,lambda:engine.execute(request,grant=grant))
        session.logout()
        raises(PermissionError,lambda:engine.execute(ActionRequest('calendar.read')))
    from core.reminders.reminder_engine import execute_reminder_proposal,save_reminders
    raises(PermissionError,lambda:execute_reminder_proposal({'title':'bypass'},authorized=True))
    raises(PermissionError,lambda:save_reminders({}))
    print(f'PASS: {checks} checks — parsing, Pacific DST, recurrence, persistence, alerts, retries, cancellation, edits, and exact-action authentication. No live notifications sent.')

if __name__=='__main__':
    if '--child' in sys.argv: child(sys.argv[-1])
    else: run()
