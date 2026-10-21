"""Browser-only voice authentication. No owner or desktop approval authority."""
from __future__ import annotations

import json
import secrets
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.api.mobile_auth import APP_HEADER, CHALLENGE_COOKIE, CHALLENGE_TTL, COOKIE, SESSION_TTL, MobileAuth, VoiceLoginError


def browser_request_allowed(request: Request) -> bool:
    # Custom header requires a CORS preflight from other origins. No CORS is enabled.
    if request.headers.get(APP_HEADER) != "1" or request.headers.get("sec-fetch-site", "same-origin") not in {"same-origin", "none"}:
        return False
    if request.url.scheme != "https" and request.url.hostname not in {"localhost", "127.0.0.1", "::1", "testserver"}:
        return False
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != request.url.scheme or parsed.netloc != request.url.netloc:
            return False
    return True


def create_mobile_auth_router(service: MobileAuth) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["mobile authentication"])

    def guard(request):
        if not browser_request_allowed(request):
            raise HTTPException(403, "Open Zae at its secure address to sign in.")

    def peer(request):
        return request.client.host if request.client else "unknown"

    def failure(error):
        raise HTTPException(error.status, str(error), headers={"Cache-Control": "no-store", **({"Retry-After": "600"} if error.status == 429 else {})}) from error

    @router.post("/voice/challenge")
    def challenge(request: Request):
        guard(request)
        binding = secrets.token_urlsafe(32)
        try:
            result = service.challenge(peer(request), binding)
        except VoiceLoginError as error:
            failure(error)
        response = JSONResponse(result, headers={"Cache-Control": "no-store"})
        response.set_cookie(CHALLENGE_COOKIE, binding, max_age=CHALLENGE_TTL, path="/api/auth/voice",
                            secure=request.url.scheme == "https", httponly=True, samesite="strict")
        return response

    @router.post("/voice/verify")
    async def verify(request: Request):
        guard(request)
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "Send a voice recording as JSON.")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 650_000:
                raise HTTPException(413, "The voice recording is too large.")
        try:
            body = json.loads(raw)
            if not isinstance(body, dict) or not isinstance(body.get("challenge_id"), str) or len(body["challenge_id"]) > 128:
                raise ValueError()
        except (ValueError, UnicodeError):
            raise HTTPException(400, "The voice check could not be read.")
        # Speaker inference must not block the API's async request loop.
        from starlette.concurrency import run_in_threadpool
        try:
            token = await run_in_threadpool(service.verify, body["challenge_id"], request.cookies.get(CHALLENGE_COOKIE, ""), peer(request), body.get("audio"))
        except VoiceLoginError as error:
            failure(error)
        service.logout(request.cookies.get(COOKIE, ""))
        response = JSONResponse({"success": True}, headers={"Cache-Control": "no-store"})
        response.set_cookie(COOKIE, token, max_age=SESSION_TTL, path="/api", secure=request.url.scheme == "https",
                            httponly=True, samesite="strict")
        response.delete_cookie(CHALLENGE_COOKIE, path="/api/auth/voice")
        return response

    @router.post("/logout")
    def logout(request: Request):
        guard(request)
        service.logout(request.cookies.get(COOKIE, ""))
        response = JSONResponse({"success": True}, headers={"Cache-Control": "no-store"})
        response.delete_cookie(COOKIE, path="/api")
        response.delete_cookie(CHALLENGE_COOKIE, path="/api/auth/voice")
        return response

    return router
