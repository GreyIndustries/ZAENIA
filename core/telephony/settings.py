"""Phone-line settings and the Twilio credential.

Settings (no secrets) are in data/telephony/config.json. The Twilio auth token
is sealed to Grey's Windows account with DPAPI in data/secure/twilio_token.dpapi,
so it can't be read by another account or copied off this PC. Both are written
only by `python -m core.telephony setup`, which asks for the owner passkey.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "data" / "telephony" / "config.json"
TOKEN_FILE = PROJECT_ROOT / "data" / "secure" / "twilio_token.dpapi"
_PHONE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_number(value: str) -> str:
    """E.164 (+15551234567); a 10-digit US number gets +1. Raises ValueError otherwise."""
    digits = re.sub(r"[^\d+]", "", str(value or ""))
    if re.fullmatch(r"\d{10}", digits):
        digits = "+1" + digits
    elif re.fullmatch(r"1\d{10}", digits):
        digits = "+" + digits
    if not _PHONE.match(digits):
        raise ValueError(f"Not a phone number in international form: {value!r}")
    return digits


def load(config_file: Path = CONFIG_FILE) -> dict[str, Any]:
    try:
        data = json.loads(Path(config_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(record: dict[str, Any], config_file: Path = CONFIG_FILE) -> None:
    from core.foundation.security.io import atomic_write
    atomic_write(Path(config_file), json.dumps(record, indent=2).encode("utf-8"))


def ready(config: dict[str, Any] | None = None) -> bool:
    config = load() if config is None else config
    return bool(config.get("enabled") and config.get("account_sid") and config.get("zae_number")
                and config.get("owner_numbers") and config.get("public_base_url"))


def is_owner_number(number: str, config: dict[str, Any] | None = None) -> bool:
    config = load() if config is None else config
    try:
        return normalize_number(number) in {normalize_number(item) for item in config.get("owner_numbers") or []}
    except ValueError:
        return False


def store_token(token: str, token_file: Path = TOKEN_FILE) -> None:
    from core.foundation.security.io import atomic_write
    from core.voice_security.windows_protection import protect
    atomic_write(Path(token_file), protect(token.strip().encode("utf-8")))


def auth_token(token_file: Path = TOKEN_FILE) -> str:
    from core.voice_security.windows_protection import protect
    return protect(Path(token_file).read_bytes(), decrypt=True).decode("utf-8")
