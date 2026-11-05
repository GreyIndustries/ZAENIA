"""Separate Calm-view return password; never an owner or execution credential.

Only the trusted local console can create/change/remove this password, after a
fresh existing owner-passkey proof. The authenticated API can check it to return
from Calm view; success does not create a session, permission, or action grant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import threading
import time
from pathlib import Path
from typing import Callable

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError

from core.foundation.security.audit import audit
from core.foundation.security.io import atomic_write, file_lock, reject_link
from core.foundation.storage.paths import SECURE_DIR

PASSWORD_FILE = SECURE_DIR / "calm_return_password.json"
MIN_LENGTH = 12
MAX_LENGTH = 128
MAX_FAILURES = 5
LOCK_SECONDS = 30
_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)


class CalmPasswordError(Exception):
    def __init__(self, message: str, status: int = 400, *, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def configure_payload(password: str) -> dict[str, str]:
    return {"purpose": "calm.password.configure", "password_digest": hashlib.sha256(password.encode("utf-8")).hexdigest()}


class CalmPassword:
    def __init__(self, path: Path = PASSWORD_FILE, *, clock: Callable[[], float] = time.time, hasher: PasswordHasher | None = None):
        self.path = Path(path)
        self.clock = clock
        self.hasher = hasher or _HASHER
        self.lock = threading.RLock()

    @staticmethod
    def validate_new(password: str) -> None:
        if not CalmPassword._valid_text(password, minimum=MIN_LENGTH) or not password.strip():
            raise CalmPasswordError(f"Use a dashboard password of {MIN_LENGTH}–{MAX_LENGTH} characters.", 422)

    @staticmethod
    def _valid_text(password: str, *, minimum: int = 1) -> bool:
        if not isinstance(password, str) or not minimum <= len(password) <= MAX_LENGTH:
            return False
        try:
            return len(password.encode("utf-8")) <= MAX_LENGTH * 4
        except UnicodeEncodeError:
            return False

    def _read(self) -> dict | None:
        reject_link(self.path)
        if not self.path.exists():
            return None
        try:
            if not self.path.is_file() or self.path.stat().st_size > 4096:
                raise ValueError()
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or set(record) != {"version", "hash", "failures", "locked_until"}:
                raise ValueError()
            if type(record["version"]) is not int or record["version"] != 1 or not isinstance(record["hash"], str) or not 50 <= len(record["hash"]) <= 512:
                raise ValueError()
            if type(record["failures"]) is not int or not 0 <= record["failures"] <= MAX_FAILURES:
                raise ValueError()
            if type(record["locked_until"]) not in (int, float) or not math.isfinite(record["locked_until"]) or record["locked_until"] < 0:
                raise ValueError()
            params = extract_parameters(record["hash"])
            if (params.type is not Type.ID or params.version != 19 or not 1 <= params.time_cost <= 5
                    or not 8192 <= params.memory_cost <= 131072 or not 1 <= params.parallelism <= 4
                    or not 16 <= params.salt_len <= 32 or not 16 <= params.hash_len <= 64):
                raise ValueError()
            return record
        except (OSError, ValueError, TypeError, KeyError, OverflowError, InvalidHashError) as error:
            raise CalmPasswordError("The dashboard password store is unavailable. Use its owner setup console to recover it.", 503) from error

    def _save(self, record: dict) -> None:
        atomic_write(self.path, json.dumps(record, separators=(",", ":"), allow_nan=False).encode("utf-8"))

    def status(self) -> dict[str, bool]:
        with self.lock:
            reject_link(self.path)
            if not self.path.exists():
                return {"configured": False}
            with file_lock(self.path.with_suffix(".lock")):
                return {"configured": self._read() is not None}

    def configure(self, password: str, owner_proof: object) -> None:
        self.validate_new(password)
        from core.foundation.auth.passkey import consume_fresh_auth
        consume_fresh_auth(owner_proof, operation="calm.password.configure", payload=configure_payload(password))
        with self.lock, file_lock(self.path.with_suffix(".lock")):
            self._save({"version": 1, "hash": self.hasher.hash(password), "failures": 0, "locked_until": 0})
        audit("calm.password_configured", operation="calm.password.configure", reason_code="owner_console")

    def reset(self, owner_proof: object) -> None:
        from core.foundation.auth.passkey import consume_fresh_auth
        consume_fresh_auth(owner_proof, operation="calm.password.reset", payload={"purpose": "calm.password.reset"})
        with self.lock, file_lock(self.path.with_suffix(".lock")):
            reject_link(self.path)
            self.path.unlink(missing_ok=True)
        audit("calm.password_reset", operation="calm.password.reset", reason_code="owner_console")

    def verify(self, password: str) -> bool:
        if not self._valid_text(password):
            raise CalmPasswordError("Enter your dashboard password.", 422)
        with self.lock, file_lock(self.path.with_suffix(".lock")):
            record = self._read()
            if record is None:
                raise CalmPasswordError("Create your dashboard password in the local owner setup console first.", 409)
            now = self.clock()
            if record["locked_until"] > now:
                delay = max(1, math.ceil(record["locked_until"] - now))
                audit("calm.password_rejected", operation="calm.password.verify", reason_code="temporarily_rate_limited")
                raise CalmPasswordError("Too many attempts. Wait before trying the dashboard password again.", 429, retry_after=delay)
            if record["locked_until"]:
                record["failures"] = 0
                record["locked_until"] = 0
            try:
                valid = self.hasher.verify(record["hash"], password)
            except InvalidHashError as error:
                raise CalmPasswordError("The dashboard password store is unavailable. Use its owner setup console to recover it.", 503) from error
            except VerificationError:
                valid = False
            if not valid:
                record["failures"] += 1
                record["locked_until"] = now + LOCK_SECONDS if record["failures"] >= MAX_FAILURES else 0
                self._save(record)
                audit("calm.password_rejected", operation="calm.password.verify", reason_code="credential_rejected")
                raise CalmPasswordError("That dashboard password did not match.", 401)
            record["failures"] = 0
            record["locked_until"] = 0
            if self.hasher.check_needs_rehash(record["hash"]):
                record["hash"] = self.hasher.hash(password)
            self._save(record)
        audit("calm.password_verified", operation="calm.password.verify", reason_code="calm_return_only")
        return True


_SERVICE: CalmPassword | None = None
_SERVICE_LOCK = threading.Lock()


def calm_password() -> CalmPassword:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = CalmPassword()
        return _SERVICE


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset the separate Calm-view dashboard password locally.")
    parser.add_argument("action", choices=("setup", "reset"))
    args = parser.parse_args()
    from core.foundation.auth.passkey import _private_input, require_passkey
    service = calm_password()
    try:
        if args.action == "setup":
            print("This password returns from Calm view; your existing owner passkey stays separate.")
            password = _private_input(f"Create dashboard password ({MIN_LENGTH}–{MAX_LENGTH} characters): ")
            confirmation = _private_input("Confirm dashboard password: ")
            service.validate_new(password)
            if password != confirmation:
                raise CalmPasswordError("The dashboard passwords did not match; nothing changed.", 422)
            proof = require_passkey(operation="calm.password.configure", payload=configure_payload(password))
            service.configure(password, proof)
            del password, confirmation, proof
            print("Dashboard password saved. Refresh its status in the app.")
        else:
            if input("Type RESET to remove only the Calm-view password: ") != "RESET":
                print("Nothing changed.")
                return
            proof = require_passkey(operation="calm.password.reset", payload={"purpose": "calm.password.reset"})
            service.reset(proof)
            print("Dashboard password removed. Configure a new one before using the password return gate.")
    except (CalmPasswordError, PermissionError, RuntimeError, OSError) as error:
        print(f"Dashboard password unchanged or unavailable: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
