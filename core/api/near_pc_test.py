import base64
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from core.api.near_pc import ACTIVE_SECONDS, CODE_SECONDS, SETUP_SECONDS, NearPc


class Clock:
    def __init__(self): self.now = 1000.0
    def __call__(self): return self.now


def first(order):
    return patch("core.api.near_pc.secrets.choice", return_value=order)


class NearPcTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.near = NearPc(clock=self.clock)

    def test_the_first_step_is_picked_at_random(self):
        seen = {self.near.start()["first"] for _ in range(60)}
        self.assertEqual(seen, {"code", "voice"})

    def test_the_second_step_waits_for_the_first(self):
        with first("voice"):
            secret = self.near.start()["secret"]
        self.assertIsNone(self.near.code_for_pc())  # no code on the PC yet
        with self.assertRaises(ValueError):
            self.near.submit_code(secret, "123456")
        self.assertTrue(self.near.pending(secret))
        with first("code"):
            secret = self.near.start()["secret"]
        self.assertFalse(self.near.pending(secret))  # voice isn't open until the code is in
        with self.assertRaises(PermissionError):
            self.near.voice_passed(secret)
        self.assertIsNotNone(self.near.code_for_pc())

    def test_code_then_voice_turns_the_pass_on(self):
        with first("code"):
            secret = self.near.start()["secret"]
        self.assertFalse(self.near.allows(secret))
        code = self.near.code_for_pc()["code"]
        self.assertEqual(len(code), 6)
        self.assertTrue(self.near.submit_code(secret, code)["code"])
        self.assertIsNone(self.near.code_for_pc())  # the PC stops showing it once it's used
        self.assertFalse(self.near.allows(secret))
        self.assertTrue(self.near.voice_passed(secret)["active"])
        self.assertTrue(self.near.allows(secret))
        self.clock.now += ACTIVE_SECONDS + 1
        self.assertFalse(self.near.allows(secret))

    def test_the_qr_key_works_and_an_old_one_does_not(self):
        with first("code"):
            secret = self.near.start()["secret"]
        shown = self.near.code_for_pc()
        self.assertTrue(shown["qr"].startswith("zae-near:"))
        self.assertGreater(len(shown["qr"]), 30)
        self.clock.now += CODE_SECONDS + 1
        fresh = self.near.code_for_pc()["qr"]
        self.assertNotEqual(fresh, shown["qr"])
        with self.assertRaises(ValueError):
            self.near.submit_code(secret, shown["qr"])
        self.assertTrue(self.near.submit_code(secret, fresh)["code"])

    def test_voice_then_code_works_too(self):
        with first("voice"):
            secret = self.near.start()["secret"]
        self.assertTrue(self.near.pending(secret))
        self.assertFalse(self.near.voice_passed(secret)["active"])
        self.assertFalse(self.near.pending(secret))
        self.assertTrue(self.near.code_for_pc()["voice"])
        self.assertTrue(self.near.submit_code(secret, self.near.code_for_pc()["code"])["active"])
        self.assertTrue(self.near.allows(secret))

    def test_wrong_secret_wrong_code_and_old_code_are_refused(self):
        with first("code"):
            secret = self.near.start()["secret"]
        code = self.near.code_for_pc()["code"]
        self.assertFalse(self.near.allows("someone-else"))
        with self.assertRaises(PermissionError):
            self.near.submit_code("someone-else", code)
        with self.assertRaises(ValueError):
            self.near.submit_code(secret, "000000" if code != "000000" else "111111")
        self.clock.now += CODE_SECONDS + 1
        fresh = self.near.code_for_pc()["code"]  # rotated
        if fresh != code:
            with self.assertRaises(ValueError):
                self.near.submit_code(secret, code)
        self.assertTrue(self.near.submit_code(secret, fresh)["code"])

    def test_five_wrong_codes_end_the_pass(self):
        with first("code"):
            secret = self.near.start()["secret"]
        code = self.near.code_for_pc()["code"]
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(4):
            with self.assertRaises(ValueError):
                self.near.submit_code(secret, wrong)
        with self.assertRaises(PermissionError):
            self.near.submit_code(secret, wrong)
        self.assertFalse(self.near.status(secret)["pass"])

    def test_setup_expires_and_a_new_pass_replaces_the_old(self):
        first = self.near.start()["secret"]
        self.clock.now += SETUP_SECONDS + 1
        self.assertFalse(self.near.status(first)["pass"])
        first = self.near.start()["secret"]
        second = self.near.start()["secret"]
        self.assertFalse(self.near.status(first)["pass"])
        self.assertTrue(self.near.status(second)["pass"])
        self.near.end(from_pc=True)
        self.assertFalse(self.near.status(second)["pass"])


