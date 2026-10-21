"""Desktop approval key: proof that a request comes from the ZÆNIA desktop app.

The phone carries only the API token. Applying a file change also needs this
key, which lives in the user profile (%APPDATA%\\ZAENIA on Windows,
~/.config/zaenia on Linux) where the desktop app and the local server can read
it and the phone never can.
Creating or replacing it needs the owner passkey at the PC:

    python -m core.api.server pair-desktop
"""
from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

KEY_HEADER = "X-ZAENIA-DESKTOP-KEY"


def key_path() -> Path:
    override = os.environ.get("ZAENIA_DESKTOP_KEY_FILE")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "ZAENIA" / "desktop_approval.key"
    config = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config) / "zaenia" / "desktop_approval.key"


def _stored() -> str | None:
    path = key_path()
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 200:
            return None
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value if len(value) >= 32 else None


def is_paired() -> bool:
    return _stored() is not None


def verify(supplied: str | None) -> bool:
    stored = _stored()
    if not stored or not supplied:
        return False
    return secrets.compare_digest(
        hashlib.sha256(supplied.strip().encode("utf-8")).digest(),
        hashlib.sha256(stored.encode("utf-8")).digest(),
    )


def pair_desktop() -> Path:
    """Create (or replace) the key after the owner passkey is entered locally."""
    from core.foundation.auth.passkey import consume_fresh_auth, require_passkey
    from core.foundation.security.audit import audit
    from core.foundation.security.io import atomic_write

    key = secrets.token_urlsafe(32)
    payload = {"purpose": "desktop_approval_key", "new_digest": hashlib.sha256(key.encode("utf-8")).hexdigest()}
    proof = require_passkey(operation="auth.token.create", payload=payload)
    consume_fresh_auth(proof, operation="auth.token.create", payload=payload)
    path = key_path()
    atomic_write(path, key.encode("utf-8"))
    audit("api.desktop_paired", operation="auth.token.create", reason_code="desktop_approval_key")
    return path
