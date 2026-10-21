"""Console integration checks against real isolated foundation policies."""
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import os
import subprocess
import sys
import tempfile

def run():
    with tempfile.TemporaryDirectory(prefix='zaenia-console-check-') as folder:
        env=dict(os.environ,ZAENIA_FOUNDATION_DATA_DIR=folder,PYTHONIOENCODING='utf-8')
        return subprocess.run([sys.executable,'-m','core.foundation.integration_check','--worker'],env=env).returncode==0

def worker():
    from unittest.mock import patch
    from types import SimpleNamespace
    from core.foundation.auth.passkey import create_passkey,authenticate_passphrase
    from core.foundation.rules.vault import create_default_vault,add_rule
    from core.foundation.rules.models import create_rule,ActionRequest
    from core.foundation.moral_code.vault import create_policy,DEFAULT_CHARTER_SHA256
    from core.foundation.rules.engine import RuleEngine
    from core.foundation.console_gate import launch_request,register_launchers,ConsoleGate
    from core.foundation.storage.paths import AUDIT_FILE
    phrase='isolated console integration credential 2026'
    count=0
    def check(value):
        nonlocal count
        assert value
        count+=1
    def raises(kind,fn):
        try: fn()
        except kind: check(True)
        else: raise AssertionError('Expected '+kind.__name__)
    create_passkey(phrase,phrase)
    create_default_vault(authenticate_passphrase(phrase,operation='rules.create'))
    create_policy(authenticate_passphrase(phrase,operation='moral.create',payload={'charter_sha256':DEFAULT_CHARTER_SHA256}))
    calls=[]
    def runner(argv,**kwargs):
        calls.append((argv,kwargs));return SimpleNamespace(returncode=0)
    engine=RuleEngine.open(authenticate_passphrase(phrase))
    register_launchers(engine,runner)
    raises(PermissionError,lambda:launch_request('os',['shell']))
    raises(PermissionError,lambda:launch_request('core.weather.weather_main',['now',';powershell']))
    raises(ValueError,lambda:launch_request('core.weather.weather_main',[{}]))
    request=launch_request('core.weather.weather_main',['now'])
    check(engine.execute(request)==0)
    check(len(calls)==1 and calls[0][0][1:]==['-m','core.weather.weather_main','now'])
    check('shell' not in calls[0][1])
    request=launch_request('core.google_calendar_sync.google_calendar_sync_main',['sync','--days','2'])
    raises(PermissionError,lambda:engine.execute(request))
    check(len(calls)==1)
    grant=engine.session.reauthenticate(request.operation,request.params,phrase)
    check(engine.execute(request,grant=grant)==0)
    raises(PermissionError,lambda:engine.execute(request,grant=grant))
    raises(PermissionError,lambda:engine.execute(ActionRequest('weather.read',request.params)))
    engine.close()
    raises(PermissionError,lambda:engine.execute(launch_request('core.weather.weather_main',['now'])))
    denial=create_rule('Console fixture deny','Owner scope check','soft','deny',operations=('weather.read',))
    add_rule(denial,authenticate_passphrase(phrase,operation='rules.add',payload=denial.to_dict()))
    engine=RuleEngine.open(authenticate_passphrase(phrase));register_launchers(engine,runner)
    raises(PermissionError,lambda:engine.execute(launch_request('core.weather.weather_main',['now'])))
    engine.close()
    from core.console import zaenia_console as console
    raises(PermissionError,lambda:console.run_powershell('anything'))
    console.log_command(phrase)
    check(phrase not in AUDIT_FILE.read_text())
    # Verify legacy sync is routed to the authenticated writer without importing
    # network/parser dependencies or fetching a private calendar.
    import ast
    sync_path=Path(__file__).resolve().parents[1]/'google_calendar_sync/google_calendar_ics.py'
    tree=ast.parse(sync_path.read_text(encoding='utf-8'))
    body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='save_local_calendar_config')
    imports=[n for n in ast.walk(body) if isinstance(n,ast.ImportFrom)]
    check(any(n.module=='core.calendar_context.calendar_update_main' for n in imports))
    print(f'PASS: {count} console integration checks. No commands or messages executed.')

if __name__=='__main__':
    if '--worker' in sys.argv: worker()
    else: raise SystemExit(0 if run() else 1)
