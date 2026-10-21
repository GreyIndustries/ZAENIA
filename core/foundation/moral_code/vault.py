"""Encrypted owner moral policy with immutable principles and reviewed notes."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from core.foundation.auth.passkey import consume_fresh_auth, payload_digest
from core.foundation.security.audit import audit
from core.foundation.security.crypto import decrypt_text_scoped, encrypt_text_scoped
from core.foundation.security.io import atomic_write, file_lock, reject_link
from core.foundation.storage.paths import MORAL_VAULT_FILE

SCOPE = "moral_code_v1"
DEFAULT_CHARTER_SHA256 = "262b4ac1d25339886878807c11a305d7c350b3a876796d1cb4599ea494304b0c"

def default_charter() -> dict:
    path = Path(__file__).with_name("charter.json")
    reject_link(path)
    encoded = path.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != DEFAULT_CHARTER_SHA256:
        raise PermissionError("The moral-code source charter changed. Restore the reviewed package.")
    return json.loads(encoded.decode("utf-8"))

def validate_policy(policy: dict) -> dict:
    baseline = default_charter()
    if not isinstance(policy, dict) or set(policy) != {"version", "charter", "notes"} or type(policy["version"]) is not int or policy["version"] != 1 or policy["charter"] != baseline:
        raise PermissionError("Protected moral principles were changed.")
    notes = policy["notes"]
    if not isinstance(notes, list) or len(notes) > 500:
        raise ValueError("Malformed moral notes.")
    if any(not isinstance(note, str) or len(note) > 4000 for note in notes):
        raise ValueError("Invalid moral note.")
    return copy.deepcopy(policy)

def load_policy(passphrase: str) -> dict:
    reject_link(MORAL_VAULT_FILE)
    if not MORAL_VAULT_FILE.is_file():
        raise RuntimeError("Moral policy is missing. Run foundation verify.")
    text = decrypt_text_scoped(MORAL_VAULT_FILE.read_bytes(), passphrase, scope=SCOPE)
    return validate_policy(json.loads(text))

def _write_policy(policy: dict, passphrase: str, *, expected_digest: str | None = None) -> None:
    draft = validate_policy(policy)
    ciphertext = encrypt_text_scoped(json.dumps(draft, ensure_ascii=False), passphrase, scope=SCOPE)
    with file_lock(MORAL_VAULT_FILE.with_suffix(".lock")):
        reject_link(MORAL_VAULT_FILE)
        current = hashlib.sha256(MORAL_VAULT_FILE.read_bytes()).hexdigest() if MORAL_VAULT_FILE.exists() else ""
        if expected_digest is not None and current != expected_digest:
            raise RuntimeError("Moral policy changed concurrently; review it again.")
        atomic_write(MORAL_VAULT_FILE, ciphertext)
    audit("moral.saved", reason_code="encrypted_moral_policy_committed")

def create_policy(passphrase: str) -> None:
    if MORAL_VAULT_FILE.exists():
        raise RuntimeError("Moral policy already exists; refusing to overwrite it.")
    consume_fresh_auth(passphrase, operation="moral.create", payload={"charter_sha256": DEFAULT_CHARTER_SHA256})
    _write_policy({"version": 1, "charter": default_charter(), "notes": []}, passphrase, expected_digest="")

def update_notes(notes: list[str], passphrase: str) -> None:
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(passphrase,"moral.notes.update")
    digest = hashlib.sha256(MORAL_VAULT_FILE.read_bytes()).hexdigest()
    policy = load_policy(passphrase)
    draft = validate_policy({**policy, "notes": notes})
    consume_fresh_auth(passphrase, operation="moral.notes.update", payload={"notes_digest": payload_digest(notes)})
    _write_policy(draft, passphrase, expected_digest=digest)
