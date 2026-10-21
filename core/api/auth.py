"""Local client tokens; token authentication never grants owner administration."""
from __future__ import annotations
import argparse
import hashlib
import re
import secrets
from typing import Callable
from core.foundation.auth.passkey import consume_fresh_auth, require_passkey
from core.foundation.security.audit import audit
from core.foundation.security.io import atomic_write, file_lock, reject_link
from core.foundation.storage.paths import SECURE_DIR, ensure_storage

API_TOKEN_HASH_FILE = SECURE_DIR / "api_access.sha256"
API_TOKEN_HEADER = "X-ZAENIA-API-TOKEN"
CLIENT_CAPABILITIES = frozenset({"chat.reply", "briefing.generate", "carplay.session.update", "carplay.audio.read", "status.read",
    "tasks.read", "calendar.read", "files.read", "ui.tasks.write", "ui.tasks.delete", "ui.calendar.write", "ui.calendar.delete", "chat.history.read", "chat.speak", "files.propose", "files.desktop.apply", "voice.transcribe",
    "memory.read", "memory.write", "notifications.read", "notifications.write", "assistant.settings.write"})
from core.assistant_platform.capabilities import PLATFORM_CAPABILITIES
CLIENT_CAPABILITIES = CLIENT_CAPABILITIES | PLATFORM_CAPABILITIES

def hash_api_token(token: str) -> str:
    if not isinstance(token, str) or not token.strip() or len(token) > 512:
        raise ValueError("Invalid API token.")
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

def api_token_exists() -> bool:
    reject_link(API_TOKEN_HASH_FILE)
    return API_TOKEN_HASH_FILE.is_file()

def _current_digest() -> str:
    if not api_token_exists():
        return ""
    return API_TOKEN_HASH_FILE.read_text(encoding="ascii").strip()

def save_api_token_hash(token: str, *, overwrite: bool = False, passphrase: str | None = None) -> None:
    """Compatibility saver, now protected by exact, fresh owner authentication."""
    ensure_storage()
    digest = hash_api_token(token)
    operation = "auth.token.rotate" if overwrite else "auth.token.create"
    previous = _current_digest()
    if previous and not overwrite:
        raise RuntimeError("API credential already exists; use explicit rotation.")
    if overwrite and not previous:
        raise RuntimeError("No API credential exists to rotate.")
    binding = {"new_digest": digest, "previous_digest": previous}
    consume_fresh_auth(passphrase, operation=operation, payload=binding)
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(passphrase,operation)
    with file_lock(API_TOKEN_HASH_FILE.with_suffix(".lock")):
        if _current_digest() != previous:
            raise RuntimeError("API credential changed concurrently; authenticate again.")
        atomic_write(API_TOKEN_HASH_FILE, digest.encode("ascii"), overwrite=overwrite)
    audit("api.credential_changed", operation=operation, reason_code="hash_only")

def verify_api_token(token: str) -> bool:
    try:
        supplied = hash_api_token(token)
        expected = _current_digest()
        return bool(re.fullmatch(r"[0-9a-f]{64}", expected) and secrets.compare_digest(supplied, expected))
    except (ValueError, OSError, UnicodeError, PermissionError):
        return False

def generate_api_token() -> str:
    return secrets.token_urlsafe(32)

def _new_token(*, rotate: bool) -> str:
    token = generate_api_token()
    previous = _current_digest()
    if bool(previous) != rotate:
        raise RuntimeError("Use create for the first credential or rotate for an existing credential.")
    operation = "auth.token.rotate" if rotate else "auth.token.create"
    proof = require_passkey(operation=operation, payload={"new_digest": hash_api_token(token), "previous_digest": previous})
    save_api_token_hash(token, overwrite=rotate, passphrase=proof)
    return token

def create_api_token() -> str:
    return _new_token(rotate=False)

def rotate_api_token() -> str:
    return _new_token(rotate=True)

def revoke_api_token(passphrase: str | None = None) -> None:
    previous = _current_digest()
    if not previous:
        raise RuntimeError("No API credential exists to revoke.")
    binding = {"previous_digest": previous}
    proof = passphrase if passphrase is not None else require_passkey(operation="auth.token.revoke", payload=binding)
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(proof,"auth.token.revoke")
    consume_fresh_auth(proof, operation="auth.token.revoke", payload=binding)
    with file_lock(API_TOKEN_HASH_FILE.with_suffix(".lock")):
        if _current_digest() != previous:
            raise RuntimeError("API credential changed concurrently; authenticate again.")
        reject_link(API_TOKEN_HASH_FILE)
        API_TOKEN_HASH_FILE.unlink()
    audit("api.credential_revoked", operation="auth.token.revoke", reason_code="client_access_revoked")

def build_memory_token_verifier(expected_token: str) -> Callable[[str], bool]:
    expected = hash_api_token(expected_token)
    def verifier(supplied_token: str) -> bool:
        try:
            return secrets.compare_digest(hash_api_token(supplied_token), expected)
        except ValueError:
            return False
    return verifier

def main() -> None:
    parser = argparse.ArgumentParser(description="ZÆNIA local API credential management")
    parser.add_argument("command", choices=["create", "rotate", "revoke", "status"])
    command = parser.parse_args().command
    if command == "status":
        require_passkey()
        print("API credential: " + ("configured" if api_token_exists() else "not configured"))
    elif command == "revoke":
        revoke_api_token()
        print("API credential revoked. Existing clients must be paired again.")
    else:
        token = rotate_api_token() if command == "rotate" else create_api_token()
        print("Credential shown once locally. Keep it private; do not paste it into chat.")
        print(token)

if __name__ == "__main__":
    main()
