"""Locked Security tab: unlocked with the owner passkey or the spoken phrase plus the owner's voice.

The passkey is never typed into the app. The tab asks the server for an unlock
request, then opens the owner console at the PC (scripts/security_console.ps1),
which runs this module:

    python -m core.api.security_unlock passkey <request>
    python -m core.api.security_unlock voice <request>

The console checks the passkey (rate-limited, audited), or records the spoken
phrase once from the approved microphone and checks both the phrase hash and
the enrolled voice (the phrase alone never proves who is speaking). On success
it writes a one-time grant named after the request. The server accepts a grant
only for a request it issued in the last few minutes, deletes it, and gives the
desktop app a session that locks after 10 minutes without activity.

Requests and sessions live in this server's RAM; a restart locks the tab. The
unlock only shows information and opens owner consoles. Every change made from
the tab still asks for a fresh passkey in its own console.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

from core.foundation.storage.paths import SECURE_DIR

UNLOCK_DIR = SECURE_DIR / "security_unlock"
REQUEST_TTL = 180          # seconds to finish the passkey or phrase in the console
IDLE_SECONDS = 10 * 60     # the tab locks after 10 minutes without activity
MAX_PENDING = 3
MAX_SESSIONS = 3
METHODS = ("passkey", "voice")
REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def grant_path(request: str) -> Path:
    if not REQUEST_ID.match(request or ""):
        raise ValueError("Invalid unlock request.")
    return UNLOCK_DIR / f"{request}.grant"


class SecurityUnlock:
    def __init__(self, clock: Callable[[], float] = time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.pending: dict[str, float] = {}             # request -> created
        self.sessions: dict[str, dict[str, Any]] = {}   # token digest -> {method, unlocked, active}

    def _purge(self) -> None:
        now = self.clock()
        for request, created in list(self.pending.items()):
            if now - created > REQUEST_TTL:
                del self.pending[request]
                try:
                    grant_path(request).unlink(missing_ok=True)
                except OSError:
                    pass
        self.sessions = {key: s for key, s in self.sessions.items() if now - s["active"] < IDLE_SECONDS}

    def begin(self) -> dict[str, Any]:
        with self.lock:
            self._purge()
            while len(self.pending) >= MAX_PENDING:
                del self.pending[min(self.pending, key=self.pending.get)]
            request = secrets.token_hex(16)
            self.pending[request] = self.clock()
            return {"request": request, "expiresIn": REQUEST_TTL}

    def _read_grant(self, request: str, created: float) -> str | None:
        path = grant_path(request)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024:
            return None
        try:
            grant = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        finally:
            path.unlink(missing_ok=True)  # one use, valid or not
        if not isinstance(grant, dict) or grant.get("request") != request or grant.get("method") not in METHODS:
            return None
        at = grant.get("at")
        if type(at) not in (int, float) or not created - 5 <= at <= self.clock() + 5:
            return None
        return grant["method"]

    def poll(self, request: str) -> dict[str, Any]:
        """Waiting, expired, or unlocked (the session is returned once)."""
        if not REQUEST_ID.match(request or ""):
            return {"status": "expired"}
        with self.lock:
            self._purge()
            created = self.pending.get(request)
            if created is None:
                return {"status": "expired"}
            method = self._read_grant(request, created) if grant_path(request).exists() else None
            if method is None:
                return {"status": "waiting", "expiresIn": max(0, int(created + REQUEST_TTL - self.clock()))}
            del self.pending[request]
            while len(self.sessions) >= MAX_SESSIONS:
                del self.sessions[min(self.sessions, key=lambda key: self.sessions[key]["active"])]
            token = secrets.token_urlsafe(32)
            now = self.clock()
            self.sessions[_digest(token)] = {"method": method, "unlocked": now, "active": now}
        from core.foundation.security.audit import audit
        audit("security.tab_unlocked", operation="security.tab.open", reason_code=f"unlocked_{method}")
        return {"status": "unlocked", "session": token, "method": method, "idleSeconds": IDLE_SECONDS}

    def check(self, token: str | None, *, touch: bool = False) -> dict[str, Any] | None:
        if not isinstance(token, str) or not 20 <= len(token) <= 100:
            return None
        with self.lock:
            self._purge()
            session = self.sessions.get(_digest(token))
            if session is None:
                return None
            if touch:
                session["active"] = self.clock()
            return {"method": session["method"], "unlocked": session["unlocked"],
                    "idleLeft": max(0, int(session["active"] + IDLE_SECONDS - self.clock()))}

    def lock_session(self, token: str | None) -> None:
        if isinstance(token, str):
            with self.lock:
                self.sessions.pop(_digest(token), None)


_SERVICE: SecurityUnlock | None = None
_SERVICE_LOCK = threading.Lock()


def security_unlock() -> SecurityUnlock:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = SecurityUnlock()
        return _SERVICE


# ------------------------------------------------------------- owner console side

def write_grant(request: str, method: str) -> None:
    if method not in METHODS:
        raise ValueError("Unknown unlock method.")
    from core.foundation.security.io import atomic_write, reject_link
    from core.foundation.storage.paths import ensure_storage
    ensure_storage()
    reject_link(UNLOCK_DIR)
    UNLOCK_DIR.mkdir(exist_ok=True)
    atomic_write(grant_path(request), json.dumps({"request": request, "method": method, "at": time.time()}).encode("utf-8"))


def unlock_with_passkey(request: str) -> None:
    from core.foundation.auth.passkey import consume_fresh_auth, require_passkey
    payload = {"purpose": "security.tab.open", "request": request}
    proof = require_passkey(operation="security.tab.open", payload=payload)
    consume_fresh_auth(proof, operation="security.tab.open", payload=payload)
    write_grant(request, "passkey")


def unlock_with_voice(request: str, *, record=None, phrase_ok=None, speaker_ok=None) -> None:
    """Say the enrolled phrase once: both the words and the voice must match."""
    from core.foundation.security.audit import audit
    if record is None or phrase_ok is None:
        from core.foundation.auth import voice_passkey
        record = record or voice_passkey.record_phrase
        phrase_ok = phrase_ok or voice_passkey.phrase_matches
    if speaker_ok is None:
        from core.api.mobile_auth import LocalSpeaker
        speaker_ok = LocalSpeaker().verify  # loads the voice reference first, so a missing setup fails before recording
        speaker_ok(b"")
    print("Say your security phrase now.")
    pcm, words = record(6)
    phrase = phrase_ok(words)
    voice = bool(pcm) and speaker_ok(pcm)
    del pcm, words
    if not (phrase and voice):
        audit("security.tab_unlock_failed", operation="security.tab.open",
              reason_code="phrase_rejected" if not phrase else "speaker_rejected")
        raise PermissionError("That didn't match your phrase and your voice. The Security tab stays locked.")
    write_grant(request, "voice")


def main() -> None:
    parser = argparse.ArgumentParser(description="Unlock ZAE's Security tab at this PC.")
    parser.add_argument("method", choices=METHODS)
    parser.add_argument("request")
    args = parser.parse_args()
    if not REQUEST_ID.match(args.request):
        raise SystemExit("Invalid unlock request. Start again from the Security tab.")
    try:
        if args.method == "passkey":
            unlock_with_passkey(args.request)
        else:
            unlock_with_voice(args.request)
    except Exception as error:  # the console shows a plain reason and keeps the tab locked
        from core.api.mobile_auth import VoiceLoginError
        reason = str(error) if isinstance(error, (PermissionError, RuntimeError, ValueError, VoiceLoginError)) else type(error).__name__
        if "mobile voice sign-in" in reason.lower():
            reason += " (python -m core.api.mobile_voice_profile enable)"
        print(f"Not unlocked: {reason}")
        raise SystemExit(1)
    print("Security tab unlocked. You can close this window.")


if __name__ == "__main__":
    main()
