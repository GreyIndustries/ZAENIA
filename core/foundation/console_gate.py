"""Fixed console registry: no model text, YAML alias, or caller creates capabilities."""
from __future__ import annotations
from pathlib import Path
from types import MappingProxyType
import subprocess
import sys
from core.foundation.auth.passkey import require_passkey
from core.foundation.rules.engine import RuleEngine
from core.foundation.rules.models import ActionRequest

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = MappingProxyType({
    ('core.briefing.drive_briefing_main',('now',)):'briefing.generate',
    ('core.briefing.drive_briefing_main',('now','--say')):'briefing.generate',
    ('core.briefing.drive_briefing_main',('now','--force-traffic')):'briefing.generate',
    ('core.weather.weather_main',('now',)):'weather.read',
    ('core.weather.weather_main',('now','--say')):'weather.read',
    ('core.traffic.traffic_main',('now','--force')):'traffic.read',
    ('core.calendar_context.calendar_context_main',('today',)):'calendar.read',
    ('core.google_calendar_sync.google_calendar_sync_main',('sync','--days','2')):'calendar.write',
    ('core.carplay_audio.carplay_audio_main',('generate',)):'briefing.generate',
    ('core.carplay_audio.carplay_audio_main',('generate','--force-traffic')):'briefing.generate',
})

def validate_launch(params):
    if not isinstance(params,dict) or set(params)!={'module','args'}:
        raise ValueError('Invalid console launch parameters.')
    module,args=params['module'],params['args']
    if not isinstance(module,str) or not isinstance(args,list) or any(not isinstance(a,str) for a in args):
        raise ValueError('Invalid module or arguments.')
    if (module,tuple(args)) not in COMMANDS:
        raise PermissionError('Console command is not registered.')
    return {'module':module,'args':list(args)}

def launch_request(module,args=None):
    params=validate_launch({'module':module,'args':list(args or [])})
    return ActionRequest(COMMANDS[(params['module'],tuple(params['args']))],params)

def register_launchers(engine,runner=None):
    active_runner=runner or subprocess.run
    for operation in sorted(set(COMMANDS.values())):
        def validator(params,operation=operation):
            valid=validate_launch(params)
            if COMMANDS[(valid['module'],tuple(valid['args']))]!=operation:
                raise PermissionError('Command does not match the registered operation.')
            return valid
        def execute(params):
            result=active_runner([sys.executable,'-m',params['module'],*params['args']],cwd=str(ROOT),text=True)
            return result.returncode
        engine.register(operation,execute,validator)

class ConsoleGate:
    """Only trusted local host holds the engine. Calls require a live owner session."""
    def __init__(self):
        self.engine=None
    def require_owner(self):
        if self.engine is not None and self.engine.session.is_valid():
            return self.engine
        if self.engine is not None: self.engine.close()
        self.engine=RuleEngine.open(require_passkey())
        register_launchers(self.engine)
        return self.engine
    def run(self,module,args=None):
        request=launch_request(module,args)
        engine=self.require_owner()
        request=engine.prepare(request)
        decision=engine.evaluate(request)
        grant=None
        if decision.requires_reauth:
            print('Review command:',request.operation,request.params)
            grant=engine.session.reauthenticate(request.operation,request.params)
        return engine.execute(request,grant=grant)
    def close(self):
        if self.engine is not None: self.engine.close()
        self.engine=None

console_gate=ConsoleGate()
