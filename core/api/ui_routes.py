"""API routes behind the ZÆNIA UI's functions: tasks, calendar, chat history,
speech, the system brief and the file tools.

Every route depends on the API token check (require_api_authentication), which
also asks the client gate whether the operation is allowed. OPERATION_PATTERNS
tells that check which operation each request is. Applying a file change also
needs the desktop approval key (desktop_key.py).
"""
from __future__ import annotations

import re
import hashlib
from datetime import date
from typing import Any, Callable, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.foundation.security.audit import audit

ID = r"[A-Za-z0-9_-]{1,100}"
OPERATION_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = tuple(
    (method, re.compile(f"^{pattern}$"), operation) for method, pattern, operation in (
        ("GET", r"/api/tasks", "tasks.read"),
        ("POST", r"/api/tasks", "ui.tasks.write"),
        ("POST", r"/api/tasks/import", "ui.tasks.write"),
        ("PATCH", rf"/api/tasks/{ID}", "ui.tasks.write"),
        ("DELETE", rf"/api/tasks/{ID}", "ui.tasks.delete"),
        ("GET", r"/api/calendar", "calendar.read"),
        ("PUT", r"/api/calendar/duty-status", "ui.calendar.write"),
        ("POST", r"/api/calendar/events", "ui.calendar.write"),
        ("DELETE", rf"/api/calendar/events/{ID}", "ui.calendar.delete"),
        ("GET", r"/api/chat/history", "chat.history.read"),
        ("POST", r"/api/chat/stream", "chat.reply"),
        ("POST", r"/api/chat/cancel", "chat.reply"),
        ("POST", r"/api/speak", "chat.speak"),
        ("GET", r"/api/system/brief", "status.read"),
        ("GET", r"/api/files/recent", "files.read"),
        ("GET", r"/api/files/list", "files.read"),
        ("GET", r"/api/files/content", "files.read"),
        ("PUT", r"/api/files/content", "files.desktop.apply"),
        ("GET", r"/api/files/proposals", "files.read"),
        ("POST", r"/api/files/proposals", "files.propose"),
        ("GET", r"/api/files/proposals/[0-9a-f]{32}", "files.read"),
        ("POST", r"/api/files/proposals/[0-9a-f]{32}/approve", "files.desktop.apply"),
        ("POST", r"/api/files/proposals/[0-9a-f]{32}/reject", "files.propose"),
        ("GET", r"/api/desktop/check", "files.read"),
        ("POST", r"/api/voice/transcribe", "voice.transcribe"),
        ("POST", r"/api/voice/dictation", "memory.write"),
        ("POST", r"/api/research/notebook/link/[0-9a-f]{32}", "memory.write"),
        ("GET", r"/api/voice/status", "status.read"),
        ("GET", r"/api/weather/now", "status.read"),
        ("GET", r"/api/screen/watch", "status.read"),
        ("GET", r"/api/gaming/coach", "status.read"),
        ("GET", r"/api/news/tech", "status.read"),
        ("GET", r"/api/security/activity", "status.read"),
        ("GET", r"/api/security/checks", "status.read"),
        ("GET", r"/api/security/checks/\d{8}T\d{6}Z", "status.read"),
        ("POST", r"/api/security/checks", "status.read"),
        # The locked Security tab (security_unlock.py): desktop key plus an unlock session.
        ("GET", r"/api/security/summary", "status.read"),
        ("GET", r"/api/status/bar", "status.read"),
        ("POST", r"/api/security/unlock", "status.read"),
        ("GET", r"/api/security/unlock/[0-9a-f]{32}", "status.read"),
        ("POST", r"/api/security/session", "status.read"),
        ("POST", r"/api/security/session/lock", "status.read"),
        ("POST", r"/api/security/full", "status.read"),
        # The Vault (vault.py): desktop key plus a live Security unlock session, like /api/security/full.
        ("POST", r"/api/vault/list", "status.read"),
        ("POST", r"/api/vault/item", "status.read"),
        ("POST", r"/api/vault/save", "status.read"),
        ("POST", r"/api/vault/delete", "status.read"),
        ("GET", r"/api/email/important", "notifications.read"),
        ("POST", r"/api/email/check", "notifications.read"),
        ("POST", r"/api/news/tech/refresh", "status.read"),
        ("POST", r"/api/screen/watch", "assistant.desktop.manage"),
        ("POST", r"/api/gaming/coach", "assistant.desktop.manage"),
        # Code Doctor, Suggestions, Arena, source search (tools_routes.py).
        ("POST", r"/api/code/scan", "files.read"),
        ("POST", r"/api/code/explain", "chat.reply"),
        ("POST", r"/api/code/fix", "chat.reply"),
        ("POST", r"/api/code/apply", "files.desktop.apply"),
        ("GET", r"/api/code/search", "files.read"),
        ("GET", r"/api/suggestions", "status.read"),
        ("POST", r"/api/suggestions/think", "chat.reply"),
        ("POST", r"/api/suggestions/[0-9a-f]{32}", "ui.tasks.write"),
        ("GET", r"/api/arena", "status.read"),
        ("POST", r"/api/arena/round", "chat.reply"),
        ("POST", r"/api/arena/vote", "status.read"),
        ("POST", r"/api/arena/brain", "assistant.desktop.manage"),
        # Reminders, Protocols, Self-Sustain (selfcare_routes.py).
        ("GET", r"/api/reminders", "tasks.read"),
        ("POST", r"/api/reminders", "ui.tasks.write"),
        ("DELETE", r"/api/reminders/[0-9a-f]{32}", "ui.tasks.write"),
        ("GET", r"/api/protocols", "status.read"),
        ("POST", r"/api/protocols", "assistant.desktop.manage"),
        ("PUT", r"/api/protocols/[0-9a-f]{32}", "assistant.desktop.manage"),
        ("DELETE", r"/api/protocols/[0-9a-f]{32}", "assistant.desktop.manage"),
        ("GET", r"/api/selfcare", "status.read"),
        ("GET", r"/api/push/key", "status.read"),
        ("POST", r"/api/push/(?:subscribe|unsubscribe)", "memory.write"),
        ("POST", r"/api/push/test", "status.read"),
        ("POST", r"/api/selfcare/backup", "assistant.desktop.manage"),
        ("POST", r"/api/selfcare/watchdog", "assistant.desktop.manage"),
        # Research (research_routes.py): public sources are reads; the notebook is memory; her analysis is a chat reply.
        ("GET", r"/api/research/library", "status.read"),
        ("POST", r"/api/research/library/read", "status.read"),
        ("GET", r"/api/research/article", "status.read"),
        ("GET", r"/api/research/history", "status.read"),
        ("GET", r"/api/research/history/samples", "status.read"),
        ("GET", r"/api/research/worldnews", "status.read"),
        ("GET", r"/api/research/scripture", "memory.read"),
        ("GET", r"/api/research/scripture/search", "memory.read"),
        ("GET", r"/api/research/scripture/marks", "memory.read"),
        ("POST", r"/api/research/scripture/marks", "memory.write"),
        ("DELETE", r"/api/research/scripture/marks/[0-9a-f]{32}", "memory.write"),
        ("POST", r"/api/research/analyze", "chat.reply"),
        ("POST", r"/api/research/translate", "chat.reply"),
        ("GET", r"/api/research/agent", "memory.read"),
        ("GET", r"/api/pc/specs", "status.read"),
        ("POST", r"/api/research/agent", "chat.reply"),
        ("DELETE", r"/api/research/agent/[0-9a-f]{32}", "memory.write"),
        ("POST", r"/api/research/watch", "memory.write"),
        ("POST", r"/api/research/watch/[0-9a-f]{32}/check", "chat.reply"),
        ("DELETE", r"/api/research/watch/[0-9a-f]{32}", "memory.write"),
        ("GET", r"/api/research/translate/languages", "status.read"),
        ("GET", r"/api/research/notebook", "memory.read"),
        ("POST", r"/api/research/notebook", "memory.write"),
        ("GET", r"/api/research/notebook/[0-9a-f]{32}", "memory.read"),
        ("DELETE", r"/api/research/notebook/[0-9a-f]{32}", "memory.write"),
        ("PUT", r"/api/research/notebook/[0-9a-f]{32}/notes", "memory.write"),
        ("POST", r"/api/research/notebook/[0-9a-f]{32}/sources", "memory.write"),
        ("DELETE", r"/api/research/notebook/[0-9a-f]{32}/sources/[0-9a-f]{32}", "memory.write"),
    )
)


