"""ZAE's phone line: who's calling, what to say back.

Calls to ZAE's number
  * From one of Grey's numbers: she asks for his spoken phrase. The phrase must
    match AND the voice must be his (the enrolled ECAPA profile). If the voice
    check fails on a bad line, his phone PIN on the keypad can stand in for it
    (phrase still required). Every later turn is checked against his voice too,
    unless the PIN was used. Then it's a normal conversation: he speaks, she
    answers in her Kokoro voice.
  * From anyone else, or forwarded from Grey's own number when he doesn't pick
    up: she's his answering service. She takes a name and message, says she'll
    pass it on, and texts it to him. Callers learn nothing about him.

Texts to ZAE's number
  * From Grey's number: she texts back an answer. Texts can't be voice-checked,
    so nothing is saved, changed or acted on from a text (answers only). A forged
    sender number can't read the reply: Twilio delivers it to Grey's real phone.
  * From anyone else: no reply; Grey gets the text forwarded.

Audio is only ever handled in memory here. Twilio's copy of each recording is
deleted as soon as she has heard it. Caller words are reference, never
instructions: callers can't make her do anything.
"""
from __future__ import annotations

import io
import re
import secrets
import threading
import time
import wave
from typing import Any, Callable

GOODBYE = re.compile(r"^(?:ok(?:ay)?[, ]+)?(?:bye|goodbye|good bye|that's all|thats all|hang up|end call|talk later|see you)\b", re.I)
VERIFY_TRIES = 2
VOICE_MISSES_ALLOWED = 2
JOB_POLL_SECONDS = 2
AUDIO_TTL = 300.0
MESSAGES_PER_HOUR = 3


