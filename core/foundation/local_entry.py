"""Trusted local entry-point adapters; never expose callbacks or grants to a model."""
from functools import wraps
import inspect
import json
from pathlib import Path
from typing import get_args
from core.foundation.auth.passkey import require_passkey
from core.foundation.rules.engine import RuleEngine
from core.foundation.rules.models import ActionRequest


def json_parameters(params):
    if not isinstance(params,dict): raise ValueError('Expected an argument mapping.')
    encoded=json.dumps(params,sort_keys=True,allow_nan=False,ensure_ascii=False)
    if len(encoded.encode('utf-8'))>65536: raise ValueError('Arguments exceed the size limit.')
    return json.loads(encoded)


def owner_execute(operation,params,handler,validator=json_parameters):
    """Trusted application code only. No model can choose or supply handler code."""
    engine=RuleEngine.open(require_passkey())
    try:
        engine.register(operation,handler,validator)
        request=engine.prepare(ActionRequest(operation,json_parameters(params)))
        decision=engine.evaluate(request)
        grant=None
        if decision.requires_reauth:
            print('Review exact action:',request.operation)
            print(json.dumps(request.params,indent=2,ensure_ascii=False))
            grant=engine.session.reauthenticate(request.operation,request.params)
        return engine.execute(request,grant=grant)
    finally:
        engine.close()


def owner_command(operation):
    """Guard a synchronous JSON-argument CLI function without changing its signature."""
    def decorate(function):
        if inspect.isgeneratorfunction(function) or inspect.iscoroutinefunction(function):
            raise TypeError('Use a lifecycle-aware adapter for asynchronous handlers.')
        signature=inspect.signature(function,eval_str=True)
        path_fields={name for name,param in signature.parameters.items() if param.annotation is Path or Path in get_args(param.annotation)}
        @wraps(function)
        def guarded(*args,**kwargs):
            bound=signature.bind(*args,**kwargs)
            bound.apply_defaults()
            params=json_parameters({name:str(value) if isinstance(value,Path) and name in path_fields else value for name,value in bound.arguments.items()})
            def validator(p):
                clean=json_parameters(p)
                signature.bind(**clean)
                return clean
            def call(p):
                values={name:Path(value) if name in path_fields and value is not None else value for name,value in p.items()}
                return function(**values)
            return owner_execute(operation,params,call,validator)
        guarded.__signature__=signature
        return guarded
    return decorate
