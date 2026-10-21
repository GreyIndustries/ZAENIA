"""Apply enabled scoped denials to owner management entry points too."""
from core.foundation.security.audit import audit

def assert_owner_scope(passphrase: str, operation: str) -> None:
    from core.foundation.rules.vault import load_vault,CANONICAL_HARD
    from core.foundation.rules.models import OPERATIONS
    if operation not in OPERATIONS:
        raise PermissionError("Unknown owner management operation.")
    vault=load_vault(passphrase)
    if any(r["enabled"] and r["id"] not in CANONICAL_HARD and r["action"]=="deny"
           and ("*" in r["operations"] or operation in r["operations"]) for r in vault["rules"]):
        audit("owner.action_denied",operation=operation,reason_code="scoped_rule_denied")
        raise PermissionError("An enabled scoped rule denies this owner operation.")
