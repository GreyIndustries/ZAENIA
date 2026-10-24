from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from core.api.models import (
    CarPlayAnswerRequest, CarPlayBriefingResponse,
    CarPlayConnectionRequest, CarPlayPlayedRequest,
)
from core.carplay_audio.carplay_audio import get_default_audio_path
from core.carplay_trigger.briefing_session import BriefingSessions, SessionConflict, SessionNotFound


AuthDependency = Callable[..., Any]


def create_carplay_router(auth_dependency: AuthDependency, *, handoff_loader=None) -> APIRouter:
    router = APIRouter(tags=["briefing"],
                       dependencies=[Depends(auth_dependency)])
    service = None

    def sessions() -> BriefingSessions:
        nonlocal service
        if service is None:
            service = BriefingSessions(handoff_loader=handoff_loader)
        return service

    def failure(error: Exception):
        if isinstance(error, SessionNotFound):
            raise HTTPException(404, str(error)) from error
        if isinstance(error, SessionConflict):
            raise HTTPException(409, str(error)) from error
        print("CarPlay session error:", repr(error))
        raise HTTPException(500, "ZÆNIA could not complete the CarPlay request.") from error

    @router.post("/api/briefing", response_model=CarPlayBriefingResponse)
    @router.post("/api/carplay/briefing", response_model=CarPlayBriefingResponse)
    def generate_briefing(http_request: Request, request: CarPlayConnectionRequest | None = None):
        try:
            if http_request.url.path == "/api/briefing":
                result = sessions().start(request.request_id if request else None, force_full=True)
                return dict(result, audio_endpoint="/api/briefing/audio?session_id=" + result["session_id"])
            return sessions().start(request.request_id if request else None)
        except Exception as error:
            failure(error)

    @router.post("/api/briefing/answer", response_model=CarPlayBriefingResponse)
    @router.post("/api/carplay/answer", response_model=CarPlayBriefingResponse)
    def answer_departure(http_request: Request, request: CarPlayAnswerRequest):
        try:
            result = sessions().start(parent_id=request.session_id, answer=request.answer)
            if http_request.url.path == "/api/briefing/answer":
                return dict(result, audio_endpoint="/api/briefing/audio?session_id=" + result["session_id"])
            return result
        except Exception as error:
            failure(error)

    @router.post("/api/briefing/played")
    @router.post("/api/carplay/played")
    def record_playback(request: CarPlayPlayedRequest):
        try:
            return sessions().played(request.session_id)
        except Exception as error:
            failure(error)

    @router.get("/api/briefing/audio")
    @router.get("/api/carplay/audio")
    def get_latest_audio(session_id: str | None = None):
        try:
            if session_id:
                session = sessions().get(session_id)
                sessions().require_recent(session)
                audio_path = Path(session["audio_path"])
            else:
                # Compatibility with the old shortcut. The new shortcut always sends an ID.
                with sessions().connect() as db:
                    row = db.execute("SELECT id FROM sessions ORDER BY rowid DESC LIMIT 1").fetchone()
                audio_path = Path(sessions().get(row[0])["audio_path"]) if row else get_default_audio_path()
            if not audio_path.is_file() or audio_path.stat().st_size <= 0:
                raise SessionNotFound("No generated CarPlay audio is available.")
            return FileResponse(audio_path, media_type="audio/wav", filename="CarStartupAudio.wav",
                                headers={"Cache-Control": "no-store"})
        except Exception as error:
            failure(error)

    return router