def wav_to_pcm16k(data: bytes) -> bytes:
    """Twilio's 8 kHz recording as 16 kHz mono 16-bit PCM (what Vosk and the voice model expect)."""
    with wave.open(io.BytesIO(data)) as clip:
        rate, channels, width = clip.getframerate(), clip.getnchannels(), clip.getsampwidth()
        frames = clip.readframes(clip.getnframes())
    import numpy as np
    if width == 1:
        samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) * 256
    else:
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        from scipy.signal import resample_poly
        from math import gcd
        step = gcd(16000, rate)
        samples = resample_poly(samples, 16000 // step, rate // step)
    return np.clip(samples, -32768, 32767).astype("<i2").tobytes()


class PhoneLine:
    def __init__(self, config: dict[str, Any], client: Any, *,
                 transcribe: Callable[[bytes], str], speaker_ok: Callable[[bytes], bool], phrase_ok: Callable[[str], bool],
                 answer: Callable[[str, bool], str], speak: Callable[[str], bytes | None],
                 notify: Callable[[str, str], None], pin_ok: Callable[[str], bool] | None = None,
                 audit: Callable[[str, str], None] | None = None, clock: Callable[[], float] = time.monotonic,
                 background: Callable[[Callable[[], None]], None] | None = None):
        self.config, self.client = config, client
        self.transcribe, self.speaker_ok, self.phrase_ok = transcribe, speaker_ok, phrase_ok
        self.answer, self.speak, self.notify, self.pin_ok = answer, speak, notify, pin_ok
        self.audit = audit or (lambda event, reason: None)
        self.clock = clock
        self.background = background or (lambda work: threading.Thread(target=work, daemon=True).start())
        self.lock = threading.Lock()
        self.calls: dict[str, dict[str, Any]] = {}
        self.audio: dict[str, tuple[bytes, float]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.recent_messages: dict[str, list[float]] = {}

    # ---- helpers ------------------------------------------------------------------
    @property
    def base(self) -> str:
        return str(self.config.get("public_base_url", "")).rstrip("/")

    def _owner(self, number: str) -> bool:
        from core.telephony.settings import is_owner_number
        return is_owner_number(number, self.config)

    def _voice(self, text: str) -> str:
        """Her Kokoro voice when it's available, else Twilio's speech."""
        from core.telephony import twilio
        try:
            clip = self.speak(text)
        except Exception:
            clip = None
        if not clip:
            return twilio.say(text)
        clip_id = secrets.token_urlsafe(18)
        with self.lock:
            now = self.clock()
            self.audio = {key: value for key, value in self.audio.items() if value[1] > now}
            self.audio[clip_id] = (clip, now + AUDIO_TTL)
        return twilio.play(f"{self.base}/phone/audio/{clip_id}.wav")

    def audio_clip(self, clip_id: str) -> bytes | None:
        with self.lock:
            found = self.audio.get(clip_id)
        return found[0] if found and found[1] > self.clock() else None

    def _heard(self, params: dict[str, str]) -> bytes:
        url = params.get("RecordingUrl", "")
        try:
            return wav_to_pcm16k(self.client.recording_wav(url))
        finally:
            self.client.delete_recording(url)

    # ---- calls ----------------------------------------------------------------------
    def voice(self, params: dict[str, str]) -> str:
        from core.telephony import twilio
        call_id, caller = params.get("CallSid", ""), params.get("From", "")
        forwarded = bool(params.get("ForwardedFrom"))
        if self._owner(caller) and not forwarded:
            with self.lock:
                self.calls[call_id] = {"owner": True, "verified": False, "tries": 0, "misses": 0, "voice_checks": True}
            self.audit("phone.call_owner", "phrase_requested")
            return twilio.response(self._voice("Hi, it's ZAE. Say your phrase."),
                                   twilio.record("/phone/voice/verify", max_seconds=8))
        self.audit("phone.call_other", "forwarded" if forwarded else "direct")
        greeting = ("Hi, you've reached Zack's assistant. He can't take your call right now. "
                    "Please say your name and a short message after the tone, and I'll make sure he gets it.")
        return twilio.response(self._voice(greeting), twilio.record("/phone/voice/message", max_seconds=60, silence=4, beep=True))

    def verify(self, params: dict[str, str]) -> str:
        from core.telephony import twilio
        from core.foundation.auth.voice_passkey import normalize_phrase
        call = self.calls.get(params.get("CallSid", ""))
        if not call or not call["owner"]:
            return twilio.response(hangup=True)
        try:
            pcm = self._heard(params)
            phrase = self.phrase_ok(normalize_phrase(self.transcribe(pcm)))
            voice = phrase and self.speaker_ok(pcm)
        except Exception:
            phrase = voice = False
        if phrase and voice:
            call["verified"] = True
            self.audit("phone.owner_verified", "phrase_and_voice")
            return twilio.response(self._voice("Go ahead, sir."), twilio.record("/phone/voice/turn"))
        if phrase and self.pin_ok is not None:
            call["phrase_ok"] = True
            return twilio.response(self._voice("Your phrase matched but the line's too rough to check your voice. Enter your phone PIN."),
                                   twilio.keypad("/phone/voice/pin", int(self.config.get("pin_digits", 6))))
        call["tries"] += 1
        self.audit("phone.owner_rejected", "phrase_rejected" if not phrase else "voice_rejected")
        if call["tries"] < VERIFY_TRIES:
            return twilio.response(self._voice("Sorry, I couldn't confirm that. Say your phrase again."),
                                   twilio.record("/phone/voice/verify", max_seconds=8))
        self.calls.pop(params.get("CallSid", ""), None)
        return twilio.response(self._voice("I couldn't confirm it's you. Goodbye."), hangup=True)

    def pin(self, params: dict[str, str]) -> str:
        from core.telephony import twilio
        call = self.calls.get(params.get("CallSid", ""))
        if not call or not call.get("phrase_ok") or self.pin_ok is None:
            return twilio.response(hangup=True)
        if self.pin_ok(params.get("Digits", "")):
            call.update(verified=True, voice_checks=False)
            self.audit("phone.owner_verified", "phrase_and_pin")
            return twilio.response(self._voice("Thanks. Go ahead, sir."), twilio.record("/phone/voice/turn"))
        self.audit("phone.owner_rejected", "pin_rejected")
        self.calls.pop(params.get("CallSid", ""), None)
        return twilio.response(self._voice("That PIN didn't match. Goodbye."), hangup=True)

    def turn(self, params: dict[str, str]) -> str:
        """His next sentence. The answer is worked out in the background (Twilio waits 15 s at most)."""
        from core.telephony import twilio
        call_id = params.get("CallSid", "")
        call = self.calls.get(call_id)
        if not call or not call["verified"]:
            return twilio.response(hangup=True)
        try:
            pcm = self._heard(params)
        except Exception:
            return twilio.response(self._voice("Sorry, I lost that. Say it again."), twilio.record("/phone/voice/turn"))
        if call["voice_checks"] and not self.speaker_ok(pcm):
            call["misses"] += 1
            self.audit("phone.turn_rejected", "voice_rejected")
            if call["misses"] > VOICE_MISSES_ALLOWED:
                self.calls.pop(call_id, None)
                return twilio.response(self._voice("I can't confirm it's still you, so I'm ending the call."), hangup=True)
            return twilio.response(self._voice("That didn't sound like you. Say it again."), twilio.record("/phone/voice/turn"))
        call["misses"] = 0
        words = " ".join(self.transcribe(pcm).split())
        if not words:
            return twilio.response(self._voice("I didn't catch that."), twilio.record("/phone/voice/turn"))
        if GOODBYE.match(words):
            self.calls.pop(call_id, None)
            return twilio.response(self._voice("Goodbye, sir."), hangup=True)
        job_id = secrets.token_urlsafe(12)
        job: dict[str, Any] = {"call": call_id, "reply": None}
        with self.lock:
            self.jobs[job_id] = job

        def work() -> None:
            try:
                job["reply"] = self.answer(words, True) or "I don't have an answer for that."
            except Exception:
                job["reply"] = "Sorry, my brain didn't answer. Try again."
        self.background(work)
        return twilio.response(f'<Pause length="{JOB_POLL_SECONDS}"/>', f'<Redirect method="POST">/phone/voice/wait?job={job_id}</Redirect>')

    def wait(self, params: dict[str, str], job_id: str) -> str:
        from core.telephony import twilio
        with self.lock:
            job = self.jobs.get(job_id)
        if not job or job["call"] != params.get("CallSid", ""):
            return twilio.response(hangup=True)
        if job["reply"] is None:
            return twilio.response(f'<Pause length="{JOB_POLL_SECONDS}"/>', f'<Redirect method="POST">/phone/voice/wait?job={job_id}</Redirect>')
        with self.lock:
            self.jobs.pop(job_id, None)
        return twilio.response(self._voice(job["reply"]), twilio.record("/phone/voice/turn"))

    def caller_message(self, params: dict[str, str]) -> str:
        """Answering service: pass a caller's message to Grey as a text (and a notice in the app)."""
        from core.telephony import twilio
        caller = params.get("From", "unknown number")
        now = self.clock()
        with self.lock:
            stamps = [stamp for stamp in self.recent_messages.get(caller, []) if now - stamp < 3600]
            limited = len(stamps) >= MESSAGES_PER_HOUR
            self.recent_messages[caller] = stamps + ([] if limited else [now])
        if not limited:
            try:
                words = " ".join(self.transcribe(self._heard(params)).split())
            except Exception:
                words = ""
            text = f'Missed call from {caller}: "{words[:400]}"' if words else f"Missed call from {caller} (no message)."
            self.notify("Phone message", text)
            self.audit("phone.message_taken", "rate_ok")
        return twilio.response(self._voice("Thanks. I'll pass that on. Goodbye."), hangup=True)

    # ---- texts ----------------------------------------------------------------------
    def sms(self, params: dict[str, str]) -> str:
        from core.telephony import twilio
        sender, body = params.get("From", ""), " ".join(str(params.get("Body", "")).split())[:1000]
        if not body:
            return twilio.response()
        if self._owner(sender):
            self.audit("phone.sms_owner", "answer_only")
            try:
                reply = self.answer(body, False)
            except Exception:
                reply = "My brain didn't answer that. Try again in a moment."
            return twilio.response(twilio.message(reply))
        now = self.clock()
        with self.lock:
            stamps = [stamp for stamp in self.recent_messages.get(sender, []) if now - stamp < 3600]
            limited = len(stamps) >= MESSAGES_PER_HOUR
            self.recent_messages[sender] = stamps + ([] if limited else [now])
        if not limited:
            self.notify("Text message", f'Text to ZAE from {sender}: "{body[:400]}"')
        self.audit("phone.sms_other", "forwarded" if not limited else "rate_limited")
        return twilio.response()
