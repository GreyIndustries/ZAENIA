"""Phone confirms when the phone is at the PC (Grey, 2026-10-30: "code plus voice, in either order").

The phone asks for a pass. The PC app (desktop key) shows a 6-digit code that changes every minute; typing it on the
phone proves someone at the PC screen. A fresh voice check on the phone (the same local speaker and spoken-words check
as voice sign-in) proves it's Grey. Both steps, in either order, within 3 minutes turn the pass on for 10 minutes.
While it's on, the phone can approve a short list of confirms that otherwise need the desktop app: a waiting file
change, a Code Doctor fix, opening a registered app, restoring a workspace with its apps. Nothing else: Security,
the Vault, the passkey, folder grants, approval settings and direct file edits stay at the PC.

One pass at a time, kept in memory only (a server restart ends it), and a new pass replaces the old one.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from typing import Any

PASS_HEADER = "X-ZAENIA-NEAR-PASS"
SETUP_SECONDS = 180       # both steps must be done within 3 minutes of asking
ACTIVE_SECONDS = 600      # then the phone can confirm for 10 minutes
CODE_SECONDS = 60         # the code on the PC screen changes every minute
MAX_CODE_TRIES = 5        # wrong codes end the pass


def _key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class NearPc:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.current: dict[str, Any] | None = None

    def _live(self) -> dict[str, Any] | None:
        now = self.clock()
        p = self.current
        if p and (p["active_until"] and now > p["active_until"] or not p["active_until"] and now > p["started"] + SETUP_SECONDS):
            self.current = p = None
        return p

    def _match(self, secret: str | None) -> dict[str, Any] | None:
        p = self._live()
        if not p or not secret or len(secret) > 128 or not secrets.compare_digest(p["key"], _key(secret)):
            return None
        return p

    def _view(self, p: dict[str, Any] | None) -> dict[str, Any]:
        if not p:
            return {"pass": False, "code": False, "voice": False, "active": False, "secondsLeft": 0}
        now = self.clock()
        left = p["active_until"] - now if p["active_until"] else p["started"] + SETUP_SECONDS - now
        return {"pass": True, "code": p["code_ok"], "voice": p["voice_ok"], "active": bool(p["active_until"]), "secondsLeft": max(0, round(left))}

    def _maybe_activate(self, p: dict[str, Any]) -> None:
        if p["code_ok"] and p["voice_ok"] and not p["active_until"]:
            p["active_until"] = self.clock() + ACTIVE_SECONDS

    def start(self) -> dict[str, Any]:
        secret = secrets.token_urlsafe(32)
        with self.lock:
            self.current = {"key": _key(secret), "started": self.clock(), "code": "", "code_at": 0.0, "tries": 0,
                            "code_ok": False, "voice_ok": False, "active_until": 0.0}
            return {"secret": secret, **self._view(self.current)}

    def code_for_pc(self) -> dict[str, Any] | None:
        """For the desktop app: the code to show while a pass still needs it."""
        with self.lock:
            p = self._live()
            if not p or p["code_ok"]:
                return None
            now = self.clock()
            if not p["code"] or now - p["code_at"] >= CODE_SECONDS:
                p["code"], p["code_at"] = f"{secrets.randbelow(1_000_000):06d}", now
            return {"code": p["code"], "secondsLeft": max(1, round(CODE_SECONDS - (now - p["code_at"]))), "voice": p["voice_ok"]}

    def submit_code(self, secret: str | None, code: str) -> dict[str, Any]:
        with self.lock:
            p = self._match(secret)
            if not p:
                raise PermissionError("That phone pass ended. Start again.")
            fresh = p["code"] and self.clock() - p["code_at"] < CODE_SECONDS + 10
            if not fresh or not secrets.compare_digest(p["code"], "".join(ch for ch in str(code) if ch.isdigit())[:6]):
                p["tries"] += 1
                if p["tries"] >= MAX_CODE_TRIES:
                    self.current = None
                    raise PermissionError("Too many wrong codes. Start again at the PC.")
                raise ValueError("That code doesn't match the one on the PC screen.")
            p["code_ok"], p["code"] = True, ""
            self._maybe_activate(p)
            return self._view(p)

    def pending(self, secret: str | None) -> bool:
        """Before running a voice check: is this a pass that still needs one?"""
        with self.lock:
            p = self._match(secret)
            return bool(p and not p["voice_ok"])

    def voice_passed(self, secret: str | None) -> dict[str, Any]:
        with self.lock:
            p = self._match(secret)
            if not p:
                raise PermissionError("That phone pass ended. Start again.")
            p["voice_ok"] = True
            self._maybe_activate(p)
            return self._view(p)

    def status(self, secret: str | None) -> dict[str, Any]:
        with self.lock:
            return self._view(self._match(secret))

    def allows(self, secret: str | None) -> bool:
        with self.lock:
            p = self._match(secret)
            return bool(p and p["active_until"])

    def end(self, secret: str | None = None, *, from_pc: bool = False) -> None:
        with self.lock:
            if from_pc or self._match(secret):
                self.current = None


_instance = NearPc()


def near_pc() -> NearPc:
    return _instance


def desktop_or_near(desktop_key: str | None, near_pass: str | None) -> str | None:
    """Which proof allows a listed confirm: "desktop", "near" (the phone's pass) or None."""
    from core.api.desktop_key import verify
    if verify(desktop_key):
        return "desktop"
    if near_pc().allows(near_pass):
        from core.foundation.security.audit import audit
        audit("assistant.near_pc_confirm", operation="assistant.desktop.manage", reason_code="code_and_voice")
        return "near"
    return None
