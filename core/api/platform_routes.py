"""Authenticated assistant controls; local file/process grants require desktop pairing."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

ID = r"[A-Za-z0-9_-]{1,100}"
PATTERNS = [
    ('GET',r'calendar-completions', 'calendar.read'),
    ('PUT',r'calendar-completions/[a-f0-9]{64}', 'ui.calendar.write'),
    ('GET',r'personal/fitness-summary', 'memory.read'),
    ('GET',r'personal/training(?:/day)?', 'memory.read'),
    ('POST',r'personal/training/(?:profile|program|day|actual|quick-log|source|improve)', 'memory.write'),
    ('GET',rf'personal/(?:workbench|experiments|music|food|recipes|exercise|plans|fitness-settings|inventory|meal-plans)(?:/{ID})?', 'memory.read'),
    ('POST',r'personal/nutrition/(?:meal-preview|barcode|search|suggest|web|label|recipe-math)', 'memory.read'),
    ('POST',r'personal/nutrition/log', 'memory.write'),
    ('POST',r'personal/(?:workbench|experiments|music|food|recipes|exercise|plans|fitness-settings|inventory|meal-plans|training-source)', 'memory.write'),
    ('PUT',rf'personal/(?:workbench|experiments|music|food|recipes|exercise|plans|fitness-settings|inventory|meal-plans)/{ID}', 'memory.write'),
    ('GET',r'knowledge(?:/search)?|scripture(?:/status)?', 'memory.read'),
    ('POST',r'knowledge', 'memory.write'),
    ('DELETE',rf'knowledge/{ID}', 'memory.write'),
    ('GET',rf'notes(?:/{ID})?', 'memory.read'),
    ('POST',r'notes', 'memory.write'),
    ('POST',rf'notes/{ID}/append', 'memory.write'),
    ('PUT',rf'notes/{ID}', 'memory.write'),
    ('GET',rf'operator/(?:summary|missions/{ID}|handoff)', 'assistant.platform.read'),
    ('POST',rf'operator/(?:missions|draft|missions/{ID}/cancel|continuity|suggestions/dismiss)', 'assistant.platform.write'),
    ('PATCH',rf'operator/continuity/{ID}', 'assistant.platform.write'),
    ('DELETE',rf'operator/continuity/{ID}', 'assistant.platform.write'),
    ('PUT',r'operator/handoff', 'assistant.platform.write'),
    ('POST',rf'operator/(?:missions/{ID}/(?:start|resolve)|roots|screen/(?:grant|inspect))', 'assistant.desktop.manage'),
    ('GET',r'operator/screen/windows', 'assistant.desktop.manage'),
    ('DELETE',rf'operator/(?:roots/{ID}|screen/grant)', 'assistant.desktop.manage'),
    ("GET",r"summary|jobs|metrics|apps|apps/suggestions|projects|workspaces|approvals|actions|health|readiness|profile/requests", "assistant.platform.read"),
    ("POST",rf"jobs|jobs/{ID}/cancel|projects|projects/plan|workspaces|workspaces/{ID}/restore", "assistant.platform.write"),
    ("PATCH",rf"projects/{ID}|workspaces/{ID}", "assistant.platform.write"),
    ("DELETE",rf"projects/{ID}|workspaces/{ID}", "assistant.platform.write"),
    ("GET",r"documents|documents/search|documents/onedrive-candidates|documents/images", "assistant.documents.read"),
    ("POST",rf"apps|documents|documents/{ID}/index|documents/open|documents/read-image|actions/{ID}/undo|health/recover|profile/requests|snapshots", "assistant.desktop.manage"),
    ("PUT",r"approvals", "assistant.desktop.manage"),
    ("DELETE",rf"apps/{ID}|documents/{ID}", "assistant.desktop.manage"),
    ("POST",rf"apps/{ID}/launch", "assistant.apps.launch"),
]


def operation_for(method,path):
    if not path.startswith("/api/platform/"): return None
    route = path[len("/api/platform/"):]
    for verb,pattern,operation in PATTERNS:
        if verb==method and re.fullmatch("(?:"+pattern+")",route): return operation
    return None


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisBody(Body):
    question: str = Field(min_length=1,max_length=6000)
    priority: bool = False
    detailed: bool = False


class KnowledgeBody(Body):
    url: str = Field(default='',max_length=2000)
    title: str = Field(default='',max_length=250)
    content: str = Field(default='',max_length=1_000_000)


class TargetBody(Body):
    name: str = Field(min_length=1,max_length=100)
    path: str = Field(min_length=1,max_length=1000)


class WorkspaceBody(Body):
    name: str = Field(min_length=1,max_length=80)
    windows: list[dict[str,Any]] = Field(default_factory=list,max_length=12)
    apps: list[str] = Field(default_factory=list,max_length=12)
    projectId: str | None = Field(default=None,max_length=64)
    note: str = Field(default="",max_length=2000)
    revision: int | None = Field(default=None,ge=0)


class ProjectBody(Body):
    title: str = Field(min_length=1,max_length=200)
    goal: str = Field(default="",max_length=2000)
    steps: list[dict[str,Any]] = Field(default_factory=list,max_length=150)
    revision: int | None = Field(default=None,ge=0)


class RestoreBody(Body):
    launchApps: bool = False
    revision: int | None = Field(default=None,ge=1)


class ProfileBody(Body):
    mode: str
    path: str = Field(min_length=1,max_length=1000)
    restoreMode: str = "merge"
    uiSettings: dict[str,str] = Field(default_factory=dict)


def create_platform_router(require_auth:Callable[...,Any],authorize:Callable[[str],Any], *, provider=None):
    from core.assistant_platform.service import platform
    get = provider or platform
    router = APIRouter(tags=["platform"],dependencies=[Depends(require_auth)])

    def desktop(key: str | None = Header(default=None,alias="X-ZAENIA-DESKTOP-KEY")):
        from core.api.desktop_key import verify
        if not verify(key): raise HTTPException(403,"Use the paired desktop app to approve local file, process, or policy changes.")
        return key

    def desktop_or_phone_at_pc(key: str | None = Header(default=None,alias="X-ZAENIA-DESKTOP-KEY"),
                               near: str | None = Header(default=None,alias="X-ZAENIA-NEAR-PASS")):
        # Opening a registered app or restoring one: the desktop app, or the phone with an active at-the-PC pass.
        from core.api.near_pc import desktop_or_near
        if desktop_or_near(key,near) is None: desktop(key)

    def call(function):
        from core.assistant_platform.store import Conflict
        try: return function()
        except Conflict as error: raise HTTPException(409,str(error)) from error
        except (ValueError,TypeError,KeyError) as error: raise HTTPException(422,str(error)) from error
        except PermissionError as error: raise HTTPException(403,str(error)) from error
        except TimeoutError as error: raise HTTPException(503,"The local store is busy; refresh before retrying.") from error

    @router.get("/api/platform/summary")
    def summary():
        service = get()
        from core.assistant_platform.performance import COORDINATOR
        from core.api.ui_voice import service_status
        voice=service_status()
        timing=voice.get("timing") if voice.get("running") else None
        return {"jobs":service.all_jobs(),"activeWorkspace":service.store.get("settings","active_workspace"),
                "metrics":timing if isinstance(timing,dict) else COORDINATOR.snapshot(),"metricsSource":"pcVoice" if isinstance(timing,dict) else "api","policy":service.history.policy()}

    @router.get('/api/platform/knowledge')
    def knowledge_list(): return {'sources':get().knowledge.list()}

    @router.post('/api/platform/knowledge')
    def knowledge_learn(body:KnowledgeBody):
        def learn():
            if body.url:
                if body.content: raise ValueError('Choose a webpage or pasted text, not both.')
                return get().knowledge.learn_url(body.url)
            return get().knowledge.learn(body.title,body.content)
        return call(learn)

    @router.delete('/api/platform/knowledge/{identifier}')
    def knowledge_remove(identifier:str): return {'removed':call(lambda:get().knowledge.remove(identifier))}

    @router.get('/api/platform/knowledge/search')
    def knowledge_search(q:str=Query(min_length=1,max_length=1000)):
        return {'matches':call(lambda:get().knowledge.search(q))}

    @router.get('/api/platform/scripture/status')
    def scripture_status():
        from core.foundation.moral_code.scripture_context import Corpus
        coverage=call(lambda:Corpus().coverage())
        return {'available':True,'books':len(coverage['books']),'translations':coverage['translations'],
                'credit':'STEP Bible / Tyndale House Cambridge · CC BY 4.0',
                'source':'https://github.com/STEPBible/STEPBible-Data'}

    @router.get('/api/platform/scripture')
    def scripture_read(reference:str=Query(min_length=3,max_length=80)):
        from core.assistant_platform.knowledge import scripture
        return call(lambda:scripture(reference))

    @router.get("/api/platform/metrics")
    def metrics():
        from core.assistant_platform.performance import COORDINATOR
        from core.api.ui_voice import service_status
        return {"api":COORDINATOR.snapshot(),"pcVoice":service_status().get("timing")}

    @router.get("/api/platform/jobs")
    def jobs(): return {"jobs":get().all_jobs()}

    @router.post("/api/platform/jobs")
    def submit(body:AnalysisBody):
        authorize("chat.reply")
        return call(lambda:get().analyze(body.question,priority=body.priority,detailed=body.detailed,authorize=authorize))

    @router.post("/api/platform/jobs/{identifier}/cancel")
    def cancel(identifier:str): return call(lambda:get().jobs.cancel(identifier))

    @router.get("/api/platform/apps")
    def apps(): return {"apps":get().store.list("app")}

    @router.get("/api/platform/apps/suggestions")
    def suggestions():
        from core.assistant_platform.service import app_suggestions
        return {"suggestions":app_suggestions()}

    @router.post("/api/platform/apps",dependencies=[Depends(desktop)])
    def register_app(body:TargetBody):
        from core.assistant_platform.apps import validate_target
        return call(lambda:get().store.put("app",validate_target(body.model_dump())))

    @router.delete("/api/platform/apps/{identifier}",dependencies=[Depends(desktop)])
    def forget_app(identifier:str): return {"removed":get().store.delete("app",identifier)}

    @router.post("/api/platform/apps/{identifier}/launch",dependencies=[Depends(desktop_or_phone_at_pc)])
    def launch(identifier:str):
        service=get()
        result=call(lambda:service.apps.open(identifier))
        service.history.receipt("app.launch",f"Opened {result['name']}",target=identifier)
        return result

    @router.get("/api/platform/workspaces")
    def workspaces(): return {"workspaces":get().store.list("workspace"),"importedDisplay":get().store.get("settings","imported_display")}

    @router.post("/api/platform/workspaces")
    def create_workspace(body:WorkspaceBody):
        from core.assistant_platform.workspaces import validate_workspace
        return call(lambda:get().store.put("workspace",validate_workspace(body.model_dump())))

    @router.patch("/api/platform/workspaces/{identifier}")
    def save_workspace(identifier:str,body:WorkspaceBody):
        from core.assistant_platform.workspaces import validate_workspace
        if body.revision is None: raise HTTPException(422,"Refresh the workspace and supply its revision.")
        return call(lambda:get().store.put("workspace",validate_workspace(body.model_dump()),identifier,revision=body.revision))

    @router.delete("/api/platform/workspaces/{identifier}")
    def delete_workspace(identifier:str): return {"removed":get().store.delete("workspace",identifier)}

    @router.post("/api/platform/workspaces/{identifier}/restore")
    def restore_workspace(identifier:str,body:RestoreBody,key:str|None=Header(default=None,alias="X-ZAENIA-DESKTOP-KEY"),
                          near:str|None=Header(default=None,alias="X-ZAENIA-NEAR-PASS")):
        if body.launchApps: desktop_or_phone_at_pc(key,near); authorize("assistant.apps.launch")
        return call(lambda:get().restore_workspace(identifier,authorize,launch_apps=body.launchApps,revision=body.revision))

    @router.get("/api/platform/projects")
    def projects():
        from core.assistant_platform.projects import project_view
        return {"projects":[project_view(item) for item in get().store.list("project")]}

    @router.post("/api/platform/projects")
    def create_project(body:ProjectBody):
        from core.assistant_platform.projects import project_view,validate_project
        return call(lambda:project_view(get().store.put("project",validate_project(body.model_dump()))))

    @router.post("/api/platform/projects/plan")
    def draft_project(body:ProjectBody):
        authorize("chat.reply")
        return call(lambda:get().draft_plan(body.title,body.goal,authorize))

    @router.patch("/api/platform/projects/{identifier}")
    def save_project(identifier:str,body:ProjectBody):
        from core.assistant_platform.projects import project_view,validate_project
        if body.revision is None: raise HTTPException(422,"Refresh the project and supply its revision.")
        return call(lambda:project_view(get().store.put("project",validate_project(body.model_dump()),identifier,revision=body.revision)))

    @router.delete("/api/platform/projects/{identifier}")
    def delete_project(identifier:str): return {"removed":get().store.delete("project",identifier)}

    @router.get("/api/platform/documents")
    def documents():
        authorize("files.read")
        return {"folders":get().store.list("document_root")}

    @router.get("/api/platform/documents/onedrive-candidates")
    def onedrive_candidates():
        authorize("files.read")
        from core.assistant_platform.documents import onedrive_candidates as find_local
        return {"folders":find_local()}

    @router.get("/api/platform/documents/images")
    def document_images():
        authorize("files.read"); authorize("assistant.documents.read")
        return {"images":get().documents.list_images()}

    @router.post("/api/platform/documents/read-image",dependencies=[Depends(desktop)])
    def read_document_image(body:dict[str,str]):
        authorize("files.read"); authorize("assistant.documents.read"); authorize("memory.read")
        from core.assistant_platform.documents import IMAGE_SUFFIXES, selected_file
        root=get().store.get("document_root",body.get("rootId"))
        if root is None: raise HTTPException(404,"That folder permission no longer exists.")
        def read_selected():
            path=selected_file(root,body.get("path"))
            if path.suffix.casefold() not in IMAGE_SUFFIXES: raise ValueError("Choose an indexed JPG, PNG or WebP image.")
            import hashlib
            with get().store.connection() as db:
                indexed=db.execute("SELECT mtime,size,sha FROM document_files WHERE root_id=? AND path=?",(root["id"],body.get("path"))).fetchone()
            if indexed is None: raise ValueError("Index this image first so ZAE can use the approved reference.")
            metadata=path.stat()
            if (metadata.st_mtime_ns,metadata.st_size)!=(indexed["mtime"],indexed["size"]): raise ValueError("This photo changed; refresh the folder index first.")
            if metadata.st_size>8*1024*1024: raise ValueError("Choose an image under 8 MiB for local nutrition reading.")
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=indexed["sha"]: raise ValueError("This photo changed; refresh the folder index first.")
            from core.assistant_platform.nutrition import read_label
            parsed=read_label(raw)
            from datetime import datetime,timezone
            return {**parsed,"title":path.stem,"sourceName":f"Owner-selected photo · {root['name']}","source":f"{root['name']} / {body.get('path')}",
                    "servingSize":"","fromLabel":True,"checkedAt":datetime.now(timezone.utc).isoformat(timespec="seconds")}
        return call(read_selected)

    @router.post("/api/platform/documents",dependencies=[Depends(desktop)])
    def add_documents(body:TargetBody):
        from core.assistant_platform.documents import register_root
        return call(lambda:get().store.put("document_root",register_root(body.model_dump())))

    @router.post("/api/platform/documents/{identifier}/index",dependencies=[Depends(desktop)])
    def index_documents(identifier:str):
        authorize("assistant.documents.read"); authorize("files.read")
        service=get()
        def index(context):
            authorize("assistant.documents.read"); authorize("files.read")
            return service.documents.index(identifier,context)
        return call(lambda:service.jobs.submit("Index selected documents",index))

    @router.delete("/api/platform/documents/{identifier}",dependencies=[Depends(desktop)])
    def forget_documents(identifier:str): return {"removed":get().documents.remove_root(identifier)}

    @router.get("/api/platform/documents/search")
    def search(q:str=Query(min_length=1,max_length=500)):
        authorize("files.read")
        return call(lambda:{"results":get().documents.search(q)})

    @router.post("/api/platform/documents/open",dependencies=[Depends(desktop)])
    def open_document(body:dict[str,str]):
        authorize("files.read"); authorize("assistant.apps.launch"); authorize("assistant.documents.read")
        from core.assistant_platform.documents import selected_file
        root=get().store.get("document_root",body.get("rootId"))
        if root is None: raise HTTPException(404,"That folder permission no longer exists.")
        def open_selected():
            from core.assistant_platform.apps import AppLauncher
            path=selected_file(root,body.get("path"))
            return AppLauncher._launch({"kind":"file","path":str(path)})
        return call(open_selected)

    @router.get("/api/platform/approvals")
    def approvals(): return get().history.policy()

    @router.put("/api/platform/approvals",dependencies=[Depends(desktop)])
    def save_approvals(body:dict[str,Any]): return call(lambda:get().history.save_policy(body))

    @router.get("/api/platform/actions")
    def actions(): return {"actions":get().history.public()}

    @router.post("/api/platform/actions/{identifier}/undo",dependencies=[Depends(desktop)])
    def undo(identifier:str): return call(lambda:get().history.undo(identifier,authorize))

    @router.get("/api/platform/health")
    def health():
        from core.assistant_platform.health import inspect_health
        return inspect_health()

    @router.post("/api/platform/health/recover",dependencies=[Depends(desktop)])
    def recover(body:dict[str,str]):
        if body!={"action":"warm_model"}: raise HTTPException(422,"Choose the fixed local model warm-up action; voice/API restart uses the desktop controls.")
        from core.assistant_platform.health import recover_model
        return call(recover_model)

    @router.get("/api/platform/readiness")
    def readiness():
        from core.assistant_platform.health import readiness
        return readiness()

    @router.get("/api/platform/profile/requests")
    def profile_requests(): return {"requests":get().store.list("profile_request")[:20]}

    @router.post("/api/platform/profile/requests",dependencies=[Depends(desktop)])
    def profile_request(body:ProfileBody):
        from core.assistant_platform.profiles import ui_preferences
        from core.foundation.security.io import reject_link
        path=Path(body.path)
        if body.mode not in {"export","restore"} or body.restoreMode not in {"merge","overwrite_conflicts"}:
            raise HTTPException(422,"Choose export/restore and a supported merge mode.")
        if not path.is_absolute() or path.suffix!=".zae-profile" or str(path).startswith(("\\\\","//")) or not path.parent.is_dir():
            raise HTTPException(422,"Choose an absolute .zae-profile path in an existing folder.")
        if body.mode=="export" and path.exists(): raise HTTPException(409,"Choose a new filename; exports never overwrite a backup.")
        if body.mode=="restore" and (not path.is_file() or path.stat().st_size>40*1024*1024): raise HTTPException(422,"Choose an existing supported profile under 40 MiB.")
        return call(lambda:(reject_link(path),get().store.put("profile_request",{**body.model_dump(),"uiSettings":ui_preferences(body.uiSettings),"status":"pending"}))[1])

    @router.post("/api/platform/snapshots",dependencies=[Depends(desktop)])
    def snapshot():
        from core.assistant_platform.releases import capture_release
        return call(lambda:capture_release(get().store))

    from core.api.operator_routes import create_operator_router
    router.include_router(create_operator_router(get,authorize,desktop,call))
    from core.api.notes_routes import create_notes_router
    router.include_router(create_notes_router(get,call))
    from core.api.personal_tools_routes import create_personal_tools_router
    router.include_router(create_personal_tools_router(get,call))
    from core.api.personal_tools_routes import create_completion_router
    router.include_router(create_completion_router(get,call))
    return router
