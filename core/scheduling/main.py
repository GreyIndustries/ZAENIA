from datetime import datetime,timezone
from pathlib import Path
import argparse
import json
import threading
from core.scheduling.service import Store, register, validate_event
from core.scheduling.parser import propose
from core.scheduling.notifications import send
from core.foundation.rules.engine import RuleEngine
from core.foundation.rules.models import ActionRequest
from core.foundation.auth.passkey import require_passkey

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser(description='ZÆNIA guarded calendar and notifications')
    commands = parser.add_subparsers(dest='command',required=True)
    preview = commands.add_parser('preview'); preview.add_argument('text')
    add = commands.add_parser('add'); add.add_argument('text'); add.add_argument('--channels',nargs='+',default=['console'])
    put = commands.add_parser('put'); put.add_argument('json_file',type=Path)
    delete = commands.add_parser('delete'); delete.add_argument('id')
    commands.add_parser('list'); commands.add_parser('worker'); commands.add_parser('self-test')
    args = parser.parse_args()
    if args.command == 'self-test':
        from core.scheduling.self_test import run
        run(); return
    if args.command == 'preview':
        print(json.dumps(propose(args.text),indent=2)); return
    store = Store(ROOT/'data'/'scheduling'/'calendar.sqlite3')
    engine = RuleEngine.open(require_passkey())
    register(engine,store)
    try:
        if args.command == 'worker':
            # Owner startup approval; enforce calendar.read policy before each cycle.
            # Session expires: worker pauses and prompts locally for reauthentication.
            while True:
                if not engine.session.is_valid():
                    engine.close()
                    engine = RuleEngine.open(require_passkey())
                    register(engine,store)
                engine.execute(ActionRequest('calendar.read'))
                store.tick(datetime.now(timezone.utc),send)
                threading.Event().wait(5)
        elif args.command == 'list':
            print(json.dumps(engine.execute(ActionRequest('calendar.read')),indent=2))
        else:
            op = 'calendar.delete' if args.command == 'delete' else 'calendar.write'
            if args.command == 'delete': params = {'id':args.id}
            elif args.command == 'put': params = validate_event(json.loads(args.json_file.read_text(encoding='utf-8')))
            else:
                result = propose(args.text)
                if result['needs_clarification']: raise ValueError(result['reason'])
                params = result['proposal']; params['channels'] = args.channels
            request = engine.prepare(ActionRequest(op,params))
            print('Review exact action:'); print(json.dumps(request.params,indent=2))
            grant = engine.session.reauthenticate(op,request.params)
            print(json.dumps(engine.execute(request,grant=grant),indent=2))
    finally: engine.close()

if __name__=='__main__':
    main()
