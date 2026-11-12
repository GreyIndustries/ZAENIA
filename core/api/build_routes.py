"""Build requests (build_helper.py) and ZAE's nightly improvement ideas (build_ideas.py). Operations are in ui_routes.ROUTES.

Writing a brief or rejecting is allowed wherever chat is. Starting needs the desktop app or the phone's near-PC pass.
Approving, undoing and rebuilding change the live app, so they need the paired desktop app on the PC. A server
restart after an approved change is done by the desktop app (restart_server), not from here.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.api.tools_routes import _bad, require_desktop


class NewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: str = Field(min_length=4, max_length=2000)
    idea: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class StartBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief: str | None = Field(default=None, max_length=3000)
    tool: str | None = Field(default=None, pattern=r"^(claude|aider)$")


def _talk(prompt: str) -> str:
    from core.brain.conductor import TALK_MODEL
    from core.research.analyze import run_local
    return run_local(prompt, model=TALK_MODEL)


def create_build_router(require_api_authentication: Callable[..., None]) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_api_authentication)])

    @router.get("/api/build")
    def build_list() -> dict[str, Any]:
        from core.assistant_platform.build_helper import build_requests, view
        return view(build_requests().list())

    @router.post("/api/build")
    def build_new(body: NewBody) -> dict[str, Any]:
        from core.assistant_platform.build_helper import build_requests
        try:
            item = build_requests().create(body.request, _talk, source="idea" if body.idea else "app", idea=body.idea)
            if body.idea:
                from core.assistant_platform.suggestions import suggestions
                suggestions().mark(body.idea, "approved", "Sent to Build requests.")
            return item
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/build/{request_id}/start")
    def build_start(request_id: str, body: StartBody,
                    x_zaenia_desktop_key: str | None = Header(default=None, alias="X-ZAENIA-DESKTOP-KEY"),
                    x_zaenia_near_pass: str | None = Header(default=None, alias="X-ZAENIA-NEAR-PASS")) -> dict[str, Any]:
        from core.api.near_pc import desktop_or_near
        from core.assistant_platform.build_helper import build_requests
        from core.foundation.security.audit import audit
        if desktop_or_near(x_zaenia_desktop_key, x_zaenia_near_pass) is None:
            require_desktop(x_zaenia_desktop_key)
        try:
            item = build_requests().start(request_id, brief=body.brief, tool=body.tool)
        except Exception as error:
            raise _bad(error) from error
        audit("build_request.started", operation="assistant.desktop.manage", reason_code="owner_start")
        return item

    @router.post("/api/build/{request_id}/approve", dependencies=[Depends(require_desktop)])
    def build_approve(request_id: str) -> dict[str, Any]:
        from core.assistant_platform.build_helper import build_requests
        from core.foundation.security.audit import audit
        try:
            item = build_requests().approve(request_id)
        except Exception as error:
            raise _bad(error) from error
        audit("build_request.approved", operation="assistant.desktop.manage", reason_code="owner_approved_at_pc")
        return item

    @router.post("/api/build/{request_id}/undo", dependencies=[Depends(require_desktop)])
    def build_undo(request_id: str) -> dict[str, Any]:
        from core.assistant_platform.build_helper import build_requests
        from core.foundation.security.audit import audit
        try:
            item = build_requests().undo(request_id)
        except Exception as error:
            raise _bad(error) from error
        audit("build_request.undone", operation="assistant.desktop.manage", reason_code="owner_undo")
        return item

    @router.post("/api/build/{request_id}/rebuild", dependencies=[Depends(require_desktop)])
    def build_rebuild(request_id: str) -> dict[str, Any]:
        """After an approved or undone change to the app's screens: rebuild and reinstall the desktop app."""
        from core.assistant_platform.build_helper import build_requests, rebuild_app
        try:
            item = build_requests().get(request_id)
            if item["status"] not in ("approved", "undone") or not (item.get("needs") or {}).get("app"):
                raise ValueError("Nothing to rebuild for this request.")
            rebuild_app()
        except Exception as error:
            raise _bad(error) from error
        return {"ok": True}

    @router.post("/api/build/{request_id}/reject")
    def build_reject(request_id: str) -> dict[str, Any]:
        from core.assistant_platform.build_helper import build_requests
        try:
            return build_requests().reject(request_id)
        except Exception as error:
            raise _bad(error) from error

    # ---- nightly ideas (option 3)
    @router.post("/api/build/ideas/think")
    def ideas_think() -> dict[str, Any]:
        from core.assistant_platform.build_ideas import ideas
        try:
            return {"new": ideas().run(force=True)}
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/build/ideas/{idea_id}/never")
    def ideas_never(idea_id: str) -> dict[str, Any]:
        from core.assistant_platform.suggestions import suggestions
        try:
            return suggestions().mark(idea_id, "never", "She won't suggest this kind of change again.")
        except KeyError as error:
            raise HTTPException(404, "That idea no longer exists.") from error

    return router
