"""Public webhooks for ZAE's phone line, reached only through Tailscale Funnel's /phone path.

These routes can't use the API token (Twilio doesn't have it), so every POST
must carry a valid Twilio signature for this account, checked against the
exact public URL; anything else gets 403. Nothing is served until the phone
line has been set up and enabled. Audio clips are served by unguessable,
five-minute ids (Twilio fetches them with a plain GET).
"""
from __future__ import annotations

import re
import threading
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

_LINE: Any = None
_LINE_KEY: Any = None
_LOCK = threading.Lock()
_CLIP = re.compile(r"^[A-Za-z0-9_-]{16,40}$")


def build_line(config: dict[str, Any], authorize: Callable[[str], None], notify_app: Callable[[str, str], None]) -> Any:
    """The phone line wired to ZAE's real voice, brain and checks."""
    from core.telephony import settings
    from core.telephony.service import PhoneLine
    from core.telephony.twilio import TwilioClient
    client = TwilioClient(config["account_sid"], settings.auth_token())

    def transcribe(pcm: bytes) -> str:
        from core.api.ui_voice import recognize
        return recognize(pcm)

    speaker = {"check": None}

    def speaker_ok(pcm: bytes) -> bool:
        if speaker["check"] is None:
            from core.api.mobile_auth import LocalSpeaker
            speaker["check"] = LocalSpeaker()
        return bool(speaker["check"].verify(pcm))

    def phrase_ok(words: str) -> bool:
        from core.foundation.auth.voice_passkey import phrase_matches
        return phrase_matches(words)

    def answer(text: str, spoken: bool) -> str:
        from core.brain.brain_service import BrainService
        authorize("chat.reply")
        # Calls (voice-verified) are remembered like any conversation; texts are answer-only.
        reply = BrainService(memory_authorizer=authorize).ask(text, remember=spoken)
        return str(reply.get("answer") or "")

    def speak(text: str) -> bytes | None:
        from core.voice_output.neural_voice import synthesize_wav
        return synthesize_wav(text)

    def notify(title: str, message: str) -> None:
        try:
            notify_app(title, message)
        except Exception:
            pass
        for owner in (config.get("owner_numbers") or [])[:1]:
            try:
                client.send_sms(config["zae_number"], owner, message)
            except Exception:
                pass

    from core.telephony.pin import pin_matches, pin_exists
    from core.foundation.security.audit import audit
    return PhoneLine(config, client, transcribe=transcribe, speaker_ok=speaker_ok, phrase_ok=phrase_ok, answer=answer,
                     speak=speak, notify=notify, pin_ok=pin_matches if pin_exists() else None,
                     audit=lambda event, reason: audit(event, operation="phone.line", reason_code=reason))


def create_phone_router(authorize: Callable[[str], None], notify_app: Callable[[str, str], None],
                        line_factory: Callable[..., Any] = build_line) -> APIRouter:
    router = APIRouter()

    def line() -> tuple[Any, dict[str, Any]]:
        global _LINE, _LINE_KEY
        from core.telephony import settings
        config = settings.load()
        if not settings.ready(config):
            raise HTTPException(404)
        key = (config.get("account_sid"), config.get("zae_number"), tuple(config.get("owner_numbers") or []),
               config.get("public_base_url"))
        with _LOCK:
            if _LINE is None or _LINE_KEY != key:
                _LINE, _LINE_KEY = line_factory(config, authorize, notify_app), key
            return _LINE, config

    async def signed(request: Request) -> tuple[Any, dict[str, str]]:
        phone, config = line()
        from core.telephony import settings
        from core.telephony.twilio import valid_request
        from urllib.parse import parse_qsl
        body = await request.body()
        if len(body) > 64_000:
            raise HTTPException(413)
        form = dict(parse_qsl(body.decode("utf-8", "replace"), keep_blank_values=True))
        url = str(config["public_base_url"]).rstrip("/") + request.url.path + (f"?{request.url.query}" if request.url.query else "")
        try:
            token = settings.auth_token()
        except Exception:
            token = ""
        if not valid_request(token, url, form, request.headers.get("X-Twilio-Signature")):
            from core.foundation.security.audit import audit
            audit("phone.request_rejected", operation="phone.line", reason_code="bad_signature")
            raise HTTPException(403)
        return phone, form

    def xml(body: str) -> Response:
        return Response(content=body, media_type="application/xml")

    @router.post("/phone/voice")
    async def incoming_call(request: Request) -> Response:
        phone, form = await signed(request)
        return xml(phone.voice(form))

    @router.post("/phone/voice/verify")
    async def verify(request: Request) -> Response:
        phone, form = await signed(request)
        return xml(phone.verify(form))

    @router.post("/phone/voice/pin")
    async def pin(request: Request) -> Response:
        phone, form = await signed(request)
        return xml(phone.pin(form))

    @router.post("/phone/voice/turn")
    async def turn(request: Request) -> Response:
        phone, form = await signed(request)
        return xml(phone.turn(form))

    @router.post("/phone/voice/wait")
    async def wait(request: Request, job: str = "") -> Response:
        phone, form = await signed(request)
        return xml(phone.wait(form, job))

    @router.post("/phone/voice/message")
    async def caller_message(request: Request) -> Response:
        phone, form = await signed(request)
        return xml(phone.caller_message(form))

    @router.post("/phone/sms")
    async def sms(request: Request) -> Response:
        phone, form = await signed(request)
        return xml(phone.sms(form))

    @router.get("/phone/audio/{clip_id}.wav")
    def audio(clip_id: str) -> Response:
        phone, _ = line()
        clip = phone.audio_clip(clip_id) if _CLIP.match(clip_id) else None
        if clip is None:
            raise HTTPException(404)
        return Response(content=clip, media_type="audio/wav", headers={"Cache-Control": "no-store"})

    return router
