"""Optional phone PIN: stands in for the voice check on a rough line (the spoken phrase is still required).

Stored only as an Argon2 hash in data/secure/phone_pin.hash; set with
`python -m core.telephony pin` (owner passkey). One PIN try per call.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIN_FILE = PROJECT_ROOT / "data" / "secure" / "phone_pin.hash"


def _hasher():
    from argon2 import PasswordHasher
    return PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)


def pin_exists(pin_file: Path = PIN_FILE) -> bool:
    return Path(pin_file).is_file()


def set_pin(pin: str, pin_file: Path = PIN_FILE) -> None:
    if not re.fullmatch(r"\d{6,8}", pin or ""):
        raise ValueError("Use 6 to 8 digits.")
    if len(set(pin)) < 3 or pin in "0123456789" or pin in "9876543210":
        raise ValueError("That PIN is too easy to guess.")
    from core.foundation.security.io import atomic_write
    atomic_write(Path(pin_file), _hasher().hash(pin).encode("utf-8"))


def pin_matches(pin: str, pin_file: Path = PIN_FILE) -> bool:
    if not re.fullmatch(r"\d{6,8}", pin or "") or not pin_exists(pin_file):
        return False
    try:
        return _hasher().verify(Path(pin_file).read_text(encoding="utf-8"), pin)
    except Exception:
        return False
