"""Isolated Calm password checks. No owner credentials or real state are read."""
from __future__ import annotations

from contextlib import ExitStack
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from argon2 import PasswordHasher
from fastapi import HTTPException, Request

from core.api import calm_password as cp
from core.api import calm_password_routes as routes
from core.api.calm_password_routes import create_calm_password_router, operation_for


class Clock:
    now = 1_000_000.0

    def __call__(self):
        return self.now


class Fixture:
    def setUp(self):
        self.stack = ExitStack()
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.clock = Clock()
        self.hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1, salt_len=16, hash_len=32)
        self.service = cp.CalmPassword(self.folder / "calm.json", clock=self.clock, hasher=self.hasher)
        self.stack.enter_context(patch.object(cp, "audit"))

    def tearDown(self):
        self.stack.close()

    def configure(self, password="isolated example password"):
        proof = object()
        with patch("core.foundation.auth.passkey.consume_fresh_auth") as consume:
            self.service.configure(password, proof)
            consume.assert_called_once_with(proof, operation="calm.password.configure", payload=cp.configure_payload(password))
        return password


class PasswordTest(Fixture, unittest.TestCase):
    def test_creation_requires_owner_proof_and_never_stores_plaintext(self):
        self.assertEqual(self.service.status(), {"configured": False})
        with self.assertRaises(PermissionError):
            self.service.configure("isolated example password", object())
        self.assertFalse(self.service.path.exists())
        password = self.configure()
        raw = self.service.path.read_text()
        self.assertNotIn(password, raw)
        self.assertIn("$argon2id$", raw)
        self.assertEqual(self.service.status(), {"configured": True})
        self.assertTrue(self.service.verify(password))
        first_hash = json.loads(raw)["hash"]
        self.configure(password)
        self.assertNotEqual(first_hash, json.loads(self.service.path.read_text())["hash"])

    def test_invalid_new_password_does_not_consume_owner_proof(self):
        with patch("core.foundation.auth.passkey.consume_fresh_auth") as consume:
            for password in ("short", " " * 20, "x" * 129):
                with self.assertRaises(cp.CalmPasswordError):
                    self.service.configure(password, object())
            consume.assert_not_called()

    def test_unicode_password_limit_counts_code_points(self):
        password = "\U0001f680" * cp.MAX_LENGTH
        self.configure(password)
        self.assertTrue(self.service.verify(password))
        self.assertLess(len(json.dumps({"password": password}, ensure_ascii=False).encode("utf-8")), 1024)
        with self.assertRaises(cp.CalmPasswordError):
            self.service.validate_new(password + "\U0001f680")

    def test_throttle_persists_across_service_restart_and_recovers(self):
        password = self.configure()
        for _ in range(cp.MAX_FAILURES):
            with self.assertRaises(cp.CalmPasswordError) as wrong:
                self.service.verify("incorrect")
            self.assertEqual(wrong.exception.status, 401)
        restarted = cp.CalmPassword(self.service.path, clock=self.clock, hasher=self.hasher)
        with self.assertRaises(cp.CalmPasswordError) as limited:
            restarted.verify(password)
        self.assertEqual(limited.exception.status, 429)
        self.assertEqual(limited.exception.retry_after, 30)
        self.clock.now += 31
        self.assertTrue(restarted.verify(password))
        saved = json.loads(self.service.path.read_text())
        self.assertEqual((saved["failures"], saved["locked_until"]), (0, 0))

    def test_missing_or_corrupt_store_does_not_unlock(self):
        with self.assertRaises(cp.CalmPasswordError) as missing:
            self.service.verify("isolated example password")
        self.assertEqual(missing.exception.status, 409)
        self.service.path.write_text('{"version":1}')
        with self.assertRaises(cp.CalmPasswordError) as corrupt:
            self.service.status()
        self.assertEqual(corrupt.exception.status, 503)
        self.assertEqual(self.service.path.read_text(), '{"version":1}')

    def test_reset_requires_owner_proof_and_only_removes_calm_password(self):
        self.configure()
        other = self.folder / "owner.hash"
        other.write_text("unrelated fixture")
        with self.assertRaises(PermissionError):
            self.service.reset(object())
        self.assertTrue(self.service.status()["configured"])
        proof = object()
        with patch("core.foundation.auth.passkey.consume_fresh_auth") as consume:
            self.service.reset(proof)
            consume.assert_called_once_with(proof, operation="calm.password.reset", payload={"purpose": "calm.password.reset"})
        self.assertEqual(self.service.status(), {"configured": False})
        self.assertEqual(other.read_text(), "unrelated fixture")

    def test_cancelled_confirmation_does_not_request_owner_proof_or_change_password(self):
        self.configure()
        before = self.service.path.read_bytes()
        with patch.object(cp, "calm_password", return_value=self.service), \
                patch("sys.argv", ["calm_password", "setup"]), \
                patch("core.foundation.auth.passkey._private_input", side_effect=["new example password", "does not match"]), \
                patch("core.foundation.auth.passkey.require_passkey") as auth, \
                patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                cp.main()
            auth.assert_not_called()
        self.assertEqual(self.service.path.read_bytes(), before)


