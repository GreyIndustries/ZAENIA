"""Isolated local UI fixture. No owner data, real credentials, or model calls.

Run from the project root: .venv/Scripts/python.exe -m scripts.assistant_ui_preview
Only for local development; its known token must never be used by production.
"""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import uvicorn


def main():
    from core.api import assistant_routes, ui_tasks, ui_calendar, ui_chat_stream, ui_conversation, ui_voice, ui_files
    from core.api.server import create_app
    from core.assistant_followthrough.service import FollowThroughService
    from core.personal_memory import MemoryStore
    from core.foundation.client_gate import CLIENT_CAPABILITIES
    from core.assistant_platform.service import PlatformService
    from core.assistant_platform.store import PlatformStore
    from core.assistant_platform.jobs import JobManager
    from core.assistant_platform.projects import validate_project

    class Gate:
        def authorize(self, operation):
            return operation in CLIENT_CAPABILITIES

    class Brain:
        def __init__(self,*args,**kwargs): pass
        def remember_exchange(self, **record):
            pass
        def remember_action_result(self, **record):
            pass
        def stream_ask(self, message, *, remember):
            yield {"type": "text", "text": "This is an isolated local UI preview."}
            yield {"type": "final", "answer": "This is an isolated local UI preview."}

    with ExitStack() as stack:
        root = Path(stack.enter_context(TemporaryDirectory(prefix="zae-ui-preview-",dir=Path(__file__).resolve().parents[1])))
        store = MemoryStore(root / "memory.sqlite3")
        store.upsert("response style", "Keep responses concise and practical.", "preference")
        service = FollowThroughService(root / "inbox.sqlite3")
        now = datetime.now(timezone.utc)
        service.poll(events=[{"id": "preview-inspection", "title": "Preview: car inspection", "start": (now + timedelta(minutes=10)).isoformat(), "recurrence": "none"}], tasks=[])
        platform=PlatformService(PlatformStore(root/"platform/state.sqlite3"),JobManager())
        from core.assistant_platform.notes import Notes
        Notes(platform.store).save({'title':'Preview: ideas for later','body':'Keep useful ideas, project details and things to revisit here.\nThis is isolated sample data.','pinned':True})
        from core.assistant_platform.personal_tools import PersonalTools
        personal = PersonalTools(platform.store)
        personal.save('workbench', {'title':'Preview: portable sensor','category':'Tech','color':'blue','size':'large','status':'Prototype',
            'body':'Project notes, measurements and experiments live here. This is isolated sample data.', 'boardWidth':120.0,
            'strokes':[{'color':'#75cfff','width':2.0,'points':[[200.0,200.0],[800.0,200.0],[800.0,400.0],[200.0,400.0],[200.0,200.0]]}],
            'scenarios':'Compare enclosure materials in a CAD solver, then record measured results.'})
        personal.save('workbench', {'title':'Preview: biology notebook','category':'Biology','color':'green','size':'small'})
        personal.save('workbench', {'title':'Preview: AI experiment','category':'AI','color':'violet','size':'medium'})
        personal.save('music', {'title':'Preview: First Light','stage':'Mixing','bpm':96.0,'key':'D minor','body':'Fixture project only.',
            'stats':[{'platform':'YouTube','date':now.date().isoformat(),'metric':'Views','value':120,'source':'Isolated sample count, lifetime'}]})
        from zoneinfo import ZoneInfo
        day=datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
        personal.save('food',{'title':'Preview: meal','date':day,'calories':520.0,'protein':32.0,'fiber':9.0})
        personal.save('exercise',{'title':'Preview: walk','date':day,'minutes':30.0,'calories':130.0})
        personal.save('plans',{'title':'Preview: weekly routine','schedule':'Monday / Wednesday / Friday','sourceName':'Isolated sample',
            'sourceText':'Squats: 3 x 10 reps\nWalk: 20 minutes','steps':[{'exercise':'Squats','prescription':'3 x 10 reps'},{'exercise':'Walk','prescription':'20 minutes'}]})
        from types import SimpleNamespace
        stack.enter_context(patch('core.tech_news.service.tech_news',return_value=SimpleNamespace(headlines=lambda **kw:{'stories':[],'sources':[],'updatedAt':None})))
        platform.operator.create('Preview: research to document',[
            {'tool':'web.read','args':{'url':'https://docs.python.org/3/library/pathlib.html'}},
            {'tool':'evidence.summarize','args':{'sourceStep':0}},
        ],priority=True)
        goal=platform.operator.continuity({'kind':'goal','title':'Preview: SSD readiness','detail':'Finish verified tasks and recovery checks before moving to an SSD.'})
        platform.operator.continuity({'kind':'decision','title':'Preview: interface direction','detail':'Keep the existing amber and glass style.','links':[goal['id']]})
        platform.operator.handoff({'device':'phone','summary':'Preview: continue the readiness review.','nextStep':'Inspect the mission plan and source receipts.'},0)
        stack.enter_context(patch('core.assistant_followthrough.service.local_calendar_snapshot',return_value=[]))
        stack.enter_context(patch('core.brain.local_llm.chat_local',return_value='{"steps":[{"tool":"web.read","args":{"url":"https://docs.python.org/3/library/pathlib.html"}}]}'))
        stack.enter_context(patch('core.assistant_operator.planner.plan_json',return_value={'steps':[{'tool':'web.read','args':{'url':'https://docs.python.org/3/library/pathlib.html'}}]}))
        platform.store.put("project",validate_project({"title":"Preview: assistant readiness","goal":"Verify the new tools using isolated sample data.","steps":[{"id":"first","title":"Review the current setup","status":"completed"},{"id":"second","title":"Verify the next change","dependsOn":["first"]}]}))
        platform.store.put("workspace",{"name":"Preview coding","windows":[{"id":"files","x":.15,"y":.04,"w":.55,"h":.7,"z":12,"minimized":False}],"apps":[],"note":"Sample session only.","projectId":None})
        stack.enter_context(patch("core.assistant_platform.service.platform",return_value=platform))
        stack.enter_context(patch("core.assistant_platform.service.existing_platform",return_value=platform))
        stack.enter_context(patch("core.brain.brain_service.BrainService",Brain))
        stack.enter_context(patch("core.personal_memory.insights.DEFAULT_PATH",root/"insights.json"))
        from core.personal_memory.owner_profile import OwnerProfile
        stack.enter_context(patch('core.personal_memory.owner_profile.owner_profile',return_value=OwnerProfile(root/'owner-profile.sqlite3',extract=lambda text:[])))
        from core.calendar_context import duty_status
        stack.enter_context(patch.object(duty_status,'DUTY_FILE',root/'duty/overrides.json'))
        def preview_calendar(start,days):
            saved=duty_status.read_overrides()
            keys=[(start+timedelta(days=index)).isoformat() for index in range(days)]
            overrides={key:saved['days'][key] for key in keys if key in saved['days']}
            return {'start':start.isoformat(),'days':days,'events':[],
                    'dayStatus':{key:duty_status.LABELS[overrides[key]] if key in overrides else 'Fixture calendar status' for key in keys},
                    'dutyOverrides':overrides,'dutyRevision':saved['revision'],'google':'unavailable','notice':'Isolated preview','googleWrite':False}
        stack.enter_context(patch.object(ui_calendar,'read_calendar',side_effect=preview_calendar))
        stack.enter_context(patch("core.assistant_platform.health.inspect_health",return_value={"checkedAt":now.isoformat(),"components":[{"id":"preview","state":"ready","detail":"Sample health only; owner services are not probed."}]}))
        stack.enter_context(patch("core.assistant_platform.health.readiness",return_value={"ready":False,"checks":[{"id":"preview","ok":True,"detail":"Sample data only"}],"scope":"Isolated preview, not destination readiness.","manualChecks":["Live hardware acceptance remains separate."],"portableExclusions":[]}))
        stack.enter_context(patch.object(assistant_routes, "memory_store", return_value=store))
        stack.enter_context(patch.object(assistant_routes, "audit"))
        stack.enter_context(patch("core.api.ui_routes.audit"))
        stack.enter_context(patch.object(ui_tasks, "UI_DATA_DIR", root / "tasks"))
        stack.enter_context(patch.object(ui_calendar, "scheduling_db", return_value=root / "calendar.sqlite3"))
        stack.enter_context(patch.object(ui_chat_stream, "_brain", return_value=Brain()))
        stack.enter_context(patch.object(ui_chat_stream, "_conversation_hooks"))
        stack.enter_context(patch.object(ui_conversation, "MEMORY_PATH", root / "history.jsonl"))
        stack.enter_context(patch.object(ui_voice, "service_status", return_value={"running": False, "state": "off"}))
        stack.enter_context(patch("core.api.ui_weather.current_weather",return_value={"available":False,"notice":"Isolated preview; weather disabled."}))
        stack.enter_context(patch.object(ui_files, "list_proposals", return_value=[]))
        stack.enter_context(patch("core.assistant_followthrough.service.FollowThroughService", return_value=service))
        app = create_app(token_verifier=lambda token: token == "assistant-preview-test-token", client_gate=Gate(), include_carplay=False,platform_provider=lambda:platform)
        # Do not read real status/brief/calendar data during visual inspection.
        app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", "") not in {"/api/status", "/api/calendar"}]
        @app.get("/api/status")
        def status():
            from fastapi import HTTPException
            raise HTTPException(503, "Isolated UI preview: system telemetry is disabled.")
        @app.get('/preview-hands')
        def hands_probe():
            from fastapi.responses import HTMLResponse
            return HTMLResponse('<!doctype html><title>Local hand worker check</title><button id="start">Test with blank frame</button><p id="result">Camera off. Synthetic frame only.</p><script src="/preview-hands.js"></script>')
        @app.get('/preview-hands.js')
        def hands_probe_script():
            from fastapi.responses import Response
            return Response('''document.getElementById("start").onclick=()=>{
              const result=document.getElementById("result");result.textContent="Loading local worker…";
              const worker=new Worker("/app/handtracking/worker.js");
              worker.onerror=event=>{result.textContent="Failed: "+event.message;worker.terminate();};
              worker.onmessage=async event=>{
                if(event.data.type==="ready"){
                  const canvas=new OffscreenCanvas(256,256);canvas.getContext("2d").fillRect(0,0,256,256);
                  const frame=await createImageBitmap(canvas);worker.postMessage({type:"frame",frame,at:performance.now()},[frame]);
                }else if(event.data.type==="landmarks"){
                  result.textContent=event.data.points?"Unexpected hand on blank frame":"PASS: local model loaded; blank frame detected no hands; camera remained off.";
                  worker.postMessage({type:"close"});
                }else if(event.data.type==="error"){result.textContent="Failed: "+event.data.detail;worker.terminate();}
              };worker.postMessage({type:"init"});
            };''',media_type='text/javascript')
        uvicorn.run(app, host="127.0.0.1", port=8877, log_level="warning")


if __name__ == "__main__":
    main()
