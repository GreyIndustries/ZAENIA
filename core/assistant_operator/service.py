"""Durable reviewed missions, continuity, factual suggestions and session handoff."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import re
import threading
import uuid
from core.assistant_platform.store import Conflict,now_text,text
from core.assistant_platform.jobs import process_alive
from core.assistant_platform.performance import WorkCancelled
from .tools import Tools,CATALOG,catalog,validate

ACTIVE={'queued','running'}
TERMINAL={'completed','completed_with_limits','cancelled'}


def owner_alive(row):
    if not process_alive(row.get('ownerPid')): return False
    if row.get('ownerBirth') is None: return False
    import psutil
    try: return abs(psutil.Process(row['ownerPid']).create_time()-row['ownerBirth'])<.01
    except (psutil.NoSuchProcess,psutil.AccessDenied): return False


def plan_hash(steps):
    return hashlib.sha256(json.dumps(steps,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def clean_steps(steps):
    if not isinstance(steps,list) or not 1<=len(steps)<=20: raise ValueError('A mission needs 1–20 controlled steps.')
    result=[]
    for index,step in enumerate(steps):
        if not isinstance(step,dict) or set(step)-{'tool','args','label'}: raise ValueError('Each step needs a tool, arguments and optional label.')
        tool=step.get('tool'); args=validate(tool,step.get('args',{}))
        if args.get('sourceStep') is not None and args['sourceStep']>=index: raise ValueError('Evidence dependencies must point to an earlier step.')
        result.append({'tool':tool,'args':args,'label':text(step.get('label') or CATALOG[tool][2],'Step label',200)})
    if len(json.dumps(result).encode())>200000: raise ValueError('Mission plan is too large.')
    return result


def validate_continuity(payload):
    if not isinstance(payload,dict) or set(payload)-{'kind','title','detail','status','links','source','id','revision','updatedAt','ownerReviewed'}: raise ValueError('Unknown continuity field.')
    kind=payload.get('kind'); status=payload.get('status','active')
    if kind not in {'goal','person','project','decision','preference','commitment'} or status not in {'active','resolved','superseded'}: raise ValueError('Choose a supported record type and status.')
    detail=payload.get('detail',''); source=payload.get('source','Owner entry')
    if not isinstance(detail,str) or len(detail)>800 or not isinstance(source,str) or len(source)>500: raise ValueError('Continuity detail or source is too long.')
    from core.personal_memory.store import validate_memory
    validate_memory(payload.get('title'),detail or '(no detail)','preference' if kind=='preference' else 'fact','explicit_owner')
    validate_memory('Source',source or 'Owner entry')
    links=payload.get('links',[])
    if not isinstance(links,list) or len(links)>20 or any(not isinstance(x,str) or not re.fullmatch('[a-f0-9]{32}',x) for x in links): raise ValueError('Related records must use valid continuity IDs.')
    return {'kind':kind,'title':text(payload.get('title'),'Title',120),'detail':detail,'status':status,'links':list(dict.fromkeys(links)),'source':source,'ownerReviewed':True}


class Operator:
    def __init__(self,platform,tools=None):
        self.platform=platform; self.store=platform.store; self.tools=tools or Tools(self.store)
        self.lock=threading.RLock(); self.instance=uuid.uuid4().hex; self._screen=None
        with self.store.connection() as db:
            db.execute("CREATE INDEX IF NOT EXISTS operator_mission_status ON records(json_extract(payload,'$.status'),updated DESC) WHERE kind='mission'")

    @property
    def screen(self):
        with self.lock:
            if self._screen is None:
                from .screen import Screen
                self._screen=Screen()
            return self._screen

    def create(self,title,steps,*,priority=False):
        steps=clean_steps(steps)
        return self.store.put('mission',{'title':text(title,'Mission title',160),'plan':steps,'planHash':plan_hash(steps),
            'priority':bool(priority),'status':'draft','steps':[{'status':'pending'} for _ in steps],
            'createdAt':now_text(),'cancelRequested':False,'approval':None})

    def draft(self,title,goal,authorize,*,priority=False):
        if not isinstance(goal,str) or not 1<=len(goal.strip())<=4000: raise ValueError('Describe a goal in 1–4,000 characters.')
        def work(ctx):
            for permission in ('chat.reply','assistant.platform.write','files.read'):
                if authorize(permission) is False: raise PermissionError('Permission denied: '+permission)
            from .planner import plan_json
            ctx.progress('Drafting a controlled mission',detail='Proposal only; nothing is executed until the exact steps are reviewed.')
            prompt='Return JSON only: {"steps":[{"tool":"...","args":{...},"label":"..."}]}. Use 1–8 supported tools only. No invented paths, root IDs or credentials. Stop with an empty steps list if a required input is unknown. Earlier result references use zero-based sourceStep. Never execute code. '
            # Full UI JSON schemas crowd small local-model context windows.
            # Send compact signatures so planning rules and the entire goal fit.
            signatures=[]
            for item in catalog():
                fields=[]
                for key,prop in item['schema']['properties'].items():
                    kind=prop.get('type') or '/'.join(x.get('type','value') for x in prop.get('anyOf',[]) if x.get('type')!='null')
                    fields.append(key+':'+kind+('' if key in item['schema'].get('required',[]) else ' (optional)'))
                signatures.append(item['name']+'('+', '.join(fields)+'): '+item['description'])
            prompt+='Include every requested operation, not just the first one. Read-and-summarize means TWO steps: web.read with url, then evidence.summarize with sourceStep 0. '
            prompt+='\nCATALOG:\n'+'\n'.join(signatures)+'\nAPPROVED FOLDERS: '+json.dumps(self.store.list('operator_root'))+'\nOWNER GOAL: '+goal
            data=plan_json(prompt); ctx.check()
            try: proposed=clean_steps(data.get('steps',[]))
            except ValueError as error:
                ctx.progress('Repairing proposed steps',detail='One bounded structured retry; no operations have run.')
                data=plan_json(prompt+'\nThe prior proposal failed validation: '+str(error)[:600]+'. Correct it using the catalog, without adding unknown inputs.')
                ctx.check(); proposed=clean_steps(data.get('steps',[]))
            if authorize('assistant.platform.write') is False: raise PermissionError('Mission drafting permission was revoked.')
            mission=self.create(title,proposed,priority=priority)
            return {'missionId':mission['id'],'text':'Draft saved for review; no operations ran.'}
        return self.platform.jobs.submit('Draft mission: '+text(title,limit=160),work,priority=priority)

    def reconcile(self,*,compact=False):
        rows=[]
        with self.store.connection() as db:
            # Histories are bounded. Active older work is always included. The
            # summary projection strips receipt bodies inside SQLite, avoiding
            # loading old research/documents on each visible UI poll.
            projection="id,revision,updated,json_remove(payload,'$.steps') AS payload,(SELECT json_group_array(json_remove(value,'$.result')) FROM json_each(records.payload,'$.steps')) AS states" if compact else '*'
            recent=list(db.execute(f"SELECT {projection} FROM records WHERE kind='mission' ORDER BY updated DESC,id LIMIT 30"))
            running=list(db.execute(f"SELECT {projection} FROM records WHERE kind='mission' AND json_extract(payload,'$.status') IN ('queued','running','needs_review','interrupted','failed') ORDER BY updated DESC LIMIT 24"))
            records={x['id']:x for x in recent+running}
            decoded=[]
            for entry in records.values():
                row=self.store.decode(entry)
                if compact: row['steps']=json.loads(entry['states'] or '[]')
                decoded.append(row)
        for row in decoded:
            job=self.store.get('job',row.get('jobId')) if row.get('jobId') and row['status'] in ACTIVE else None
            stopped_job=bool(job and job.get('status') in {'cancelled','failed','interrupted','completed'})
            if row['status'] in ACTIVE and (not owner_alive(row) or stopped_job):
                if compact: row=self.store.get('mission',row['id'])
                steps=row['steps']; uncertain=False
                for index,state in enumerate(steps):
                    if state['status']=='running':
                        mutation=CATALOG[row['plan'][index]['tool']][1]
                        state.update(status='needs_review' if mutation else 'interrupted',detail='The process exited before a final receipt was saved.')
                        uncertain|=mutation
                status='needs_review' if uncertain else 'cancelled' if job and job.get('status')=='cancelled' else 'interrupted'
                row=self.store.put('mission',{**row,'status':status,'steps':steps},row['id'],revision=row['revision'])
                if compact: row['steps']=[{k:v for k,v in state.items() if k!='result'} for state in row['steps']]
            rows.append(row)
        return rows

    def start(self,identifier,revision,digest,authorize):
        # CAS claims the mission across API processes; exact immutable plan is bound to review.
        row=self.store.get('mission',identifier)
        if not row or row['revision']!=revision or row['planHash']!=digest or plan_hash(row['plan'])!=digest: raise Conflict('The reviewed mission changed. Refresh and review it again.')
        if row['status'] not in {'draft','failed','interrupted','cancelled'}: raise Conflict('This mission cannot start in its current state.')
        if any(x['status']=='needs_review' for x in row['steps']): raise Conflict('Resolve the uncertain step before continuing.')
        self._authorize_plan(row,authorize)
        from .tools import file_path
        for step,state in zip(row['plan'],row['steps']):
            receipt=state.get('result',{})
            if state['status']=='completed' and receipt.get('sha256'):
                args=step['args']
                if args.get('rootId'):
                    path=file_path(self.store,args['rootId'],args.get('output') or args['path'])
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['sha256']:
                        raise Conflict('An earlier verified file changed. Create a revised mission using the current file.')
        import psutil
        row=self.store.put('mission',{**row,'status':'queued','cancelRequested':False,'ownerPid':os.getpid(),'ownerBirth':psutil.Process().create_time(),
            'ownerInstance':self.instance,'approval':{'planHash':digest,'reviewedAt':now_text()}},identifier,revision=revision)
        try:
            job=self.platform.jobs.submit(row['title'],lambda ctx:self._execute(identifier,ctx,authorize),priority=row['priority'])
            self.store.patch('mission',identifier,{'jobId':job['id']})
            return {'missionId':identifier,'job':job}
        except Exception:
            self.store.patch('mission',identifier,{'status':'interrupted'}); raise

    @staticmethod
    def _authorize_plan(row,authorize):
        def require(op):
            if authorize(op) is False: raise PermissionError(f'Permission denied: {op}')
        require('assistant.desktop.manage')
        for step in row['plan']:
            tool=step['tool']
            if tool.startswith(('document.','spreadsheet.','blender.','vscode.')): require('files.read')
            if tool in {'document.create','spreadsheet.create','spreadsheet.copy_edit','blender.move_copy'}: require('files.desktop.apply')
            if tool.startswith(('browser.','vscode.','blender.')): require('assistant.apps.launch')
            if tool=='evidence.summarize': require('chat.reply')

    def _execute(self,identifier,ctx,authorize):
        row=self.store.get('mission',identifier); states=row['steps']; previous=[state.get('result',{}) for state in states]
        index=None; in_effect=False
        try:
            for index,step in enumerate(row['plan']):
                if states[index]['status']=='completed': continue
                current=self.store.get('mission',identifier)
                if current.get('cancelRequested'): raise WorkCancelled('Owner stopped this mission.')
                ctx.check(); self._authorize_plan({'plan':[step]},authorize)
                ctx.progress(step['label'],done=sum(x['status']=='completed' for x in states),total=len(states))
                states[index]={'status':'running','startedAt':now_text()}
                self.store.patch('mission',identifier,{'status':'running','steps':states})
                # Durable running marker precedes every possible effect.
                in_effect=True
                result=self.tools.execute(step['tool'],step['args'],ctx,previous)
                encoded=json.dumps(result,ensure_ascii=False,allow_nan=False,default=str)
                if len(encoded.encode())>85000:
                    result={'text':str(result.get('text',''))[:30000],'verified':False,'truncated':True,'detail':'Receipt exceeded the saved size limit.'}
                else: result=json.loads(encoded)
                states[index]={'status':'completed','finishedAt':now_text(),'result':result}
                self.store.patch('mission',identifier,{'steps':states})
                in_effect=False; previous[index]=result
            limited=any(x.get('result',{}).get('verified') is False for x in states)
            self.store.patch('mission',identifier,{'status':'completed_with_limits' if limited else 'completed','finishedAt':now_text()})
            return {'missionId':identifier,'steps':len(states),'text':'Mission finished; inspect each saved receipt for verification and any limits.'}
        except BaseException as error:
            uncertain=in_effect and index is not None and CATALOG[row['plan'][index]['tool']][1]
            if index is not None and states[index]['status']!='completed':
                states[index].update(status='needs_review' if uncertain else 'interrupted' if isinstance(error,WorkCancelled) else 'failed',
                    detail=str(error)[:400] if isinstance(error,(ValueError,PermissionError,WorkCancelled)) else type(error).__name__)
            self.store.patch('mission',identifier,{'steps':states,'status':'needs_review' if uncertain else 'cancelled' if isinstance(error,WorkCancelled) else 'failed'})
            raise

    def cancel(self,identifier):
        row=self.store.get('mission',identifier)
        if not row: raise ValueError('Unknown mission.')
        if row['status'] not in ACTIVE: raise Conflict('This mission is not running.')
        return self.store.patch('mission',identifier,{'cancelRequested':True})

    def resolve(self,identifier,revision,index,decision):
        row=self.store.get('mission',identifier)
        if not row or row['revision']!=revision or row['status']!='needs_review': raise Conflict('Refresh the uncertain mission before resolving it.')
        if not 0<=index<len(row['steps']) or row['steps'][index]['status']!='needs_review': raise ValueError('Choose an uncertain step.')
        if decision not in {'retry','accept'}: raise ValueError('Choose retry after inspection, or accept the existing result.')
        row['steps'][index]={'status':'pending'} if decision=='retry' else {'status':'completed','result':{
            'verified':False,'text':'Owner accepted the external result after inspection; no automatic verification receipt is available.'}}
        return self.store.put('mission',{**row,'status':'interrupted'},identifier,revision=revision)

    def continuity(self,payload,identifier=None,revision=None):
        value=validate_continuity(payload)
        if any(self.store.get('continuity',x) is None or x==identifier for x in value['links']): raise ValueError('Links must refer to existing other continuity records.')
        if identifier and revision is None: raise ValueError('Supply the revision when editing continuity.')
        return self.store.put('continuity',value,identifier,revision=revision)

    def context(self,question):
        tokens=set(re.findall(r'[\w]{3,}',question.casefold()))
        rows=self.store.list('continuity'); scored=[]
        for row in rows:
            if row.get('status')!='active': continue
            score=len(tokens & set(re.findall(r'[\w]{3,}',(row['title']+' '+row['detail']).casefold())))
            if score: scored.append((score,row))
        selected=[{'id':r['id'],'kind':r['kind'],'title':r['title'],'detail':r['detail'],'links':r['links'],'source':r['source'],'updatedAt':r['updatedAt']} for _,r in sorted(scored,key=lambda p:p[0],reverse=True)[:4]]
        handoff=self.store.get('handoff','active')
        return {'records':selected,'activeSession':handoff} if selected or handoff else None

    def handoff(self,payload,revision):
        if set(payload)-{'device','missionId','summary','nextStep'}: raise ValueError('Unknown handoff field.')
        device=payload.get('device')
        if device not in {'pc','phone','car'}: raise ValueError('Choose PC, phone or car.')
        mission=payload.get('missionId') or None
        if mission and not self.store.get('mission',mission): raise ValueError('Choose an existing mission.')
        summary=text(payload.get('summary'),'Session summary',1500)
        next_step=text(payload.get('nextStep'),'Next step',1000)
        return self.store.put('handoff',{'device':device,'missionId':mission,'summary':summary,'nextStep':next_step,
            'executionLocation':'pc','notice':'Device label is not authentication; execution remains on the PC.'},'active',revision=revision)

    def suggestions(self,*,tasks=(),events=(),duty=None,now=None):
        now=now or datetime.now(timezone.utc); found=[]
        for row in self.reconcile(compact=True):
            if row['status'] in {'failed','needs_review','interrupted'}:
                found.append({'key':'mission:'+row['id']+':'+str(row['revision']),'title':'Resume or inspect '+row['title'],
                    'reason':'Saved work is '+row['status']+'. Review its last receipt before continuing.','source':'mission ledger','missionId':row['id']})
        # Actual persisted project dependencies, never a model guess.
        for project in self.store.list('project'):
            from core.assistant_platform.projects import project_view
            view=project_view(project); next_step=view.get('nextStep')
            if next_step:
                found.append({'key':'project:'+project['id']+':'+next_step['id'],'title':next_step['title'],
                    'reason':'Prerequisites are complete in '+project['title']+'.','source':'saved project'})
        starts=[]
        for task in tasks:
            try:
                due=datetime.fromisoformat(str(task.get('deadline','')).replace('Z','+00:00'))
                if task.get('status') not in {'Done','done','completed'} and not task.get('archived') and due.tzinfo and due<now:
                    found.append({'key':'overdue:'+str(task.get('id'))+':'+due.isoformat(),'title':'Review overdue work: '+str(task.get('title','task')),
                        'reason':'Its saved deadline has passed. Replan it or mark it complete after checking the result.','source':'saved tasks'})
            except (ValueError,TypeError): continue
        for event in events:
            try:
                begin=datetime.fromisoformat(str(event.get('start','')).replace('Z','+00:00'))
                end=datetime.fromisoformat(str(event.get('end','')).replace('Z','+00:00'))
                if begin.tzinfo and end.tzinfo and end>now and begin<now+timedelta(days=1): starts.append((begin,end,event))
            except (ValueError,TypeError): continue
        starts.sort(key=lambda x:x[0])
        for i,(begin,end,event) in enumerate(starts):
            if now<begin<=now+timedelta(hours=2):
                found.append({'key':'prepare:'+str(event.get('id'))+':'+begin.isoformat(),'title':'Prepare for '+str(event.get('title','event')),
                    'reason':f'Saved event begins at {begin.isoformat()}. Review materials and unfinished prerequisites.','source':'saved calendar'})
            for other_start,other_end,other in starts[i+1:]:
                if other_start<end:
                    found.append({'key':'conflict:'+str(event.get('id'))+':'+str(other.get('id')),'title':'Calendar overlap',
                        'reason':f"{event.get('title','Event')} overlaps {other.get('title','another event')}; no event was changed.",'source':'saved calendar'})
        if duty in {'class','on_duty','leave'} and any(x['status'] in ACTIVE for x in self.reconcile(compact=True)):
            found.append({'key':'availability:'+now.date().isoformat()+':'+duty,'title':'Current availability',
                'reason':f'Your selected status is {duty.replace("_"," ")}. Active work stays on the PC; choose a handoff if needed.','source':'owner-selected daily status'})
        dismissed={x['id'] for x in self.store.list('suggestion_dismissed')}
        return [x for x in found if hashlib.sha256(x['key'].encode()).hexdigest() not in dismissed][:30]

    def dismiss(self,key):
        return self.store.put('suggestion_dismissed',{'key':text(key,limit=400)},hashlib.sha256(key.encode()).hexdigest())

    def recovery(self):
        missions=self.reconcile(compact=True)
        return {'checkedAt':now_text(),'interrupted':[{'id':x['id'],'title':x['title'],'status':x['status']} for x in missions if x['status'] in {'needs_review','failed','interrupted'}],
            'policy':{'automaticReplayOfUnknownChanges':False,'startupAuthentication':'unchanged','rawScreenImagesSaved':False},
            'sourceSnapshots':self.store.list('release')[:10],
            'limits':['Unknown side effects require inspection before retry.','Source snapshots do not roll back installed apps, the OS or executables.','Browser sessions and screen grants expire with their owning process.']}
