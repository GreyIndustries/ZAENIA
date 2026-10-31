"""Owner voice check for every app-microphone turn (Grey's choice B2, 2026-10-22).

The desktop/phone app microphone used to be trusted because it runs on Grey's
own device. Now every spoken turn from the app is also checked against his
enrolled voice before it can reach ZAE's brain:

* the check reuses the account-sealed voice reference that the phone's voice
  sign-in uses (core/api/mobile_voice_profile.py) and the same ECAPA model and
  calibrated threshold as PC Voice (IdentityGate: every window must match);
* a clip too short to check (under ~1.5 s, e.g. "yes", "do it") is accepted
  only within 45 seconds of a turn that *was* recognised, so quick replies in
  a conversation still work without lowering the bar for new speakers;
* a rejected turn is dropped: its words are not returned, not answered and
  not learned from. It is audited (voice.turn_rejected / app_mic_*);
* recent scores are kept in memory only, so the app can show how well
  recognition is working and suggest voice training when it isn't.

If voice checking isn't set up yet (no sealed reference), turns are rejected
with a reason the app shows, because Grey chose to require his voice.
"""
from __future__ import annotations

import math
import threading
import time
from array import array
from collections import deque
from typing import Any, Callable

SESSION_SECONDS = 45.0
MIN_CHECK_SECONDS = 1.5
STATS_SIZE = 50


def _active_span(pcm: bytes) -> bytes:
    """Trim leading/trailing silence (keeps a little padding)."""
    samples = array("h"); samples.frombytes(pcm)
    frame = 320
    active = [i for i in range(0, len(samples), frame)
              if math.sqrt(sum((v / 32768.0) ** 2 for v in samples[i:i + frame]) / max(1, len(samples[i:i + frame]))) >= .008]
    if not active:
        return b""
    start, end = max(0, active[0] - 1600), min(len(samples), active[-1] + frame + 1920)
    return pcm[start * 2:end * 2]


class AppMicGate:
    def __init__(self, *, verify: Callable[[bytes], bool] | None = None, score: Callable[[bytes], float] | None = None,
                 configured: Callable[[], bool] | None = None, audit: Callable[[str], None] | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self._speaker = None
        self.verify_fn, self.score_fn = verify, score
        self.configured = configured or self._configured
        self.audit = audit or self._audit
        self.clock = clock
        self.lock = threading.Lock()
        self.last_verified = -1e9
        self.recent: deque[dict[str, Any]] = deque(maxlen=STATS_SIZE)

    @staticmethod
    def _configured() -> bool:
        try:
            from core.api import mobile_voice_profile
            return mobile_voice_profile.configured()
        except Exception:
            return False

    @staticmethod
    def _audit(reason: str) -> None:
        try:
            from core.foundation.security.audit import audit
            audit("voice.turn_rejected", operation="voice.transcribe", reason_code=reason)
        except Exception:
            pass

    def _verify(self, pcm: bytes) -> bool:
        if self.verify_fn is not None:
            return self.verify_fn(pcm)
        if self._speaker is None:
            from core.api.mobile_auth import LocalSpeaker
            self._speaker = LocalSpeaker()
        return self._speaker.verify(pcm)

    def check(self, pcm: bytes) -> dict[str, Any]:
        """{"accepted": bool, "reason": str} for one app-mic clip (16 kHz mono PCM16)."""
        with self.lock:
            now = self.clock()
            if not self.configured():
                self.audit("app_mic_voice_not_set_up")
                return self._note(False, "not_set_up", None)
            speech = _active_span(pcm)
            seconds = len(speech) / 32000
            if seconds < MIN_CHECK_SECONDS:
                if now - self.last_verified <= SESSION_SECONDS and seconds > 0.15:
                    return self._note(True, "short_reply_in_conversation", None)
                self.audit("app_mic_too_short")
                return self._note(False, "too_short", None)
            try:
                accepted = bool(self._verify(pcm))
            except Exception:
                self.audit("app_mic_verification_failed")
                return self._note(False, "check_failed", None)
            score = None
            scorer = self.score_fn or getattr(getattr(self._speaker, "_gate", None), "scorer", None)
            if scorer is not None:
                try:
                    score = float(scorer(speech))  # for the recognition stats only
                except Exception:
                    score = None
            if accepted:
                self.last_verified = now
                return self._note(True, "recognised", score)
            self.audit("app_mic_speaker_rejected")
            return self._note(False, "not_recognised", score)

    def _note(self, accepted: bool, reason: str, score: float | None) -> dict[str, Any]:
        if reason != "short_reply_in_conversation":
            self.recent.append({"accepted": accepted, "reason": reason, "score": score, "at": time.time()})
        try:  # the owner/other-speaker trial only watches; it never changes the verdict
            from core.voice_security.voice_trial import voice_trial
            voice_trial().note(accepted, reason, score)
        except Exception:
            pass
        return {"accepted": accepted, "reason": reason}

    def stats(self) -> dict[str, Any]:
        checked = [r for r in self.recent if r["reason"] in ("recognised", "not_recognised")]
        rate = (sum(1 for r in checked if r["accepted"]) / len(checked)) if checked else None
        scores = [r["score"] for r in checked if r["score"] is not None]
        threshold = getattr(getattr(self._speaker, "_gate", None), "threshold", None)
        return {"required": True, "setUp": self.configured(), "checked": len(checked),
                "averageScore": round(sum(scores) / len(scores), 3) if scores else None,
                "threshold": round(float(threshold), 3) if threshold is not None else None,
                "recognisedRate": None if rate is None else round(rate, 2),
                "needsTraining": bool(checked) and len(checked) >= 5 and (rate or 0) < 0.7,
                "lastReason": self.recent[-1]["reason"] if self.recent else None}


REJECT_MESSAGES = {
    "not_set_up": "Voice check isn't set up yet. Run voice training once on your PC.",
    "too_short": "Too short to check your voice. Say a little more.",
    "not_recognised": "That didn't sound like you, so I ignored it.",
    "check_failed": "I couldn't check your voice just then. Try again.",
}

_GATE: AppMicGate | None = None
_GATE_LOCK = threading.Lock()


def app_mic_gate() -> AppMicGate:
    global _GATE
    with _GATE_LOCK:
        if _GATE is None:
            _GATE = AppMicGate()
        return _GATE