def operation_for(method: str, path: str) -> str | None:
    for allowed_method, pattern, operation in OPERATION_PATTERNS:
        if method == allowed_method and pattern.match(path):
            return operation
    return None


# ------------------------------------------------------------- bodies

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=400)
    priority: str = Field(default="Normal", max_length=20)
    deadline: str | None = Field(default=None, max_length=40)
    fromConversation: bool = False


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, max_length=400)
    priority: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=20)
    deadline: str | None = Field(default=None, max_length=40)
    archived: bool | None = None


class TaskImport(BaseModel):
    tasks: list[dict[str, Any]]  # at most 500, checked in ui_tasks.import_tasks


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: str = Field(min_length=10, max_length=10)
    time: str = Field(min_length=3, max_length=5)
    recurrence: str = Field(default="none", max_length=10)
    fromConversation: bool = False


class SecuritySession(BaseModel):
    session: str = Field(min_length=20, max_length=100)


class VaultRequest(SecuritySession):
    id: str = Field(default="", max_length=32)


class VaultSave(SecuritySession):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(default="", max_length=2_000_000)
    name: str = Field(default="", max_length=200)
    data: str = Field(default="", max_length=21_000_000)
    mime: str = Field(default="", max_length=100)


class PhotoHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class SharedFile(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    data: str = Field(min_length=1, max_length=21_000_000)  # base64, 15 MB file


class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    requestId: str = Field(min_length=8, max_length=64)
    conversationId: str | None = Field(default=None, min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    images: list[str] = Field(default_factory=list, max_length=4)
    photoHistory: list[PhotoHistoryTurn] = Field(default_factory=list, max_length=6)
    files: list[SharedFile] = Field(default_factory=list, max_length=4)


class DutyStatusUpdate(BaseModel):
    model_config={'extra':'forbid'}
    date: str = Field(min_length=10,max_length=10)
    status: Literal['on_duty','off_duty','class','leave'] | None
    revision: int = Field(ge=0,strict=True)


class GameCoachRequest(BaseModel):
    model_config = {"extra": "forbid"}
    on: bool


class ScreenWatchRequest(BaseModel):
    model_config = {'extra': 'forbid'}
    on: bool
    monitor: int | None = Field(default=None, ge=1, le=8)


class ChatCancelRequest(BaseModel):
    requestId: str = Field(min_length=8, max_length=64)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class VoiceClip(BaseModel):
    audio: str = Field(min_length=1, max_length=900_000)
    wake: bool = False


class FileSave(BaseModel):
    path: str = Field(min_length=1, max_length=400)
    baseSha256: str = Field(min_length=64, max_length=64)
    text: str = Field(max_length=600_000)


class FileProposal(FileSave):
    note: str = Field(default="", max_length=300)


# ------------------------------------------------------------- router

def create_ui_router(require_api_authentication: Callable[..., Any], mode: Callable[[], str], *, authorize_operation: Callable[[str], Any] | None = None) -> APIRouter:
    router = APIRouter(tags=["ui"], dependencies=[Depends(require_api_authentication)])

    def require_desktop(x_zaenia_desktop_key: str | None = Header(default=None, alias="X-ZAENIA-DESKTOP-KEY")) -> None:
        from core.api.desktop_key import is_paired, verify
        if not is_paired():
            raise HTTPException(403, "The desktop app isn't paired yet. At the PC run: python -m core.api.server pair-desktop")
        if not verify(x_zaenia_desktop_key):
            raise HTTPException(403, "Only the ZÆNIA desktop app on the PC can apply file changes.")

    # ---- tasks
    from core.api import ui_tasks

    def remember_saved_action(answer: str) -> None:
        # Only call after the independently authorized handler saved its result.
        # An unavailable conversation log must not turn a saved action into an
        # apparent failure and invite a duplicate submission.
        try:
            from core.api.ui_chat_stream import _brain
            _brain().remember_action_result(answer=answer)
        except Exception:
            pass

    def task_call(action: Callable[[], Any]) -> Any:
        try:
            return action()
        except ui_tasks.TaskNotFound as error:
            raise HTTPException(404, "That task no longer exists.") from error
        except ui_tasks.TaskError as error:
            raise HTTPException(422, str(error)) from error
        except TimeoutError as error:
            raise HTTPException(503, "The task list is busy. Try again.") from error

    @router.get("/api/tasks")
    def tasks_list() -> dict[str, Any]:
        return {"tasks": task_call(ui_tasks.list_tasks)}

    @router.post("/api/tasks")
    def tasks_create(body: TaskCreate) -> dict[str, Any]:
        tasks, task = task_call(lambda: ui_tasks.create_task(body.title, body.priority, body.deadline))
        audit("ui.task_changed", operation="ui.tasks.write", reason_code="created")
        if body.fromConversation:
            remember_saved_action("Created task " + repr(task["title"]) + " in your ZÆNIA task list (ID: " + task["id"] + "). No notification was scheduled.")
        return {"tasks": tasks, "task": task}

    @router.post("/api/tasks/import")
    def tasks_import(body: TaskImport) -> dict[str, Any]:
        tasks, added = task_call(lambda: ui_tasks.import_tasks(body.tasks))
        audit("ui.task_changed", operation="ui.tasks.write", reason_code="imported")
        return {"tasks": tasks, "added": added}

    @router.patch("/api/tasks/{task_id}")
    def tasks_update(task_id: str, body: TaskPatch) -> dict[str, Any]:
        # Pydantic 2 (model_dump) or 1 (dict): only the fields the UI sent.
        patch = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
        tasks, task = task_call(lambda: ui_tasks.update_task(task_id, patch))
        audit("ui.task_changed", operation="ui.tasks.write", reason_code="updated")
        return {"tasks": tasks, "task": task}

    @router.delete("/api/tasks/{task_id}")
    def tasks_delete(task_id: str) -> dict[str, Any]:
        tasks = task_call(lambda: ui_tasks.delete_task(task_id))
        audit("ui.task_changed", operation="ui.tasks.delete", reason_code="deleted")
        return {"tasks": tasks}

    # ---- calendar
    from core.api import ui_calendar

    @router.get("/api/calendar")
    def calendar_read(start: str | None = Query(default=None, max_length=10), days: int = Query(default=42, ge=1, le=62)) -> dict[str, Any]:
        from core.calendar_context.duty_status import DutyStatusError
        try:
            first = date.fromisoformat(start) if start else ui_calendar.today()
        except ValueError as error:
            raise HTTPException(422, "Use a date like 2026-10-15.") from error
        try:
            return ui_calendar.read_calendar(first, days)
        except ui_calendar.CalendarError as error:
            raise HTTPException(422, str(error)) from error
        except DutyStatusError as error:
            raise HTTPException(503,str(error)) from error

    @router.put('/api/calendar/duty-status')
    def duty_status_update(body:DutyStatusUpdate):
        from core.calendar_context.duty_status import set_day,DutyStatusConflict,DutyStatusError
        try:result=set_day(body.date,body.status,body.revision)
        except DutyStatusConflict as error:raise HTTPException(409,str(error)) from error
        except DutyStatusError as error:raise HTTPException(422,str(error)) from error
        except TimeoutError as error:raise HTTPException(503,'Duty status is busy; refresh before retrying.') from error
        audit('ui.duty_status_changed',operation='ui.calendar.write',reason_code='owner_override_saved' if body.status else 'owner_override_cleared')
        return result

    @router.post("/api/calendar/events")
    def calendar_add(body: EventCreate) -> dict[str, Any]:
        try:
            event = ui_calendar.add_event(body.title, body.date, body.time, body.recurrence)
        except ui_calendar.CalendarError as error:
            raise HTTPException(422, str(error)) from error
        audit("ui.calendar_changed", operation="ui.calendar.write", reason_code="event_added")
        if body.fromConversation:
            remember_saved_action("Added " + repr(event["title"]) + " to your ZÆNIA calendar at " + event["start"] + " (America/Los_Angeles; ID: " + event["id"] + "). This saved event does not confirm phone or spoken alert delivery.")
        return {"event": event}

    @router.delete("/api/calendar/events/{event_id}")
    def calendar_delete(event_id: str) -> dict[str, Any]:
        try:
            ui_calendar.delete_event(event_id)
        except ui_calendar.EventNotFound as error:
            raise HTTPException(404, "Only ZÆNIA events can be deleted here; Google events are read-only for now.") from error
        audit("ui.calendar_changed", operation="ui.calendar.delete", reason_code="event_deleted")
        return {"deleted": event_id}

    # ---- conversation
    from core.api import ui_conversation

    @router.get("/api/chat/history")
    def chat_history(limit: int = Query(default=40, ge=1, le=200)) -> dict[str, Any]:
        return {"messages": ui_conversation.read_history(limit)}

    from core.api import ui_chat_stream

    @router.post("/api/chat/stream")
    def chat_stream(body: ChatStreamRequest, request: Request):
        message = body.message.strip()
        if not message:
            raise HTTPException(422, "Chat message cannot be empty.")
        if not ui_chat_stream.REQUEST_ID.match(body.requestId):
            raise HTTPException(422, "Invalid request id.")
        from core.api.photo_chat import normalize_photos
        try:
            images = normalize_photos(body.images)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        from core.api.chat_files import SharedFileError, decode_files
        try:
            files = decode_files([item.model_dump() for item in body.files])
        except SharedFileError as error:
            raise HTTPException(422, str(error)) from error
        principal = request.headers.get("X-ZAENIA-API-TOKEN") or request.headers.get("X-ZAENIA-DESKTOP-KEY") or ""
        conversation = hashlib.sha256(principal.encode("utf-8")).hexdigest() + ":" + body.conversationId if body.conversationId else None
        return StreamingResponse(
            ui_chat_stream.stream(message, body.requestId, authorize=authorize_operation, conversation_id=conversation,
                                  images=images, photo_history=[turn.model_dump() for turn in body.photoHistory], files=files),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @router.post("/api/chat/cancel")
    def chat_cancel(body: ChatCancelRequest) -> dict[str, Any]:
        return {"cancelled": ui_chat_stream.cancel(body.requestId)}

    @router.post("/api/speak")
    def speak(body: SpeakRequest) -> dict[str, Any]:
        try:
            return ui_conversation.synthesize(body.text)
        except ui_conversation.SpeechError as error:
            raise HTTPException(503, str(error)) from error

    # ---- system brief
    @router.get("/api/system/brief")
    def system_brief() -> dict[str, Any]:
        from core.api.system_brief import build_system_brief
        return build_system_brief(mode())

    # ---- voice
    from core.api import ui_voice

    @router.post("/api/voice/transcribe")
    def voice_transcribe(body: VoiceClip) -> dict[str, Any]:
        try:
            return ui_voice.transcribe(body.audio, body.wake)
        except ui_voice.VoiceError as error:
            raise HTTPException(422, str(error)) from error
        except ui_voice.VoiceUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @router.post("/api/voice/dictation")
    def voice_dictation(body: VoiceClip) -> dict[str, Any]:
        """Live transcripts for notes: words only (any speaker, e.g. a lecture), never a command or a chat turn."""
        try:
            return {"text": ui_voice.recognize(ui_voice._decode(body.audio))}
        except ui_voice.VoiceError as error:
            raise HTTPException(422, str(error)) from error
        except ui_voice.VoiceUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except Exception as error:
            raise HTTPException(503, f"Speech recognition failed ({type(error).__name__}).") from error

    @router.get("/api/voice/status")
    def voice_status() -> dict[str, Any]:
        return ui_voice.service_status()

    @router.get("/api/email/important")
    def email_important(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        from core.email_watch import gmail
        from core.email_watch.service import email_watch
        return {**email_watch().recent(limit), **{"setup": gmail.status()}}

    @router.post("/api/email/check")
    def email_check() -> dict[str, Any]:
        from core.email_watch.service import email_watch
        try:
            result = email_watch().check()
        except Exception as error:
            raise HTTPException(503, f"Email check failed ({type(error).__name__}).") from error
        return {**result, **email_watch().recent(20)}

    @router.get("/api/security/activity")
    def security_activity(limit: int = Query(default=60, ge=1, le=300)) -> dict[str, Any]:
        from core.api.security_activity import recent_activity
        return recent_activity(limit=limit)

    # Security self-check: read-only, isolated tests plus live-setup checks (core/api/security_check.py).
    @router.get("/api/security/checks")
    def security_check_state() -> dict[str, Any]:
        from core.api.security_check import security_checks
        return security_checks().state()

    @router.get("/api/security/checks/{report_id}")
    def security_check_report(report_id: str) -> dict[str, Any]:
        from core.api.security_check import load_report
        report = load_report(report_id)
        if report is None:
            raise HTTPException(404, "No such security report.")
        return report

    @router.post("/api/security/checks")
    def security_check_run() -> dict[str, Any]:
        from core.api.security_check import security_checks
        result = security_checks().start_check("manual", mode())
        if not result["started"] and result.get("retryAfter"):
            raise HTTPException(429, result["reason"])
        return {**result, **security_checks().state()}

    # Status tab: the overall security level only; the details are on the locked Security tab.
    @router.get("/api/status/bar")
    def status_bar() -> dict[str, Any]:
        from core.api.status_bar import status_bar as read
        return read(mode())

    @router.get("/api/security/summary")
    def security_summary() -> dict[str, Any]:
        from core.api.security_posture import summary
        return summary(mode())

    def require_security_desktop(x_zaenia_desktop_key: str | None = Header(default=None, alias="X-ZAENIA-DESKTOP-KEY")) -> None:
        from core.api.desktop_key import is_paired, verify
        if not is_paired():
            raise HTTPException(403, "The desktop app isn't paired yet. At the PC run: python -m core.api.server pair-desktop")
        if not verify(x_zaenia_desktop_key):
            raise HTTPException(403, "The Security tab opens only in the ZÆNIA desktop app on the PC.")

    def security_session(body: SecuritySession, *, touch: bool = False) -> dict[str, Any]:
        from core.api.security_unlock import security_unlock
        session = security_unlock().check(body.session, touch=touch)
        if session is None:
            raise HTTPException(401, "The Security tab is locked. Unlock it with your passkey or your spoken phrase.")
        return session

    @router.post("/api/security/unlock", dependencies=[Depends(require_security_desktop)])
    def security_unlock_begin() -> dict[str, Any]:
        from core.api.security_unlock import security_unlock
        return security_unlock().begin()

    @router.get("/api/security/unlock/{request_id}", dependencies=[Depends(require_security_desktop)])
    def security_unlock_poll(request_id: str) -> dict[str, Any]:
        from core.api.security_unlock import security_unlock
        return security_unlock().poll(request_id)

    @router.post("/api/security/session", dependencies=[Depends(require_security_desktop)])
    def security_session_touch(body: SecuritySession) -> dict[str, Any]:
        """Activity on the open tab: restarts its 10-minute idle timer."""
        return security_session(body, touch=True)

    @router.post("/api/security/session/lock", dependencies=[Depends(require_security_desktop)])
    def security_session_lock(body: SecuritySession) -> dict[str, Any]:
        from core.api.security_unlock import security_unlock
        security_unlock().lock_session(body.session)
        return {"locked": True}

    @router.post("/api/security/full", dependencies=[Depends(require_security_desktop)])
    def security_full(body: SecuritySession, request: Request) -> dict[str, Any]:
        session = security_session(body)
        from core.api.security_activity import recent_activity
        from core.api.security_posture import full_view
        mobile_sessions = None
        auth = getattr(request.app.state, "mobile_auth", None)
        if auth is not None:
            with auth.lock:
                auth._purge()
                mobile_sessions = len(auth.sessions)
        return {**full_view(mode(), mobile_sessions=mobile_sessions), "activity": recent_activity(limit=300), "session": session}

    @router.post("/api/vault/list", dependencies=[Depends(require_security_desktop)])
    def vault_list(body: VaultRequest) -> dict[str, Any]:
        security_session(body, touch=True)
        from core.api.vault import vault
        return {"items": vault().list()}

    @router.post("/api/vault/item", dependencies=[Depends(require_security_desktop)])
    def vault_item(body: VaultRequest) -> dict[str, Any]:
        security_session(body, touch=True)
        from core.api.vault import vault
        try:
            item = vault().get(body.id)
        except KeyError as error:
            raise HTTPException(404, "No such vault item.") from error
        audit("vault.item_opened", operation="vault.read", reason_code="owner_session")
        return item

    @router.post("/api/vault/save", dependencies=[Depends(require_security_desktop)])
    def vault_save(body: VaultSave) -> dict[str, Any]:
        security_session(body, touch=True)
        from core.api.vault import vault
        try:
            saved = vault().save(title=body.title, text=body.text, name=body.name, data_b64=body.data, mime=body.mime)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        audit("vault.item_saved", operation="vault.write", reason_code="owner_session")
        return saved

    @router.post("/api/vault/delete", dependencies=[Depends(require_security_desktop)])
    def vault_delete(body: VaultRequest) -> dict[str, Any]:
        security_session(body, touch=True)
        from core.api.vault import vault
        try:
            vault().delete(body.id)
        except KeyError as error:
            raise HTTPException(404, "No such vault item.") from error
        audit("vault.item_deleted", operation="vault.write", reason_code="owner_session")
        return {"ok": True}

    @router.get("/api/news/tech")
    def tech_news_headlines(q: str = Query(default="", max_length=200), topic: str = Query(default="", max_length=40),
                            limit: int = Query(default=20, ge=1, le=50)) -> dict[str, Any]:
        from core.tech_news.service import tech_news
        return tech_news().headlines(query=q, topic=topic, limit=limit)

    @router.post("/api/news/tech/refresh")
    def tech_news_refresh() -> dict[str, Any]:
        from core.tech_news.service import tech_news
        tech_news().refresh()
        return tech_news().headlines(limit=20)

    @router.get("/api/screen/watch")
    def screen_watch_status() -> dict[str, Any]:
        from core.assistant_platform.screen_watch import watcher
        return watcher().status()

    @router.post("/api/screen/watch")
    def screen_watch(body: ScreenWatchRequest) -> dict[str, Any]:
        from core.assistant_platform.screen_watch import watcher
        try:
            result = watcher().start(body.monitor) if body.on else watcher().stop()
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        audit("assistant.screen_watch", operation="assistant.desktop.manage", reason_code="started" if body.on else "stopped")
        return result

    @router.get("/api/gaming/coach")
    def gaming_coach_status() -> dict[str, Any]:
        from core.assistant_platform.game_coach import game_coach
        return game_coach().status()

    @router.post("/api/gaming/coach")
    def gaming_coach(body: GameCoachRequest) -> dict[str, Any]:
        from core.assistant_platform.game_coach import game_coach
        result = game_coach().set_enabled(body.on)
        audit("assistant.game_coach", operation="assistant.desktop.manage", reason_code="on" if body.on else "off")
        return result

    @router.get("/api/weather/now")
    def weather_now() -> dict[str, Any]:
        from core.api.ui_weather import current_weather
        try:
            return current_weather()
        except Exception as error:
            raise HTTPException(503, f"Weather unavailable ({type(error).__name__}).") from error

    # ---- files
    from core.api import ui_files

    def file_call(action: Callable[[], Any]) -> Any:
        try:
            return action()
        except ui_files.FileNotAvailable as error:
            raise HTTPException(404, "That file or change isn't there.") from error
        except ui_files.FileConflict as error:
            raise HTTPException(409, str(error)) from error
        except ui_files.FileToolError as error:
            raise HTTPException(422, str(error)) from error
        except TimeoutError as error:
            raise HTTPException(503, "The file tools are busy. Try again.") from error

    @router.get("/api/files/recent")
    def files_recent(limit: int = Query(default=40, ge=1, le=100)) -> dict[str, Any]:
        return {"files": file_call(lambda: ui_files.recent_files(limit))}

    @router.get("/api/files/list")
    def files_list(dir: str = Query(default="", max_length=400)) -> dict[str, Any]:
        return file_call(lambda: ui_files.list_dir(dir))

    @router.get("/api/files/content")
    def files_read(path: str = Query(..., min_length=1, max_length=400)) -> dict[str, Any]:
        return file_call(lambda: ui_files.read_file(path))

    @router.put("/api/files/content", dependencies=[Depends(require_desktop)])
    def files_save(body: FileSave) -> dict[str, Any]:
        result = file_call(lambda: ui_files.save_from_desktop(body.path, body.baseSha256, body.text))
        audit("ui.file_changed", operation="files.desktop.apply", reason_code="desktop_save")
        return result

    @router.get("/api/files/proposals")
    def proposals_list() -> dict[str, Any]:
        return {"proposals": file_call(ui_files.list_proposals)}

    @router.post("/api/files/proposals")
    def proposals_create(body: FileProposal) -> dict[str, Any]:
        result = file_call(lambda: ui_files.create_proposal(body.path, body.baseSha256, body.text, body.note))
        audit("ui.file_proposed", operation="files.propose", reason_code="proposal_created")
        return result

    @router.get("/api/files/proposals/{proposal_id}")
    def proposals_get(proposal_id: str) -> dict[str, Any]:
        return file_call(lambda: ui_files.get_proposal(proposal_id))

    @router.post("/api/files/proposals/{proposal_id}/approve", dependencies=[Depends(require_desktop)])
    def proposals_approve(proposal_id: str) -> dict[str, Any]:
        result = file_call(lambda: ui_files.approve_proposal(proposal_id))
        audit("ui.file_changed", operation="files.desktop.apply", reason_code="proposal_applied")
        return result

    @router.post("/api/files/proposals/{proposal_id}/reject")
    def proposals_reject(proposal_id: str) -> dict[str, Any]:
        result = file_call(lambda: ui_files.reject_proposal(proposal_id))
        audit("ui.file_proposed", operation="files.propose", reason_code="proposal_rejected")
        return result

    @router.get("/api/desktop/check")
    def desktop_check(x_zaenia_desktop_key: str | None = Header(default=None, alias="X-ZAENIA-DESKTOP-KEY")) -> dict[str, Any]:
        from core.api.desktop_key import is_paired, verify
        return {"paired": is_paired(), "approver": verify(x_zaenia_desktop_key)}

    return router
