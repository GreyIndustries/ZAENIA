"""Browser-only voice authentication. No owner or desktop approval authority on its own; /voice/near is the voice
half of the phone-at-the-PC pass (near_pc.py), which also needs the code shown on the PC screen."""
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

    @router.post("/voice/near")
    async def near_voice(request: Request):
        """The voice step of a phone-at-the-PC pass: a fresh voice check that signs nothing in."""
        from core.api.near_pc import PASS_HEADER, near_pc
        guard(request)
        secret = request.headers.get(PASS_HEADER)
        if not near_pc().pending(secret):
            raise HTTPException(403, "It isn't the voice check's turn, or that phone pass ended.")
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
        from starlette.concurrency import run_in_threadpool
        try:
            token = await run_in_threadpool(service.verify, body["challenge_id"], request.cookies.get(CHALLENGE_COOKIE, ""), peer(request), body.get("audio"))
        except VoiceLoginError as error:
            failure(error)
        service.logout(token)  # the check only proves the voice; it doesn't start another phone session
        try:
            result = near_pc().voice_passed(secret)
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        from core.foundation.security.audit import audit
        audit("assistant.near_pc", operation="assistant.desktop.manage", reason_code="active" if result["active"] else "voice_ok")
        response = JSONResponse(result, headers={"Cache-Control": "no-store"})
        response.delete_cookie(CHALLENGE_COOKIE, path="/api/auth/voice")
        return response

    # ---- Face ID (WebAuthn passkey), face_passkey.py
    PASSKEY_COOKIE = "zaenia_passkey_binding"

    def site(request):
        return request.url.hostname or "", f"{request.url.scheme}://{request.url.netloc}"

    def passkey_failure(error):
        raise HTTPException(error.status, str(error), headers={"Cache-Control": "no-store"}) from error

    def with_binding(request, payload):
        binding = secrets.token_urlsafe(32)
        return binding, payload

    async def small_json(request):
        raw = await request.body()
        if len(raw) > 20_000:
            raise HTTPException(413, "That Face ID answer is too large.")
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError()
            return body
        except (ValueError, UnicodeError):
            raise HTTPException(400, "The Face ID answer could not be read.")

    def binding_response(request, payload, binding):
        response = JSONResponse(payload, headers={"Cache-Control": "no-store"})
        response.set_cookie(PASSKEY_COOKIE, binding, max_age=120, path="/api/auth/passkey", secure=request.url.scheme == "https",
                            httponly=True, samesite="strict")
        return response

    @router.get("/passkey/status")
    def passkey_status(request: Request):
        guard(request)
        from core.api.face_passkey import face_passkeys
        return JSONResponse({"available": face_passkeys().has_approved()}, headers={"Cache-Control": "no-store"})

    @router.post("/passkey/register/options")
    def passkey_register_options(request: Request):
        guard(request)
        if not service.authenticated(request.cookies.get(COOKIE, "")):
            raise HTTPException(401, "Sign in with your voice first, then add Face ID.")
        from core.api.face_passkey import face_passkeys, PasskeyError
        binding = secrets.token_urlsafe(32)
        try:
            options = face_passkeys().register_options(site(request)[0], binding)
        except PasskeyError as error:
            passkey_failure(error)
        return binding_response(request, options, binding)

    @router.post("/passkey/register")
    async def passkey_register(request: Request):
        guard(request)
        if not service.authenticated(request.cookies.get(COOKIE, "")):
            raise HTTPException(401, "Sign in with your voice first, then add Face ID.")
        from core.api.face_passkey import face_passkeys, PasskeyError
        from core.foundation.security.audit import audit
        body = await small_json(request)
        rp_id, origin = site(request)
        try:
            result = face_passkeys().register(body, rp_id, origin, request.cookies.get(PASSKEY_COOKIE, ""), str(body.get("label") or "iPhone"))
        except PasskeyError as error:
            passkey_failure(error)
        audit("auth.passkey", operation="voice.service.open", reason_code="registered_pending_pc_approval")
        response = JSONResponse(result, headers={"Cache-Control": "no-store"})
        response.delete_cookie(PASSKEY_COOKIE, path="/api/auth/passkey")
        return response

    @router.post("/passkey/login/options")
    def passkey_login_options(request: Request):
        guard(request)
        from core.api.face_passkey import face_passkeys, PasskeyError
        try:
            with service.lock:
                service._limit("passkey:" + peer(request), 20)
        except VoiceLoginError as error:
            failure(error)
        binding = secrets.token_urlsafe(32)
        try:
            options = face_passkeys().login_options(site(request)[0], binding)
        except PasskeyError as error:
            passkey_failure(error)
        return binding_response(request, options, binding)

    @router.post("/passkey/login")
    async def passkey_login(request: Request):
        guard(request)
        from core.api.face_passkey import face_passkeys, PasskeyError
        from core.foundation.security.audit import audit
        body = await small_json(request)
        rp_id, origin = site(request)
        try:
            face_passkeys().login(body, rp_id, origin, request.cookies.get(PASSKEY_COOKIE, ""))
        except PasskeyError as error:
            audit("auth.passkey", operation="voice.service.open", reason_code="sign_in_rejected")
            passkey_failure(error)
        audit("auth.passkey", operation="voice.service.open", reason_code="signed_in")
        service.logout(request.cookies.get(COOKIE, ""))
        token = service.issue_session()
        response = JSONResponse({"success": True}, headers={"Cache-Control": "no-store"})
        response.set_cookie(COOKIE, token, max_age=SESSION_TTL, path="/api", secure=request.url.scheme == "https",
                            httponly=True, samesite="strict")
        response.delete_cookie(PASSKEY_COOKIE, path="/api/auth/passkey")
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
