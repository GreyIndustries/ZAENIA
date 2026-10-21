"""Owner passkeys and short-lived proof of a specific fresh authentication."""
from __future__ import annotations
from contextlib import closing
from getpass import getpass, GetPassWarning
import hashlib
import json
import secrets
import sqlite3
import threading
import time
import warnings
from typing import Any
from argon2 import PasswordHasher, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError
from core.foundation.security.audit import audit
from core.foundation.security.io import atomic_write, reject_link
from core.foundation.storage.paths import PASSKEY_FILE, AUTH_RATE_FILE, ensure_storage

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)
_PROOFS: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()
FRESH_SECONDS = 60.0

def _private_input(prompt: str) -> str:
    # getpass's nonterminal fallback can echo secrets; reject that fallback.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error",GetPassWarning)
            return getpass(prompt)
    except GetPassWarning as error:
        raise RuntimeError("Authenticate in an interactive local terminal with hidden input.") from error

def payload_digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    if len(text.encode("utf-8")) > 65536:
        raise ValueError("Authorization payload exceeds the size limit.")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def credential_generation() -> str:
    reject_link(PASSKEY_FILE)
    return hashlib.sha256(PASSKEY_FILE.read_bytes()).hexdigest()

def passkey_exists() -> bool:
    reject_link(PASSKEY_FILE)
    return PASSKEY_FILE.is_file()

def _validate_new_passphrase(passphrase: str) -> None:
    if not isinstance(passphrase, str) or len(passphrase.strip()) < 16 or len(passphrase.encode("utf-8")) > 4096:
        raise ValueError("Use a private passphrase of at least 16 characters.")

def create_passkey(passphrase: str | None = None, confirmation: str | None = None) -> None:
    ensure_storage()
    if passkey_exists():
        raise RuntimeError("Passkey already exists; refusing to overwrite it.")
    if passphrase is None:
        passphrase = _private_input("Create ZÆNIA passkey phrase: ")
        confirmation = _private_input("Confirm ZÆNIA passkey phrase: ")
    _validate_new_passphrase(passphrase)
    if confirmation != passphrase:
        raise ValueError("Passkey phrases do not match.")
    atomic_write(PASSKEY_FILE, ph.hash(passphrase).encode("utf-8"), overwrite=False)
    audit("auth.created", reason_code="owner_passkey_created")

def verify_passkey(passphrase: str) -> bool:
    if not passkey_exists():
        raise RuntimeError("No passkey exists. Run setup first.")
    if not isinstance(passphrase, str) or not passphrase or len(passphrase.encode("utf-8")) > 4096:
        return False
    ensure_storage()
    reject_link(AUTH_RATE_FILE)
    # SQLite's transaction context does not close its file handle. Commit or
    # roll back first, then close, including every early return and exception.
    with closing(sqlite3.connect(AUTH_RATE_FILE, timeout=15)) as db, db:
        if __import__("os").name != "nt":
            AUTH_RATE_FILE.chmod(0o600)
        db.execute("CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY CHECK(id=1), failures INTEGER NOT NULL, locked_until REAL NOT NULL)")
        db.execute("INSERT OR IGNORE INTO attempts VALUES (1,0,0)")
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        failures, locked_until = db.execute("SELECT failures,locked_until FROM attempts WHERE id=1").fetchone()
        now = time.time()
        if locked_until > now:
            audit("auth.failed", reason_code="temporarily_rate_limited")
            return False
        if locked_until:
            failures = 0
        try:
            stored = PASSKEY_FILE.read_text(encoding="utf-8").strip()
            parameters = extract_parameters(stored)
            if not (1 <= parameters.time_cost <= 10 and 8192 <= parameters.memory_cost <= 262144 and 1 <= parameters.parallelism <= 16):
                raise ValueError("Unsupported stored authentication parameters.")
            valid = ph.verify(stored, passphrase)
        except (VerificationError, InvalidHashError, ValueError):
            failures += 1
            locked_until = now + 30 if failures >= 5 else 0
            db.execute("UPDATE attempts SET failures=?,locked_until=? WHERE id=1", (failures, locked_until))
            audit("auth.failed", reason_code="credential_rejected")
            return False
        db.execute("UPDATE attempts SET failures=0,locked_until=0 WHERE id=1")
        if valid and ph.check_needs_rehash(stored):
            atomic_write(PASSKEY_FILE, ph.hash(passphrase).encode("utf-8"))
        audit("auth.verified", reason_code="owner_passkey_verified")
        return True

class AuthenticatedPassphrase(str):
    """Compatibility with existing encryption readers; never pass to a model."""
    def __repr__(self) -> str:
        return "<authenticated owner credential>"

def authenticate_passphrase(passphrase: str, *, operation: str = "session.open", payload: Any = None) -> AuthenticatedPassphrase:
    if not verify_passkey(passphrase):
        raise PermissionError("Authentication failed.")
    proof = AuthenticatedPassphrase(passphrase)
    nonce = secrets.token_urlsafe(32)
    proof._nonce = nonce
    now = time.monotonic()
    with _LOCK:
        for key in list(_PROOFS):
            if _PROOFS[key]["expires"] <= now:
                del _PROOFS[key]
        _PROOFS[nonce] = {
            "object": proof, "operation": operation, "payload": payload_digest(payload),
            "expires": now + FRESH_SECONDS, "generation": credential_generation(),
        }
    return proof

def require_passkey(*, operation: str = "session.open", payload: Any = None) -> AuthenticatedPassphrase:
    # Trusted local UI entry point; no password argument is accepted over the API.
    entered = _private_input("Authenticate with ZÆNIA passkey: ")
    return authenticate_passphrase(entered, operation=operation, payload=payload)

def consume_fresh_auth(passphrase: str, *, operation: str, payload: Any = None) -> None:
    if not isinstance(passphrase, AuthenticatedPassphrase):
        raise PermissionError("Fresh owner authentication is required for this change.")
    with _LOCK:
        record = _PROOFS.get(getattr(passphrase, "_nonce", ""))
        if not record or record["object"] is not passphrase:
            raise PermissionError("Authentication proof is invalid or already used.")
        if record["expires"] <= time.monotonic() or record["generation"] != credential_generation():
            del _PROOFS[passphrase._nonce]
            raise PermissionError("Authentication proof expired; authenticate again.")
        if record["operation"] != operation or record["payload"] != payload_digest(payload):
            raise PermissionError("Authentication was for a different operation or payload.")
        del _PROOFS[passphrase._nonce]
