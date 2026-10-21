"""Owner-approved policy snapshot for a restricted, authenticated API service."""
from __future__ import annotations
from core.foundation.auth.passkey import consume_fresh_auth, credential_generation
from core.foundation.moral_code.vault import load_policy
from core.foundation.rules.engine import RuleEngine
from core.foundation.rules.models import OPERATIONS
from core.foundation.rules.vault import CANONICAL_HARD, load_vault
from core.foundation.security.audit import audit

CLIENT_CAPABILITIES = frozenset({"chat.reply","briefing.generate","carplay.session.update","carplay.audio.read","status.read",
    "tasks.read","calendar.read","files.read","ui.tasks.write","ui.tasks.delete","ui.calendar.write","ui.calendar.delete","chat.history.read","chat.speak","files.propose","files.desktop.apply","voice.transcribe",
    "memory.read","memory.write","notifications.read","notifications.write","assistant.settings.write"})
from core.assistant_platform.capabilities import PLATFORM_CAPABILITIES
CLIENT_CAPABILITIES = CLIENT_CAPABILITIES | PLATFORM_CAPABILITIES

class ScopedClientGate:
    def __init__(self, passphrase: str):
        consume_fresh_auth(passphrase,operation="api.service.open",payload={"capabilities":sorted(CLIENT_CAPABILITIES)})
        self._rules = load_vault(passphrase)["rules"]
        load_policy(passphrase)
        self._policy_generation = RuleEngine._policy_generation()
        self._owner_generation = credential_generation()

    def authorize(self, operation: str) -> bool:
        # Caller must have already verified the current client token on this request.
        if operation not in CLIENT_CAPABILITIES or OPERATIONS[operation].sensitive:
            return False
        try:
            if self._policy_generation != RuleEngine._policy_generation() or self._owner_generation != credential_generation():
                raise PermissionError("Policy or owner credential changed; restart and authenticate the API service.")
        except OSError as error:
            raise PermissionError("API service policy is unavailable.") from error
        matched = [r for r in self._rules if r["enabled"] and r["id"] not in CANONICAL_HARD and ("*" in r["operations"] or operation in r["operations"])]
        allowed = not any(r["action"] in ("deny","require_reauth") for r in matched)
        audit("api.capability_checked",operation=operation,reason_code="scoped_client_allowed" if allowed else "scoped_client_denied")
        return allowed
