"""Face ID sign-in for the phone web app (Grey, 2026-11-01: "build it").

A WebAuthn passkey made on Grey's iPhone: Safari asks for Face ID before the phone signs ZAE's challenge, and ZAE
only ever sees Apple's signed answer, never the face. Rules:

* Registering a key needs a phone that is already signed in (voice) AND Grey's approval on the PC (desktop key).
  Until approved, the key can't sign anything in.
* Signing in checks the challenge, the site (rp id and origin), that the person was present and verified
  (Face ID / passcode), and the P-256 signature. It gives the same phone session as voice sign-in: nothing on the
  PC side (passkey, security, folder grants) changes.
* Keys live in data/secure/phone_passkeys.json (public keys only) and can be removed from the PC.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import struct
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
KEYS_FILE = ROOT / "data" / "secure" / "phone_passkeys.json"
CHALLENGE_TTL = 120
PENDING_TTL = 600
USER_ID = b"zaenia-owner"


class PasskeyError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64u(text: str) -> bytes:
    if not isinstance(text, str) or len(text) > 4096:
        raise PasskeyError("The Face ID answer could not be read.")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, TypeError) as error:
        raise PasskeyError("The Face ID answer could not be read.") from error


# ---------------------------------------------------------------- minimal CBOR (what WebAuthn sends)
def cbor_decode(data: bytes, pos: int = 0) -> tuple[Any, int]:
    if pos >= len(data):
        raise PasskeyError("The Face ID key data is incomplete.")
    first = data[pos]; pos += 1
    major, info = first >> 5, first & 31
    if info < 24:
        value = info
    elif info in (24, 25, 26, 27):
        size = 1 << (info - 24)
        if pos + size > len(data):
            raise PasskeyError("The Face ID key data is incomplete.")
        value = int.from_bytes(data[pos:pos + size], "big"); pos += size
    else:
        raise PasskeyError("The Face ID key data uses an unsupported format.")
    if major == 0:
        return value, pos
    if major == 1:
        return -1 - value, pos
    if major in (2, 3):
        if pos + value > len(data):
            raise PasskeyError("The Face ID key data is incomplete.")
        raw = data[pos:pos + value]; pos += value
        return (raw if major == 2 else raw.decode("utf-8")), pos
    if major == 4:
        items = []
        for _ in range(value):
            item, pos = cbor_decode(data, pos); items.append(item)
        return items, pos
    if major == 5:
        out = {}
        for _ in range(value):
            k, pos = cbor_decode(data, pos); v, pos = cbor_decode(data, pos); out[k] = v
        return out, pos
    if major == 7 and info in (20, 21, 22):
        return {20: False, 21: True, 22: None}[info], pos
    raise PasskeyError("The Face ID key data uses an unsupported format.")


def parse_auth_data(auth: bytes, rp_id: str, *, attested: bool) -> dict[str, Any]:
    if len(auth) < 37:
        raise PasskeyError("The Face ID answer is incomplete.")
    if auth[:32] != hashlib.sha256(rp_id.encode()).digest():
        raise PasskeyError("That Face ID key belongs to a different site.", 403)
    flags = auth[32]
    if not flags & 0x01 or not flags & 0x04:
        raise PasskeyError("Face ID (or your passcode) has to confirm it's you.", 403)
    out: dict[str, Any] = {"count": struct.unpack(">I", auth[33:37])[0]}
    if attested:
        if not flags & 0x40 or len(auth) < 55:
            raise PasskeyError("The new Face ID key is missing.")
        length = struct.unpack(">H", auth[53:55])[0]
        out["credential_id"] = auth[55:55 + length]
        out["cose"], _ = cbor_decode(auth, 55 + length)
    return out


def _client_data(raw: bytes, kind: str, challenge: str, origin: str) -> None:
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise PasskeyError("The Face ID answer could not be read.") from error
    if data.get("type") != kind or data.get("challenge") != challenge:
        raise PasskeyError("That Face ID request expired. Try again.", 401)
    if data.get("origin") != origin:
        raise PasskeyError("Open ZAE at its usual address to use Face ID.", 403)


def _public_key(cose: dict):
    from cryptography.hazmat.primitives.asymmetric import ec
    if cose.get(1) != 2 or cose.get(3) != -7 or cose.get(-1) != 1:
        raise PasskeyError("This kind of key isn't supported. Use the iPhone's Face ID key.")
    x, y = cose.get(-2), cose.get(-3)
    if not isinstance(x, bytes) or not isinstance(y, bytes) or len(x) != 32 or len(y) != 32:
        raise PasskeyError("The Face ID key is malformed.")
    return ec.EllipticCurvePublicNumbers(int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()).public_key()


class FacePasskeys:
    def __init__(self, path: Path = KEYS_FILE, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.lock = threading.Lock()
        self.challenges: dict[str, tuple[float, str, str]] = {}   # challenge -> (expires, kind, binding)

    # storage
    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [k for k in data.get("keys", []) if isinstance(k, dict)]
        except (OSError, ValueError, AttributeError):
            return []

    def _save(self, keys: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"keys": keys}, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def active(self) -> list[dict[str, Any]]:
        now = self.clock()
        return [k for k in self._load() if k.get("approved") or now - float(k.get("created", 0)) <= PENDING_TTL]

    def summary(self) -> list[dict[str, Any]]:
        return [{"id": k["id"][:12], "label": k.get("label", "iPhone"), "approved": bool(k.get("approved")), "created": k.get("created")} for k in self.active()]

    def has_approved(self) -> bool:
        return any(k.get("approved") for k in self._load())

    def _challenge(self, kind: str, binding: str) -> str:
        now = self.clock()
        with self.lock:
            self.challenges = {c: v for c, v in self.challenges.items() if v[0] > now}
            if len(self.challenges) > 64:
                raise PasskeyError("Face ID is busy. Try again in a minute.", 429)
            challenge = b64u(secrets.token_bytes(32))
            self.challenges[challenge] = (now + CHALLENGE_TTL, kind, binding)
            return challenge

    def _take(self, challenge: str, kind: str, binding: str) -> None:
        with self.lock:
            record = self.challenges.pop(challenge, None)
        if not record or record[0] < self.clock() or record[1] != kind or not secrets.compare_digest(record[2], binding):
            raise PasskeyError("That Face ID request expired. Try again.", 401)

    # registration (phone already signed in)
    def register_options(self, rp_id: str, binding: str) -> dict[str, Any]:
        return {"challenge": self._challenge("create", binding), "rp": {"id": rp_id, "name": "ZÆNIA"},
                "user": {"id": b64u(USER_ID), "name": "Zack", "displayName": "Zack"},
                "pubKeyCredParams": [{"type": "public-key", "alg": -7}], "timeout": CHALLENGE_TTL * 1000,
                "authenticatorSelection": {"authenticatorAttachment": "platform", "userVerification": "required", "residentKey": "preferred"},
                "attestation": "none", "excludeCredentials": [{"type": "public-key", "id": k["id"]} for k in self._load()]}

    def register(self, body: dict, rp_id: str, origin: str, binding: str, label: str = "iPhone") -> dict[str, Any]:
        client = unb64u(body.get("clientDataJSON", ""))
        try:
            challenge = json.loads(client).get("challenge", "")
        except (ValueError, AttributeError) as error:
            raise PasskeyError("The Face ID answer could not be read.") from error
        self._take(challenge, "create", binding)
        _client_data(client, "webauthn.create", challenge, origin)
        attestation, _ = cbor_decode(unb64u(body.get("attestationObject", "")))
        if not isinstance(attestation, dict) or not isinstance(attestation.get("authData"), bytes):
            raise PasskeyError("The new Face ID key could not be read.")
        auth = parse_auth_data(attestation["authData"], rp_id, attested=True)
        _public_key(auth["cose"])  # validates the key
        x, y = auth["cose"][-2], auth["cose"][-3]
        keys = self._load()
        if len(keys) >= 8:
            raise PasskeyError("There are already 8 Face ID keys. Remove one on the PC first.", 409)
        entry = {"id": b64u(auth["credential_id"]), "x": b64u(x), "y": b64u(y), "count": auth["count"], "approved": False,
                 "created": self.clock(), "label": str(label)[:40] or "iPhone"}
        self._save([k for k in keys if k["id"] != entry["id"]] + [entry])
        return {"pending": True, "id": entry["id"][:12]}

    # PC approval
    def approve(self, short_id: str) -> bool:
        keys = self._load(); changed = False
        for k in keys:
            if k["id"].startswith(short_id) and not k.get("approved") and self.clock() - float(k.get("created", 0)) <= PENDING_TTL:
                k["approved"] = True; changed = True
        if changed:
            self._save(keys)
        return changed

    def remove(self, short_id: str) -> bool:
        keys = self._load()
        kept = [k for k in keys if not k["id"].startswith(short_id)]
        if len(kept) != len(keys):
            self._save(kept)
            return True
        return False

    # sign-in
    def login_options(self, rp_id: str, binding: str) -> dict[str, Any]:
        keys = [k for k in self._load() if k.get("approved")]
        if not keys:
            raise PasskeyError("Face ID sign-in isn't set up yet. Sign in with your voice and add it.", 404)
        return {"challenge": self._challenge("get", binding), "rpId": rp_id, "timeout": CHALLENGE_TTL * 1000,
                "userVerification": "required", "allowCredentials": [{"type": "public-key", "id": k["id"], "transports": ["internal", "hybrid"]} for k in keys]}

    def login(self, body: dict, rp_id: str, origin: str, binding: str) -> None:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        client = unb64u(body.get("clientDataJSON", ""))
        try:
            challenge = json.loads(client).get("challenge", "")
        except ValueError as error:
            raise PasskeyError("The Face ID answer could not be read.") from error
        self._take(challenge, "get", binding)
        _client_data(client, "webauthn.get", challenge, origin)
        keys = self._load()
        key = next((k for k in keys if k.get("approved") and k["id"] == body.get("id")), None)
        if key is None:
            raise PasskeyError("That Face ID key isn't approved on the PC.", 403)
        auth_raw = unb64u(body.get("authenticatorData", ""))
        auth = parse_auth_data(auth_raw, rp_id, attested=False)
        public = _public_key({1: 2, 3: -7, -1: 1, -2: unb64u(key["x"]), -3: unb64u(key["y"])})
        try:
            public.verify(unb64u(body.get("signature", "")), auth_raw + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        except InvalidSignature as error:
            raise PasskeyError("Face ID couldn't be verified.", 401) from error
        # A counter that goes backwards means a copied key (iPhone passkeys report 0, which is allowed).
        if auth["count"] and auth["count"] <= int(key.get("count", 0)):
            raise PasskeyError("That Face ID key looks copied. Remove it on the PC.", 403)
        key["count"] = max(int(key.get("count", 0)), auth["count"]); key["used"] = self.clock()
        self._save(keys)


_INSTANCE: FacePasskeys | None = None


def face_passkeys() -> FacePasskeys:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = FacePasskeys()
    return _INSTANCE
