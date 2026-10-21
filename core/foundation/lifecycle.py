"""Authenticated migration and portable encrypted policy backup/restore."""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
from core.foundation.auth.passkey import consume_fresh_auth
from core.foundation.moral_code.vault import DEFAULT_CHARTER_SHA256, default_charter, load_policy, _write_policy
from core.foundation.moral_code.scripture_context import CONTEXT_FILE, CONTEXT_SCOPE, Corpus
from core.foundation.rules.vault import CANONICAL_HARD, load_vault, normalize_vault, _write_validated
from core.foundation.security.audit import audit
from core.foundation.security.crypto import _derive_key_from_salt, decrypt_text, decrypt_text_scoped
from core.foundation.security.io import atomic_write, file_lock, protect_storage, reject_link
from core.foundation.storage.paths import SECURE_DIR, VAULT_FILE, MORAL_VAULT_FILE, SALT_FILE, ensure_storage

POLICY_FILES = {p.name:p for p in (VAULT_FILE,MORAL_VAULT_FILE,CONTEXT_FILE,SALT_FILE)}
BACKUP_MAGIC = b"ZAENIA-POLICY-BACKUP-1\n"

def _digest(path: Path) -> str:
    reject_link(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""

def activation_binding() -> dict:
    return {"rules":_digest(VAULT_FILE),"moral":_digest(MORAL_VAULT_FILE),"salt":_digest(SALT_FILE),"charter":DEFAULT_CHARTER_SHA256}

def activate_foundation(passphrase: str, binding: dict) -> dict:
    """Upgrade legacy encrypted rules without changing the existing key/salt."""
    consume_fresh_auth(passphrase,operation="foundation.upgrade",payload=binding)
    ensure_storage()
    with file_lock(SECURE_DIR / "foundation_upgrade.lock"):
        if binding != activation_binding():
            raise RuntimeError("Protected files changed while authenticating. Retry verify.")
        vault = load_vault(passphrase) if VAULT_FILE.exists() else {"version":2,"rules":list(CANONICAL_HARD.values())}
        policy = load_policy(passphrase) if MORAL_VAULT_FILE.exists() else {"version":1,"charter":default_charter(),"notes":[]}
        # Decrypt and validate every existing file before modifying either policy.
        originals = {path:path.read_bytes() if path.exists() else None for path in (VAULT_FILE,MORAL_VAULT_FILE)}
        protect_storage(SECURE_DIR)
        if any(data is not None for data in originals.values()):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            directory = SECURE_DIR / "policy_versions" / stamp
            directory.mkdir(parents=True)
            for path,data in originals.items():
                if data is not None:
                    atomic_write(directory / path.name,data,overwrite=False)
            if SALT_FILE.exists():
                atomic_write(directory / SALT_FILE.name,SALT_FILE.read_bytes(),overwrite=False)
        try:
            _write_validated(vault,passphrase,expected_cipher_digest=binding["rules"])
            _write_policy(policy,passphrase,expected_digest=binding["moral"])
            load_vault(passphrase)
            load_policy(passphrase)
        except BaseException:
            for path,data in originals.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path,data)
            raise
        permissions = protect_storage(SECURE_DIR)
    audit("foundation.activated",reason_code="authenticated_upgrade")
    return {"rules":len(vault["rules"]),"moral_principles":len(policy["charter"]["principles"]),"permissions":permissions}

def backup_binding(destination: Path) -> dict:
    destination = Path(destination).absolute()
    reject_link(destination)
    if destination.exists():
        raise FileExistsError("Choose a new backup filename.")
    return {"destination":str(destination),"files":{n:_digest(p) for n,p in POLICY_FILES.items()}}

