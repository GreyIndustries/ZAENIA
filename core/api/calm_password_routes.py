"""Authenticated UI-only Calm return checks; owner enrollment stays in a console."""
from __future__ import annotations

import json
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from core.api.calm_password import MAX_LENGTH, CalmPasswordError, calm_password


def operation_for(method: str, path: str) -> str | None:
    if (method, path) in {("GET", "/api/calm/password/status"), ("POST", "/api/calm/password/verify")}:
        return "status.read"
    return None


def create_calm_password_router(require_auth: Callable, *, provider: Callable = calm_password) -> APIRouter:
    router = APIRouter(tags=["calm"], dependencies=[Depends(require_auth)])

    def response_error(error: CalmPasswordError) -> HTTPException:
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
        return HTTPException(error.status, str(error), headers=headers)

    @router.get("/api/calm/password/status")
    def password_status():
        try:
            return provider().status()
        except CalmPasswordError as error:
            raise response_error(error) from error

    @router.post("/api/calm/password/verify")
    async def password_verify(request: Request):
        # Do not put a password into a Pydantic validation error or log message.
        # Read a small, fixed-shape JSON request and report only generic errors.
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 1024:
                raise HTTPException(413, "The dashboard password request is too large.")
            raw.extend(chunk)
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as error:
            raise HTTPException(422, "Enter your dashboard password.") from error
        if (not isinstance(body, dict) or set(body) != {"password"} or not isinstance(body["password"], str)
                or not 1 <= len(body["password"]) <= MAX_LENGTH):
            raise HTTPException(422, "Enter your dashboard password.")
        try:
            return {"unlocked": await run_in_threadpool(provider().verify, body["password"])}
        except CalmPasswordError as error:
            raise response_error(error) from error

    return router
