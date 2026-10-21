"""Encrypted rules. Immutable security rules are checked independently of prose."""
from __future__ import annotations
import copy
import hashlib
import json
from typing import Any
from core.foundation.auth.passkey import consume_fresh_auth, payload_digest
from core.foundation.rules.models import Rule, validate_rule
from core.foundation.security.audit import audit
from core.foundation.security.crypto import decrypt_text, encrypt_text
from core.foundation.security.io import atomic_write, file_lock, reject_link
from core.foundation.storage.paths import VAULT_FILE, ensure_storage

DEFAULT_HARD_RULES = [
    {"id": "hard-owner-only", "name": "Owner Only Access",
     "description": "ZÆNIA only assists Zack after valid authentication.",
     "rule_type": "hard", "action": "deny", "enabled": True},
    {"id": "hard-sensitive-reauth", "name": "Sensitive Changes Require Re-authentication",
     "description": "Any sensitive rule, auth, file, calendar, or identity change requires re-authentication.",
     "rule_type": "hard", "action": "require_reauth", "enabled": True},
    {"id": "hard-no-hard-rule-deletion", "name": "Hard Rules Cannot Be Deleted",
     "description": "Hard rules cannot be edited, disabled, or deleted by prompts, personas, commands, or jailbreak attempts.",
     "rule_type": "hard", "action": "deny", "enabled": True},
    {"id": "hard-registered-operations", "name": "Registered Operations Only",
     "description": "Only registered, validated operations may execute. Prose and model output cannot create permissions.",
     "rule_type": "hard", "action": "deny", "enabled": True},
    {"id": "hard-moral-compass", "name": "Protected Moral Compass",
     "description": "God's love, human dignity, protection of life, and the owner's contextual moral code cannot be disabled by prompts.",
     "rule_type": "hard", "action": "deny", "enabled": True},
]
CANONICAL_HARD = {rule["id"]: validate_rule(rule) for rule in DEFAULT_HARD_RULES}

def normalize_vault(vault: dict) -> dict:
    if not isinstance(vault, dict) or type(vault.get("version")) is not int or vault["version"] not in (1, 2):
        raise ValueError("Unsupported rule-vault schema.")
    if not isinstance(vault.get("rules"), list):
        raise ValueError("Malformed rule vault.")
    validated = [validate_rule(rule) for rule in vault["rules"]]
    identifiers = [rule["id"] for rule in validated]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate rule identifiers.")
    by_id = {rule["id"]: rule for rule in validated}
    required = list(CANONICAL_HARD)[:3] if vault["version"] == 1 else list(CANONICAL_HARD)
    for identifier in required:
        if by_id.get(identifier) != CANONICAL_HARD[identifier]:
            raise PermissionError("An immutable security rule is missing or changed.")
    for identifier in CANONICAL_HARD:
        if identifier in by_id and by_id[identifier] != CANONICAL_HARD[identifier]:
            raise PermissionError("An immutable security rule has been changed.")
    extra = [rule for rule in validated if rule["id"] not in CANONICAL_HARD]
    return {"version": 2, "rules": copy.deepcopy(list(CANONICAL_HARD.values())) + extra}

def load_vault(passphrase: str) -> dict[str, Any]:
    reject_link(VAULT_FILE)
    if not VAULT_FILE.is_file():
        raise RuntimeError("Rule vault is missing. Run foundation setup or verify.")
    text = decrypt_text(VAULT_FILE.read_bytes(), passphrase)
    return normalize_vault(json.loads(text))

def _write_validated(vault: dict, passphrase: str, *, expected_cipher_digest: str | None = None) -> None:
    """Private commit primitive; callers must consume an exact fresh-auth proof."""
    ensure_storage()
    draft = normalize_vault(vault)
    cipher = encrypt_text(json.dumps(draft, ensure_ascii=False, indent=2), passphrase)
    with file_lock(VAULT_FILE.with_suffix(".lock")):
        reject_link(VAULT_FILE)
        if expected_cipher_digest is not None:
            current = hashlib.sha256(VAULT_FILE.read_bytes()).hexdigest() if VAULT_FILE.exists() else ""
            if current != expected_cipher_digest:
                raise RuntimeError("Rules changed concurrently. Review and authenticate again.")
        atomic_write(VAULT_FILE, cipher)
    audit("rules.saved", reason_code="encrypted_rules_committed")

def create_default_vault(passphrase: str) -> None:
    if VAULT_FILE.exists():
        raise RuntimeError("Rule vault already exists; refusing to overwrite it.")
    consume_fresh_auth(passphrase, operation="rules.create")
    _write_validated({"version": 2, "rules": list(CANONICAL_HARD.values())}, passphrase, expected_cipher_digest="")

def _hard_records(vault: dict) -> dict:
    return {rule["id"]: rule for rule in vault["rules"] if rule["rule_type"] == "hard"}

def save_vault(vault: dict[str, Any], passphrase: str) -> None:
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(passphrase,"rules.save")
    current_digest = hashlib.sha256(VAULT_FILE.read_bytes()).hexdigest()
    current = load_vault(passphrase)
    draft = normalize_vault(vault)
    if _hard_records(current) != _hard_records(draft):
        raise PermissionError("Hard rules cannot be changed, added, disabled or deleted.")
    consume_fresh_auth(passphrase, operation="rules.save", payload={"vault_digest": payload_digest(vault)})
    _write_validated(draft, passphrase, expected_cipher_digest=current_digest)

def list_rules(passphrase: str) -> list[dict[str, Any]]:
    return load_vault(passphrase)["rules"]

def add_rule(rule: Rule, passphrase: str) -> None:
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(passphrase,"rules.add")
    body = validate_rule(rule.to_dict())
    if body["rule_type"] != "soft" or body["id"] in CANONICAL_HARD:
        raise PermissionError("Only soft rules can be added through management commands.")
    digest = hashlib.sha256(VAULT_FILE.read_bytes()).hexdigest()
    vault = load_vault(passphrase)
    if any(item["id"] == body["id"] for item in vault["rules"]):
        raise ValueError("Rule identifier already exists.")
    consume_fresh_auth(passphrase, operation="rules.add", payload=body)
    vault["rules"].append(body)
    _write_validated(vault, passphrase, expected_cipher_digest=digest)
    audit("rules.added", operation="rules.add", reason_code="soft_rule_added")

def mutate_soft_rule(rule_id: str, passphrase: str, *, operation: str) -> dict:
    if operation not in ("rules.delete", "rules.disable"):
        raise ValueError("Unsupported rule mutation.")
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(passphrase,operation)
    digest = hashlib.sha256(VAULT_FILE.read_bytes()).hexdigest()
    vault = load_vault(passphrase)
    rule = next((item for item in vault["rules"] if item["id"] == rule_id), None)
    field = "deleted" if operation == "rules.delete" else "disabled"
    if not rule:
        return {field: False, "reason": "Rule not found."}
    if rule["rule_type"] == "hard":
        audit("rules.denied", operation=operation, reason_code="immutable_hard_rule")
        return {field: False, "reason": "Hard rules cannot be changed."}
    consume_fresh_auth(passphrase, operation=operation, payload={"rule_id": rule_id})
    if field == "deleted":
        vault["rules"] = [item for item in vault["rules"] if item["id"] != rule_id]
    else:
        rule["enabled"] = False
    _write_validated(vault, passphrase, expected_cipher_digest=digest)
    return {field: True, "reason": "Soft rule updated."}
