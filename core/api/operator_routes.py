"""Controls integrated with the existing API gate and paired desktop approval."""
from datetime import datetime
from typing import Any,Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,Query
from pydantic import BaseModel,ConfigDict,Field

class Body(BaseModel):
    model_config=ConfigDict(extra='forbid')
class Mission(Body):
    title:str=Field(min_length=1,max_length=160)
    steps:list[dict[str,Any]]=Field(min_length=1,max_length=20)
    priority:bool=False
class Draft(Body):
    title:str=Field(min_length=1,max_length=160)
    goal:str=Field(min_length=1,max_length=4000)
    priority:bool=False
class Start(Body):
    revision:int=Field(ge=1)
    planHash:str=Field(pattern=r'^[a-f0-9]{64}$')
class Resolve(Body):
    revision:int=Field(ge=1)
    step:int=Field(ge=0,le=19)
    decision:Literal['retry','accept']
class Root(Body):
    name:str=Field(min_length=1,max_length=100)
    path:str=Field(min_length=1,max_length=1000)
class Continuity(Body):
    kind:Literal['goal','person','project','decision','preference','commitment']
    title:str=Field(min_length=1,max_length=120)
    detail:str=Field(default='',max_length=800)
    status:Literal['active','resolved','superseded']='active'
    links:list[str]=Field(default_factory=list,max_length=20)
    source:str=Field(default='Owner entry',max_length=500)
    revision:int|None=Field(default=None,ge=1)
class Handoff(Body):
    device:Literal['pc','phone','car']
    missionId:str|None=Field(default=None,max_length=100)
    summary:str=Field(min_length=1,max_length=1500)
    nextStep:str=Field(min_length=1,max_length=1000)
    revision:int=Field(ge=0)
class Dismiss(Body):
    key:str=Field(min_length=1,max_length=400)
class Grant(Body):
    handle:int=Field(gt=0)
class Inspect(Body):
    grantId:str=Field(min_length=1,max_length=100)
    question:str=Field(default='Describe this window and the current task context.',min_length=1,max_length=1500)


def create_operator_router(get,authorize,desktop,call):
    router=APIRouter(prefix='/api/platform/operator',tags=['operator'])
    def operator(): return get().operator
    def allowed(op):
        if authorize(op) is False: raise PermissionError('Permission denied: '+op)
    def suggestions():
        from core.assistant_followthrough.service import local_calendar_snapshot,local_task_snapshot
        from core.calendar_context.duty_status import read_overrides
        tasks=[]; events=[]; status=None; unavailable=[]
        try:
            allowed('calendar.read'); events=local_calendar_snapshot()
            status=read_overrides()['days'].get(datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat())
        except Exception: unavailable.append('Calendar or selected daily status unavailable; no calendar-based suggestions inferred.')
        try: allowed('tasks.read'); tasks=local_task_snapshot()
        except Exception: unavailable.append('Task deadlines unavailable; no overdue suggestions inferred.')
        return {'items':operator().suggestions(tasks=tasks,events=events,duty=status),'unavailable':unavailable}

    @router.get('/summary')
    def summary():
        allowed('memory.read'); allowed('files.read')
        from core.assistant_operator.tools import catalog
        service=operator(); missions=service.reconcile(compact=True)
        compact=[]
        for mission in missions:
            compact.append({**mission,'steps':[{**s,'result':{k:v for k,v in s['result'].items() if k in {'verified','path','sha256','bytes','verification'}}} if 'result' in s else s for s in mission['steps']]})
        proposed=call(suggestions)
        return {'missions':compact,'catalog':catalog(),'roots':service.store.list('operator_root'),
            'continuity':service.store.list('continuity'),'handoff':service.store.get('handoff','active'),
            'suggestions':proposed['items'],'suggestionNotices':proposed['unavailable'],'recovery':service.recovery()}

    @router.get('/missions/{identifier}')
    def mission(identifier:str):
        allowed('files.read'); return operator().store.get('mission',identifier)

    @router.post('/missions')
    def create(body:Mission): return call(lambda:operator().create(body.title,body.steps,priority=body.priority))

    @router.post('/draft')
    def draft(body:Draft): return call(lambda:operator().draft(body.title,body.goal,authorize,priority=body.priority))

    @router.post('/missions/{identifier}/start',dependencies=[Depends(desktop)])
    def start(identifier:str,body:Start,key=Depends(desktop)):
        def execution_authorize(operation):
            desktop(key) # Revoking desktop pairing also stops subsequent steps.
            return authorize(operation)
        return call(lambda:operator().start(identifier,body.revision,body.planHash,execution_authorize))

    @router.post('/missions/{identifier}/cancel')
    def cancel(identifier:str): return call(lambda:operator().cancel(identifier))

    @router.post('/missions/{identifier}/resolve',dependencies=[Depends(desktop)])
    def resolve(identifier:str,body:Resolve): return call(lambda:operator().resolve(identifier,body.revision,body.step,body.decision))

    @router.post('/roots',dependencies=[Depends(desktop)])
    def root(body:Root):
        from core.assistant_platform.documents import register_root
        return call(lambda:operator().store.put('operator_root',register_root(body.model_dump())))

    @router.delete('/roots/{identifier}',dependencies=[Depends(desktop)])
    def revoke(identifier:str): return {'revoked':operator().store.delete('operator_root',identifier)}

    @router.post('/continuity')
    def remember(body:Continuity):
        allowed('memory.write')
        return call(lambda:operator().continuity(body.model_dump(exclude={'revision'})))

    @router.patch('/continuity/{identifier}')
    def update(identifier:str,body:Continuity):
        allowed('memory.write')
        return call(lambda:operator().continuity(body.model_dump(exclude={'revision'}),identifier,body.revision))

    @router.delete('/continuity/{identifier}')
    def forget(identifier:str,revision:int=Query(ge=1)):
        allowed('memory.write')
        return call(lambda:{'removed':operator().store.delete('continuity',identifier,revision=revision)})

    @router.put('/handoff')
    def handoff(body:Handoff):
        return call(lambda:operator().handoff(body.model_dump(exclude={'revision'}),body.revision))

    @router.get('/handoff')
    def active():
        service=operator(); row=service.store.get('handoff','active')
        mission=service.store.get('mission',row.get('missionId')) if row and row.get('missionId') else None
        return {'session':row,'progress':{'title':mission['title'],'status':mission['status'],
                'completed':sum(x['status']=='completed' for x in mission['steps']),'total':len(mission['steps'])} if mission else None}

    @router.post('/suggestions/dismiss')
    def dismiss(body:Dismiss): return call(lambda:operator().dismiss(body.key))

    @router.get('/screen/windows',dependencies=[Depends(desktop)])
    def windows():
        from core.assistant_operator.screen import windows
        return call(lambda:{'windows':windows()})

    @router.post('/screen/grant',dependencies=[Depends(desktop)])
    def grant(body:Grant): return call(lambda:operator().screen.grant(body.handle))

    @router.delete('/screen/grant',dependencies=[Depends(desktop)])
    def clear(): return operator().screen.revoke()

    @router.post('/screen/inspect',dependencies=[Depends(desktop)])
    def inspect(body:Inspect):
        allowed('chat.reply')
        return call(lambda:operator().screen.inspect(body.grantId,body.question))

    return router
