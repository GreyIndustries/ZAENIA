import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from core.api.face_passkey import FacePasskeys, PasskeyError, b64u, cbor_decode

RP, ORIGIN = "zae.tail1234.ts.net", "https://zae.tail1234.ts.net"


def cbor(value) -> bytes:
    def head(major, n):
        if n < 24: return bytes([major << 5 | n])
        if n < 256: return bytes([major << 5 | 24, n])
        return bytes([major << 5 | 25]) + n.to_bytes(2, "big")
    if isinstance(value, bool): return bytes([0xF5 if value else 0xF4])
    if isinstance(value, int): return head(0, value) if value >= 0 else head(1, -1 - value)
    if isinstance(value, bytes): return head(2, len(value)) + value
    if isinstance(value, str): return head(3, len(value.encode())) + value.encode()
    if isinstance(value, dict): return head(5, len(value)) + b"".join(cbor(k) + cbor(v) for k, v in value.items())
    raise TypeError(value)


class Phone:
    """A pretend iPhone passkey: makes the same answers Safari would."""
    def __init__(self, rp=RP, origin=ORIGIN):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred = b"cred-" + bytes(range(16))
        self.rp, self.origin, self.count = rp, origin, 0

    def client(self, kind, challenge):
        return json.dumps({"type": kind, "challenge": challenge, "origin": self.origin}).encode()

    def create(self, options, flags=0x45):
        nums = self.key.public_key().public_numbers()
        cose = {1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")}
        auth = hashlib.sha256(self.rp.encode()).digest() + bytes([flags]) + struct.pack(">I", 0) + bytes(16) \
            + struct.pack(">H", len(self.cred)) + self.cred + cbor(cose)
        return {"clientDataJSON": b64u(self.client("webauthn.create", options["challenge"])),
                "attestationObject": b64u(cbor({"fmt": "none", "attStmt": {}, "authData": auth}))}

    def get(self, options, flags=0x05):
        client = self.client("webauthn.get", options["challenge"])
        auth = hashlib.sha256(self.rp.encode()).digest() + bytes([flags]) + struct.pack(">I", self.count)
        signature = self.key.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": b64u(self.cred), "clientDataJSON": b64u(client), "authenticatorData": b64u(auth), "signature": b64u(signature)}


class FacePasskeyTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.now = [1000.0]
        self.keys = FacePasskeys(Path(self.folder.name) / "keys.json", clock=lambda: self.now[0])
        self.phone = Phone()

    def tearDown(self):
        self.folder.cleanup()

    def enrol(self, approve=True):
        options = self.keys.register_options(RP, "bind-1")
        result = self.keys.register(self.phone.create(options), RP, ORIGIN, "bind-1")
        if approve:
            self.assertTrue(self.keys.approve(result["id"]))
        return result

    def test_cbor_round_trip(self):
        self.assertEqual(cbor_decode(cbor({1: 2, -1: b"ab", "x": "y"}))[0], {1: 2, -1: b"ab", "x": "y"})

    def test_face_id_signs_in_only_after_the_pc_approves_the_key(self):
        self.enrol(approve=False)
        with self.assertRaises(PasskeyError):
            self.keys.login_options(RP, "bind-2")              # nothing approved yet
        pending = [k for k in self.keys.summary() if not k["approved"]]
        self.assertEqual(len(pending), 1)
        self.assertTrue(self.keys.approve(pending[0]["id"]))
        self.assertTrue(self.keys.has_approved())
        options = self.keys.login_options(RP, "bind-2")
        self.keys.login(self.phone.get(options), RP, ORIGIN, "bind-2")   # no exception = signed in

    def test_a_challenge_works_once_and_only_with_its_own_cookie(self):
        self.enrol()
        options = self.keys.login_options(RP, "bind-2")
        answer = self.phone.get(options)
        with self.assertRaises(PasskeyError):
            self.keys.login(answer, RP, ORIGIN, "another-browser")
        options = self.keys.login_options(RP, "bind-3")
        answer = self.phone.get(options)
        self.keys.login(answer, RP, ORIGIN, "bind-3")
        with self.assertRaises(PasskeyError):
            self.keys.login(answer, RP, ORIGIN, "bind-3")       # replay

    def test_wrong_site_missing_face_id_or_another_key_is_refused(self):
        self.enrol()
        options = self.keys.login_options(RP, "b")
        with self.assertRaises(PasskeyError):                    # Face ID / passcode not used (UV flag off)
            self.keys.login(self.phone.get(options, flags=0x01), RP, ORIGIN, "b")
        options = self.keys.login_options(RP, "b")
        with self.assertRaises(PasskeyError):                    # another site
            self.keys.login(self.phone.get(options), RP, "https://evil.example", "b")
        options = self.keys.login_options(RP, "b")
        impostor = Phone(); impostor.cred = self.phone.cred      # same id, different private key
        with self.assertRaises(PasskeyError):
            self.keys.login(impostor.get(options), RP, ORIGIN, "b")

    def test_unapproved_keys_expire_and_removed_keys_stop_working(self):
        result = self.enrol(approve=False)
        self.now[0] += 601
        self.assertFalse(self.keys.approve(result["id"]))       # too late to approve
        self.phone = Phone()
        result = self.enrol()
        self.assertTrue(self.keys.remove(result["id"]))
        with self.assertRaises(PasskeyError):
            self.keys.login_options(RP, "b")

    def test_only_public_keys_are_stored(self):
        self.enrol()
        saved = json.loads((Path(self.folder.name) / "keys.json").read_text())["keys"][0]
        self.assertEqual(set(saved), {"id", "x", "y", "count", "approved", "created", "label"})


class FacePasskeyRoutesTest(unittest.TestCase):
    def test_add_on_a_signed_in_phone_approve_on_pc_then_sign_in_with_face_id(self):
        from unittest.mock import patch
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.api import face_passkey
        from core.api.mobile_auth import COOKIE, MobileAuth
        from core.api.mobile_auth_routes import create_mobile_auth_router
        with tempfile.TemporaryDirectory() as folder, patch("core.foundation.security.audit.audit"):
            store = FacePasskeys(Path(folder) / "keys.json")
            auth = MobileAuth(speaker=lambda pcm: True, transcribe=lambda pcm: "", generation=lambda: 1, available=lambda: True)
            app = FastAPI(); app.include_router(create_mobile_auth_router(auth))
            client = TestClient(app); client.headers.update({"X-ZAENIA-APP": "1"})
            phone = Phone(rp="testserver", origin="http://testserver")
            with patch.object(face_passkey, "_INSTANCE", store):
                self.assertEqual(client.post("/api/auth/passkey/register/options").status_code, 401)   # not signed in
                client.cookies.set(COOKIE, auth.issue_session(), path="/api")
                options = client.post("/api/auth/passkey/register/options").json()
                added = client.post("/api/auth/passkey/register", json=phone.create(options))
                self.assertEqual(added.status_code, 200, added.text)
                self.assertFalse(client.get("/api/auth/passkey/status").json()["available"])   # waits for the PC
                store.approve(added.json()["id"])
                client.cookies.clear()
                options = client.post("/api/auth/passkey/login/options").json()
                signed = client.post("/api/auth/passkey/login", json=phone.get(options))
                self.assertEqual(signed.status_code, 200, signed.text)
                self.assertTrue(auth.authenticated(signed.cookies.get(COOKIE)))


if __name__ == "__main__":
    unittest.main()