class RoutesTest(Fixture, unittest.TestCase):
    def test_authentication_shape_status_and_no_secret_echo(self):
        def authenticate():
            raise AssertionError("The full API supplies the existing client authenticator.")

        router = create_calm_password_router(authenticate, provider=lambda: self.service)
        handlers = {route.path: route for route in router.routes}
        for route in router.routes:
            self.assertIn(authenticate, [dependency.dependency for dependency in route.dependencies])
        self.assertNotIn("/api/calm/password/setup", handlers)
        status = handlers["/api/calm/password/status"].endpoint
        verify = handlers["/api/calm/password/verify"].endpoint
        self.assertEqual(status(), {"configured": False})
        self.configure()
        self.assertEqual(status(), {"configured": True})

        def request(body):
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            return Request({"type": "http", "method": "POST", "path": "/api/calm/password/verify", "headers": []}, receive)

        # Check endpoint behavior directly: the sandbox's ASGI transport cannot
        # reliably start an AnyIO worker thread. This is not a live auth test.
        async def direct(function, *args):
            return function(*args)

        def complete(coroutine):
            # The request receiver and the patched worker complete immediately;
            # avoid the unavailable Windows async transport in these unit checks.
            try:
                coroutine.send(None)
            except StopIteration as result:
                return result.value
            finally:
                coroutine.close()
            raise AssertionError("Unexpected asynchronous transport dependency.")

        with patch.object(routes, "run_in_threadpool", direct):
            marker = "never-echo-this-value"
            with self.assertRaises(HTTPException) as invalid:
                complete(verify(request(json.dumps({"password": {"private": marker}}).encode())))
            self.assertEqual(invalid.exception.status_code, 422)
            self.assertNotIn(marker, str(invalid.exception.detail))
            with self.assertRaises(HTTPException) as oversized:
                complete(verify(request((marker * 100).encode())))
            self.assertEqual(oversized.exception.status_code, 413)
            self.assertNotIn(marker, str(oversized.exception.detail))
            success = complete(verify(request(json.dumps({"password": "isolated example password"}).encode())))
            self.assertEqual(success, {"unlocked": True})
            self.assertNotIn("session", success)

    def test_routes_map_only_to_existing_ui_status_permission(self):
        self.assertEqual(operation_for("GET", "/api/calm/password/status"), "status.read")
        self.assertEqual(operation_for("POST", "/api/calm/password/verify"), "status.read")
        self.assertIsNone(operation_for("POST", "/api/calm/password/setup"))
        self.assertIsNone(operation_for("POST", "/api/calm/password/status"))


if __name__ == "__main__":
    unittest.main()
