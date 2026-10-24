import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core.api import security_unlock as su


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


class UnlockTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(su, "UNLOCK_DIR", folder / "security_unlock"))
        self.stack.enter_context(patch("core.foundation.security.audit.audit", lambda *a, **k: None))
        (folder / "security_unlock").mkdir()
        self.clock = Clock()
        self.service = su.SecurityUnlock(clock=self.clock)

    def tearDown(self):
        self.stack.close()

    def grant(self, request, method="passkey", at=None):
        su.grant_path(request).write_text(json.dumps({"request": request, "method": method, "at": self.clock.now if at is None else at}))

    def test_grant_unlocks_once_and_session_locks_after_ten_idle_minutes(self):
        request = self.service.begin()["request"]
        self.assertEqual(self.service.poll(request)["status"], "waiting")
        self.grant(request)
        result = self.service.poll(request)
        self.assertEqual((result["status"], result["method"]), ("unlocked", "passkey"))
        self.assertFalse(su.grant_path(request).exists())
        self.assertEqual(self.service.poll(request)["status"], "expired")  # one use
        token = result["session"]
        self.clock.now += 9 * 60
        self.assertIsNotNone(self.service.check(token, touch=True))  # activity restarts the timer
        self.clock.now += 9 * 60
        self.assertEqual(self.service.check(token)["idleLeft"], 60)
        self.clock.now += 61
        self.assertIsNone(self.service.check(token))

    def test_forged_or_stale_grants_are_refused(self):
        self.grant("ab" * 16)  # a request the server never issued
        self.assertEqual(self.service.poll("ab" * 16)["status"], "expired")
        request = self.service.begin()["request"]
        self.grant(request, method="guess")
        self.assertEqual(self.service.poll(request)["status"], "waiting")
        self.assertFalse(su.grant_path(request).exists())  # deleted even when invalid
        self.grant(request, at=self.clock.now - 3600)  # written before the request existed
        self.assertEqual(self.service.poll(request)["status"], "waiting")
        self.clock.now += su.REQUEST_TTL + 1
        self.grant(request)
        self.assertEqual(self.service.poll(request)["status"], "expired")
        self.assertEqual(self.service.poll("../secure")["status"], "expired")

    def test_lock_and_bad_tokens(self):
        request = self.service.begin()["request"]
        self.grant(request, method="voice")
        token = self.service.poll(request)["session"]
        self.assertIsNone(self.service.check("x" * 40))
        self.assertIsNone(self.service.check(None))
        self.service.lock_session(token)
        self.assertIsNone(self.service.check(token))

    def test_voice_unlock_needs_both_phrase_and_voice(self):
        request = "cd" * 16
        record = lambda seconds: (b"\x01\x00" * 16000, "my phrase")
        for phrase, voice in ((True, False), (False, True)):
            with self.assertRaises(PermissionError):
                su.unlock_with_voice(request, record=record, phrase_ok=lambda words: phrase, speaker_ok=lambda pcm: voice)
            self.assertFalse(su.grant_path(request).exists())
        su.unlock_with_voice(request, record=record, phrase_ok=lambda words: True, speaker_ok=lambda pcm: True)
        self.assertEqual(json.loads(su.grant_path(request).read_text())["method"], "voice")


class RouteTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from core.api.server import create_app
        self.stack = ExitStack()
        folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(su, "UNLOCK_DIR", folder))
        self.stack.enter_context(patch.object(su, "_SERVICE", su.SecurityUnlock()))
        self.stack.enter_context(patch("core.foundation.security.audit.audit", lambda *a, **k: None))
        self.stack.enter_context(patch("core.api.desktop_key.is_paired", lambda: True))
        self.stack.enter_context(patch("core.api.desktop_key.verify", lambda key: key == "isolated-desktop-key"))
        self.stack.enter_context(patch("core.api.security_posture.full_view", lambda mode, **_: {"posture": {"score": 90}}))
        self.stack.enter_context(patch("core.api.security_posture.summary", lambda mode: {"level": "strong", "score": 90}))
        self.stack.enter_context(patch("core.api.security_activity.recent_activity", lambda **_: {"events": []}))

        class Gate:
            def authorize(self, operation):
                return operation == "status.read"
        self.client = self.stack.enter_context(TestClient(create_app(token_verifier=lambda token: token == "isolated-token",
                                                                     client_gate=Gate(), include_carplay=False, include_phone_app=False)))
        self.client.headers["X-ZAENIA-API-TOKEN"] = "isolated-token"

    def tearDown(self):
        self.stack.close()

    def test_full_view_needs_desktop_key_and_unlock(self):
        self.assertEqual(self.client.get("/api/security/summary").json()["level"], "strong")  # phone and Status tab: level only
        self.assertEqual(self.client.post("/api/security/unlock").status_code, 403)  # phone token alone
        desktop = {"X-ZAENIA-DESKTOP-KEY": "isolated-desktop-key"}
        request = self.client.post("/api/security/unlock", headers=desktop).json()["request"]
        self.assertEqual(self.client.post("/api/security/full", json={"session": "y" * 40}, headers=desktop).status_code, 401)
        su.write_grant(request, "passkey")
        session = self.client.get(f"/api/security/unlock/{request}", headers=desktop).json()["session"]
        self.assertEqual(self.client.post("/api/security/full", json={"session": session}).status_code, 403)  # no desktop key
        view = self.client.post("/api/security/full", json={"session": session}, headers=desktop)
        self.assertEqual(view.status_code, 200)
        self.assertEqual(view.json()["posture"]["score"], 90)
        self.assertEqual(self.client.post("/api/security/session", json={"session": session}, headers=desktop).json()["method"], "passkey")
        self.client.post("/api/security/session/lock", json={"session": session}, headers=desktop)
        self.assertEqual(self.client.post("/api/security/full", json={"session": session}, headers=desktop).status_code, 401)

    def test_routes_map_to_status_read(self):
        from core.api.ui_routes import operation_for
        for method, path in (("GET", "/api/security/summary"), ("POST", "/api/security/unlock"), ("GET", "/api/security/unlock/" + "a" * 32),
                             ("POST", "/api/security/session"), ("POST", "/api/security/session/lock"), ("POST", "/api/security/full")):
            self.assertEqual(operation_for(method, path), "status.read")
        self.assertIsNone(operation_for("GET", "/api/security/unlock/..%2F"))


if __name__ == "__main__":
    unittest.main()