def export_policy_backup(destination: Path, passphrase: str, binding: dict) -> None:
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(passphrase,"security.backup")
    consume_fresh_auth(passphrase,operation="security.backup",payload=binding)
    if binding != backup_binding(destination):
        raise RuntimeError("Backup inputs changed while authenticating.")
    load_vault(passphrase)
    load_policy(passphrase)
    document = {"version":1,"files":{name:base64.b64encode(path.read_bytes()).decode("ascii") for name,path in POLICY_FILES.items() if path.exists()}}
    salt = os.urandom(16)
    scoped = hashlib.sha256(salt+b"\x00ZAENIA-POLICY-BACKUP\x00").digest()[:16]
    cipher = Fernet(_derive_key_from_salt(passphrase,scoped)).encrypt(json.dumps(document).encode())
    atomic_write(Path(destination).absolute(),BACKUP_MAGIC+salt+cipher,overwrite=False)
    audit("policy.backup_exported",operation="security.backup",reason_code="portable_encrypted_backup")

def restore_binding(source: Path) -> dict:
    return {"source_digest":_digest(source),"current_files":{n:_digest(p) for n,p in POLICY_FILES.items()}}

def restore_policy_backup(source: Path, passphrase: str, binding: dict) -> None:
    consume_fresh_auth(passphrase,operation="security.restore",payload=binding)
    if binding != restore_binding(source):
        raise RuntimeError("Restore inputs changed while authenticating.")
    raw = Path(source).read_bytes()
    if len(raw) > 32*1024*1024 or not raw.startswith(BACKUP_MAGIC):
        raise ValueError("Invalid policy backup.")
    offset = len(BACKUP_MAGIC)
    salt, cipher = raw[offset:offset+16],raw[offset+16:]
    scoped = hashlib.sha256(salt+b"\x00ZAENIA-POLICY-BACKUP\x00").digest()[:16]
    document = json.loads(Fernet(_derive_key_from_salt(passphrase,scoped)).decrypt(cipher))
    if not isinstance(document,dict) or document.get("version") != 1 or not isinstance(document.get("files"),dict):
        raise ValueError("Malformed policy backup.")
    if set(document["files"]) - set(POLICY_FILES) or not {VAULT_FILE.name,MORAL_VAULT_FILE.name,SALT_FILE.name} <= set(document["files"]):
        raise ValueError("Incomplete or unrecognized policy backup.")
    files = {name:base64.b64decode(value,validate=True) for name,value in document["files"].items()}
    original_salt = files[SALT_FILE.name]
    if len(original_salt) != 16 or (SALT_FILE.exists() and SALT_FILE.read_bytes() != original_salt):
        raise PermissionError("Restore requires the same master salt; other encrypted subsystems must not be damaged.")
    # Validate with the backed-up salt without touching live files first.
    key = _derive_key_from_salt(passphrase,original_salt)
    normalize_vault(json.loads(Fernet(key).decrypt(files[VAULT_FILE.name])))
    from core.foundation.moral_code.vault import validate_policy,SCOPE
    def decrypt_scope(data,scope):
        material = original_salt+b"\x00ZAENIA-SECURE-SCOPE\x00"+scope.encode()
        return json.loads(Fernet(_derive_key_from_salt(passphrase,hashlib.sha256(material).digest()[:16])).decrypt(data))
    validate_policy(decrypt_scope(files[MORAL_VAULT_FILE.name],SCOPE))
    if CONTEXT_FILE.name in files:
        notes = decrypt_scope(files[CONTEXT_FILE.name],CONTEXT_SCOPE)
        if not isinstance(notes,dict) or notes.get("version") != 1 or not isinstance(notes.get("records"),dict):
            raise ValueError("Malformed backed-up context notes.")
    with file_lock(SECURE_DIR / "foundation_upgrade.lock"):
        if binding != restore_binding(source):
            raise RuntimeError("Live policy changed before restore.")
        originals = {path:path.read_bytes() if path.exists() else None for path in POLICY_FILES.values()}
        try:
            for name,path in POLICY_FILES.items():
                if name in files:
                    atomic_write(path,files[name])
                elif path == CONTEXT_FILE:
                    path.unlink(missing_ok=True)
            load_vault(passphrase)
            load_policy(passphrase)
            protect_storage(SECURE_DIR)
        except BaseException:
            for path,data in originals.items():
                if data is None: path.unlink(missing_ok=True)
                else: atomic_write(path,data)
            raise
    audit("policy.backup_restored",operation="security.restore",reason_code="validated_encrypted_backup")
