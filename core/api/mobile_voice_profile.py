"""Owner-approved, Windows-account-sealed reference for browser voice sign-in.

The reference contains only the enrolled embedding and calibrated threshold.
The passphrase, raw audio, rule vault, and API token are never cached here.
"""
from __future__ import annotations

import argparse
import hashlib
import json

from core.foundation.auth.passkey import credential_generation, consume_fresh_auth, require_passkey
from core.foundation.security.io import atomic_write, protect_storage, reject_link
from core.foundation.storage.paths import SECURE_DIR, SPEAKER_PROFILE_FILE
from core.voice_security.windows_protection import protect

CACHE = SECURE_DIR / "mobile_voice.dpapi"
CALIBRATION = SECURE_DIR / "speaker_auth_calibration.yaml"


def digest(path) -> str:
    reject_link(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generation() -> dict:
    return {"owner": credential_generation(), "profile": digest(SPEAKER_PROFILE_FILE),
            "calibration": digest(CALIBRATION)}


def session_generation() -> tuple[str, str]:
    return json.dumps(generation(), sort_keys=True), digest(CACHE)


def configured() -> bool:
    reject_link(CACHE)
    return CACHE.is_file()


def load() -> dict:
    reject_link(CACHE)
    if not CACHE.is_file() or CACHE.stat().st_size > 32_000:
        raise PermissionError("Enable mobile voice sign-in once on your PC.")
    baseline = generation()
    snapshot = json.loads(protect(CACHE.read_bytes(), decrypt=True))
    if snapshot.get("version") != 1 or snapshot.get("generation") != baseline or generation() != baseline:
        raise PermissionError("Your voice profile changed. Enable mobile voice sign-in again on your PC.")
    from core.voice_security.gate import validate_calibration
    validate_calibration(snapshot["calibration"], snapshot["profile_id"], baseline["profile"])
    import math
    values = snapshot.get("embedding")
    if not isinstance(values, list) or not 64 <= len(values) <= 2048 or not all(
        type(value) in (int, float) and math.isfinite(value) for value in values
    ) or sum(value * value for value in values) <= 0:
        raise PermissionError("The enrolled voice reference is invalid.")
    return snapshot


def enable() -> None:
    import yaml
    from core.foundation.auth.speaker_profile import load_encrypted_profile
    from core.foundation.rules.policy import assert_owner_scope
    from core.voice_security.gate import validate_calibration
    baseline = generation()
    binding = {"purpose": "mobile.voice.signin", **baseline}
    proof = require_passkey(operation="voice.service.open", payload=binding)
    assert_owner_scope(proof, "voice.service.open")
    consume_fresh_auth(proof, operation="voice.service.open", payload=binding)
    profile = load_encrypted_profile(proof)
    calibration = yaml.safe_load(CALIBRATION.read_text(encoding="utf-8"))
    validate_calibration(calibration, profile["profile_id"], baseline["profile"])
    snapshot = {"version": 1, "generation": baseline, "profile_id": profile["profile_id"],
                "embedding": profile["speaker_embedding"], "calibration": calibration}
    if generation() != baseline:
        raise PermissionError("Voice enrollment changed during setup. Run setup again.")
    sealed = protect(json.dumps(snapshot, allow_nan=False).encode("utf-8"))
    protect_storage(SECURE_DIR)
    atomic_write(CACHE, sealed)
    from core.foundation.security.audit import audit
    audit("mobile.voice_enabled", operation="voice.service.open", reason_code="account_sealed_reference")
    print("Mobile voice sign-in enabled. Open Zae on your phone and choose Verify my voice.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["enable", "disable", "status"])
    args = parser.parse_args()
    if args.command == "enable":
        enable()
    elif args.command == "disable":
        reject_link(CACHE)
        CACHE.unlink(missing_ok=True)
        from core.foundation.security.audit import audit
        audit("mobile.voice_disabled", operation="voice.service.open", reason_code="browser_sessions_revoked")
        print("Mobile voice sign-in disabled; existing voice sessions are revoked.")
    else:
        print("Mobile voice sign-in configured." if configured() else "One-time PC setup required.")


if __name__ == "__main__":
    main()
