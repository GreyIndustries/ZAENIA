"""Isolated browser authentication checks; no real profile, credentials, or mic."""
from __future__ import annotations

import base64
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.mobile_auth import APP_HEADER, COOKIE, IDLE_TTL, SESSION_TTL, MobileAuth, VoiceLoginError
from core.api.mobile_auth_routes import create_mobile_auth_router

AUDIO = base64.b64encode(b"\x10\x10" * 48_000).decode()
HEADERS = {APP_HEADER: "1", "Origin": "https://testserver"}


class MobileAuthTests(unittest.TestCase):
    def setUp(self):
        self.now = [1000.0]
        self.generation = ["enrolled-v1"]
        self.available = [True]
        self.matches = [True]
        self.words = [""]
        self.scored = []
        self.service = MobileAuth(
            speaker=lambda pcm: self.scored.append(pcm) or self.matches[0],
            transcribe=lambda pcm: self.words[0],
            generation=lambda: self.generation[0], available=lambda: self.available[0], clock=lambda: self.now[0])
        app = FastAPI()
        app.include_router(create_mobile_auth_router(self.service))
        self.client = TestClient(app, base_url="https://testserver", headers=HEADERS)
        self.addCleanup(self.client.close)

    def challenge(self):
        reply = self.client.post("/api/auth/voice/challenge")
        self.assertEqual(reply.status_code, 200, reply.text)
        body = reply.json()
        self.words[0] = body["phrase"]
        return body

    def verify(self, challenge):
        return self.client.post("/api/auth/voice/verify", json={"challenge_id": challenge["challenge_id"], "audio": AUDIO})

    def login(self):
        result = self.verify(self.challenge())
        self.assertEqual(result.status_code, 200, result.text)
        return self.client.cookies.get(COOKIE)

    def test_voice_session_is_http_only_secure_strict_and_not_returned_to_javascript(self):
        result = self.verify(self.challenge())
        self.assertEqual(result.json(), {"success": True})
        cookie = result.headers["set-cookie"]
        for part in ["HttpOnly", "Secure", "SameSite=strict", "Path=/api"]:
            self.assertIn(part, cookie)
        self.assertTrue(self.service.authenticated(self.client.cookies.get(COOKIE)))
        self.assertEqual(len(self.scored), 1)

    def test_wrong_speaker_fails(self):
        challenge = self.challenge()
        self.matches[0] = False
        self.assertEqual(self.verify(challenge).status_code, 401)
        self.assertFalse(self.client.cookies.get(COOKIE))

    def test_wrong_words_fail_before_speaker_inference(self):
        challenge = self.challenge()
        self.words[0] = "recording from an older prompt"
        self.assertEqual(self.verify(challenge).status_code, 401)
        self.assertFalse(self.scored)

    def test_challenge_cannot_be_reused(self):
        challenge = self.challenge()
        self.assertEqual(self.verify(challenge).status_code, 200)
        self.assertEqual(self.verify(challenge).status_code, 401)

    def test_failed_challenge_cannot_be_retried(self):
        challenge = self.challenge()
        self.matches[0] = False
        self.assertEqual(self.verify(challenge).status_code, 401)
        self.matches[0] = True
        self.assertEqual(self.verify(challenge).status_code, 401)

    def test_expired_challenge_fails(self):
        challenge = self.challenge()
        self.now[0] += 91
        self.assertEqual(self.verify(challenge).status_code, 401)

    def test_challenge_is_bound_to_the_browser(self):
        challenge = self.challenge()
        self.client.cookies.clear()
        self.assertEqual(self.verify(challenge).status_code, 401)

    def test_challenge_is_bound_to_peer(self):
        challenge = self.service.challenge("phone-a", "nonce")
        self.words[0] = challenge["phrase"]
        with self.assertRaises(VoiceLoginError):
            self.service.verify(challenge["challenge_id"], "nonce", "phone-b", AUDIO)

    def test_short_invalid_and_oversized_audio_fail(self):
        for audio in ["!bad", base64.b64encode(b"\0" * 10).decode(), "A" * 640_004, None]:
            with self.subTest(audio_type=type(audio)):
                challenge = self.challenge()
                result = self.client.post("/api/auth/voice/verify", json={"challenge_id": challenge["challenge_id"], "audio": audio})
                self.assertEqual(result.status_code, 400)
        self.assertFalse(self.scored)

    def test_attempts_are_rate_limited(self):
        for _ in range(5):
            self.assertEqual(self.verify(self.challenge()).status_code, 200)
        self.assertEqual(self.verify(self.challenge()).status_code, 429)

    def test_new_challenges_are_rate_limited(self):
        for _ in range(10):
            self.challenge()
        self.assertEqual(self.client.post("/api/auth/voice/challenge").status_code, 429)

    def test_idle_timeout(self):
        token = self.login()
        self.now[0] += IDLE_TTL
        self.assertFalse(self.service.authenticated(token))

    def test_absolute_timeout_even_with_activity(self):
        token = self.login()
        for _ in range(SESSION_TTL // 600 - 1):
            self.now[0] += 600
            self.assertTrue(self.service.authenticated(token))
        self.now[0] += 600
        self.assertFalse(self.service.authenticated(token))

    def test_changed_enrollment_revokes_sessions(self):
        token = self.login()
        self.generation[0] = "new-profile"
        self.assertFalse(self.service.authenticated(token))

    def test_disabling_voice_login_revokes_sessions(self):
        token = self.login()
        self.available[0] = False
        self.assertFalse(self.service.authenticated(token))

    def test_restart_loses_sessions(self):
        token = self.login()
        other = MobileAuth(speaker=lambda _: True, transcribe=lambda _: "", generation=lambda: "enrolled-v1", available=lambda: True)
        self.assertFalse(other.authenticated(token))

    def test_logout_revokes_server_session_and_cookie(self):
        token = self.login()
        result = self.client.post("/api/auth/logout")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(self.service.authenticated(token))
        self.assertFalse(self.client.cookies.get(COOKIE))

    def test_cross_origin_requests_and_missing_app_header_fail(self):
        for headers in [{APP_HEADER: "1", "Origin": "https://other.example"}, {APP_HEADER: "1", "Origin": "null"}, {APP_HEADER: "1", "Sec-Fetch-Site": "cross-site"}]:
            self.assertEqual(self.client.post("/api/auth/voice/challenge", headers=headers).status_code, 403)
        self.client.headers.pop(APP_HEADER)
        self.assertEqual(self.client.post("/api/auth/voice/challenge").status_code, 403)

    def test_no_setup_fails_closed(self):
        self.available[0] = False
        self.assertEqual(self.client.post("/api/auth/voice/challenge").status_code, 503)

    def test_model_error_fails_closed(self):
        challenge = self.challenge()
        self.service.speaker = lambda _: 1 / 0
        self.assertEqual(self.verify(challenge).status_code, 503)
        self.assertFalse(self.client.cookies.get(COOKIE))

    def test_identity_changed_during_verification_fails(self):
        challenge = self.challenge()
        def change(_):
            self.generation[0] = "changed"
            return True
        self.service.speaker = change
        self.assertEqual(self.verify(challenge).status_code, 503)

    def test_body_limit_and_invalid_json(self):
        result = self.client.post("/api/auth/voice/verify", content=b" " * 650_001, headers={"Content-Type": "application/json"})
        self.assertEqual(result.status_code, 413)
        self.assertEqual(self.client.post("/api/auth/voice/verify", content="{", headers={"Content-Type": "application/json"}).status_code, 400)

    def test_secure_transport_required_away_from_loopback(self):
        app = FastAPI()
        app.include_router(create_mobile_auth_router(self.service))
        with TestClient(app, base_url="http://phone.example", headers={APP_HEADER: "1", "Origin": "http://phone.example"}) as client:
            self.assertEqual(client.post("/api/auth/voice/challenge").status_code, 403)


class MobileApiIntegrationTests(MobileAuthTests):
    # Reuse login helpers with the real route-level permission dependency.
    def setUp(self):
        super().setUp()
        from core.api.server import create_app
        self.seen = []
        class Gate:
            def authorize(gate, operation):
                self.seen.append(operation)
                return False
        self.client.close()
        self.app = create_app(token_verifier=lambda t: t == "test-token", client_gate=Gate(), include_carplay=False,
                              mobile_auth_service=self.service)
        self.client = TestClient(self.app, base_url="https://testserver", headers=HEADERS)
        self.addCleanup(self.client.close)

    def test_no_token_and_no_session_is_unauthorized(self):
        self.assertEqual(self.client.get("/api/auth/check").status_code, 401)

    def test_voice_session_authenticates_without_api_token(self):
        self.login()
        self.assertEqual(self.client.get("/api/auth/check").status_code, 200)

    def test_voice_does_not_bypass_operation_gate(self):
        self.login()
        result = self.client.get("/api/status")
        self.assertEqual(result.status_code, 403)
        self.assertEqual(self.seen, ["status.read"])

    def test_cookie_cannot_be_used_from_other_origins(self):
        self.login()
        self.assertEqual(self.client.get("/api/auth/check", headers={"Origin": "https://other.example"}).status_code, 401)

    def test_token_access_still_works(self):
        self.assertEqual(self.client.get("/api/auth/check", headers={"X-ZAENIA-API-TOKEN": "test-token"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