class NearPcApiTest(unittest.TestCase):
    """End to end: the phone's pass approves a waiting file change only after the PC code and a voice check."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from core.api.mobile_auth import MobileAuth
        from core.api.server import create_app
        from core.api import near_pc
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.near = NearPc()
        self.stack.enter_context(patch.object(near_pc, "_instance", self.near))
        self.stack.enter_context(patch("core.api.desktop_key.verify", side_effect=lambda key: key == "pc-key"))
        self.stack.enter_context(patch("core.api.desktop_key.is_paired", return_value=True))
        self.stack.enter_context(patch("core.foundation.security.audit.audit"))
        self.stack.enter_context(patch("core.api.ui_routes.audit"))
        self.phrase = ""
        auth = MobileAuth(speaker=lambda pcm: True, transcribe=lambda pcm: self.phrase, generation=lambda: 1, available=lambda: True)

        class Gate:
            def authorize(self, operation): return operation is not None
        self.client = self.stack.enter_context(TestClient(create_app(
            token_verifier=lambda token: token == "phone-token", client_gate=Gate(), include_carplay=False,
            include_phone_app=False, mobile_auth_service=auth)))
        self.client.headers.update({"X-ZAENIA-API-TOKEN": "phone-token", "X-ZAENIA-APP": "1"})

    def approve(self, secret):
        return self.client.post("/api/files/proposals/" + "a" * 32 + "/approve", headers={"X-ZAENIA-NEAR-PASS": secret})

    def test_pass_needs_both_steps_then_reaches_the_approval(self):
        with first("code"):
            secret = self.client.post("/api/near/start").json()["secret"]
        self.assertEqual(self.approve(secret).status_code, 403)
        # PC shows the code (desktop key only).
        self.assertEqual(self.client.get("/api/remote/collect").status_code, 403)
        code = self.client.get("/api/remote/collect", headers={"X-ZAENIA-DESKTOP-KEY": "pc-key"}).json()["nearCode"]["code"]
        self.assertEqual(self.client.post("/api/near/code", json={"code": code}, headers={"X-ZAENIA-NEAR-PASS": secret}).status_code, 200)
        self.assertEqual(self.approve(secret).status_code, 403)
        # Voice: a wrong pass can't run it; the right one can.
        self.assertEqual(self.client.post("/api/auth/voice/near", json={}, headers={"X-ZAENIA-NEAR-PASS": "nope"}).status_code, 403)
        challenge = self.client.post("/api/auth/voice/challenge").json()
        self.phrase = challenge["phrase"]
        audio = base64.b64encode(b"\x01\x00" * 40_000).decode()
        voice = self.client.post("/api/auth/voice/near", json={"challenge_id": challenge["challenge_id"], "audio": audio},
                                 headers={"X-ZAENIA-NEAR-PASS": secret})
        self.assertEqual(voice.status_code, 200, voice.text)
        self.assertTrue(voice.json()["active"])
        self.assertNotIn("zaenia_mobile_session", voice.cookies)  # the voice step signs nothing in
        reply = self.approve(secret)
        self.assertIn(reply.status_code, (404, 422), reply.text)  # past the gate; the made-up change just isn't there
        # Not a master key: direct file edits still need the desktop app.
        edit = self.client.put("/api/files/content", json={"path": "x.txt", "baseSha256": "0" * 64, "text": "x"},
                               headers={"X-ZAENIA-NEAR-PASS": secret})
        self.assertEqual(edit.status_code, 403)
        self.client.post("/api/near/end", headers={"X-ZAENIA-NEAR-PASS": secret})
        self.assertEqual(self.approve(secret).status_code, 403)

    def test_routes_have_capabilities(self):
        from core.api.ui_routes import operation_for
        self.assertEqual(operation_for("POST", "/api/near/start"), "assistant.desktop.manage")
        self.assertEqual(operation_for("POST", "/api/near/code"), "assistant.desktop.manage")
        self.assertEqual(operation_for("GET", "/api/near/status"), "status.read")


if __name__ == "__main__":
    unittest.main()
